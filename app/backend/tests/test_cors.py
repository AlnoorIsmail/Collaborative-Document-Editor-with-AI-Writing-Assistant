from app.backend.core.config import Settings


def test_cors_preflight_allows_vite_dev_server_origin(client) -> None:
    response = client.options(
        "/v1/auth/login",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.headers["access-control-allow-credentials"] == "true"
    assert "POST" in response.headers["access-control-allow-methods"]


def test_allowed_origins_supports_json_env(monkeypatch) -> None:
    monkeypatch.setenv(
        "AI_COLLAB_ALLOWED_ORIGINS",
        '["http://localhost:5173", "https://preview.example.com"]',
    )

    settings = Settings()

    assert settings.allowed_origins == [
        "http://localhost:5173",
        "https://preview.example.com",
    ]
