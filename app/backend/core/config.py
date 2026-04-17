"""Centralized application settings."""

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded through environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="AI_COLLAB_",
        env_file=".env",
        extra="ignore",
    )

    app_name: str = "Collaborative Document Editor with AI Writing Assistant Backend"
    api_v1_prefix: str = "/v1"
    environment: str = "development"
    debug: bool = True
    database_url: str = Field(
        default="sqlite:///./collab_editor.db",
        validation_alias=AliasChoices("DATABASE_URL", "AI_COLLAB_DATABASE_URL"),
    )
    realtime_url: str = "wss://api.example.com/realtime"
    secret_key: str = Field(
        default="change-me",
        validation_alias=AliasChoices("SECRET_KEY", "AI_COLLAB_SECRET_KEY"),
    )
    access_token_expire_minutes: int = Field(
        default=15,
        validation_alias=AliasChoices(
            "ACCESS_TOKEN_EXPIRE_MINUTES",
            "AI_COLLAB_ACCESS_TOKEN_EXPIRE_MINUTES",
        ),
    )
    refresh_token_expire_days: int = Field(
        default=7,
        validation_alias=AliasChoices(
            "REFRESH_TOKEN_EXPIRE_DAYS",
            "AI_COLLAB_REFRESH_TOKEN_EXPIRE_DAYS",
        ),
    )
    algorithm: str = Field(
        default="HS256",
        validation_alias=AliasChoices(
            "JWT_ALGORITHM",
            "AI_COLLAB_JWT_ALGORITHM",
            "AI_COLLAB_ALGORITHM",
        ),
    )
    ai_api_key: str = ""
    ai_api_url: str = ""
    ai_model: str = "gpt-4o-mini"
    ai_request_timeout_seconds: float = 30.0
    ai_prompt_token_cost_per_1k: float = 0.0
    ai_completion_token_cost_per_1k: float = 0.0
    allowed_origins: list[str] = Field(
        validation_alias=AliasChoices("ALLOWED_ORIGINS", "AI_COLLAB_ALLOWED_ORIGINS"),
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
