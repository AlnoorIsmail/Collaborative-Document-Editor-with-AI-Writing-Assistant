"""Assignment-facing backend contract tests.

These tests validate that the backend can be exercised end to end by a client
and that the JSON contracts stay stable.
"""


def register_and_login(client) -> str:
    register_response = client.post(
        "/v1/auth/register",
        json={
            "email": "backend@example.com",
            "display_name": "Backend User",
            "password": "strong-password",
        },
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/v1/auth/login",
        json={
            "email": "backend@example.com",
            "password": "strong-password",
        },
    )
    assert login_response.status_code == 200
    return login_response.json()["access_token"]


def test_backend_document_flow_contracts(client) -> None:
    token = register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    create_response = client.post(
        "/v1/documents",
        headers=headers,
        json={
            "title": "Backend Contract Document",
            "initial_content": "First draft",
            "content_format": "plain_text",
            "ai_enabled": True,
        },
    )

    assert create_response.status_code == 201
    create_body = create_response.json()
    assert set(create_body) == {
        "document_id",
        "title",
        "current_content",
        "content_format",
        "owner",
        "owner_user_id",
        "role",
        "ai_enabled",
        "revision",
        "latest_version_id",
        "latest_version",
        "created_at",
        "updated_at",
    }
    assert create_body["title"] == "Backend Contract Document"
    assert create_body["current_content"] == "First draft"
    assert create_body["content_format"] == "plain_text"
    assert create_body["role"] == "owner"
    assert create_body["ai_enabled"] is True
    assert create_body["latest_version_id"] is None

    document_id = create_body["document_id"]

    get_response = client.get(
        f"/v1/documents/{document_id}",
        headers=headers,
    )

    assert get_response.status_code == 200
    get_body = get_response.json()
    assert set(get_body) == {
        "document_id",
        "title",
        "current_content",
        "content_format",
        "owner",
        "owner_user_id",
        "role",
        "ai_enabled",
        "revision",
        "latest_version_id",
        "latest_version",
        "created_at",
        "updated_at",
    }
    assert get_body["document_id"] == document_id
    assert get_body["title"] == "Backend Contract Document"
    assert get_body["current_content"] == "First draft"

    save_response = client.patch(
        f"/v1/documents/{document_id}/content",
        headers=headers,
        json={
            "content": "Updated draft from client",
            "base_revision": 0,
        },
    )

    assert save_response.status_code == 200
    save_body = save_response.json()
    assert save_body == {
        "document_id": document_id,
        "latest_version_id": 1,
        "revision": 1,
        "saved_at": save_body["saved_at"],
    }


def test_backend_realtime_and_ai_contracts(client) -> None:
    token = register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    document_response = client.post(
        "/v1/documents",
        headers=headers,
        json={
            "title": "Realtime Contract Doc",
            "initial_content": "First draft",
        },
    )
    document_id = document_response.json()["document_id"]

    session_response = client.post(
        f"/v1/documents/{document_id}/sessions",
        headers=headers,
        json={"last_known_revision": 0},
    )

    assert session_response.status_code == 201
    session_body = session_response.json()
    assert set(session_body) == {
        "session_id",
        "session_token",
        "document_id",
        "revision",
        "realtime_url",
    }
    assert session_body["document_id"] == document_id
    assert session_body["revision"] == 0

    create_ai_response = client.post(
        f"/v1/documents/{document_id}/ai/interactions",
        headers=headers,
        json={
            "feature_type": "rewrite",
            "scope_type": "selection",
            "selection_range": {"start": 0, "end": 11},
            "selected_text_snapshot": "First draft",
            "surrounding_context": "Short backend document",
            "user_prompt": "Make this more formal",
            "base_revision": 0,
            "options": {"tone": "formal"},
        },
    )

    assert create_ai_response.status_code == 202
    create_ai_body = create_ai_response.json()
    assert set(create_ai_body) == {
        "interaction_id",
        "status",
        "document_id",
        "base_revision",
        "created_at",
    }
    assert create_ai_body["status"] == "pending"
    assert create_ai_body["document_id"] == document_id
    assert create_ai_body["base_revision"] == 0

    list_ai_response = client.get(
        f"/v1/documents/{document_id}/ai/interactions",
        headers=headers,
    )

    assert list_ai_response.status_code == 200
    list_ai_body = list_ai_response.json()
    assert len(list_ai_body) == 1
    assert list_ai_body[0] == {
        "interaction_id": create_ai_body["interaction_id"],
        "feature_type": "rewrite",
        "user_id": 1,
        "status": "completed",
        "created_at": create_ai_body["created_at"],
    }

    detail_response = client.get(
        f"/v1/ai/interactions/{create_ai_body['interaction_id']}",
        headers=headers,
    )

    assert detail_response.status_code == 200
    detail_body = detail_response.json()
    assert detail_body == {
        "interaction_id": create_ai_body["interaction_id"],
        "status": "completed",
        "document_id": document_id,
        "base_revision": 0,
        "suggestion": {
            "suggestion_id": "sug_1",
            "generated_output": "More formal rewritten paragraph",
            "model_name": "gpt-x",
            "stale": False,
        },
    }

    accept_response = client.post(
        "/v1/ai/suggestions/sug_1/accept",
        headers=headers,
        json={"apply_to_range": {"start": 0, "end": 11}},
    )

    assert accept_response.status_code == 200
    assert accept_response.json() == {
        "suggestion_id": "sug_1",
        "outcome": "accepted",
        "applied": True,
        "new_revision": 1,
    }
