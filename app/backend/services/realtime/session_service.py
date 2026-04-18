"""Service layer for realtime session bootstrap endpoints."""

from app.backend.core.config import Settings
from app.backend.repositories.document_repository import DocumentRepository
from app.backend.repositories.permission_repository import PermissionRepository
from app.backend.repositories.sessions import SessionRepository
from app.backend.schemas.realtime import (
    SessionBootstrapRequest,
    SessionBootstrapResponse,
    SessionCollaboratorResponse,
)
from app.backend.models.user import User
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
        current_user: User,
        payload: SessionBootstrapRequest,
    ) -> SessionBootstrapResponse:
        access = self._access_service.require_read_access(
            document_id=document_id,
            user_id=current_user.id,
        )
        record = self._repository.create_or_join_session(
            document_id=access.document.id,
            user_id=current_user.id,
            display_name=current_user.display_name,
            last_known_revision=payload.last_known_revision,
        )
        missed_revision_count = max(access.current_revision - payload.last_known_revision, 0)
        return SessionBootstrapResponse(
            session_id=record.session_id,
            session_token=record.session_token,
            document_id=record.document_id,
            revision=access.current_revision,
            realtime_url=self._settings.realtime_url,
            resync_required=missed_revision_count > 0,
            missed_revision_count=missed_revision_count,
            active_collaborators=[
                SessionCollaboratorResponse(
                    user_id=collaborator.user_id,
                    display_name=collaborator.display_name,
                    session_id=collaborator.session_id,
                    last_known_revision=collaborator.last_known_revision,
                    joined_at=collaborator.joined_at,
                    last_seen_at=collaborator.last_seen_at,
                )
                for collaborator in record.active_collaborators
            ],
        )
