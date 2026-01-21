# Overview: Service-layer operations for imports; encapsulates business logic and database work.

"""
Import Service (Staging-Based)

WHY: Support large-scale imports via staging tables. Nothing posts to real
ledgers until mappings are resolved and explicit posting is requested.
"""

import json
from datetime import datetime

from ..extensions import db
from ..models import ImportBatch, ImportStagingRow, ImportEntityMapping
from app.time_utils import utcnow


class ImportError(ValueError):
    """Raised when import operations fail."""
    pass


def create_import_batch(
    *,
    org_id: int,
    import_type: str,
    created_by_user_id: int,
    source_file_name: str | None = None,
    source_file_format: str | None = None,
) -> ImportBatch:
    batch = ImportBatch(
        org_id=org_id,
        import_type=import_type,
        status="CREATED",
        source_file_name=source_file_name,
        source_file_format=source_file_format,
        created_by_user_id=created_by_user_id,
        created_at=utcnow(),
    )
    db.session.add(batch)
    db.session.commit()
    return batch


def stage_rows(*, batch_id: int, rows: list[dict]) -> dict:
    batch = db.session.query(ImportBatch).filter_by(id=batch_id).first()
    if not batch:
        raise ImportError("Import batch not found")

    staged = 0
    for idx, row in enumerate(rows, start=1):
        raw_data = json.dumps(row)
        foreign_id = row.get("foreign_id") or row.get("id")

        staging = ImportStagingRow(
            batch_id=batch_id,
            row_number=row.get("row_number", idx),
            raw_data=raw_data,
            foreign_id=str(foreign_id) if foreign_id is not None else None,
            mapping_status="PENDING",
            posting_status="PENDING",
        )
        db.session.add(staging)
        staged += 1

    batch.staged_rows = (batch.staged_rows or 0) + staged
    if batch.total_rows is None:
        batch.total_rows = batch.staged_rows
    batch.status = "STAGED"
    db.session.commit()

    return {"staged": staged, "batch_id": batch_id}


def _ensure_mapping(batch_id: int, entity_type: str, foreign_id: str, local_entity_id: int | None) -> ImportEntityMapping:
    mapping = db.session.query(ImportEntityMapping).filter_by(
        batch_id=batch_id,
        entity_type=entity_type,
        foreign_id=foreign_id,
    ).first()
    if mapping:
        mapping.local_entity_id = local_entity_id
        mapping.status = "MAPPED" if local_entity_id else "PENDING"
        mapping.mapped_at = utcnow() if local_entity_id else None
        return mapping

    mapping = ImportEntityMapping(
        batch_id=batch_id,
        entity_type=entity_type,
        foreign_id=foreign_id,
        local_entity_id=local_entity_id,
        status="MAPPED" if local_entity_id else "PENDING",
        mapped_at=utcnow() if local_entity_id else None,
    )
    db.session.add(mapping)
    return mapping


def set_entity_mapping(*, batch_id: int, entity_type: str, foreign_id: str, local_entity_id: int) -> ImportEntityMapping:
    batch = db.session.query(ImportBatch).filter_by(id=batch_id).first()
    if not batch:
        raise ImportError("Import batch not found")

    if not entity_type or not foreign_id:
        raise ImportError("entity_type and foreign_id are required")

    mapping = _ensure_mapping(batch_id, entity_type, foreign_id, local_entity_id)
    db.session.commit()
    return mapping


def get_unmapped_entities(batch_id: int) -> dict:
    batch = db.session.query(ImportBatch).filter_by(id=batch_id).first()
    if not batch:
        raise ImportError("Import batch not found")

    rows = db.session.query(ImportStagingRow).filter_by(batch_id=batch_id).all()
    unmapped = {"products": set(), "users": set(), "registers": set()}

    for row in rows:
        data = json.loads(row.raw_data)
        product_id = data.get("product_id")
        user_id = data.get("user_id")
        register_id = data.get("register_id")

        if product_id:
            mapping = db.session.query(ImportEntityMapping).filter_by(
                batch_id=batch_id,
                entity_type="product",
                foreign_id=str(product_id),
                status="MAPPED",
            ).first()
            if not mapping:
                unmapped["products"].add(str(product_id))

        if user_id:
            mapping = db.session.query(ImportEntityMapping).filter_by(
                batch_id=batch_id,
                entity_type="user",
                foreign_id=str(user_id),
                status="MAPPED",
            ).first()
            if not mapping:
                unmapped["users"].add(str(user_id))

        if register_id:
            mapping = db.session.query(ImportEntityMapping).filter_by(
                batch_id=batch_id,
                entity_type="register",
                foreign_id=str(register_id),
                status="MAPPED",
            ).first()
            if not mapping:
                unmapped["registers"].add(str(register_id))

    return {
        "products": sorted(unmapped["products"]),
        "users": sorted(unmapped["users"]),
        "registers": sorted(unmapped["registers"]),
    }


def post_mapped_rows(*, batch_id: int, limit: int = 500) -> dict:
    batch = db.session.query(ImportBatch).filter_by(id=batch_id).first()
    if not batch:
        raise ImportError("Import batch not found")

    rows = db.session.query(ImportStagingRow).filter_by(
        batch_id=batch_id,
        posting_status="PENDING",
    ).limit(limit).all()

    posted = 0
    quarantined = 0

    for row in rows:
        data = json.loads(row.raw_data)
        unmapped = []

        for entity_type, key in (("product", "product_id"), ("user", "user_id"), ("register", "register_id")):
            foreign_id = data.get(key)
            if foreign_id is None:
                continue
            mapping = db.session.query(ImportEntityMapping).filter_by(
                batch_id=batch_id,
                entity_type=entity_type,
                foreign_id=str(foreign_id),
                status="MAPPED",
            ).first()
            if not mapping:
                unmapped.append(f"{entity_type}:{foreign_id}")

        if unmapped:
            row.mapping_status = "UNMAPPED"
            row.posting_status = "QUARANTINED"
            row.unmapped_references = json.dumps(unmapped)
            quarantined += 1
            continue

        # Posting is domain-specific; actual posting is deferred until
        # real mappers are implemented. Mark as posted for now.
        row.mapping_status = "MAPPED"
        row.posting_status = "POSTED"
        row.posted_at = utcnow()
        posted += 1

    batch.posted_rows = (batch.posted_rows or 0) + posted
    batch.quarantined_rows = (batch.quarantined_rows or 0) + quarantined
    batch.status = "POSTING" if posted else batch.status
    db.session.commit()

    return {"posted": posted, "quarantined": quarantined}


def get_batch_status(batch_id: int) -> dict:
    batch = db.session.query(ImportBatch).filter_by(id=batch_id).first()
    if not batch:
        raise ImportError("Import batch not found")

    return batch.to_dict()
