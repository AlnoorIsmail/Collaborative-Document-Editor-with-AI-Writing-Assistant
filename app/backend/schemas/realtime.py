"""Pydantic schemas for realtime session bootstrap contracts."""

from datetime import datetime

from pydantic import Field

from app.backend.schemas.common import AppSchema


class SessionBootstrapRequest(AppSchema):
    last_known_revision: int = Field(ge=0)


class SessionCollaboratorResponse(AppSchema):
    user_id: int
    display_name: str
    session_id: str
    last_known_revision: int = Field(ge=0)
    joined_at: datetime
    last_seen_at: datetime


class SessionBootstrapResponse(AppSchema):
    session_id: str
    session_token: str
    document_id: int
    revision: int = Field(ge=0)
    realtime_url: str
    resync_required: bool = False
    missed_revision_count: int = Field(default=0, ge=0)
    active_collaborators: list[SessionCollaboratorResponse] = Field(
        default_factory=list
    )
