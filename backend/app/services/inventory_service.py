# Overview: Service-layer operations for inventory; encapsulates business logic and database work.

# backend/app/services/inventory_service.py

from datetime import datetime, timedelta, timezone
from sqlalchemy import func

from ..extensions import db
from ..models import Product, InventoryTransaction
from app.time_utils import utcnow, parse_iso_datetime, to_utc_z
from .ledger_service import append_ledger_event
from .concurrency import lock_for_update, run_with_retry
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

Lifecycle ():
- ONLY transactions with status='POSTED' affect inventory calculations.
- DRAFT and APPROVED transactions exist but are ignored in quantity/cost calculations.
- Transactions default to POSTED for backwards compatibility with existing code.
- Use status='DRAFT' parameter to create drafts that require approval before posting.

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


def _ensure_product_in_store(
    store_id: int,
    product_id: int,
    *,
    require_active: bool = False,
    lock: bool = False
) -> Product:
    query = db.session.query(Product).filter_by(id=product_id)
    if lock:
        query = lock_for_update(query)
    product = query.first()
    if product is None:
        raise ValueError("product not found")
    if product.store_id != store_id:
        raise ValueError("product does not belong to store")
    if require_active and not product.is_active:
        raise ValueError("product is inactive")
    return product


def get_quantity_on_hand(store_id: int, product_id: int, as_of: datetime | None = None) -> int:
    """
    Calculate quantity on hand from POSTED transactions only.

    CRITICAL: Only status='POSTED' transactions affect inventory.
    DRAFT and APPROVED transactions are ignored.

    WHY: Draft transactions haven't been finalized. Including them would
    create phantom inventory that doesn't really exist.
    """
    q = db.session.query(
        func.coalesce(func.sum(InventoryTransaction.quantity_delta), 0)
    ).filter(
        InventoryTransaction.store_id == store_id,
        InventoryTransaction.product_id == product_id,
        InventoryTransaction.status == "POSTED",  # Only count posted
    )
    if as_of is not None:
        q = q.filter(InventoryTransaction.occurred_at <= as_of)

    return int(q.scalar() or 0)


