from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.backend.core.contracts import utc_now
from app.backend.core.database import Base


class DocumentConflict(Base):
    __tablename__ = "document_conflicts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id"), index=True, nullable=False
    )
    conflict_key: Mapped[Optional[str]] = mapped_column(
        String(255), unique=True, nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    source_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_collab_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    anchor_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    anchor_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    exact_text_snapshot: Mapped[str] = mapped_column(Text, default="", nullable=False)
    prefix_context: Mapped[str] = mapped_column(Text, default="", nullable=False)
    suffix_context: Mapped[str] = mapped_column(Text, default="", nullable=False)
    resolved_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    resolved_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="conflicts",
        foreign_keys=[document_id],
    )
    candidates: Mapped[List["DocumentConflictCandidate"]] = relationship(
        "DocumentConflictCandidate",
        back_populates="conflict",
        cascade="all, delete-orphan",
        order_by="DocumentConflictCandidate.created_at",
    )


class DocumentConflictCandidate(Base):
    __tablename__ = "document_conflict_candidates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    conflict_id: Mapped[int] = mapped_column(
        ForeignKey("document_conflicts.id"), index=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    user_display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    batch_id: Mapped[str] = mapped_column(String(128), nullable=False)
    client_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    range_start: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    range_end: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    candidate_content_snapshot: Mapped[str] = mapped_column(
        Text, default="", nullable=False
    )
    exact_text_snapshot: Mapped[str] = mapped_column(Text, default="", nullable=False)
    prefix_context: Mapped[str] = mapped_column(Text, default="", nullable=False)
    suffix_context: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    conflict: Mapped["DocumentConflict"] = relationship(
        "DocumentConflict",
        back_populates="candidates",
        foreign_keys=[conflict_id],
    )
