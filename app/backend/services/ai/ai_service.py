"""Service layer for suggestion-based AI endpoints."""

from http import HTTPStatus
from threading import Lock

from sqlalchemy.exc import IntegrityError

from app.backend.core.contracts import parse_resource_id
from app.backend.core.errors import ApiError, AppError
from app.backend.core.security import AuthenticatedPrincipal
from app.backend.integrations.ai_provider import (
    AIProviderClient,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
)
from app.backend.models.ai import AIUsageRecord
from app.backend.repositories.ai import AIRepository
from app.backend.repositories.document_repository import DocumentRepository
from app.backend.repositories.permission_repository import PermissionRepository
from app.backend.repositories.version_repository import VersionRepository
from app.backend.schemas.ai import (
    AIChatMessageStreamRequest,
    AIChatMode,
    AIChatThreadEntryResponse,
    AIEntryKind,
    AIInteractionAcceptedResponse,
    AIInteractionCancelResponse,
    AIInteractionCreateRequest,
    AIInteractionDetailResponse,
    AIInteractionHistoryItem,
    AIMessageRole,
    AIInteractionStatus,
    AISelectionRangeResponse,
    AISuggestionPayload,
    AIUsageResponse,
    AcceptSuggestionRequest,
    AcceptSuggestionResponse,
    ApplyEditedSuggestionRequest,
    ApplyEditedSuggestionResponse,
    RejectSuggestionResponse,
    SuggestionOutcome,
)
from app.backend.schemas.common import ErrorCode, TextRange
from app.backend.services.access_service import DocumentAccessService
from app.backend.services.ai.prompt_builder import PromptTemplateRenderer

AI_INTERACTION_QUOTA_PER_DOCUMENT_USER = 25


