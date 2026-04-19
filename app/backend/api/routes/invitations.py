from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.backend.api.deps import get_current_authenticated_user
from app.backend.core.database import get_db
from app.backend.models.user import User
from app.backend.repositories.document_repository import DocumentRepository
from app.backend.repositories.invitation_repository import InvitationRepository
from app.backend.repositories.permission_repository import PermissionRepository
from app.backend.repositories.user_repository import UserRepository
from app.backend.schemas.invitation import (
    InvitationAcceptResponse,
    InvitationDeclineResponse,
    InvitationCreateRequest,
    InvitationCreateResponse,
    InvitationInboxItemResponse,
)
from app.backend.services.invitation_service import InvitationService

router = APIRouter(tags=["Invitations"])


def get_invitation_service(db: Session = Depends(get_db)) -> InvitationService:
    return InvitationService(
        DocumentRepository(db),
        InvitationRepository(db),
        PermissionRepository(db),
        UserRepository(db),
    )


@router.post(
    "/documents/{documentId}/invitations",
    response_model=InvitationCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def send_invitation(
    documentId: str,
    payload: InvitationCreateRequest,
    current_user: User = Depends(get_current_authenticated_user),
    invitation_service: InvitationService = Depends(get_invitation_service),
) -> InvitationCreateResponse:
    return invitation_service.send_invitation(
        document_id=documentId,
        payload=payload,
        current_user=current_user,
    )


@router.get(
    "/invitations",
    response_model=list[InvitationInboxItemResponse],
)
def list_invitations(
    current_user: User = Depends(get_current_authenticated_user),
    invitation_service: InvitationService = Depends(get_invitation_service),
) -> list[InvitationInboxItemResponse]:
    return invitation_service.list_pending_invitations(current_user=current_user)


@router.post(
    "/invitations/{invitationId}/accept", response_model=InvitationAcceptResponse
)
def accept_invitation(
    invitationId: str,
    current_user: User = Depends(get_current_authenticated_user),
    invitation_service: InvitationService = Depends(get_invitation_service),
) -> InvitationAcceptResponse:
    return invitation_service.accept_invitation(
        invitation_id=invitationId,
        current_user=current_user,
    )


@router.post(
    "/invitations/{invitationId}/decline", response_model=InvitationDeclineResponse
)
def decline_invitation(
    invitationId: str,
    current_user: User = Depends(get_current_authenticated_user),
    invitation_service: InvitationService = Depends(get_invitation_service),
) -> InvitationDeclineResponse:
    return invitation_service.decline_invitation(
        invitation_id=invitationId,
        current_user=current_user,
    )
