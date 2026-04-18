from app.backend.core.contracts import prefixed_id, utc_z
from app.backend.models.user import User
from app.backend.repositories.document_repository import DocumentRepository
from app.backend.repositories.invitation_repository import InvitationRepository
from app.backend.repositories.permission_repository import PermissionRepository
from app.backend.repositories.share_link_repository import ShareLinkRepository
from app.backend.schemas.sharing import (
    SharingCollaboratorResponse,
    SharingInvitationResponse,
    SharingLinkResponse,
    SharingOverviewResponse,
    SharingUserResponse,
)
from app.backend.services.access_service import DocumentAccessService


class SharingService:
    def __init__(
        self,
        document_repository: DocumentRepository,
        permission_repository: PermissionRepository,
        invitation_repository: InvitationRepository,
        share_link_repository: ShareLinkRepository,
    ) -> None:
        self.document_repository = document_repository
        self.permission_repository = permission_repository
        self.invitation_repository = invitation_repository
        self.share_link_repository = share_link_repository
        self.access_service = DocumentAccessService(
            document_repository,
            permission_repository,
        )

    def get_sharing_overview(
        self,
        *,
        document_id: str | int,
        current_user: User,
    ) -> SharingOverviewResponse:
        access = self.access_service.require_owner_access(
            document_id=document_id,
            user_id=current_user.id,
        )
        document = access.document
        owner = document.owner

        collaborators = [
            SharingCollaboratorResponse(
                permission_id=prefixed_id("perm", permission.id),
                user=SharingUserResponse(
                    user_id=prefixed_id("usr", permission.user.id),
                    email=permission.user.email,
                    username=permission.user.username,
                    display_name=permission.user.display_name,
                ),
                role=permission.role,
                ai_allowed=permission.ai_allowed,
                granted_at=utc_z(permission.created_at),
            )
            for permission in self.permission_repository.list_for_document(document.id)
        ]
        invitations = [
            SharingInvitationResponse(
                invitation_id=prefixed_id("inv", invitation.id),
                invited_email=invitation.email,
                role=invitation.role,
                status=invitation.status,
                created_at=utc_z(invitation.created_at),
                expires_at=utc_z(invitation.expires_at),
            )
            for invitation in self.invitation_repository.list_for_document(document.id)
        ]
        share_links = [
            SharingLinkResponse(
                link_id=prefixed_id("link", share_link.id),
                token=share_link.token,
                role=share_link.role,
                require_sign_in=share_link.require_sign_in,
                revoked=share_link.revoked,
                created_at=utc_z(share_link.created_at),
                expires_at=utc_z(share_link.expires_at),
            )
            for share_link in self.share_link_repository.list_for_document(document.id)
        ]

        return SharingOverviewResponse(
            document_id=prefixed_id("doc", document.id),
            owner=SharingUserResponse(
                user_id=prefixed_id("usr", owner.id),
                email=owner.email,
                username=owner.username,
                display_name=owner.display_name,
            ),
            collaborators=collaborators,
            invitations=invitations,
            share_links=share_links,
        )
