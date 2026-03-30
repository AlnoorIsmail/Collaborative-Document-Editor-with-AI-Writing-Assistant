from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.backend.core.database import Base


class Invitation(Base):
    __tablename__ = "invitations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    token: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    invited_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    document: Mapped["Document"] = relationship("Document", back_populates="invitations")
    inviter: Mapped["User"] = relationship(
        "User",
        back_populates="sent_invitations",
        foreign_keys=[invited_by],
    )
