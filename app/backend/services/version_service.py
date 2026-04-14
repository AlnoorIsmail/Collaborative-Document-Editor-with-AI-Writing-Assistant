from fastapi import status

from app.backend.core.contracts import parse_resource_id
from app.backend.core.errors import ApiError
from app.backend.models.user import User
from app.backend.repositories.document_repository import DocumentRepository
from app.backend.repositories.permission_repository import PermissionRepository
from app.backend.repositories.version_repository import VersionRepository
from app.backend.schemas.version import VersionResponse, VersionRestoreResponse
from app.backend.services.access_service import DocumentAccessService


class VersionService:
    def __init__(
        self,
        document_repository: DocumentRepository,
        version_repository: VersionRepository,
        permission_repository: PermissionRepository,
    ) -> None:
        self.document_repository = document_repository
        self.version_repository = version_repository
        self.access_service = DocumentAccessService(
            document_repository,
            permission_repository,
        )

    def list_versions(self, *, document_id: str | int, current_user: User):
        access = self.access_service.require_read_access(
            document_id=document_id,
            user_id=current_user.id,
        )
        versions = self.version_repository.list_for_document(access.document.id)
        return [
            VersionResponse(
                version_id=version.id,
                version_number=version.version_number,
                created_by=version.created_by,
                created_at=version.created_at,
                is_restore_version=version.is_restore_version,
            )
            for version in versions
        ]

    def restore_version(
        self,
        *,
        document_id: str | int,
        version_id: str | int,
        current_user: User,
    ) -> VersionRestoreResponse:
        access = self.access_service.require_restore_access(
            document_id=document_id,
            user_id=current_user.id,
        )

        version = self.version_repository.get_by_id(
            parse_resource_id(version_id, "ver")
        )
        if version is None:
            raise ApiError(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code="VALIDATION_ERROR",
                message="Version not found.",
            )

        if version.document_id != access.document.id:
            raise ApiError(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code="VALIDATION_ERROR",
                message="Version does not belong to this document.",
            )

        restored_document = self.document_repository.update(
            access.document,
            content=version.content_snapshot,
        )
        restore_version_entry = self._create_restore_version(
            document=restored_document,
            current_user=current_user,
        )
        self.document_repository.db.commit()
        return VersionRestoreResponse(
            document_id=restored_document.id,
            restored_from_version_id=version.id,
            new_version_id=restore_version_entry.id,
            message="Version restored as a new version entry.",
        )

    def _create_restore_version(self, *, document, current_user: User):
        latest_version = self.version_repository.get_latest_for_document(document.id)
        version = self.version_repository.create(
            document_id=document.id,
            version_number=(
                1 if latest_version is None else latest_version.version_number + 1
            ),
            content_snapshot=document.content,
            created_by=current_user.id,
            is_restore_version=True,
        )
        self.document_repository.update(document, latest_version_id=version.id)
        return version
