from typing import List

from typing import Annotated, List

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

router = APIRouter(prefix="/documents", tags=["Versions"])


def get_version_service(db: Session = Depends(get_db)) -> VersionService:
    return VersionService(
        DocumentRepository(db),
        VersionRepository(db),
        PermissionRepository(db),
    )


@router.get(
    "/{documentId}/versions",
    response_model=List[VersionResponse],
    summary="List document versions",
    description="Return append-only version history metadata for a readable document.",
)
def list_versions(
    documentId: str,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    version_service: Annotated[VersionService, Depends(get_version_service)],
) -> List[VersionResponse]:
    return version_service.list_versions(
        document_id=documentId, current_user=current_user
    )


@router.post(
    "/{documentId}/versions/{versionId}/restore",
    response_model=VersionRestoreResponse,
    summary="Restore a historical version",
    description=(
        "Restore a previous snapshot by creating a brand-new current version entry "
        "without deleting existing history."
    ),
)
def restore_version(
    documentId: str,
    versionId: str,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    version_service: Annotated[VersionService, Depends(get_version_service)],
) -> VersionRestoreResponse:
    return version_service.restore_version(
        document_id=documentId,
        version_id=versionId,
        current_user=current_user,
    )
