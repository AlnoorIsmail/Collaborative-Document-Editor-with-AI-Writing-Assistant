from apps.backend.tests.conftest import create_test_client
from apps.backend.tests.test_documents import create_user_and_token


def test_owner_can_grant_permission() -> None:
    client = create_test_client()
    owner, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    grantee, _ = create_user_and_token(client, "editor@example.com", "Editor")
    create_response = client.post(
        "/v1/documents",
        json={"title": "Doc", "initial_content": ""},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )
    document_id = create_response.json()["document_id"]

    response = client.post(
        "/v1/documents/{document_id}/permissions".format(document_id=document_id),
        json={
            "grantee_type": "user",
            "user_id": "usr_{id}".format(id=grantee["user_id"]),
            "role": "editor",
            "ai_allowed": True,
        },
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )

    assert response.status_code == 201
    assert response.json()["permission_id"] == "perm_1"
    assert response.json()["document_id"] == "doc_{id}".format(id=document_id)
    assert response.json()["grantee_type"] == "user"
    assert response.json()["user_id"] == "usr_{id}".format(id=grantee["user_id"])
    assert response.json()["role"] == "editor"
    assert response.json()["ai_allowed"] is True
    assert response.json()["granted_at"]
    assert owner["user_id"] == 1


def test_non_owner_cannot_grant_permission() -> None:
    client = create_test_client()
    _, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    _, stranger_token = create_user_and_token(client, "stranger@example.com", "Stranger")
    grantee, _ = create_user_and_token(client, "editor@example.com", "Editor")
    create_response = client.post(
        "/v1/documents",
        json={"title": "Doc", "initial_content": ""},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )
    document_id = create_response.json()["document_id"]

    response = client.post(
        "/v1/documents/{document_id}/permissions".format(document_id=document_id),
        json={
            "grantee_type": "user",
            "user_id": "usr_{id}".format(id=grantee["user_id"]),
            "role": "editor",
            "ai_allowed": True,
        },
        headers={"Authorization": "Bearer {token}".format(token=stranger_token)},
    )

    assert response.status_code == 403
    assert response.json() == {
        "error_code": "PERMISSION_DENIED",
        "message": "You are not allowed to access this document.",
        "retryable": False,
    }


def test_owner_can_revoke_permission() -> None:
    client = create_test_client()
    _, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    grantee, _ = create_user_and_token(client, "editor@example.com", "Editor")
    create_response = client.post(
        "/v1/documents",
        json={"title": "Doc", "initial_content": ""},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )
    document_id = create_response.json()["document_id"]
    permission_response = client.post(
        "/v1/documents/{document_id}/permissions".format(document_id=document_id),
        json={
            "grantee_type": "user",
            "user_id": "usr_{id}".format(id=grantee["user_id"]),
            "role": "editor",
            "ai_allowed": True,
        },
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )

    permission_id = permission_response.json()["permission_id"].split("_", 1)[1]
    response = client.delete(
        "/v1/documents/{document_id}/permissions/{permission_id}".format(
            document_id=document_id,
            permission_id=permission_id,
        ),
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )

    assert response.status_code == 204
    assert response.content == b""


def test_non_owner_cannot_revoke_permission() -> None:
    client = create_test_client()
    _, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    _, stranger_token = create_user_and_token(client, "stranger@example.com", "Stranger")
    grantee, _ = create_user_and_token(client, "editor@example.com", "Editor")
    create_response = client.post(
        "/v1/documents",
        json={"title": "Doc", "initial_content": ""},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )
    document_id = create_response.json()["document_id"]
    permission_response = client.post(
        "/v1/documents/{document_id}/permissions".format(document_id=document_id),
        json={
            "grantee_type": "user",
            "user_id": "usr_{id}".format(id=grantee["user_id"]),
            "role": "editor",
            "ai_allowed": True,
        },
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )
    permission_id = permission_response.json()["permission_id"].split("_", 1)[1]

    response = client.delete(
        "/v1/documents/{document_id}/permissions/{permission_id}".format(
            document_id=document_id,
            permission_id=permission_id,
        ),
        headers={"Authorization": "Bearer {token}".format(token=stranger_token)},
    )

    assert response.status_code == 403
    assert response.json() == {
        "error_code": "PERMISSION_DENIED",
        "message": "You are not allowed to access this document.",
        "retryable": False,
    }


def test_revoking_missing_permission_returns_not_found() -> None:
    client = create_test_client()
    _, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    create_response = client.post(
        "/v1/documents",
        json={"title": "Doc", "initial_content": ""},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )
    document_id = create_response.json()["document_id"]

    response = client.delete(
        "/v1/documents/{document_id}/permissions/999".format(document_id=document_id),
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )

    assert response.status_code == 404
    assert response.json() == {
        "error_code": "VALIDATION_ERROR",
        "message": "Permission not found.",
        "retryable": False,
    }


def test_duplicate_permission_updates_existing_record() -> None:
    client = create_test_client()
    _, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    grantee, _ = create_user_and_token(client, "editor@example.com", "Editor")
    create_response = client.post(
        "/v1/documents",
        json={"title": "Doc", "initial_content": ""},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )
    document_id = create_response.json()["document_id"]

    first_response = client.post(
        "/v1/documents/{document_id}/permissions".format(document_id=document_id),
        json={
            "grantee_type": "user",
            "user_id": "usr_{id}".format(id=grantee["user_id"]),
            "role": "viewer",
            "ai_allowed": False,
        },
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )
    second_response = client.post(
        "/v1/documents/{document_id}/permissions".format(document_id=document_id),
        json={
            "grantee_type": "user",
            "user_id": "usr_{id}".format(id=grantee["user_id"]),
            "role": "editor",
            "ai_allowed": True,
        },
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert second_response.json()["permission_id"] == first_response.json()["permission_id"]
    assert second_response.json()["role"] == "editor"
    assert second_response.json()["ai_allowed"] is True
