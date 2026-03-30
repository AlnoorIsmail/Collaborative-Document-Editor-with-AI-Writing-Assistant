import secrets
from datetime import datetime, timedelta

from fastapi import status

from apps.backend.core.contracts import parse_prefixed_id, prefixed_id, utc_z
from apps.backend.core.errors import ApiError
from apps.backend.models.user import User
from apps.backend.repositories.document_repository import DocumentRepository
from apps.backend.repositories.invitation_repository import InvitationRepository
from apps.backend.repositories.permission_repository import PermissionRepository
from apps.backend.repositories.user_repository import UserRepository
from apps.backend.schemas.invitation import InvitationAcceptResponse, InvitationCreateRequest, InvitationCreateResponse
from apps.backend.services.document_service import DocumentService

INVITATION_EXPIRY_DAYS = 2


class InvitationService:
    def __init__(
        self,
        document_repository: DocumentRepository,
        invitation_repository: InvitationRepository,
        permission_repository: PermissionRepository,
        user_repository: UserRepository,
    ):
        self.document_repository = document_repository
        self.invitation_repository = invitation_repository
        self.permission_repository = permission_repository
        self.user_repository = user_repository
        self.document_service = DocumentService(document_repository, None)

    def send_invitation(
        self,
        *,
        document_id: int,
        payload: InvitationCreateRequest,
        current_user: User,
    ) -> InvitationCreateResponse:
        document = self.document_repository.get_by_id(document_id)
        self.document_service._ensure_owner_access(document=document, current_user=current_user)

        expires_at = datetime.utcnow() + timedelta(days=INVITATION_EXPIRY_DAYS)
        invitation = self.invitation_repository.create(
            document_id=document.id,
            email=payload.invited_email.lower(),
            role=payload.role,
            token=secrets.token_urlsafe(24),
            invited_by=current_user.id,
            expires_at=expires_at,
        )
        self.invitation_repository.db.commit()
        return self._to_create_response(invitation)

    def accept_invitation(
        self,
        *,
        invitation_id: str,
        current_user: User,
    ) -> InvitationAcceptResponse:
        invitation_pk = parse_prefixed_id(invitation_id, "inv")
        invitation = self.invitation_repository.get_by_id(invitation_pk)
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

        if invitation.expires_at < datetime.utcnow():
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
            accepted_at=datetime.utcnow(),
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
