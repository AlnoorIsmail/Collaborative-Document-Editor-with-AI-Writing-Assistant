from app.backend.tests.conftest import create_test_client


def create_user_and_headers(client, email: str) -> dict[str, str]:
    register_response = client.post(
        "/v1/auth/register",
        json={
            "email": email,
            "display_name": email.split("@", 1)[0].title(),
            "password": "strong-password",
        },
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/v1/auth/login",
        json={
            "email": email,
            "password": "strong-password",
        },
    )
    assert login_response.status_code == 200
    return {"Authorization": f"Bearer {login_response.json()['access_token']}"}


def test_auth_and_document_assignment_scope() -> None:
    client = create_test_client()
    headers = create_user_and_headers(client, "student@example.com")

    me_response = client.get("/v1/auth/me", headers=headers)
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "student@example.com"

    create_response = client.post(
        "/v1/documents",
        headers=headers,
        json={
            "title": "Software Engineering Notes",
            "initial_content": "Draft 1",
            "content_format": "plain_text",
            "ai_enabled": True,
        },
    )
    assert create_response.status_code == 201
    document_id = create_response.json()["document_id"]

    list_response = client.get("/v1/documents", headers=headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    get_response = client.get(f"/v1/documents/{document_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["title"] == "Software Engineering Notes"

    patch_response = client.patch(
        f"/v1/documents/{document_id}",
        headers=headers,
        json={
            "title": "SE Notes",
            "content": "Draft 2",
            "base_revision": 0,
        },
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["title"] == "SE Notes"
    assert patch_response.json()["current_content"] == "Draft 2"
    assert patch_response.json()["revision"] == 1

    versions_response = client.get(
        f"/v1/documents/{document_id}/versions",
        headers=headers,
    )
    assert versions_response.status_code == 200
    assert len(versions_response.json()) == 1
    version_id = versions_response.json()[0]["version_id"]

    restore_response = client.post(
        f"/v1/documents/{document_id}/versions/{version_id}/restore",
        headers=headers,
    )
    assert restore_response.status_code == 200

    restored_document_response = client.get(
        f"/v1/documents/{document_id}",
        headers=headers,
    )
    assert restored_document_response.status_code == 200
    assert restored_document_response.json()["current_content"] == "Draft 2"
    assert restored_document_response.json()["revision"] == 2

    delete_response = client.delete(f"/v1/documents/{document_id}", headers=headers)
    assert delete_response.status_code == 204


def test_document_endpoints_require_valid_tokens() -> None:
    client = create_test_client()

    create_without_token = client.post(
        "/v1/documents",
        json={"title": "Unauthorized"},
    )
    list_without_token = client.get("/v1/documents")
    list_with_invalid_token = client.get(
        "/v1/documents",
        headers={"Authorization": "Bearer invalid.token.value"},
    )

    assert create_without_token.status_code == 401
    assert list_without_token.status_code == 401
    assert list_with_invalid_token.status_code == 401
