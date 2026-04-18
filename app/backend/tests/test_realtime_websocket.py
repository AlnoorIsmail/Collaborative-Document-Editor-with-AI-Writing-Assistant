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
