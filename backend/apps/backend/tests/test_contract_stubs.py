"""Contract-shaped stub response tests for session and AI endpoints."""

CREATE_AI_PAYLOAD = {
    "feature_type": "rewrite",
    "scope_type": "selection",
    "selection_range": {"start": 100, "end": 180},
    "selected_text_snapshot": "Original selected paragraph",
    "surrounding_context": "Previous and next sentence",
    "user_prompt": "Make this more formal",
    "base_revision": 22,
    "options": {"tone": "formal"},
}


def create_ai_interaction(client, auth_headers, document_id: str = "doc_101") -> dict:
    response = client.post(
        f"/v1/documents/{document_id}/ai/interactions",
        headers=auth_headers,
        json=CREATE_AI_PAYLOAD,
    )

    assert response.status_code == 202
    return response.json()


def test_session_bootstrap_returns_contract_shaped_response(client, auth_headers) -> None:
    response = client.post(
        "/v1/documents/doc_101/sessions",
        headers=auth_headers,
        json={"last_known_revision": 22},
    )

    assert response.status_code == 201
    assert response.json() == {
        "session_id": "sess_1",
        "session_token": "realtime-jwt",
        "document_id": "doc_101",
        "revision": 22,
        "realtime_url": "wss://api.example.com/realtime",
    }


def test_create_ai_interaction_returns_pending_stub(client, auth_headers) -> None:
    response = create_ai_interaction(client, auth_headers)

    assert response == {
        "interaction_id": "ai_1",
        "status": "pending",
        "document_id": "doc_101",
        "base_revision": 22,
        "created_at": "2026-03-25T10:40:00Z",
    }


def test_list_ai_interactions_returns_history_stub(client, auth_headers) -> None:
    create_ai_interaction(client, auth_headers)

    response = client.get(
        "/v1/documents/doc_101/ai/interactions",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "interaction_id": "ai_1",
            "feature_type": "rewrite",
            "user_id": "usr_test",
            "status": "completed",
            "created_at": "2026-03-25T10:40:00Z",
        }
    ]


def test_get_ai_interaction_returns_suggestion_stub(client, auth_headers) -> None:
    interaction = create_ai_interaction(client, auth_headers)

    response = client.get(
        f"/v1/ai/interactions/{interaction['interaction_id']}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json() == {
        "interaction_id": "ai_1",
        "status": "completed",
        "document_id": "doc_101",
        "base_revision": 22,
        "suggestion": {
            "suggestion_id": "sug_1",
            "generated_output": "More formal rewritten paragraph",
            "model_name": "gpt-x",
            "stale": False,
        },
    }


def test_accept_reject_and_apply_edited_suggestion_stubs(client, auth_headers) -> None:
    interaction = create_ai_interaction(client, auth_headers)
    detail_response = client.get(
        f"/v1/ai/interactions/{interaction['interaction_id']}",
        headers=auth_headers,
    )
    suggestion_id = detail_response.json()["suggestion"]["suggestion_id"]

    accept_response = client.post(
        f"/v1/ai/suggestions/{suggestion_id}/accept",
        headers=auth_headers,
        json={"apply_to_range": {"start": 100, "end": 180}},
    )
    reject_response = client.post(
        f"/v1/ai/suggestions/{suggestion_id}/reject",
        headers=auth_headers,
    )
    apply_response = client.post(
        f"/v1/ai/suggestions/{suggestion_id}/apply-edited",
        headers=auth_headers,
        json={
            "edited_output": "User-modified version of the suggestion",
            "apply_to_range": {"start": 100, "end": 180},
        },
    )

    assert accept_response.status_code == 200
    assert accept_response.json() == {
        "suggestion_id": suggestion_id,
        "outcome": "accepted",
        "applied": True,
        "new_revision": 23,
    }

    assert reject_response.status_code == 200
    assert reject_response.json() == {
        "suggestion_id": suggestion_id,
        "outcome": "rejected",
    }

    assert apply_response.status_code == 200
    assert apply_response.json() == {
        "suggestion_id": suggestion_id,
        "outcome": "modified",
        "applied": True,
        "new_revision": 23,
    }
