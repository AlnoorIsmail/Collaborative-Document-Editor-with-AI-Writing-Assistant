from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.backend.api.deps import get_current_authenticated_user
from app.backend.core.database import get_db
from app.backend.models.user import User
from app.backend.repositories.document_repository import DocumentRepository
from app.backend.repositories.permission_repository import PermissionRepository
from app.backend.repositories.version_repository import VersionRepository
from app.backend.schemas.version import VersionResponse, VersionRestoreResponse
from app.backend.services.version_service import VersionService

router = APIRouter(prefix="/documents", tags=["versions"])


def get_version_service(db: Session = Depends(get_db)) -> VersionService:
    return VersionService(
        DocumentRepository(db),
        VersionRepository(db),
        PermissionRepository(db),
    )


@router.get(
    "/{document_id}/versions",
    response_model=List[VersionResponse],
    summary="List document versions",
    description="Return version history entries for a document visible to the authenticated user.",
)
def list_versions(
    document_id: str,
    current_user: User = Depends(get_current_authenticated_user),
    version_service: VersionService = Depends(get_version_service),
) -> List[VersionResponse]:
    return version_service.list_versions(
        document_id=document_id,
        current_user=current_user,
    )


@router.post(
    "/{document_id}/versions/{version_id}/restore",
    response_model=VersionRestoreResponse,
    summary="Restore a document version",
    description="Restore a historical snapshot by creating a new current version entry.",
)
def restore_version(
    document_id: str,
    version_id: str,
    current_user: User = Depends(get_current_authenticated_user),
    version_service: VersionService = Depends(get_version_service),
) -> VersionRestoreResponse:
    return version_service.restore_version(
        document_id=document_id,
        version_id=version_id,
        current_user=current_user,
    )
