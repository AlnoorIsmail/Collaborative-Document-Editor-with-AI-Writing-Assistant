"""Shared FastAPI dependencies for services and auth."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.backend.core.config import Settings, get_settings
from app.backend.core.database import get_db
from app.backend.core.security import (
    AuthenticatedPrincipal,
    bearer_scheme,
    build_authenticated_principal,
)
from app.backend.integrations.ai_provider import (
    AIProviderClient,
    OpenAICompatibleAIProviderClient,
    StubAIProviderClient,
)
from app.backend.models.user import User
from app.backend.repositories.ai import AIRepository, StubAIRepository
from app.backend.repositories.document_repository import DocumentRepository
from app.backend.repositories.permission_repository import PermissionRepository
from app.backend.repositories.refresh_token_repository import RefreshTokenRepository
from app.backend.repositories.sessions import InMemorySessionRepository, SessionRepository
from app.backend.repositories.user_repository import UserRepository
from app.backend.repositories.version_repository import VersionRepository
from app.backend.services.ai.ai_service import AIService
from app.backend.services.auth_service import AuthService
from app.backend.services.document_service import DocumentService
from app.backend.services.realtime.collaboration_service import (
    CollaborationService,
    RealtimeHub,
)
from app.backend.services.realtime.session_service import SessionService


def get_auth_service(db: Annotated[Session, Depends(get_db)]) -> AuthService:
    return AuthService(
        UserRepository(db),
        RefreshTokenRepository(db),
    )


def get_bearer_token(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
) -> str:
    if credentials is None or not credentials.credentials.strip():
        from app.backend.core.errors import ApiError

        raise ApiError(
            status_code=401,
            error_code="UNAUTHORIZED",
            message="Missing or invalid bearer token.",
        )

    return credentials.credentials.strip()


def get_current_authenticated_user(
    token: Annotated[str, Depends(get_bearer_token)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> User:
    return auth_service.get_current_user(token)


def get_current_principal(
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    token: Annotated[str, Depends(get_bearer_token)],
) -> AuthenticatedPrincipal:
    return build_authenticated_principal(
        user_id=current_user.id,
        token=token,
    )


def get_optional_authenticated_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> User | None:
    if credentials is None:
        return None

    token = credentials.credentials.strip()
    if not token:
        from app.backend.core.errors import ApiError

        raise ApiError(
            status_code=401,
            error_code="UNAUTHORIZED",
            message="Missing or invalid bearer token.",
        )

    return auth_service.get_current_user(token)


@lru_cache
def get_session_repository() -> SessionRepository:
    return InMemorySessionRepository()


@lru_cache
def get_ai_repository() -> AIRepository:
    return StubAIRepository()


@lru_cache
def get_ai_provider() -> AIProviderClient:
    settings = get_settings()
    if settings.ai_api_key.strip() and settings.ai_api_url.strip():
        return OpenAICompatibleAIProviderClient(
            api_key=settings.ai_api_key,
            api_url=settings.ai_api_url,
            model_name=settings.ai_model,
            timeout_seconds=settings.ai_request_timeout_seconds,
            prompt_token_cost_per_1k=settings.ai_prompt_token_cost_per_1k,
            completion_token_cost_per_1k=settings.ai_completion_token_cost_per_1k,
        )
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


@lru_cache
def get_realtime_hub() -> RealtimeHub:
    return RealtimeHub()


def get_collaboration_service(
    session_repository: Annotated[SessionRepository, Depends(get_session_repository)],
    hub: Annotated[RealtimeHub, Depends(get_realtime_hub)],
    db: Annotated[Session, Depends(get_db)],
) -> CollaborationService:
    return CollaborationService(
        session_repository=session_repository,
        hub=hub,
        document_service=DocumentService(
            DocumentRepository(db),
            VersionRepository(db),
            PermissionRepository(db),
        ),
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
