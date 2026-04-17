"""Internal record types for AI interaction scaffolding."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional


@dataclass(frozen=True)
class AIUsageRecord:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float | None = None


@dataclass(frozen=True)
class AISuggestionRecord:
    suggestion_id: str
    generated_output: str
    model_name: str
    stale: bool
    usage: Optional[AIUsageRecord] = None


@dataclass(frozen=True)
class AIInteractionRecord:
    interaction_id: str
    document_id: int
    user_id: int
    feature_type: str
    scope_type: str
    status: str
    base_revision: int
    created_at: datetime
    completed_at: Optional[datetime] = None
    rendered_prompt: str = ""
    selected_range_start: Optional[int] = None
    selected_range_end: Optional[int] = None
    selected_text_snapshot: Optional[str] = None
    surrounding_context: Optional[str] = None
    user_instruction: Optional[str] = None
    parameters: dict[str, Any] | None = None
    outcome: Optional[str] = None
    outcome_recorded_at: Optional[datetime] = None
    apply_range_start: Optional[int] = None
    apply_range_end: Optional[int] = None
    edited_output: Optional[str] = None
    suggestion: Optional[AISuggestionRecord] = None


@dataclass(frozen=True)
class AIInteractionHistoryRecord:
    interaction_id: str
    feature_type: str
    scope_type: str
    user_id: int
    status: str
    created_at: datetime
    model_name: Optional[str] = None
    outcome: Optional[str] = None
    total_tokens: Optional[int] = None


@dataclass(frozen=True)
class SuggestionOutcomeRecord:
    suggestion_id: str
    outcome: str
    applied: bool = False
    new_revision: Optional[int] = None
