import secrets
from datetime import timedelta

from fastapi import status

from app.backend.core.contracts import parse_resource_id, prefixed_id, utc_now, utc_z
from app.backend.core.errors import ApiError
from app.backend.core.usernames import normalize_username_seed
from app.backend.models.user import User
from app.backend.repositories.document_repository import DocumentRepository
from app.backend.repositories.invitation_repository import InvitationRepository
from app.backend.repositories.permission_repository import PermissionRepository
from app.backend.repositories.user_repository import UserRepository
from app.backend.schemas.invitation import (
    InvitationAcceptResponse,
    InvitationCreateRequest,
    InvitationCreateResponse,
)
from app.backend.services.access_service import DocumentAccessService

INVITATION_EXPIRY_DAYS = 2


class InvitationService:
    def __init__(
        self,
        document_repository: DocumentRepository,
        invitation_repository: InvitationRepository,
        permission_repository: PermissionRepository,
        user_repository: UserRepository,
    ) -> None:
        self.document_repository = document_repository
        self.invitation_repository = invitation_repository
        self.permission_repository = permission_repository
        self.user_repository = user_repository
        self.access_service = DocumentAccessService(
            document_repository,
            permission_repository,
        )

    def send_invitation(
        self,
        *,
        document_id: str | int,
        payload: InvitationCreateRequest,
        current_user: User,
    ) -> InvitationCreateResponse:
        access = self.access_service.require_owner_access(
            document_id=document_id,
            user_id=current_user.id,
        )
        role = self.access_service.validate_role(payload.role)
        raw_invitee = payload.invitee.strip()
        normalized_email = raw_invitee.lower() if "@" in raw_invitee else ""
        normalized_username = (
            normalize_username_seed(raw_invitee) if "@" not in raw_invitee else ""
        )
        invited_user = (
            self.user_repository.get_by_email(normalized_email)
            if normalized_email
            else self.user_repository.get_by_username(normalized_username)
        )

        if invited_user is None:
            raise ApiError(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code="USER_NOT_FOUND",
                message=(
                    "No account exists for this email."
                    if normalized_email
                    else "No account exists for this username."
                ),
            )

        expires_at = utc_now() + timedelta(days=INVITATION_EXPIRY_DAYS)
        invitation = self.invitation_repository.create(
            document_id=access.document.id,
            email=invited_user.email.lower(),
            role=role,
            token=secrets.token_urlsafe(24),
            invited_by=current_user.id,
            expires_at=expires_at,
        )
        self.invitation_repository.db.commit()
        return self._to_create_response(invitation)

    def accept_invitation(
        self,
        *,
        invitation_id: str | int,
        current_user: User,
    ) -> InvitationAcceptResponse:
        invitation = self.invitation_repository.get_by_id(
            parse_resource_id(invitation_id, "inv")
        )
        if invitation is None:
            raise ApiError(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code="INVITATION_NOT_FOUND",
                message="Invitation not found.",
            )

        if invitation.status != "pending":
            raise ApiError(
                status_code=status.HTTP_409_CONFLICT,
                error_code="INVITATION_ALREADY_PROCESSED",
                message="Invitation has already been processed.",
            )

        if invitation.expires_at < utc_now():
            raise ApiError(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code="INVITATION_EXPIRED",
                message="Invitation has expired.",
            )

        if current_user.email.lower() != invitation.email.lower():
            raise ApiError(
                status_code=status.HTTP_403_FORBIDDEN,
                error_code="FORBIDDEN",
                message="You are not allowed to accept this invitation.",
            )

        permission = self.permission_repository.get_by_document_and_user(
            document_id=invitation.document_id,
            user_id=current_user.id,
        )
        if permission is None:
            self.permission_repository.create(
                document_id=invitation.document_id,
                user_id=current_user.id,
                grantee_type="user",
                role=invitation.role,
                ai_allowed=False,
            )
        else:
            self.permission_repository.update(
                permission,
                grantee_type="user",
                role=invitation.role,
            )

        updated_invitation = self.invitation_repository.update(
            invitation,
            status="accepted",
            accepted_at=utc_now(),
        )
        self.invitation_repository.db.commit()
        return InvitationAcceptResponse(
            invitation_id=prefixed_id("inv", updated_invitation.id),
            status=updated_invitation.status,
            document_id=prefixed_id("doc", updated_invitation.document_id),
            role=updated_invitation.role,
        )

    def _to_create_response(self, invitation) -> InvitationCreateResponse:
        return InvitationCreateResponse(
            invitation_id=prefixed_id("inv", invitation.id),
            document_id=prefixed_id("doc", invitation.document_id),
            invited_email=invitation.email,
            role=invitation.role,
            status=invitation.status,
            expires_at=utc_z(invitation.expires_at),
        )
