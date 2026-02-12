# Overview: Service-layer operations for imports; encapsulates business logic and database work.

from __future__ import annotations

import json
from dataclasses import dataclass
from collections import defaultdict
from typing import Any

from sqlalchemy import case, func

from ..extensions import db
from ..models import ImportBatch, ImportEntityMapping, ImportStagingRow, MasterLedgerEvent
from app.time_utils import utcnow
from .import_schemas import SCHEMAS, SchemaContext
from .ledger_service import append_ledger_event


class ImportError(ValueError):
    """Raised when import operations fail."""


CHUNK_SIZE_DEFAULT = 200


@dataclass
class BatchContext:
    batch: ImportBatch
    schema_name: str


def _get_batch_for_org(batch_id: int, org_id: int) -> ImportBatch:
    batch = db.session.query(ImportBatch).filter_by(id=batch_id, org_id=org_id).first()
    if not batch:
        raise ImportError("Import batch not found")
    return batch


def _json_dumps(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def _schema_for(batch: ImportBatch):
    schema = SCHEMAS.get(batch.import_type)
    if not schema:
        raise ImportError(f"Unsupported import_type: {batch.import_type}")
    return schema


def _mapping_lookup(batch_id: int) -> dict[tuple[str, str], int]:
    mappings = (
        db.session.query(ImportEntityMapping)
        .filter_by(batch_id=batch_id, status="MAPPED")
        .filter(ImportEntityMapping.local_entity_id.isnot(None))
        .all()
    )
    return {
        (str(m.entity_type).lower(), str(m.foreign_id)): int(m.local_entity_id)
        for m in mappings
    }


def _apply_entity_mappings(
    normalized: dict[str, Any],
    batch_id: int,
    lookup: dict[tuple[str, str], int] | None = None,
) -> dict[str, Any]:
    lookup = lookup if lookup is not None else _mapping_lookup(batch_id)

    def mapped(entity: str, foreign_value: Any) -> int | None:
        if foreign_value is None:
            return None
        return lookup.get((entity.lower(), str(foreign_value)))

    if normalized.get("store_id") is not None:
        maybe = mapped("store", normalized.get("store_id"))
        if maybe:
            normalized["store_id"] = maybe
    if normalized.get("created_by_user_id") is not None:
        maybe = mapped("user", normalized.get("created_by_user_id"))
        if maybe:
            normalized["created_by_user_id"] = maybe
    if normalized.get("register_id") is not None:
        maybe = mapped("register", normalized.get("register_id"))
        if maybe:
            normalized["register_id"] = maybe
    if normalized.get("product_id") is not None:
        maybe = mapped("product", normalized.get("product_id"))
        if maybe:
            normalized["product_id"] = maybe

    for line in normalized.get("lines", []) if isinstance(normalized.get("lines"), list) else []:
        if line.get("product_id") is not None:
            maybe = mapped("product", line.get("product_id"))
            if maybe:
                line["product_id"] = maybe
    return normalized


def _refresh_batch_counts(batch: ImportBatch) -> None:
    counts = (
        db.session.query(
            func.count(ImportStagingRow.id).label("total"),
            func.sum(case((ImportStagingRow.mapping_status == "READY", 1), else_=0)).label("ready"),
            func.sum(case((ImportStagingRow.mapping_status == "UNMAPPED", 1), else_=0)).label("unmapped"),
            func.sum(case((ImportStagingRow.mapping_status == "ERROR", 1), else_=0)).label("mapping_error"),
            func.sum(case((ImportStagingRow.posting_status == "POSTED", 1), else_=0)).label("posted"),
            func.sum(case((ImportStagingRow.posting_status == "ERROR", 1), else_=0)).label("post_error"),
            func.sum(case((ImportStagingRow.posting_status == "QUARANTINED", 1), else_=0)).label("quarantined"),
        )
        .filter(ImportStagingRow.batch_id == batch.id)
        .one()
    )

    batch.total_rows = int(counts.total or 0)
    batch.staged_rows = int(counts.total or 0)
    batch.mapped_rows = int(counts.ready or 0)
    batch.posted_rows = int(counts.posted or 0)
    batch.error_rows = int((counts.mapping_error or 0) + (counts.post_error or 0))
    batch.quarantined_rows = int(counts.quarantined or 0)
    if batch.total_rows and (batch.posted_rows + batch.error_rows + batch.quarantined_rows) >= batch.total_rows:
        batch.status = "COMPLETED"
        batch.completed_at = batch.completed_at or utcnow()
    elif batch.mapped_rows > 0:
        batch.status = "POSTING"
    elif batch.error_rows > 0:
        batch.status = "MAPPING"
    else:
        batch.status = "STAGED"


def create_import_batch(
    *,
    org_id: int,
    import_type: str,
    created_by_user_id: int,
    source_file_name: str | None = None,
    source_file_format: str | None = None,
) -> ImportBatch:
    if import_type not in SCHEMAS:
        raise ImportError(f"Unsupported import_type: {import_type}")
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


def stage_rows(*, batch_id: int, org_id: int, rows: list[dict[str, Any]]) -> dict[str, Any]:
    batch = _get_batch_for_org(batch_id, org_id)
    schema = _schema_for(batch)
    mapping_lookup = _mapping_lookup(batch.id)
    staged = 0

    for idx, row in enumerate(rows, start=1):
        raw_data = row if isinstance(row, dict) else {}
        foreign_id = raw_data.get("foreign_id") or raw_data.get("id")
        row_number = int(raw_data.get("row_number") or idx)

        normalized = schema.normalize_row(raw_data)
        normalized = _apply_entity_mappings(normalized, batch.id, lookup=mapping_lookup)
        validation_errors = schema.validate_row(normalized)
        if validation_errors:
            mapping_status = "ERROR"
            error_message = "; ".join(validation_errors)
            unmapped = []
        else:
            unmapped = schema.auto_resolve_references(normalized, org_id)
            if unmapped:
                mapping_status = "UNMAPPED"
                error_message = None
            else:
                mapping_status = "READY"
                error_message = None

        staging = ImportStagingRow(
            batch_id=batch.id,
            row_number=row_number,
            raw_data=_json_dumps(raw_data),
            normalized_data=normalized,
            foreign_id=str(foreign_id) if foreign_id is not None else None,
            mapping_status=mapping_status,
            posting_status="PENDING",
            error_message=error_message,
            unmapped_references=_json_dumps(unmapped) if unmapped else None,
        )
        db.session.add(staging)
        staged += 1

    batch.status = "STAGED"
    _refresh_batch_counts(batch)
    db.session.commit()
    return {"staged": staged, "batch_id": batch.id}


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


def set_entity_mapping(
    *,
    batch_id: int,
    org_id: int,
    entity_type: str,
    foreign_id: str,
    local_entity_id: int,
) -> ImportEntityMapping:
    batch = _get_batch_for_org(batch_id, org_id)
    if not entity_type or not foreign_id:
        raise ImportError("entity_type and foreign_id are required")

    mapping = _ensure_mapping(batch_id, entity_type, foreign_id, local_entity_id)
    db.session.flush()

    # Re-evaluate UNMAPPED rows after mapping is supplied.
    rows = (
        db.session.query(ImportStagingRow)
        .filter(ImportStagingRow.batch_id == batch_id)
        .filter(ImportStagingRow.mapping_status == "UNMAPPED")
        .all()
    )
    schema = _schema_for(batch)
    mapping_lookup = _mapping_lookup(batch.id)
    for row in rows:
        normalized = row.normalized_data or schema.normalize_row(json.loads(row.raw_data))
        normalized = _apply_entity_mappings(normalized, batch.id, lookup=mapping_lookup)
        unmapped = schema.auto_resolve_references(normalized, org_id)
        row.normalized_data = normalized
        row.unmapped_references = _json_dumps(unmapped) if unmapped else None
        row.mapping_status = "UNMAPPED" if unmapped else "READY"
        row.error_message = None

    _refresh_batch_counts(batch)
    db.session.commit()
    return mapping


def list_batch_rows(
    *,
    batch_id: int,
    org_id: int,
    status: str | None = None,
    page: int = 1,
    per_page: int = 100,
) -> dict[str, Any]:
    _get_batch_for_org(batch_id, org_id)
    page = max(1, int(page or 1))
    per_page = max(1, min(500, int(per_page or 100)))

    query = db.session.query(ImportStagingRow).filter_by(batch_id=batch_id)
    if status:
        query = query.filter(
            (ImportStagingRow.mapping_status == status)
            | (ImportStagingRow.posting_status == status)
        )

    total = query.count()
    rows = (
        query.order_by(ImportStagingRow.row_number.asc(), ImportStagingRow.id.asc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {
        "rows": [r.to_dict() for r in rows],
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": (total + per_page - 1) // per_page if per_page else 1,
    }


def get_unmapped_entities(*, batch_id: int, org_id: int) -> dict[str, Any]:
    _get_batch_for_org(batch_id, org_id)
    rows = (
        db.session.query(ImportStagingRow)
        .filter_by(batch_id=batch_id, mapping_status="UNMAPPED")
        .all()
    )
    grouped: dict[str, set[str]] = defaultdict(set)
    details: list[dict[str, Any]] = []

    for row in rows:
        refs = json.loads(row.unmapped_references) if row.unmapped_references else []
        if not isinstance(refs, list):
            refs = []
        for ref in refs:
            entity_type = str(ref.get("entity_type") or "UNKNOWN").upper()
            value = str(ref.get("value"))
            grouped[entity_type].add(value)
            details.append(
                {
                    "row_number": row.row_number,
                    "field": ref.get("field"),
                    "entity_type": entity_type,
                    "value": value,
                }
            )
    return {
        "unmapped": {k: sorted(v) for k, v in grouped.items()},
        "details": details,
        "count": len(details),
    }


def _mark_existing_posted_from_ledger(row: ImportStagingRow) -> bool:
    existing = (
        db.session.query(MasterLedgerEvent)
        .filter(MasterLedgerEvent.import_batch_id == row.batch_id)
        .filter(MasterLedgerEvent.source_row_number == row.row_number)
        .first()
    )
    if not existing:
        return False
    row.posting_status = "POSTED"
    row.mapping_status = "READY"
    row.posted_entity_type = existing.entity_type
    row.posted_entity_id = existing.entity_id
    row.posted_at = row.posted_at or utcnow()
    row.error_message = None
    return True


def post_mapped_rows(
    *,
    batch_id: int,
    org_id: int,
    actor_user_id: int,
    limit: int = CHUNK_SIZE_DEFAULT,
) -> dict[str, Any]:
    batch = _get_batch_for_org(batch_id, org_id)
    schema = _schema_for(batch)
    mapping_lookup = _mapping_lookup(batch.id)
    limit = max(1, int(limit or CHUNK_SIZE_DEFAULT))

    ready_rows = (
        db.session.query(ImportStagingRow)
        .filter(ImportStagingRow.batch_id == batch_id)
        .filter(ImportStagingRow.mapping_status == "READY")
        .filter(ImportStagingRow.posting_status.in_(["PENDING", "ERROR"]))
        .order_by(ImportStagingRow.row_number.asc(), ImportStagingRow.id.asc())
        .limit(limit)
        .all()
    )
    if batch.import_type in ("Sales", "Inventory"):
        ready_rows.sort(key=lambda r: (str((r.normalized_data or {}).get("occurred_at") or ""), r.row_number))

    posted = 0
    skipped = 0
    errored = 0
    processed = 0

    for index, row in enumerate(ready_rows, start=1):
        processed += 1
        if row.posting_status == "POSTED":
            skipped += 1
            continue
        if _mark_existing_posted_from_ledger(row):
            skipped += 1
            continue

        nested = db.session.begin_nested()
        try:
            normalized = row.normalized_data or schema.normalize_row(json.loads(row.raw_data))
            normalized = _apply_entity_mappings(normalized, batch.id, lookup=mapping_lookup)
            row.normalized_data = normalized
            validation_errors = schema.validate_row(normalized)
            if validation_errors:
                row.mapping_status = "ERROR"
                row.posting_status = "ERROR"
                row.error_message = "; ".join(validation_errors)
                row.unmapped_references = None
                errored += 1
                nested.commit()
                continue

            unmapped = schema.auto_resolve_references(normalized, org_id)
            if unmapped:
                row.mapping_status = "UNMAPPED"
                row.posting_status = "PENDING"
                row.unmapped_references = _json_dumps(unmapped)
                row.error_message = None
                nested.commit()
                continue

            result = schema.post_row(
                normalized,
                SchemaContext(
                    batch_id=batch.id,
                    org_id=org_id,
                    actor_user_id=actor_user_id,
                    staging_row_number=row.row_number,
                    source_foreign_id=row.foreign_id,
                ),
            )

            ev = append_ledger_event(
                store_id=result["store_id"],
                event_type=result["event_type"],
                event_category=result["event_category"],
                entity_type=result["entity_type"],
                entity_id=result["entity_id"],
                actor_user_id=actor_user_id,
                sale_id=result.get("sale_id"),
                occurred_at=result.get("occurred_at") or utcnow(),
                import_batch_id=batch.id,
                source="IMPORT",
                source_row_number=row.row_number,
                source_foreign_id=row.foreign_id,
                note=f"Imported from batch {batch.id}, row {row.row_number}",
            )
            # Ensure we resolve and persist generated ids before status update.
            db.session.flush()

            row.mapping_status = "READY"
            row.posting_status = "POSTED"
            row.posted_entity_type = result["entity_type"]
            row.posted_entity_id = result["entity_id"]
            row.posted_at = utcnow()
            row.error_message = None
            row.unmapped_references = None
            posted += 1
            nested.commit()
        except Exception as exc:  # noqa: BLE001
            nested.rollback()
            row.posting_status = "ERROR"
            row.error_message = str(exc)
            errored += 1

        if index % CHUNK_SIZE_DEFAULT == 0:
            db.session.flush()
            db.session.commit()

    _refresh_batch_counts(batch)
    batch.last_processed_row = max((r.row_number for r in ready_rows), default=batch.last_processed_row or 0)
    batch.started_at = batch.started_at or utcnow()
    db.session.commit()
    return {
        "batch_id": batch_id,
        "processed": processed,
        "posted": posted,
        "skipped": skipped,
        "errors": errored,
    }


def get_batch_status(*, batch_id: int, org_id: int) -> dict[str, Any]:
    batch = _get_batch_for_org(batch_id, org_id)
    _refresh_batch_counts(batch)
    db.session.commit()
    return batch.to_dict()
