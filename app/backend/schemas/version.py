from datetime import datetime

from pydantic import BaseModel, Field


class VersionResponse(BaseModel):
    """Document version metadata returned by history endpoints."""

    version_id: int
    version_number: int
    created_by: int
    created_at: datetime
    is_restore_version: bool


class VersionRestoreResponse(BaseModel):
    """Response returned after restoring a historical version."""

    document_id: int
    restored_from_version_id: int = Field(
        description="Historical version chosen by the client.",
    )
    new_version_id: int = Field(
        description="Newly created version representing the restored content.",
    )
    message: str
