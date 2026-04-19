"""Pydantic schemas for realtime session bootstrap contracts."""

from datetime import datetime

from pydantic import Field

from app.backend.schemas.common import AppSchema


class SessionBootstrapRequest(AppSchema):
    last_known_revision: int = Field(
        ge=0,
        description="Most recent document revision currently known by the client.",
    )


class SessionCollaboratorResponse(AppSchema):
    user_id: int = Field(..., description="Numeric collaborator user identifier.")
    display_name: str = Field(..., description="Display name for the collaborator.")
    session_id: str = Field(..., description="Ephemeral realtime session identifier.")
    last_known_revision: int = Field(
        ge=0,
        description="Latest persisted document revision reported by that collaborator.",
    )
    joined_at: datetime = Field(..., description="UTC time when the collaborator joined.")
    last_seen_at: datetime = Field(
        ..., description="UTC time when the collaborator was last active."
    )


class SessionBootstrapResponse(AppSchema):
    session_id: str = Field(..., description="Ephemeral realtime session identifier.")
    session_token: str = Field(
        ..., description="Signed short-lived token used to authenticate the websocket."
    )
    document_id: int = Field(..., description="Numeric document identifier.")
    revision: int = Field(ge=0, description="Current persisted document revision.")
    collab_version: int = Field(
        default=0,
        ge=0,
        description="Current in-memory collaboration step version.",
    )
    content_snapshot: str = Field(
        default="",
        description="Current shared content snapshot for realtime bootstrap.",
    )
    line_spacing_snapshot: float = Field(
        default=1.15,
        ge=1.0,
        le=3.0,
        description="Current shared line-spacing value for realtime bootstrap.",
    )
    realtime_url: str = Field(
        ..., description="Relative websocket URL that the frontend should open next."
    )
    resync_required: bool = Field(
        default=False,
        description="Whether the client missed revisions and should expect resync behavior.",
    )
    missed_revision_count: int = Field(
        default=0,
        ge=0,
        description="How many persisted revisions the client is behind at bootstrap time.",
    )
    active_collaborators: list[SessionCollaboratorResponse] = Field(
        default_factory=list,
        description="Currently connected collaborators visible in the live presence snapshot.",
    )
