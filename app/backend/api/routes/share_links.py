from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.backend.api.deps import (
    get_current_authenticated_user,
)
from app.backend.core.database import get_db
from app.backend.models.user import User
from app.backend.repositories.document_repository import DocumentRepository
from app.backend.repositories.permission_repository import PermissionRepository
from app.backend.repositories.share_link_repository import ShareLinkRepository
from app.backend.schemas.share_link import (
    ShareLinkCreateRequest,
    ShareLinkCreateResponse,
    ShareLinkRedeemResponse,
)
from app.backend.services.share_link_service import ShareLinkService

router = APIRouter(prefix="/share-links", tags=["Share Links"])


def get_share_link_service(db: Session = Depends(get_db)) -> ShareLinkService:
    return ShareLinkService(
        DocumentRepository(db),
        ShareLinkRepository(db),
        PermissionRepository(db),
    )


@router.post(
    "",
    response_model=ShareLinkCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a share link",
    description=(
        "Create a bearer-style share link that can grant the requested role until "
        "it expires or is revoked. Baseline-compliant share links always require "
        "the redeemer to be signed in."
    ),
)
def create_share_link(
    payload: ShareLinkCreateRequest,
    current_user: User = Depends(get_current_authenticated_user),
    share_link_service: ShareLinkService = Depends(get_share_link_service),
) -> ShareLinkCreateResponse:
    return share_link_service.create_share_link(
        payload=payload, current_user=current_user
    )


@router.post(
    "/{token}/redeem",
    response_model=ShareLinkRedeemResponse,
    summary="Redeem a share link",
    description=(
        "Validate a share-link token for the authenticated user and grant access "
        "when the token is still active."
    ),
)
def redeem_share_link(
    token: str,
    current_user: User = Depends(get_current_authenticated_user),
    share_link_service: ShareLinkService = Depends(get_share_link_service),
) -> ShareLinkRedeemResponse:
    return share_link_service.redeem_share_link(token=token, current_user=current_user)


@router.delete(
    "/{linkId}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke a share link",
    description="Revoke an existing share link so it can no longer grant access.",
)
def revoke_share_link(
    linkId: str,
    current_user: User = Depends(get_current_authenticated_user),
    share_link_service: ShareLinkService = Depends(get_share_link_service),
) -> Response:
    share_link_service.revoke_share_link(link_id=linkId, current_user=current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
