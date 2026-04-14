from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.backend.models.refresh_token import RefreshToken


class RefreshTokenRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, *, user_id: int, jti: str, expires_at: datetime) -> RefreshToken:
        refresh_token = RefreshToken(
            user_id=user_id,
            jti=jti,
            expires_at=expires_at,
        )
        self.db.add(refresh_token)
        self.db.flush()
        self.db.refresh(refresh_token)
        return refresh_token

    def get_by_jti(self, jti: str) -> Optional[RefreshToken]:
        return self.db.query(RefreshToken).filter(RefreshToken.jti == jti).first()

    def revoke(
        self,
        refresh_token: RefreshToken,
        *,
        revoked_at: datetime,
    ) -> RefreshToken:
        refresh_token.revoked_at = revoked_at
        self.db.add(refresh_token)
        self.db.flush()
        self.db.refresh(refresh_token)
        return refresh_token
