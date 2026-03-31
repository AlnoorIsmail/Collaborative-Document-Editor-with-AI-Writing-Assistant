from fastapi import status

from app.backend.core.errors import ApiError
from app.backend.models.user import User
from app.backend.repositories.document_repository import DocumentRepository
from app.backend.repositories.version_repository import VersionRepository
from app.backend.schemas.version import VersionResponse, VersionRestoreResponse
from app.backend.services.document_service import DocumentService


class VersionService:
    def __init__(
        self,
        document_repository: DocumentRepository,
        version_repository: VersionRepository,
    ):
        self.document_repository = document_repository
        self.version_repository = version_repository
        self.document_service = DocumentService(document_repository, version_repository)

    def list_versions(self, *, document_id: int, current_user: User):
        document = self.document_repository.get_by_id(document_id)
        self.document_service._ensure_owner_access(
            document=document, current_user=current_user
        )

        versions = self.version_repository.list_for_document(document_id)
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
        document_id: int,
        version_id: int,
        current_user: User,
    ) -> VersionRestoreResponse:
        document = self.document_repository.get_by_id(document_id)
        self.document_service._ensure_owner_access(
            document=document, current_user=current_user
        )

        version = self.version_repository.get_by_id(version_id)
        if version is None:
            raise ApiError(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code="VALIDATION_ERROR",
                message="Version not found.",
            )

        if version.document_id != document.id:
            raise ApiError(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code="VALIDATION_ERROR",
                message="Version does not belong to this document.",
            )

        restored_document = self.document_repository.update(
            document,
            content=version.content_snapshot,
        )
        restore_version_entry = self.document_service._create_version_if_needed(
            document=restored_document,
            current_user=current_user,
            mark_as_restore=True,
            force_create=True,
        )
        self.document_repository.db.commit()
        return VersionRestoreResponse(
            document_id=document.id,
            restored_from_version_id=version.id,
            new_version_id=restore_version_entry.id,
            message="Version restored as a new version entry.",
        )
