"""Routes for suggestion-based AI interaction workflows."""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse

from app.backend.api.deps import get_ai_service, get_current_principal
from app.backend.core.security import AuthenticatedPrincipal
from app.backend.integrations.ai_provider import (
    GeneratedSuggestionChunk,
    GeneratedSuggestionComplete,
)
from app.backend.schemas.ai import (
    AIChatMessageStreamRequest,
    AIChatThreadClearResponse,
    AIChatThreadEntryResponse,
    AIInteractionAcceptedResponse,
    AIInteractionCancelResponse,
    AIInteractionCreateRequest,
    AIInteractionDetailResponse,
    AIInteractionHistoryItem,
    AcceptSuggestionRequest,
    AcceptSuggestionResponse,
    ApplyEditedSuggestionRequest,
    ApplyEditedSuggestionResponse,
    RejectSuggestionResponse,
)
from app.backend.services.ai.ai_service import AIService

router = APIRouter(tags=["ai"])


def _encode_sse(event: str, data: object) -> str:
    payload = json.dumps(jsonable_encoder(data))
    return f"event: {event}\ndata: {payload}\n\n"

@router.post(
    "/documents/{documentId}/ai/interactions",
    response_model=AIInteractionAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue an AI suggestion interaction",
    description=(
        "Create an AI interaction record for document or selected-text scope and "
        "return the accepted interaction metadata."
    ),
)
def create_ai_interaction(
    documentId: str,
    payload: AIInteractionCreateRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    service: Annotated[AIService, Depends(get_ai_service)],
) -> AIInteractionAcceptedResponse:
    return service.create_interaction(
        document_id=documentId,
        principal=principal,
        payload=payload,
    )


@router.post(
    "/documents/{documentId}/ai/interactions/stream",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Stream an AI suggestion interaction",
    description=(
        "Start an AI suggestion request and stream incremental Server-Sent Events "
        "for metadata, text chunks, completion, cancellation, or errors."
    ),
)
async def stream_ai_interaction(
    documentId: str,
    payload: AIInteractionCreateRequest,
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    service: Annotated[AIService, Depends(get_ai_service)],
) -> StreamingResponse:
    accepted_response, stream_handle = service.start_stream_interaction(
        document_id=documentId,
        principal=principal,
        payload=payload,
    )
    return _stream_response(
        accepted_response=accepted_response,
        stream_handle=stream_handle,
        request=request,
        principal=principal,
        service=service,
    )


@router.get(
    "/documents/{documentId}/ai/chat/thread",
    response_model=list[AIChatThreadEntryResponse],
    status_code=status.HTTP_200_OK,
    summary="List the document AI chat thread",
    description=(
        "Return the authenticated user's persisted AI chat sidebar thread for the "
        "requested document."
    ),
)
def get_ai_chat_thread(
    documentId: str,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    service: Annotated[AIService, Depends(get_ai_service)],
) -> list[AIChatThreadEntryResponse]:
    return service.list_chat_thread(
        document_id=documentId,
        principal=principal,
    )


@router.delete(
    "/documents/{documentId}/ai/chat/thread",
    response_model=AIChatThreadClearResponse,
    status_code=status.HTTP_200_OK,
    summary="Clear the document AI chat thread",
    description=(
        "Delete the authenticated user's AI chat thread entries and related "
        "interaction history for the requested document."
    ),
)
def clear_ai_chat_thread(
    documentId: str,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    service: Annotated[AIService, Depends(get_ai_service)],
) -> AIChatThreadClearResponse:
    return service.clear_chat_thread(
        document_id=documentId,
        principal=principal,
    )


@router.post(
    "/documents/{documentId}/ai/chat/messages/stream",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Stream an AI chat reply",
    description=(
        "Send a sidebar chat message to the AI assistant and stream the reply back "
        "over Server-Sent Events."
    ),
)
async def stream_ai_chat_message(
    documentId: str,
    payload: AIChatMessageStreamRequest,
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    service: Annotated[AIService, Depends(get_ai_service)],
) -> StreamingResponse:
    accepted_response, stream_handle = service.start_stream_chat_message(
        document_id=documentId,
        principal=principal,
        payload=payload,
    )
    return _stream_response(
        accepted_response=accepted_response,
        stream_handle=stream_handle,
        request=request,
        principal=principal,
        service=service,
    )


