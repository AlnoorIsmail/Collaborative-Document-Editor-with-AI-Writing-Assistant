"""Internal record types for realtime session scaffolding."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class RealtimeCollaboratorRecord:
    user_id: int
    session_id: str
    last_known_revision: int
    joined_at: datetime
    last_seen_at: datetime


@dataclass(frozen=True)
class RealtimeSessionRecord:
    session_id: str
    session_token: str
    document_id: int
    joined_at: datetime
    active_collaborators: tuple[RealtimeCollaboratorRecord, ...] = field(
        default_factory=tuple
    )
