from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.backend.core.contracts import utc_now
from app.backend.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now
    )

    owned_documents: Mapped[List["Document"]] = relationship(
        "Document",
        back_populates="owner",
        foreign_keys="Document.owner_id",
    )
    created_versions: Mapped[List["DocumentVersion"]] = relationship(
        "DocumentVersion",
        back_populates="creator",
        foreign_keys="DocumentVersion.created_by",
    )
    document_permissions: Mapped[List["DocumentPermission"]] = relationship(
        "DocumentPermission",
        back_populates="user",
        foreign_keys="DocumentPermission.user_id",
    )
    sent_invitations: Mapped[List["Invitation"]] = relationship(
        "Invitation",
        back_populates="inviter",
        foreign_keys="Invitation.invited_by",
    )
    created_share_links: Mapped[List["ShareLink"]] = relationship(
        "ShareLink",
        back_populates="creator",
        foreign_keys="ShareLink.created_by",
    )
