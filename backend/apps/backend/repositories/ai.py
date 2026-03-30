"""Repository seams for AI interaction and suggestion scaffolding."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone

from apps.backend.models.ai import (
    AIInteractionHistoryRecord,
    AIInteractionRecord,
    AISuggestionRecord,
    SuggestionOutcomeRecord,
)

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
    def create_interaction(
        self,
        *,
        document_id: str,
        user_id: str,
        feature_type: str,
        scope_type: str,
        base_revision: int,
    ) -> AIInteractionRecord:
        # TODO: Store AI interaction metadata and prompt context in persistent storage.
        return AIInteractionRecord(
            interaction_id="ai_1",
            document_id=document_id,
            user_id=user_id,
            feature_type=feature_type,
            scope_type=scope_type,
            status="pending",
            base_revision=base_revision,
            created_at=STUB_CREATED_AT,
        )

    def list_interactions(self, *, document_id: str, user_id: str) -> list[AIInteractionHistoryRecord]:
        # TODO: Query interaction history by document and permission-scoped principal.
        del document_id
        return [
            AIInteractionHistoryRecord(
                interaction_id="ai_1",
                feature_type="rewrite",
                user_id=user_id,
                status="completed",
                created_at=STUB_CREATED_AT,
            )
        ]

    def get_interaction(self, *, interaction_id: str, user_id: str) -> AIInteractionRecord:
        # TODO: Load interaction and suggestion state from persistent AI logs.
        del user_id
        return AIInteractionRecord(
            interaction_id=interaction_id,
            document_id="doc_101",
            user_id="usr_123",
            feature_type="rewrite",
            scope_type="selection",
            status="completed",
            base_revision=22,
            created_at=STUB_CREATED_AT,
            suggestion=AISuggestionRecord(
                suggestion_id="sug_1",
                generated_output="More formal rewritten paragraph",
                model_name="gpt-x",
                stale=False,
            ),
        )

    def accept_suggestion(
        self,
        *,
        suggestion_id: str,
        user_id: str,
        apply_range_start: int,
        apply_range_end: int,
    ) -> SuggestionOutcomeRecord:
        # TODO: Persist suggestion acceptance and append a new document revision.
        del user_id, apply_range_start, apply_range_end
        return SuggestionOutcomeRecord(
            suggestion_id=suggestion_id,
            outcome="accepted",
            applied=True,
            new_revision=23,
        )

    def reject_suggestion(self, *, suggestion_id: str, user_id: str) -> SuggestionOutcomeRecord:
        # TODO: Persist suggestion rejection for auditability.
        del user_id
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
        # TODO: Persist edited suggestion application and append a new document revision.
        del user_id, edited_output, apply_range_start, apply_range_end
        return SuggestionOutcomeRecord(
            suggestion_id=suggestion_id,
            outcome="modified",
            applied=True,
            new_revision=23,
        )
