"""Repository seams for realtime session bootstrapping."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
import secrets
from threading import Lock

from app.backend.core.contracts import utc_now
from app.backend.models.realtime import (
    RealtimeCollaboratorRecord,
    RealtimeSessionRecord,
)

SESSION_TTL = timedelta(minutes=15)


class SessionRepository(ABC):
    @abstractmethod
    def create_or_join_session(
        self,
        *,
        document_id: int,
        user_id: int,
        display_name: str,
        last_known_revision: int,
    ) -> RealtimeSessionRecord:
        """Create or resume a realtime session for a document."""

    @abstractmethod
    def validate_session(
        self,
        *,
        document_id: int,
        user_id: int,
        session_id: str,
        session_token: str,
    ) -> RealtimeSessionRecord | None:
        """Return the stored session when the token still matches."""

    @abstractmethod
    def mark_session_seen(
        self,
        *,
        session_id: str,
        last_known_revision: int | None = None,
    ) -> RealtimeSessionRecord | None:
        """Refresh a session heartbeat and optionally its known revision."""


@dataclass
class _StoredSession:
    session_id: str
    session_token: str
    document_id: int
    user_id: int
    display_name: str
    last_known_revision: int
    joined_at: datetime
    last_seen_at: datetime


class InMemorySessionRepository(SessionRepository):
    def __init__(self) -> None:
        self._sessions_by_document_user: dict[tuple[int, int], _StoredSession] = {}
        self._sessions_by_id: dict[str, _StoredSession] = {}
        self._lock = Lock()
        self._session_sequence = 0

    def create_or_join_session(
        self,
        *,
        document_id: int,
        user_id: int,
        display_name: str,
        last_known_revision: int,
    ) -> RealtimeSessionRecord:
        now = utc_now()
        key = (document_id, user_id)
        with self._lock:
            self._prune_expired(now)
            existing = self._sessions_by_document_user.get(key)
            if existing is None:
                existing = _StoredSession(
                    session_id=self._session_id(),
                    session_token=self._session_token(),
                    document_id=document_id,
                    user_id=user_id,
                    display_name=display_name,
                    last_known_revision=last_known_revision,
                    joined_at=now,
                    last_seen_at=now,
                )
            else:
                existing.display_name = display_name
                existing.last_known_revision = last_known_revision
                existing.last_seen_at = now

            self._sessions_by_document_user[key] = existing
            self._sessions_by_id[existing.session_id] = existing
            return self._build_session_record(existing)

    def validate_session(
        self,
        *,
        document_id: int,
        user_id: int,
        session_id: str,
        session_token: str,
    ) -> RealtimeSessionRecord | None:
        now = utc_now()
        with self._lock:
            self._prune_expired(now)
            session = self._sessions_by_id.get(session_id)
            if session is None:
                return None
            if (
                session.document_id != document_id
                or session.user_id != user_id
                or session.session_token != session_token
            ):
                return None
            session.last_seen_at = now
            return self._build_session_record(session)

    def mark_session_seen(
        self,
        *,
        session_id: str,
        last_known_revision: int | None = None,
    ) -> RealtimeSessionRecord | None:
        now = utc_now()
        with self._lock:
            self._prune_expired(now)
            session = self._sessions_by_id.get(session_id)
            if session is None:
                return None
            session.last_seen_at = now
            if last_known_revision is not None:
                session.last_known_revision = last_known_revision
            return self._build_session_record(session)

    def _prune_expired(self, now: datetime) -> None:
        expired_keys = [
            key
            for key, session in self._sessions_by_document_user.items()
            if now - session.last_seen_at > SESSION_TTL
        ]
        for key in expired_keys:
            session = self._sessions_by_document_user.pop(key)
            self._sessions_by_id.pop(session.session_id, None)

    def _session_id(self) -> str:
        self._session_sequence += 1
        return f"sess_{self._session_sequence}"

    def _session_token(self) -> str:
        return secrets.token_urlsafe(24)

    def _build_session_record(self, session: _StoredSession) -> RealtimeSessionRecord:
        collaborators = tuple(
            RealtimeCollaboratorRecord(
                user_id=candidate.user_id,
                display_name=candidate.display_name,
                session_id=candidate.session_id,
                last_known_revision=candidate.last_known_revision,
                joined_at=candidate.joined_at,
                last_seen_at=candidate.last_seen_at,
            )
            for candidate in sorted(
                (
                    candidate
                    for candidate in self._sessions_by_document_user.values()
                    if candidate.document_id == session.document_id
                ),
                key=lambda candidate: (candidate.joined_at, candidate.user_id),
            )
        )
        return RealtimeSessionRecord(
            session_id=session.session_id,
            session_token=session.session_token,
            document_id=session.document_id,
            user_id=session.user_id,
            display_name=session.display_name,
            joined_at=session.joined_at,
            last_known_revision=session.last_known_revision,
            last_seen_at=session.last_seen_at,
            active_collaborators=collaborators,
        )
