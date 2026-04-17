from app.backend.tests.conftest import create_test_client
from app.backend.tests.test_documents import create_user_and_token


def test_owner_can_grant_permission() -> None:
    client = create_test_client()
    owner, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    grantee, _ = create_user_and_token(client, "editor@example.com", "Editor")
    create_response = client.post(
        "/v1/documents",
        json={"title": "Doc", "initial_content": ""},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    document_id = create_response.json()["document_id"]

    response = client.post(
        f"/v1/documents/{document_id}/permissions",
        json={
            "grantee_type": "user",
            "user_id": "usr_{id}".format(id=grantee["user_id"]),
            "role": "editor",
            "ai_allowed": True,
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert response.status_code == 201
    assert response.json()["permission_id"] == "perm_1"
    assert response.json()["document_id"] == f"doc_{document_id}"
    assert response.json()["grantee_type"] == "user"
    assert response.json()["user_id"] == "usr_{id}".format(id=grantee["user_id"])
    assert response.json()["role"] == "editor"
    assert response.json()["ai_allowed"] is True
    assert response.json()["granted_at"]
    assert owner["user_id"] == 1


def test_non_owner_cannot_grant_permission() -> None:
    client = create_test_client()
    _, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    _, stranger_token = create_user_and_token(
        client, "stranger@example.com", "Stranger"
    )
    grantee, _ = create_user_and_token(client, "editor@example.com", "Editor")
    create_response = client.post(
        "/v1/documents",
        json={"title": "Doc", "initial_content": ""},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    document_id = create_response.json()["document_id"]

    response = client.post(
        f"/v1/documents/{document_id}/permissions",
        json={
            "grantee_type": "user",
            "user_id": "usr_{id}".format(id=grantee["user_id"]),
            "role": "editor",
            "ai_allowed": True,
        },
        headers={"Authorization": f"Bearer {stranger_token}"},
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
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    document_id = create_response.json()["document_id"]
    permission_response = client.post(
        f"/v1/documents/{document_id}/permissions",
        json={
            "grantee_type": "user",
            "user_id": "usr_{id}".format(id=grantee["user_id"]),
            "role": "editor",
            "ai_allowed": True,
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    permission_id = permission_response.json()["permission_id"].split("_", 1)[1]
    response = client.delete(
        f"/v1/documents/{document_id}/permissions/{permission_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert response.status_code == 204
    assert response.content == b""


def test_non_owner_cannot_revoke_permission() -> None:
    client = create_test_client()
    _, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    _, stranger_token = create_user_and_token(
        client, "stranger@example.com", "Stranger"
    )
    grantee, _ = create_user_and_token(client, "editor@example.com", "Editor")
    create_response = client.post(
        "/v1/documents",
        json={"title": "Doc", "initial_content": ""},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    document_id = create_response.json()["document_id"]
    permission_response = client.post(
        f"/v1/documents/{document_id}/permissions",
        json={
            "grantee_type": "user",
            "user_id": "usr_{id}".format(id=grantee["user_id"]),
            "role": "editor",
            "ai_allowed": True,
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    permission_id = permission_response.json()["permission_id"].split("_", 1)[1]

    response = client.delete(
        f"/v1/documents/{document_id}/permissions/{permission_id}",
        headers={"Authorization": f"Bearer {stranger_token}"},
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
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    document_id = create_response.json()["document_id"]

    response = client.delete(
        f"/v1/documents/{document_id}/permissions/999",
        headers={"Authorization": f"Bearer {owner_token}"},
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
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    document_id = create_response.json()["document_id"]

    first_response = client.post(
        f"/v1/documents/{document_id}/permissions",
        json={
            "grantee_type": "user",
            "user_id": "usr_{id}".format(id=grantee["user_id"]),
            "role": "viewer",
            "ai_allowed": False,
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    second_response = client.post(
        f"/v1/documents/{document_id}/permissions",
        json={
            "grantee_type": "user",
            "user_id": "usr_{id}".format(id=grantee["user_id"]),
            "role": "editor",
            "ai_allowed": True,
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert (
        second_response.json()["permission_id"]
        == first_response.json()["permission_id"]
    )
    assert second_response.json()["role"] == "editor"
    assert second_response.json()["ai_allowed"] is True


def test_viewer_can_read_but_cannot_edit_shared_document() -> None:
    client = create_test_client()
    _, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    viewer, viewer_token = create_user_and_token(client, "viewer@example.com", "Viewer")
    create_response = client.post(
        "/v1/documents",
        json={"title": "Doc", "initial_content": "Original"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    document_id = create_response.json()["document_id"]
    client.post(
        f"/v1/documents/{document_id}/permissions",
        json={
            "grantee_type": "user",
            "user_id": f"usr_{viewer['user_id']}",
            "role": "viewer",
            "ai_allowed": True,
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    read_response = client.get(
        f"/v1/documents/{document_id}",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    edit_response = client.patch(
        f"/v1/documents/{document_id}/content",
        json={"content": "Attempted edit", "base_revision": 0},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert read_response.status_code == 200
    assert read_response.json()["role"] == "viewer"
    assert edit_response.status_code == 403
    assert edit_response.json() == {
        "error_code": "PERMISSION_DENIED",
        "message": "You are not allowed to access this document.",
        "retryable": False,
    }


def test_editor_can_edit_shared_document() -> None:
    client = create_test_client()
    _, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    editor, editor_token = create_user_and_token(client, "editor@example.com", "Editor")
    create_response = client.post(
        "/v1/documents",
        json={"title": "Doc", "initial_content": "Original"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    document_id = create_response.json()["document_id"]
    client.post(
        f"/v1/documents/{document_id}/permissions",
        json={
            "grantee_type": "user",
            "user_id": f"usr_{editor['user_id']}",
            "role": "editor",
            "ai_allowed": True,
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    edit_response = client.patch(
        f"/v1/documents/{document_id}/content",
        json={"content": "Editor update", "base_revision": 0},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    document_response = client.get(
        f"/v1/documents/{document_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert edit_response.status_code == 200
    assert edit_response.json()["revision"] == 1
    assert document_response.status_code == 200
    assert document_response.json()["current_content"] == "Editor update"
