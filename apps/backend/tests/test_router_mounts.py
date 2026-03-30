"""OpenAPI checks for mounted session and AI routes."""

EXPECTED_PATHS = {
    "/v1/documents/{document_id}/sessions": {"post"},
    "/v1/documents/{document_id}/ai/interactions": {"get", "post"},
    "/v1/ai/interactions/{interaction_id}": {"get"},
    "/v1/ai/suggestions/{suggestion_id}/accept": {"post"},
    "/v1/ai/suggestions/{suggestion_id}/reject": {"post"},
    "/v1/ai/suggestions/{suggestion_id}/apply-edited": {"post"},
}


def test_only_documented_contract_paths_are_mounted(client) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]

    assert set(paths) == set(EXPECTED_PATHS)
    for path, methods in EXPECTED_PATHS.items():
        assert set(paths[path]) == methods
