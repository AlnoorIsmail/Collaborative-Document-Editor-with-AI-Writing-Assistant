"""Pydantic schemas for realtime session bootstrap contracts."""

from pydantic import Field

from apps.backend.schemas.common import AppSchema


class SessionBootstrapRequest(AppSchema):
    last_known_revision: int = Field(ge=0)


class SessionBootstrapResponse(AppSchema):
    session_id: str
    session_token: str
    document_id: str
    revision: int = Field(ge=0)
    realtime_url: str
