from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect, status

from app.backend.core.contracts import parse_resource_id, utc_now, utc_z
from app.backend.core.errors import ApiError
from app.backend.models.user import User
from app.backend.repositories.sessions import SessionRepository
from app.backend.schemas.document import DocumentContentSaveRequest
from app.backend.services.document_service import DocumentService


@dataclass
class _ConnectedCollaborator:
    websocket: WebSocket
    document_id: int
    session_id: str
    user_id: int
    display_name: str
    last_known_revision: int
    joined_at: datetime
    last_seen_at: datetime
    typing: bool = False


class RealtimeHub:
    def __init__(self) -> None:
        self._connections_by_document: dict[int, dict[str, _ConnectedCollaborator]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, collaborator: _ConnectedCollaborator) -> None:
        async with self._lock:
            self._connections_by_document.setdefault(collaborator.document_id, {})[
                collaborator.session_id
            ] = collaborator

    async def disconnect(self, document_id: int, session_id: str) -> None:
        async with self._lock:
            document_connections = self._connections_by_document.get(document_id)
            if not document_connections:
                return
            document_connections.pop(session_id, None)
            if not document_connections:
                self._connections_by_document.pop(document_id, None)

    async def update_state(
        self,
        *,
        document_id: int,
        session_id: str,
        last_known_revision: int | None = None,
        typing: bool | None = None,
    ) -> list[dict[str, Any]]:
        async with self._lock:
            collaborator = self._connections_by_document.get(document_id, {}).get(session_id)
            if collaborator is None:
                return []
            if last_known_revision is not None:
                collaborator.last_known_revision = last_known_revision
            if typing is not None:
                collaborator.typing = typing
            collaborator.last_seen_at = utc_now()
            return self._presence_snapshot(document_id)

    async def get_presence_snapshot(self, document_id: int) -> list[dict[str, Any]]:
        async with self._lock:
            return self._presence_snapshot(document_id)

    async def send_json(
        self,
        *,
        document_id: int,
        session_id: str,
        payload: dict[str, Any],
    ) -> None:
        async with self._lock:
            collaborator = self._connections_by_document.get(document_id, {}).get(session_id)
            websocket = collaborator.websocket if collaborator else None
        if websocket is not None:
            await websocket.send_json(payload)

    async def broadcast_json(self, *, document_id: int, payload: dict[str, Any]) -> None:
        async with self._lock:
            sockets = [
                collaborator.websocket
                for collaborator in self._connections_by_document.get(document_id, {}).values()
            ]
        for websocket in sockets:
            await websocket.send_json(payload)

    def _presence_snapshot(self, document_id: int) -> list[dict[str, Any]]:
        collaborators = self._connections_by_document.get(document_id, {})
        return [
            {
                "user_id": collaborator.user_id,
                "display_name": collaborator.display_name,
                "session_id": collaborator.session_id,
                "last_known_revision": collaborator.last_known_revision,
                "joined_at": utc_z(collaborator.joined_at),
                "last_seen_at": utc_z(collaborator.last_seen_at),
                "typing": collaborator.typing,
            }
            for collaborator in sorted(
                collaborators.values(),
                key=lambda candidate: (candidate.joined_at, candidate.user_id),
            )
        ]


