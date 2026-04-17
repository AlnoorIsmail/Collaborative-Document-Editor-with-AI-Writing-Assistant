"""Repository seams for AI interaction and suggestion scaffolding."""

from abc import ABC, abstractmethod
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from typing import Any

from app.backend.core.contracts import utc_now
from app.backend.core.errors import AppError
from app.backend.models.ai import (
    AIInteractionHistoryRecord,
    AIInteractionRecord,
    AISuggestionRecord,
    AIUsageRecord,
    SuggestionOutcomeRecord,
)
from app.backend.schemas.common import ErrorCode

STUB_CREATED_AT = datetime(2026, 3, 25, 10, 40, tzinfo=timezone.utc)


class AIRepository(ABC):
    @abstractmethod
    def create_interaction(
        self,
        *,
        document_id: int,
        user_id: int,
        feature_type: str,
        scope_type: str,
        base_revision: int,
        rendered_prompt: str,
        selected_range_start: int | None,
        selected_range_end: int | None,
        selected_text_snapshot: str | None,
        surrounding_context: str | None,
        user_instruction: str | None,
        parameters: dict[str, Any],
        generated_output: str,
        model_name: str,
        usage: AIUsageRecord | None,
    ) -> AIInteractionRecord:
        """Create an AI interaction record."""

    @abstractmethod
    def list_interactions(
        self, *, document_id: int, user_id: int
    ) -> list[AIInteractionHistoryRecord]:
        """List historical AI interactions for a document."""

    @abstractmethod
    def get_interaction(
        self, *, interaction_id: str, user_id: int
    ) -> AIInteractionRecord:
        """Fetch an AI interaction and its latest suggestion state."""

    @abstractmethod
    def get_interaction_for_suggestion(
        self, *, suggestion_id: str, user_id: int
    ) -> AIInteractionRecord:
        """Fetch the AI interaction that owns a suggestion."""

    @abstractmethod
    def accept_suggestion(
        self,
        *,
        suggestion_id: str,
        user_id: int,
        apply_range_start: int,
        apply_range_end: int,
    ) -> SuggestionOutcomeRecord:
        """Record acceptance of an AI suggestion."""

    @abstractmethod
    def reject_suggestion(
        self, *, suggestion_id: str, user_id: int
    ) -> SuggestionOutcomeRecord:
        """Record rejection of an AI suggestion."""

    @abstractmethod
    def apply_edited_suggestion(
        self,
        *,
        suggestion_id: str,
        user_id: int,
        edited_output: str,
        apply_range_start: int,
        apply_range_end: int,
    ) -> SuggestionOutcomeRecord:
        """Record application of a user-edited AI suggestion."""


