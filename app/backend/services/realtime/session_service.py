"""Service layer for realtime session bootstrap endpoints."""

from app.backend.core.config import Settings
from app.backend.core.security import AuthenticatedPrincipal
from app.backend.repositories.sessions import SessionRepository
from app.backend.schemas.realtime import (
    SessionBootstrapRequest,
    SessionBootstrapResponse,
)


class SessionService:
    def __init__(self, *, repository: SessionRepository, settings: Settings) -> None:
        self._repository = repository
        self._settings = settings

    def create_or_join_session(
        self,
        *,
        document_id: str,
        principal: AuthenticatedPrincipal,
        payload: SessionBootstrapRequest,
    ) -> SessionBootstrapResponse:
        record = self._repository.create_or_join_session(
            document_id=document_id,
            user_id=principal.user_id,
            last_known_revision=payload.last_known_revision,
        )
        return SessionBootstrapResponse(
            session_id=record.session_id,
            session_token=record.session_token,
            document_id=record.document_id,
            revision=record.revision,
            realtime_url=self._settings.realtime_url,
        )
