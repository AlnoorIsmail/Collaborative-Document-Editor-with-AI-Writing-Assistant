from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class DocumentCreate(BaseModel):
    """Payload used to create a new document."""

    title: str = Field(
        min_length=1,
        max_length=255,
        description="Human-readable document title.",
    )
    initial_content: str = Field(
        default="",
        description="Initial document body.",
    )
    content_format: str = Field(
        default="plain_text",
        description="Stored content format such as plain_text or markdown.",
    )
    ai_enabled: bool = Field(
        default=True,
        description="Whether AI assistant features are enabled for the document.",
    )

    model_config = ConfigDict(extra="forbid")


class DocumentUpdate(BaseModel):
    """Payload used to update document metadata and optionally content."""

    title: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Updated document title.",
    )
    content: Optional[str] = Field(
        default=None,
        description="Updated full document content. When provided, a new version is created.",
    )
    content_format: Optional[str] = Field(
        default=None,
        description="Updated storage format for the document content.",
    )
    ai_enabled: Optional[bool] = Field(
        default=None,
        description="Whether AI assistant features remain enabled.",
    )
    base_revision: Optional[int] = Field(
        default=None,
        ge=0,
        description="Current document revision known by the client when updating content.",
    )

    model_config = ConfigDict(extra="forbid")


class DocumentContentSaveRequest(BaseModel):
    """Payload used by the explicit content-save endpoint."""

    content: str = Field(description="Full updated document body.")
    base_revision: int = Field(
        ge=0,
        description="Revision the client edited from.",
    )

    model_config = ConfigDict(extra="forbid")


class DocumentOwnerResponse(BaseModel):
    """Owner metadata embedded in document responses."""

    user_id: int
    display_name: str


class LatestVersionReference(BaseModel):
    """Reference to the newest persisted document version."""

    version_id: int
    revision: int


class DocumentCreateResponse(BaseModel):
    """Document payload returned after creation."""

    document_id: int
    title: str
    current_content: str
    content_format: str
    owner: DocumentOwnerResponse
    owner_user_id: int
    role: str
    ai_enabled: bool
    revision: int
    latest_version_id: Optional[int]
    latest_version: Optional[LatestVersionReference]
    created_at: datetime
    updated_at: datetime


class DocumentListItemResponse(BaseModel):
    """Document summary returned by the list endpoint."""

    document_id: int
    title: str
    content_format: str
    owner: DocumentOwnerResponse
    owner_user_id: int
    role: str
    ai_enabled: bool
    revision: int
    latest_version_id: Optional[int]
    latest_version: Optional[LatestVersionReference]
    created_at: datetime
    updated_at: datetime


class DocumentDetailResponse(BaseModel):
    """Full document payload returned by detail and update endpoints."""

    document_id: int
    title: str
    current_content: str
    content_format: str
    owner: DocumentOwnerResponse
    owner_user_id: int
    role: str
    ai_enabled: bool
    revision: int
    latest_version_id: Optional[int]
    latest_version: Optional[LatestVersionReference]
    created_at: datetime
    updated_at: datetime


class DocumentMetadataResponse(BaseModel):
    """Metadata-only response kept for backward compatibility on partial updates."""

    document_id: int
    title: str
    ai_enabled: bool
    role: str
    updated_at: datetime


class DocumentUpdateResponse(DocumentDetailResponse):
    """Current document state returned after PATCH updates."""


class DocumentContentSaveResponse(BaseModel):
    """Response returned after persisting a new document version."""

    document_id: int
    latest_version_id: int
    revision: int
    saved_at: datetime


class DocumentExportRequest(BaseModel):
    """Payload used to export a document in another format."""

    format: str = Field(
        default="plain_text",
        description="Desired export format.",
    )

    model_config = ConfigDict(extra="forbid")


class DocumentExportResponse(BaseModel):
    """Exported document payload returned by the export endpoint."""

    document_id: int
    title: str
    format: str
    content_type: str
    filename: str
    exported_content: str
    revision: int
    exported_at: datetime