class StubAIRepository(AIRepository):
    def __init__(self) -> None:
        self._interaction_sequence = 0
        self._interactions: dict[str, AIInteractionRecord] = {}
        self._prepared_suggestions: dict[str, AISuggestionRecord] = {}
        self._suggestion_to_interaction: dict[str, str] = {}

    def create_interaction(
        self,
        *,
        document_id: int,
        user_id: int,
        feature_type: str,
        scope_type: str,
        base_revision: int,
        rendered_prompt: str,
        selected_range_start: int | None,
        selected_range_end: int | None,
        selected_text_snapshot: str | None,
        surrounding_context: str | None,
        user_instruction: str | None,
        parameters: dict[str, Any],
        generated_output: str,
        model_name: str,
        usage: AIUsageRecord | None,
    ) -> AIInteractionRecord:
        self._interaction_sequence += 1
        interaction_id = f"ai_{self._interaction_sequence}"
        suggestion_id = f"sug_{self._interaction_sequence}"
        created_at = STUB_CREATED_AT + timedelta(minutes=self._interaction_sequence - 1)

        record = AIInteractionRecord(
            interaction_id=interaction_id,
            document_id=document_id,
            user_id=user_id,
            feature_type=feature_type,
            scope_type=scope_type,
            status="pending",
            base_revision=base_revision,
            created_at=created_at,
            completed_at=None,
            rendered_prompt=rendered_prompt,
            selected_range_start=selected_range_start,
            selected_range_end=selected_range_end,
            selected_text_snapshot=selected_text_snapshot,
            surrounding_context=surrounding_context,
            user_instruction=user_instruction,
            parameters=dict(parameters),
        )
        self._interactions[interaction_id] = record
        self._prepared_suggestions[interaction_id] = AISuggestionRecord(
            suggestion_id=suggestion_id,
            generated_output=generated_output,
            model_name=model_name,
            stale=False,
            usage=usage,
        )
        self._suggestion_to_interaction[suggestion_id] = interaction_id
        return record

    def list_interactions(
        self, *, document_id: int, user_id: int
    ) -> list[AIInteractionHistoryRecord]:
        records = [
            AIInteractionHistoryRecord(
                interaction_id=record.interaction_id,
                feature_type=record.feature_type,
                scope_type=record.scope_type,
                user_id=record.user_id,
                status=record.status,
                created_at=record.created_at,
                model_name=(
                    None if record.suggestion is None else record.suggestion.model_name
                ),
                outcome=record.outcome,
                total_tokens=(
                    None
                    if record.suggestion is None or record.suggestion.usage is None
                    else record.suggestion.usage.total_tokens
                ),
            )
            for record in self._complete_matching_interactions(
                document_id=document_id,
                user_id=user_id,
            )
        ]
        return sorted(records, key=lambda record: record.created_at)

    def get_interaction(
        self, *, interaction_id: str, user_id: int
    ) -> AIInteractionRecord:
        self._ensure_owned_interaction(interaction_id=interaction_id, user_id=user_id)
        return self._complete_interaction(interaction_id)

    def get_interaction_for_suggestion(
        self, *, suggestion_id: str, user_id: int
    ) -> AIInteractionRecord:
        return self._get_interaction_for_suggestion(
            suggestion_id=suggestion_id,
            user_id=user_id,
        )

    def accept_suggestion(
        self,
        *,
        suggestion_id: str,
        user_id: int,
        apply_range_start: int,
        apply_range_end: int,
    ) -> SuggestionOutcomeRecord:
        interaction = self._get_interaction_for_suggestion(
            suggestion_id=suggestion_id,
            user_id=user_id,
        )
        self._record_outcome(
            interaction=interaction,
            outcome="accepted",
            apply_range_start=apply_range_start,
            apply_range_end=apply_range_end,
        )
        return SuggestionOutcomeRecord(
            suggestion_id=suggestion_id,
            outcome="accepted",
            applied=True,
            new_revision=interaction.base_revision + 1,
        )

    def reject_suggestion(
        self, *, suggestion_id: str, user_id: int
    ) -> SuggestionOutcomeRecord:
        interaction = self._get_interaction_for_suggestion(
            suggestion_id=suggestion_id,
            user_id=user_id,
        )
        self._record_outcome(
            interaction=interaction,
            outcome="rejected",
        )
        return SuggestionOutcomeRecord(
            suggestion_id=suggestion_id,
            outcome="rejected",
            applied=False,
            new_revision=None,
        )

    def apply_edited_suggestion(
        self,
        *,
        suggestion_id: str,
        user_id: int,
        edited_output: str,
        apply_range_start: int,
        apply_range_end: int,
    ) -> SuggestionOutcomeRecord:
        interaction = self._get_interaction_for_suggestion(
            suggestion_id=suggestion_id,
            user_id=user_id,
        )
        self._record_outcome(
            interaction=interaction,
            outcome="modified",
            apply_range_start=apply_range_start,
            apply_range_end=apply_range_end,
            edited_output=edited_output,
        )
        return SuggestionOutcomeRecord(
            suggestion_id=suggestion_id,
            outcome="modified",
            applied=True,
            new_revision=interaction.base_revision + 1,
        )

    def _complete_matching_interactions(
        self,
        *,
        document_id: int,
        user_id: int,
    ) -> list[AIInteractionRecord]:
        matching_ids = [
            interaction_id
            for interaction_id, record in self._interactions.items()
            if record.document_id == document_id and record.user_id == user_id
        ]
        return [
            self._complete_interaction(interaction_id)
            for interaction_id in matching_ids
        ]

    def _complete_interaction(self, interaction_id: str) -> AIInteractionRecord:
        record = self._interactions[interaction_id]
        if record.status == "completed":
            return record

        completed = replace(
            record,
            status="completed",
            completed_at=record.created_at + timedelta(seconds=2),
            suggestion=self._prepared_suggestions[interaction_id],
        )
        self._interactions[interaction_id] = completed
        return completed

    def _ensure_owned_interaction(self, *, interaction_id: str, user_id: int) -> None:
        record = self._interactions.get(interaction_id)
        if record is None:
            raise AppError(
                status_code=HTTPStatus.NOT_FOUND,
                error_code="AI_INTERACTION_NOT_FOUND",
                message="AI interaction not found.",
            )
        if record.user_id != user_id:
            raise AppError(
                status_code=HTTPStatus.FORBIDDEN,
                error_code=ErrorCode.PERMISSION_DENIED,
                message="You are not allowed to access this AI interaction.",
            )

    def _get_interaction_for_suggestion(
        self, *, suggestion_id: str, user_id: int
    ) -> AIInteractionRecord:
        interaction_id = self._suggestion_to_interaction.get(suggestion_id)
        if interaction_id is None:
            raise AppError(
                status_code=HTTPStatus.NOT_FOUND,
                error_code="AI_SUGGESTION_NOT_FOUND",
                message="AI suggestion not found.",
            )

        self._ensure_owned_interaction(interaction_id=interaction_id, user_id=user_id)
        return self._complete_interaction(interaction_id)

    def _record_outcome(
        self,
        *,
        interaction: AIInteractionRecord,
        outcome: str,
        apply_range_start: int | None = None,
        apply_range_end: int | None = None,
        edited_output: str | None = None,
    ) -> None:
        self._interactions[interaction.interaction_id] = replace(
            interaction,
            outcome=outcome,
            outcome_recorded_at=utc_now(),
            apply_range_start=apply_range_start,
            apply_range_end=apply_range_end,
            edited_output=edited_output,
        )
