from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.backend.api.routes.auth import get_current_authenticated_user
from app.backend.core.database import get_db
from app.backend.models.user import User
from app.backend.repositories.document_repository import DocumentRepository
from app.backend.repositories.version_repository import VersionRepository
from app.backend.schemas.version import VersionResponse, VersionRestoreResponse
from app.backend.services.version_service import VersionService

router = APIRouter(prefix="/documents", tags=["versions"])


def get_version_service(db: Session = Depends(get_db)) -> VersionService:
    return VersionService(DocumentRepository(db), VersionRepository(db))


@router.get("/{documentId}/versions", response_model=List[VersionResponse])
def list_versions(
    documentId: int,
    current_user: User = Depends(get_current_authenticated_user),
    version_service: VersionService = Depends(get_version_service),
) -> List[VersionResponse]:
    return version_service.list_versions(document_id=documentId, current_user=current_user)


@router.post("/{documentId}/versions/{versionId}/restore", response_model=VersionRestoreResponse)
def restore_version(
    documentId: int,
    versionId: int,
    current_user: User = Depends(get_current_authenticated_user),
    version_service: VersionService = Depends(get_version_service),
) -> VersionRestoreResponse:
    return version_service.restore_version(
        document_id=documentId,
        version_id=versionId,
        current_user=current_user,
    )
