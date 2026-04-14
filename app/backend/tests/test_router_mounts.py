"""OpenAPI checks for mounted merged routes."""

EXPECTED_PATHS = {
    "/v1/auth/register": {"post"},
    "/v1/auth/login": {"post"},
    "/v1/auth/refresh": {"post"},
    "/v1/auth/me": {"get"},
    "/v1/documents": {"get", "post"},
    "/v1/documents/{document_id}": {"delete", "get", "patch"},
    "/v1/documents/{document_id}/content": {"patch"},
    "/v1/documents/{document_id}/versions": {"get"},
    "/v1/documents/{document_id}/versions/{version_id}/restore": {"post"},
    "/v1/documents/{documentId}/permissions": {"post"},
    "/v1/documents/{documentId}/permissions/{permissionId}": {"delete"},
    "/v1/documents/{documentId}/invitations": {"post"},
    "/v1/invitations/{invitationId}/accept": {"post"},
    "/v1/share-links": {"post"},
    "/v1/share-links/{token}/redeem": {"post"},
    "/v1/documents/{documentId}/sessions": {"post"},
    "/v1/documents/{documentId}/ai/interactions": {"get", "post"},
    "/v1/ai/interactions/{interactionId}": {"get"},
    "/v1/ai/suggestions/{suggestionId}/accept": {"post"},
    "/v1/ai/suggestions/{suggestionId}/reject": {"post"},
    "/v1/ai/suggestions/{suggestionId}/apply-edited": {"post"},
    "/health": {"get"},
}


def test_expected_contract_paths_are_mounted(client) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]

    for path, methods in EXPECTED_PATHS.items():
        assert path in paths
        assert set(paths[path]) == methods
