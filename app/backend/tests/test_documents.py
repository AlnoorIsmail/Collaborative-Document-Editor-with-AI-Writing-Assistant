from fastapi.testclient import TestClient

from app.backend.tests.conftest import create_test_client


def create_user_and_token(client: TestClient, email: str, display_name: str):
    register_response = client.post(
        "/v1/auth/register",
        json={
            "email": email,
            "display_name": display_name,
            "password": "strong-password",
        },
    )
    user = register_response.json()
    login_response = client.post(
        "/v1/auth/login",
        json={"email": email, "password": "strong-password"},
    )
    token = login_response.json()["access_token"]
    return user, token


def test_create_document_success() -> None:
    client = create_test_client()
    owner, token = create_user_and_token(client, "owner@example.com", "Owner")

    response = client.post(
        "/v1/documents",
        json={
            "title": "My First Document",
            "initial_content": "Hello world",
            "content_format": "rich_text",
            "ai_enabled": True,
        },
        headers={"Authorization": "Bearer {token}".format(token=token)},
    )

    assert response.status_code == 201
    assert response.json()["document_id"] == 1
    assert response.json()["title"] == "My First Document"
    assert response.json()["current_content"] == "Hello world"
    assert response.json()["content_format"] == "rich_text"
    assert response.json()["owner"] == {
        "user_id": owner["user_id"],
        "display_name": "Owner",
    }
    assert response.json()["owner_user_id"] == owner["user_id"]
    assert response.json()["role"] == "owner"
    assert response.json()["ai_enabled"] is True
    assert response.json()["revision"] == 0
    assert response.json()["latest_version_id"] is None
    assert response.json()["latest_version"] is None
    assert response.json()["created_at"]
    assert response.json()["updated_at"]


def test_get_document_success() -> None:
    client = create_test_client()
    owner, token = create_user_and_token(client, "owner@example.com", "Owner")
    create_response = client.post(
        "/v1/documents",
        json={"title": "Readable Doc", "initial_content": "Body"},
        headers={"Authorization": "Bearer {token}".format(token=token)},
    )
    document_id = create_response.json()["document_id"]

    response = client.get(
        "/v1/documents/{document_id}".format(document_id=document_id),
        headers={"Authorization": "Bearer {token}".format(token=token)},
    )

    assert response.status_code == 200
    assert response.json()["document_id"] == document_id
    assert response.json()["title"] == "Readable Doc"
    assert response.json()["current_content"] == "Body"
    assert response.json()["owner"] == {
        "user_id": owner["user_id"],
        "display_name": "Owner",
    }
    assert response.json()["owner_user_id"] == owner["user_id"]
    assert response.json()["role"] == "owner"
    assert response.json()["revision"] == 0
    assert response.json()["created_at"]


def test_update_document_success() -> None:
    client = create_test_client()
    _, token = create_user_and_token(client, "owner@example.com", "Owner")
    create_response = client.post(
        "/v1/documents",
        json={"title": "Original", "initial_content": "Draft"},
        headers={"Authorization": "Bearer {token}".format(token=token)},
    )
    document_id = create_response.json()["document_id"]

    response = client.patch(
        "/v1/documents/{document_id}".format(document_id=document_id),
        json={
            "title": "Updated",
            "ai_enabled": False,
        },
        headers={"Authorization": "Bearer {token}".format(token=token)},
    )

    assert response.status_code == 200
    assert response.json()["document_id"] == document_id
    assert response.json()["title"] == "Updated"
    assert response.json()["ai_enabled"] is False
    assert response.json()["role"] == "owner"
    assert response.json()["updated_at"]
    assert response.json()["current_content"] == "Draft"
    assert response.json()["revision"] == 0


def test_save_document_content_success() -> None:
    client = create_test_client()
    _, token = create_user_and_token(client, "owner@example.com", "Owner")
    create_response = client.post(
        "/v1/documents",
        json={"title": "Original", "initial_content": ""},
        headers={"Authorization": "Bearer {token}".format(token=token)},
    )
    document_id = create_response.json()["document_id"]

    response = client.patch(
        "/v1/documents/{document_id}/content".format(document_id=document_id),
        json={"content": "Final copy", "base_revision": 0},
        headers={"Authorization": "Bearer {token}".format(token=token)},
    )

    assert response.status_code == 200
    assert response.json()["document_id"] == document_id
    assert response.json()["latest_version_id"] == 1
    assert response.json()["revision"] == 1
    assert response.json()["saved_at"]


def test_unauthenticated_access_rejected() -> None:
    client = create_test_client()

    response = client.post(
        "/v1/documents",
        json={"title": "Private Doc", "initial_content": "Secret"},
    )

    assert response.status_code == 401
    assert response.json() == {
        "error_code": "UNAUTHORIZED",
        "message": "Missing or invalid bearer token.",
        "retryable": False,
    }


def test_non_owner_access_rejected() -> None:
    client = create_test_client()
    _, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    _, stranger_token = create_user_and_token(
        client, "stranger@example.com", "Stranger"
    )
    create_response = client.post(
        "/v1/documents",
        json={"title": "Owner Doc", "initial_content": "Secret"},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )
    document_id = create_response.json()["document_id"]

    response = client.get(
        "/v1/documents/{document_id}".format(document_id=document_id),
        headers={"Authorization": "Bearer {token}".format(token=stranger_token)},
    )

    assert response.status_code == 403
    assert response.json() == {
        "error_code": "PERMISSION_DENIED",
        "message": "You are not allowed to access this document.",
        "retryable": False,
    }


def test_list_documents_success() -> None:
    client = create_test_client()
    _, token = create_user_and_token(client, "owner@example.com", "Owner")
    client.post(
        "/v1/documents",
        json={"title": "Doc One", "initial_content": "A"},
        headers={"Authorization": f"Bearer {token}"},
    )
    client.post(
        "/v1/documents",
        json={"title": "Doc Two", "initial_content": "B"},
        headers={"Authorization": f"Bearer {token}"},
    )

    response = client.get(
        "/v1/documents",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["title"] == "Doc Two"
    assert body[1]["title"] == "Doc One"


def test_delete_document_success() -> None:
    client = create_test_client()
    _, token = create_user_and_token(client, "owner@example.com", "Owner")
    create_response = client.post(
        "/v1/documents",
        json={"title": "Disposable", "initial_content": "Draft"},
        headers={"Authorization": f"Bearer {token}"},
    )
    document_id = create_response.json()["document_id"]

    delete_response = client.delete(
        f"/v1/documents/{document_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    get_response = client.get(
        f"/v1/documents/{document_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert delete_response.status_code == 204
    assert get_response.status_code == 404
