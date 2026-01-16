from __future__ import annotations

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import DocumentSequence
from .concurrency import run_with_retry


class DocumentSequenceError(Exception):
    """Raised when document sequence operations fail."""
    pass


def next_document_number(
    *,
    store_id: int,
    document_type: str,
    prefix: str,
    pad: int = 4,
) -> str:
    """
    Atomically allocate the next document number for a store/type.

    Uses row-level lock on (store_id, document_type) to prevent race conditions.
    """
    def _op() -> str:
        if not store_id:
            raise DocumentSequenceError("store_id is required")
        if not document_type:
            raise DocumentSequenceError("document_type is required")

        stmt = (
            update(DocumentSequence)
            .where(
                DocumentSequence.store_id == store_id,
                DocumentSequence.document_type == document_type,
            )
            .values(next_number=DocumentSequence.next_number + 1)
        )

        result = db.session.execute(stmt)
        if result.rowcount:
            db.session.flush()
            current = (
                db.session.query(DocumentSequence.next_number)
                .filter_by(store_id=store_id, document_type=document_type)
                .scalar()
            )
            next_num = current - 1
        else:
            seq = DocumentSequence(store_id=store_id, document_type=document_type, next_number=2)
            db.session.add(seq)
            try:
                db.session.flush()
                next_num = 1
            except IntegrityError:
                db.session.rollback()
                result = db.session.execute(stmt)
                if not result.rowcount:
                    raise
                db.session.flush()
                current = (
                    db.session.query(DocumentSequence.next_number)
                    .filter_by(store_id=store_id, document_type=document_type)
                    .scalar()
                )
                next_num = current - 1

        return f"{prefix}-{store_id:03d}-{next_num:0{pad}d}"

    return run_with_retry(_op)