class AIService:
    _canceled_interactions: set[str] = set()
    _cancel_lock = Lock()

    def __init__(
        self,
        *,
        repository: AIRepository,
        provider: AIProviderClient,
        document_repository: DocumentRepository,
        permission_repository: PermissionRepository,
        version_repository: VersionRepository,
        prompt_renderer: PromptTemplateRenderer | None = None,
    ) -> None:
        self._repository = repository
        self._provider = provider
        self._document_repository = document_repository
        self._version_repository = version_repository
        self._prompt_renderer = prompt_renderer or PromptTemplateRenderer()
        self._access_service = DocumentAccessService(
            document_repository,
            permission_repository,
        )

    def create_interaction(
        self,
        *,
        document_id: str,
        principal: AuthenticatedPrincipal,
        payload: AIInteractionCreateRequest,
    ) -> AIInteractionAcceptedResponse:
        record = self._build_interaction_record(
            document_id=document_id,
            principal=principal,
            payload=payload,
            entry_kind=AIEntryKind.SUGGESTION.value,
        )
        return AIInteractionAcceptedResponse(
            interaction_id=record.interaction_id,
            status=AIInteractionStatus.PENDING,
            document_id=record.document_id,
            base_revision=record.base_revision,
            created_at=record.created_at,
        )

    def start_stream_interaction(
        self,
        *,
        document_id: str,
        principal: AuthenticatedPrincipal,
        payload: AIInteractionCreateRequest,
    ) -> tuple[AIInteractionAcceptedResponse, str]:
        record = self._build_interaction_record(
            document_id=document_id,
            principal=principal,
            payload=payload,
            entry_kind=AIEntryKind.SUGGESTION.value,
        )
        user_id = self._principal_user_id(principal)
        processing_record = self._repository.mark_interaction_processing(
            interaction_id=record.interaction_id,
            user_id=user_id,
        )
        suggestion = self._repository.get_prepared_suggestion(
            interaction_id=processing_record.interaction_id,
            user_id=user_id,
        )
        return (
            AIInteractionAcceptedResponse(
                interaction_id=processing_record.interaction_id,
                status=AIInteractionStatus.PROCESSING,
                document_id=processing_record.document_id,
                base_revision=processing_record.base_revision,
                created_at=processing_record.created_at,
            ),
            suggestion.generated_output,
        )

    def complete_stream_interaction(
        self,
        *,
        interaction_id: str,
        principal: AuthenticatedPrincipal,
    ) -> AIInteractionDetailResponse:
        user_id = self._principal_user_id(principal)
        self.clear_stream_cancellation(interaction_id=interaction_id)
        self._repository.complete_interaction(
            interaction_id=interaction_id,
            user_id=user_id,
        )
        return self.get_interaction(interaction_id=interaction_id, principal=principal)

    def fail_stream_interaction(
        self,
        *,
        interaction_id: str,
        principal: AuthenticatedPrincipal,
    ) -> AIInteractionCancelResponse:
        user_id = self._principal_user_id(principal)
        self.clear_stream_cancellation(interaction_id=interaction_id)
        failed = self._repository.fail_interaction(
            interaction_id=interaction_id,
            user_id=user_id,
        )
        return AIInteractionCancelResponse(
            interaction_id=failed.interaction_id,
            status=AIInteractionStatus(failed.status),
            canceled_at=failed.completed_at or failed.created_at,
        )

    def cancel_stream_interaction(
        self,
        *,
        interaction_id: str,
        principal: AuthenticatedPrincipal,
    ) -> AIInteractionCancelResponse:
        with self._cancel_lock:
            self._canceled_interactions.add(interaction_id)
        user_id = self._principal_user_id(principal)
        failed = self._repository.fail_interaction(
            interaction_id=interaction_id,
            user_id=user_id,
        )
        return AIInteractionCancelResponse(
            interaction_id=failed.interaction_id,
            status=AIInteractionStatus(failed.status),
            canceled_at=failed.completed_at or failed.created_at,
        )

    def is_stream_canceled(self, *, interaction_id: str) -> bool:
        return interaction_id in self._canceled_interactions

    def clear_stream_cancellation(self, *, interaction_id: str) -> None:
        with self._cancel_lock:
            self._canceled_interactions.discard(interaction_id)

    def list_interactions(
        self,
        *,
        document_id: str,
        principal: AuthenticatedPrincipal,
    ) -> list[AIInteractionHistoryItem]:
        user_id = self._principal_user_id(principal)
        access = self._access_service.require_read_access(
            document_id=document_id,
            user_id=user_id,
        )
        records = self._repository.list_interactions(
            document_id=access.document.id,
            user_id=user_id,
        )
        return [
            AIInteractionHistoryItem(
                interaction_id=record.interaction_id,
                conversation_id=record.conversation_id,
                entry_kind=AIEntryKind(record.entry_kind),
                message_role=AIMessageRole(record.message_role),
                feature_type=record.feature_type,
                scope_type=record.scope_type,
                user_id=record.user_id,
                status=AIInteractionStatus(record.status),
                created_at=record.created_at,
                source_revision=record.source_revision,
                model_name=record.model_name,
                outcome=(
                    None if record.outcome is None else SuggestionOutcome(record.outcome)
                ),
                total_tokens=record.total_tokens,
            )
            for record in records
        ]

    def list_chat_thread(
        self,
        *,
        document_id: str,
        principal: AuthenticatedPrincipal,
    ) -> list[AIChatThreadEntryResponse]:
        user_id = self._principal_user_id(principal)
        access = self._access_service.require_read_access(
            document_id=document_id,
            user_id=user_id,
        )
        records = self._repository.list_thread(
            document_id=access.document.id,
            user_id=user_id,
        )
        return [self._to_thread_entry_response(record, access.current_revision) for record in records]

    def start_stream_chat_message(
        self,
        *,
        document_id: str,
        principal: AuthenticatedPrincipal,
        payload: AIChatMessageStreamRequest,
    ) -> tuple[AIInteractionAcceptedResponse, str]:
        feature_type = (
            "chat_assistant"
            if payload.mode == AIChatMode.CHAT
            else "rewrite"
        )
        scope_type = "selection" if payload.selected_range is not None else "document"
        interaction_payload = AIInteractionCreateRequest(
            feature_type=feature_type,
            scope_type=scope_type,
            selected_range=payload.selected_range,
            selected_text_snapshot=payload.selected_text_snapshot,
            surrounding_context=payload.surrounding_context,
            user_instruction=payload.message,
            base_revision=payload.base_revision,
            parameters={"mode": payload.mode.value},
        )
        entry_kind = (
            AIEntryKind.CHAT_MESSAGE.value
            if payload.mode == AIChatMode.CHAT
            else AIEntryKind.SUGGESTION.value
        )
        record = self._build_interaction_record(
            document_id=document_id,
            principal=principal,
            payload=interaction_payload,
            entry_kind=entry_kind,
        )
        user_id = self._principal_user_id(principal)
        processing_record = self._repository.mark_interaction_processing(
            interaction_id=record.interaction_id,
            user_id=user_id,
        )
        suggestion = self._repository.get_prepared_suggestion(
            interaction_id=processing_record.interaction_id,
            user_id=user_id,
        )
        return (
            AIInteractionAcceptedResponse(
                interaction_id=processing_record.interaction_id,
                status=AIInteractionStatus.PROCESSING,
                document_id=processing_record.document_id,
                base_revision=processing_record.base_revision,
                created_at=processing_record.created_at,
            ),
            suggestion.generated_output,
        )

    def get_interaction(
        self,
        *,
        interaction_id: str,
        principal: AuthenticatedPrincipal,
    ) -> AIInteractionDetailResponse:
        user_id = self._principal_user_id(principal)
        record = self._repository.get_interaction(
            interaction_id=interaction_id,
            user_id=user_id,
        )
        access = self._access_service.require_read_access(
            document_id=record.document_id,
            user_id=user_id,
        )
        suggestion = None
        if record.suggestion is not None:
            suggestion = AISuggestionPayload(
                suggestion_id=record.suggestion.suggestion_id,
                generated_output=record.suggestion.generated_output,
                model_name=record.suggestion.model_name,
                stale=access.current_revision != record.base_revision,
                usage=self._to_usage_response(record.suggestion.usage),
            )
        return AIInteractionDetailResponse(
            interaction_id=record.interaction_id,
            conversation_id=record.conversation_id,
            entry_kind=AIEntryKind(record.entry_kind),
            message_role=AIMessageRole(record.message_role),
            feature_type=record.feature_type,
            scope_type=record.scope_type,
            status=AIInteractionStatus(record.status),
            document_id=record.document_id,
            source_revision=record.base_revision,
            base_revision=record.base_revision,
            created_at=record.created_at,
            completed_at=record.completed_at,
            rendered_prompt=record.rendered_prompt,
            selected_range=self._to_selected_range_response(record),
            selected_text_snapshot=record.selected_text_snapshot,
            surrounding_context=record.surrounding_context,
            user_instruction=record.user_instruction,
            reply_to_interaction_id=record.reply_to_interaction_id,
            parameters={} if record.parameters is None else dict(record.parameters),
            outcome=(
                None if record.outcome is None else SuggestionOutcome(record.outcome)
            ),
            outcome_recorded_at=record.outcome_recorded_at,
            suggestion=suggestion,
        )

    def accept_suggestion(
        self,
        *,
        suggestion_id: str,
        principal: AuthenticatedPrincipal,
        payload: AcceptSuggestionRequest,
    ) -> AcceptSuggestionResponse:
        user_id = self._principal_user_id(principal)
        record = self._repository.get_interaction_for_suggestion(
            suggestion_id=suggestion_id,
            user_id=user_id,
        )
        access = self._access_service.require_ai_access(
            document_id=record.document_id,
            user_id=user_id,
        )
        self._ensure_matching_revision(
            base_revision=record.base_revision,
            current_revision=access.current_revision,
            error_code=ErrorCode.STALE_SELECTION,
        )
        if record.suggestion is None:
            raise AppError(
                status_code=HTTPStatus.CONFLICT,
                error_code=ErrorCode.CONFLICT_DETECTED,
                message="The AI interaction has not completed yet.",
            )

        try:
            updated_document = self._apply_replacement(
                document=access.document,
                apply_to_range=payload.apply_to_range,
                replacement=record.suggestion.generated_output,
            )
            version = self._create_version(document=updated_document, user_id=user_id)
            self._document_repository.db.commit()
        except IntegrityError as exc:
            self._document_repository.db.rollback()
            raise AppError(
                status_code=HTTPStatus.CONFLICT,
                error_code=ErrorCode.STALE_SELECTION,
                message=(
                    "The selected content changed before the AI suggestion could "
                    "be applied. Refresh and retry the AI action."
                ),
            ) from exc

        outcome = self._repository.accept_suggestion(
            suggestion_id=suggestion_id,
            user_id=user_id,
            apply_range_start=payload.apply_to_range.start,
            apply_range_end=payload.apply_to_range.end,
        )
        return AcceptSuggestionResponse(
            suggestion_id=outcome.suggestion_id,
            outcome=SuggestionOutcome(outcome.outcome),
            applied=outcome.applied,
            new_revision=version.version_number,
        )

    def reject_suggestion(
        self,
        *,
        suggestion_id: str,
        principal: AuthenticatedPrincipal,
    ) -> RejectSuggestionResponse:
        user_id = self._principal_user_id(principal)
        outcome = self._repository.reject_suggestion(
            suggestion_id=suggestion_id,
            user_id=user_id,
        )
        return RejectSuggestionResponse(
            suggestion_id=outcome.suggestion_id,
            outcome=SuggestionOutcome(outcome.outcome),
        )

    def apply_edited_suggestion(
        self,
        *,
        suggestion_id: str,
        principal: AuthenticatedPrincipal,
        payload: ApplyEditedSuggestionRequest,
    ) -> ApplyEditedSuggestionResponse:
        user_id = self._principal_user_id(principal)
        record = self._repository.get_interaction_for_suggestion(
            suggestion_id=suggestion_id,
            user_id=user_id,
        )
        access = self._access_service.require_ai_access(
            document_id=record.document_id,
            user_id=user_id,
        )
        self._ensure_matching_revision(
            base_revision=record.base_revision,
            current_revision=access.current_revision,
            error_code=ErrorCode.STALE_SELECTION,
        )

        try:
            updated_document = self._apply_replacement(
                document=access.document,
                apply_to_range=payload.apply_to_range,
                replacement=payload.edited_output,
            )
            version = self._create_version(document=updated_document, user_id=user_id)
            self._document_repository.db.commit()
        except IntegrityError as exc:
            self._document_repository.db.rollback()
            raise AppError(
                status_code=HTTPStatus.CONFLICT,
                error_code=ErrorCode.STALE_SELECTION,
                message=(
                    "The selected content changed before the AI suggestion could "
                    "be applied. Refresh and retry the AI action."
                ),
            ) from exc

        outcome = self._repository.apply_edited_suggestion(
            suggestion_id=suggestion_id,
            user_id=user_id,
            edited_output=payload.edited_output,
            apply_range_start=payload.apply_to_range.start,
            apply_range_end=payload.apply_to_range.end,
        )
        return ApplyEditedSuggestionResponse(
            suggestion_id=outcome.suggestion_id,
            outcome=SuggestionOutcome(outcome.outcome),
            applied=outcome.applied,
            new_revision=version.version_number,
        )

    def _ensure_quota(self, *, document_id: int, user_id: int) -> None:
        interaction_count = len(
            self._repository.list_interactions(
                document_id=document_id,
                user_id=user_id,
            )
        )
        if interaction_count < AI_INTERACTION_QUOTA_PER_DOCUMENT_USER:
            return
        raise AppError(
            status_code=HTTPStatus.TOO_MANY_REQUESTS,
            error_code=ErrorCode.AI_QUOTA_EXCEEDED,
            message="AI usage quota exceeded for this document.",
        )

    def _principal_user_id(self, principal: AuthenticatedPrincipal) -> int:
        try:
            return parse_resource_id(principal.user_id, "usr")
        except ApiError as exc:
            raise AppError(
                status_code=HTTPStatus.UNAUTHORIZED,
                error_code=ErrorCode.UNAUTHORIZED,
                message="Missing or invalid bearer token.",
            ) from exc

    def _ensure_matching_revision(
        self,
        *,
        base_revision: int,
        current_revision: int,
        error_code: ErrorCode = ErrorCode.CONFLICT_DETECTED,
    ) -> None:
        if base_revision == current_revision:
            return
        message = "The selected content is stale. Refresh and retry the AI action."
        if error_code == ErrorCode.CONFLICT_DETECTED:
            message = "The document revision is stale. Refresh and retry."
        raise AppError(
            status_code=HTTPStatus.CONFLICT,
            error_code=error_code,
            message=message,
        )

    def _to_selected_range_response(
        self, record
    ) -> AISelectionRangeResponse | None:
        if record.selected_range_start is None or record.selected_range_end is None:
            return None
        return AISelectionRangeResponse(
            start=record.selected_range_start,
            end=record.selected_range_end,
        )

    def _to_usage_record(
        self, usage
    ) -> AIUsageRecord | None:
        if usage is None:
            return None
        return AIUsageRecord(
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            estimated_cost_usd=usage.estimated_cost_usd,
        )

    def _to_usage_response(
        self, usage: AIUsageRecord | None
    ) -> AIUsageResponse | None:
        if usage is None:
            return None
        return AIUsageResponse(
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            estimated_cost_usd=usage.estimated_cost_usd,
        )

    def _apply_replacement(self, *, document, apply_to_range: TextRange, replacement: str):
        content_length = len(document.content)
        if apply_to_range.end > content_length:
            raise AppError(
                status_code=HTTPStatus.BAD_REQUEST,
                error_code=ErrorCode.VALIDATION_ERROR,
                message="The apply range is outside the current document bounds.",
            )

        updated_content = (
            document.content[: apply_to_range.start]
            + replacement
            + document.content[apply_to_range.end :]
        )
        return self._document_repository.update(document, content=updated_content)

    def _create_version(self, *, document, user_id: int):
        latest_version = self._version_repository.get_latest_for_document(document.id)
        version = self._version_repository.create(
            document_id=document.id,
            version_number=1 if latest_version is None else latest_version.version_number + 1,
            content_snapshot=document.content,
            line_spacing_snapshot=document.line_spacing,
            save_source="manual",
            created_by=user_id,
            is_restore_version=False,
        )
        self._document_repository.update(document, latest_version_id=version.id)
        return version

    def _build_interaction_record(
        self,
        *,
        document_id: str,
        principal: AuthenticatedPrincipal,
        payload: AIInteractionCreateRequest,
        entry_kind: str,
    ):
        user_id = self._principal_user_id(principal)
        access = self._access_service.require_ai_access(
            document_id=document_id,
            user_id=user_id,
        )
        self._ensure_matching_revision(
            base_revision=payload.base_revision,
            current_revision=access.current_revision,
        )
        self._ensure_quota(document_id=access.document.id, user_id=user_id)

        conversation_id = self._conversation_id(
            document_id=access.document.id,
            user_id=user_id,
        )
        prior_entries = self._repository.list_thread(
            document_id=access.document.id,
            user_id=user_id,
        )
        reply_to_interaction_id = next(
            (
                entry.interaction_id
                for entry in reversed(prior_entries)
                if entry.message_role == "assistant" and entry.interaction_id
            ),
            None,
        )
        self._repository.create_user_thread_entry(
            document_id=access.document.id,
            user_id=user_id,
            conversation_id=conversation_id,
            feature_type=payload.feature_type,
            scope_type=payload.scope_type,
            source_revision=payload.base_revision,
            content=self._build_user_thread_message(payload=payload, entry_kind=entry_kind),
            selected_range_start=(
                None if payload.selected_range is None else payload.selected_range.start
            ),
            selected_range_end=(
                None if payload.selected_range is None else payload.selected_range.end
            ),
            selected_text_snapshot=payload.selected_text_snapshot,
            surrounding_context=payload.surrounding_context,
            reply_to_interaction_id=reply_to_interaction_id,
            entry_kind=entry_kind,
        )
        enriched_payload = payload.model_copy(
            update={
                "surrounding_context": self._build_prompt_context(
                    document_title=access.document.title,
                    current_revision=access.current_revision,
                    raw_context=payload.surrounding_context,
                    prior_entries=prior_entries,
                ),
            }
        )

        try:
            prompt = self._prompt_renderer.render(enriched_payload)
            suggestion = self._provider.generate_suggestion(
                feature_type=payload.feature_type,
                prompt=prompt,
            )
        except AIProviderTimeoutError as exc:
            raise AppError(
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                error_code=ErrorCode.PROVIDER_TIMEOUT,
                message="The AI provider timed out. Please retry.",
                retryable=True,
            ) from exc
        except AIProviderUnavailableError as exc:
            raise AppError(
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                error_code=ErrorCode.PROVIDER_UNAVAILABLE,
                message="The AI provider is temporarily unavailable. Please retry.",
                retryable=True,
            ) from exc

        return self._repository.create_interaction(
            document_id=access.document.id,
            user_id=user_id,
            conversation_id=conversation_id,
            entry_kind=entry_kind,
            message_role=AIMessageRole.ASSISTANT.value,
            reply_to_interaction_id=reply_to_interaction_id,
            feature_type=payload.feature_type,
            scope_type=payload.scope_type,
            base_revision=payload.base_revision,
            rendered_prompt=prompt,
            selected_range_start=(
                None if payload.selected_range is None else payload.selected_range.start
            ),
            selected_range_end=(
                None if payload.selected_range is None else payload.selected_range.end
            ),
            selected_text_snapshot=payload.selected_text_snapshot,
            surrounding_context=payload.surrounding_context,
            user_instruction=payload.user_instruction,
            parameters=payload.parameters,
            generated_output=suggestion.generated_output,
            model_name=suggestion.model_name,
            usage=self._to_usage_record(suggestion.usage),
        )

    def _to_thread_entry_response(
        self,
        record,
        current_revision: int,
    ) -> AIChatThreadEntryResponse:
        suggestion = None
        review_only = record.feature_type == "summarize" or record.entry_kind == "chat_message"
        if record.suggestion is not None:
            suggestion = AISuggestionPayload(
                suggestion_id=record.suggestion.suggestion_id,
                generated_output=record.suggestion.generated_output,
                model_name=record.suggestion.model_name,
                stale=current_revision != record.source_revision,
                usage=self._to_usage_response(record.suggestion.usage),
            )
        return AIChatThreadEntryResponse(
            entry_id=record.entry_id,
            interaction_id=record.interaction_id,
            conversation_id=record.conversation_id,
            entry_kind=AIEntryKind(record.entry_kind),
            message_role=AIMessageRole(record.message_role),
            feature_type=record.feature_type,
            scope_type=record.scope_type,
            status=AIInteractionStatus(record.status),
            created_at=record.created_at,
            source_revision=record.source_revision,
            content=record.content,
            selected_range=self._to_selected_range_response(record),
            selected_text_snapshot=record.selected_text_snapshot,
            surrounding_context=record.surrounding_context,
            reply_to_interaction_id=record.reply_to_interaction_id,
            outcome=(
                None if record.outcome is None else SuggestionOutcome(record.outcome)
            ),
            review_only=review_only,
            suggestion=suggestion,
        )

    def _conversation_id(self, *, document_id: int, user_id: int) -> str:
        return f"conv_doc_{document_id}_usr_{user_id}"

    def _build_prompt_context(
        self,
        *,
        document_title: str | None,
        current_revision: int,
        raw_context: str | None,
        prior_entries: list,
    ) -> str:
        parts: list[str] = []
        if document_title:
            parts.append(f"Document title: {document_title}")
        parts.append(f"Current revision: {current_revision}")
        if raw_context and raw_context.strip():
            parts.append(raw_context.strip())
        recent_turns = [
            entry
            for entry in prior_entries[-6:]
            if entry.content.strip()
        ]
        if recent_turns:
            parts.append(
                "Recent AI thread:\n"
                + "\n".join(
                    f"{'User' if entry.message_role == 'user' else 'Assistant'}: {entry.content.strip()}"
                    for entry in recent_turns
                )
            )
        return "\n\n".join(parts)

    def _build_user_thread_message(
        self,
        *,
        payload: AIInteractionCreateRequest,
        entry_kind: str,
    ) -> str:
        scope_label = (
            "selected text"
            if payload.scope_type == "selection"
            else "the document"
        )
        instruction = (payload.user_instruction or "").strip()
        if payload.feature_type == "chat_assistant" and instruction:
            return instruction
        if payload.feature_type == "summarize":
            return (
                f"Summarize {scope_label}."
                if not instruction
                else f"Summarize {scope_label}. Focus: {instruction}"
            )
        if payload.feature_type == "translate":
            target_language = str(payload.parameters.get("target_language") or "the target language")
            prefix = f"Translate {scope_label} to {target_language}."
            return prefix if not instruction else f"{prefix} Notes: {instruction}"
        if payload.feature_type == "grammar_fix":
            prefix = f"Fix grammar in {scope_label}."
            return prefix if not instruction else f"{prefix} Notes: {instruction}"
        if payload.feature_type == "expand":
            prefix = f"Expand {scope_label}."
            return prefix if not instruction else f"{prefix} Focus: {instruction}"
        if payload.feature_type == "restructure":
            prefix = f"Restructure {scope_label}."
            return prefix if not instruction else f"{prefix} Goal: {instruction}"
        if entry_kind == AIEntryKind.SUGGESTION.value:
            prefix = f"Suggest edits for {scope_label}."
            return prefix if not instruction else f"{prefix} Request: {instruction}"
        return instruction or f"Ask AI about {scope_label}."
