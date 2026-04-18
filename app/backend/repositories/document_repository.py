from typing import List, Optional

from sqlalchemy.orm import Session, joinedload

from app.backend.models.document import Document


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
        line_spacing: float,
        owner_id: int,
    ) -> Document:
        document = Document(
            title=title,
            content=content,
            content_format=content_format,
            ai_enabled=ai_enabled,
            line_spacing=line_spacing,
            owner_id=owner_id,
        )
        self.db.add(document)
        self.db.flush()
        self.db.refresh(document)
        return document

    def get_by_id(self, document_id: int) -> Optional[Document]:
        return (
            self.db.query(Document)
            .options(
                joinedload(Document.owner),
                joinedload(Document.latest_version),
            )
            .filter(Document.id == document_id)
            .first()
        )

    def list_owned_by_user(self, user_id: int) -> List[Document]:
        return (
            self.db.query(Document)
            .options(
                joinedload(Document.owner),
                joinedload(Document.latest_version),
            )
            .filter(Document.owner_id == user_id)
            .order_by(Document.updated_at.desc(), Document.created_at.desc())
            .all()
        )

    def list_titles_by_owner(
        self, *, owner_id: int, exclude_document_id: int | None = None
    ) -> List[str]:
        query = self.db.query(Document.title).filter(Document.owner_id == owner_id)
        if exclude_document_id is not None:
            query = query.filter(Document.id != exclude_document_id)
        return [title for (title,) in query.all()]

    def update(self, document: Document, **fields) -> Document:
        for key, value in fields.items():
            setattr(document, key, value)

        self.db.add(document)
        self.db.flush()
        self.db.refresh(document)
        return document

    def delete(self, document: Document) -> None:
        document.latest_version_id = None
        self.db.add(document)
        self.db.flush()
        self.db.delete(document)
        self.db.flush()
