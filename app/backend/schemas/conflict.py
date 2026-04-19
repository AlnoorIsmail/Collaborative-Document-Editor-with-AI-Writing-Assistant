from datetime import datetime
from typing import Optional

from pydantic import Field, model_validator

from app.backend.schemas.common import AppSchema, TextRange


class ConflictCandidateCreateRequest(AppSchema):
    batch_id: str = Field(min_length=1, description="Client-side step batch identifier.")
    client_id: Optional[str] = Field(
        default=None,
        description="Optional client instance identifier for this candidate batch.",
    )
    user_id: Optional[int] = Field(
        default=None,
        ge=1,
        description="Numeric user identifier for the candidate author when known.",
    )
    user_display_name: Optional[str] = Field(
        default=None,
        description="Display name for the candidate author when known.",
    )
    range: TextRange = Field(..., description="Affected text range for the conflicting edit.")
    candidate_content_snapshot: str = Field(
        default="",
        description="Replacement content snapshot preserved for this candidate.",
    )
    exact_text_snapshot: str = Field(
        default="",
        description="Exact quoted text captured from the conflict region at detection time.",
    )
    prefix_context: str = Field(
        default="",
        description="Prefix context stored to help later re-anchor the conflict.",
    )
    suffix_context: str = Field(
        default="",
        description="Suffix context stored to help later re-anchor the conflict.",
    )


class DocumentConflictCreateRequest(AppSchema):
    conflict_key: Optional[str] = Field(
        default=None,
        description="Optional idempotency key used to collapse duplicate conflict reports.",
    )
    source_revision: int = Field(
        ge=0,
        description="Persisted document revision where the overlap was detected.",
    )
    source_collab_version: int = Field(
        ge=0,
        description="Realtime collaboration version where the overlap was detected.",
    )
    local_candidate: ConflictCandidateCreateRequest = Field(
        ..., description="Candidate preserved from the reporting client."
    )
    remote_candidate: ConflictCandidateCreateRequest = Field(
        ..., description="Candidate preserved from the conflicting remote collaborator."
    )


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
    candidate_id: Optional[int] = Field(
        default=None,
        ge=1,
        description="Candidate to accept as the final resolution when no manual text is provided.",
    )
    resolved_content: Optional[str] = Field(
        default=None,
        description="Manual or AI-assisted final content chosen to resolve the conflict.",
    )

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
