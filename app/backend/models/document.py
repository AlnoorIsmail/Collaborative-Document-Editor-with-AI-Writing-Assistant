from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.backend.core.contracts import utc_now
from app.backend.core.database import Base


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("owner_id", "title", name="uq_documents_owner_id_title"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    content_format: Mapped[str] = mapped_column(
        String(50), default="plain_text", nullable=False
    )
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=False
    )
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    line_spacing: Mapped[float] = mapped_column(Float, default=1.15, nullable=False)
    latest_version_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("document_versions.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now
    )

    owner: Mapped["User"] = relationship(
        "User",
        back_populates="owned_documents",
        foreign_keys=[owner_id],
    )
    latest_version: Mapped[Optional["DocumentVersion"]] = relationship(
        "DocumentVersion",
        foreign_keys=[latest_version_id],
        post_update=True,
    )
    versions: Mapped[List["DocumentVersion"]] = relationship(
        "DocumentVersion",
        back_populates="document",
        foreign_keys="DocumentVersion.document_id",
        cascade="all, delete-orphan",
    )
    permissions: Mapped[List["DocumentPermission"]] = relationship(
        "DocumentPermission",
        back_populates="document",
        cascade="all, delete-orphan",
    )
    invitations: Mapped[List["Invitation"]] = relationship(
        "Invitation",
        back_populates="document",
        cascade="all, delete-orphan",
    )
    share_links: Mapped[List["ShareLink"]] = relationship(
        "ShareLink",
        back_populates="document",
        cascade="all, delete-orphan",
    )
    conflicts: Mapped[List["DocumentConflict"]] = relationship(
        "DocumentConflict",
        back_populates="document",
        cascade="all, delete-orphan",
    )
    comments: Mapped[List["DocumentComment"]] = relationship(
        "DocumentComment",
        back_populates="document",
        cascade="all, delete-orphan",
    )
