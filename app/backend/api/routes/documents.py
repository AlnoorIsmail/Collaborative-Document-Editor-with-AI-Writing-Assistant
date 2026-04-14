from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.backend.api.deps import get_current_authenticated_user
from app.backend.core.database import get_db
from app.backend.models.user import User
from app.backend.repositories.document_repository import DocumentRepository
from app.backend.repositories.permission_repository import PermissionRepository
from app.backend.repositories.version_repository import VersionRepository
from app.backend.schemas.document import (
    DocumentContentSaveRequest,
    DocumentContentSaveResponse,
    DocumentCreate,
    DocumentCreateResponse,
    DocumentDetailResponse,
    DocumentExportRequest,
    DocumentExportResponse,
    DocumentListItemResponse,
    DocumentUpdate,
    DocumentUpdateResponse,
)
from app.backend.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])


def get_document_service(db: Session = Depends(get_db)) -> DocumentService:
    return DocumentService(
        DocumentRepository(db),
        VersionRepository(db),
        PermissionRepository(db),
    )


@router.post(
    "",
    response_model=DocumentCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create document",
    description="Create a new document owned by the authenticated user.",
)
def create_document(
    payload: DocumentCreate,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentCreateResponse:
    return document_service.create_document(payload=payload, current_user=current_user)


@router.get(
    "",
    response_model=list[DocumentListItemResponse],
    summary="List documents",
    description="List documents owned by or explicitly shared with the authenticated user.",
)
def list_documents(
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    document_service: DocumentService = Depends(get_document_service),
) -> list[DocumentListItemResponse]:
    return document_service.list_documents(current_user=current_user)


@router.get(
    "/{document_id}",
    response_model=DocumentDetailResponse,
    summary="Get document",
    description="Return the current state and metadata for a single visible document.",
)
def get_document(
    document_id: str,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentDetailResponse:
    return document_service.get_document(
        document_id=document_id,
        current_user=current_user,
    )


@router.patch(
    "/{document_id}",
    response_model=DocumentUpdateResponse,
    summary="Update document",
    description="Update document metadata and optionally the full content body. Content updates create a new version entry.",
)
def update_document(
    document_id: str,
    payload: DocumentUpdate,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentUpdateResponse:
    return document_service.update_document(
        document_id=document_id,
        payload=payload,
        current_user=current_user,
    )


@router.patch(
    "/{document_id}/content",
    response_model=DocumentContentSaveResponse,
    summary="Save document content",
    description="Persist new document content as an explicit versioned save operation.",
)
def save_document_content(
    document_id: str,
    payload: DocumentContentSaveRequest,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentContentSaveResponse:
    return document_service.save_document_content(
        document_id=document_id,
        payload=payload,
        current_user=current_user,
    )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete document",
    description="Delete a document owned by the authenticated user.",
)
def delete_document(
    document_id: str,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    document_service: DocumentService = Depends(get_document_service),
) -> Response:
    document_service.delete_document(
        document_id=document_id,
        current_user=current_user,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{document_id}/export",
    response_model=DocumentExportResponse,
    summary="Export document",
    description="Serialize a document into a client-friendly export format.",
)
def export_document(
    document_id: str,
    payload: DocumentExportRequest,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentExportResponse:
    return document_service.export_document(
        document_id=document_id,
        payload=payload,
        current_user=current_user,
    )
