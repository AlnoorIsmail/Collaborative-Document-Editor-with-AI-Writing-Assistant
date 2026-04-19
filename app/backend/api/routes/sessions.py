"""Routes for realtime session bootstrap and collaboration sockets."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, WebSocket
from fastapi import status

from app.backend.api.deps import (
    get_auth_service,
    get_collaboration_service,
    get_current_authenticated_user,
    get_session_service,
)
from app.backend.services.auth_service import AuthService
from app.backend.models.user import User
from app.backend.schemas.realtime import (
    SessionBootstrapRequest,
    SessionBootstrapResponse,
)
from app.backend.services.realtime.collaboration_service import CollaborationService
from app.backend.services.realtime.session_service import SessionService

router = APIRouter(prefix="/documents/{documentId}/sessions", tags=["sessions"])


@router.post(
    "",
    response_model=SessionBootstrapResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Bootstrap a realtime collaboration session",
    description=(
        "Create or resume an authenticated document collaboration session and "
        "return the short-lived websocket session token plus the current "
        "collaboration snapshot."
    ),
)
def create_or_join_session(
    documentId: str,
    payload: SessionBootstrapRequest,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    service: Annotated[SessionService, Depends(get_session_service)],
) -> SessionBootstrapResponse:
    return service.create_or_join_session(
        document_id=documentId,
        current_user=current_user,
        payload=payload,
    )


@router.websocket("/{sessionId}/ws")
async def document_realtime_socket(
    websocket: WebSocket,
    documentId: str,
    sessionId: str,
    session_token: str = Query(...),
    access_token: str = Query(...),
    auth_service: AuthService = Depends(get_auth_service),
    collaboration_service: CollaborationService = Depends(get_collaboration_service),
) -> None:
    try:
        current_user = auth_service.get_current_user(access_token)
    except Exception:
        await websocket.close(code=4401, reason="Missing or invalid bearer token.")
        return

    await collaboration_service.serve_websocket(
        websocket=websocket,
        document_id=documentId,
        session_id=sessionId,
        session_token=session_token,
        current_user=current_user,
    )
