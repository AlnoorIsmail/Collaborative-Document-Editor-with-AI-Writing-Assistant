from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus

from app.backend.core.contracts import parse_resource_id, utc_now
from app.backend.core.errors import AppError
from app.backend.core.security import AuthenticatedPrincipal
from app.backend.models.user import User
from app.backend.repositories.conflict_repository import ConflictRepository
from app.backend.repositories.document_repository import DocumentRepository
from app.backend.repositories.permission_repository import PermissionRepository
from app.backend.repositories.version_repository import VersionRepository
from app.backend.schemas.ai import AIInteractionCreateRequest
from app.backend.schemas.common import ErrorCode, TextRange
from app.backend.schemas.conflict import (
    ConflictCandidateCreateRequest,
    DocumentConflictCreateRequest,
    DocumentConflictResolveRequest,
    DocumentConflictResolveResponse,
    DocumentConflictResponse,
    DocumentConflictCandidateResponse,
)
from app.backend.services.access_service import DocumentAccessService


UNRESOLVED_CONFLICT_STATUSES = {"open", "stale"}
ANCHOR_CONTEXT_WINDOW = 24


@dataclass(frozen=True)
class ConflictResolutionResult:
    response: DocumentConflictResolveResponse
    content: str
    line_spacing: float


class ConflictService:
    def __init__(
        self,
        *,
        conflict_repository: ConflictRepository,
        document_repository: DocumentRepository,
        permission_repository: PermissionRepository,
        version_repository: VersionRepository,
    ) -> None:
        self._conflict_repository = conflict_repository
        self._document_repository = document_repository
        self._version_repository = version_repository
        self._access_service = DocumentAccessService(
            document_repository,
            permission_repository,
        )

    def list_conflicts(
        self,
        *,
        document_id: str | int,
        current_user: User,
    ) -> list[DocumentConflictResponse]:
        access = self._access_service.require_read_access(
            document_id=document_id,
            user_id=current_user.id,
        )
        conflicts = self._conflict_repository.list_open_conflicts(
            document_id=access.document.id
        )
        responses = [
            self._to_conflict_response(
                conflict=conflict,
                document_content=access.document.content,
            )
            for conflict in conflicts
        ]
        self._conflict_repository.db.commit()
        return responses

    def get_conflict(
        self,
        *,
        document_id: str | int,
        conflict_id: int,
        current_user: User,
    ) -> DocumentConflictResponse:
        access = self._access_service.require_read_access(
            document_id=document_id,
            user_id=current_user.id,
        )
        conflict = self._conflict_repository.get_conflict_by_id(
            conflict_id=conflict_id,
            document_id=access.document.id,
        )
        if conflict is None:
            raise AppError(
                status_code=HTTPStatus.NOT_FOUND,
                error_code=ErrorCode.DOCUMENT_NOT_FOUND,
                message="Conflict not found.",
            )
        response = self._to_conflict_response(
            conflict=conflict,
            document_content=access.document.content,
        )
        self._conflict_repository.db.commit()
        return response

    def create_conflict(
        self,
        *,
        document_id: str | int,
        current_user: User,
        payload: DocumentConflictCreateRequest,
    ) -> DocumentConflictResponse:
        access = self._access_service.require_edit_access(
            document_id=document_id,
            user_id=current_user.id,
        )
        local_candidate = payload.local_candidate
        remote_candidate = payload.remote_candidate
        anchor_start, anchor_end = self._merge_ranges(
            local_candidate.range,
            remote_candidate.range,
        )

        current_content = access.document.content
        exact_text_snapshot = self._slice_text(current_content, anchor_start, anchor_end)
        prefix_context, suffix_context = self._anchor_context(
            current_content,
            anchor_start,
            anchor_end,
        )

        conflict = None
        if payload.conflict_key:
            conflict = self._conflict_repository.get_conflict_by_key(
                document_id=access.document.id,
                conflict_key=payload.conflict_key,
            )

        if conflict is None:
            conflict = self._conflict_repository.find_overlapping_open_conflict(
                document_id=access.document.id,
                source_collab_version=payload.source_collab_version,
                anchor_start=anchor_start,
                anchor_end=anchor_end,
            )

        if conflict is None:
            conflict = self._conflict_repository.create_conflict(
                document_id=access.document.id,
                conflict_key=payload.conflict_key,
                status="open",
                source_revision=payload.source_revision,
                source_collab_version=payload.source_collab_version,
                anchor_start=anchor_start,
                anchor_end=anchor_end,
                exact_text_snapshot=exact_text_snapshot,
                prefix_context=prefix_context,
                suffix_context=suffix_context,
                created_by_user_id=current_user.id,
            )
        else:
            conflict = self._conflict_repository.update_conflict(
                conflict,
                anchor_start=anchor_start,
                anchor_end=anchor_end,
                exact_text_snapshot=exact_text_snapshot,
                prefix_context=prefix_context,
                suffix_context=suffix_context,
                source_revision=max(conflict.source_revision, payload.source_revision),
                source_collab_version=max(
                    conflict.source_collab_version, payload.source_collab_version
                ),
                status="open",
            )

        self._ensure_candidate(
            conflict_id=conflict.id,
            candidate=local_candidate,
            fallback_user_id=current_user.id,
            fallback_display_name=current_user.display_name,
        )
        self._ensure_candidate(
            conflict_id=conflict.id,
            candidate=remote_candidate,
            fallback_user_id=parse_resource_id(
                remote_candidate.user_id or current_user.id,
                "usr",
            ),
            fallback_display_name=remote_candidate.user_display_name or "Collaborator",
        )

        self._conflict_repository.db.commit()
        refreshed = self._conflict_repository.get_conflict_by_id(
            conflict_id=conflict.id,
            document_id=access.document.id,
        )
        return self._to_conflict_response(
            conflict=refreshed,
            document_content=current_content,
        )

    def resolve_conflict(
        self,
        *,
        document_id: str | int,
        conflict_id: int,
        current_user: User,
        payload: DocumentConflictResolveRequest,
    ) -> ConflictResolutionResult:
        access = self._access_service.require_edit_access(
            document_id=document_id,
            user_id=current_user.id,
        )
        conflict = self._conflict_repository.get_conflict_by_id(
            conflict_id=conflict_id,
            document_id=access.document.id,
        )
        if conflict is None:
            raise AppError(
                status_code=HTTPStatus.NOT_FOUND,
                error_code=ErrorCode.DOCUMENT_NOT_FOUND,
                message="Conflict not found.",
            )

        if conflict.status not in UNRESOLVED_CONFLICT_STATUSES:
            raise AppError(
                status_code=HTTPStatus.CONFLICT,
                error_code=ErrorCode.CONFLICT_DETECTED,
                message="This conflict was already resolved.",
            )

        anchor_range = self._locate_anchor(
            content=access.document.content,
            anchor_start=conflict.anchor_start,
            anchor_end=conflict.anchor_end,
            exact_text_snapshot=conflict.exact_text_snapshot,
            prefix_context=conflict.prefix_context,
            suffix_context=conflict.suffix_context,
        )
        if anchor_range is None:
            self._conflict_repository.update_conflict(conflict, status="stale")
            self._conflict_repository.db.commit()
            raise AppError(
                status_code=HTTPStatus.CONFLICT,
                error_code=ErrorCode.CONFLICT_DETECTED,
                message=(
                    "The conflict region moved and could not be safely re-anchored. "
                    "Refresh the document and review the conflict again."
                ),
            )

        resolved_content = (payload.resolved_content or "").strip()
        if payload.candidate_id is not None and not resolved_content:
            candidate = next(
                (
                    entry
                    for entry in conflict.candidates
                    if entry.id == payload.candidate_id
                ),
                None,
            )
            if candidate is None:
                raise AppError(
                    status_code=HTTPStatus.NOT_FOUND,
                    error_code=ErrorCode.DOCUMENT_NOT_FOUND,
                    message="Conflict candidate not found.",
                )
            resolved_content = candidate.candidate_content_snapshot

        if not resolved_content:
            raise AppError(
                status_code=HTTPStatus.BAD_REQUEST,
                error_code=ErrorCode.VALIDATION_ERROR,
                message="Resolution content cannot be empty.",
            )

        next_content = (
            access.document.content[: anchor_range.start]
            + resolved_content
            + access.document.content[anchor_range.end :]
        )
        updated_document = self._document_repository.update(
            access.document,
            content=next_content,
        )
        latest_version = self._version_repository.get_latest_for_document(updated_document.id)
        version = self._version_repository.create(
            document_id=updated_document.id,
            version_number=1 if latest_version is None else latest_version.version_number + 1,
            content_snapshot=updated_document.content,
            line_spacing_snapshot=updated_document.line_spacing,
            save_source="manual",
            created_by=current_user.id,
            is_restore_version=False,
        )
        self._document_repository.update(updated_document, latest_version_id=version.id)
        resolved_at = utc_now()
        self._conflict_repository.resolve_conflict(
            conflict=conflict,
            status="resolved",
            resolved_content=resolved_content,
            resolved_by_user_id=current_user.id,
            resolved_at=resolved_at,
        )
        self._conflict_repository.db.commit()

        response = DocumentConflictResolveResponse(
            conflict_id=conflict.id,
            status="resolved",
            resolved_content=resolved_content,
            new_revision=version.version_number,
            latest_version_id=version.id,
            collab_version=0,
            resolved_at=resolved_at,
        )
        return ConflictResolutionResult(
            response=response,
            content=updated_document.content,
            line_spacing=updated_document.line_spacing,
        )

    def build_conflict_merge_request(
        self,
        *,
        document_id: str | int,
        conflict_id: int,
        principal: AuthenticatedPrincipal,
    ) -> AIInteractionCreateRequest:
        user_id = parse_resource_id(principal.user_id, "usr")
        access = self._access_service.require_ai_access(
            document_id=document_id,
            user_id=user_id,
        )
        conflict = self._conflict_repository.get_conflict_by_id(
            conflict_id=conflict_id,
            document_id=access.document.id,
        )
        if conflict is None:
            raise AppError(
                status_code=HTTPStatus.NOT_FOUND,
                error_code=ErrorCode.DOCUMENT_NOT_FOUND,
                message="Conflict not found.",
            )

        anchor_range = self._locate_anchor(
            content=access.document.content,
            anchor_start=conflict.anchor_start,
            anchor_end=conflict.anchor_end,
            exact_text_snapshot=conflict.exact_text_snapshot,
            prefix_context=conflict.prefix_context,
            suffix_context=conflict.suffix_context,
        )
        conflict_snapshot = "\n\n".join(
            f"{candidate.user_display_name}: {candidate.candidate_content_snapshot}"
            for candidate in conflict.candidates
        )
        surrounding_context = (
            f"Conflict prefix context: {conflict.prefix_context or 'Not provided.'}\n"
            f"Conflict suffix context: {conflict.suffix_context or 'Not provided.'}\n"
            f"Current document conflict region: {conflict.exact_text_snapshot or 'Not provided.'}"
        )
        return AIInteractionCreateRequest(
            feature_type="conflict_merge",
            scope_type="selection",
            selected_range=anchor_range,
            selected_text_snapshot=conflict_snapshot,
            surrounding_context=surrounding_context,
            user_instruction=(
                "Propose a single merged resolution that preserves the strongest parts "
                "of each conflicting candidate."
            ),
            base_revision=access.current_revision,
            parameters={"conflict_id": conflict_id},
        )

    def _ensure_candidate(
        self,
        *,
        conflict_id: int,
        candidate: ConflictCandidateCreateRequest,
        fallback_user_id: int,
        fallback_display_name: str,
    ) -> None:
        resolved_user_id = parse_resource_id(
            candidate.user_id or fallback_user_id,
            "usr",
        )
        existing_candidate = self._conflict_repository.find_candidate(
            conflict_id=conflict_id,
            batch_id=candidate.batch_id,
            user_id=resolved_user_id,
        )
        if existing_candidate is not None:
            return

        self._conflict_repository.create_candidate(
            conflict_id=conflict_id,
            user_id=resolved_user_id,
            user_display_name=candidate.user_display_name or fallback_display_name,
            batch_id=candidate.batch_id,
            client_id=candidate.client_id,
            range_start=candidate.range.start,
            range_end=candidate.range.end,
            candidate_content_snapshot=candidate.candidate_content_snapshot,
            exact_text_snapshot=candidate.exact_text_snapshot,
            prefix_context=candidate.prefix_context,
            suffix_context=candidate.suffix_context,
        )

    def _to_conflict_response(
        self,
        *,
        conflict,
        document_content: str,
    ) -> DocumentConflictResponse:
        anchor_range = self._locate_anchor(
            content=document_content,
            anchor_start=conflict.anchor_start,
            anchor_end=conflict.anchor_end,
            exact_text_snapshot=conflict.exact_text_snapshot,
            prefix_context=conflict.prefix_context,
            suffix_context=conflict.suffix_context,
        )
        next_status = conflict.status
        if conflict.status in UNRESOLVED_CONFLICT_STATUSES:
            next_status = "open" if anchor_range is not None else "stale"
            if next_status != conflict.status:
                self._conflict_repository.update_conflict(conflict, status=next_status)

        return DocumentConflictResponse(
            conflict_id=conflict.id,
            conflict_key=conflict.conflict_key,
            status=next_status,
            stale=next_status == "stale",
            source_revision=conflict.source_revision,
            source_collab_version=conflict.source_collab_version,
            anchor_range=anchor_range,
            exact_text_snapshot=conflict.exact_text_snapshot,
            prefix_context=conflict.prefix_context,
            suffix_context=conflict.suffix_context,
            created_at=conflict.created_at,
            updated_at=conflict.updated_at,
            resolved_at=conflict.resolved_at,
            resolved_content=conflict.resolved_content,
            candidates=[
                DocumentConflictCandidateResponse(
                    candidate_id=candidate.id,
                    user_id=candidate.user_id,
                    user_display_name=candidate.user_display_name,
                    batch_id=candidate.batch_id,
                    client_id=candidate.client_id,
                    range=TextRange(
                        start=candidate.range_start,
                        end=candidate.range_end,
                    ),
                    candidate_content_snapshot=candidate.candidate_content_snapshot,
                    exact_text_snapshot=candidate.exact_text_snapshot,
                    prefix_context=candidate.prefix_context,
                    suffix_context=candidate.suffix_context,
                    created_at=candidate.created_at,
                )
                for candidate in conflict.candidates
            ],
        )

    def _merge_ranges(
        self,
        local_range: TextRange,
        remote_range: TextRange,
    ) -> tuple[int, int]:
        return (
            min(local_range.start, remote_range.start),
            max(local_range.end, remote_range.end),
        )

    def _anchor_context(
        self,
        content: str,
        start: int,
        end: int,
    ) -> tuple[str, str]:
        normalized_start = max(0, min(start, len(content)))
        normalized_end = max(normalized_start, min(end, len(content)))
        return (
            content[max(0, normalized_start - ANCHOR_CONTEXT_WINDOW) : normalized_start],
            content[normalized_end : min(len(content), normalized_end + ANCHOR_CONTEXT_WINDOW)],
        )

    def _slice_text(self, content: str, start: int, end: int) -> str:
        normalized_start = max(0, min(start, len(content)))
        normalized_end = max(normalized_start, min(end, len(content)))
        return content[normalized_start:normalized_end]

    def _locate_anchor(
        self,
        *,
        content: str,
        anchor_start: int | None,
        anchor_end: int | None,
        exact_text_snapshot: str,
        prefix_context: str,
        suffix_context: str,
    ) -> TextRange | None:
        if anchor_start is None or anchor_end is None:
            return None

        normalized_start = max(0, min(anchor_start, len(content)))
        normalized_end = max(normalized_start, min(anchor_end, len(content)))
        if content[normalized_start:normalized_end] == exact_text_snapshot:
            return TextRange(start=normalized_start, end=normalized_end)

        if not exact_text_snapshot:
            return TextRange(start=normalized_start, end=normalized_end)

        best_match: tuple[int, int, int] | None = None
        search_cursor = 0
        while True:
            index = content.find(exact_text_snapshot, search_cursor)
            if index < 0:
                break
            end_index = index + len(exact_text_snapshot)
            score = 0
            if prefix_context and content[max(0, index - len(prefix_context)) : index] == prefix_context:
                score += 2
            if suffix_context and content[end_index : end_index + len(suffix_context)] == suffix_context:
                score += 2
            if best_match is None or score > best_match[0]:
                best_match = (score, index, end_index)
            search_cursor = index + 1

        if best_match is None:
            return None
        return TextRange(start=best_match[1], end=best_match[2])
