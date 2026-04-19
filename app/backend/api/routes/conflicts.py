from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse

from app.backend.api.deps import (
    get_ai_service,
    get_conflict_service,
    get_current_authenticated_user,
    get_current_principal,
    get_realtime_hub,
)
from app.backend.api.routes.ai import _stream_response
from app.backend.core.contracts import parse_resource_id, utc_now
from app.backend.core.security import AuthenticatedPrincipal
from app.backend.models.user import User
from app.backend.schemas.conflict import (
    DocumentConflictCreateRequest,
    DocumentConflictResolveRequest,
    DocumentConflictResolveResponse,
    DocumentConflictResponse,
)
from app.backend.services.ai.ai_service import AIService
from app.backend.services.conflict_service import ConflictService
from app.backend.services.realtime.collaboration_service import RealtimeHub

router = APIRouter(prefix="/documents/{documentId}/conflicts", tags=["conflicts"])


@router.get(
    "",
    response_model=list[DocumentConflictResponse],
    status_code=status.HTTP_200_OK,
)
def list_document_conflicts(
    documentId: str,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    service: Annotated[ConflictService, Depends(get_conflict_service)],
) -> list[DocumentConflictResponse]:
    return service.list_conflicts(
        document_id=documentId,
        current_user=current_user,
    )


@router.get(
    "/{conflictId}",
    response_model=DocumentConflictResponse,
    status_code=status.HTTP_200_OK,
)
def get_document_conflict(
    documentId: str,
    conflictId: int,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    service: Annotated[ConflictService, Depends(get_conflict_service)],
) -> DocumentConflictResponse:
    return service.get_conflict(
        document_id=documentId,
        conflict_id=conflictId,
        current_user=current_user,
    )


@router.post(
    "",
    response_model=DocumentConflictResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_document_conflict(
    documentId: str,
    payload: DocumentConflictCreateRequest,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    service: Annotated[ConflictService, Depends(get_conflict_service)],
    hub: Annotated[RealtimeHub, Depends(get_realtime_hub)],
) -> DocumentConflictResponse:
    conflict = service.create_conflict(
        document_id=documentId,
        current_user=current_user,
        payload=payload,
    )
    resolved_document_id = parse_resource_id(documentId, "doc")
    await hub.broadcast_json(
        document_id=resolved_document_id,
        payload={
            "type": "conflict_created",
            "conflict": jsonable_encoder(conflict),
        },
    )
    return conflict


@router.post(
    "/{conflictId}/resolve",
    response_model=DocumentConflictResolveResponse,
    status_code=status.HTTP_200_OK,
)
async def resolve_document_conflict(
    documentId: str,
    conflictId: int,
    payload: DocumentConflictResolveRequest,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    service: Annotated[ConflictService, Depends(get_conflict_service)],
    hub: Annotated[RealtimeHub, Depends(get_realtime_hub)],
) -> DocumentConflictResolveResponse:
    resolved_document_id = parse_resource_id(documentId, "doc")
    result = service.resolve_conflict(
        document_id=documentId,
        conflict_id=conflictId,
        current_user=current_user,
        payload=payload,
    )
    collab_state = await hub.reset_snapshot(
        document_id=resolved_document_id,
        content=result.content,
        line_spacing=result.line_spacing,
        updated_at=utc_now(),
    )
    await hub.broadcast_json(
        document_id=resolved_document_id,
        payload={
            "type": "content_updated",
            "document_id": resolved_document_id,
            "content": result.content,
            "line_spacing": result.line_spacing,
            "revision": result.response.new_revision,
            "latest_version_id": result.response.latest_version_id,
            "actor_user_id": current_user.id,
            "actor_display_name": current_user.display_name,
            "saved_at": collab_state["updated_at"],
            "collab_version": collab_state["version"],
            "collab_reset": True,
        },
    )
    await hub.broadcast_json(
        document_id=resolved_document_id,
        payload={
            "type": "conflict_resolved",
            "conflict_id": conflictId,
            "status": "resolved",
        },
    )
    return result.response.model_copy(update={"collab_version": collab_state["version"]})


@router.post(
    "/{conflictId}/ai-merge/stream",
    status_code=status.HTTP_202_ACCEPTED,
)
async def stream_conflict_ai_merge(
    documentId: str,
    conflictId: int,
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    conflict_service: Annotated[ConflictService, Depends(get_conflict_service)],
    ai_service: Annotated[AIService, Depends(get_ai_service)],
) -> StreamingResponse:
    ai_payload = conflict_service.build_conflict_merge_request(
        document_id=documentId,
        conflict_id=conflictId,
        principal=principal,
    )
    accepted_response, stream_handle = ai_service.start_stream_interaction(
        document_id=documentId,
        principal=principal,
        payload=ai_payload,
    )
    return _stream_response(
        accepted_response=accepted_response,
        stream_handle=stream_handle,
        request=request,
        principal=principal,
        service=ai_service,
    )
