"""Shared FastAPI dependencies for services and auth."""

from functools import lru_cache
from typing import Annotated, Optional

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials

from apps.backend.core.config import Settings, get_settings
from apps.backend.core.security import (
    AuthenticatedPrincipal,
    bearer_scheme,
    get_principal_from_credentials,
)
from apps.backend.integrations.ai_provider import AIProviderClient, StubAIProviderClient
from apps.backend.repositories.ai import AIRepository, StubAIRepository
from apps.backend.repositories.sessions import SessionRepository, StubSessionRepository
from apps.backend.services.ai.ai_service import AIService
from apps.backend.services.realtime.session_service import SessionService


def get_current_principal(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)],
) -> AuthenticatedPrincipal:
    return get_principal_from_credentials(credentials)


@lru_cache
def get_session_repository() -> SessionRepository:
    return StubSessionRepository()


@lru_cache
def get_ai_repository() -> AIRepository:
    return StubAIRepository()


@lru_cache
def get_ai_provider() -> AIProviderClient:
    return StubAIProviderClient()


def get_session_service(
    repository: Annotated[SessionRepository, Depends(get_session_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SessionService:
    return SessionService(repository=repository, settings=settings)


def get_ai_service(
    repository: Annotated[AIRepository, Depends(get_ai_repository)],
    provider: Annotated[AIProviderClient, Depends(get_ai_provider)],
) -> AIService:
    return AIService(repository=repository, provider=provider)
