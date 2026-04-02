"""Shared FastAPI dependencies for services and auth."""

from functools import lru_cache
from typing import Annotated, Optional

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.backend.core.database import get_db
from app.backend.core.config import Settings, get_settings
from app.backend.core.security import (
    AuthenticatedPrincipal,
    bearer_scheme,
    get_principal_from_credentials,
)
from app.backend.integrations.ai_provider import AIProviderClient, StubAIProviderClient
from app.backend.repositories.ai import AIRepository, StubAIRepository
from app.backend.repositories.document_repository import DocumentRepository
from app.backend.repositories.permission_repository import PermissionRepository
from app.backend.repositories.sessions import SessionRepository, StubSessionRepository
from app.backend.repositories.version_repository import VersionRepository
from app.backend.services.ai.ai_service import AIService
from app.backend.services.realtime.session_service import SessionService


def get_current_principal(
    credentials: Annotated[
        Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)
    ],
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
    db: Annotated[Session, Depends(get_db)],
) -> SessionService:
    return SessionService(
        repository=repository,
        settings=settings,
        document_repository=DocumentRepository(db),
        permission_repository=PermissionRepository(db),
    )


def get_ai_service(
    repository: Annotated[AIRepository, Depends(get_ai_repository)],
    provider: Annotated[AIProviderClient, Depends(get_ai_provider)],
    db: Annotated[Session, Depends(get_db)],
) -> AIService:
    return AIService(
        repository=repository,
        provider=provider,
        document_repository=DocumentRepository(db),
        permission_repository=PermissionRepository(db),
        version_repository=VersionRepository(db),
    )
