from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.backend.models.invitation import Invitation


class InvitationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        *,
        document_id: int,
        email: str,
        role: str,
        token: str,
        invited_by: int,
        expires_at: datetime,
    ) -> Invitation:
        invitation = Invitation(
            document_id=document_id,
            email=email,
            role=role,
            token=token,
            invited_by=invited_by,
            expires_at=expires_at,
        )
        self.db.add(invitation)
        self.db.flush()
        self.db.refresh(invitation)
        return invitation

    def get_by_id(self, invitation_id: int) -> Optional[Invitation]:
        return self.db.query(Invitation).filter(Invitation.id == invitation_id).first()

    def update(self, invitation: Invitation, **fields) -> Invitation:
        for key, value in fields.items():
            setattr(invitation, key, value)

        self.db.add(invitation)
        self.db.flush()
        self.db.refresh(invitation)
        return invitation
