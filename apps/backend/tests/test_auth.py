"""Authentication scaffold tests for protected routes."""

EXPECTED_UNAUTHORIZED = {
    "error_code": "UNAUTHORIZED",
    "message": "Missing or invalid bearer token.",
    "retryable": False,
}


def test_sessions_route_requires_bearer_token(client) -> None:
    response = client.post(
        "/v1/documents/doc_101/sessions",
        json={"last_known_revision": 22},
    )

    assert response.status_code == 401
    assert response.json() == EXPECTED_UNAUTHORIZED


def test_ai_route_requires_bearer_token(client) -> None:
    response = client.get("/v1/documents/doc_101/ai/interactions")

    assert response.status_code == 401
    assert response.json() == EXPECTED_UNAUTHORIZED
