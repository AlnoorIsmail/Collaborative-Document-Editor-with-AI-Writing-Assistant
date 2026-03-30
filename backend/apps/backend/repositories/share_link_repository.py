from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from apps.backend.models.share_link import ShareLink


class ShareLinkRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        *,
        document_id: int,
        token: str,
        role: str,
        require_sign_in: bool,
        expires_at: datetime,
        created_by: int,
    ) -> ShareLink:
        share_link = ShareLink(
            document_id=document_id,
            token=token,
            role=role,
            require_sign_in=require_sign_in,
            expires_at=expires_at,
            created_by=created_by,
        )
        self.db.add(share_link)
        self.db.flush()
        self.db.refresh(share_link)
        return share_link

    def get_by_token(self, token: str) -> Optional[ShareLink]:
        return self.db.query(ShareLink).filter(ShareLink.token == token).first()

    def update(self, share_link: ShareLink, **fields) -> ShareLink:
        for key, value in fields.items():
            setattr(share_link, key, value)

        self.db.add(share_link)
        self.db.flush()
        self.db.refresh(share_link)
        return share_link
