from typing import Optional

from sqlalchemy.orm import Session

from apps.backend.models.document_permission import DocumentPermission


class PermissionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, permission_id: int) -> Optional[DocumentPermission]:
        return (
            self.db.query(DocumentPermission)
            .filter(DocumentPermission.id == permission_id)
            .first()
        )

    def get_by_document_and_user(self, *, document_id: int, user_id: int) -> Optional[DocumentPermission]:
        return (
            self.db.query(DocumentPermission)
            .filter(
                DocumentPermission.document_id == document_id,
                DocumentPermission.user_id == user_id,
            )
            .first()
        )

    def create(
        self,
        *,
        document_id: int,
        user_id: int,
        grantee_type: str,
        role: str,
        ai_allowed: bool,
    ) -> DocumentPermission:
        permission = DocumentPermission(
            document_id=document_id,
            user_id=user_id,
            grantee_type=grantee_type,
            role=role,
            ai_allowed=ai_allowed,
        )
        self.db.add(permission)
        self.db.flush()
        self.db.refresh(permission)
        return permission

    def update(self, permission: DocumentPermission, **fields) -> DocumentPermission:
        for key, value in fields.items():
            setattr(permission, key, value)

        self.db.add(permission)
        self.db.flush()
        self.db.refresh(permission)
        return permission

    def delete(self, permission: DocumentPermission) -> None:
        self.db.delete(permission)
        self.db.flush()
