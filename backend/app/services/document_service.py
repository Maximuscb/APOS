# Overview: Service-layer operations for document; encapsulates business logic and database work.

from __future__ import annotations

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import (
    DocumentSequence,
    Sale,
    ReceiveDocument,
    InventoryTransaction,
    Count,
    Transfer,
    Return,
    Payment,
    RegisterSession,
    ImportBatch,
    Register,
    MasterLedgerEvent,
)
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


# =============================================================================
# Unified Documents Index
# =============================================================================

DOCUMENT_TYPES = {
    "SALES": Sale,
    "RECEIVES": ReceiveDocument,
    "ADJUSTMENTS": InventoryTransaction,
    "COUNTS": Count,
    "TRANSFERS": Transfer,
    "RETURNS": Return,
    "PAYMENTS": Payment,
    "SHIFTS": RegisterSession,
    "IMPORTS": ImportBatch,
    "DEVICES": MasterLedgerEvent,
    "EVENTS": MasterLedgerEvent,
}


def _document_to_index_row(doc_type: str, doc) -> dict:
    if doc_type == "SALES":
        return {
            "id": doc.id,
            "type": doc_type,
            "document_number": doc.document_number,
            "store_id": doc.store_id,
            "status": doc.status,
            "occurred_at": doc.created_at,
            "user_id": doc.created_by_user_id,
            "register_id": doc.register_id,
        }
    if doc_type == "RECEIVES":
        return {
            "id": doc.id,
            "type": doc_type,
            "document_number": doc.document_number,
            "store_id": doc.store_id,
            "status": doc.status,
            "occurred_at": doc.occurred_at,
            "user_id": doc.created_by_user_id,
            "register_id": None,
        }
    if doc_type == "ADJUSTMENTS":
        if hasattr(doc, "event_category"):
            return {
                "id": doc.id,
                "type": doc_type,
                "document_number": None,
                "store_id": doc.store_id,
                "status": doc.event_type,
                "occurred_at": doc.occurred_at,
                "user_id": doc.actor_user_id,
                "register_id": doc.register_id,
            }
        return {
            "id": doc.id,
            "type": doc_type,
            "document_number": None,
            "store_id": doc.store_id,
            "status": doc.status,
            "occurred_at": doc.occurred_at,
            # InventoryTransaction has no created_by_user_id; use the
            # lifecycle actor fields in priority order.
            "user_id": doc.posted_by_user_id or doc.approved_by_user_id,
            "register_id": None,
        }
    if doc_type == "COUNTS":
        return {
            "id": doc.id,
            "type": doc_type,
            "document_number": doc.document_number,
            "store_id": doc.store_id,
            "status": doc.status,
            "occurred_at": doc.created_at,
            "user_id": doc.created_by_user_id,
            "register_id": None,
        }
    if doc_type == "TRANSFERS":
        return {
            "id": doc.id,
            "type": doc_type,
            "document_number": doc.document_number,
            "store_id": doc.from_store_id,
            "status": doc.status,
            "occurred_at": doc.created_at,
            "user_id": doc.created_by_user_id,
            "register_id": None,
        }
    if doc_type == "RETURNS":
        return {
            "id": doc.id,
            "type": doc_type,
            "document_number": doc.document_number,
            "store_id": doc.store_id,
            "status": doc.status,
            "occurred_at": doc.created_at,
            "user_id": doc.created_by_user_id,
            "register_id": doc.register_id,
        }
    if doc_type == "PAYMENTS":
        if hasattr(doc, "event_category"):
            return {
                "id": doc.id,
                "type": doc_type,
                "document_number": None,
                "store_id": doc.store_id,
                "status": doc.event_type,
                "occurred_at": doc.occurred_at,
                "user_id": doc.actor_user_id,
                "register_id": doc.register_id,
            }
        return {
            "id": doc.id,
            "type": doc_type,
            "document_number": None,
            "store_id": doc.sale.store_id if doc.sale else None,
            "status": doc.status,
            "occurred_at": doc.created_at,
            "user_id": doc.created_by_user_id,
            "register_id": doc.register_id,
        }
    if doc_type == "SHIFTS":
        return {
            "id": doc.id,
            "type": doc_type,
            "document_number": None,
            "store_id": doc.register.store_id if doc.register else None,
            "status": doc.status,
            "occurred_at": doc.opened_at,
            "user_id": doc.user_id,
            "register_id": doc.register_id,
        }
    if doc_type == "IMPORTS":
        return {
            "id": doc.id,
            "type": doc_type,
            "document_number": None,
            "store_id": None,
            "status": doc.status,
            "occurred_at": doc.created_at,
            "user_id": doc.created_by_user_id,
            "register_id": None,
        }
    if doc_type == "DEVICES":
        return {
            "id": doc.id,
            "type": doc_type,
            "document_number": None,
            "store_id": doc.store_id,
            "status": doc.event_type,
            "occurred_at": doc.occurred_at,
            "user_id": doc.actor_user_id,
            "register_id": doc.register_id,
        }
    if doc_type == "EVENTS":
        return {
            "id": doc.id,
            "type": doc_type,
            "document_number": None,
            "store_id": doc.store_id,
            "status": doc.event_type,
            "occurred_at": doc.occurred_at,
            "user_id": doc.actor_user_id,
            "register_id": doc.register_id,
        }
    return {
        "id": doc.id,
        "type": doc_type,
        "document_number": None,
        "store_id": getattr(doc, "store_id", None),
        "status": getattr(doc, "status", None),
        "occurred_at": getattr(doc, "created_at", None),
        "user_id": getattr(doc, "created_by_user_id", None),
        "register_id": getattr(doc, "register_id", None),
    }


