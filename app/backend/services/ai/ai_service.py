"""Service layer for suggestion-based AI endpoints."""

from http import HTTPStatus

from app.backend.core.contracts import parse_resource_id
from app.backend.core.errors import ApiError, AppError
from app.backend.core.security import AuthenticatedPrincipal
from app.backend.integrations.ai_provider import (
    AIProviderClient,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
)
from app.backend.repositories.ai import AIRepository
from app.backend.repositories.document_repository import DocumentRepository
from app.backend.repositories.permission_repository import PermissionRepository
from app.backend.repositories.version_repository import VersionRepository
from app.backend.schemas.ai import (
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
from app.backend.schemas.common import ErrorCode, TextRange
from app.backend.services.access_service import DocumentAccessService
from app.backend.services.ai.prompt_builder import PromptTemplateRenderer

AI_INTERACTION_QUOTA_PER_DOCUMENT_USER = 25


class AIService:
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

        try:
            prompt = self._prompt_renderer.render(payload)
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

        record = self._repository.create_interaction(
            document_id=access.document.id,
            user_id=user_id,
            feature_type=payload.feature_type,
            scope_type=payload.scope_type,
            base_revision=payload.base_revision,
            generated_output=suggestion.generated_output,
            model_name=suggestion.model_name,
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

        outcome = self._repository.accept_suggestion(
            suggestion_id=suggestion_id,
            user_id=user_id,
            apply_range_start=payload.apply_to_range.start,
            apply_range_end=payload.apply_to_range.end,
        )
        updated_document = self._apply_replacement(
            document=access.document,
            apply_to_range=payload.apply_to_range,
            replacement=record.suggestion.generated_output,
        )
        version = self._create_version(document=updated_document, user_id=user_id)
        self._document_repository.db.commit()
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

        outcome = self._repository.apply_edited_suggestion(
            suggestion_id=suggestion_id,
            user_id=user_id,
            edited_output=payload.edited_output,
            apply_range_start=payload.apply_to_range.start,
            apply_range_end=payload.apply_to_range.end,
        )
        updated_document = self._apply_replacement(
            document=access.document,
            apply_to_range=payload.apply_to_range,
            replacement=payload.edited_output,
        )
        version = self._create_version(document=updated_document, user_id=user_id)
        self._document_repository.db.commit()
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
            created_by=user_id,
            is_restore_version=False,
        )
        self._document_repository.update(document, latest_version_id=version.id)
        return version
