from fastapi.testclient import TestClient

from app.backend.services.document_service import (
    generate_unique_document_title,
)
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
        headers={"Authorization": f"Bearer {token}"},
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
    assert response.json()["line_spacing"] == 1.15
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
        headers={"Authorization": f"Bearer {token}"},
    )
    document_id = create_response.json()["document_id"]

    response = client.get(
        f"/v1/documents/{document_id}",
        headers={"Authorization": f"Bearer {token}"},
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
    assert response.json()["line_spacing"] == 1.15
    assert response.json()["revision"] == 0
    assert response.json()["created_at"]


def test_list_documents_success() -> None:
    client = create_test_client()
    _, token = create_user_and_token(client, "owner@example.com", "Owner")
    client.post(
        "/v1/documents",
        json={"title": "Readable Doc", "initial_content": "Body"},
        headers={"Authorization": f"Bearer {token}"},
    )

    response = client.get(
        "/v1/documents",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["title"] == "Readable Doc"
    assert response.json()[0]["preview_text"] == "Body"
    assert response.json()[0]["role"] == "owner"
    assert response.json()[0]["line_spacing"] == 1.15
    assert response.json()[0]["created_at"]
    assert response.json()[0]["updated_at"]


def test_list_documents_includes_shared_documents_for_grantee() -> None:
    client = create_test_client()
    owner, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    viewer, viewer_token = create_user_and_token(client, "viewer@example.com", "Viewer")
    create_response = client.post(
        "/v1/documents",
        json={"title": "Shared Doc", "initial_content": "Body"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    document_id = create_response.json()["document_id"]
    client.post(
        f"/v1/documents/{document_id}/permissions",
        json={
            "grantee_type": "user",
            "user_id": f"usr_{viewer['user_id']}",
            "role": "viewer",
            "ai_allowed": False,
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    response = client.get(
        "/v1/documents",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "document_id": document_id,
            "title": "Shared Doc",
            "preview_text": "Body",
            "content_format": "plain_text",
            "owner": {
                "user_id": owner["user_id"],
                "display_name": "Owner",
            },
            "owner_user_id": owner["user_id"],
            "role": "viewer",
            "ai_enabled": True,
            "line_spacing": 1.15,
            "revision": 0,
            "latest_version_id": None,
            "latest_version": None,
            "created_at": response.json()[0]["created_at"],
            "updated_at": response.json()[0]["updated_at"],
        }
    ]


def test_generate_unique_document_title_adds_predictable_suffixes() -> None:
    assert generate_unique_document_title(None, []) == "Untitled Document"
    assert generate_unique_document_title("", ["Untitled Document"]) == "Untitled Document 1"
    assert (
        generate_unique_document_title("", ["Untitled Document 1", "Untitled Document 2"])
        == "Untitled Document 3"
    )
    assert (
        generate_unique_document_title(
            "Notes",
            ["Notes", "Notes 1", "Project Plan"],
        )
        == "Notes 2"
    )
    assert generate_unique_document_title("Notes", ["Notes 2"]) == "Notes 3"
    assert (
        generate_unique_document_title(
            "Notes 1",
            ["Notes", "Notes 1"],
        )
        == "Notes 2"
    )


def test_create_multiple_untitled_documents_gets_distinct_titles() -> None:
    client = create_test_client()
    _, token = create_user_and_token(client, "owner@example.com", "Owner")
    headers = {"Authorization": f"Bearer {token}"}

    first = client.post(
        "/v1/documents",
        json={"initial_content": ""},
        headers=headers,
    )
    second = client.post(
        "/v1/documents",
        json={"initial_content": ""},
        headers=headers,
    )
    third = client.post(
        "/v1/documents",
        json={"initial_content": ""},
        headers=headers,
    )
    listed = client.get("/v1/documents", headers=headers)

    assert first.status_code == 201
    assert second.status_code == 201
    assert third.status_code == 201
    assert first.json()["document_id"] != second.json()["document_id"]
    assert second.json()["document_id"] != third.json()["document_id"]
    assert first.json()["title"] == "Untitled Document"
    assert second.json()["title"] == "Untitled Document 1"
    assert third.json()["title"] == "Untitled Document 2"
    assert [doc["title"] for doc in listed.json()] == [
        "Untitled Document 2",
        "Untitled Document 1",
        "Untitled Document",
    ]


def test_update_document_renames_duplicates_predictably() -> None:
    client = create_test_client()
    _, token = create_user_and_token(client, "owner@example.com", "Owner")
    headers = {"Authorization": f"Bearer {token}"}
    original = client.post(
        "/v1/documents",
        json={"title": "Notes", "initial_content": ""},
        headers=headers,
    )
    renamed = client.post(
        "/v1/documents",
        json={"title": "Draft", "initial_content": ""},
        headers=headers,
    )
    document_id = renamed.json()["document_id"]

    response = client.patch(
        f"/v1/documents/{document_id}",
        json={"title": "Notes"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Notes 1"


def test_create_document_keeps_incrementing_existing_name_family() -> None:
    client = create_test_client()
    _, token = create_user_and_token(client, "owner@example.com", "Owner")
    headers = {"Authorization": f"Bearer {token}"}

    client.post(
        "/v1/documents",
        json={"title": "Notes 1", "initial_content": ""},
        headers=headers,
    )
    client.post(
        "/v1/documents",
        json={"title": "Notes 2", "initial_content": ""},
        headers=headers,
    )

    response = client.post(
        "/v1/documents",
        json={"title": "Notes", "initial_content": ""},
        headers=headers,
    )

    assert response.status_code == 201
    assert response.json()["title"] == "Notes 3"


def test_update_document_success() -> None:
    client = create_test_client()
    _, token = create_user_and_token(client, "owner@example.com", "Owner")
    create_response = client.post(
        "/v1/documents",
        json={"title": "Original", "initial_content": "Draft"},
        headers={"Authorization": f"Bearer {token}"},
    )
    document_id = create_response.json()["document_id"]

    response = client.patch(
        f"/v1/documents/{document_id}",
        json={
            "title": "Updated",
            "ai_enabled": False,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["document_id"] == document_id
    assert response.json()["title"] == "Updated"
    assert response.json()["ai_enabled"] is False
    assert response.json()["line_spacing"] == 1.15
    assert response.json()["role"] == "owner"
    assert response.json()["updated_at"]
    assert "current_content" not in response.json()


def test_save_document_content_success() -> None:
    client = create_test_client()
    _, token = create_user_and_token(client, "owner@example.com", "Owner")
    create_response = client.post(
        "/v1/documents",
        json={"title": "Original", "initial_content": ""},
        headers={"Authorization": f"Bearer {token}"},
    )
    document_id = create_response.json()["document_id"]

    response = client.patch(
        f"/v1/documents/{document_id}/content",
        json={"content": "Final copy", "base_revision": 0},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["document_id"] == document_id
    assert response.json()["latest_version_id"] == 1
    assert response.json()["line_spacing"] == 1.15
    assert response.json()["revision"] == 1
    assert response.json()["saved_at"]


def test_repeated_same_content_save_reuses_existing_version() -> None:
    client = create_test_client()
    _, token = create_user_and_token(client, "owner@example.com", "Owner")
    create_response = client.post(
        "/v1/documents",
        json={"title": "Original", "initial_content": ""},
        headers={"Authorization": f"Bearer {token}"},
    )
    document_id = create_response.json()["document_id"]

    first_save = client.patch(
        f"/v1/documents/{document_id}/content",
        json={"content": "Stable body", "base_revision": 0},
        headers={"Authorization": f"Bearer {token}"},
    )
    second_save = client.patch(
        f"/v1/documents/{document_id}/content",
        json={"content": "Stable body", "base_revision": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    versions = client.get(
        f"/v1/documents/{document_id}/versions",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert first_save.status_code == 200
    assert second_save.status_code == 200
    assert second_save.json() == first_save.json()
    assert versions.status_code == 200
    assert len(versions.json()) == 1


def test_stale_same_content_save_returns_current_version_instead_of_conflict() -> None:
    client = create_test_client()
    _, token = create_user_and_token(client, "owner@example.com", "Owner")
    create_response = client.post(
        "/v1/documents",
        json={"title": "Original", "initial_content": ""},
        headers={"Authorization": f"Bearer {token}"},
    )
    document_id = create_response.json()["document_id"]

    first_save = client.patch(
        f"/v1/documents/{document_id}/content",
        json={"content": "Shared body", "base_revision": 0},
        headers={"Authorization": f"Bearer {token}"},
    )
    late_duplicate_save = client.patch(
        f"/v1/documents/{document_id}/content",
        json={"content": "Shared body", "base_revision": 0},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert first_save.status_code == 200
    assert late_duplicate_save.status_code == 200
    assert late_duplicate_save.json() == first_save.json()


def test_session_bootstrap_reports_resync_and_active_collaborators() -> None:
    client = create_test_client()
    owner, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    editor, editor_token = create_user_and_token(client, "editor@example.com", "Editor")
    create_response = client.post(
        "/v1/documents",
        json={"title": "Shared Doc", "initial_content": ""},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    document_id = create_response.json()["document_id"]
    save_response = client.patch(
        f"/v1/documents/{document_id}/content",
        json={"content": "First shared revision", "base_revision": 0},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    permission_response = client.post(
        f"/v1/documents/{document_id}/permissions",
        json={
            "grantee_type": "user",
            "user_id": f"usr_{editor['user_id']}",
            "role": "editor",
            "ai_allowed": True,
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    owner_session = client.post(
        f"/v1/documents/{document_id}/sessions",
        json={"last_known_revision": 0},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    editor_session = client.post(
        f"/v1/documents/{document_id}/sessions",
        json={"last_known_revision": 1},
        headers={"Authorization": f"Bearer {editor_token}"},
    )

    assert save_response.status_code == 200
    assert permission_response.status_code == 201
    assert owner_session.status_code == 201
    assert owner_session.json()["document_id"] == document_id
    assert owner_session.json()["revision"] == 1
    assert (
        owner_session.json()["realtime_url"]
        == f"/v1/documents/{document_id}/sessions/sess_1/ws"
    )
    assert owner_session.json()["resync_required"] is True
    assert owner_session.json()["missed_revision_count"] == 1
    assert len(owner_session.json()["active_collaborators"]) == 1
    assert owner_session.json()["active_collaborators"][0]["user_id"] == owner["user_id"]
    assert owner_session.json()["active_collaborators"][0]["display_name"] == "Owner"

    assert editor_session.status_code == 201
    assert (
        editor_session.json()["realtime_url"]
        == f"/v1/documents/{document_id}/sessions/sess_2/ws"
    )
    assert editor_session.json()["resync_required"] is False
    assert editor_session.json()["missed_revision_count"] == 0
    assert len(editor_session.json()["active_collaborators"]) == 2
    assert {
        collaborator["user_id"]
        for collaborator in editor_session.json()["active_collaborators"]
    } == {owner["user_id"], editor["user_id"]}
    assert {
        collaborator["display_name"]
        for collaborator in editor_session.json()["active_collaborators"]
    } == {"Owner", "Editor"}


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


def test_invalid_token_access_rejected() -> None:
    client = create_test_client()

    response = client.get(
        "/v1/documents",
        headers={"Authorization": "Bearer invalid.jwt.token"},
    )

    assert response.status_code == 401
    assert response.json() == {
        "error_code": "UNAUTHORIZED",
        "message": "Invalid or expired token.",
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
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    document_id = create_response.json()["document_id"]

    response = client.get(
        f"/v1/documents/{document_id}",
        headers={"Authorization": f"Bearer {stranger_token}"},
    )

    assert response.status_code == 403
    assert response.json() == {
        "error_code": "PERMISSION_DENIED",
        "message": "You are not allowed to access this document.",
        "retryable": False,
    }


def test_delete_document_success() -> None:
    client = create_test_client()
    _, token = create_user_and_token(client, "owner@example.com", "Owner")
    create_response = client.post(
        "/v1/documents",
        json={"title": "Temporary Doc", "initial_content": "Draft"},
        headers={"Authorization": f"Bearer {token}"},
    )
    document_id = create_response.json()["document_id"]

    delete_response = client.delete(
        f"/v1/documents/{document_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    fetch_response = client.get(
        f"/v1/documents/{document_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert delete_response.status_code == 204
    assert fetch_response.status_code == 404
    assert fetch_response.json() == {
        "error_code": "DOCUMENT_NOT_FOUND",
        "message": "Document not found.",
        "retryable": False,
    }


def test_html_export_renders_rich_text_content_while_escaping_title() -> None:
    client = create_test_client()
    _, token = create_user_and_token(client, "owner@example.com", "Owner")
    create_response = client.post(
        "/v1/documents",
        json={
            "title": '<script>alert("title")</script>',
            "initial_content": '<p><strong>Formatted</strong> body</p>',
            "content_format": "rich_text",
            "line_spacing": 1.5,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    document_id = create_response.json()["document_id"]

    response = client.post(
        f"/v1/documents/{document_id}/export",
        json={"format": "html"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    exported_content = response.json()["exported_content"]
    assert exported_content.startswith("<!doctype html>")
    assert "&lt;script&gt;alert(&quot;title&quot;)&lt;/script&gt;" in exported_content
    assert "<pre>" not in exported_content
    assert "<strong>Formatted</strong> body" in exported_content
    assert 'data-document-id="{document_id}"'.format(document_id=document_id) in exported_content
    assert 'data-revision="0"' in exported_content
    assert "line-height: 1.5;" in exported_content


def test_plain_text_export_strips_rich_text_tags() -> None:
    client = create_test_client()
    _, token = create_user_and_token(client, "owner@example.com", "Owner")
    create_response = client.post(
        "/v1/documents",
        json={
            "title": "Rich text export",
            "initial_content": "<h1>Title</h1><p>Hello <strong>world</strong></p><ul><li>One</li><li>Two</li></ul>",
            "content_format": "rich_text",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    document_id = create_response.json()["document_id"]

    response = client.post(
        f"/v1/documents/{document_id}/export",
        json={"format": "plain_text"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    exported_content = response.json()["exported_content"]
    assert "<p>" not in exported_content
    assert "<strong>" not in exported_content
    assert "Hello world" in exported_content
    assert "- One" in exported_content
    assert "- Two" in exported_content


def test_markdown_export_converts_rich_text_tags_to_markdown() -> None:
    client = create_test_client()
    _, token = create_user_and_token(client, "owner@example.com", "Owner")
    create_response = client.post(
        "/v1/documents",
        json={
            "title": "Markdown export",
            "initial_content": "<h2>Heading</h2><p><strong>Bold</strong> and <em>italic</em></p>",
            "content_format": "rich_text",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    document_id = create_response.json()["document_id"]

    response = client.post(
        f"/v1/documents/{document_id}/export",
        json={"format": "markdown"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    exported_content = response.json()["exported_content"]
    assert "<p>" not in exported_content
    assert "<strong>" not in exported_content
    assert "## Heading" in exported_content
    assert "**Bold** and *italic*" in exported_content
