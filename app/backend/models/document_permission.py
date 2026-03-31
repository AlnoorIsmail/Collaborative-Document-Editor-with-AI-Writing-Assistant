from datetime import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.backend.core.contracts import utc_now
from app.backend.core.database import Base


class DocumentPermission(Base):
    __tablename__ = "document_permissions"
    __table_args__ = (
        UniqueConstraint(
            "document_id", "user_id", name="uq_document_permissions_document_id_user_id"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id"), index=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=False
    )
    grantee_type: Mapped[str] = mapped_column(
        String(50), default="user", nullable=False
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    ai_allowed: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)

    document: Mapped["Document"] = relationship(
        "Document", back_populates="permissions"
    )
    user: Mapped["User"] = relationship("User", back_populates="document_permissions")
