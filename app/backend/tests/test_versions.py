from app.backend.tests.conftest import create_test_client
from app.backend.tests.test_documents import create_user_and_token


def test_version_created_on_document_content_update() -> None:
    client = create_test_client()
    _, token = create_user_and_token(client, "owner@example.com", "Owner")
    create_response = client.post(
        "/v1/documents",
        json={"title": "Doc", "initial_content": ""},
        headers={"Authorization": "Bearer {token}".format(token=token)},
    )
    document_id = create_response.json()["document_id"]

    save_response = client.patch(
        "/v1/documents/{document_id}/content".format(document_id=document_id),
        json={"content": "First saved body", "base_revision": 0},
        headers={"Authorization": "Bearer {token}".format(token=token)},
    )

    versions_response = client.get(
        "/v1/documents/{document_id}/versions".format(document_id=document_id),
        headers={"Authorization": "Bearer {token}".format(token=token)},
    )

    assert save_response.status_code == 200
    assert save_response.json()["latest_version_id"] is not None
    assert versions_response.status_code == 200
    assert len(versions_response.json()) == 1
    assert versions_response.json()[0]["version_number"] == 1
    assert versions_response.json()[0]["version_id"] == 1
    assert versions_response.json()[0]["created_by"] == 1
    assert versions_response.json()[0]["is_restore_version"] is False
    assert versions_response.json()[0]["save_source"] == "manual"


def test_save_document_content_persists_line_spacing() -> None:
    client = create_test_client()
    _, token = create_user_and_token(client, "owner@example.com", "Owner")
    create_response = client.post(
        "/v1/documents",
        json={"title": "Doc", "initial_content": ""},
        headers={"Authorization": "Bearer {token}".format(token=token)},
    )
    document_id = create_response.json()["document_id"]

    save_response = client.patch(
        "/v1/documents/{document_id}/content".format(document_id=document_id),
        json={"content": "Spaced body", "base_revision": 0, "line_spacing": 1.5},
        headers={"Authorization": "Bearer {token}".format(token=token)},
    )
    document_response = client.get(
        "/v1/documents/{document_id}".format(document_id=document_id),
        headers={"Authorization": "Bearer {token}".format(token=token)},
    )

    assert save_response.status_code == 200
    assert save_response.json()["line_spacing"] == 1.5
    assert document_response.status_code == 200
    assert document_response.json()["line_spacing"] == 1.5


def test_list_versions_works() -> None:
    client = create_test_client()
    _, token = create_user_and_token(client, "owner@example.com", "Owner")
    create_response = client.post(
        "/v1/documents",
        json={"title": "Doc", "initial_content": ""},
        headers={"Authorization": "Bearer {token}".format(token=token)},
    )
    document_id = create_response.json()["document_id"]

    client.patch(
        "/v1/documents/{document_id}/content".format(document_id=document_id),
        json={"content": "Version one", "base_revision": 0},
        headers={"Authorization": "Bearer {token}".format(token=token)},
    )
    client.patch(
        "/v1/documents/{document_id}/content".format(document_id=document_id),
        json={"content": "Version two", "base_revision": 1},
        headers={"Authorization": "Bearer {token}".format(token=token)},
    )

    response = client.get(
        "/v1/documents/{document_id}/versions".format(document_id=document_id),
        headers={"Authorization": "Bearer {token}".format(token=token)},
    )

    assert response.status_code == 200
    assert len(response.json()) == 2
    assert response.json()[0]["version_number"] == 2
    assert response.json()[0]["is_restore_version"] is False
    assert response.json()[0]["save_source"] == "manual"
    assert response.json()[1]["version_number"] == 1
    assert response.json()[1]["is_restore_version"] is False
    assert response.json()[1]["save_source"] == "manual"


def test_versions_record_explicit_autosave_source() -> None:
    client = create_test_client()
    _, token = create_user_and_token(client, "owner@example.com", "Owner")
    create_response = client.post(
        "/v1/documents",
        json={"title": "Doc", "initial_content": ""},
        headers={"Authorization": "Bearer {token}".format(token=token)},
    )
    document_id = create_response.json()["document_id"]

    save_response = client.patch(
        "/v1/documents/{document_id}/content".format(document_id=document_id),
        json={
            "content": "Autosaved body",
            "base_revision": 0,
            "save_source": "autosave",
        },
        headers={"Authorization": "Bearer {token}".format(token=token)},
    )
    versions_response = client.get(
        "/v1/documents/{document_id}/versions".format(document_id=document_id),
        headers={"Authorization": "Bearer {token}".format(token=token)},
    )

    assert save_response.status_code == 200
    assert versions_response.status_code == 200
    assert versions_response.json()[0]["save_source"] == "autosave"


