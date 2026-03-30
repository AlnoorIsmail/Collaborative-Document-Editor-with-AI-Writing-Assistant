"""Pydantic schemas for suggestion-based AI workflows."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import Field

from apps.backend.schemas.common import AppSchema, TextRange


class AIInteractionStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class SuggestionOutcome(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    MODIFIED = "modified"


class AIInteractionCreateRequest(AppSchema):
    feature_type: str = Field(min_length=1)
    scope_type: str = Field(min_length=1)
    selection_range: TextRange | None = None
    selected_text_snapshot: str | None = None
    surrounding_context: str | None = None
    user_prompt: str | None = None
    base_revision: int = Field(ge=0)
    options: dict[str, Any] = Field(default_factory=dict)


class AIInteractionAcceptedResponse(AppSchema):
    interaction_id: str
    status: AIInteractionStatus
    document_id: str
    base_revision: int = Field(ge=0)
    created_at: datetime


class AISuggestionPayload(AppSchema):
    suggestion_id: str
    generated_output: str
    model_name: str
    stale: bool


class AIInteractionDetailResponse(AppSchema):
    interaction_id: str
    status: AIInteractionStatus
    document_id: str
    base_revision: int = Field(ge=0)
    suggestion: AISuggestionPayload | None = None


class AIInteractionHistoryItem(AppSchema):
    interaction_id: str
    feature_type: str
    user_id: str
    status: AIInteractionStatus
    created_at: datetime


class AcceptSuggestionRequest(AppSchema):
    apply_to_range: TextRange


class AcceptSuggestionResponse(AppSchema):
    suggestion_id: str
    outcome: SuggestionOutcome
    applied: bool
    new_revision: int = Field(ge=0)


class RejectSuggestionResponse(AppSchema):
    suggestion_id: str
    outcome: SuggestionOutcome


class ApplyEditedSuggestionRequest(AppSchema):
    edited_output: str = Field(min_length=1)
    apply_to_range: TextRange


class ApplyEditedSuggestionResponse(AppSchema):
    suggestion_id: str
    outcome: SuggestionOutcome
    applied: bool
    new_revision: int = Field(ge=0)
