from fastapi import status

from app.backend.core.contracts import parse_resource_id, prefixed_id, utc_z
from app.backend.core.errors import ApiError
from app.backend.models.user import User
from app.backend.repositories.document_repository import DocumentRepository
from app.backend.repositories.permission_repository import PermissionRepository
from app.backend.repositories.user_repository import UserRepository
from app.backend.schemas.permission import PermissionGrantRequest, PermissionResponse
from app.backend.services.access_service import DocumentAccessService


class PermissionService:
    def __init__(
        self,
        document_repository: DocumentRepository,
        permission_repository: PermissionRepository,
        user_repository: UserRepository,
    ) -> None:
        self.document_repository = document_repository
        self.permission_repository = permission_repository
        self.user_repository = user_repository
        self.access_service = DocumentAccessService(
            document_repository,
            permission_repository,
        )

    def grant_permission(
        self,
        *,
        document_id: str | int,
        payload: PermissionGrantRequest,
        current_user: User,
    ) -> PermissionResponse:
        access = self.access_service.require_owner_access(
            document_id=document_id,
            user_id=current_user.id,
        )

        if payload.grantee_type != "user":
            raise ApiError(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code="VALIDATION_ERROR",
                message="Only grantee_type 'user' is supported.",
            )

        role = self.access_service.validate_role(payload.role)
        grantee_user_id = parse_resource_id(payload.user_id, "usr")
        grantee = self.user_repository.get_by_id(grantee_user_id)
        if grantee is None:
            raise ApiError(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code="VALIDATION_ERROR",
                message="Target user not found.",
            )

        permission = self.permission_repository.get_by_document_and_user(
            document_id=access.document.id,
            user_id=grantee_user_id,
        )
        if permission is None:
            permission = self.permission_repository.create(
                document_id=access.document.id,
                user_id=grantee_user_id,
                grantee_type=payload.grantee_type,
                role=role,
                ai_allowed=payload.ai_allowed,
            )
        else:
            permission = self.permission_repository.update(
                permission,
                grantee_type=payload.grantee_type,
                role=role,
                ai_allowed=payload.ai_allowed,
            )

        self.permission_repository.db.commit()
        return self._to_permission_response(permission)

    def revoke_permission(
        self,
        *,
        document_id: str | int,
        permission_id: str | int,
        current_user: User,
    ) -> None:
        access = self.access_service.require_owner_access(
            document_id=document_id,
            user_id=current_user.id,
        )

        permission = self.permission_repository.get_by_id(
            parse_resource_id(permission_id, "perm")
        )
        if permission is None or permission.document_id != access.document.id:
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
