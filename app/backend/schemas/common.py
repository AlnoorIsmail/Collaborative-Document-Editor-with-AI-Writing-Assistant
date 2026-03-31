"""Shared schemas used across backend modules."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AppSchema(BaseModel):
    """Base schema with strict request/response validation defaults."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ErrorCode(str, Enum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    DOCUMENT_NOT_FOUND = "DOCUMENT_NOT_FOUND"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    INVITATION_NOT_FOUND = "INVITATION_NOT_FOUND"
    INVITATION_ALREADY_PROCESSED = "INVITATION_ALREADY_PROCESSED"
    INVITATION_EXPIRED = "INVITATION_EXPIRED"
    SHARE_LINK_NOT_FOUND = "SHARE_LINK_NOT_FOUND"
    SHARE_LINK_REVOKED = "SHARE_LINK_REVOKED"
    SHARE_LINK_EXPIRED = "SHARE_LINK_EXPIRED"
    AI_DISABLED = "AI_DISABLED"
    AI_ROLE_NOT_ALLOWED = "AI_ROLE_NOT_ALLOWED"
    AI_QUOTA_EXCEEDED = "AI_QUOTA_EXCEEDED"
    STALE_SELECTION = "STALE_SELECTION"
    CONFLICT_DETECTED = "CONFLICT_DETECTED"
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"


class ErrorResponse(AppSchema):
    error_code: str
    message: str
    retryable: bool = False


class HealthResponse(AppSchema):
    status: str


class TextRange(AppSchema):
    start: int = Field(ge=0)
    end: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_bounds(self) -> "TextRange":
        if self.end < self.start:
            raise ValueError("end must be greater than or equal to start")
        return self