class CollaborationService:
    def __init__(
        self,
        *,
        session_repository: SessionRepository,
        document_service: DocumentService,
        hub: RealtimeHub,
    ) -> None:
        self._session_repository = session_repository
        self._document_service = document_service
        self._hub = hub

    async def serve_websocket(
        self,
        *,
        websocket: WebSocket,
        document_id: str,
        session_id: str,
        session_token: str,
        current_user: User,
    ) -> None:
        resolved_document_id = parse_resource_id(document_id, "doc")
        session = self._session_repository.validate_session(
            document_id=resolved_document_id,
            user_id=current_user.id,
            session_id=session_id,
            session_token=session_token,
        )
        if session is None:
            await websocket.close(code=4401, reason="Invalid realtime session.")
            return

        access = self._document_service.ensure_read_access(
            document_id=document_id,
            current_user=current_user,
        )

        await websocket.accept()
        await self._hub.connect(
            _ConnectedCollaborator(
                websocket=websocket,
                document_id=access.document.id,
                session_id=session.session_id,
                user_id=current_user.id,
                display_name=current_user.display_name,
                last_known_revision=access.current_revision,
                joined_at=session.joined_at,
                last_seen_at=session.last_seen_at,
            )
        )
        await self._hub.send_json(
            document_id=access.document.id,
            session_id=session.session_id,
            payload={
                "type": "session_joined",
                "session_id": session.session_id,
                "document_id": access.document.id,
                "revision": access.current_revision,
                "content": access.document.content,
                "line_spacing": access.document.line_spacing,
                "presence": await self._hub.get_presence_snapshot(access.document.id),
            },
        )
        await self._broadcast_presence(access.document.id)

        try:
            while True:
                message = await websocket.receive_json()
                await self._handle_message(
                    document_id=document_id,
                    resolved_document_id=access.document.id,
                    session_id=session.session_id,
                    current_user=current_user,
                    payload=message,
                )
        except WebSocketDisconnect:
            await self._hub.disconnect(access.document.id, session.session_id)
            await self._broadcast_presence(access.document.id)

    async def _handle_message(
        self,
        *,
        document_id: str,
        resolved_document_id: int,
        session_id: str,
        current_user: User,
        payload: dict[str, Any],
    ) -> None:
        message_type = str(payload.get("type") or "").strip().lower()

        if message_type == "heartbeat":
            last_known_revision = payload.get("last_known_revision")
            if isinstance(last_known_revision, int):
                self._session_repository.mark_session_seen(
                    session_id=session_id,
                    last_known_revision=last_known_revision,
                )
                await self._hub.update_state(
                    document_id=resolved_document_id,
                    session_id=session_id,
                    last_known_revision=last_known_revision,
                )
            return

        if message_type == "typing":
            await self._hub.update_state(
                document_id=resolved_document_id,
                session_id=session_id,
                typing=bool(payload.get("active")),
            )
            await self._broadcast_presence(resolved_document_id)
            return

        if message_type == "request_resync":
            access = self._document_service.ensure_read_access(
                document_id=document_id,
                current_user=current_user,
            )
            await self._hub.send_json(
                document_id=resolved_document_id,
                session_id=session_id,
                payload={
                    "type": "content_updated",
                    "document_id": access.document.id,
                    "content": access.document.content,
                    "line_spacing": access.document.line_spacing,
                    "revision": access.current_revision,
                    "latest_version_id": access.document.latest_version_id,
                    "actor_user_id": None,
                    "actor_display_name": None,
                    "saved_at": utc_z(access.document.updated_at),
                },
            )
            return

        if message_type != "content_update":
            await self._hub.send_json(
                document_id=resolved_document_id,
                session_id=session_id,
                payload={
                    "type": "error",
                    "code": "UNKNOWN_MESSAGE_TYPE",
                    "message": "Unsupported realtime message type.",
                },
            )
            return

        try:
            response = self._document_service.save_document_content(
                document_id=document_id,
                payload=DocumentContentSaveRequest(
                    content=str(payload.get("content") or ""),
                    base_revision=int(payload.get("base_revision")),
                    line_spacing=payload.get("line_spacing"),
                    save_source=str(payload.get("save_source") or "autosave"),
                ),
                current_user=current_user,
            )
        except (TypeError, ValueError):
            await self._hub.send_json(
                document_id=resolved_document_id,
                session_id=session_id,
                payload={
                    "type": "error",
                    "code": "VALIDATION_ERROR",
                    "message": "Realtime update payload is invalid.",
                },
            )
            return
        except ApiError as error:
            if error.status_code != status.HTTP_409_CONFLICT:
                await self._hub.send_json(
                    document_id=resolved_document_id,
                    session_id=session_id,
                    payload={
                        "type": "error",
                        "code": error.error_code,
                        "message": error.detail["message"],
                    },
                )
                return

            access = self._document_service.ensure_read_access(
                document_id=document_id,
                current_user=current_user,
            )
            await self._hub.send_json(
                document_id=resolved_document_id,
                session_id=session_id,
                payload={
                    "type": "conflict_detected",
                    "message": error.detail["message"],
                    "revision": access.current_revision,
                    "content": access.document.content,
                    "line_spacing": access.document.line_spacing,
                    "latest_version_id": access.document.latest_version_id,
                },
            )
            return

        access = self._document_service.ensure_read_access(
            document_id=document_id,
            current_user=current_user,
        )
        self._session_repository.mark_session_seen(
            session_id=session_id,
            last_known_revision=response.revision,
        )
        await self._hub.update_state(
            document_id=resolved_document_id,
            session_id=session_id,
            last_known_revision=response.revision,
            typing=False,
        )
        await self._hub.broadcast_json(
            document_id=resolved_document_id,
            payload={
                "type": "content_updated",
                "document_id": access.document.id,
                "content": access.document.content,
                "line_spacing": access.document.line_spacing,
                "revision": response.revision,
                "latest_version_id": response.latest_version_id,
                "actor_user_id": current_user.id,
                "actor_display_name": current_user.display_name,
                "saved_at": utc_z(response.saved_at),
            },
        )
        await self._broadcast_presence(resolved_document_id)

    async def _broadcast_presence(self, document_id: int) -> None:
        await self._hub.broadcast_json(
            document_id=document_id,
            payload={
                "type": "presence_snapshot",
                "presence": await self._hub.get_presence_snapshot(document_id),
            },
        )
