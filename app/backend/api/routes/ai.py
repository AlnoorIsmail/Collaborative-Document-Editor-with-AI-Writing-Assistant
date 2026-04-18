"""Routes for suggestion-based AI interaction workflows."""

import asyncio
import json
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse

from app.backend.api.deps import get_ai_service, get_current_principal
from app.backend.core.security import AuthenticatedPrincipal
from app.backend.schemas.ai import (
    AIChatMessageStreamRequest,
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

STREAM_CHUNK_SIZE = 48
STREAM_CHUNK_DELAY_SECONDS = 0.04


def _encode_sse(event: str, data: object) -> str:
    payload = json.dumps(jsonable_encoder(data))
    return f"event: {event}\ndata: {payload}\n\n"


def _chunk_text(text: str, chunk_size: int = STREAM_CHUNK_SIZE) -> list[str]:
    if not text:
        return [""]

    chunks: list[str] = []
    cursor = 0
    while cursor < len(text):
        window = text[cursor : cursor + chunk_size]
        if cursor + chunk_size >= len(text):
            chunks.append(window)
            break

        split_at = window.rfind(" ")
        if split_at <= 0:
            split_at = len(window)
        chunks.append(text[cursor : cursor + split_at])
        cursor += split_at
        while cursor < len(text) and text[cursor] == " ":
            cursor += 1

    return chunks


@router.post(
    "/documents/{documentId}/ai/interactions",
    response_model=AIInteractionAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
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
)
async def stream_ai_interaction(
    documentId: str,
    payload: AIInteractionCreateRequest,
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    service: Annotated[AIService, Depends(get_ai_service)],
) -> StreamingResponse:
    accepted_response, generated_output = service.start_stream_interaction(
        document_id=documentId,
        principal=principal,
        payload=payload,
    )
    return _stream_response(
        accepted_response=accepted_response,
        generated_output=generated_output,
        request=request,
        principal=principal,
        service=service,
    )


@router.get(
    "/documents/{documentId}/ai/chat/thread",
    response_model=list[AIChatThreadEntryResponse],
    status_code=status.HTTP_200_OK,
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


@router.post(
    "/documents/{documentId}/ai/chat/messages/stream",
    status_code=status.HTTP_202_ACCEPTED,
)
async def stream_ai_chat_message(
    documentId: str,
    payload: AIChatMessageStreamRequest,
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    service: Annotated[AIService, Depends(get_ai_service)],
) -> StreamingResponse:
    accepted_response, generated_output = service.start_stream_chat_message(
        document_id=documentId,
        principal=principal,
        payload=payload,
    )
    return _stream_response(
        accepted_response=accepted_response,
        generated_output=generated_output,
        request=request,
        principal=principal,
        service=service,
    )


def _stream_response(
    *,
    accepted_response: AIInteractionAcceptedResponse,
    generated_output: str,
    request: Request,
    principal: AuthenticatedPrincipal,
    service: AIService,
) -> StreamingResponse:

    async def event_stream():
        interaction_id = accepted_response.interaction_id
        accumulated_output = ""

        try:
            yield _encode_sse("meta", accepted_response)

            for chunk in _chunk_text(generated_output):
                if await request.is_disconnected():
                    service.fail_stream_interaction(
                        interaction_id=interaction_id,
                        principal=principal,
                    )
                    return

                if service.is_stream_canceled(interaction_id=interaction_id):
                    canceled = service.fail_stream_interaction(
                        interaction_id=interaction_id,
                        principal=principal,
                    )
                    yield _encode_sse("cancelled", canceled)
                    return

                accumulated_output += chunk
                yield _encode_sse(
                    "chunk",
                    {
                        "interaction_id": interaction_id,
                        "delta": chunk,
                        "output": accumulated_output,
                    },
                )
                await asyncio.sleep(STREAM_CHUNK_DELAY_SECONDS)

            detail = service.complete_stream_interaction(
                interaction_id=interaction_id,
                principal=principal,
            )
            yield _encode_sse("complete", detail)
        except Exception as exc:
            service.fail_stream_interaction(
                interaction_id=accepted_response.interaction_id,
                principal=principal,
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
