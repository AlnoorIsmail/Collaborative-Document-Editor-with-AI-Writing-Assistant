"""Repository seams for AI interaction and suggestion scaffolding."""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from http import HTTPStatus

from apps.backend.core.errors import AppError
from apps.backend.models.ai import (
    AIInteractionHistoryRecord,
    AIInteractionRecord,
    AISuggestionRecord,
    SuggestionOutcomeRecord,
)
from apps.backend.schemas.common import ErrorCode

STUB_CREATED_AT = datetime(2026, 3, 25, 10, 40, tzinfo=timezone.utc)


class AIRepository(ABC):
    @abstractmethod
    def create_interaction(
        self,
        *,
        document_id: str,
        user_id: str,
        feature_type: str,
        scope_type: str,
        base_revision: int,
    ) -> AIInteractionRecord:
        """Create an AI interaction record."""

    @abstractmethod
    def list_interactions(self, *, document_id: str, user_id: str) -> list[AIInteractionHistoryRecord]:
        """List historical AI interactions for a document."""

    @abstractmethod
    def get_interaction(self, *, interaction_id: str, user_id: str) -> AIInteractionRecord:
        """Fetch an AI interaction and its latest suggestion state."""

    @abstractmethod
    def accept_suggestion(
        self,
        *,
        suggestion_id: str,
        user_id: str,
        apply_range_start: int,
        apply_range_end: int,
    ) -> SuggestionOutcomeRecord:
        """Record acceptance of an AI suggestion."""

    @abstractmethod
    def reject_suggestion(self, *, suggestion_id: str, user_id: str) -> SuggestionOutcomeRecord:
        """Record rejection of an AI suggestion."""

    @abstractmethod
    def apply_edited_suggestion(
        self,
        *,
        suggestion_id: str,
        user_id: str,
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
        document_id: str,
        user_id: str,
        feature_type: str,
        scope_type: str,
        base_revision: int,
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
        )
        self._interactions[interaction_id] = record
        self._prepared_suggestions[interaction_id] = AISuggestionRecord(
            suggestion_id=suggestion_id,
            generated_output="More formal rewritten paragraph",
            model_name="gpt-x",
            stale=False,
        )
        self._suggestion_to_interaction[suggestion_id] = interaction_id
        return record

    def list_interactions(self, *, document_id: str, user_id: str) -> list[AIInteractionHistoryRecord]:
        records = [
            AIInteractionHistoryRecord(
                interaction_id=record.interaction_id,
                feature_type=record.feature_type,
                user_id=record.user_id,
                status=record.status,
                created_at=record.created_at,
            )
            for record in self._complete_matching_interactions(document_id=document_id, user_id=user_id)
        ]
        return sorted(records, key=lambda record: record.created_at)

    def get_interaction(self, *, interaction_id: str, user_id: str) -> AIInteractionRecord:
        self._ensure_owned_interaction(interaction_id=interaction_id, user_id=user_id)
        return self._complete_interaction(interaction_id)

    def accept_suggestion(
        self,
        *,
        suggestion_id: str,
        user_id: str,
        apply_range_start: int,
        apply_range_end: int,
    ) -> SuggestionOutcomeRecord:
        del apply_range_start, apply_range_end
        interaction = self._get_interaction_for_suggestion(
            suggestion_id=suggestion_id,
            user_id=user_id,
        )
        return SuggestionOutcomeRecord(
            suggestion_id=suggestion_id,
            outcome="accepted",
            applied=True,
            new_revision=interaction.base_revision + 1,
        )

    def reject_suggestion(self, *, suggestion_id: str, user_id: str) -> SuggestionOutcomeRecord:
        self._get_interaction_for_suggestion(
            suggestion_id=suggestion_id,
            user_id=user_id,
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
        user_id: str,
        edited_output: str,
        apply_range_start: int,
        apply_range_end: int,
    ) -> SuggestionOutcomeRecord:
        del edited_output, apply_range_start, apply_range_end
        interaction = self._get_interaction_for_suggestion(
            suggestion_id=suggestion_id,
            user_id=user_id,
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
        document_id: str,
        user_id: str,
    ) -> list[AIInteractionRecord]:
        matching_ids = [
            interaction_id
            for interaction_id, record in self._interactions.items()
            if record.document_id == document_id and record.user_id == user_id
        ]
        return [self._complete_interaction(interaction_id) for interaction_id in matching_ids]

    def _complete_interaction(self, interaction_id: str) -> AIInteractionRecord:
        record = self._interactions[interaction_id]
        if record.status == "completed":
            return record

        completed = AIInteractionRecord(
            interaction_id=record.interaction_id,
            document_id=record.document_id,
            user_id=record.user_id,
            feature_type=record.feature_type,
            scope_type=record.scope_type,
            status="completed",
            base_revision=record.base_revision,
            created_at=record.created_at,
            suggestion=self._prepared_suggestions[interaction_id],
        )
        self._interactions[interaction_id] = completed
        return completed

    def _ensure_owned_interaction(self, *, interaction_id: str, user_id: str) -> None:
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

    def _get_interaction_for_suggestion(self, *, suggestion_id: str, user_id: str) -> AIInteractionRecord:
        interaction_id = self._suggestion_to_interaction.get(suggestion_id)
        if interaction_id is None:
            raise AppError(
                status_code=HTTPStatus.NOT_FOUND,
                error_code="AI_SUGGESTION_NOT_FOUND",
                message="AI suggestion not found.",
            )

        self._ensure_owned_interaction(interaction_id=interaction_id, user_id=user_id)
        return self._complete_interaction(interaction_id)
