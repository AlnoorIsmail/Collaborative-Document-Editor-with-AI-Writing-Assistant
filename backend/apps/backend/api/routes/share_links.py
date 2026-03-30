from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from apps.backend.api.routes.auth import get_current_authenticated_user, get_optional_authenticated_user
from apps.backend.core.database import get_db
from apps.backend.models.user import User
from apps.backend.repositories.document_repository import DocumentRepository
from apps.backend.repositories.permission_repository import PermissionRepository
from apps.backend.repositories.share_link_repository import ShareLinkRepository
from apps.backend.schemas.share_link import ShareLinkCreateRequest, ShareLinkCreateResponse, ShareLinkRedeemResponse
from apps.backend.services.share_link_service import ShareLinkService

router = APIRouter(prefix="/share-links", tags=["share-links"])


def get_share_link_service(db: Session = Depends(get_db)) -> ShareLinkService:
    return ShareLinkService(
        DocumentRepository(db),
        ShareLinkRepository(db),
        PermissionRepository(db),
    )


@router.post("", response_model=ShareLinkCreateResponse, status_code=status.HTTP_201_CREATED)
def create_share_link(
    payload: ShareLinkCreateRequest,
    current_user: User = Depends(get_current_authenticated_user),
    share_link_service: ShareLinkService = Depends(get_share_link_service),
) -> ShareLinkCreateResponse:
    return share_link_service.create_share_link(payload=payload, current_user=current_user)


@router.post("/{token}/redeem", response_model=ShareLinkRedeemResponse)
def redeem_share_link(
    token: str,
    current_user: User = Depends(get_optional_authenticated_user),
    share_link_service: ShareLinkService = Depends(get_share_link_service),
) -> ShareLinkRedeemResponse:
    return share_link_service.redeem_share_link(token=token, current_user=current_user)
