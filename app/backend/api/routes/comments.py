from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.backend.api.deps import (
    get_comment_service,
    get_current_authenticated_user,
    get_realtime_hub,
)
from app.backend.core.contracts import parse_resource_id
from app.backend.models.user import User
from app.backend.schemas.comment import (
    DocumentCommentCreateRequest,
    DocumentCommentResponse,
)
from app.backend.services.comment_service import CommentService
from app.backend.services.realtime.collaboration_service import RealtimeHub

router = APIRouter(prefix="/documents/{documentId}/comments", tags=["Comments"])


@router.get(
    "",
    response_model=list[DocumentCommentResponse],
    summary="List document comments",
    description="Return sidebar comments visible to the authenticated collaborator.",
)
def list_document_comments(
    documentId: str,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    comment_service: Annotated[CommentService, Depends(get_comment_service)],
) -> list[DocumentCommentResponse]:
    return comment_service.list_comments(
        document_id=documentId,
        current_user=current_user,
    )


@router.post(
    "",
    response_model=DocumentCommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a document comment",
    description="Create a new sidebar comment for a readable document.",
)
async def create_document_comment(
    documentId: str,
    payload: DocumentCommentCreateRequest,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    comment_service: Annotated[CommentService, Depends(get_comment_service)],
    hub: Annotated[RealtimeHub, Depends(get_realtime_hub)],
) -> DocumentCommentResponse:
    comment = comment_service.create_comment(
        document_id=documentId,
        payload=payload,
        current_user=current_user,
    )
    await hub.broadcast_json(
        document_id=comment.document_id,
        payload={
            "type": "comment_created",
            "comment": comment.model_dump(mode="json"),
        },
    )
    return comment


@router.post(
    "/{commentId}/resolve",
    response_model=DocumentCommentResponse,
    summary="Resolve a document comment",
    description="Mark a sidebar comment as resolved.",
)
async def resolve_document_comment(
    documentId: str,
    commentId: str,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    comment_service: Annotated[CommentService, Depends(get_comment_service)],
    hub: Annotated[RealtimeHub, Depends(get_realtime_hub)],
) -> DocumentCommentResponse:
    comment = comment_service.resolve_comment(
        document_id=documentId,
        comment_id=commentId,
        current_user=current_user,
    )
    await hub.broadcast_json(
        document_id=comment.document_id,
        payload={
            "type": "comment_resolved",
            "comment": comment.model_dump(mode="json"),
        },
    )
    return comment


@router.delete(
    "/{commentId}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document comment",
    description="Delete an existing sidebar comment.",
)
async def delete_document_comment(
    documentId: str,
    commentId: str,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    comment_service: Annotated[CommentService, Depends(get_comment_service)],
    hub: Annotated[RealtimeHub, Depends(get_realtime_hub)],
) -> Response:
    resolved_document_id = parse_resource_id(documentId, "doc")
    deleted_comment_id = comment_service.delete_comment(
        document_id=documentId,
        comment_id=commentId,
        current_user=current_user,
    )
    await hub.broadcast_json(
        document_id=resolved_document_id,
        payload={
            "type": "comment_deleted",
            "comment_id": deleted_comment_id,
        },
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
