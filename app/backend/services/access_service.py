from dataclasses import dataclass

from fastapi import status

from app.backend.core.contracts import parse_resource_id
from app.backend.core.errors import ApiError
from app.backend.models.document import Document
from app.backend.repositories.document_repository import DocumentRepository
from app.backend.repositories.permission_repository import PermissionRepository

VALID_DOCUMENT_ROLES = {"owner", "editor", "commenter", "viewer"}
EDIT_ROLES = {"owner", "editor"}
READ_ROLES = VALID_DOCUMENT_ROLES


@dataclass(frozen=True)
class DocumentAccess:
    document: Document
    role: str
    user_id: int
    ai_allowed: bool
    current_revision: int

    @property
    def can_read(self) -> bool:
        return self.role in READ_ROLES

    @property
    def can_edit(self) -> bool:
        return self.role in EDIT_ROLES

    @property
    def can_manage(self) -> bool:
        return self.role == "owner"

    @property
    def can_restore_versions(self) -> bool:
        return self.role in EDIT_ROLES

    @property
    def can_use_ai(self) -> bool:
        return self.role in EDIT_ROLES and self.ai_allowed


class DocumentAccessService:
    def __init__(
        self,
        document_repository: DocumentRepository,
        permission_repository: PermissionRepository,
    ) -> None:
        self.document_repository = document_repository
        self.permission_repository = permission_repository

    def resolve_access(self, *, document_id: str | int, user_id: str | int) -> DocumentAccess:
        resolved_document_id = parse_resource_id(document_id, "doc")
        resolved_user_id = parse_resource_id(user_id, "usr")

        document = self.document_repository.get_by_id(resolved_document_id)
        if document is None:
            raise ApiError(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code="DOCUMENT_NOT_FOUND",
                message="Document not found.",
            )

        if document.owner_id == resolved_user_id:
            return DocumentAccess(
                document=document,
                role="owner",
                user_id=resolved_user_id,
                ai_allowed=bool(document.ai_enabled),
                current_revision=self._current_revision(document),
            )

        permission = self.permission_repository.get_by_document_and_user(
            document_id=document.id,
            user_id=resolved_user_id,
        )
        if permission is None:
            raise ApiError(
                status_code=status.HTTP_403_FORBIDDEN,
                error_code="PERMISSION_DENIED",
                message="You are not allowed to access this document.",
            )

        return DocumentAccess(
            document=document,
            role=permission.role,
            user_id=resolved_user_id,
            ai_allowed=bool(document.ai_enabled and permission.ai_allowed),
            current_revision=self._current_revision(document),
        )

    def require_read_access(
        self, *, document_id: str | int, user_id: str | int
    ) -> DocumentAccess:
        access = self.resolve_access(document_id=document_id, user_id=user_id)
        if access.can_read:
            return access
        self._raise_forbidden()

    def require_edit_access(
        self, *, document_id: str | int, user_id: str | int
    ) -> DocumentAccess:
        access = self.resolve_access(document_id=document_id, user_id=user_id)
        if access.can_edit:
            return access
        self._raise_forbidden()

    def require_owner_access(
        self, *, document_id: str | int, user_id: str | int
    ) -> DocumentAccess:
        access = self.resolve_access(document_id=document_id, user_id=user_id)
        if access.can_manage:
            return access
        self._raise_forbidden()

    def require_restore_access(
        self, *, document_id: str | int, user_id: str | int
    ) -> DocumentAccess:
        access = self.resolve_access(document_id=document_id, user_id=user_id)
        if access.can_restore_versions:
            return access
        self._raise_forbidden()

    def require_ai_access(
        self, *, document_id: str | int, user_id: str | int
    ) -> DocumentAccess:
        access = self.resolve_access(document_id=document_id, user_id=user_id)
        if not access.document.ai_enabled:
            raise ApiError(
                status_code=status.HTTP_403_FORBIDDEN,
                error_code="AI_DISABLED",
                message="AI is disabled for this document.",
            )
        if access.can_use_ai:
            return access
        raise ApiError(
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="AI_ROLE_NOT_ALLOWED",
            message="Your role is not allowed to use AI features.",
        )

    def validate_role(self, role: str) -> str:
        normalized_role = role.strip().lower()
        if normalized_role not in VALID_DOCUMENT_ROLES - {"owner"}:
            raise ApiError(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code="VALIDATION_ERROR",
                message="Unsupported document role.",
            )
        return normalized_role

    def _current_revision(self, document: Document) -> int:
        latest_version = document.latest_version
        if latest_version is None:
            return 0
        return latest_version.version_number

    def _raise_forbidden(self) -> None:
        raise ApiError(
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="PERMISSION_DENIED",
            message="You are not allowed to access this document.",
        )
