# backend/app/services/inventory_service.py

from datetime import datetime, timedelta, timezone
from sqlalchemy import func

from ..extensions import db
from ..models import Product, InventoryTransaction
from app.time_utils import utcnow, parse_iso_datetime, to_utc_z
from .ledger_service import append_ledger_event
"""
APOS Inventory Invariants & Time Semantics (authoritative)

Canonical time handling:
- All internal datetimes are UTC-naive (tzinfo=None).
- API accepts ISO-8601 with 'Z' or offsets; inputs are normalized to UTC-naive.
- API responses serialize datetimes as ISO-8601 'Z' strings.

As-of semantics:
- All "as_of" filters are inclusive: occurred_at <= as_of.

Inventory model:
- Inventory is ledger-derived from InventoryTransaction rows; never stored as a mutable quantity field.
- Quantity on hand is SUM(quantity_delta) over transactions (optionally as-of).

Business invariants:
- On-hand quantity may never go negative at the effective time of a transaction.
- RECEIVE increases on-hand and may include unit_cost_cents.
- ADJUST changes on-hand but does NOT affect weighted average cost (WAC).
- WAC is computed from RECEIVE transactions only, as:
    sum(qty * unit_cost) / sum(qty)  (nearest-cent rounding, half-up)
  and is optionally as-of.

Audit:
- Each inventory transaction creation appends a MasterLedgerEvent in the same DB transaction.
- Master ledger is append-only (no updates/deletes).
"""



from datetime import datetime, timedelta, timezone  # add timezone
from app.time_utils import utcnow, parse_iso_datetime  # add parse_iso_datetime

def _parse_occurred_at(value):
    """
    Normalize occurred_at to canonical UTC-naive datetime.

    Accepts:
    - None -> utcnow() (UTC-naive)
    - datetime:
        - aware -> convert to UTC, strip tzinfo
        - naive -> treat as UTC-naive
    - str -> parse_iso_datetime (accepts Z/offsets; returns UTC-naive)
    """
    if value is None:
        return utcnow()

    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value  # already naive; treat as UTC-naive

    if isinstance(value, str):
        dt = parse_iso_datetime(value)
        if dt is None:
            raise ValueError("invalid occurred_at")
        return dt

    raise ValueError("invalid occurred_at")


def _ensure_product_in_store(store_id: int, product_id: int, *, require_active: bool = False) -> Product:
    product = Product.query.get(product_id)
    if product is None:
        raise ValueError("product not found")
    if product.store_id != store_id:
        raise ValueError("product does not belong to store")
    if require_active and not product.is_active:
        raise ValueError("product is inactive")
    return product


def get_quantity_on_hand(store_id: int, product_id: int, as_of: datetime | None = None) -> int:
    q = db.session.query(
        func.coalesce(func.sum(InventoryTransaction.quantity_delta), 0)
    ).filter(
        InventoryTransaction.store_id == store_id,
        InventoryTransaction.product_id == product_id,
    )
    if as_of is not None:
        q = q.filter(InventoryTransaction.occurred_at <= as_of)

    return int(q.scalar() or 0)


