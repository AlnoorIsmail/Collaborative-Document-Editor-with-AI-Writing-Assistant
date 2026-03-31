"""Realtime event names from the documented collaboration contract."""

from enum import Enum


class RealtimeEventType(str, Enum):
    JOIN_DOCUMENT = "join_document"
    EDIT_OPERATION = "edit_operation"
    PRESENCE_UPDATE = "presence_update"
    REMOTE_OPERATION = "remote_operation"
    COLLABORATOR_PRESENCE = "collaborator_presence"
    CONFLICT_DETECTED = "conflict_detected"
    RESYNC_REQUIRED = "resync_required"
