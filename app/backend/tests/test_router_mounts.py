"""OpenAPI checks for mounted merged routes."""

EXPECTED_PATHS = {
    "/v1/auth/register": {"post"},
    "/v1/auth/login": {"post"},
    "/v1/auth/me": {"get"},
    "/v1/documents": {"post"},
    "/v1/documents/{documentId}": {"get", "patch"},
    "/v1/documents/{documentId}/content": {"patch"},
    "/v1/documents/{documentId}/versions": {"get"},
    "/v1/documents/{documentId}/versions/{versionId}/restore": {"post"},
    "/v1/documents/{documentId}/permissions": {"post"},
    "/v1/documents/{documentId}/permissions/{permissionId}": {"delete"},
    "/v1/documents/{documentId}/invitations": {"post"},
    "/v1/invitations/{invitationId}/accept": {"post"},
    "/v1/share-links": {"post"},
    "/v1/share-links/{token}/redeem": {"post"},
    "/v1/documents/{document_id}/sessions": {"post"},
    "/v1/documents/{document_id}/ai/interactions": {"get", "post"},
    "/v1/ai/interactions/{interaction_id}": {"get"},
    "/v1/ai/suggestions/{suggestion_id}/accept": {"post"},
    "/v1/ai/suggestions/{suggestion_id}/reject": {"post"},
    "/v1/ai/suggestions/{suggestion_id}/apply-edited": {"post"},
    "/health": {"get"},
}


def test_expected_contract_paths_are_mounted(client) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]

    for path, methods in EXPECTED_PATHS.items():
        assert path in paths
        assert set(paths[path]) == methods