def get_weighted_average_cost_cents(
    store_id: int, product_id: int, as_of: datetime | None = None
) -> int | None:
    """
    Calculate weighted average cost from POSTED RECEIVE and inbound TRANSFER transactions.

    CRITICAL: Only status='POSTED' AND type in ('RECEIVE', 'TRANSFER') with
    positive quantity and non-null unit_cost_cents affect WAC.
    DRAFT and APPROVED receive transactions are ignored.

    WHY: WAC should only include inventory that's actually been posted to the books.
    Draft receiving transactions might be corrections or data entry errors.
    """
    q = db.session.query(
        func.coalesce(func.sum(InventoryTransaction.quantity_delta), 0).label("units"),
        func.coalesce(
            func.sum(InventoryTransaction.quantity_delta * InventoryTransaction.unit_cost_cents),
            0,
        ).label("cost"),
    ).filter(
        InventoryTransaction.store_id == store_id,
        InventoryTransaction.product_id == product_id,
        InventoryTransaction.type.in_(["RECEIVE", "TRANSFER"]),
        InventoryTransaction.status == "POSTED",  # Only count posted
        InventoryTransaction.quantity_delta > 0,
        InventoryTransaction.unit_cost_cents.isnot(None),
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
    """
    Get the most recent POSTED receive or inbound transfer cost.

    CRITICAL: Only status='POSTED' transactions with cost are considered.
    """
    q = InventoryTransaction.query.filter_by(
        store_id=store_id,
        product_id=product_id,
        status="POSTED",  # Only count posted
    )
    q = q.filter(
        InventoryTransaction.type.in_(["RECEIVE", "TRANSFER"]),
        InventoryTransaction.quantity_delta > 0,
        InventoryTransaction.unit_cost_cents.isnot(None),
    )
    if as_of is not None:
        q = q.filter(InventoryTransaction.occurred_at <= as_of)

    tx = q.order_by(
        InventoryTransaction.occurred_at.desc(),
        InventoryTransaction.id.desc(),
    ).first()
    return tx.unit_cost_cents if tx else None


def _receive_inventory_inner(
    *,
    store_id: int,
    product_id: int,
    quantity: int,
    unit_cost_cents: int,
    occurred_dt: datetime,
    note: str | None = None,
    status: str = "POSTED",
    posted_by_user_id: int | None = None,
) -> InventoryTransaction:
    """Core RECEIVE logic without locking, retry, future-guard, or commit.

    Called by both the public receive_inventory() and import schemas.
    """
    tx = InventoryTransaction(
        store_id=store_id,
        product_id=product_id,
        type="RECEIVE",
        quantity_delta=quantity,
        unit_cost_cents=unit_cost_cents,
        note=note,
        occurred_at=occurred_dt,
        status=status,
        posted_by_user_id=posted_by_user_id,
        posted_at=utcnow() if posted_by_user_id else None,
    )
    db.session.add(tx)
    db.session.flush()
    return tx


def receive_inventory(
    *,
    store_id: int,
    product_id: int,
    quantity: int,
    unit_cost_cents: int,
    occurred_at=None,
    note: str | None = None,
    status: str = "POSTED",  # Default POSTED for backwards compatibility
) -> InventoryTransaction:
    """
    Create a RECEIVE inventory transaction.

    WHY status parameter:
    - status='POSTED' (default): Immediately affects inventory (backwards compatible)
    - status='DRAFT': Create draft that requires approval before affecting inventory
    - status='APPROVED': Pre-approved, ready to post (uncommon for receives)

    DESIGN NOTE: For direct receives (e.g., from POS interface or verified deliveries),
    use default status='POSTED'. For data entry that needs review, use status='DRAFT'.
    """
    def _op():
        _ensure_product_in_store(store_id, product_id, require_active=True, lock=True)

        occurred_dt = _parse_occurred_at(occurred_at)

        now = utcnow()
        if occurred_dt > (now + timedelta(minutes=2)):
            raise ValueError("occurred_at cannot be in the future")

        tx = _receive_inventory_inner(
            store_id=store_id,
            product_id=product_id,
            quantity=quantity,
            unit_cost_cents=unit_cost_cents,
            occurred_dt=occurred_dt,
            note=note,
            status=status,
        )

        # Only append to master ledger if POSTED
        # DRAFT and APPROVED transactions don't affect ledger until posted
        if status == "POSTED":
            append_ledger_event(
                store_id=store_id,
                event_type="inventory.received",
                event_category="inventory",
                entity_type="inventory_transaction",
                entity_id=tx.id,
                actor_user_id=tx.posted_by_user_id,
                occurred_at=tx.occurred_at,
                note=tx.note,
            )

        db.session.commit()
        return tx

    return run_with_retry(_op)



def _adjust_inventory_inner(
    *,
    store_id: int,
    product_id: int,
    quantity_delta: int,
    occurred_dt: datetime,
    note: str | None = None,
    status: str = "POSTED",
    posted_by_user_id: int | None = None,
) -> InventoryTransaction:
    """Core ADJUST logic without locking, retry, future-guard, or commit.

    Called by both the public adjust_inventory() and import schemas.
    """
    tx = InventoryTransaction(
        store_id=store_id,
        product_id=product_id,
        type="ADJUST",
        quantity_delta=quantity_delta,
        unit_cost_cents=None,
        note=note,
        occurred_at=occurred_dt,
        status=status,
        posted_by_user_id=posted_by_user_id,
        posted_at=utcnow() if posted_by_user_id else None,
    )
    db.session.add(tx)
    db.session.flush()
    return tx


def adjust_inventory(
    *,
    store_id: int,
    product_id: int,
    quantity_delta: int,
    occurred_at=None,
    note: str | None = None,
    status: str = "POSTED",  # Default POSTED for backwards compatibility
) -> InventoryTransaction:
    """
    Create an ADJUST inventory transaction.

    WHY status parameter:
    - status='POSTED' (default): Immediately affects inventory (backwards compatible)
    - status='DRAFT': Create draft adjustment for review (recommended for manual corrections)
    - status='APPROVED': Pre-approved, ready to post

    DESIGN NOTE: Manual adjustments should typically use status='DRAFT' to require
    manager approval before affecting inventory. Automatic adjustments (e.g., from
    cycle counts) might use status='POSTED' directly.
    """
    def _op():
        _ensure_product_in_store(store_id, product_id, require_active=True, lock=True)

        occurred_dt = _parse_occurred_at(occurred_at)

        now = utcnow()
        if occurred_dt > (now + timedelta(minutes=2)):
            raise ValueError("occurred_at cannot be in the future")

        # Only check negative on-hand for POSTED transactions
        # DRAFT transactions don't affect inventory, so negative check doesn't apply
        if status == "POSTED":
            current = get_quantity_on_hand(store_id, product_id, as_of=occurred_dt)
            if current + quantity_delta < 0:
                raise ValueError("adjustment would make on-hand negative")

        tx = _adjust_inventory_inner(
            store_id=store_id,
            product_id=product_id,
            quantity_delta=quantity_delta,
            occurred_dt=occurred_dt,
            note=note,
            status=status,
        )

        # Only append to master ledger if POSTED
        if status == "POSTED":
            append_ledger_event(
                store_id=store_id,
                event_type="inventory.adjusted",
                event_category="inventory",
                entity_type="inventory_transaction",
                entity_id=tx.id,
                actor_user_id=tx.posted_by_user_id,
                occurred_at=tx.occurred_at,
                note=tx.note,
            )

        db.session.commit()
        return tx

    return run_with_retry(_op)



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

def _sell_inventory_inner(
    *,
    store_id: int,
    product_id: int,
    quantity: int,
    sale_id: str,
    sale_line_id: str,
    occurred_dt: datetime,
    note: str | None = None,
    status: str = "POSTED",
    posted_by_user_id: int | None = None,
    skip_negative_check: bool = False,
) -> InventoryTransaction:
    """Core SALE logic without locking, retry, future-guard, or commit.

    Called by both the public sell_inventory() and import schemas.
    Computes WAC as-of occurred_dt and snapshots unit_cost_cents_at_sale / cogs_cents.
    """
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

    if status == "POSTED":
        if not skip_negative_check:
            current = get_quantity_on_hand(store_id, product_id, as_of=occurred_dt)
            if current - quantity < 0:
                raise ValueError("sale would make on-hand negative")

        wac = get_weighted_average_cost_cents(store_id, product_id, as_of=occurred_dt)
        if wac is None:
            raise ValueError("cannot sell without a cost basis (no RECEIVE history as-of occurred_at)")
    else:
        wac = get_weighted_average_cost_cents(store_id, product_id, as_of=occurred_dt)
        if wac is None:
            wac = 0

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
        status=status,
        posted_by_user_id=posted_by_user_id,
        posted_at=utcnow() if posted_by_user_id else None,
    )
    db.session.add(tx)
    db.session.flush()
    return tx


