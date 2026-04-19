"""Authentication tests covering both merged auth flows and protected Part B routes."""

from app.backend.core.security import decode_access_token
from app.backend.tests.conftest import create_test_client

EXPECTED_UNAUTHORIZED = {
    "error_code": "UNAUTHORIZED",
    "message": "Missing or invalid bearer token.",
    "retryable": False,
}
EXPECTED_INVALID_TOKEN = {
    "error_code": "UNAUTHORIZED",
    "message": "Invalid or expired token.",
    "retryable": False,
}


def test_sessions_route_requires_bearer_token(client) -> None:
    response = client.post(
        "/v1/documents/1/sessions",
        json={"last_known_revision": 22},
    )

    assert response.status_code == 401
    assert response.json() == EXPECTED_UNAUTHORIZED


def test_ai_route_requires_bearer_token(client) -> None:
    response = client.get("/v1/documents/1/ai/interactions")

    assert response.status_code == 401
    assert response.json() == EXPECTED_UNAUTHORIZED


def test_sessions_route_rejects_placeholder_bearer_token(client) -> None:
    response = client.post(
        "/v1/documents/1/sessions",
        headers={"Authorization": "Bearer usr_1:editor"},
        json={"last_known_revision": 0},
    )

    assert response.status_code == 401
    assert response.json() == EXPECTED_INVALID_TOKEN


def test_ai_route_rejects_placeholder_bearer_token(client) -> None:
    response = client.get(
        "/v1/documents/1/ai/interactions",
        headers={"Authorization": "Bearer usr_1:editor"},
    )

    assert response.status_code == 401
    assert response.json() == EXPECTED_INVALID_TOKEN


def test_register_success() -> None:
    client = create_test_client()

    response = client.post(
        "/v1/auth/register",
        json={
            "email": "alice@example.com",
            "display_name": "Alice",
            "username": "Alice",
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
        "username": "Alice",
        "password": "strong-password",
    }

    first_response = client.post("/v1/auth/register", json=payload)
    second_response = client.post("/v1/auth/register", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json() == {
        "error_code": "CONFLICT",
        "message": "A user with this email already exists.",
        "retryable": False,
    }


def test_duplicate_username_register_rejected() -> None:
    client = create_test_client()

    first_response = client.post(
        "/v1/auth/register",
        json={
            "email": "alice@example.com",
            "display_name": "Alice",
            "username": "Alice",
            "password": "strong-password",
        },
    )
    second_response = client.post(
        "/v1/auth/register",
        json={
            "email": "alice2@example.com",
            "display_name": "Alice Two",
            "username": "alice",
            "password": "strong-password",
        },
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json() == {
        "error_code": "CONFLICT",
        "message": "A user with this username already exists.",
        "retryable": False,
    }


def test_normalized_duplicate_username_register_rejected() -> None:
    client = create_test_client()

    first_response = client.post(
        "/v1/auth/register",
        json={
            "email": "alice@example.com",
            "display_name": "Alice",
            "username": "al-noor",
            "password": "strong-password",
        },
    )
    second_response = client.post(
        "/v1/auth/register",
        json={
            "email": "alice2@example.com",
            "display_name": "Alice Two",
            "username": "al_noor",
            "password": "strong-password",
        },
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json() == {
        "error_code": "CONFLICT",
        "message": "A user with this username already exists.",
        "retryable": False,
    }


def test_username_availability_reports_taken_after_normalization() -> None:
    client = create_test_client()

    register_response = client.post(
        "/v1/auth/register",
        json={
            "email": "alice@example.com",
            "display_name": "Alice",
            "username": "Alice",
            "password": "strong-password",
        },
    )
    availability_response = client.get(
        "/v1/auth/username-availability",
        params={"username": "alice"},
    )

    assert register_response.status_code == 201
    assert availability_response.status_code == 200
    assert availability_response.json() == {
        "username": "alice",
        "normalized_username": "alice",
        "available": False,
    }


def test_username_availability_reports_available_for_fresh_username() -> None:
    client = create_test_client()

    response = client.get(
        "/v1/auth/username-availability",
        params={"username": "new_user"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "username": "new_user",
        "normalized_username": "new_user",
        "available": True,
    }


def test_login_success() -> None:
    client = create_test_client()
    register_payload = {
        "email": "alice@example.com",
        "display_name": "Alice",
        "username": "Alice",
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
    assert body["refresh_token"]
    assert body["access_token_expires_in"] > 0
    assert body["refresh_token_expires_in"] > 0
    assert decode_access_token(body["access_token"])["sub"] == "1"
    assert body["user"] == {
        "user_id": 1,
        "email": "alice@example.com",
        "display_name": "Alice",
    }


def test_login_rejects_unknown_email() -> None:
    client = create_test_client()

    response = client.post(
        "/v1/auth/login",
        json={"email": "missing@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json() == {
        "error_code": "UNAUTHORIZED",
        "message": "No account exists for this email.",
        "retryable": False,
    }


def test_login_rejects_wrong_password() -> None:
    client = create_test_client()
    client.post(
        "/v1/auth/register",
        json={
            "email": "alice@example.com",
            "display_name": "Alice",
            "username": "Alice",
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
        "message": "Incorrect password.",
        "retryable": False,
    }


def test_refresh_rotates_session() -> None:
    client = create_test_client()
    client.post(
        "/v1/auth/register",
        json={
            "email": "alice@example.com",
            "display_name": "Alice",
            "username": "Alice",
            "password": "strong-password",
        },
    )

    login_response = client.post(
        "/v1/auth/login",
        json={"email": "alice@example.com", "password": "strong-password"},
    )
    refresh_token = login_response.json()["refresh_token"]

    refresh_response = client.post(
        "/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert refresh_response.status_code == 200
    assert refresh_response.json()["access_token"]
    assert refresh_response.json()["refresh_token"]
    assert refresh_response.json()["refresh_token"] != refresh_token
    assert refresh_response.json()["user"] == {
        "user_id": 1,
        "email": "alice@example.com",
        "display_name": "Alice",
    }

    reused_refresh_response = client.post(
        "/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert reused_refresh_response.status_code == 401
    assert reused_refresh_response.json() == {
        "error_code": "UNAUTHORIZED",
        "message": "Invalid or expired refresh token.",
        "retryable": False,
    }


def test_me_returns_current_user_with_valid_auth() -> None:
    client = create_test_client()
    client.post(
        "/v1/auth/register",
        json={
            "email": "alice@example.com",
            "display_name": "Alice",
            "username": "Alice",
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


def test_me_rejects_invalid_token() -> None:
    client = create_test_client()

    response = client.get(
        "/v1/auth/me",
        headers={"Authorization": "Bearer invalid.jwt.token"},
    )

    assert response.status_code == 401
    assert response.json() == EXPECTED_INVALID_TOKEN
