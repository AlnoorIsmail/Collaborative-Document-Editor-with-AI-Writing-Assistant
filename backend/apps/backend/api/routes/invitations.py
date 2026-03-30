from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from apps.backend.api.routes.auth import get_current_authenticated_user
from apps.backend.core.database import get_db
from apps.backend.models.user import User
from apps.backend.repositories.document_repository import DocumentRepository
from apps.backend.repositories.invitation_repository import InvitationRepository
from apps.backend.repositories.permission_repository import PermissionRepository
from apps.backend.repositories.user_repository import UserRepository
from apps.backend.schemas.invitation import InvitationAcceptResponse, InvitationCreateRequest, InvitationCreateResponse
from apps.backend.services.invitation_service import InvitationService

router = APIRouter(tags=["invitations"])


def get_invitation_service(db: Session = Depends(get_db)) -> InvitationService:
    return InvitationService(
        DocumentRepository(db),
        InvitationRepository(db),
        PermissionRepository(db),
        UserRepository(db),
    )


@router.post("/documents/{documentId}/invitations", response_model=InvitationCreateResponse, status_code=status.HTTP_201_CREATED)
def send_invitation(
    documentId: int,
    payload: InvitationCreateRequest,
    current_user: User = Depends(get_current_authenticated_user),
    invitation_service: InvitationService = Depends(get_invitation_service),
) -> InvitationCreateResponse:
    return invitation_service.send_invitation(
        document_id=documentId,
        payload=payload,
        current_user=current_user,
    )


@router.post("/invitations/{invitationId}/accept", response_model=InvitationAcceptResponse)
def accept_invitation(
    invitationId: str,
    current_user: User = Depends(get_current_authenticated_user),
    invitation_service: InvitationService = Depends(get_invitation_service),
) -> InvitationAcceptResponse:
    return invitation_service.accept_invitation(
        invitation_id=invitationId,
        current_user=current_user,
    )
