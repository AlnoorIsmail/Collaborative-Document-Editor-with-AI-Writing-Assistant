"""Contract-shaped tests for session and AI endpoints backed by stub repositories."""

DEFAULT_DOCUMENT_CONTENT = "Original selected paragraph"
CREATE_AI_PAYLOAD = {
    "feature_type": "rewrite",
    "scope_type": "selection",
    "selection_range": {"start": 0, "end": len(DEFAULT_DOCUMENT_CONTENT)},
    "selected_text_snapshot": DEFAULT_DOCUMENT_CONTENT,
    "surrounding_context": "Previous and next sentence",
    "user_prompt": "Make this more formal",
    "base_revision": 0,
    "options": {"tone": "formal"},
}


def create_document(
    client,
    auth_headers,
    *,
    initial_content: str = DEFAULT_DOCUMENT_CONTENT,
) -> dict:
    response = client.post(
        "/v1/documents",
        headers=auth_headers,
        json={
            "title": "Contract Test Doc",
            "initial_content": initial_content,
        },
    )

    assert response.status_code == 201
    return response.json()


def create_ai_interaction(client, auth_headers) -> tuple[int, dict]:
    document = create_document(client, auth_headers)
    response = client.post(
        f"/v1/documents/{document['document_id']}/ai/interactions",
        headers=auth_headers,
        json=CREATE_AI_PAYLOAD,
    )

    assert response.status_code == 202
    return document["document_id"], response.json()


def get_suggestion_id(client, auth_headers, interaction_id: str) -> str:
    detail_response = client.get(
        f"/v1/ai/interactions/{interaction_id}",
        headers=auth_headers,
    )

    assert detail_response.status_code == 200
    return detail_response.json()["suggestion"]["suggestion_id"]


def test_session_bootstrap_returns_contract_shaped_response(
    client, auth_headers
) -> None:
    document = create_document(client, auth_headers, initial_content="")
    response = client.post(
        f"/v1/documents/{document['document_id']}/sessions",
        headers=auth_headers,
        json={"last_known_revision": 0},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["session_id"] == "sess_1"
    assert body["session_token"]
    assert body["document_id"] == document["document_id"]
    assert body["revision"] == 0
    assert body["realtime_url"] == "wss://api.example.com/realtime"
    assert body["resync_required"] is False
    assert body["missed_revision_count"] == 0
    assert body["active_collaborators"] == [
        {
            "user_id": 1,
            "display_name": "Fixture User",
            "session_id": "sess_1",
            "last_known_revision": 0,
            "joined_at": body["active_collaborators"][0]["joined_at"],
            "last_seen_at": body["active_collaborators"][0]["last_seen_at"],
        }
    ]


def test_create_ai_interaction_returns_pending_stub(client, auth_headers) -> None:
    document_id, response = create_ai_interaction(client, auth_headers)

    assert response == {
        "interaction_id": "ai_1",
        "status": "pending",
        "document_id": document_id,
        "base_revision": 0,
        "created_at": "2026-03-25T10:40:00Z",
    }


def test_list_ai_interactions_returns_history_stub(client, auth_headers) -> None:
    document_id, interaction = create_ai_interaction(client, auth_headers)

    response = client.get(
        f"/v1/documents/{document_id}/ai/interactions",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "interaction_id": interaction["interaction_id"],
            "feature_type": "rewrite",
            "scope_type": "selection",
            "user_id": 1,
            "status": "completed",
            "created_at": interaction["created_at"],
            "model_name": "local-rewrite-fallback",
            "outcome": None,
            "total_tokens": response.json()[0]["total_tokens"],
        }
    ]
    assert response.json()[0]["total_tokens"] > 0


