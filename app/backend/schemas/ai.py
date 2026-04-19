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


class AIEntryKind(str, Enum):
    CHAT_MESSAGE = "chat_message"
    SUGGESTION = "suggestion"


class AIMessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class AIChatMode(str, Enum):
    CHAT = "chat"
    SUGGEST_EDIT = "suggest_edit"


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


class AIChatMessageStreamRequest(AppSchema):
    message: str = Field(min_length=1)
    mode: AIChatMode = AIChatMode.CHAT
    selected_range: Optional[TextRange] = Field(
        default=None,
        validation_alias=AliasChoices("selected_range", "selection_range"),
        serialization_alias="selected_range",
    )
    selected_text_snapshot: Optional[str] = None
    surrounding_context: Optional[str] = None
    base_revision: int = Field(ge=0)


class AIInteractionAcceptedResponse(AppSchema):
    interaction_id: str
    status: AIInteractionStatus
    document_id: int
    base_revision: int = Field(ge=0)
    created_at: datetime


class AIInteractionCancelResponse(AppSchema):
    interaction_id: str
    status: AIInteractionStatus
    canceled_at: datetime


class AIChatThreadClearResponse(AppSchema):
    document_id: int
    deleted_entry_count: int = Field(ge=0)
    cleared_at: datetime


class AIUsageResponse(AppSchema):
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    estimated_cost_usd: Optional[float] = Field(default=None, ge=0)


class AISuggestionPayload(AppSchema):
    suggestion_id: str
    generated_output: str
    model_name: str
    stale: bool
    usage: Optional[AIUsageResponse] = None


class AISelectionRangeResponse(AppSchema):
    start: int = Field(ge=0)
    end: int = Field(ge=0)


class AIInteractionDetailResponse(AppSchema):
    interaction_id: str
    conversation_id: str
    entry_kind: AIEntryKind
    message_role: AIMessageRole
    feature_type: str
    scope_type: str
    status: AIInteractionStatus
    document_id: int
    source_revision: int = Field(ge=0)
    base_revision: int = Field(ge=0)
    created_at: datetime
    completed_at: Optional[datetime] = None
    rendered_prompt: str
    selected_range: Optional[AISelectionRangeResponse] = None
    selected_text_snapshot: Optional[str] = None
    surrounding_context: Optional[str] = None
    user_instruction: Optional[str] = None
    reply_to_interaction_id: Optional[str] = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    outcome: Optional[SuggestionOutcome] = None
    outcome_recorded_at: Optional[datetime] = None
    suggestion: Optional[AISuggestionPayload] = None


class AIInteractionHistoryItem(AppSchema):
    interaction_id: str
    conversation_id: str
    entry_kind: AIEntryKind
    message_role: AIMessageRole
    feature_type: str
    scope_type: str
    user_id: int
    status: AIInteractionStatus
    created_at: datetime
    source_revision: int = Field(ge=0)
    model_name: Optional[str] = None
    outcome: Optional[SuggestionOutcome] = None
    total_tokens: Optional[int] = Field(default=None, ge=0)


class AIChatThreadEntryResponse(AppSchema):
    entry_id: str
    interaction_id: Optional[str] = None
    conversation_id: str
    entry_kind: AIEntryKind
    message_role: AIMessageRole
    feature_type: str
    scope_type: str
    status: AIInteractionStatus
    created_at: datetime
    source_revision: int = Field(ge=0)
    content: str
    selected_range: Optional[AISelectionRangeResponse] = None
    selected_text_snapshot: Optional[str] = None
    surrounding_context: Optional[str] = None
    reply_to_interaction_id: Optional[str] = None
    outcome: Optional[SuggestionOutcome] = None
    review_only: bool = False
    suggestion: Optional[AISuggestionPayload] = None


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