def test_restore_version_works() -> None:
    client = create_test_client()
    _, token = create_user_and_token(client, "owner@example.com", "Owner")
    create_response = client.post(
        "/v1/documents",
        json={"title": "Doc", "initial_content": ""},
        headers={"Authorization": "Bearer {token}".format(token=token)},
    )
    document_id = create_response.json()["document_id"]

    client.patch(
        "/v1/documents/{document_id}/content".format(document_id=document_id),
        json={"content": "Version one", "base_revision": 0, "line_spacing": 2},
        headers={"Authorization": "Bearer {token}".format(token=token)},
    )
    client.patch(
        "/v1/documents/{document_id}/content".format(document_id=document_id),
        json={"content": "Version two", "base_revision": 1, "line_spacing": 1.15},
        headers={"Authorization": "Bearer {token}".format(token=token)},
    )
    versions_response = client.get(
        "/v1/documents/{document_id}/versions".format(document_id=document_id),
        headers={"Authorization": "Bearer {token}".format(token=token)},
    )
    original_version_id = versions_response.json()[1]["version_id"]

    restore_response = client.post(
        "/v1/documents/{document_id}/versions/{version_id}/restore".format(
            document_id=document_id,
            version_id=original_version_id,
        ),
        headers={"Authorization": "Bearer {token}".format(token=token)},
    )
    restored_document = client.get(
        "/v1/documents/{document_id}".format(document_id=document_id),
        headers={"Authorization": "Bearer {token}".format(token=token)},
    )
    list_after_restore = client.get(
        "/v1/documents/{document_id}/versions".format(document_id=document_id),
        headers={"Authorization": "Bearer {token}".format(token=token)},
    )

    assert restore_response.status_code == 200
    assert restore_response.json() == {
        "document_id": document_id,
        "restored_from_version_id": original_version_id,
        "new_version_id": 3,
        "message": "Version restored as a new version entry.",
    }
    assert restored_document.status_code == 200
    assert restored_document.json()["current_content"] == "Version one"
    assert restored_document.json()["line_spacing"] == 2
    assert restored_document.json()["revision"] == 3
    assert len(list_after_restore.json()) == 3
    assert list_after_restore.json()[0]["version_number"] == 3
    assert list_after_restore.json()[0]["is_restore_version"] is True
    assert list_after_restore.json()[0]["save_source"] == "restore"


def test_restoring_invalid_version_is_rejected() -> None:
    client = create_test_client()
    _, token = create_user_and_token(client, "owner@example.com", "Owner")
    create_response = client.post(
        "/v1/documents",
        json={"title": "Doc", "initial_content": ""},
        headers={"Authorization": "Bearer {token}".format(token=token)},
    )
    document_id = create_response.json()["document_id"]

    response = client.post(
        "/v1/documents/{document_id}/versions/999/restore".format(
            document_id=document_id
        ),
        headers={"Authorization": "Bearer {token}".format(token=token)},
    )

    assert response.status_code == 404
    assert response.json() == {
        "error_code": "VALIDATION_ERROR",
        "message": "Version not found.",
        "retryable": False,
    }


def test_non_owner_restore_is_rejected() -> None:
    client = create_test_client()
    _, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    _, stranger_token = create_user_and_token(
        client, "stranger@example.com", "Stranger"
    )
    create_response = client.post(
        "/v1/documents",
        json={"title": "Doc", "initial_content": ""},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )
    document_id = create_response.json()["document_id"]
    client.patch(
        "/v1/documents/{document_id}/content".format(document_id=document_id),
        json={"content": "Owner version", "base_revision": 0},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )
    versions_response = client.get(
        "/v1/documents/{document_id}/versions".format(document_id=document_id),
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )
    version_id = versions_response.json()[0]["version_id"]

    response = client.post(
        "/v1/documents/{document_id}/versions/{version_id}/restore".format(
            document_id=document_id,
            version_id=version_id,
        ),
        headers={"Authorization": "Bearer {token}".format(token=stranger_token)},
    )

    assert response.status_code == 403
    assert response.json() == {
        "error_code": "PERMISSION_DENIED",
        "message": "You are not allowed to access this document.",
        "retryable": False,
    }
