from fastapi import status

from apps.backend.core.errors import ApiError
from apps.backend.models.document import Document
from apps.backend.models.user import User
from apps.backend.repositories.document_repository import DocumentRepository
from apps.backend.repositories.version_repository import VersionRepository
from apps.backend.schemas.document import (
    DocumentContentSaveRequest,
    DocumentContentSaveResponse,
    DocumentCreate,
    DocumentCreateResponse,
    DocumentDetailResponse,
    DocumentMetadataResponse,
    DocumentUpdate,
)


class DocumentService:
    def __init__(
        self,
        document_repository: DocumentRepository,
        version_repository: VersionRepository,
    ):
        self.document_repository = document_repository
        self.version_repository = version_repository

    def create_document(self, *, payload: DocumentCreate, current_user: User) -> DocumentCreateResponse:
        document = self.document_repository.create(
            title=payload.title,
            content=payload.initial_content,
            content_format=payload.content_format,
            ai_enabled=payload.ai_enabled,
            owner_id=current_user.id,
        )
        self.document_repository.db.commit()
        return self._to_document_create_response(self.document_repository.get_by_id(document.id))

    def get_document(self, *, document_id: int, current_user: User) -> DocumentDetailResponse:
        document = self.document_repository.get_by_id(document_id)
        self._ensure_owner_access(document=document, current_user=current_user)
        return self._to_document_detail_response(document)

    def update_document(
        self,
        *,
        document_id: int,
        payload: DocumentUpdate,
        current_user: User,
    ) -> DocumentMetadataResponse:
        document = self.document_repository.get_by_id(document_id)
        self._ensure_owner_access(document=document, current_user=current_user)

        update_fields = payload.model_dump(exclude_unset=True)
        updated_document = self.document_repository.update(document, **update_fields)

        self.document_repository.db.commit()
        refreshed_document = self.document_repository.get_by_id(updated_document.id)
        return DocumentMetadataResponse(
            document_id=refreshed_document.id,
            title=refreshed_document.title,
            ai_enabled=refreshed_document.ai_enabled,
            updated_at=refreshed_document.updated_at,
        )

    def save_document_content(
        self,
        *,
        document_id: int,
        payload: DocumentContentSaveRequest,
        current_user: User,
    ) -> DocumentContentSaveResponse:
        document = self.document_repository.get_by_id(document_id)
        self._ensure_owner_access(document=document, current_user=current_user)

        updated_document = self.document_repository.update(document, content=payload.content)
        version = self._create_version_if_needed(
            document=updated_document,
            current_user=current_user,
            mark_as_restore=False,
            force_create=True,
        )
        self.document_repository.db.commit()
        refreshed_document = self.document_repository.get_by_id(updated_document.id)
        return DocumentContentSaveResponse(
            document_id=refreshed_document.id,
            latest_version_id=version.id,
            revision=version.version_number,
            saved_at=version.created_at,
        )

    def _ensure_owner_access(self, *, document: Document, current_user: User) -> None:
        if document is None:
            raise ApiError(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code="DOCUMENT_NOT_FOUND",
                message="Document not found.",
            )

        if document.owner_id != current_user.id:
            raise ApiError(
                status_code=status.HTTP_403_FORBIDDEN,
                error_code="PERMISSION_DENIED",
                message="You are not allowed to access this document.",
            )

    def _create_version_if_needed(
        self,
        *,
        document: Document,
        current_user: User,
        mark_as_restore: bool,
        force_create: bool,
    ):
        if self.version_repository is None:
            return None

        latest_version = self.version_repository.get_latest_for_document(document.id)
        should_create_version = force_create or latest_version is not None or bool(document.content)

        if not should_create_version:
            return None

        version = self.version_repository.create(
            document_id=document.id,
            version_number=1 if latest_version is None else latest_version.version_number + 1,
            content_snapshot=document.content,
            created_by=current_user.id,
            is_restore_version=mark_as_restore,
        )
        document.latest_version_id = version.id
        self.document_repository.update(document, latest_version_id=version.id)
        return version

    def _to_document_create_response(self, document) -> DocumentCreateResponse:
        return DocumentCreateResponse(
            document_id=document.id,
            title=document.title,
            current_content=document.content,
            content_format=document.content_format,
            owner_user_id=document.owner_id,
            role="owner",
            ai_enabled=document.ai_enabled,
            latest_version_id=document.latest_version_id,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )

    def _to_document_detail_response(self, document) -> DocumentDetailResponse:
        return DocumentDetailResponse(
            document_id=document.id,
            title=document.title,
            current_content=document.content,
            content_format=document.content_format,
            owner_user_id=document.owner_id,
            role="owner",
            ai_enabled=document.ai_enabled,
            latest_version_id=document.latest_version_id,
            updated_at=document.updated_at,
        )
