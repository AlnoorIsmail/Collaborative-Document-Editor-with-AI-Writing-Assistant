from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class DocumentCreate(BaseModel):
    title: str
    initial_content: str = ""
    content_format: str = "plain_text"
    ai_enabled: bool = True

    model_config = ConfigDict(extra="forbid")


class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    ai_enabled: Optional[bool] = None

    model_config = ConfigDict(extra="forbid")


class DocumentContentSaveRequest(BaseModel):
    content: str
    base_revision: int

    model_config = ConfigDict(extra="forbid")


class DocumentCreateResponse(BaseModel):
    document_id: int
    title: str
    current_content: str
    content_format: str
    owner_user_id: int
    role: str
    ai_enabled: bool
    latest_version_id: Optional[int]
    created_at: datetime
    updated_at: datetime


class DocumentDetailResponse(BaseModel):
    document_id: int
    title: str
    current_content: str
    content_format: str
    owner_user_id: int
    role: str
    ai_enabled: bool
    latest_version_id: Optional[int]
    updated_at: datetime


class DocumentMetadataResponse(BaseModel):
    document_id: int
    title: str
    ai_enabled: bool
    updated_at: datetime


class DocumentContentSaveResponse(BaseModel):
    document_id: int
    latest_version_id: int
    revision: int
    saved_at: datetime
