"""Internal record types for realtime session scaffolding."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RealtimeSessionRecord:
    session_id: str
    session_token: str
    document_id: str
    revision: int
