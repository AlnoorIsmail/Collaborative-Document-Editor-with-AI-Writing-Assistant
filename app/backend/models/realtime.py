"""Internal record types for realtime session scaffolding."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class RealtimeCollaboratorRecord:
    user_id: int
    display_name: str
    session_id: str
    last_known_revision: int
    joined_at: datetime
    last_seen_at: datetime


@dataclass(frozen=True)
class RealtimeSessionRecord:
    session_id: str
    session_token: str
    document_id: int
    user_id: int
    display_name: str
    joined_at: datetime
    last_known_revision: int
    last_seen_at: datetime
    active_collaborators: tuple[RealtimeCollaboratorRecord, ...] = field(
        default_factory=tuple
    )
