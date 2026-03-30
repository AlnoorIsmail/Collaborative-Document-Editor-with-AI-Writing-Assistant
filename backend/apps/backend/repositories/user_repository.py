from typing import Optional

from sqlalchemy.orm import Session

from apps.backend.models.user import User


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()

    def get_by_id(self, user_id: int) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id).first()

    def create(self, *, email: str, display_name: str, password_hash: str) -> User:
        user = User(
            email=email,
            display_name=display_name,
            password_hash=password_hash,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
