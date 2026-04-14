from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class DocumentCreate(BaseModel):
    title: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Human-readable document title.",
    )
    initial_content: str = Field(
        default="",
        description="Initial document body stored at creation time.",
    )
    content_format: str = Field(
        default="plain_text",
        description="Format identifier for the stored document content.",
    )
    ai_enabled: bool = Field(
        default=True,
        description="Whether AI suggestion features are enabled for the document.",
    )

    model_config = ConfigDict(extra="forbid")


class DocumentUpdate(BaseModel):
    title: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Updated document title.",
    )
    ai_enabled: Optional[bool] = Field(
        default=None,
        description="Toggle AI suggestion features for the document.",
    )

    model_config = ConfigDict(extra="forbid")


class DocumentContentSaveRequest(BaseModel):
    content: str = Field(..., description="Full document body to persist.")
    base_revision: int = Field(
        ...,
        ge=0,
        description="Current revision known by the client for optimistic concurrency.",
    )

    model_config = ConfigDict(extra="forbid")


class DocumentOwnerResponse(BaseModel):
    user_id: int = Field(..., description="Numeric owner user identifier.")
    display_name: str = Field(..., description="Display name for the owning user.")


class LatestVersionReference(BaseModel):
    version_id: int = Field(..., description="Identifier of the latest stored version.")
    revision: int = Field(
        ..., description="Revision number of the latest stored version."
    )


class DocumentSummaryResponse(BaseModel):
    document_id: int = Field(..., description="Numeric document identifier.")
    title: str = Field(..., description="Current document title.")
    content_format: str = Field(..., description="Persisted document content format.")
    owner: DocumentOwnerResponse
    owner_user_id: int = Field(..., description="Numeric owner user identifier.")
    role: str = Field(..., description="Current caller role for this document.")
    ai_enabled: bool = Field(..., description="Whether AI suggestions are enabled.")
    revision: int = Field(..., ge=0, description="Current document revision number.")
    latest_version_id: Optional[int] = Field(
        default=None,
        description="Latest version identifier if at least one version exists.",
    )
    latest_version: Optional[LatestVersionReference] = None
    created_at: datetime = Field(..., description="UTC document creation timestamp.")
    updated_at: datetime = Field(..., description="UTC document update timestamp.")


class DocumentCreateResponse(BaseModel):
    document_id: int = Field(..., description="Numeric document identifier.")
    title: str = Field(..., description="Current document title.")
    current_content: str = Field(..., description="Current persisted document body.")
    content_format: str = Field(..., description="Persisted document content format.")
    owner: DocumentOwnerResponse
    owner_user_id: int = Field(..., description="Numeric owner user identifier.")
    role: str = Field(..., description="Current caller role for this document.")
    ai_enabled: bool = Field(..., description="Whether AI suggestions are enabled.")
    revision: int = Field(..., ge=0, description="Current document revision number.")
    latest_version_id: Optional[int] = Field(
        default=None,
        description="Latest version identifier if at least one version exists.",
    )
    latest_version: Optional[LatestVersionReference]
    created_at: datetime = Field(..., description="UTC document creation timestamp.")
    updated_at: datetime = Field(..., description="UTC document update timestamp.")


class DocumentDetailResponse(BaseModel):
    document_id: int = Field(..., description="Numeric document identifier.")
    title: str = Field(..., description="Current document title.")
    current_content: str = Field(..., description="Current persisted document body.")
    content_format: str = Field(..., description="Persisted document content format.")
    owner: DocumentOwnerResponse
    owner_user_id: int = Field(..., description="Numeric owner user identifier.")
    role: str = Field(..., description="Current caller role for this document.")
    ai_enabled: bool = Field(..., description="Whether AI suggestions are enabled.")
    revision: int = Field(..., ge=0, description="Current document revision number.")
    latest_version_id: Optional[int] = Field(
        default=None,
        description="Latest version identifier if at least one version exists.",
    )
    latest_version: Optional[LatestVersionReference]
    created_at: datetime = Field(..., description="UTC document creation timestamp.")
    updated_at: datetime = Field(..., description="UTC document update timestamp.")


class DocumentMetadataResponse(BaseModel):
    document_id: int = Field(..., description="Numeric document identifier.")
    title: str = Field(..., description="Current document title.")
    ai_enabled: bool = Field(..., description="Whether AI suggestions are enabled.")
    role: str = Field(..., description="Current caller role for this document.")
    updated_at: datetime = Field(..., description="UTC document update timestamp.")


class DocumentContentSaveResponse(BaseModel):
    document_id: int = Field(..., description="Numeric document identifier.")
    latest_version_id: int = Field(
        ..., description="Identifier of the newly created version."
    )
    revision: int = Field(..., ge=1, description="New current revision number.")
    saved_at: datetime = Field(
        ..., description="UTC timestamp when the save completed."
    )


class DocumentExportRequest(BaseModel):
    format: str = Field(
        default="plain_text",
        description="Requested export format: plain_text, markdown, html, or json.",
    )

    model_config = ConfigDict(extra="forbid")


class DocumentExportResponse(BaseModel):
    document_id: int = Field(..., description="Numeric document identifier.")
    title: str = Field(..., description="Current document title.")
    format: str = Field(..., description="Resolved export format.")
    content_type: str = Field(..., description="Returned MIME content type.")
    filename: str = Field(..., description="Suggested export filename.")
    exported_content: str = Field(..., description="Serialized document content.")
    revision: int = Field(..., ge=0, description="Revision exported for the document.")
    exported_at: datetime = Field(
        ..., description="UTC timestamp for the export snapshot."
    )