def get_weighted_average_cost_cents(
    store_id: int, product_id: int, as_of: datetime | None = None
) -> int | None:
    q = db.session.query(
        func.coalesce(func.sum(InventoryTransaction.quantity_delta), 0).label("units"),
        func.coalesce(
            func.sum(InventoryTransaction.quantity_delta * InventoryTransaction.unit_cost_cents),
            0,
        ).label("cost"),
    ).filter(
        InventoryTransaction.store_id == store_id,
        InventoryTransaction.product_id == product_id,
        InventoryTransaction.type == "RECEIVE",
    )
    if as_of is not None:
        q = q.filter(InventoryTransaction.occurred_at <= as_of)

    row = q.one()
    total_units = int(row.units or 0)
    if total_units <= 0:
        return None

    total_cost = int(row.cost or 0)
    # nearest-cent rounding (half-up)
    return (total_cost + (total_units // 2)) // total_units


def get_recent_receive_cost_cents(
    store_id: int, product_id: int, as_of: datetime | None = None
) -> int | None:
    q = InventoryTransaction.query.filter_by(
        store_id=store_id,
        product_id=product_id,
        type="RECEIVE",
    )
    if as_of is not None:
        q = q.filter(InventoryTransaction.occurred_at <= as_of)

    tx = q.order_by(
        InventoryTransaction.occurred_at.desc(),
        InventoryTransaction.id.desc(),
    ).first()
    return tx.unit_cost_cents if tx else None


def receive_inventory(
    *,
    store_id: int,
    product_id: int,
    quantity: int,
    unit_cost_cents: int,
    occurred_at=None,
    note: str | None = None,
) -> InventoryTransaction:
    _ensure_product_in_store(store_id, product_id, require_active=True)

    occurred_dt = _parse_occurred_at(occurred_at)

    now = utcnow()
    if occurred_dt > (now + timedelta(minutes=2)):
        raise ValueError("occurred_at cannot be in the future")

    tx = InventoryTransaction(
        store_id=store_id,
        product_id=product_id,
        type="RECEIVE",
        quantity_delta=quantity,
        unit_cost_cents=unit_cost_cents,
        note=note,
        occurred_at=occurred_dt,
    )
    db.session.add(tx)
    db.session.flush()  # ensure tx.id is assigned before we reference it

    append_ledger_event(
        store_id=store_id,
        event_type="INV_TX_CREATED",
        entity_type="inventory_transaction",
        entity_id=tx.id,
        occurred_at=tx.occurred_at,
        note=tx.note,
    )

    db.session.commit()
    return tx



def adjust_inventory(
    *,
    store_id: int,
    product_id: int,
    quantity_delta: int,
    occurred_at=None,
    note: str | None = None,
) -> InventoryTransaction:
    _ensure_product_in_store(store_id, product_id, require_active=True)

    occurred_dt = _parse_occurred_at(occurred_at)

    now = utcnow()
    if occurred_dt > (now + timedelta(minutes=2)):
        raise ValueError("occurred_at cannot be in the future")

    # Disallow negative on-hand at the effective time
    current = get_quantity_on_hand(store_id, product_id, as_of=occurred_dt)
    if current + quantity_delta < 0:
        raise ValueError("adjustment would make on-hand negative")

    tx = InventoryTransaction(
        store_id=store_id,
        product_id=product_id,
        type="ADJUST",
        quantity_delta=quantity_delta,
        unit_cost_cents=None,
        note=note,
        occurred_at=occurred_dt,
    )
    db.session.add(tx)
    db.session.flush()  # ensure tx.id is assigned before we reference it

    append_ledger_event(
        store_id=store_id,
        event_type="INV_TX_CREATED",
        entity_type="inventory_transaction",
        entity_id=tx.id,
        occurred_at=tx.occurred_at,
        note=tx.note,
    )

    db.session.commit()
    return tx



def get_inventory_summary(
    *, store_id: int, product_id: int, as_of=None
) -> dict:
    _ensure_product_in_store(store_id, product_id)

    as_of_dt = _parse_occurred_at(as_of)  # defaults to now when None

    qty = get_quantity_on_hand(store_id, product_id, as_of=as_of_dt)
    wac = get_weighted_average_cost_cents(store_id, product_id, as_of=as_of_dt)
    recent = get_recent_receive_cost_cents(store_id, product_id, as_of=as_of_dt)

    return {
        "store_id": store_id,
        "product_id": product_id,
        "as_of": to_utc_z(as_of_dt) if as_of_dt else None,
        "quantity_on_hand": qty,
        "weighted_average_cost_cents": wac,
        "recent_unit_cost_cents": recent,
        "inventory_value_cents": (qty * wac) if wac is not None else None,
    }

def list_inventory_transactions(*, store_id: int, product_id: int, limit: int = 200):
    _ensure_product_in_store(store_id, product_id)

    q = InventoryTransaction.query.filter_by(
        store_id=store_id,
        product_id=product_id,
    ).order_by(
        InventoryTransaction.occurred_at.desc(),
        InventoryTransaction.id.desc(),
    )

    return q.limit(limit).all()

def sell_inventory(
    *,
    store_id: int,
    product_id: int,
    quantity: int,
    sale_id: str,
    sale_line_id: str,
    occurred_at=None,
    note: str | None = None,
) -> InventoryTransaction:
    _ensure_product_in_store(store_id, product_id, require_active=True)

    occurred_dt = _parse_occurred_at(occurred_at)

    now = utcnow()
    if occurred_dt > (now + timedelta(minutes=2)):
        raise ValueError("occurred_at cannot be in the future")

    # Idempotency: if already posted, return it
    existing = InventoryTransaction.query.filter_by(
        store_id=store_id,
        sale_id=sale_id,
        sale_line_id=sale_line_id,
    ).first()
    if existing is not None:
        if existing.type != "SALE" or existing.product_id != product_id:
            raise ValueError("sale_id/sale_line_id already used for a different transaction")
        return existing

    # Oversell check at effective time
    current = get_quantity_on_hand(store_id, product_id, as_of=occurred_dt)
    if current - quantity < 0:
        raise ValueError("sale would make on-hand negative")

    # Snapshot WAC at sale time
    wac = get_weighted_average_cost_cents(store_id, product_id, as_of=occurred_dt)
    if wac is None:
        raise ValueError("cannot sell without a cost basis (no RECEIVE history as-of occurred_at)")

    tx = InventoryTransaction(
        store_id=store_id,
        product_id=product_id,
        type="SALE",
        quantity_delta=-quantity,
        unit_cost_cents=None,
        sale_id=sale_id,
        sale_line_id=sale_line_id,
        unit_cost_cents_at_sale=wac,
        cogs_cents=wac * quantity,
        note=note,
        occurred_at=occurred_dt,
    )
    db.session.add(tx)
    db.session.flush()

    append_ledger_event(
        store_id=store_id,
        event_type="SALE_RECORDED",
        entity_type="inventory_transaction",
        entity_id=tx.id,
        occurred_at=tx.occurred_at,
        note=tx.note,
    )

    db.session.commit()
    return tx
