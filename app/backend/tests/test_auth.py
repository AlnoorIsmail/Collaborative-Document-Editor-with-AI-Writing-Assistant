"""Authentication tests covering both merged auth flows and protected Part B routes."""

from app.backend.tests.conftest import create_test_client

EXPECTED_UNAUTHORIZED = {
    "error_code": "UNAUTHORIZED",
    "message": "Missing or invalid bearer token.",
    "retryable": False,
}


def test_sessions_route_requires_bearer_token(client) -> None:
    response = client.post(
        "/v1/documents/doc_101/sessions",
        json={"last_known_revision": 22},
    )

    assert response.status_code == 401
    assert response.json() == EXPECTED_UNAUTHORIZED


def test_ai_route_requires_bearer_token(client) -> None:
    response = client.get("/v1/documents/doc_101/ai/interactions")

    assert response.status_code == 401
    assert response.json() == EXPECTED_UNAUTHORIZED


def test_register_success() -> None:
    client = create_test_client()

    response = client.post(
        "/v1/auth/register",
        json={
            "email": "alice@example.com",
            "display_name": "Alice",
            "password": "strong-password",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["user_id"] == 1
    assert body["email"] == "alice@example.com"
    assert body["display_name"] == "Alice"
    assert body["account_status"] == "active"
    assert body["created_at"]


def test_duplicate_register_rejected() -> None:
    client = create_test_client()
    payload = {
        "email": "alice@example.com",
        "display_name": "Alice",
        "password": "strong-password",
    }

    first_response = client.post("/v1/auth/register", json=payload)
    second_response = client.post("/v1/auth/register", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 400
    assert second_response.json() == {
        "error_code": "VALIDATION_ERROR",
        "message": "A user with this email already exists.",
        "retryable": False,
    }


def test_login_success() -> None:
    client = create_test_client()
    register_payload = {
        "email": "alice@example.com",
        "display_name": "Alice",
        "password": "strong-password",
    }

    client.post("/v1/auth/register", json=register_payload)
    response = client.post(
        "/v1/auth/login",
        json={"email": "alice@example.com", "password": "strong-password"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"] == {
        "user_id": 1,
        "email": "alice@example.com",
        "display_name": "Alice",
    }


def test_invalid_login_rejected() -> None:
    client = create_test_client()
    client.post(
        "/v1/auth/register",
        json={
            "email": "alice@example.com",
            "display_name": "Alice",
            "password": "strong-password",
        },
    )

    response = client.post(
        "/v1/auth/login",
        json={"email": "alice@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json() == {
        "error_code": "UNAUTHORIZED",
        "message": "Invalid email or password.",
        "retryable": False,
    }


def test_me_returns_current_user_with_valid_auth() -> None:
    client = create_test_client()
    client.post(
        "/v1/auth/register",
        json={
            "email": "alice@example.com",
            "display_name": "Alice",
            "password": "strong-password",
        },
    )
    login_response = client.post(
        "/v1/auth/login",
        json={"email": "alice@example.com", "password": "strong-password"},
    )
    token = login_response.json()["access_token"]

    response = client.get(
        "/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "user_id": 1,
        "email": "alice@example.com",
        "display_name": "Alice",
        "account_status": "active",
    }
