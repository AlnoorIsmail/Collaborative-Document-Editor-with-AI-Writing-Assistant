from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.backend.api.deps import get_current_authenticated_user
from app.backend.core.database import get_db
from app.backend.models.user import User
from app.backend.repositories.document_repository import DocumentRepository
from app.backend.repositories.invitation_repository import InvitationRepository
from app.backend.repositories.permission_repository import PermissionRepository
from app.backend.repositories.share_link_repository import ShareLinkRepository
from app.backend.schemas.sharing import SharingOverviewResponse
from app.backend.services.sharing_service import SharingService

router = APIRouter(prefix="/documents", tags=["Sharing"])


def get_sharing_service(
    db: Annotated[Session, Depends(get_db)],
) -> SharingService:
    return SharingService(
        DocumentRepository(db),
        PermissionRepository(db),
        InvitationRepository(db),
        ShareLinkRepository(db),
    )


@router.get(
    "/{documentId}/sharing",
    response_model=SharingOverviewResponse,
    summary="Get document sharing overview",
    description=(
        "Return the current owner-managed sharing state including collaborators, "
        "pending invitations, and active share links."
    ),
)
def get_sharing_overview(
    documentId: str,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    sharing_service: Annotated[SharingService, Depends(get_sharing_service)],
) -> SharingOverviewResponse:
    return sharing_service.get_sharing_overview(
        document_id=documentId,
        current_user=current_user,
    )
