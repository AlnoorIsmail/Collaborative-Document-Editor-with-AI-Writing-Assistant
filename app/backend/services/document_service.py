import html as html_lib
import json
import re

from fastapi import status
from sqlalchemy.exc import IntegrityError

from app.backend.core.errors import ApiError
from app.backend.models.document import Document
from app.backend.models.user import User
from app.backend.repositories.document_repository import DocumentRepository
from app.backend.repositories.permission_repository import PermissionRepository
from app.backend.repositories.version_repository import VersionRepository
from app.backend.schemas.document import (
    DocumentContentSaveRequest,
    DocumentContentSaveResponse,
    DocumentCreate,
    DocumentCreateResponse,
    DocumentDetailResponse,
    DocumentExportRequest,
    DocumentExportResponse,
    DocumentMetadataResponse,
    DocumentOwnerResponse,
    DocumentSummaryResponse,
    DocumentUpdate,
    LatestVersionReference,
)
from app.backend.services.access_service import DocumentAccess, DocumentAccessService

DEFAULT_DOCUMENT_TITLE = "Untitled Document"
TITLE_SUFFIX_PATTERN = re.compile(r"^(?P<base>.+?) (?P<index>\d+)$")
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
MAX_TITLE_GENERATION_ATTEMPTS = 5


def normalize_document_title(raw_title: str | None) -> str:
    if raw_title is None:
        return DEFAULT_DOCUMENT_TITLE

    normalized = re.sub(r"\s+", " ", raw_title).strip()
    return normalized or DEFAULT_DOCUMENT_TITLE


def generate_unique_document_title(
    preferred_title: str | None,
    existing_titles: list[str],
) -> str:
    normalized_title = normalize_document_title(preferred_title)

    match = TITLE_SUFFIX_PATTERN.match(normalized_title)
    if match:
        base_title = match.group("base").strip()
        requested_suffix = int(match.group("index"))
    else:
        base_title = normalized_title
        requested_suffix = None

    used_suffixes: set[int] = set()
    normalized_lookup: set[str] = set()

    for existing_title in existing_titles:
        normalized_existing = normalize_document_title(existing_title)
        normalized_lookup.add(normalized_existing.casefold())
        if normalized_existing.casefold() == base_title.casefold():
            used_suffixes.add(0)
            continue

        sibling_match = TITLE_SUFFIX_PATTERN.match(normalized_existing)
        if not sibling_match:
            continue
        if sibling_match.group("base").strip().casefold() != base_title.casefold():
            continue
        used_suffixes.add(int(sibling_match.group("index")))

    if requested_suffix is not None and normalized_title.casefold() not in normalized_lookup:
        return normalized_title

    if not used_suffixes:
        return normalized_title

    next_index = max(used_suffixes)
    if requested_suffix is not None:
        next_index = max(next_index, requested_suffix)
    next_index += 1

    while True:
        candidate = f"{base_title} {next_index}"
        if candidate.casefold() not in normalized_lookup:
            return candidate
        next_index += 1


