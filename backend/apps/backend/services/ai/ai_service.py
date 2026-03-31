"""Service layer for suggestion-based AI endpoints."""

from http import HTTPStatus

from apps.backend.core.errors import AppError
from apps.backend.core.security import AuthenticatedPrincipal
from apps.backend.integrations.ai_provider import AIProviderClient
from apps.backend.repositories.ai import AIRepository
from apps.backend.schemas.common import ErrorCode
from apps.backend.schemas.ai import (
    AIInteractionAcceptedResponse,
    AIInteractionCreateRequest,
    AIInteractionDetailResponse,
    AIInteractionHistoryItem,
    AIInteractionStatus,
    AISuggestionPayload,
    AcceptSuggestionRequest,
    AcceptSuggestionResponse,
    ApplyEditedSuggestionRequest,
    ApplyEditedSuggestionResponse,
    RejectSuggestionResponse,
    SuggestionOutcome,
)


class AIService:
    def __init__(self, *, repository: AIRepository, provider: AIProviderClient) -> None:
        self._repository = repository
        self._provider = provider

    def create_interaction(
        self,
        *,
        document_id: str,
        principal: AuthenticatedPrincipal,
        payload: AIInteractionCreateRequest,
    ) -> AIInteractionAcceptedResponse:
        self._ensure_ai_role_allowed(principal)
        # TODO: Use the provider seam to enqueue or orchestrate async suggestion generation.
        _ = self._provider
        record = self._repository.create_interaction(
            document_id=document_id,
            user_id=principal.user_id,
            feature_type=payload.feature_type,
            scope_type=payload.scope_type,
            base_revision=payload.base_revision,
        )
        return AIInteractionAcceptedResponse(
            interaction_id=record.interaction_id,
            status=AIInteractionStatus(record.status),
            document_id=record.document_id,
            base_revision=record.base_revision,
            created_at=record.created_at,
        )

    def list_interactions(
        self,
        *,
        document_id: str,
        principal: AuthenticatedPrincipal,
    ) -> list[AIInteractionHistoryItem]:
        self._ensure_ai_role_allowed(principal)
        records = self._repository.list_interactions(
            document_id=document_id,
            user_id=principal.user_id,
        )
        return [
            AIInteractionHistoryItem(
                interaction_id=record.interaction_id,
                feature_type=record.feature_type,
                user_id=record.user_id,
                status=AIInteractionStatus(record.status),
                created_at=record.created_at,
            )
            for record in records
        ]

    def get_interaction(
        self,
        *,
        interaction_id: str,
        principal: AuthenticatedPrincipal,
    ) -> AIInteractionDetailResponse:
        self._ensure_ai_role_allowed(principal)
        record = self._repository.get_interaction(
            interaction_id=interaction_id,
            user_id=principal.user_id,
        )
        suggestion = None
        if record.suggestion is not None:
            suggestion = AISuggestionPayload(
                suggestion_id=record.suggestion.suggestion_id,
                generated_output=record.suggestion.generated_output,
                model_name=record.suggestion.model_name,
                stale=record.suggestion.stale,
            )
        return AIInteractionDetailResponse(
            interaction_id=record.interaction_id,
            status=AIInteractionStatus(record.status),
            document_id=record.document_id,
            base_revision=record.base_revision,
            suggestion=suggestion,
        )

    def accept_suggestion(
        self,
        *,
        suggestion_id: str,
        principal: AuthenticatedPrincipal,
        payload: AcceptSuggestionRequest,
    ) -> AcceptSuggestionResponse:
        self._ensure_ai_role_allowed(principal)
        record = self._repository.accept_suggestion(
            suggestion_id=suggestion_id,
            user_id=principal.user_id,
            apply_range_start=payload.apply_to_range.start,
            apply_range_end=payload.apply_to_range.end,
        )
        return AcceptSuggestionResponse(
            suggestion_id=record.suggestion_id,
            outcome=SuggestionOutcome(record.outcome),
            applied=record.applied,
            new_revision=record.new_revision or 0,
        )

    def reject_suggestion(
        self,
        *,
        suggestion_id: str,
        principal: AuthenticatedPrincipal,
    ) -> RejectSuggestionResponse:
        self._ensure_ai_role_allowed(principal)
        record = self._repository.reject_suggestion(
            suggestion_id=suggestion_id,
            user_id=principal.user_id,
        )
        return RejectSuggestionResponse(
            suggestion_id=record.suggestion_id,
            outcome=SuggestionOutcome(record.outcome),
        )

    def apply_edited_suggestion(
        self,
        *,
        suggestion_id: str,
        principal: AuthenticatedPrincipal,
        payload: ApplyEditedSuggestionRequest,
    ) -> ApplyEditedSuggestionResponse:
        self._ensure_ai_role_allowed(principal)
        record = self._repository.apply_edited_suggestion(
            suggestion_id=suggestion_id,
            user_id=principal.user_id,
            edited_output=payload.edited_output,
            apply_range_start=payload.apply_to_range.start,
            apply_range_end=payload.apply_to_range.end,
        )
        return ApplyEditedSuggestionResponse(
            suggestion_id=record.suggestion_id,
            outcome=SuggestionOutcome(record.outcome),
            applied=record.applied,
            new_revision=record.new_revision or 0,
        )

    def _ensure_ai_role_allowed(self, principal: AuthenticatedPrincipal) -> None:
        if principal.role in {"owner", "editor"}:
            return

        raise AppError(
            status_code=HTTPStatus.FORBIDDEN,
            error_code=ErrorCode.AI_ROLE_NOT_ALLOWED,
            message="Your role is not allowed to use AI features.",
        )