def _stream_response(
    *,
    accepted_response: AIInteractionAcceptedResponse,
    stream_handle,
    request: Request,
    principal: AuthenticatedPrincipal,
    service: AIService,
) -> StreamingResponse:

    async def event_stream():
        interaction_id = accepted_response.interaction_id
        accumulated_output = ""
        model_name: str | None = None
        usage = None

        try:
            yield _encode_sse("meta", accepted_response)

            async for provider_event in stream_handle.stream:
                if await request.is_disconnected():
                    service.fail_stream_interaction(
                        interaction_id=interaction_id,
                        principal=principal,
                        generated_output=accumulated_output,
                    )
                    return

                if service.is_stream_canceled(interaction_id=interaction_id):
                    canceled = service.fail_stream_interaction(
                        interaction_id=interaction_id,
                        principal=principal,
                        generated_output=accumulated_output,
                    )
                    yield _encode_sse("cancelled", canceled)
                    return

                if isinstance(provider_event, GeneratedSuggestionChunk):
                    accumulated_output += provider_event.delta
                    service.update_stream_interaction_output(
                        interaction_id=interaction_id,
                        principal=principal,
                        generated_output=accumulated_output,
                    )
                    yield _encode_sse(
                        "chunk",
                        {
                            "interaction_id": interaction_id,
                            "delta": provider_event.delta,
                            "output": accumulated_output,
                        },
                    )
                    continue

                if isinstance(provider_event, GeneratedSuggestionComplete):
                    model_name = provider_event.model_name
                    usage = provider_event.usage

            detail = service.complete_stream_interaction(
                interaction_id=interaction_id,
                principal=principal,
                generated_output=accumulated_output,
                model_name=model_name,
                usage=usage,
            )
            yield _encode_sse("complete", detail)
        except Exception as exc:
            service.fail_stream_interaction(
                interaction_id=accepted_response.interaction_id,
                principal=principal,
                generated_output=accumulated_output,
            )
            yield _encode_sse(
                "error",
                {
                    "interaction_id": accepted_response.interaction_id,
                    "message": str(exc) or "AI streaming failed.",
                },
            )

    return StreamingResponse(
        event_stream(),
        status_code=status.HTTP_202_ACCEPTED,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/documents/{documentId}/ai/interactions",
    response_model=list[AIInteractionHistoryItem],
    status_code=status.HTTP_200_OK,
    summary="List document AI interaction history",
    description=(
        "Return document-level AI interaction history items, including feature type, "
        "scope, status, and token totals when available."
    ),
)
def list_ai_interactions(
    documentId: str,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    service: Annotated[AIService, Depends(get_ai_service)],
) -> list[AIInteractionHistoryItem]:
    return service.list_interactions(
        document_id=documentId,
        principal=principal,
    )


@router.get(
    "/ai/interactions/{interactionId}",
    response_model=AIInteractionDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get AI interaction details",
    description=(
        "Return the full persisted AI interaction record, including prompt context, "
        "review state, and any stored suggestion payload."
    ),
)
def get_ai_interaction(
    interactionId: str,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    service: Annotated[AIService, Depends(get_ai_service)],
) -> AIInteractionDetailResponse:
    return service.get_interaction(
        interaction_id=interactionId,
        principal=principal,
    )


@router.post(
    "/ai/interactions/{interactionId}/cancel",
    response_model=AIInteractionCancelResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel a streaming AI interaction",
    description=(
        "Request cancellation for an in-progress streaming AI interaction and "
        "return the updated interaction status."
    ),
)
def cancel_ai_interaction(
    interactionId: str,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    service: Annotated[AIService, Depends(get_ai_service)],
) -> AIInteractionCancelResponse:
    return service.cancel_stream_interaction(
        interaction_id=interactionId,
        principal=principal,
    )


@router.post(
    "/ai/suggestions/{suggestionId}/accept",
    response_model=AcceptSuggestionResponse,
    status_code=status.HTTP_200_OK,
    summary="Accept an AI suggestion",
    description=(
        "Apply a stored AI suggestion into the requested document range and record "
        "an accepted review outcome."
    ),
)
def accept_ai_suggestion(
    suggestionId: str,
    payload: AcceptSuggestionRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    service: Annotated[AIService, Depends(get_ai_service)],
) -> AcceptSuggestionResponse:
    return service.accept_suggestion(
        suggestion_id=suggestionId,
        principal=principal,
        payload=payload,
    )


@router.post(
    "/ai/suggestions/{suggestionId}/reject",
    response_model=RejectSuggestionResponse,
    status_code=status.HTTP_200_OK,
    summary="Reject an AI suggestion",
    description=(
        "Reject a stored AI suggestion without changing document content while "
        "recording the review outcome."
    ),
)
def reject_ai_suggestion(
    suggestionId: str,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    service: Annotated[AIService, Depends(get_ai_service)],
) -> RejectSuggestionResponse:
    return service.reject_suggestion(
        suggestion_id=suggestionId,
        principal=principal,
    )


@router.post(
    "/ai/suggestions/{suggestionId}/apply-edited",
    response_model=ApplyEditedSuggestionResponse,
    status_code=status.HTTP_200_OK,
    summary="Apply an edited AI suggestion",
    description=(
        "Apply a human-edited variant of a stored AI suggestion into the document "
        "and record the modified review outcome."
    ),
)
def apply_edited_ai_suggestion(
    suggestionId: str,
    payload: ApplyEditedSuggestionRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    service: Annotated[AIService, Depends(get_ai_service)],
) -> ApplyEditedSuggestionResponse:
    return service.apply_edited_suggestion(
        suggestion_id=suggestionId,
        principal=principal,
        payload=payload,
    )
