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
    DocumentMetadataResponse,
    DocumentSummaryResponse,
    DocumentUpdate,
)
from app.backend.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["Documents"])


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
    summary="Create a document",
    description="Create a new document owned by the authenticated user.",
)
def create_document(
    payload: DocumentCreate,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    document_service: Annotated[DocumentService, Depends(get_document_service)],
) -> DocumentCreateResponse:
    return document_service.create_document(payload=payload, current_user=current_user)


@router.get(
    "",
    response_model=list[DocumentSummaryResponse],
    summary="List visible documents",
    description=(
        "Return documents owned by the authenticated user plus documents shared "
        "with them through existing permission records."
    ),
)
def list_documents(
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    document_service: Annotated[DocumentService, Depends(get_document_service)],
) -> list[DocumentSummaryResponse]:
    return document_service.list_documents(current_user=current_user)


@router.get(
    "/{documentId}",
    response_model=DocumentDetailResponse,
    summary="Get a single document",
    description="Return the current document state and metadata for a readable document.",
)
def get_document(
    documentId: str,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    document_service: Annotated[DocumentService, Depends(get_document_service)],
) -> DocumentDetailResponse:
    return document_service.get_document(
        document_id=documentId, current_user=current_user
    )


@router.patch(
    "/{documentId}",
    response_model=DocumentMetadataResponse,
    summary="Update document metadata",
    description="Update owner-managed document metadata such as title and AI availability.",
)
def update_document(
    documentId: str,
    payload: DocumentUpdate,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    document_service: Annotated[DocumentService, Depends(get_document_service)],
) -> DocumentMetadataResponse:
    return document_service.update_document(
        document_id=documentId,
        payload=payload,
        current_user=current_user,
    )


@router.delete(
    "/{documentId}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document",
    description="Permanently delete an owned document and its dependent records.",
)
def delete_document(
    documentId: str,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    document_service: Annotated[DocumentService, Depends(get_document_service)],
) -> Response:
    document_service.delete_document(document_id=documentId, current_user=current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
    "/{documentId}/content",
    response_model=DocumentContentSaveResponse,
    summary="Save document content",
    description=(
        "Persist document body changes and append a new version entry when the "
        "provided base revision matches the current revision."
    ),
)
def save_document_content(
    documentId: str,
    payload: DocumentContentSaveRequest,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    document_service: Annotated[DocumentService, Depends(get_document_service)],
) -> DocumentContentSaveResponse:
    return document_service.save_document_content(
        document_id=documentId,
        payload=payload,
        current_user=current_user,
    )


@router.post(
    "/{documentId}/export",
    response_model=DocumentExportResponse,
    summary="Export a document snapshot",
    description="Serialize the current document state into a requested export format.",
)
def export_document(
    documentId: str,
    payload: DocumentExportRequest,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    document_service: Annotated[DocumentService, Depends(get_document_service)],
) -> DocumentExportResponse:
    return document_service.export_document(
        document_id=documentId,
        payload=payload,
        current_user=current_user,
    )
