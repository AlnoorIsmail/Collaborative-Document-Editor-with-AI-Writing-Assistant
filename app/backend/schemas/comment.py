from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.backend.core.contracts import prefixed_id


class CommentAuthorResponse(BaseModel):
    user_id: int = Field(..., description="Numeric author user identifier.")
    display_name: str = Field(..., description="Display name for the author.")


class DocumentCommentCreateRequest(BaseModel):
    body: str = Field(..., max_length=4000, description="Comment body text.")
    quoted_text: str | None = Field(
        default=None,
        max_length=2000,
        description="Optional plain-text snapshot from the selected document text.",
    )

    model_config = ConfigDict(extra="forbid")


class DocumentCommentResponse(BaseModel):
    comment_id: str = Field(..., description="Stable comment identifier.")
    document_id: int = Field(..., description="Numeric document identifier.")
    author_user_id: int = Field(..., description="Numeric author user identifier.")
    author: CommentAuthorResponse
    body: str = Field(..., description="Comment body text.")
    quoted_text: str | None = Field(
        default=None,
        description="Optional selected-text snapshot stored with the comment.",
    )
    status: Literal["open", "resolved"] = Field(
        ...,
        description="Current comment lifecycle state.",
    )
    created_at: datetime = Field(..., description="UTC comment creation timestamp.")
    updated_at: datetime = Field(..., description="UTC comment update timestamp.")
    resolved_at: datetime | None = Field(
        default=None,
        description="UTC timestamp when the comment was resolved, if resolved.",
    )
    resolved_by_user_id: int | None = Field(
        default=None,
        description="Numeric user identifier for the resolver, if resolved.",
    )


def serialize_comment_id(comment_id: int) -> str:
    return prefixed_id("cmt", comment_id)