def list_documents(
    *,
    store_id: int | None = None,
    store_ids: list[int] | None = None,
    doc_type: str | None = None,
    from_date=None,
    to_date=None,
    user_id: int | None = None,
    register_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """
    List documents across types with common filters.
    """
    types = [doc_type] if doc_type else list(DOCUMENT_TYPES.keys())
    rows: list[dict] = []

    for dtype in types:
        model = DOCUMENT_TYPES.get(dtype)
        if not model:
            continue

        query = db.session.query(model)

        if dtype == "ADJUSTMENTS":
            model = MasterLedgerEvent
            query = db.session.query(model).filter(
                model.event_category == "inventory",
                model.event_type == "inventory.adjusted",
            )

        effective_store_ids = store_ids if store_ids is not None else ([store_id] if store_id else None)

        if dtype == "TRANSFERS" and effective_store_ids:
            query = query.filter(model.from_store_id.in_(effective_store_ids))
        elif dtype == "PAYMENTS":
            model = MasterLedgerEvent
            query = db.session.query(model).filter(model.event_category == "payment")
            if effective_store_ids:
                query = query.filter(model.store_id.in_(effective_store_ids))
        elif dtype == "SHIFTS" and effective_store_ids:
            query = query.filter(model.register_id.isnot(None)).join(
                Register, Register.id == model.register_id
            ).filter(Register.store_id.in_(effective_store_ids))
        elif dtype == "DEVICES":
            query = query.filter(model.event_category == "device")
            if effective_store_ids:
                query = query.filter(model.store_id.in_(effective_store_ids))
        elif dtype == "EVENTS":
            if effective_store_ids:
                query = query.filter(model.store_id.in_(effective_store_ids))
        elif dtype == "IMPORTS" and effective_store_ids:
            # Imports are org-level (no store_id). Reports are store-scoped.
            continue
        elif effective_store_ids and hasattr(model, "store_id"):
            query = query.filter(model.store_id.in_(effective_store_ids))

        if user_id:
            if model is MasterLedgerEvent:
                query = query.filter(model.actor_user_id == user_id)
            elif hasattr(model, "created_by_user_id"):
                query = query.filter(model.created_by_user_id == user_id)
        if register_id and hasattr(model, "register_id"):
            query = query.filter(model.register_id == register_id)

        if from_date:
            if model is MasterLedgerEvent:
                query = query.filter(model.occurred_at >= from_date)
            elif hasattr(model, "created_at"):
                query = query.filter(model.created_at >= from_date)
        if to_date:
            if model is MasterLedgerEvent:
                query = query.filter(model.occurred_at <= to_date)
            elif hasattr(model, "created_at"):
                query = query.filter(model.created_at <= to_date)

        docs = query.order_by(model.id.desc()).all()
        rows.extend([_document_to_index_row(dtype, doc) for doc in docs])

    rows.sort(key=lambda r: r.get("occurred_at") or r.get("id"), reverse=True)
    total = len(rows)

    if offset < 0:
        offset = 0
    if limit < 1:
        limit = 1
    if limit > 500:
        limit = 500

    return rows[offset: offset + limit], total


def get_document(doc_type: str, doc_id: int) -> dict | None:
    model = DOCUMENT_TYPES.get(doc_type)
    if not model:
        return None

    doc = db.session.query(model).filter_by(id=doc_id).first()
    if not doc:
        return None

    if hasattr(doc, "to_dict"):
        return doc.to_dict()

    return _document_to_index_row(doc_type, doc)
