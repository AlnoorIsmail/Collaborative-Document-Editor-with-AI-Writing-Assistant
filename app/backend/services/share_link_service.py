import secrets

from fastapi import status

from app.backend.core.contracts import (
    parse_resource_id,
    parse_utc_datetime,
    prefixed_id,
    utc_now,
    utc_z,
)
from app.backend.core.errors import ApiError
from app.backend.models.user import User
from app.backend.repositories.document_repository import DocumentRepository
from app.backend.repositories.permission_repository import PermissionRepository
from app.backend.repositories.share_link_repository import ShareLinkRepository
from app.backend.schemas.share_link import (
    ShareLinkCreateRequest,
    ShareLinkCreateResponse,
    ShareLinkRedeemResponse,
)
from app.backend.services.access_service import DocumentAccessService


class ShareLinkService:
    def __init__(
        self,
        document_repository: DocumentRepository,
        share_link_repository: ShareLinkRepository,
        permission_repository: PermissionRepository,
    ) -> None:
        self.document_repository = document_repository
        self.share_link_repository = share_link_repository
        self.permission_repository = permission_repository
        self.access_service = DocumentAccessService(
            document_repository,
            permission_repository,
        )

    def create_share_link(
        self,
        *,
        payload: ShareLinkCreateRequest,
        current_user: User,
    ) -> ShareLinkCreateResponse:
        document_id = parse_resource_id(payload.document_id, "doc")
        access = self.access_service.require_owner_access(
            document_id=document_id,
            user_id=current_user.id,
        )

        expires_at = parse_utc_datetime(payload.expires_at)
        role = self.access_service.validate_role(payload.role)
        share_link = self.share_link_repository.create(
            document_id=access.document.id,
            token=secrets.token_urlsafe(18),
            role=role,
            require_sign_in=payload.require_sign_in,
            expires_at=expires_at,
            created_by=current_user.id,
        )
        self.share_link_repository.db.commit()
        return self._to_create_response(share_link)

    def redeem_share_link(
        self,
        *,
        token: str,
        current_user: User = None,
    ) -> ShareLinkRedeemResponse:
        share_link = self.share_link_repository.get_by_token(token)
        if share_link is None:
            raise ApiError(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code="SHARE_LINK_NOT_FOUND",
                message="Share link not found.",
            )

        if share_link.revoked:
            raise ApiError(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code="SHARE_LINK_REVOKED",
                message="Share link has been revoked.",
            )

        if share_link.expires_at is not None and share_link.expires_at < utc_now():
            raise ApiError(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code="SHARE_LINK_EXPIRED",
                message="Share link has expired.",
            )

        if share_link.require_sign_in and current_user is None:
            raise ApiError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                error_code="UNAUTHORIZED",
                message="Authentication is required to redeem this share link.",
            )

        if share_link.require_sign_in and current_user is not None:
            permission = self.permission_repository.get_by_document_and_user(
                document_id=share_link.document_id,
                user_id=current_user.id,
            )
            if permission is None:
                self.permission_repository.create(
                    document_id=share_link.document_id,
                    user_id=current_user.id,
                    grantee_type="user",
                    role=share_link.role,
                    ai_allowed=False,
                )
            else:
                self.permission_repository.update(
                    permission,
                    role=share_link.role,
                    grantee_type="user",
                )
            self.share_link_repository.db.commit()

        return ShareLinkRedeemResponse(
            document_id=prefixed_id("doc", share_link.document_id),
            role=share_link.role,
            access_granted=True,
        )

    def _to_create_response(self, share_link) -> ShareLinkCreateResponse:
        return ShareLinkCreateResponse(
            link_id=prefixed_id("link", share_link.id),
            document_id=prefixed_id("doc", share_link.document_id),
            token=share_link.token,
            role=share_link.role,
            require_sign_in=share_link.require_sign_in,
            expires_at=utc_z(share_link.expires_at),
            revoked=share_link.revoked,
        )
