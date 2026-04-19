from datetime import datetime
from typing import Optional

from pydantic import Field, model_validator

from app.backend.schemas.common import AppSchema, TextRange


class ConflictCandidateCreateRequest(AppSchema):
    batch_id: str = Field(min_length=1)
    client_id: Optional[str] = None
    user_id: Optional[int] = Field(default=None, ge=1)
    user_display_name: Optional[str] = None
    range: TextRange
    candidate_content_snapshot: str = ""
    exact_text_snapshot: str = ""
    prefix_context: str = ""
    suffix_context: str = ""


class DocumentConflictCreateRequest(AppSchema):
    conflict_key: Optional[str] = None
    source_revision: int = Field(ge=0)
    source_collab_version: int = Field(ge=0)
    local_candidate: ConflictCandidateCreateRequest
    remote_candidate: ConflictCandidateCreateRequest


class DocumentConflictCandidateResponse(AppSchema):
    candidate_id: int
    user_id: int
    user_display_name: str
    batch_id: str
    client_id: Optional[str] = None
    range: TextRange
    candidate_content_snapshot: str
    exact_text_snapshot: str
    prefix_context: str
    suffix_context: str
    created_at: datetime


class DocumentConflictResponse(AppSchema):
    conflict_id: int
    conflict_key: Optional[str] = None
    status: str
    stale: bool = False
    source_revision: int = Field(ge=0)
    source_collab_version: int = Field(ge=0)
    anchor_range: Optional[TextRange] = None
    exact_text_snapshot: str
    prefix_context: str
    suffix_context: str
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    resolved_content: Optional[str] = None
    candidates: list[DocumentConflictCandidateResponse] = Field(default_factory=list)


class DocumentConflictResolveRequest(AppSchema):
    candidate_id: Optional[int] = Field(default=None, ge=1)
    resolved_content: Optional[str] = None

    @model_validator(mode="after")
    def validate_resolution_source(self) -> "DocumentConflictResolveRequest":
        if self.candidate_id is None and not (self.resolved_content or "").strip():
            raise ValueError("candidate_id or resolved_content is required")
        return self


class DocumentConflictResolveResponse(AppSchema):
    conflict_id: int
    status: str
    resolved_content: str
    new_revision: int = Field(ge=0)
    latest_version_id: Optional[int] = None
    collab_version: int = Field(ge=0)
    resolved_at: datetime
