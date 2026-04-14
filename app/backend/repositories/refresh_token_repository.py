from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.backend.models.refresh_token import RefreshToken


class RefreshTokenRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self, *, user_id: int, token_id: str, expires_at: datetime
    ) -> RefreshToken:
        refresh_token = RefreshToken(
            user_id=user_id,
            token_id=token_id,
            expires_at=expires_at,
        )
        self.db.add(refresh_token)
        self.db.flush()
        self.db.refresh(refresh_token)
        return refresh_token

    def get_by_token_id(self, token_id: str) -> Optional[RefreshToken]:
        return (
            self.db.query(RefreshToken)
            .filter(RefreshToken.token_id == token_id)
            .first()
        )

    def revoke(
        self, refresh_token: RefreshToken, *, revoked_at: datetime
    ) -> RefreshToken:
        refresh_token.revoked_at = revoked_at
        self.db.add(refresh_token)
        self.db.flush()
        self.db.refresh(refresh_token)
        return refresh_token
