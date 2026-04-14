from typing import Optional

from sqlalchemy.orm import Session, joinedload

from app.backend.models.document import Document
from app.backend.models.document_permission import DocumentPermission


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
            .options(
                joinedload(Document.owner),
                joinedload(Document.latest_version),
            )
            .filter(Document.id == document_id)
            .first()
        )

    def list_accessible_for_user(self, user_id: int) -> list[tuple[Document, str]]:
        owned_documents = [
            (document, "owner")
            for document in (
                self.db.query(Document)
                .options(
                    joinedload(Document.owner),
                    joinedload(Document.latest_version),
                )
                .filter(Document.owner_id == user_id)
                .order_by(Document.updated_at.desc(), Document.id.desc())
                .all()
            )
        ]
        shared_documents = (
            self.db.query(Document, DocumentPermission.role)
            .join(
                DocumentPermission,
                DocumentPermission.document_id == Document.id,
            )
            .options(
                joinedload(Document.owner),
                joinedload(Document.latest_version),
            )
            .filter(
                DocumentPermission.user_id == user_id,
                Document.owner_id != user_id,
            )
            .order_by(Document.updated_at.desc(), Document.id.desc())
            .all()
        )
        documents_by_id: dict[int, tuple[Document, str]] = {
            document.id: (document, role)
            for document, role in owned_documents + shared_documents
        }
        return sorted(
            documents_by_id.values(),
            key=lambda item: (item[0].updated_at, item[0].id),
            reverse=True,
        )

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
