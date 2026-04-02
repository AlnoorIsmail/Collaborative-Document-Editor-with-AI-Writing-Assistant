"""Centralized application settings."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded through environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="AI_COLLAB_",
        env_file=".env",
        extra="ignore",
    )

    app_name: str = "AI Collaborative Document Editor Backend"
    api_v1_prefix: str = "/v1"
    environment: str = "development"
    debug: bool = True
    database_url: str = "sqlite:///./collab_editor.db"
    realtime_url: str = "wss://api.example.com/realtime"
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 60
    algorithm: str = "HS256"
    ai_api_key: str = ""
    ai_api_url: str = ""
    ai_model: str = "gpt-4o-mini"
    ai_request_timeout_seconds: float = 30.0
    allowed_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ]
    )

    @property
    def jwt_secret(self) -> str:
        return self.secret_key

    @property
    def jwt_algorithm(self) -> str:
        return self.algorithm


@lru_cache
def get_settings() -> Settings:
    """Cache settings so dependencies share a single config snapshot."""

    return Settings()


settings = get_settings()
