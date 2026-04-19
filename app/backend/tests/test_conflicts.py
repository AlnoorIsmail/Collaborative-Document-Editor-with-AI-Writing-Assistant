from app.backend.tests.conftest import create_test_client
from app.backend.tests.test_documents import create_user_and_token


def _grant_role(client, *, document_id: int, owner_token: str, user_id: int, role: str) -> None:
    response = client.post(
        f"/v1/documents/{document_id}/permissions",
        json={
            "grantee_type": "user",
            "user_id": f"usr_{user_id}",
            "role": role,
            "ai_allowed": role in {"owner", "editor"},
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 201


def _create_conflict(client, *, document_id: int, token: str, local_user_id: int, remote_user_id: int):
    response = client.post(
        f"/v1/documents/{document_id}/conflicts",
        json={
            "conflict_key": f"conflict:{document_id}:batch-local:batch-remote",
            "source_revision": 0,
            "source_collab_version": 0,
            "local_candidate": {
                "batch_id": "batch-local",
                "client_id": "client-local",
                "user_id": local_user_id,
                "user_display_name": "Owner",
                "range": {"start": 0, "end": 8},
                "candidate_content_snapshot": "My draft",
                "exact_text_snapshot": "Original",
                "prefix_context": "",
                "suffix_context": " ending",
            },
            "remote_candidate": {
                "batch_id": "batch-remote",
                "client_id": "client-remote",
                "user_id": remote_user_id,
                "user_display_name": "Editor",
                "range": {"start": 0, "end": 8},
                "candidate_content_snapshot": "Their draft",
                "exact_text_snapshot": "Original",
                "prefix_context": "",
                "suffix_context": " ending",
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    return response.json()


def test_conflicts_persist_and_list_for_collaborators() -> None:
    client = create_test_client()
    owner, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    editor, editor_token = create_user_and_token(client, "editor@example.com", "Editor")
    create_response = client.post(
        "/v1/documents",
        json={"title": "Conflict Doc", "initial_content": "Original ending"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    document_id = create_response.json()["document_id"]
    _grant_role(
        client,
        document_id=document_id,
        owner_token=owner_token,
        user_id=editor["user_id"],
        role="editor",
    )

    created_conflict = _create_conflict(
        client,
        document_id=document_id,
        token=owner_token,
        local_user_id=owner["user_id"],
        remote_user_id=editor["user_id"],
    )

    listed = client.get(
        f"/v1/documents/{document_id}/conflicts",
        headers={"Authorization": f"Bearer {editor_token}"},
    )

    assert listed.status_code == 200
    assert listed.json()[0]["conflict_id"] == created_conflict["conflict_id"]
    assert listed.json()[0]["status"] == "open"
    assert len(listed.json()[0]["candidates"]) == 2


def test_resolving_conflict_updates_document_and_clears_open_list() -> None:
    client = create_test_client()
    owner, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    editor, _ = create_user_and_token(client, "editor@example.com", "Editor")
    create_response = client.post(
        "/v1/documents",
        json={"title": "Conflict Doc", "initial_content": "Original ending"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    document_id = create_response.json()["document_id"]
    conflict = _create_conflict(
        client,
        document_id=document_id,
        token=owner_token,
        local_user_id=owner["user_id"],
        remote_user_id=editor["user_id"],
    )

    resolve_response = client.post(
        f"/v1/documents/{document_id}/conflicts/{conflict['conflict_id']}/resolve",
        json={"candidate_id": conflict["candidates"][1]["candidate_id"]},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    document_response = client.get(
        f"/v1/documents/{document_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    open_conflicts = client.get(
        f"/v1/documents/{document_id}/conflicts",
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert resolve_response.status_code == 200
    assert resolve_response.json()["status"] == "resolved"
    assert document_response.status_code == 200
    assert document_response.json()["current_content"].startswith("Their draft")
    assert open_conflicts.json() == []


def test_viewer_can_read_conflicts_but_cannot_resolve_them() -> None:
    client = create_test_client()
    owner, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    editor, _ = create_user_and_token(client, "editor@example.com", "Editor")
    viewer, viewer_token = create_user_and_token(client, "viewer@example.com", "Viewer")
    create_response = client.post(
        "/v1/documents",
        json={"title": "Conflict Doc", "initial_content": "Original ending"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    document_id = create_response.json()["document_id"]
    _grant_role(
        client,
        document_id=document_id,
        owner_token=owner_token,
        user_id=viewer["user_id"],
        role="viewer",
    )

    conflict = _create_conflict(
        client,
        document_id=document_id,
        token=owner_token,
        local_user_id=owner["user_id"],
        remote_user_id=editor["user_id"],
    )

    listed = client.get(
        f"/v1/documents/{document_id}/conflicts",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    resolve_attempt = client.post(
        f"/v1/documents/{document_id}/conflicts/{conflict['conflict_id']}/resolve",
        json={"resolved_content": "Manual merge"},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert listed.status_code == 200
    assert listed.json()[0]["conflict_id"] == conflict["conflict_id"]
    assert resolve_attempt.status_code == 403


def test_conflicts_are_marked_stale_when_anchor_cannot_be_relocated() -> None:
    client = create_test_client()
    owner, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    editor, _ = create_user_and_token(client, "editor@example.com", "Editor")
    create_response = client.post(
        "/v1/documents",
        json={"title": "Conflict Doc", "initial_content": "Original ending"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    document_id = create_response.json()["document_id"]
    conflict = _create_conflict(
        client,
        document_id=document_id,
        token=owner_token,
        local_user_id=owner["user_id"],
        remote_user_id=editor["user_id"],
    )

    update_response = client.patch(
        f"/v1/documents/{document_id}/content",
        json={
            "content": "Completely different text",
            "base_revision": 0,
            "line_spacing": 1.15,
            "save_source": "manual",
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    listed = client.get(
        f"/v1/documents/{document_id}/conflicts",
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert update_response.status_code == 200
    assert listed.status_code == 200
    assert listed.json()[0]["conflict_id"] == conflict["conflict_id"]
    assert listed.json()[0]["status"] == "stale"
    assert listed.json()[0]["stale"] is True
    assert listed.json()[0]["anchor_range"] is None


def test_conflict_ai_merge_streams_a_reviewable_suggestion() -> None:
    client = create_test_client()
    owner, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    editor, _ = create_user_and_token(client, "editor@example.com", "Editor")
    create_response = client.post(
        "/v1/documents",
        json={"title": "Conflict Doc", "initial_content": "Original ending"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    document_id = create_response.json()["document_id"]
    conflict = _create_conflict(
        client,
        document_id=document_id,
        token=owner_token,
        local_user_id=owner["user_id"],
        remote_user_id=editor["user_id"],
    )

    response = client.post(
        f"/v1/documents/{document_id}/conflicts/{conflict['conflict_id']}/ai-merge/stream",
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert response.status_code == 202
    assert "event: meta" in response.text
    assert "event: complete" in response.text
