from fastapi import status

from app.backend.core.contracts import parse_resource_id, utc_now
from app.backend.core.errors import ApiError
from app.backend.models.user import User
from app.backend.repositories.comment_repository import CommentRepository
from app.backend.repositories.document_repository import DocumentRepository
from app.backend.repositories.permission_repository import PermissionRepository
from app.backend.schemas.comment import (
    CommentAuthorResponse,
    DocumentCommentCreateRequest,
    DocumentCommentResponse,
    serialize_comment_id,
)
from app.backend.services.access_service import DocumentAccessService

COMMENT_CREATE_ROLES = {"owner", "editor", "commenter"}
COMMENT_MANAGE_ROLES = {"owner", "editor"}


class CommentService:
    def __init__(
        self,
        *,
        comment_repository: CommentRepository,
        document_repository: DocumentRepository,
        permission_repository: PermissionRepository,
    ) -> None:
        self._comment_repository = comment_repository
        self._access_service = DocumentAccessService(
            document_repository,
            permission_repository,
        )

    def list_comments(
        self,
        *,
        document_id: str | int,
        current_user: User,
    ) -> list[DocumentCommentResponse]:
        access = self._access_service.require_read_access(
            document_id=document_id,
            user_id=current_user.id,
        )
        comments = self._comment_repository.list_for_document(access.document.id)
        return [self._to_comment_response(comment) for comment in comments]

    def create_comment(
        self,
        *,
        document_id: str | int,
        payload: DocumentCommentCreateRequest,
        current_user: User,
    ) -> DocumentCommentResponse:
        access = self._access_service.resolve_access(
            document_id=document_id,
            user_id=current_user.id,
        )
        if access.role not in COMMENT_CREATE_ROLES:
            self._raise_forbidden()

        normalized_body = payload.body.strip()
        normalized_quote = payload.quoted_text.strip() if payload.quoted_text else None
        if not normalized_body:
            raise ApiError(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code="VALIDATION_ERROR",
                message="Comment text is required.",
            )

        comment = self._comment_repository.create(
            document_id=access.document.id,
            author_user_id=current_user.id,
            body=normalized_body,
            quoted_text=normalized_quote or None,
        )
        self._comment_repository.db.commit()
        return self._to_comment_response(comment)

    def resolve_comment(
        self,
        *,
        document_id: str | int,
        comment_id: str | int,
        current_user: User,
    ) -> DocumentCommentResponse:
        access = self._access_service.resolve_access(
            document_id=document_id,
            user_id=current_user.id,
        )
        if access.role not in COMMENT_MANAGE_ROLES:
            self._raise_forbidden()

        comment = self._require_comment(comment_id=comment_id, document_id=access.document.id)
        if comment.status == "resolved":
            return self._to_comment_response(comment)

        updated_comment = self._comment_repository.update(
            comment,
            status="resolved",
            resolved_at=utc_now(),
            resolved_by_user_id=current_user.id,
        )
        self._comment_repository.db.commit()
        return self._to_comment_response(updated_comment)

    def delete_comment(
        self,
        *,
        document_id: str | int,
        comment_id: str | int,
        current_user: User,
    ) -> str:
        access = self._access_service.require_read_access(
            document_id=document_id,
            user_id=current_user.id,
        )
        comment = self._require_comment(comment_id=comment_id, document_id=access.document.id)
        can_delete = (
            access.role in COMMENT_MANAGE_ROLES
            or comment.author_user_id == current_user.id
        )
        if not can_delete:
            self._raise_forbidden()

        serialized_comment_id = serialize_comment_id(comment.id)
        self._comment_repository.delete(comment)
        self._comment_repository.db.commit()
        return serialized_comment_id

    def _require_comment(
        self,
        *,
        comment_id: str | int,
        document_id: int,
    ):
        resolved_comment_id = parse_resource_id(comment_id, "cmt")
        comment = self._comment_repository.get_by_id(resolved_comment_id)
        if comment is None or comment.document_id != document_id:
            raise ApiError(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code="COMMENT_NOT_FOUND",
                message="Comment not found.",
            )
        return comment

    def _to_comment_response(self, comment) -> DocumentCommentResponse:
        author = comment.author
        if author is None:
            raise ApiError(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error_code="COMMENT_AUTHOR_MISSING",
                message="Comment author could not be loaded.",
            )

        return DocumentCommentResponse(
            comment_id=serialize_comment_id(comment.id),
            document_id=comment.document_id,
            author_user_id=comment.author_user_id,
            author=CommentAuthorResponse(
                user_id=author.id,
                display_name=author.display_name,
            ),
            body=comment.body,
            quoted_text=comment.quoted_text,
            status=comment.status,
            created_at=comment.created_at,
            updated_at=comment.updated_at,
            resolved_at=comment.resolved_at,
            resolved_by_user_id=comment.resolved_by_user_id,
        )

    def _raise_forbidden(self) -> None:
        raise ApiError(
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="PERMISSION_DENIED",
            message="You are not allowed to access this document.",
        )
