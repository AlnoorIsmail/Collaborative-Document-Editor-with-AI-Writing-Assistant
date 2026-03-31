from fastapi import status

from app.backend.core.contracts import parse_prefixed_id, prefixed_id, utc_z
from app.backend.core.errors import ApiError
from app.backend.models.user import User
from app.backend.repositories.document_repository import DocumentRepository
from app.backend.repositories.permission_repository import PermissionRepository
from app.backend.repositories.user_repository import UserRepository
from app.backend.schemas.permission import PermissionGrantRequest, PermissionResponse
from app.backend.services.document_service import DocumentService


class PermissionService:
    def __init__(
        self,
        document_repository: DocumentRepository,
        permission_repository: PermissionRepository,
        user_repository: UserRepository,
    ):
        self.document_repository = document_repository
        self.permission_repository = permission_repository
        self.user_repository = user_repository
        self.document_service = DocumentService(document_repository, None)

    def grant_permission(
        self,
        *,
        document_id: int,
        payload: PermissionGrantRequest,
        current_user: User,
    ) -> PermissionResponse:
        document = self.document_repository.get_by_id(document_id)
        self.document_service._ensure_owner_access(
            document=document, current_user=current_user
        )

        if payload.grantee_type != "user":
            raise ApiError(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code="VALIDATION_ERROR",
                message="Only grantee_type 'user' is supported.",
            )

        grantee_user_id = parse_prefixed_id(payload.user_id, "usr")
        grantee = self.user_repository.get_by_id(grantee_user_id)
        if grantee is None:
            raise ApiError(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code="VALIDATION_ERROR",
                message="Target user not found.",
            )

        permission = self.permission_repository.get_by_document_and_user(
            document_id=document.id,
            user_id=grantee_user_id,
        )
        if permission is None:
            permission = self.permission_repository.create(
                document_id=document.id,
                user_id=grantee_user_id,
                grantee_type=payload.grantee_type,
                role=payload.role,
                ai_allowed=payload.ai_allowed,
            )
        else:
            permission = self.permission_repository.update(
                permission,
                grantee_type=payload.grantee_type,
                role=payload.role,
                ai_allowed=payload.ai_allowed,
            )

        self.permission_repository.db.commit()
        return self._to_permission_response(permission)

    def revoke_permission(
        self, *, document_id: int, permission_id: int, current_user: User
    ) -> None:
        document = self.document_repository.get_by_id(document_id)
        self.document_service._ensure_owner_access(
            document=document, current_user=current_user
        )

        permission = self.permission_repository.get_by_id(permission_id)
        if permission is None or permission.document_id != document.id:
            raise ApiError(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code="VALIDATION_ERROR",
                message="Permission not found.",
            )

        self.permission_repository.delete(permission)
        self.permission_repository.db.commit()

    def _to_permission_response(self, permission) -> PermissionResponse:
        return PermissionResponse(
            permission_id=prefixed_id("perm", permission.id),
            document_id=prefixed_id("doc", permission.document_id),
            grantee_type=permission.grantee_type,
            user_id=prefixed_id("usr", permission.user_id),
            role=permission.role,
            ai_allowed=permission.ai_allowed,
            granted_at=utc_z(permission.created_at),
        )
