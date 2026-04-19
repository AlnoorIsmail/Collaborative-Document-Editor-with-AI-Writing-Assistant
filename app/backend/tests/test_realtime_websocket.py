from app.backend.tests.conftest import create_test_client
from app.backend.tests.test_documents import create_user_and_token


def _receive_until(socket, expected_type: str):
    for _ in range(6):
        message = socket.receive_json()
        if message.get("type") == expected_type:
            return message
    raise AssertionError(f"Did not receive websocket event {expected_type!r}")


def _open_socket(
    client,
    *,
    document_id: int,
    session_id: str,
    session_token: str,
    access_token: str,
):
    return client.websocket_connect(
        (
            f"/v1/documents/{document_id}/sessions/{session_id}/ws"
            f"?session_token={session_token}&access_token={access_token}"
        )
    )


def test_websocket_rejects_invalid_session_token() -> None:
    client = create_test_client()
    _, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    create_document = client.post(
        "/v1/documents",
        json={"title": "Realtime Doc", "initial_content": "Draft"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    document_id = create_document.json()["document_id"]
    bootstrap = client.post(
        f"/v1/documents/{document_id}/sessions",
        json={"last_known_revision": 0},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    session_id = bootstrap.json()["session_id"]

    try:
        with _open_socket(
            client,
            document_id=document_id,
            session_id=session_id,
            session_token="bad-token",
            access_token=owner_token,
        ):
            raise AssertionError("Expected websocket authentication to fail.")
    except Exception:
        pass


def test_websocket_rejects_mismatched_signed_session_token() -> None:
    client = create_test_client()
    _, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    first_document = client.post(
        "/v1/documents",
        json={"title": "Doc One", "initial_content": "Draft"},
        headers={"Authorization": f"Bearer {owner_token}"},
    ).json()["document_id"]
    second_document = client.post(
        "/v1/documents",
        json={"title": "Doc Two", "initial_content": "Draft"},
        headers={"Authorization": f"Bearer {owner_token}"},
    ).json()["document_id"]
    first_bootstrap = client.post(
        f"/v1/documents/{first_document}/sessions",
        json={"last_known_revision": 0},
        headers={"Authorization": f"Bearer {owner_token}"},
    ).json()
    second_bootstrap = client.post(
        f"/v1/documents/{second_document}/sessions",
        json={"last_known_revision": 0},
        headers={"Authorization": f"Bearer {owner_token}"},
    ).json()

    try:
        with _open_socket(
            client,
            document_id=second_document,
            session_id=second_bootstrap["session_id"],
            session_token=first_bootstrap["session_token"],
            access_token=owner_token,
        ):
            raise AssertionError("Expected websocket authentication to fail.")
    except Exception:
        pass


def test_websocket_supports_basic_message_exchange() -> None:
    client = create_test_client()
    _, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    create_document = client.post(
        "/v1/documents",
        json={"title": "Realtime Doc", "initial_content": "Draft"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    document_id = create_document.json()["document_id"]
    bootstrap = client.post(
        f"/v1/documents/{document_id}/sessions",
        json={"last_known_revision": 0},
        headers={"Authorization": f"Bearer {owner_token}"},
    ).json()

    with _open_socket(
        client,
        document_id=document_id,
        session_id=bootstrap["session_id"],
        session_token=bootstrap["session_token"],
        access_token=owner_token,
    ) as socket:
        joined = _receive_until(socket, "session_joined")
        presence = _receive_until(socket, "presence_snapshot")

        assert joined["content"] == "Draft"
        assert joined["line_spacing"] == 1.15
        assert presence["presence"][0]["display_name"] == "Owner"

        socket.send_json(
            {
                "type": "content_update",
                "content": "Realtime saved content",
                "line_spacing": 1.5,
                "base_revision": 0,
            }
        )
        update = _receive_until(socket, "content_updated")
        assert update["revision"] == 1
        assert update["content"] == "Realtime saved content"
        assert update["line_spacing"] == 1.5
        assert update["actor_display_name"] == "Owner"

        socket.send_json(
            {
                "type": "content_update",
                "content": "Stale content",
                "line_spacing": 1.15,
                "base_revision": 0,
            }
        )
        conflict = _receive_until(socket, "conflict_detected")
        assert conflict["revision"] == 1
        assert conflict["content"] == "Realtime saved content"
        assert conflict["line_spacing"] == 1.5

    refreshed_document = client.get(
        f"/v1/documents/{document_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert refreshed_document.status_code == 200
    assert refreshed_document.json()["current_content"] == "Realtime saved content"
    assert refreshed_document.json()["line_spacing"] == 1.5


def test_websocket_broadcasts_selection_awareness_and_clears_stale_ranges() -> None:
    client = create_test_client()
    _, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    create_document = client.post(
        "/v1/documents",
        json={"title": "Realtime Doc", "initial_content": "Draft"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    document_id = create_document.json()["document_id"]
    bootstrap = client.post(
        f"/v1/documents/{document_id}/sessions",
        json={"last_known_revision": 0},
        headers={"Authorization": f"Bearer {owner_token}"},
    ).json()

    with _open_socket(
        client,
        document_id=document_id,
        session_id=bootstrap["session_id"],
        session_token=bootstrap["session_token"],
        access_token=owner_token,
    ) as socket:
        joined = _receive_until(socket, "session_joined")
        assert joined["awareness"][0]["selection_from"] is None
        _receive_until(socket, "presence_snapshot")
        initial_awareness = _receive_until(socket, "awareness_snapshot")
        assert initial_awareness["collaborators"][0]["selection_from"] is None

        socket.send_json(
            {
                "type": "selection_update",
                "from": 2,
                "to": 5,
                "direction": "forward",
                "collab_version": 0,
            }
        )

        awareness = _receive_until(socket, "awareness_snapshot")
        assert awareness["collaborators"][0]["selection_from"] == 2
        assert awareness["collaborators"][0]["selection_to"] == 5
        assert awareness["collaborators"][0]["color_token"] == "presence-1"

        socket.send_json(
            {
                "type": "selection_clear",
            }
        )

        manually_cleared_awareness = _receive_until(socket, "awareness_snapshot")
        assert manually_cleared_awareness["collaborators"][0]["selection_from"] is None
        assert manually_cleared_awareness["collaborators"][0]["selection_to"] is None

        socket.send_json(
            {
                "type": "selection_update",
                "from": 2,
                "to": 5,
                "direction": "forward",
                "collab_version": 0,
            }
        )

        awareness = _receive_until(socket, "awareness_snapshot")
        assert awareness["collaborators"][0]["selection_from"] == 2
        assert awareness["collaborators"][0]["selection_to"] == 5

        socket.send_json(
            {
                "type": "step_update",
                "batch_id": "batch-awareness",
                "version": 0,
                "client_id": "client-awareness",
                "steps": [{"mock": "replace", "text": "Drafting"}],
                "content": "Drafting",
                "line_spacing": 1.15,
                "affected_range": {"start": 1, "end": 5},
                "candidate_content_snapshot": "Drafting",
                "exact_text_snapshot": "Draft",
                "prefix_context": "",
                "suffix_context": "",
            }
        )

        _receive_until(socket, "steps_applied")
        cleared_awareness = _receive_until(socket, "awareness_snapshot")
        assert cleared_awareness["collaborators"][0]["selection_from"] is None
        assert cleared_awareness["collaborators"][0]["selection_to"] is None


def test_session_bootstrap_reports_live_connected_collaborators() -> None:
    client = create_test_client()
    owner, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    editor, editor_token = create_user_and_token(client, "editor@example.com", "Editor")
    document_id = client.post(
        "/v1/documents",
        json={"title": "Realtime Doc", "initial_content": "Draft"},
        headers={"Authorization": f"Bearer {owner_token}"},
    ).json()["document_id"]
    client.post(
        f"/v1/documents/{document_id}/permissions",
        json={
            "grantee_type": "user",
            "user_id": editor["user_id"],
            "role": "editor",
            "ai_allowed": True,
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    owner_bootstrap = client.post(
        f"/v1/documents/{document_id}/sessions",
        json={"last_known_revision": 0},
        headers={"Authorization": f"Bearer {owner_token}"},
    ).json()

    with _open_socket(
        client,
        document_id=document_id,
        session_id=owner_bootstrap["session_id"],
        session_token=owner_bootstrap["session_token"],
        access_token=owner_token,
    ) as owner_socket:
        _receive_until(owner_socket, "session_joined")
        _receive_until(owner_socket, "presence_snapshot")

        editor_bootstrap = client.post(
            f"/v1/documents/{document_id}/sessions",
            json={"last_known_revision": 0},
            headers={"Authorization": f"Bearer {editor_token}"},
        ).json()

        assert [entry["display_name"] for entry in editor_bootstrap["active_collaborators"]] == [
            "Owner"
        ]


def test_websocket_supports_step_sync_and_resync() -> None:
    client = create_test_client()
    _, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    create_document = client.post(
        "/v1/documents",
        json={"title": "Realtime Doc", "initial_content": "Draft"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    document_id = create_document.json()["document_id"]
    bootstrap = client.post(
        f"/v1/documents/{document_id}/sessions",
        json={"last_known_revision": 0},
        headers={"Authorization": f"Bearer {owner_token}"},
    ).json()

    with _open_socket(
        client,
        document_id=document_id,
        session_id=bootstrap["session_id"],
        session_token=bootstrap["session_token"],
        access_token=owner_token,
    ) as socket:
        joined = _receive_until(socket, "session_joined")
        assert joined["collab_version"] == 0

        socket.send_json(
            {
                "type": "step_update",
                "batch_id": "batch-1",
                "version": 0,
                "client_id": "client-1",
                "steps": [{"mock": "replace", "text": "Realtime stepped content"}],
                "content": "Realtime stepped content",
                "line_spacing": 1.15,
                "affected_range": {"start": 1, "end": 5},
                "candidate_content_snapshot": "Realtime stepped content",
                "exact_text_snapshot": "Draft",
                "prefix_context": "",
                "suffix_context": "",
            }
        )

        applied = _receive_until(socket, "steps_applied")
        assert applied["collab_version"] == 1
        assert applied["content"] == "Realtime stepped content"
        assert applied["steps"] == [{"mock": "replace", "text": "Realtime stepped content"}]
        assert applied["batch"]["batch_id"] == "batch-1"
        assert applied["batch"]["affected_range"] == {"start": 1, "end": 5}

        socket.send_json(
            {
                "type": "step_update",
                "batch_id": "batch-2",
                "version": 0,
                "client_id": "client-2",
                "steps": [{"mock": "replace", "text": "Stale content"}],
                "content": "Stale content",
                "line_spacing": 1.15,
                "affected_range": {"start": 1, "end": 5},
                "candidate_content_snapshot": "Stale content",
                "exact_text_snapshot": "Draft",
                "prefix_context": "",
                "suffix_context": "",
            }
        )

        resync = _receive_until(socket, "steps_resync")
        assert resync["full_reset"] is False
        assert resync["collab_version"] == 1
        assert resync["steps"] == [{"mock": "replace", "text": "Realtime stepped content"}]
        assert resync["client_ids"] == ["client-1"]
        assert resync["batches"][0]["batch_id"] == "batch-1"

    refreshed_document = client.get(
        f"/v1/documents/{document_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert refreshed_document.status_code == 200
    assert refreshed_document.json()["current_content"] == "Realtime stepped content"