class DocumentService:
    def __init__(
        self,
        document_repository: DocumentRepository,
        version_repository: VersionRepository,
        permission_repository: PermissionRepository,
    ) -> None:
        self.document_repository = document_repository
        self.version_repository = version_repository
        self.permission_repository = permission_repository
        self.access_service = DocumentAccessService(
            document_repository,
            permission_repository,
        )

    def list_documents(self, *, current_user: User) -> list[DocumentSummaryResponse]:
        owned_documents = self.document_repository.list_owned_by_user(current_user.id)
        shared_permissions = self.permission_repository.list_for_user(current_user.id)

        documents_by_id: dict[int, DocumentSummaryResponse] = {}
        for document in owned_documents:
            documents_by_id[document.id] = self._to_document_summary_response(
                document=document,
                role="owner",
            )

        for permission in shared_permissions:
            document = permission.document
            if document.id in documents_by_id:
                continue
            documents_by_id[document.id] = self._to_document_summary_response(
                document=document,
                role=permission.role,
            )

        return sorted(
            documents_by_id.values(),
            key=lambda document: (document.updated_at, document.created_at),
            reverse=True,
        )

    def create_document(
        self, *, payload: DocumentCreate, current_user: User
    ) -> DocumentCreateResponse:
        for attempt in range(MAX_TITLE_GENERATION_ATTEMPTS):
            resolved_title = self._resolve_unique_title(
                owner_id=current_user.id,
                preferred_title=payload.title,
            )

            try:
                document = self.document_repository.create(
                    title=resolved_title,
                    content=payload.initial_content,
                    content_format=payload.content_format,
                    ai_enabled=payload.ai_enabled,
                    owner_id=current_user.id,
                )
                self.document_repository.db.commit()
                refreshed_document = self.document_repository.get_by_id(document.id)
                return self._to_document_create_response(
                    refreshed_document,
                    role="owner",
                    revision=0,
                )
            except IntegrityError:
                self.document_repository.db.rollback()
                if attempt == MAX_TITLE_GENERATION_ATTEMPTS - 1:
                    self._raise_title_conflict()

        self._raise_title_conflict()

    def get_document(
        self, *, document_id: str | int, current_user: User
    ) -> DocumentDetailResponse:
        access = self.access_service.require_read_access(
            document_id=document_id,
            user_id=current_user.id,
        )
        return self._to_document_detail_response(access)

    def update_document(
        self,
        *,
        document_id: str | int,
        payload: DocumentUpdate,
        current_user: User,
    ) -> DocumentMetadataResponse:
        access = self.access_service.require_owner_access(
            document_id=document_id,
            user_id=current_user.id,
        )

        update_fields = payload.model_dump(exclude_unset=True)
        if "title" not in update_fields:
            updated_document = self.document_repository.update(
                access.document, **update_fields
            )
            self.document_repository.db.commit()
            refreshed_access = self.access_service.require_read_access(
                document_id=updated_document.id,
                user_id=current_user.id,
            )
            return DocumentMetadataResponse(
                document_id=refreshed_access.document.id,
                title=refreshed_access.document.title,
                ai_enabled=refreshed_access.document.ai_enabled,
                role=refreshed_access.role,
                updated_at=refreshed_access.document.updated_at,
            )

        for attempt in range(MAX_TITLE_GENERATION_ATTEMPTS):
            next_update_fields = {
                **update_fields,
                "title": self._resolve_unique_title(
                    owner_id=current_user.id,
                    preferred_title=update_fields["title"],
                    exclude_document_id=access.document.id,
                ),
            }

            try:
                updated_document = self.document_repository.update(
                    access.document, **next_update_fields
                )
                self.document_repository.db.commit()
                refreshed_access = self.access_service.require_read_access(
                    document_id=updated_document.id,
                    user_id=current_user.id,
                )
                return DocumentMetadataResponse(
                    document_id=refreshed_access.document.id,
                    title=refreshed_access.document.title,
                    ai_enabled=refreshed_access.document.ai_enabled,
                    role=refreshed_access.role,
                    updated_at=refreshed_access.document.updated_at,
                )
            except IntegrityError:
                self.document_repository.db.rollback()
                access = self.access_service.require_owner_access(
                    document_id=document_id,
                    user_id=current_user.id,
                )
                if attempt == MAX_TITLE_GENERATION_ATTEMPTS - 1:
                    self._raise_title_conflict()

        self._raise_title_conflict()

    def delete_document(self, *, document_id: str | int, current_user: User) -> None:
        access = self.access_service.require_owner_access(
            document_id=document_id,
            user_id=current_user.id,
        )
        self.document_repository.delete(access.document)
        self.document_repository.db.commit()

    def save_document_content(
        self,
        *,
        document_id: str | int,
        payload: DocumentContentSaveRequest,
        current_user: User,
    ) -> DocumentContentSaveResponse:
        access = self.access_service.require_edit_access(
            document_id=document_id,
            user_id=current_user.id,
        )
        if self._can_acknowledge_existing_save(access=access, content=payload.content):
            return self._existing_save_response(access.document)
        self._ensure_matching_revision(
            base_revision=payload.base_revision,
            current_revision=access.current_revision,
        )

        try:
            updated_document = self.document_repository.update(
                access.document,
                content=payload.content,
            )
            version = self._create_version(
                document=updated_document,
                current_user=current_user,
                mark_as_restore=False,
            )
            self.document_repository.db.commit()
        except IntegrityError:
            self.document_repository.db.rollback()
            refreshed_access = self.access_service.require_edit_access(
                document_id=document_id,
                user_id=current_user.id,
            )
            if self._can_acknowledge_existing_save(
                access=refreshed_access,
                content=payload.content,
            ):
                return self._existing_save_response(refreshed_access.document)
            self._raise_concurrent_save_conflict()
        return DocumentContentSaveResponse(
            document_id=updated_document.id,
            latest_version_id=version.id,
            revision=version.version_number,
            saved_at=version.created_at,
        )

    def export_document(
        self,
        *,
        document_id: str | int,
        payload: DocumentExportRequest,
        current_user: User,
    ) -> DocumentExportResponse:
        access = self.access_service.require_read_access(
            document_id=document_id,
            user_id=current_user.id,
        )
        export_format = payload.format.strip().lower()
        content_type, exported_content = self._serialize_document(
            document=access.document,
            revision=access.current_revision,
            export_format=export_format,
        )
        filename = self._export_filename(access.document.title, export_format)

        return DocumentExportResponse(
            document_id=access.document.id,
            title=access.document.title,
            format=export_format,
            content_type=content_type,
            filename=filename,
            exported_content=exported_content,
            revision=access.current_revision,
            exported_at=access.document.updated_at,
        )

    def ensure_restore_access(
        self, *, document_id: str | int, current_user: User
    ) -> DocumentAccess:
        return self.access_service.require_restore_access(
            document_id=document_id,
            user_id=current_user.id,
        )

    def ensure_read_access(
        self, *, document_id: str | int, current_user: User
    ) -> DocumentAccess:
        return self.access_service.require_read_access(
            document_id=document_id,
            user_id=current_user.id,
        )

    def create_version_from_snapshot(
        self,
        *,
        document: Document,
        current_user: User,
        mark_as_restore: bool,
    ):
        return self._create_version(
            document=document,
            current_user=current_user,
            mark_as_restore=mark_as_restore,
        )

    def _create_version(
        self,
        *,
        document: Document,
        current_user: User,
        mark_as_restore: bool,
    ):
        latest_version = self.version_repository.get_latest_for_document(document.id)
        version = self.version_repository.create(
            document_id=document.id,
            version_number=(
                1 if latest_version is None else latest_version.version_number + 1
            ),
            content_snapshot=document.content,
            created_by=current_user.id,
            is_restore_version=mark_as_restore,
        )
        self.document_repository.update(document, latest_version_id=version.id)
        return version

    def _ensure_matching_revision(
        self, *, base_revision: int, current_revision: int
    ) -> None:
        if base_revision == current_revision:
            return
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            error_code="CONFLICT_DETECTED",
            message="The document revision is stale. Refresh and retry.",
        )

    def _can_acknowledge_existing_save(
        self, *, access: DocumentAccess, content: str
    ) -> bool:
        return (
            access.current_revision > 0
            and access.document.latest_version is not None
            and access.document.content == content
        )

    def _existing_save_response(
        self, document: Document
    ) -> DocumentContentSaveResponse:
        latest_version = document.latest_version
        if latest_version is None:
            raise ApiError(
                status_code=status.HTTP_409_CONFLICT,
                error_code="CONFLICT_DETECTED",
                message="The document revision is stale. Refresh and retry.",
            )
        return DocumentContentSaveResponse(
            document_id=document.id,
            latest_version_id=latest_version.id,
            revision=latest_version.version_number,
            saved_at=latest_version.created_at,
        )

    def _raise_concurrent_save_conflict(self) -> None:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            error_code="CONFLICT_DETECTED",
            message="Another collaborator saved a newer revision. Refresh and retry.",
        )

    def _raise_title_conflict(self) -> None:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            error_code="TITLE_CONFLICT",
            message="The document title could not be finalized. Try again.",
        )

    def _resolve_unique_title(
        self,
        *,
        owner_id: int,
        preferred_title: str | None,
        exclude_document_id: int | None = None,
    ) -> str:
        existing_titles = self.document_repository.list_titles_by_owner(
            owner_id=owner_id,
            exclude_document_id=exclude_document_id,
        )
        return generate_unique_document_title(preferred_title, existing_titles)

    def _preview_text(self, content: str, limit: int = 170) -> str:
        plain_text = html_lib.unescape(
            HTML_TAG_PATTERN.sub(" ", content or "")
        )
        normalized = re.sub(r"\s+", " ", plain_text).strip()

        if not normalized:
            return "Empty document"

        if len(normalized) <= limit:
            return normalized

        return f"{normalized[: limit - 3].rstrip()}..."

    def _serialize_document(
        self,
        *,
        document: Document,
        revision: int,
        export_format: str,
    ) -> tuple[str, str]:
        if export_format == "plain_text":
            return "text/plain; charset=utf-8", document.content

        if export_format == "markdown":
            return "text/markdown; charset=utf-8", document.content

        if export_format == "html":
            escaped_title = html_lib.escape(document.title, quote=True)
            escaped_content = html_lib.escape(document.content, quote=True)
            html_document = (
                f'<article data-document-id="{document.id}" data-revision="{revision}">'
                f"<h1>{escaped_title}</h1><pre>{escaped_content}</pre></article>"
            )
            return "text/html; charset=utf-8", html_document

        if export_format == "json":
            payload = {
                "document_id": document.id,
                "title": document.title,
                "content": document.content,
                "content_format": document.content_format,
                "revision": revision,
                "ai_enabled": document.ai_enabled,
            }
            return "application/json", json.dumps(payload, sort_keys=True)

        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="VALIDATION_ERROR",
            message="Unsupported export format.",
        )

    def _export_filename(self, title: str, export_format: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "document"
        extension = {
            "plain_text": "txt",
            "markdown": "md",
            "html": "html",
            "json": "json",
        }[export_format]
        return f"{slug}.{extension}"

    def _latest_version_reference(
        self, document: Document
    ) -> LatestVersionReference | None:
        latest_version = document.latest_version
        if latest_version is None:
            return None
        return LatestVersionReference(
            version_id=latest_version.id,
            revision=latest_version.version_number,
        )

    def _owner_response(self, document: Document) -> DocumentOwnerResponse:
        return DocumentOwnerResponse(
            user_id=document.owner.id,
            display_name=document.owner.display_name,
        )

    def _to_document_create_response(
        self,
        document: Document,
        *,
        role: str,
        revision: int,
    ) -> DocumentCreateResponse:
        latest_version = self._latest_version_reference(document)
        return DocumentCreateResponse(
            document_id=document.id,
            title=document.title,
            current_content=document.content,
            content_format=document.content_format,
            owner=self._owner_response(document),
            owner_user_id=document.owner_id,
            role=role,
            ai_enabled=document.ai_enabled,
            revision=revision,
            latest_version_id=document.latest_version_id,
            latest_version=latest_version,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )

    def _to_document_summary_response(
        self,
        *,
        document: Document,
        role: str,
    ) -> DocumentSummaryResponse:
        latest_version = self._latest_version_reference(document)
        return DocumentSummaryResponse(
            document_id=document.id,
            title=document.title,
            preview_text=self._preview_text(document.content),
            content_format=document.content_format,
            owner=self._owner_response(document),
            owner_user_id=document.owner_id,
            role=role,
            ai_enabled=document.ai_enabled,
            revision=0 if latest_version is None else latest_version.revision,
            latest_version_id=document.latest_version_id,
            latest_version=latest_version,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )

    def _to_document_detail_response(
        self, access: DocumentAccess
    ) -> DocumentDetailResponse:
        latest_version = self._latest_version_reference(access.document)
        return DocumentDetailResponse(
            document_id=access.document.id,
            title=access.document.title,
            current_content=access.document.content,
            content_format=access.document.content_format,
            owner=self._owner_response(access.document),
            owner_user_id=access.document.owner_id,
            role=access.role,
            ai_enabled=access.document.ai_enabled,
            revision=access.current_revision,
            latest_version_id=access.document.latest_version_id,
            latest_version=latest_version,
            created_at=access.document.created_at,
            updated_at=access.document.updated_at,
        )
