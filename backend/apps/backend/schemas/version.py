from datetime import datetime

from pydantic import BaseModel


class VersionResponse(BaseModel):
    version_id: int
    version_number: int
    created_by: int
    created_at: datetime
    is_restore_version: bool


class VersionRestoreResponse(BaseModel):
    document_id: int
    restored_from_version_id: int
    new_version_id: int
    message: str
