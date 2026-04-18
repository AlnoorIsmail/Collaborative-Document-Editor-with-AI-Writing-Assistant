from datetime import datetime

from pydantic import BaseModel, Field


class VersionResponse(BaseModel):
    version_id: int = Field(..., description="Numeric version identifier.")
    version_number: int = Field(
        ..., description="Monotonic revision number for the document."
    )
    created_by: int = Field(
        ..., description="Numeric identifier of the user who created the version."
    )
    created_at: datetime = Field(
        ..., description="UTC timestamp when the version entry was created."
    )
    is_restore_version: bool = Field(
        ...,
        description="True when this version was created by restoring a prior snapshot.",
    )
    save_source: str = Field(
        ...,
        description="How this version was created: manual, autosave, or restore.",
    )


class VersionRestoreResponse(BaseModel):
    document_id: int = Field(..., description="Numeric document identifier.")
    restored_from_version_id: int = Field(
        ...,
        description="Version that was used as the restore source snapshot.",
    )
    new_version_id: int = Field(
        ...,
        description="New version identifier created by the restore operation.",
    )
    message: str = Field(..., description="Human-readable restore result message.")
