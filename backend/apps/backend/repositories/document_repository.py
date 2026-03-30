from typing import Optional

from sqlalchemy.orm import Session, joinedload

from apps.backend.models.document import Document


class DocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        *,
        title: str,
        content: str,
        content_format: str,
        ai_enabled: bool,
        owner_id: int,
    ) -> Document:
        document = Document(
            title=title,
            content=content,
            content_format=content_format,
            ai_enabled=ai_enabled,
            owner_id=owner_id,
        )
        self.db.add(document)
        self.db.flush()
        self.db.refresh(document)
        return document

    def get_by_id(self, document_id: int) -> Optional[Document]:
        return (
            self.db.query(Document)
            .options(joinedload(Document.owner))
            .filter(Document.id == document_id)
            .first()
        )

    def update(self, document: Document, **fields) -> Document:
        for key, value in fields.items():
            setattr(document, key, value)

        self.db.add(document)
        self.db.flush()
        self.db.refresh(document)
        return document
