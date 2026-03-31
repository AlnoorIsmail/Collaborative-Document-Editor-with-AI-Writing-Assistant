"""Routes for realtime session bootstrap."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.backend.api.deps import get_current_principal, get_session_service
from app.backend.core.security import AuthenticatedPrincipal
from app.backend.schemas.realtime import (
    SessionBootstrapRequest,
    SessionBootstrapResponse,
)
from app.backend.services.realtime.session_service import SessionService

router = APIRouter(prefix="/documents/{document_id}/sessions", tags=["sessions"])


@router.post(
    "",
    response_model=SessionBootstrapResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_or_join_session(
    document_id: str,
    payload: SessionBootstrapRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    service: Annotated[SessionService, Depends(get_session_service)],
) -> SessionBootstrapResponse:
    return service.create_or_join_session(
        document_id=document_id,
        principal=principal,
        payload=payload,
    )
