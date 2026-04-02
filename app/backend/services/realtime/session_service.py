"""Service layer for realtime session bootstrap endpoints."""

from http import HTTPStatus

from app.backend.core.config import Settings
from app.backend.core.contracts import parse_resource_id
from app.backend.core.errors import ApiError, AppError
from app.backend.core.security import AuthenticatedPrincipal
from app.backend.repositories.document_repository import DocumentRepository
from app.backend.repositories.permission_repository import PermissionRepository
from app.backend.repositories.sessions import SessionRepository
from app.backend.schemas.common import ErrorCode
from app.backend.schemas.realtime import (
    SessionBootstrapRequest,
    SessionBootstrapResponse,
)
from app.backend.services.access_service import DocumentAccessService


class SessionService:
    def __init__(
        self,
        *,
        repository: SessionRepository,
        settings: Settings,
        document_repository: DocumentRepository,
        permission_repository: PermissionRepository,
    ) -> None:
        self._repository = repository
        self._settings = settings
        self._access_service = DocumentAccessService(
            document_repository,
            permission_repository,
        )

    def create_or_join_session(
        self,
        *,
        document_id: str,
        principal: AuthenticatedPrincipal,
        payload: SessionBootstrapRequest,
    ) -> SessionBootstrapResponse:
        user_id = self._principal_user_id(principal)
        access = self._access_service.require_read_access(
            document_id=document_id,
            user_id=user_id,
        )
        record = self._repository.create_or_join_session(
            document_id=access.document.id,
            user_id=user_id,
            last_known_revision=payload.last_known_revision,
        )
        return SessionBootstrapResponse(
            session_id=record.session_id,
            session_token=record.session_token,
            document_id=record.document_id,
            revision=access.current_revision,
            realtime_url=self._settings.realtime_url,
        )

    def _principal_user_id(self, principal: AuthenticatedPrincipal) -> int:
        try:
            return parse_resource_id(principal.user_id, "usr")
        except ApiError as exc:
            raise AppError(
                status_code=HTTPStatus.UNAUTHORIZED,
                error_code=ErrorCode.UNAUTHORIZED,
                message="Missing or invalid bearer token.",
            ) from exc
