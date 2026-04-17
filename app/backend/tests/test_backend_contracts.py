"""Assignment-facing backend contract tests.

These tests validate that the minimal backend skeleton can be exercised
end to end by a client and that the JSON contracts stay stable.
"""


def register_and_login(client) -> tuple[str, int]:
    register_response = client.post(
        "/v1/auth/register",
        json={
            "email": "integration@example.com",
            "display_name": "Integration User",
            "password": "strong-password",
        },
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/v1/auth/login",
        json={
            "email": "integration@example.com",
            "password": "strong-password",
        },
    )
    assert login_response.status_code == 200
    body = login_response.json()
    return body["access_token"], body["user"]["user_id"]


def test_backend_document_flow_contracts(client) -> None:
    token, user_id = register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    create_response = client.post(
        "/v1/documents",
        headers=headers,
        json={
            "title": "Implementation Document",
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
    assert create_body["title"] == "Implementation Document"
    assert create_body["current_content"] == "First draft"
    assert create_body["content_format"] == "plain_text"
    assert create_body["owner"] == {
        "user_id": user_id,
        "display_name": "Integration User",
    }
    assert create_body["owner_user_id"] == user_id
    assert create_body["role"] == "owner"
    assert create_body["ai_enabled"] is True
    assert create_body["revision"] == 0
    assert create_body["latest_version_id"] is None
    assert create_body["latest_version"] is None

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
    assert get_body["title"] == "Implementation Document"
    assert get_body["current_content"] == "First draft"
    assert get_body["owner"] == {
        "user_id": user_id,
        "display_name": "Integration User",
    }
    assert get_body["owner_user_id"] == user_id
    assert get_body["revision"] == 0
    assert get_body["latest_version"] is None

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
    token, user_id = register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    initial_content = "First draft"

    document_response = client.post(
        "/v1/documents",
        headers=headers,
        json={
            "title": "Realtime Contract Doc",
            "initial_content": initial_content,
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
        "resync_required",
        "missed_revision_count",
        "active_collaborators",
    }
    assert session_body["session_id"] == "sess_1"
    assert session_body["session_token"]
    assert session_body["document_id"] == document_id
    assert session_body["revision"] == 0
    assert session_body["resync_required"] is False
    assert session_body["missed_revision_count"] == 0
    assert len(session_body["active_collaborators"]) == 1
    assert set(session_body["active_collaborators"][0]) == {
        "user_id",
        "session_id",
        "last_known_revision",
        "joined_at",
        "last_seen_at",
    }

    create_ai_response = client.post(
        f"/v1/documents/{document_id}/ai/interactions",
        headers=headers,
        json={
            "feature_type": "rewrite",
            "scope_type": "selection",
            "selection_range": {"start": 0, "end": 11},
            "selected_text_snapshot": "First draft",
            "surrounding_context": "Short implementation document",
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
        "scope_type": "selection",
        "user_id": user_id,
        "status": "completed",
        "created_at": create_ai_body["created_at"],
        "model_name": "local-rewrite-fallback",
        "outcome": None,
        "total_tokens": list_ai_body[0]["total_tokens"],
    }
    assert list_ai_body[0]["total_tokens"] > 0

    detail_response = client.get(
        f"/v1/ai/interactions/{create_ai_body['interaction_id']}",
        headers=headers,
    )

    assert detail_response.status_code == 200
    detail_body = detail_response.json()
    assert set(detail_body) == {
        "interaction_id",
        "feature_type",
        "scope_type",
        "status",
        "document_id",
        "base_revision",
        "created_at",
        "completed_at",
        "rendered_prompt",
        "selected_range",
        "selected_text_snapshot",
        "surrounding_context",
        "user_instruction",
        "parameters",
        "outcome",
        "outcome_recorded_at",
        "suggestion",
    }
    assert detail_body["interaction_id"] == create_ai_body["interaction_id"]
    assert detail_body["feature_type"] == "rewrite"
    assert detail_body["scope_type"] == "selection"
    assert detail_body["status"] == "completed"
    assert detail_body["document_id"] == document_id
    assert detail_body["base_revision"] == 0
    assert detail_body["selected_range"] == {"start": 0, "end": 11}
    assert detail_body["selected_text_snapshot"] == "First draft"
    assert detail_body["surrounding_context"] == "Short implementation document"
    assert detail_body["user_instruction"] == "Make this more formal"
    assert detail_body["parameters"] == {"tone": "formal"}
    assert detail_body["outcome"] is None
    assert detail_body["outcome_recorded_at"] is None
    assert detail_body["suggestion"] == {
        "suggestion_id": "sug_1",
        "generated_output": "First draft.",
        "model_name": "local-rewrite-fallback",
        "stale": False,
        "usage": {
            "prompt_tokens": detail_body["suggestion"]["usage"]["prompt_tokens"],
            "completion_tokens": detail_body["suggestion"]["usage"]["completion_tokens"],
            "total_tokens": detail_body["suggestion"]["usage"]["total_tokens"],
            "estimated_cost_usd": None,
        },
    }
    assert detail_body["suggestion"]["usage"]["total_tokens"] > 0

    accept_response = client.post(
        f"/v1/ai/suggestions/{detail_body['suggestion']['suggestion_id']}/accept",
        headers=headers,
        json={"apply_to_range": {"start": 0, "end": len(initial_content)}},
    )

    assert accept_response.status_code == 200
    assert accept_response.json() == {
        "suggestion_id": detail_body["suggestion"]["suggestion_id"],
        "outcome": "accepted",
        "applied": True,
        "new_revision": 1,
    }

    post_accept_detail = client.get(
        f"/v1/ai/interactions/{create_ai_body['interaction_id']}",
        headers=headers,
    )
    assert post_accept_detail.status_code == 200
    assert post_accept_detail.json()["outcome"] == "accepted"
    assert post_accept_detail.json()["outcome_recorded_at"]
