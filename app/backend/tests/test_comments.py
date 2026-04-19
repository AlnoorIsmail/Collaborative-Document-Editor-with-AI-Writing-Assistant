from app.backend.tests.conftest import create_test_client
from app.backend.tests.test_documents import create_user_and_token
from app.backend.tests.test_realtime_websocket import _open_socket, _receive_until


def _grant_role(client, *, document_id: int, owner_token: str, user_id: int, role: str) -> None:
    response = client.post(
        f"/v1/documents/{document_id}/permissions",
        json={
            "grantee_type": "user",
            "user_id": f"usr_{user_id}",
            "role": role,
            "ai_allowed": False,
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 201


def test_commenter_can_create_and_list_comments_but_cannot_edit_document_content() -> None:
    client = create_test_client()
    _, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    commenter, commenter_token = create_user_and_token(
        client, "commenter@example.com", "Commenter"
    )
    create_document = client.post(
        "/v1/documents",
        json={"title": "Comment Doc", "initial_content": "Original"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    document_id = create_document.json()["document_id"]
    _grant_role(
        client,
        document_id=document_id,
        owner_token=owner_token,
        user_id=commenter["user_id"],
        role="commenter",
    )

    create_comment = client.post(
        f"/v1/documents/{document_id}/comments",
        json={
            "body": "Please reword this paragraph.",
            "quoted_text": "Original",
        },
        headers={"Authorization": f"Bearer {commenter_token}"},
    )
    list_comments = client.get(
        f"/v1/documents/{document_id}/comments",
        headers={"Authorization": f"Bearer {commenter_token}"},
    )
    edit_attempt = client.patch(
        f"/v1/documents/{document_id}/content",
        json={"content": "Changed", "base_revision": 0},
        headers={"Authorization": f"Bearer {commenter_token}"},
    )

    assert create_comment.status_code == 201
    assert create_comment.json()["author"]["display_name"] == "Commenter"
    assert create_comment.json()["quoted_text"] == "Original"
    assert create_comment.json()["status"] == "open"
    assert list_comments.status_code == 200
    assert len(list_comments.json()) == 1
    assert list_comments.json()[0]["body"] == "Please reword this paragraph."
    assert edit_attempt.status_code == 403
    assert edit_attempt.json()["error_code"] == "PERMISSION_DENIED"


def test_viewer_can_read_comments_but_cannot_create_them() -> None:
    client = create_test_client()
    _, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    viewer, viewer_token = create_user_and_token(client, "viewer@example.com", "Viewer")
    create_document = client.post(
        "/v1/documents",
        json={"title": "Comment Doc", "initial_content": "Original"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    document_id = create_document.json()["document_id"]
    _grant_role(
        client,
        document_id=document_id,
        owner_token=owner_token,
        user_id=viewer["user_id"],
        role="viewer",
    )
    owner_comment = client.post(
        f"/v1/documents/{document_id}/comments",
        json={"body": "Owner note", "quoted_text": None},
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    list_comments = client.get(
        f"/v1/documents/{document_id}/comments",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    create_attempt = client.post(
        f"/v1/documents/{document_id}/comments",
        json={"body": "Viewer note"},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert owner_comment.status_code == 201
    assert list_comments.status_code == 200
    assert list_comments.json()[0]["body"] == "Owner note"
    assert create_attempt.status_code == 403
    assert create_attempt.json()["error_code"] == "PERMISSION_DENIED"


def test_comment_author_can_delete_own_comment_but_other_commenter_cannot() -> None:
    client = create_test_client()
    _, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    commenter_one, commenter_one_token = create_user_and_token(
        client, "commenter.one@example.com", "Commenter One"
    )
    commenter_two, commenter_two_token = create_user_and_token(
        client, "commenter.two@example.com", "Commenter Two"
    )
    create_document = client.post(
        "/v1/documents",
        json={"title": "Comment Doc", "initial_content": "Original"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    document_id = create_document.json()["document_id"]
    _grant_role(
        client,
        document_id=document_id,
        owner_token=owner_token,
        user_id=commenter_one["user_id"],
        role="commenter",
    )
    _grant_role(
        client,
        document_id=document_id,
        owner_token=owner_token,
        user_id=commenter_two["user_id"],
        role="commenter",
    )
    created_comment = client.post(
        f"/v1/documents/{document_id}/comments",
        json={"body": "First comment"},
        headers={"Authorization": f"Bearer {commenter_one_token}"},
    ).json()

    rejected_delete = client.delete(
        f"/v1/documents/{document_id}/comments/{created_comment['comment_id']}",
        headers={"Authorization": f"Bearer {commenter_two_token}"},
    )
    accepted_delete = client.delete(
        f"/v1/documents/{document_id}/comments/{created_comment['comment_id']}",
        headers={"Authorization": f"Bearer {commenter_one_token}"},
    )
    remaining_comments = client.get(
        f"/v1/documents/{document_id}/comments",
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert rejected_delete.status_code == 403
    assert rejected_delete.json()["error_code"] == "PERMISSION_DENIED"
    assert accepted_delete.status_code == 204
    assert remaining_comments.json() == []


def test_editor_can_resolve_any_comment() -> None:
    client = create_test_client()
    _, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    commenter, commenter_token = create_user_and_token(
        client, "commenter@example.com", "Commenter"
    )
    editor, editor_token = create_user_and_token(client, "editor@example.com", "Editor")
    create_document = client.post(
        "/v1/documents",
        json={"title": "Comment Doc", "initial_content": "Original"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    document_id = create_document.json()["document_id"]
    _grant_role(
        client,
        document_id=document_id,
        owner_token=owner_token,
        user_id=commenter["user_id"],
        role="commenter",
    )
    _grant_role(
        client,
        document_id=document_id,
        owner_token=owner_token,
        user_id=editor["user_id"],
        role="editor",
    )
    created_comment = client.post(
        f"/v1/documents/{document_id}/comments",
        json={"body": "Needs attention"},
        headers={"Authorization": f"Bearer {commenter_token}"},
    ).json()

    resolve_response = client.post(
        f"/v1/documents/{document_id}/comments/{created_comment['comment_id']}/resolve",
        headers={"Authorization": f"Bearer {editor_token}"},
    )

    assert resolve_response.status_code == 200
    assert resolve_response.json()["status"] == "resolved"
    assert resolve_response.json()["resolved_by_user_id"] == editor["user_id"]


def test_comment_routes_broadcast_realtime_events() -> None:
    client = create_test_client()
    owner, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    commenter, commenter_token = create_user_and_token(
        client, "commenter@example.com", "Commenter"
    )
    create_document = client.post(
        "/v1/documents",
        json={"title": "Comment Doc", "initial_content": "Original"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    document_id = create_document.json()["document_id"]
    _grant_role(
        client,
        document_id=document_id,
        owner_token=owner_token,
        user_id=commenter["user_id"],
        role="commenter",
    )
    owner_bootstrap = client.post(
        f"/v1/documents/{document_id}/sessions",
        json={"last_known_revision": 0},
        headers={"Authorization": f"Bearer {owner_token}"},
    ).json()
    commenter_bootstrap = client.post(
        f"/v1/documents/{document_id}/sessions",
        json={"last_known_revision": 0},
        headers={"Authorization": f"Bearer {commenter_token}"},
    ).json()

    with _open_socket(
        client,
        document_id=document_id,
        session_id=owner_bootstrap["session_id"],
        session_token=owner_bootstrap["session_token"],
        access_token=owner_token,
    ) as owner_socket, _open_socket(
        client,
        document_id=document_id,
        session_id=commenter_bootstrap["session_id"],
        session_token=commenter_bootstrap["session_token"],
        access_token=commenter_token,
    ) as commenter_socket:
        _receive_until(owner_socket, "session_joined")
        _receive_until(owner_socket, "presence_snapshot")
        _receive_until(owner_socket, "awareness_snapshot")
        _receive_until(commenter_socket, "session_joined")
        _receive_until(commenter_socket, "presence_snapshot")
        _receive_until(commenter_socket, "awareness_snapshot")

        created_comment = client.post(
            f"/v1/documents/{document_id}/comments",
            json={"body": "Live comment"},
            headers={"Authorization": f"Bearer {commenter_token}"},
        ).json()

        owner_created = _receive_until(owner_socket, "comment_created")
        commenter_created = _receive_until(commenter_socket, "comment_created")
        assert owner_created["comment"]["body"] == "Live comment"
        assert commenter_created["comment"]["comment_id"] == created_comment["comment_id"]

        resolved_comment = client.post(
            f"/v1/documents/{document_id}/comments/{created_comment['comment_id']}/resolve",
            headers={"Authorization": f"Bearer {owner_token}"},
        ).json()

        owner_resolved = _receive_until(owner_socket, "comment_resolved")
        commenter_resolved = _receive_until(commenter_socket, "comment_resolved")
        assert owner_resolved["comment"]["status"] == "resolved"
        assert commenter_resolved["comment"]["comment_id"] == resolved_comment["comment_id"]

        delete_response = client.delete(
            f"/v1/documents/{document_id}/comments/{created_comment['comment_id']}",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert delete_response.status_code == 204

        owner_deleted = _receive_until(owner_socket, "comment_deleted")
        commenter_deleted = _receive_until(commenter_socket, "comment_deleted")
        assert owner_deleted["comment_id"] == created_comment["comment_id"]
        assert commenter_deleted["comment_id"] == created_comment["comment_id"]