def test_get_ai_interaction_returns_suggestion_stub(client, auth_headers) -> None:
    document_id, interaction = create_ai_interaction(client, auth_headers)

    response = client.get(
        f"/v1/ai/interactions/{interaction['interaction_id']}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["interaction_id"] == interaction["interaction_id"]
    assert body["feature_type"] == "rewrite"
    assert body["scope_type"] == "selection"
    assert body["status"] == "completed"
    assert body["document_id"] == document_id
    assert body["base_revision"] == 0
    assert body["created_at"] == interaction["created_at"]
    assert body["completed_at"] == "2026-03-25T10:40:02Z"
    assert "FEATURE_TYPE:\nrewrite" in body["rendered_prompt"]
    assert body["selected_range"] == {"start": 0, "end": len(DEFAULT_DOCUMENT_CONTENT)}
    assert body["selected_text_snapshot"] == DEFAULT_DOCUMENT_CONTENT
    assert body["surrounding_context"] == "Previous and next sentence"
    assert body["user_instruction"] == "Make this more formal"
    assert body["parameters"] == {"tone": "formal"}
    assert body["outcome"] is None
    assert body["outcome_recorded_at"] is None
    assert body["suggestion"] == {
        "suggestion_id": "sug_1",
        "generated_output": "Original selected paragraph.",
        "model_name": "local-rewrite-fallback",
        "stale": False,
        "usage": {
            "prompt_tokens": body["suggestion"]["usage"]["prompt_tokens"],
            "completion_tokens": body["suggestion"]["usage"]["completion_tokens"],
            "total_tokens": body["suggestion"]["usage"]["total_tokens"],
            "estimated_cost_usd": None,
        },
    }
    assert body["suggestion"]["usage"]["prompt_tokens"] > 0
    assert body["suggestion"]["usage"]["completion_tokens"] > 0


def test_accept_suggestion_returns_applied_contract(client, auth_headers) -> None:
    document_id, interaction = create_ai_interaction(client, auth_headers)
    suggestion_id = get_suggestion_id(
        client,
        auth_headers,
        interaction["interaction_id"],
    )

    accept_response = client.post(
        f"/v1/ai/suggestions/{suggestion_id}/accept",
        headers=auth_headers,
        json={"apply_to_range": {"start": 0, "end": len(DEFAULT_DOCUMENT_CONTENT)}},
    )

    assert accept_response.status_code == 200
    assert accept_response.json() == {
        "suggestion_id": suggestion_id,
        "outcome": "accepted",
        "applied": True,
        "new_revision": 1,
    }

    document_response = client.get(
        f"/v1/documents/{document_id}",
        headers=auth_headers,
    )
    assert document_response.status_code == 200
    assert document_response.json()["current_content"] == "Original selected paragraph."
    assert document_response.json()["revision"] == 1


def test_reject_suggestion_returns_rejected_contract(client, auth_headers) -> None:
    _, interaction = create_ai_interaction(client, auth_headers)
    suggestion_id = get_suggestion_id(
        client,
        auth_headers,
        interaction["interaction_id"],
    )

    reject_response = client.post(
        f"/v1/ai/suggestions/{suggestion_id}/reject",
        headers=auth_headers,
    )

    assert reject_response.status_code == 200
    assert reject_response.json() == {
        "suggestion_id": suggestion_id,
        "outcome": "rejected",
    }

    detail_response = client.get(
        f"/v1/ai/interactions/{interaction['interaction_id']}",
        headers=auth_headers,
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["outcome"] == "rejected"
    assert detail_response.json()["outcome_recorded_at"]


def test_apply_edited_suggestion_returns_modified_contract(
    client, auth_headers
) -> None:
    document_id, interaction = create_ai_interaction(client, auth_headers)
    suggestion_id = get_suggestion_id(
        client,
        auth_headers,
        interaction["interaction_id"],
    )

    apply_response = client.post(
        f"/v1/ai/suggestions/{suggestion_id}/apply-edited",
        headers=auth_headers,
        json={
            "edited_output": "User-modified version of the suggestion",
            "apply_to_range": {"start": 0, "end": len(DEFAULT_DOCUMENT_CONTENT)},
        },
    )

    assert apply_response.status_code == 200
    assert apply_response.json() == {
        "suggestion_id": suggestion_id,
        "outcome": "modified",
        "applied": True,
        "new_revision": 1,
    }

    document_response = client.get(
        f"/v1/documents/{document_id}",
        headers=auth_headers,
    )
    assert document_response.status_code == 200
    assert (
        document_response.json()["current_content"]
        == "User-modified version of the suggestion"
    )
    assert document_response.json()["revision"] == 1


def test_viewer_cannot_start_ai_interaction_even_with_ai_flag(
    client, auth_headers
) -> None:
    document = create_document(client, auth_headers, initial_content="")
    viewer, viewer_token = client.post(
        "/v1/auth/register",
        json={
            "email": "viewer@example.com",
            "display_name": "Viewer",
            "password": "strong-password",
        },
    ).json(), client.post(
        "/v1/auth/login",
        json={"email": "viewer@example.com", "password": "strong-password"},
    ).json()["access_token"]
    owner_headers = auth_headers
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

    permission_response = client.post(
        f"/v1/documents/{document['document_id']}/permissions",
        headers=owner_headers,
        json={
            "grantee_type": "user",
            "user_id": f"usr_{viewer['user_id']}",
            "role": "viewer",
            "ai_allowed": True,
        },
    )
    assert permission_response.status_code == 201

    response = client.post(
        f"/v1/documents/{document['document_id']}/ai/interactions",
        headers=viewer_headers,
        json={
            **CREATE_AI_PAYLOAD,
            "selected_text_snapshot": "",
            "selection_range": {"start": 0, "end": 0},
        },
    )

    assert response.status_code == 403
    assert response.json() == {
        "error_code": "AI_ROLE_NOT_ALLOWED",
        "message": "Your role is not allowed to use AI features.",
        "retryable": False,
    }
