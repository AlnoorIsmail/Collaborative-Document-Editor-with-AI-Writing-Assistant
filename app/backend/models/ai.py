"""Internal record types for AI interaction scaffolding."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class AISuggestionRecord:
    suggestion_id: str
    generated_output: str
    model_name: str
    stale: bool


@dataclass(frozen=True)
class AIInteractionRecord:
    interaction_id: str
    document_id: str
    user_id: str
    feature_type: str
    scope_type: str
    status: str
    base_revision: int
    created_at: datetime
    suggestion: Optional[AISuggestionRecord] = None


@dataclass(frozen=True)
class AIInteractionHistoryRecord:
    interaction_id: str
    feature_type: str
    user_id: str
    status: str
    created_at: datetime


@dataclass(frozen=True)
class SuggestionOutcomeRecord:
    suggestion_id: str
    outcome: str
    applied: bool = False
    new_revision: Optional[int] = None
