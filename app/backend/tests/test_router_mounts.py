"""OpenAPI checks for mounted merged routes."""

EXPECTED_PATHS = {
    "/v1/auth/register": {"post"},
    "/v1/auth/login": {"post"},
    "/v1/auth/refresh": {"post"},
    "/v1/auth/me": {"get"},
    "/v1/documents": {"get", "post"},
    "/v1/documents/{documentId}": {"delete", "get", "patch"},
    "/v1/documents/{documentId}/content": {"patch"},
    "/v1/documents/{documentId}/versions": {"get"},
    "/v1/documents/{documentId}/versions/{versionId}/restore": {"post"},
    "/v1/documents/{documentId}/permissions": {"post"},
    "/v1/documents/{documentId}/permissions/{permissionId}": {"delete"},
    "/v1/documents/{documentId}/invitations": {"post"},
    "/v1/documents/{documentId}/sharing": {"get"},
    "/v1/invitations/{invitationId}/accept": {"post"},
    "/v1/share-links": {"post"},
    "/v1/share-links/{linkId}": {"delete"},
    "/v1/share-links/{token}/redeem": {"post"},
    "/v1/documents/{documentId}/sessions": {"post"},
    "/v1/documents/{documentId}/ai/interactions": {"get", "post"},
    "/v1/documents/{documentId}/ai/interactions/stream": {"post"},
    "/v1/documents/{documentId}/ai/chat/thread": {"get"},
    "/v1/documents/{documentId}/ai/chat/messages/stream": {"post"},
    "/v1/ai/interactions/{interactionId}": {"get"},
    "/v1/ai/interactions/{interactionId}/cancel": {"post"},
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


def test_protected_routes_use_bearer_security_scheme(client) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    body = response.json()
    security_schemes = body["components"]["securitySchemes"]
    assert security_schemes["HTTPBearer"] == {
        "type": "http",
        "scheme": "bearer",
    }

    protected_operations = [
        body["paths"]["/v1/auth/me"]["get"],
        body["paths"]["/v1/documents"]["get"],
        body["paths"]["/v1/documents/{documentId}"]["get"],
        body["paths"]["/v1/share-links/{token}/redeem"]["post"],
    ]

    for operation in protected_operations:
        assert operation["security"] == [{"HTTPBearer": []}]
        assert "parameters" not in operation or all(
            parameter["name"].lower() != "authorization"
            for parameter in operation["parameters"]
        )
