from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.backend.api.routes.auth import get_current_authenticated_user
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
    DocumentUpdate,
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
    "", response_model=DocumentCreateResponse, status_code=status.HTTP_201_CREATED
)
def create_document(
    payload: DocumentCreate,
    current_user: User = Depends(get_current_authenticated_user),
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentCreateResponse:
    return document_service.create_document(payload=payload, current_user=current_user)


@router.get("/{documentId}", response_model=DocumentDetailResponse)
def get_document(
    documentId: str,
    current_user: User = Depends(get_current_authenticated_user),
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentDetailResponse:
    return document_service.get_document(
        document_id=documentId, current_user=current_user
    )


@router.patch("/{documentId}", response_model=DocumentMetadataResponse)
def update_document(
    documentId: str,
    payload: DocumentUpdate,
    current_user: User = Depends(get_current_authenticated_user),
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentMetadataResponse:
    return document_service.update_document(
        document_id=documentId,
        payload=payload,
        current_user=current_user,
    )


@router.patch("/{documentId}/content", response_model=DocumentContentSaveResponse)
def save_document_content(
    documentId: str,
    payload: DocumentContentSaveRequest,
    current_user: User = Depends(get_current_authenticated_user),
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentContentSaveResponse:
    return document_service.save_document_content(
        document_id=documentId,
        payload=payload,
        current_user=current_user,
    )


@router.post("/{documentId}/export", response_model=DocumentExportResponse)
def export_document(
    documentId: str,
    payload: DocumentExportRequest,
    current_user: User = Depends(get_current_authenticated_user),
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentExportResponse:
    return document_service.export_document(
        document_id=documentId,
        payload=payload,
        current_user=current_user,
    )