def sell_inventory(
    *,
    store_id: int,
    product_id: int,
    quantity: int,
    sale_id: str,
    sale_line_id: str,
    occurred_at=None,
    note: str | None = None,
    status: str = "POSTED",  # Sales typically posted immediately
    commit: bool = True,
    posted_by_user_id: int | None = None,
) -> InventoryTransaction:
    """
    Create a SALE inventory transaction.

    WHY status parameter:
    - status='POSTED' (default): Sale is complete, affects inventory immediately
    - status='DRAFT': Suspended/held sale (uncommon, for future quote/estimate support)

    DESIGN NOTE: POS sales should always use status='POSTED'. Draft sales are for
    future features like quotes, estimates, or suspended transactions.
    """
    def _op():
        _ensure_product_in_store(store_id, product_id, require_active=True, lock=True)

        occurred_dt = _parse_occurred_at(occurred_at)

        now = utcnow()
        if occurred_dt > (now + timedelta(minutes=2)):
            raise ValueError("occurred_at cannot be in the future")

        tx = _sell_inventory_inner(
            store_id=store_id,
            product_id=product_id,
            quantity=quantity,
            sale_id=sale_id,
            sale_line_id=sale_line_id,
            occurred_dt=occurred_dt,
            note=note,
            status=status,
            posted_by_user_id=posted_by_user_id,
        )

        # Only append to master ledger if POSTED
        if status == "POSTED":
            append_ledger_event(
                store_id=store_id,
                event_type="inventory.sale_recorded",
                event_category="inventory",
                entity_type="inventory_transaction",
                entity_id=tx.id,
                actor_user_id=tx.posted_by_user_id,
                occurred_at=tx.occurred_at,
                note=tx.note,
            )

        if commit:
            db.session.commit()
        else:
            db.session.flush()
        return tx

    return run_with_retry(_op)
