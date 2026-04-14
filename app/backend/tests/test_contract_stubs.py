"""Contract-shaped response tests for session and AI endpoints."""

CREATE_AI_PAYLOAD = {
    "feature_type": "rewrite",
    "scope_type": "selection",
    "selection_range": {"start": 0, "end": 11},
    "selected_text_snapshot": "First draft",
    "surrounding_context": "Previous and next sentence",
    "user_prompt": "Make this more formal",
    "base_revision": 0,
    "options": {"tone": "formal"},
}


def create_document(client, auth_headers, title: str = "Contract Doc") -> int:
    response = client.post(
        "/v1/documents",
        headers=auth_headers,
        json={
            "title": title,
            "initial_content": "First draft",
            "content_format": "plain_text",
            "ai_enabled": True,
        },
    )

    assert response.status_code == 201
    return response.json()["document_id"]


def create_ai_interaction(client, auth_headers, document_id: int) -> dict:
    response = client.post(
        f"/v1/documents/{document_id}/ai/interactions",
        headers=auth_headers,
        json=CREATE_AI_PAYLOAD,
    )

    assert response.status_code == 202
    return response.json()


def test_session_bootstrap_returns_contract_shaped_response(
    client, auth_headers
) -> None:
    document_id = create_document(client, auth_headers)

    response = client.post(
        f"/v1/documents/{document_id}/sessions",
        headers=auth_headers,
        json={"last_known_revision": 0},
    )

    assert response.status_code == 201
    assert response.json() == {
        "session_id": "sess_1",
        "session_token": "realtime-jwt",
        "document_id": document_id,
        "revision": 0,
        "realtime_url": "wss://api.example.com/realtime",
    }


def test_create_ai_interaction_returns_pending_stub(client, auth_headers) -> None:
    document_id = create_document(client, auth_headers)
    response = create_ai_interaction(client, auth_headers, document_id)

    assert response == {
        "interaction_id": "ai_1",
        "status": "pending",
        "document_id": document_id,
        "base_revision": 0,
        "created_at": "2026-03-25T10:40:00Z",
    }


def test_list_ai_interactions_returns_history_stub(client, auth_headers) -> None:
    document_id = create_document(client, auth_headers)
    create_ai_interaction(client, auth_headers, document_id)

    response = client.get(
        f"/v1/documents/{document_id}/ai/interactions",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "interaction_id": "ai_1",
            "feature_type": "rewrite",
            "user_id": 1,
            "status": "completed",
            "created_at": "2026-03-25T10:40:00Z",
        }
    ]


def test_get_ai_interaction_returns_suggestion_stub(client, auth_headers) -> None:
    document_id = create_document(client, auth_headers)
    interaction = create_ai_interaction(client, auth_headers, document_id)

    response = client.get(
        f"/v1/ai/interactions/{interaction['interaction_id']}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json() == {
        "interaction_id": "ai_1",
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


def test_accept_reject_and_apply_edited_suggestion_stubs(client, auth_headers) -> None:
    accept_document_id = create_document(client, auth_headers, title="Accept Doc")
    accept_interaction = create_ai_interaction(client, auth_headers, accept_document_id)
    accept_detail_response = client.get(
        f"/v1/ai/interactions/{accept_interaction['interaction_id']}",
        headers=auth_headers,
    )
    accept_suggestion_id = accept_detail_response.json()["suggestion"]["suggestion_id"]

    reject_document_id = create_document(client, auth_headers, title="Reject Doc")
    reject_interaction = create_ai_interaction(client, auth_headers, reject_document_id)
    reject_detail_response = client.get(
        f"/v1/ai/interactions/{reject_interaction['interaction_id']}",
        headers=auth_headers,
    )
    reject_suggestion_id = reject_detail_response.json()["suggestion"]["suggestion_id"]

    apply_document_id = create_document(client, auth_headers, title="Apply Doc")
    apply_interaction = create_ai_interaction(client, auth_headers, apply_document_id)
    apply_detail_response = client.get(
        f"/v1/ai/interactions/{apply_interaction['interaction_id']}",
        headers=auth_headers,
    )
    apply_suggestion_id = apply_detail_response.json()["suggestion"]["suggestion_id"]

    accept_response = client.post(
        f"/v1/ai/suggestions/{accept_suggestion_id}/accept",
        headers=auth_headers,
        json={"apply_to_range": {"start": 0, "end": 11}},
    )
    reject_response = client.post(
        f"/v1/ai/suggestions/{reject_suggestion_id}/reject",
        headers=auth_headers,
    )
    apply_response = client.post(
        f"/v1/ai/suggestions/{apply_suggestion_id}/apply-edited",
        headers=auth_headers,
        json={
            "edited_output": "User-modified version of the suggestion",
            "apply_to_range": {"start": 0, "end": 11},
        },
    )

    assert accept_response.status_code == 200
    assert accept_response.json() == {
        "suggestion_id": accept_suggestion_id,
        "outcome": "accepted",
        "applied": True,
        "new_revision": 1,
    }

    assert reject_response.status_code == 200
    assert reject_response.json() == {
        "suggestion_id": reject_suggestion_id,
        "outcome": "rejected",
    }

    assert apply_response.status_code == 200
    assert apply_response.json() == {
        "suggestion_id": apply_suggestion_id,
        "outcome": "modified",
        "applied": True,
        "new_revision": 1,
    }
