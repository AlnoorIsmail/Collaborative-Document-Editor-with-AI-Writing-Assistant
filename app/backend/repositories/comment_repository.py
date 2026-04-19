from typing import Optional

from sqlalchemy.orm import Session, joinedload

from app.backend.models.document_comment import DocumentComment


class CommentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, comment_id: int) -> Optional[DocumentComment]:
        return (
            self.db.query(DocumentComment)
            .options(joinedload(DocumentComment.author))
            .filter(DocumentComment.id == comment_id)
            .first()
        )

    def list_for_document(self, document_id: int) -> list[DocumentComment]:
        return (
            self.db.query(DocumentComment)
            .options(joinedload(DocumentComment.author))
            .filter(DocumentComment.document_id == document_id)
            .order_by(
                DocumentComment.status.asc(),
                DocumentComment.created_at.desc(),
                DocumentComment.id.desc(),
            )
            .all()
        )

    def create(
        self,
        *,
        document_id: int,
        author_user_id: int,
        body: str,
        quoted_text: str | None,
    ) -> DocumentComment:
        comment = DocumentComment(
            document_id=document_id,
            author_user_id=author_user_id,
            body=body,
            quoted_text=quoted_text,
        )
        self.db.add(comment)
        self.db.flush()
        self.db.refresh(comment)
        return self.get_by_id(comment.id) or comment

    def update(self, comment: DocumentComment, **fields) -> DocumentComment:
        for key, value in fields.items():
            setattr(comment, key, value)

        self.db.add(comment)
        self.db.flush()
        self.db.refresh(comment)
        return self.get_by_id(comment.id) or comment

    def delete(self, comment: DocumentComment) -> None:
        self.db.delete(comment)
        self.db.flush()
