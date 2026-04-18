"""Repository seams for AI interaction, thread, and suggestion scaffolding."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from typing import Any

from app.backend.core.contracts import utc_now
from app.backend.core.errors import AppError
from app.backend.models.ai import (
    AIChatThreadEntryRecord,
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
    def create_user_thread_entry(
        self,
        *,
        document_id: int,
        user_id: int,
        conversation_id: str,
        feature_type: str,
        scope_type: str,
        source_revision: int,
        content: str,
        selected_range_start: int | None,
        selected_range_end: int | None,
        selected_text_snapshot: str | None,
        surrounding_context: str | None,
        reply_to_interaction_id: str | None,
        entry_kind: str,
    ) -> AIChatThreadEntryRecord:
        """Persist a user-side thread entry."""

    @abstractmethod
    def create_interaction(
        self,
        *,
        document_id: int,
        user_id: int,
        conversation_id: str,
        entry_kind: str,
        message_role: str,
        reply_to_interaction_id: str | None,
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
    def list_thread(
        self, *, document_id: int, user_id: int
    ) -> list[AIChatThreadEntryRecord]:
        """List a per-document AI transcript for one user."""

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
    def get_prepared_suggestion(
        self, *, interaction_id: str, user_id: int
    ) -> AISuggestionRecord:
        """Fetch the prepared suggestion output before completion is finalized."""

    @abstractmethod
    def mark_interaction_processing(
        self, *, interaction_id: str, user_id: int
    ) -> AIInteractionRecord:
        """Mark an AI interaction as actively streaming/processing."""

    @abstractmethod
    def complete_interaction(
        self, *, interaction_id: str, user_id: int
    ) -> AIInteractionRecord:
        """Finalize an AI interaction and attach its suggestion payload."""

    @abstractmethod
    def fail_interaction(
        self, *, interaction_id: str, user_id: int
    ) -> AIInteractionRecord:
        """Mark an AI interaction as failed or canceled."""

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
        self._thread_sequence = 0
        self._interactions: dict[str, AIInteractionRecord] = {}
        self._prepared_suggestions: dict[str, AISuggestionRecord] = {}
        self._suggestion_to_interaction: dict[str, str] = {}
        self._thread_entries: dict[str, AIChatThreadEntryRecord] = {}
        self._thread_entry_ids_by_document_user: dict[tuple[int, int], list[str]] = {}
        self._assistant_thread_entry_by_interaction: dict[str, str] = {}

    def create_user_thread_entry(
        self,
        *,
        document_id: int,
        user_id: int,
        conversation_id: str,
        feature_type: str,
        scope_type: str,
        source_revision: int,
        content: str,
        selected_range_start: int | None,
        selected_range_end: int | None,
        selected_text_snapshot: str | None,
        surrounding_context: str | None,
        reply_to_interaction_id: str | None,
        entry_kind: str,
    ) -> AIChatThreadEntryRecord:
        self._thread_sequence += 1
        created_at = STUB_CREATED_AT + timedelta(seconds=self._thread_sequence - 1)
        entry = AIChatThreadEntryRecord(
            entry_id=f"thread_{self._thread_sequence}",
            interaction_id=None,
            conversation_id=conversation_id,
            entry_kind=entry_kind,
            message_role="user",
            feature_type=feature_type,
            scope_type=scope_type,
            status="completed",
            created_at=created_at,
            source_revision=source_revision,
            content=content,
            selected_range_start=selected_range_start,
            selected_range_end=selected_range_end,
            selected_text_snapshot=selected_text_snapshot,
            surrounding_context=surrounding_context,
            reply_to_interaction_id=reply_to_interaction_id,
        )
        self._store_thread_entry(entry, document_id=document_id, user_id=user_id)
        return entry

    def create_interaction(
        self,
        *,
        document_id: int,
        user_id: int,
        conversation_id: str,
        entry_kind: str,
        message_role: str,
        reply_to_interaction_id: str | None,
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

        suggestion = AISuggestionRecord(
            suggestion_id=suggestion_id,
            generated_output=generated_output,
            model_name=model_name,
            stale=False,
            usage=usage,
        )
        record = AIInteractionRecord(
            interaction_id=interaction_id,
            document_id=document_id,
            user_id=user_id,
            conversation_id=conversation_id,
            entry_kind=entry_kind,
            message_role=message_role,
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
            reply_to_interaction_id=reply_to_interaction_id,
            parameters=dict(parameters),
        )
        self._interactions[interaction_id] = record
        self._prepared_suggestions[interaction_id] = suggestion
        self._suggestion_to_interaction[suggestion_id] = interaction_id

        self._thread_sequence += 1
        assistant_entry = AIChatThreadEntryRecord(
            entry_id=f"thread_{self._thread_sequence}",
            interaction_id=interaction_id,
            conversation_id=conversation_id,
            entry_kind=entry_kind,
            message_role=message_role,
            feature_type=feature_type,
            scope_type=scope_type,
            status="pending",
            created_at=created_at + timedelta(seconds=1),
            source_revision=base_revision,
            content=generated_output,
            selected_range_start=selected_range_start,
            selected_range_end=selected_range_end,
            selected_text_snapshot=selected_text_snapshot,
            surrounding_context=surrounding_context,
            reply_to_interaction_id=reply_to_interaction_id,
            suggestion=suggestion,
        )
        self._assistant_thread_entry_by_interaction[interaction_id] = assistant_entry.entry_id
        self._store_thread_entry(assistant_entry, document_id=document_id, user_id=user_id)
        return record

    def list_interactions(
        self, *, document_id: int, user_id: int
    ) -> list[AIInteractionHistoryRecord]:
        records = [
            AIInteractionHistoryRecord(
                interaction_id=record.interaction_id,
                conversation_id=record.conversation_id,
                entry_kind=record.entry_kind,
                message_role=record.message_role,
                feature_type=record.feature_type,
                scope_type=record.scope_type,
                user_id=record.user_id,
                status=record.status,
                created_at=record.created_at,
                source_revision=record.base_revision,
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

    def list_thread(
        self, *, document_id: int, user_id: int
    ) -> list[AIChatThreadEntryRecord]:
        self._complete_matching_interactions(document_id=document_id, user_id=user_id)
        entry_ids = self._thread_entry_ids_by_document_user.get((document_id, user_id), [])
        return [
            self._thread_entries[entry_id]
            for entry_id in entry_ids
        ]

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

    def get_prepared_suggestion(
        self, *, interaction_id: str, user_id: int
    ) -> AISuggestionRecord:
        self._ensure_owned_interaction(interaction_id=interaction_id, user_id=user_id)
        return self._prepared_suggestions[interaction_id]

    def mark_interaction_processing(
        self, *, interaction_id: str, user_id: int
    ) -> AIInteractionRecord:
        self._ensure_owned_interaction(interaction_id=interaction_id, user_id=user_id)
        record = self._interactions[interaction_id]
        if record.status == "pending":
            record = replace(record, status="processing")
            self._interactions[interaction_id] = record
            self._update_assistant_thread_entry(interaction_id, status="processing")
        return record

    def complete_interaction(
        self, *, interaction_id: str, user_id: int
    ) -> AIInteractionRecord:
        self._ensure_owned_interaction(interaction_id=interaction_id, user_id=user_id)
        return self._finalize_interaction(interaction_id)

    def fail_interaction(
        self, *, interaction_id: str, user_id: int
    ) -> AIInteractionRecord:
        self._ensure_owned_interaction(interaction_id=interaction_id, user_id=user_id)
        record = self._interactions[interaction_id]
        if record.status == "completed":
            return record
        failed = replace(
            record,
            status="failed",
            completed_at=utc_now(),
        )
        self._interactions[interaction_id] = failed
        self._update_assistant_thread_entry(
            interaction_id,
            status="failed",
            suggestion=failed.suggestion,
            outcome=failed.outcome,
        )
        return failed

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
        if record.status == "pending":
            return self._finalize_interaction(interaction_id)
        if record.status in {"completed", "failed", "processing"}:
            return record
        return record

    def _finalize_interaction(self, interaction_id: str) -> AIInteractionRecord:
        record = self._interactions[interaction_id]
        if record.status in {"completed", "failed"}:
            return record

        completed = replace(
            record,
            status="completed",
            completed_at=record.created_at + timedelta(seconds=2),
            suggestion=self._prepared_suggestions[interaction_id],
        )
        self._interactions[interaction_id] = completed
        self._update_assistant_thread_entry(
            interaction_id,
            status="completed",
            suggestion=self._prepared_suggestions[interaction_id],
            outcome=completed.outcome,
        )
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
        updated = replace(
            interaction,
            outcome=outcome,
            outcome_recorded_at=utc_now(),
            apply_range_start=apply_range_start,
            apply_range_end=apply_range_end,
            edited_output=edited_output,
        )
        self._interactions[interaction.interaction_id] = updated
        self._update_assistant_thread_entry(
            interaction.interaction_id,
            status=updated.status,
            suggestion=updated.suggestion,
            outcome=outcome,
        )

    def _store_thread_entry(
        self,
        entry: AIChatThreadEntryRecord,
        *,
        document_id: int,
        user_id: int,
    ) -> None:
        self._thread_entries[entry.entry_id] = entry
        key = (document_id, user_id)
        self._thread_entry_ids_by_document_user.setdefault(key, []).append(entry.entry_id)
        self._thread_entry_ids_by_document_user[key].sort(
            key=lambda entry_id: self._thread_entries[entry_id].created_at
        )

    def _update_assistant_thread_entry(
        self,
        interaction_id: str,
        *,
        status: str,
        suggestion: AISuggestionRecord | None = None,
        outcome: str | None = None,
    ) -> None:
        entry_id = self._assistant_thread_entry_by_interaction.get(interaction_id)
        if entry_id is None:
            return
        entry = self._thread_entries[entry_id]
        next_suggestion = suggestion if suggestion is not None else entry.suggestion
        self._thread_entries[entry_id] = replace(
            entry,
            status=status,
            suggestion=next_suggestion,
            outcome=outcome if outcome is not None else entry.outcome,
        )
