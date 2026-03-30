"""Routes for suggestion-based AI interaction workflows."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from apps.backend.api.deps import get_ai_service, get_current_principal
from apps.backend.core.security import AuthenticatedPrincipal
from apps.backend.schemas.ai import (
    AIInteractionAcceptedResponse,
    AIInteractionCreateRequest,
    AIInteractionDetailResponse,
    AIInteractionHistoryItem,
    AcceptSuggestionRequest,
    AcceptSuggestionResponse,
    ApplyEditedSuggestionRequest,
    ApplyEditedSuggestionResponse,
    RejectSuggestionResponse,
)
from apps.backend.services.ai.ai_service import AIService

router = APIRouter(tags=["ai"])


@router.post(
    "/documents/{document_id}/ai/interactions",
    response_model=AIInteractionAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_ai_interaction(
    document_id: str,
    payload: AIInteractionCreateRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    service: Annotated[AIService, Depends(get_ai_service)],
) -> AIInteractionAcceptedResponse:
    return service.create_interaction(
        document_id=document_id,
        principal=principal,
        payload=payload,
    )


@router.get(
    "/documents/{document_id}/ai/interactions",
    response_model=list[AIInteractionHistoryItem],
    status_code=status.HTTP_200_OK,
)
def list_ai_interactions(
    document_id: str,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    service: Annotated[AIService, Depends(get_ai_service)],
) -> list[AIInteractionHistoryItem]:
    return service.list_interactions(
        document_id=document_id,
        principal=principal,
    )


@router.get(
    "/ai/interactions/{interaction_id}",
    response_model=AIInteractionDetailResponse,
    status_code=status.HTTP_200_OK,
)
def get_ai_interaction(
    interaction_id: str,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    service: Annotated[AIService, Depends(get_ai_service)],
) -> AIInteractionDetailResponse:
    return service.get_interaction(
        interaction_id=interaction_id,
        principal=principal,
    )


@router.post(
    "/ai/suggestions/{suggestion_id}/accept",
    response_model=AcceptSuggestionResponse,
    status_code=status.HTTP_200_OK,
)
def accept_ai_suggestion(
    suggestion_id: str,
    payload: AcceptSuggestionRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    service: Annotated[AIService, Depends(get_ai_service)],
) -> AcceptSuggestionResponse:
    return service.accept_suggestion(
        suggestion_id=suggestion_id,
        principal=principal,
        payload=payload,
    )


@router.post(
    "/ai/suggestions/{suggestion_id}/reject",
    response_model=RejectSuggestionResponse,
    status_code=status.HTTP_200_OK,
)
def reject_ai_suggestion(
    suggestion_id: str,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    service: Annotated[AIService, Depends(get_ai_service)],
) -> RejectSuggestionResponse:
    return service.reject_suggestion(
        suggestion_id=suggestion_id,
        principal=principal,
    )


@router.post(
    "/ai/suggestions/{suggestion_id}/apply-edited",
    response_model=ApplyEditedSuggestionResponse,
    status_code=status.HTTP_200_OK,
)
def apply_edited_ai_suggestion(
    suggestion_id: str,
    payload: ApplyEditedSuggestionRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    service: Annotated[AIService, Depends(get_ai_service)],
) -> ApplyEditedSuggestionResponse:
    return service.apply_edited_suggestion(
        suggestion_id=suggestion_id,
        principal=principal,
        payload=payload,
    )
