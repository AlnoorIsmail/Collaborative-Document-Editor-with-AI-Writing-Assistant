from typing import List, Optional

from sqlalchemy.orm import Session

from app.backend.models.document_version import DocumentVersion


class VersionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        *,
        document_id: int,
        version_number: int,
        content_snapshot: str,
        created_by: int,
        is_restore_version: bool,
    ) -> DocumentVersion:
        version = DocumentVersion(
            document_id=document_id,
            version_number=version_number,
            content_snapshot=content_snapshot,
            created_by=created_by,
            is_restore_version=is_restore_version,
        )
        self.db.add(version)
        self.db.flush()
        self.db.refresh(version)
        return version

    def get_by_id(self, version_id: int) -> Optional[DocumentVersion]:
        return self.db.query(DocumentVersion).filter(DocumentVersion.id == version_id).first()

    def list_for_document(self, document_id: int) -> List[DocumentVersion]:
        return (
            self.db.query(DocumentVersion)
            .filter(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_number.desc(), DocumentVersion.created_at.desc())
            .all()
        )

    def get_latest_for_document(self, document_id: int) -> Optional[DocumentVersion]:
        return (
            self.db.query(DocumentVersion)
            .filter(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_number.desc(), DocumentVersion.created_at.desc())
            .first()
        )
