"""Repository seams for realtime session bootstrapping."""

from abc import ABC, abstractmethod

from apps.backend.models.realtime import RealtimeSessionRecord


class SessionRepository(ABC):
    @abstractmethod
    def create_or_join_session(
        self,
        *,
        document_id: str,
        user_id: str,
        last_known_revision: int,
    ) -> RealtimeSessionRecord:
        """Create or resume a realtime session for a document."""


class StubSessionRepository(SessionRepository):
    def create_or_join_session(
        self,
        *,
        document_id: str,
        user_id: str,
        last_known_revision: int,
    ) -> RealtimeSessionRecord:
        # TODO: Persist session membership and enforce document access server-side.
        return RealtimeSessionRecord(
            session_id="sess_1",
            session_token="realtime-jwt",
            document_id=document_id,
            revision=last_known_revision,
        )
