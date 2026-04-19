from datetime import datetime
from typing import Iterable, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload

from app.backend.models.document_conflict import (
    DocumentConflict,
    DocumentConflictCandidate,
)


OPEN_CONFLICT_STATUSES = ("open", "stale")


class ConflictRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_conflict(
        self,
        *,
        document_id: int,
        conflict_key: str | None,
        status: str,
        source_revision: int,
        source_collab_version: int,
        anchor_start: int | None,
        anchor_end: int | None,
        exact_text_snapshot: str,
        prefix_context: str,
        suffix_context: str,
        created_by_user_id: int,
    ) -> DocumentConflict:
        conflict = DocumentConflict(
            document_id=document_id,
            conflict_key=conflict_key,
            status=status,
            source_revision=source_revision,
            source_collab_version=source_collab_version,
            anchor_start=anchor_start,
            anchor_end=anchor_end,
            exact_text_snapshot=exact_text_snapshot,
            prefix_context=prefix_context,
            suffix_context=suffix_context,
            created_by_user_id=created_by_user_id,
        )
        self.db.add(conflict)
        self.db.flush()
        self.db.refresh(conflict)
        return conflict

    def get_conflict_by_id(
        self,
        *,
        conflict_id: int,
        document_id: int | None = None,
    ) -> Optional[DocumentConflict]:
        query = (
            self.db.query(DocumentConflict)
            .options(joinedload(DocumentConflict.candidates))
            .filter(DocumentConflict.id == conflict_id)
        )
        if document_id is not None:
            query = query.filter(DocumentConflict.document_id == document_id)
        return query.first()

    def get_conflict_by_key(
        self,
        *,
        document_id: int,
        conflict_key: str,
    ) -> Optional[DocumentConflict]:
        return (
            self.db.query(DocumentConflict)
            .options(joinedload(DocumentConflict.candidates))
            .filter(
                DocumentConflict.document_id == document_id,
                DocumentConflict.conflict_key == conflict_key,
            )
            .first()
        )

    def list_open_conflicts(self, *, document_id: int) -> list[DocumentConflict]:
        return (
            self.db.query(DocumentConflict)
            .options(joinedload(DocumentConflict.candidates))
            .filter(
                DocumentConflict.document_id == document_id,
                DocumentConflict.status.in_(OPEN_CONFLICT_STATUSES),
            )
            .order_by(DocumentConflict.created_at.asc())
            .all()
        )

    def find_overlapping_open_conflict(
        self,
        *,
        document_id: int,
        source_collab_version: int,
        anchor_start: int,
        anchor_end: int,
    ) -> Optional[DocumentConflict]:
        return (
            self.db.query(DocumentConflict)
            .options(joinedload(DocumentConflict.candidates))
            .filter(
                DocumentConflict.document_id == document_id,
                DocumentConflict.status.in_(OPEN_CONFLICT_STATUSES),
                DocumentConflict.source_collab_version <= source_collab_version + 1,
                DocumentConflict.source_collab_version >= max(source_collab_version - 1, 0),
                DocumentConflict.anchor_start.is_not(None),
                DocumentConflict.anchor_end.is_not(None),
                or_(
                    and_(
                        DocumentConflict.anchor_start == DocumentConflict.anchor_end,
                        anchor_start == anchor_end,
                        DocumentConflict.anchor_start == anchor_start,
                    ),
                    and_(
                        DocumentConflict.anchor_start < anchor_end,
                        DocumentConflict.anchor_end > anchor_start,
                    ),
                ),
            )
            .order_by(DocumentConflict.created_at.asc())
            .first()
        )

    def create_candidate(
        self,
        *,
        conflict_id: int,
        user_id: int,
        user_display_name: str,
        batch_id: str,
        client_id: str | None,
        range_start: int,
        range_end: int,
        candidate_content_snapshot: str,
        exact_text_snapshot: str,
        prefix_context: str,
        suffix_context: str,
    ) -> DocumentConflictCandidate:
        candidate = DocumentConflictCandidate(
            conflict_id=conflict_id,
            user_id=user_id,
            user_display_name=user_display_name,
            batch_id=batch_id,
            client_id=client_id,
            range_start=range_start,
            range_end=range_end,
            candidate_content_snapshot=candidate_content_snapshot,
            exact_text_snapshot=exact_text_snapshot,
            prefix_context=prefix_context,
            suffix_context=suffix_context,
        )
        self.db.add(candidate)
        self.db.flush()
        self.db.refresh(candidate)
        return candidate

    def find_candidate(
        self,
        *,
        conflict_id: int,
        batch_id: str,
        user_id: int,
    ) -> Optional[DocumentConflictCandidate]:
        return (
            self.db.query(DocumentConflictCandidate)
            .filter(
                DocumentConflictCandidate.conflict_id == conflict_id,
                DocumentConflictCandidate.batch_id == batch_id,
                DocumentConflictCandidate.user_id == user_id,
            )
            .first()
        )

    def update_conflict(self, conflict: DocumentConflict, **fields) -> DocumentConflict:
        for key, value in fields.items():
            setattr(conflict, key, value)
        self.db.add(conflict)
        self.db.flush()
        self.db.refresh(conflict)
        return conflict

    def resolve_conflict(
        self,
        *,
        conflict: DocumentConflict,
        status: str,
        resolved_content: str,
        resolved_by_user_id: int,
        resolved_at: datetime,
    ) -> DocumentConflict:
        return self.update_conflict(
            conflict,
            status=status,
            resolved_content=resolved_content,
            resolved_by_user_id=resolved_by_user_id,
            resolved_at=resolved_at,
        )
