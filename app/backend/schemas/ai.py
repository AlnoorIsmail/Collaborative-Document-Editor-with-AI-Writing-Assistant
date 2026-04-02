"""Pydantic schemas for suggestion-based AI workflows."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import AliasChoices, Field

from app.backend.schemas.common import AppSchema, TextRange


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
    selected_range: Optional[TextRange] = Field(
        default=None,
        validation_alias=AliasChoices("selected_range", "selection_range"),
        serialization_alias="selected_range",
    )
    selected_text_snapshot: Optional[str] = None
    surrounding_context: Optional[str] = None
    user_instruction: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("user_instruction", "user_prompt"),
        serialization_alias="user_instruction",
    )
    base_revision: int = Field(ge=0)
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("parameters", "options"),
        serialization_alias="parameters",
    )


class AIInteractionAcceptedResponse(AppSchema):
    interaction_id: str
    status: AIInteractionStatus
    document_id: int
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
    document_id: int
    base_revision: int = Field(ge=0)
    suggestion: Optional[AISuggestionPayload] = None


class AIInteractionHistoryItem(AppSchema):
    interaction_id: str
    feature_type: str
    user_id: int
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
