from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.backend.api.routes.auth import get_current_authenticated_user
from app.backend.core.database import get_db
from app.backend.models.user import User
from app.backend.repositories.document_repository import DocumentRepository
from app.backend.repositories.permission_repository import PermissionRepository
from app.backend.repositories.user_repository import UserRepository
from app.backend.schemas.permission import PermissionGrantRequest, PermissionResponse
from app.backend.services.permission_service import PermissionService

router = APIRouter(prefix="/documents", tags=["permissions"])


def get_permission_service(db: Session = Depends(get_db)) -> PermissionService:
    return PermissionService(
        DocumentRepository(db),
        PermissionRepository(db),
        UserRepository(db),
    )


@router.post("/{documentId}/permissions", response_model=PermissionResponse, status_code=status.HTTP_201_CREATED)
def grant_permission(
    documentId: int,
    payload: PermissionGrantRequest,
    current_user: User = Depends(get_current_authenticated_user),
    permission_service: PermissionService = Depends(get_permission_service),
) -> PermissionResponse:
    return permission_service.grant_permission(
        document_id=documentId,
        payload=payload,
        current_user=current_user,
    )


@router.delete("/{documentId}/permissions/{permissionId}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_permission(
    documentId: int,
    permissionId: int,
    current_user: User = Depends(get_current_authenticated_user),
    permission_service: PermissionService = Depends(get_permission_service),
) -> Response:
    permission_service.revoke_permission(
        document_id=documentId,
        permission_id=permissionId,
        current_user=current_user,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
