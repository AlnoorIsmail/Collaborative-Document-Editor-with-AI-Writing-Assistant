from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
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


@dataclass
class _CollabStepBatch:
    batch_id: str
    start_version: int
    steps: list[dict[str, Any]]
    client_id: str
    actor_user_id: int
    actor_display_name: str
    affected_range: dict[str, int]
    candidate_content_snapshot: str
    exact_text_snapshot: str
    prefix_context: str
    suffix_context: str
    created_at: datetime


@dataclass
class _DocumentCollabState:
    version: int
    content: str
    line_spacing: float
    updated_at: datetime
    step_batches: list[_CollabStepBatch] = field(default_factory=list)


class RealtimeHub:
    def __init__(self) -> None:
        self._connections_by_document: dict[int, dict[str, _ConnectedCollaborator]] = {}
        self._collab_state_by_document: dict[int, _DocumentCollabState] = {}
        self._lock = Lock()

    def ensure_document_state_sync(
        self,
        *,
        document_id: int,
        content: str,
        line_spacing: float,
        updated_at: datetime,
    ) -> dict[str, Any]:
        with self._lock:
            state = self._collab_state_by_document.get(document_id)
            if state is None or updated_at > state.updated_at:
                state = _DocumentCollabState(
                    version=0,
                    content=content,
                    line_spacing=line_spacing,
                    updated_at=updated_at,
                )
                self._collab_state_by_document[document_id] = state
            return self._snapshot(state)

    async def ensure_document_state(
        self,
        *,
        document_id: int,
        content: str,
        line_spacing: float,
        updated_at: datetime,
    ) -> dict[str, Any]:
        return self.ensure_document_state_sync(
            document_id=document_id,
            content=content,
            line_spacing=line_spacing,
            updated_at=updated_at,
        )

    async def connect(self, collaborator: _ConnectedCollaborator) -> None:
        with self._lock:
            self._connections_by_document.setdefault(collaborator.document_id, {})[
                collaborator.session_id
            ] = collaborator

    async def disconnect(self, document_id: int, session_id: str) -> None:
        with self._lock:
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
        with self._lock:
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
        with self._lock:
            return self._presence_snapshot(document_id)

    async def get_collab_snapshot(self, document_id: int) -> dict[str, Any] | None:
        with self._lock:
            state = self._collab_state_by_document.get(document_id)
            return None if state is None else self._snapshot(state)

    async def get_steps_since(
        self,
        *,
        document_id: int,
        version: int,
    ) -> dict[str, Any]:
        with self._lock:
            state = self._collab_state_by_document.get(document_id)
            if state is None:
                return {
                    "full_reset": True,
                    "version": 0,
                    "content": "",
                    "line_spacing": 1.15,
                    "steps": [],
                    "client_ids": [],
                    "batches": [],
                }

            if version == state.version:
                return {
                    **self._snapshot(state),
                    "full_reset": False,
                    "steps": [],
                    "client_ids": [],
                    "batches": [],
                }

            earliest_version = (
                state.step_batches[0].start_version
                if state.step_batches
                else state.version
            )
            if version > state.version or version < earliest_version:
                return {
                    **self._snapshot(state),
                    "full_reset": True,
                    "steps": [],
                    "client_ids": [],
                    "batches": [],
                }

            missing_steps: list[dict[str, Any]] = []
            missing_client_ids: list[str] = []
            missing_batches: list[dict[str, Any]] = []
            for batch in state.step_batches:
                batch_end = batch.start_version + len(batch.steps)
                if batch_end <= version:
                    continue
                slice_start = max(version - batch.start_version, 0)
                missing_steps.extend(batch.steps[slice_start:])
                missing_client_ids.extend([batch.client_id for _ in batch.steps[slice_start:]])
                missing_batches.append(self._serialize_batch(batch))

            return {
                **self._snapshot(state),
                "full_reset": False,
                "steps": missing_steps,
                "client_ids": missing_client_ids,
                "batches": missing_batches,
            }

    async def apply_steps(
        self,
        *,
        document_id: int,
        version: int,
        batch_id: str,
        steps: list[dict[str, Any]],
        client_id: str,
        content: str,
        line_spacing: float,
        actor_user_id: int,
        actor_display_name: str,
        affected_range: dict[str, int],
        candidate_content_snapshot: str,
        exact_text_snapshot: str,
        prefix_context: str,
        suffix_context: str,
    ) -> dict[str, Any]:
        with self._lock:
            state = self._collab_state_by_document.get(document_id)
            if state is None:
                state = _DocumentCollabState(
                    version=0,
                    content=content,
                    line_spacing=line_spacing,
                    updated_at=utc_now(),
                )
                self._collab_state_by_document[document_id] = state

            if version != state.version:
                return {
                    "accepted": False,
                    **self._snapshot(state),
                    **self._missing_steps_payload(state, version),
                }

            batch = _CollabStepBatch(
                batch_id=batch_id,
                start_version=state.version,
                steps=steps,
                client_id=client_id,
                actor_user_id=actor_user_id,
                actor_display_name=actor_display_name,
                affected_range=affected_range,
                candidate_content_snapshot=candidate_content_snapshot,
                exact_text_snapshot=exact_text_snapshot,
                prefix_context=prefix_context,
                suffix_context=suffix_context,
                created_at=utc_now(),
            )
            state.step_batches.append(batch)
            state.version += len(steps)
            state.content = content
            state.line_spacing = line_spacing
            state.updated_at = utc_now()

            return {
                "accepted": True,
                **self._snapshot(state),
                "steps": steps,
                "client_ids": [client_id for _ in steps],
                "batch": self._serialize_batch(batch),
            }

    async def update_line_spacing(
        self,
        *,
        document_id: int,
        line_spacing: float,
    ) -> dict[str, Any]:
        with self._lock:
            state = self._collab_state_by_document.get(document_id)
            if state is None:
                state = _DocumentCollabState(
                    version=0,
                    content="",
                    line_spacing=line_spacing,
                    updated_at=utc_now(),
                )
                self._collab_state_by_document[document_id] = state
            else:
                state.line_spacing = line_spacing
                state.updated_at = utc_now()
            return self._snapshot(state)

    async def reset_snapshot(
        self,
        *,
        document_id: int,
        content: str,
        line_spacing: float,
        updated_at: datetime,
    ) -> dict[str, Any]:
        with self._lock:
            state = _DocumentCollabState(
                version=0,
                content=content,
                line_spacing=line_spacing,
                updated_at=updated_at,
            )
            self._collab_state_by_document[document_id] = state
            return self._snapshot(state)

    async def send_json(
        self,
        *,
        document_id: int,
        session_id: str,
        payload: dict[str, Any],
    ) -> None:
        with self._lock:
            collaborator = self._connections_by_document.get(document_id, {}).get(session_id)
            websocket = collaborator.websocket if collaborator else None
        if websocket is not None:
            await websocket.send_json(payload)

    async def broadcast_json(self, *, document_id: int, payload: dict[str, Any]) -> None:
        with self._lock:
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

    def _snapshot(self, state: _DocumentCollabState) -> dict[str, Any]:
        return {
            "version": state.version,
            "content": state.content,
            "line_spacing": state.line_spacing,
            "updated_at": utc_z(state.updated_at),
        }

    def _serialize_batch(self, batch: _CollabStepBatch) -> dict[str, Any]:
        return {
            "batch_id": batch.batch_id,
            "version": batch.start_version,
            "client_id": batch.client_id,
            "affected_range": batch.affected_range,
            "candidate_content_snapshot": batch.candidate_content_snapshot,
            "exact_text_snapshot": batch.exact_text_snapshot,
            "prefix_context": batch.prefix_context,
            "suffix_context": batch.suffix_context,
            "actor_user_id": batch.actor_user_id,
            "actor_display_name": batch.actor_display_name,
            "created_at": utc_z(batch.created_at),
        }

    def _missing_steps_payload(
        self,
        state: _DocumentCollabState,
        version: int,
    ) -> dict[str, Any]:
        earliest_version = (
            state.step_batches[0].start_version
            if state.step_batches
            else state.version
        )
        if version > state.version or version < earliest_version:
            return {
                "full_reset": True,
                "steps": [],
                "client_ids": [],
                "batches": [],
            }

        missing_steps: list[dict[str, Any]] = []
        missing_client_ids: list[str] = []
        missing_batches: list[dict[str, Any]] = []
        for batch in state.step_batches:
            batch_end = batch.start_version + len(batch.steps)
            if batch_end <= version:
                continue
            slice_start = max(version - batch.start_version, 0)
            missing_steps.extend(batch.steps[slice_start:])
            missing_client_ids.extend([batch.client_id for _ in batch.steps[slice_start:]])
            missing_batches.append(self._serialize_batch(batch))

        return {
            "full_reset": False,
            "steps": missing_steps,
            "client_ids": missing_client_ids,
            "batches": missing_batches,
        }


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
        collab_state = await self._hub.ensure_document_state(
            document_id=access.document.id,
            content=access.document.content,
            line_spacing=access.document.line_spacing,
            updated_at=access.document.updated_at,
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
                "content": collab_state["content"],
                "line_spacing": collab_state["line_spacing"],
                "collab_version": collab_state["version"],
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
            requested_version = self._coerce_int(payload.get("version"), default=0)
            missing = await self._hub.get_steps_since(
                document_id=resolved_document_id,
                version=requested_version,
            )
            await self._hub.send_json(
                document_id=resolved_document_id,
                session_id=session_id,
                payload={
                    "type": "steps_resync",
                    "collab_version": missing["version"],
                    "full_reset": missing["full_reset"],
                    "steps": missing["steps"],
                    "client_ids": missing["client_ids"],
                    "batches": missing.get("batches", []),
                    "content": missing["content"],
                    "line_spacing": missing["line_spacing"],
                    "revision": access.current_revision,
                    "latest_version_id": access.document.latest_version_id,
                },
            )
            return

        if message_type == "line_spacing_update":
            try:
                line_spacing = float(payload.get("line_spacing"))
            except (TypeError, ValueError):
                await self._send_validation_error(
                    document_id=resolved_document_id,
                    session_id=session_id,
                    message="Realtime line-spacing payload is invalid.",
                )
                return

            access = self._document_service.ensure_edit_access(
                document_id=document_id,
                current_user=current_user,
            )
            collab_state = await self._hub.update_line_spacing(
                document_id=resolved_document_id,
                line_spacing=line_spacing,
            )
            persisted_access = self._document_service.persist_live_snapshot(
                document_id=document_id,
                current_user=current_user,
                content=collab_state["content"],
                line_spacing=collab_state["line_spacing"],
            )
            self._session_repository.mark_session_seen(
                session_id=session_id,
                last_known_revision=persisted_access.current_revision,
            )
            await self._hub.broadcast_json(
                document_id=resolved_document_id,
                payload={
                    "type": "line_spacing_updated",
                    "document_id": resolved_document_id,
                    "line_spacing": collab_state["line_spacing"],
                    "collab_version": collab_state["version"],
                    "actor_user_id": current_user.id,
                    "actor_display_name": current_user.display_name,
                },
            )
            await self._broadcast_presence(resolved_document_id)
            return

        if message_type == "snapshot_update":
            access = self._document_service.ensure_edit_access(
                document_id=document_id,
                current_user=current_user,
            )
            content_snapshot = str(payload.get("content") or access.document.content)
            try:
                line_spacing = float(payload.get("line_spacing") or access.document.line_spacing)
            except (TypeError, ValueError):
                await self._send_validation_error(
                    document_id=resolved_document_id,
                    session_id=session_id,
                    message="Realtime snapshot payload is invalid.",
                )
                return

            collab_state = await self._hub.reset_snapshot(
                document_id=resolved_document_id,
                content=content_snapshot,
                line_spacing=line_spacing,
                updated_at=utc_now(),
            )
            await self._hub.broadcast_json(
                document_id=resolved_document_id,
                payload={
                    "type": "content_updated",
                    "document_id": resolved_document_id,
                    "content": collab_state["content"],
                    "line_spacing": collab_state["line_spacing"],
                    "revision": access.current_revision,
                    "latest_version_id": access.document.latest_version_id,
                    "actor_user_id": current_user.id,
                    "actor_display_name": current_user.display_name,
                    "saved_at": collab_state["updated_at"],
                    "collab_version": collab_state["version"],
                    "collab_reset": True,
                },
            )
            await self._broadcast_presence(resolved_document_id)
            return

        if message_type == "step_update":
            access = self._document_service.ensure_edit_access(
                document_id=document_id,
                current_user=current_user,
            )
            steps = payload.get("steps")
            version = self._coerce_int(payload.get("version"), default=None)
            if (
                version is None
                or not isinstance(steps, list)
                or not steps
                or not all(isinstance(step, dict) for step in steps)
            ):
                await self._send_validation_error(
                    document_id=resolved_document_id,
                    session_id=session_id,
                    message="Realtime step payload is invalid.",
                )
                return

            content_snapshot = str(payload.get("content") or access.document.content)
            client_id = str(payload.get("client_id") or session_id)
            batch_id = str(payload.get("batch_id") or "").strip()
            line_spacing = float(payload.get("line_spacing") or access.document.line_spacing)
            affected_range = self._parse_text_range(payload.get("affected_range"))
            candidate_content_snapshot = str(payload.get("candidate_content_snapshot") or "")
            exact_text_snapshot = str(payload.get("exact_text_snapshot") or "")
            prefix_context = str(payload.get("prefix_context") or "")
            suffix_context = str(payload.get("suffix_context") or "")

            if not batch_id or affected_range is None:
                await self._send_validation_error(
                    document_id=resolved_document_id,
                    session_id=session_id,
                    message="Realtime step payload is missing range metadata.",
                )
                return

            result = await self._hub.apply_steps(
                document_id=resolved_document_id,
                version=version,
                batch_id=batch_id,
                steps=steps,
                client_id=client_id,
                content=content_snapshot,
                line_spacing=line_spacing,
                actor_user_id=current_user.id,
                actor_display_name=current_user.display_name,
                affected_range=affected_range,
                candidate_content_snapshot=candidate_content_snapshot,
                exact_text_snapshot=exact_text_snapshot,
                prefix_context=prefix_context,
                suffix_context=suffix_context,
            )

            if not result["accepted"]:
                await self._hub.send_json(
                    document_id=resolved_document_id,
                    session_id=session_id,
                    payload={
                        "type": "steps_resync",
                        "collab_version": result["version"],
                        "full_reset": result["full_reset"],
                        "steps": result["steps"],
                        "client_ids": result["client_ids"],
                        "batches": result.get("batches", []),
                        "content": result["content"],
                        "line_spacing": result["line_spacing"],
                        "revision": access.current_revision,
                        "latest_version_id": access.document.latest_version_id,
                    },
                )
                return

            persisted_access = self._document_service.persist_live_snapshot(
                document_id=document_id,
                current_user=current_user,
                content=result["content"],
                line_spacing=result["line_spacing"],
            )
            self._session_repository.mark_session_seen(
                session_id=session_id,
                last_known_revision=persisted_access.current_revision,
            )
            await self._hub.update_state(
                document_id=resolved_document_id,
                session_id=session_id,
                last_known_revision=persisted_access.current_revision,
                typing=False,
            )
            await self._hub.broadcast_json(
                document_id=resolved_document_id,
                payload={
                    "type": "steps_applied",
                    "document_id": resolved_document_id,
                    "steps": result["steps"],
                    "client_ids": result["client_ids"],
                    "batch": result.get("batch"),
                    "collab_version": result["version"],
                    "content": result["content"],
                    "line_spacing": result["line_spacing"],
                    "actor_user_id": current_user.id,
                    "actor_display_name": current_user.display_name,
                },
            )
            await self._broadcast_presence(resolved_document_id)
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
            await self._send_validation_error(
                document_id=resolved_document_id,
                session_id=session_id,
                message="Realtime update payload is invalid.",
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
            collab_state = await self._hub.ensure_document_state(
                document_id=resolved_document_id,
                content=access.document.content,
                line_spacing=access.document.line_spacing,
                updated_at=access.document.updated_at,
            )
            await self._hub.send_json(
                document_id=resolved_document_id,
                session_id=session_id,
                payload={
                    "type": "conflict_detected",
                    "message": error.detail["message"],
                    "revision": access.current_revision,
                    "content": collab_state["content"],
                    "line_spacing": collab_state["line_spacing"],
                    "latest_version_id": access.document.latest_version_id,
                    "collab_version": collab_state["version"],
                },
            )
            return

        access = self._document_service.ensure_read_access(
            document_id=document_id,
            current_user=current_user,
        )
        collab_state = await self._hub.reset_snapshot(
            document_id=resolved_document_id,
            content=access.document.content,
            line_spacing=access.document.line_spacing,
            updated_at=access.document.updated_at,
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
                "collab_version": collab_state["version"],
                "collab_reset": True,
            },
        )
        await self._broadcast_presence(resolved_document_id)

    async def _send_validation_error(
        self,
        *,
        document_id: int,
        session_id: str,
        message: str,
    ) -> None:
        await self._hub.send_json(
            document_id=document_id,
            session_id=session_id,
            payload={
                "type": "error",
                "code": "VALIDATION_ERROR",
                "message": message,
            },
        )

    async def _broadcast_presence(self, document_id: int) -> None:
        await self._hub.broadcast_json(
            document_id=document_id,
            payload={
                "type": "presence_snapshot",
                "presence": await self._hub.get_presence_snapshot(document_id),
            },
        )

    def _coerce_int(self, value: Any, *, default: int | None) -> int | None:
        try:
            if value is None:
                return default
            return int(value)
        except (TypeError, ValueError):
            return default

    def _parse_text_range(self, value: Any) -> dict[str, int] | None:
        if not isinstance(value, dict):
            return None
        start = self._coerce_int(value.get("start"), default=None)
        end = self._coerce_int(value.get("end"), default=None)
        if start is None or end is None or start < 0 or end < start:
            return None
        return {"start": start, "end": end}
