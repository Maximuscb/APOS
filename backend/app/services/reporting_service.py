# Overview: Service-layer operations for reporting; encapsulates business logic and database work.

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from sqlalchemy import func, case
from sqlalchemy.orm import aliased

from app.extensions import db
from app.models import (
    Sale,
    SaleLine,
    Payment,
    PaymentTransaction,
    Return,
    ReturnLine,
    Product,
    InventoryTransaction,
    Vendor,
    ReceiveDocument,
    ReceiveDocumentLine,
    Register,
    RegisterSession,
    CashDrawerEvent,
    TimeClockEntry,
    TimeClockBreak,
    TimeClockCorrection,
    Count,
    CountLine,
    Transfer,
    TransferLine,
    User,
    Customer,
    CustomerRewardAccount,
    CustomerRewardTransaction,
    MasterLedgerEvent,
    SecurityEvent,
    Store,
)
from app.services.inventory_service import get_quantity_on_hand, get_weighted_average_cost_cents
from app.services.store_service import get_descendant_store_ids
from app.time_utils import parse_iso_datetime, utcnow, to_utc_z


class ReportError(Exception):
    """Raised when report generation fails."""
    pass


def _parse_range(start: str | None, end: str | None) -> tuple[datetime | None, datetime | None]:
    start_dt = parse_iso_datetime(start) if start else None
    end_dt = parse_iso_datetime(end) if end else None
    return start_dt, end_dt


def _resolve_store_ids(store_id: int, include_children: bool) -> list[int]:
    store = db.session.query(Store).filter_by(id=store_id).first()
    if not store:
        raise ReportError("Store not found")
    if include_children:
        return get_descendant_store_ids(store_id, include_self=True)
    return [store_id]


# ---------------------------------------------------------------------------
# Helper: common sale-time expression
# ---------------------------------------------------------------------------

def _sale_time():
    return func.coalesce(Sale.completed_at, Sale.created_at)


# ===========================================================================
# EXISTING REPORTS
# ===========================================================================


def sales_report(
    *,
    store_id: int,
    include_children: bool,
    start: str | None,
    end: str | None,
    group_by: str = "day",
) -> dict:
    start_dt, end_dt = _parse_range(start, end)
    store_ids = _resolve_store_ids(store_id, include_children)

    sale_time = func.coalesce(Sale.completed_at, Sale.created_at)

    if group_by == "day":
        period_expr = func.strftime("%Y-%m-%d", sale_time)
    elif group_by == "week":
        period_expr = func.strftime("%Y-W%W", sale_time)
    elif group_by == "month":
        period_expr = func.strftime("%Y-%m", sale_time)
    else:
        raise ReportError("group_by must be day, week, or month")

    query = db.session.query(
        period_expr.label("period"),
        func.count(func.distinct(Sale.id)).label("sales_count"),
        func.coalesce(func.sum(SaleLine.quantity), 0).label("items_sold"),
        func.coalesce(func.sum(SaleLine.line_total_cents), 0).label("gross_sales_cents"),
    ).join(SaleLine, SaleLine.sale_id == Sale.id).filter(
        Sale.status == "POSTED",
        Sale.store_id.in_(store_ids),
    )

    if start_dt:
        query = query.filter(sale_time >= start_dt)
    if end_dt:
        query = query.filter(sale_time <= end_dt)

    rows = query.group_by("period").order_by("period").all()
    return {
        "store_ids": store_ids,
        "group_by": group_by,
        "start": to_utc_z(start_dt) if start_dt else None,
        "end": to_utc_z(end_dt) if end_dt else None,
        "rows": [
            {
                "period": row.period,
                "sales_count": int(row.sales_count or 0),
                "items_sold": int(row.items_sold or 0),
                "gross_sales_cents": int(row.gross_sales_cents or 0),
            }
            for row in rows
        ],
    }


def inventory_valuation(
    *,
    store_id: int,
    include_children: bool,
    as_of: str | None,
) -> dict:
    as_of_dt = parse_iso_datetime(as_of) if as_of else utcnow()
    store_ids = _resolve_store_ids(store_id, include_children)

    products = db.session.query(Product).filter(
        Product.store_id.in_(store_ids),
        Product.is_active.is_(True),
    ).order_by(Product.name.asc()).all()

    rows = []
    total_value_cents = 0
    for product in products:
        qty = get_quantity_on_hand(product.store_id, product.id, as_of=as_of_dt)
        wac = get_weighted_average_cost_cents(product.store_id, product.id, as_of=as_of_dt)
        value = qty * wac if wac is not None else None
        if value is not None:
            total_value_cents += value
        rows.append(
            {
                "store_id": product.store_id,
                "product_id": product.id,
                "sku": product.sku,
                "name": product.name,
                "quantity_on_hand": qty,
                "weighted_average_cost_cents": wac,
                "inventory_value_cents": value,
            }
        )

    return {
        "store_ids": store_ids,
        "as_of": to_utc_z(as_of_dt),
        "total_value_cents": total_value_cents,
        "rows": rows,
    }


def cogs_margin_report(
    *,
    store_id: int,
    include_children: bool,
    start: str | None,
    end: str | None,
) -> dict:
    start_dt, end_dt = _parse_range(start, end)
    store_ids = _resolve_store_ids(store_id, include_children)

    sale_time = func.coalesce(Sale.completed_at, Sale.created_at)

    sales_query = db.session.query(
        func.coalesce(func.sum(SaleLine.line_total_cents), 0)
    ).join(Sale, SaleLine.sale_id == Sale.id).filter(
        Sale.status == "POSTED",
        Sale.store_id.in_(store_ids),
    )

    if start_dt:
        sales_query = sales_query.filter(sale_time >= start_dt)
    if end_dt:
        sales_query = sales_query.filter(sale_time <= end_dt)

    revenue_cents = int(sales_query.scalar() or 0)

    cogs_query = db.session.query(
        func.coalesce(func.sum(InventoryTransaction.cogs_cents), 0)
    ).filter(
        InventoryTransaction.store_id.in_(store_ids),
        InventoryTransaction.status == "POSTED",
        InventoryTransaction.type.in_(["SALE", "RETURN"]),
    )

    if start_dt:
        cogs_query = cogs_query.filter(InventoryTransaction.occurred_at >= start_dt)
    if end_dt:
        cogs_query = cogs_query.filter(InventoryTransaction.occurred_at <= end_dt)

    cogs_cents = int(cogs_query.scalar() or 0)
    margin_cents = revenue_cents - cogs_cents
    margin_pct = (margin_cents / revenue_cents * 100.0) if revenue_cents else None

    return {
        "store_ids": store_ids,
        "start": to_utc_z(start_dt) if start_dt else None,
        "end": to_utc_z(end_dt) if end_dt else None,
        "revenue_cents": revenue_cents,
        "cogs_cents": cogs_cents,
        "margin_cents": margin_cents,
        "margin_pct": round(margin_pct, 2) if margin_pct is not None else None,
    }


def abc_analysis(
    *,
    store_id: int,
    include_children: bool,
    start: str | None,
    end: str | None,
) -> dict:
    start_dt, end_dt = _parse_range(start, end)
    store_ids = _resolve_store_ids(store_id, include_children)

    sale_time = func.coalesce(Sale.completed_at, Sale.created_at)

    query = db.session.query(
        SaleLine.product_id.label("product_id"),
        Product.sku.label("sku"),
        Product.name.label("name"),
        func.coalesce(func.sum(SaleLine.line_total_cents), 0).label("revenue_cents"),
        func.coalesce(func.sum(SaleLine.quantity), 0).label("units_sold"),
    ).join(Sale, SaleLine.sale_id == Sale.id).join(
        Product, SaleLine.product_id == Product.id
    ).filter(
        Sale.status == "POSTED",
        Sale.store_id.in_(store_ids),
    )

    if start_dt:
        query = query.filter(sale_time >= start_dt)
    if end_dt:
        query = query.filter(sale_time <= end_dt)

    rows = query.group_by(SaleLine.product_id, Product.sku, Product.name).order_by(
        func.sum(SaleLine.line_total_cents).desc()
    ).all()
    total_revenue = sum(int(row.revenue_cents or 0) for row in rows)

    results = []
    cumulative = 0.0
    for row in rows:
        revenue = int(row.revenue_cents or 0)
        share = (revenue / total_revenue) if total_revenue else 0.0
        cumulative += share
        if cumulative <= 0.80:
            bucket = "A"
        elif cumulative <= 0.95:
            bucket = "B"
        else:
            bucket = "C"
        results.append(
            {
                "product_id": row.product_id,
                "sku": row.sku,
                "name": row.name,
                "revenue_cents": revenue,
                "units_sold": int(row.units_sold or 0),
                "share_pct": round(share * 100.0, 2),
                "cumulative_pct": round(cumulative * 100.0, 2),
                "category": bucket,
            }
        )

    return {
        "store_ids": store_ids,
        "start": to_utc_z(start_dt) if start_dt else None,
        "end": to_utc_z(end_dt) if end_dt else None,
        "total_revenue_cents": total_revenue,
        "rows": results,
    }


def slow_dead_stock(
    *,
    store_id: int,
    include_children: bool,
    as_of: str | None,
    slow_days: int = 30,
    dead_days: int = 90,
) -> dict:
    as_of_dt = parse_iso_datetime(as_of) if as_of else utcnow()
    store_ids = _resolve_store_ids(store_id, include_children)

    last_sales = db.session.query(
        InventoryTransaction.store_id.label("store_id"),
        InventoryTransaction.product_id.label("product_id"),
        func.max(InventoryTransaction.occurred_at).label("last_sale_at"),
    ).filter(
        InventoryTransaction.store_id.in_(store_ids),
        InventoryTransaction.type == "SALE",
        InventoryTransaction.status == "POSTED",
    ).group_by(InventoryTransaction.store_id, InventoryTransaction.product_id).all()

    last_sale_map = {
        (row.store_id, row.product_id): row.last_sale_at for row in last_sales
    }

    products = db.session.query(Product).filter(
        Product.store_id.in_(store_ids),
        Product.is_active.is_(True),
    ).order_by(Product.name.asc()).all()

    slow = []
    dead = []
    never_sold = []

    for product in products:
        last_sale = last_sale_map.get((product.store_id, product.id))
        if last_sale is None:
            never_sold.append(
                {
                    "store_id": product.store_id,
                    "product_id": product.id,
                    "sku": product.sku,
                    "name": product.name,
                    "last_sale_at": None,
                }
            )
            continue

        days_since = (as_of_dt - last_sale).days
        entry = {
            "store_id": product.store_id,
            "product_id": product.id,
            "sku": product.sku,
            "name": product.name,
            "last_sale_at": to_utc_z(last_sale),
            "days_since_last_sale": days_since,
        }

        if days_since >= dead_days:
            dead.append(entry)
        elif days_since >= slow_days:
            slow.append(entry)

    return {
        "store_ids": store_ids,
        "as_of": to_utc_z(as_of_dt),
        "slow_days": slow_days,
        "dead_days": dead_days,
        "slow_moving": slow,
        "dead_stock": dead,
        "never_sold": never_sold,
    }


def cashier_performance(
    *,
    store_id: int,
    include_children: bool,
    start: str | None,
    end: str | None,
) -> dict:
    start_dt, end_dt = _parse_range(start, end)
    store_ids = _resolve_store_ids(store_id, include_children)

    sale_time = func.coalesce(Sale.completed_at, Sale.created_at)

    query = db.session.query(
        Sale.created_by_user_id.label("user_id"),
        func.count(func.distinct(Sale.id)).label("sales_count"),
        func.coalesce(func.sum(SaleLine.line_total_cents), 0).label("gross_sales_cents"),
    ).join(SaleLine, SaleLine.sale_id == Sale.id).filter(
        Sale.status == "POSTED",
        Sale.store_id.in_(store_ids),
    )

    if start_dt:
        query = query.filter(sale_time >= start_dt)
    if end_dt:
        query = query.filter(sale_time <= end_dt)

    rows = query.group_by(Sale.created_by_user_id).order_by(func.sum(SaleLine.line_total_cents).desc()).all()
    return {
        "store_ids": store_ids,
        "start": to_utc_z(start_dt) if start_dt else None,
        "end": to_utc_z(end_dt) if end_dt else None,
        "rows": [
            {
                "user_id": row.user_id,
                "sales_count": int(row.sales_count or 0),
                "gross_sales_cents": int(row.gross_sales_cents or 0),
            }
            for row in rows
        ],
    }


def register_performance(
    *,
    store_id: int,
    include_children: bool,
    start: str | None,
    end: str | None,
) -> dict:
    start_dt, end_dt = _parse_range(start, end)
    store_ids = _resolve_store_ids(store_id, include_children)

    sale_time = func.coalesce(Sale.completed_at, Sale.created_at)

    query = db.session.query(
        Sale.register_id.label("register_id"),
        func.count(func.distinct(Sale.id)).label("sales_count"),
        func.coalesce(func.sum(SaleLine.line_total_cents), 0).label("gross_sales_cents"),
    ).join(SaleLine, SaleLine.sale_id == Sale.id).filter(
        Sale.status == "POSTED",
        Sale.store_id.in_(store_ids),
    )

    if start_dt:
        query = query.filter(sale_time >= start_dt)
    if end_dt:
        query = query.filter(sale_time <= end_dt)

    rows = query.group_by(Sale.register_id).order_by(func.sum(SaleLine.line_total_cents).desc()).all()
    return {
        "store_ids": store_ids,
        "start": to_utc_z(start_dt) if start_dt else None,
        "end": to_utc_z(end_dt) if end_dt else None,
        "rows": [
            {
                "register_id": row.register_id,
                "sales_count": int(row.sales_count or 0),
                "gross_sales_cents": int(row.gross_sales_cents or 0),
            }
            for row in rows
        ],
    }


def audit_trail(
    *,
    store_id: int | None,
    event_type: str | None,
    entity_type: str | None,
    start: str | None,
    end: str | None,
    limit: int = 200,
) -> dict:
    start_dt, end_dt = _parse_range(start, end)

    query = db.session.query(MasterLedgerEvent).order_by(MasterLedgerEvent.occurred_at.desc())
    if store_id is not None:
        query = query.filter(MasterLedgerEvent.store_id == store_id)
    if event_type:
        query = query.filter(MasterLedgerEvent.event_type == event_type)
    if entity_type:
        query = query.filter(MasterLedgerEvent.entity_type == entity_type)
    if start_dt:
        query = query.filter(MasterLedgerEvent.occurred_at >= start_dt)
    if end_dt:
        query = query.filter(MasterLedgerEvent.occurred_at <= end_dt)

    events = query.limit(limit).all()
    return {
        "store_id": store_id,
        "start": to_utc_z(start_dt) if start_dt else None,
        "end": to_utc_z(end_dt) if end_dt else None,
        "limit": limit,
        "events": [event.to_dict() for event in events],
    }


def security_events(
    *,
    user_id: int | None,
    event_type: str | None,
    start: str | None,
    end: str | None,
    limit: int = 200,
) -> dict:
    start_dt, end_dt = _parse_range(start, end)

    query = db.session.query(SecurityEvent).order_by(SecurityEvent.occurred_at.desc())
    if user_id is not None:
        query = query.filter(SecurityEvent.user_id == user_id)
    if event_type:
        query = query.filter(SecurityEvent.event_type == event_type)
    if start_dt:
        query = query.filter(SecurityEvent.occurred_at >= start_dt)
    if end_dt:
        query = query.filter(SecurityEvent.occurred_at <= end_dt)

    events = query.limit(limit).all()
    return {
        "user_id": user_id,
        "start": to_utc_z(start_dt) if start_dt else None,
        "end": to_utc_z(end_dt) if end_dt else None,
        "limit": limit,
        "events": [event.to_dict() for event in events],
    }


# ===========================================================================
# NEW REPORTS
# ===========================================================================


# ---------------------------------------------------------------------------
# 1. Sales Summary Report
# ---------------------------------------------------------------------------

def sales_summary_report(
    *,
    store_id: int,
    include_children: bool,
    start: str | None,
    end: str | None,
) -> dict:
    """Comprehensive sales summary with gross/net sales, taxes, discounts,
    transaction counts, items sold, average ticket, and payment breakdown."""
    start_dt, end_dt = _parse_range(start, end)
    store_ids = _resolve_store_ids(store_id, include_children)

    sale_time = _sale_time()

    # --- Gross sales, discount, tax, transaction count, items sold -----------
    agg = db.session.query(
        func.coalesce(func.sum(SaleLine.line_total_cents), 0).label("gross_sales_cents"),
        func.coalesce(func.sum(SaleLine.discount_cents), 0).label("discount_total_cents"),
        func.coalesce(func.sum(SaleLine.quantity), 0).label("items_sold"),
        func.count(func.distinct(Sale.id)).label("transaction_count"),
    ).join(SaleLine, SaleLine.sale_id == Sale.id).filter(
        Sale.status == "POSTED",
        Sale.store_id.in_(store_ids),
    )
    if start_dt:
        agg = agg.filter(sale_time >= start_dt)
    if end_dt:
        agg = agg.filter(sale_time <= end_dt)
    agg_row = agg.one()

    gross_sales_cents = int(agg_row.gross_sales_cents or 0)
    discount_total_cents = int(agg_row.discount_total_cents or 0)
    items_sold = int(agg_row.items_sold or 0)
    transaction_count = int(agg_row.transaction_count or 0)

    # --- Tax collected (from Sale header) ------------------------------------
    tax_q = db.session.query(
        func.coalesce(func.sum(Sale.tax_cents), 0),
    ).filter(
        Sale.status == "POSTED",
        Sale.store_id.in_(store_ids),
    )
    if start_dt:
        tax_q = tax_q.filter(sale_time >= start_dt)
    if end_dt:
        tax_q = tax_q.filter(sale_time <= end_dt)
    tax_collected_cents = int(tax_q.scalar() or 0)

    # --- Completed returns (refunds) ----------------------------------------
    return_q = db.session.query(
        func.coalesce(func.sum(Return.refund_amount_cents), 0),
    ).filter(
        Return.status == "COMPLETED",
        Return.store_id.in_(store_ids),
    )
    if start_dt:
        return_q = return_q.filter(Return.completed_at >= start_dt)
    if end_dt:
        return_q = return_q.filter(Return.completed_at <= end_dt)
    return_total_cents = int(return_q.scalar() or 0)

    net_sales_cents = gross_sales_cents - return_total_cents
    avg_ticket_cents = (gross_sales_cents // transaction_count) if transaction_count else 0

    # --- Payment breakdown ---------------------------------------------------
    pay_q = db.session.query(
        Payment.tender_type.label("tender_type"),
        func.coalesce(func.sum(Payment.amount_cents), 0).label("total_cents"),
        func.count(Payment.id).label("count"),
    ).join(Sale, Payment.sale_id == Sale.id).filter(
        Sale.status == "POSTED",
        Sale.store_id.in_(store_ids),
        Payment.status == "COMPLETED",
    )
    if start_dt:
        pay_q = pay_q.filter(sale_time >= start_dt)
    if end_dt:
        pay_q = pay_q.filter(sale_time <= end_dt)
    pay_rows = pay_q.group_by(Payment.tender_type).all()

    payment_breakdown = [
        {
            "tender_type": r.tender_type,
            "total_cents": int(r.total_cents or 0),
            "count": int(r.count or 0),
        }
        for r in pay_rows
    ]

    return {
        "store_ids": store_ids,
        "start": to_utc_z(start_dt) if start_dt else None,
        "end": to_utc_z(end_dt) if end_dt else None,
        "gross_sales_cents": gross_sales_cents,
        "net_sales_cents": net_sales_cents,
        "return_total_cents": return_total_cents,
        "tax_collected_cents": tax_collected_cents,
        "discount_total_cents": discount_total_cents,
        "transaction_count": transaction_count,
        "items_sold": items_sold,
        "avg_ticket_cents": avg_ticket_cents,
        "payment_breakdown": payment_breakdown,
    }


# ---------------------------------------------------------------------------
# 2. Sales by Time Report
# ---------------------------------------------------------------------------

def sales_by_time_report(
    *,
    store_id: int,
    include_children: bool,
    start: str | None,
    end: str | None,
    mode: str = "hourly",
) -> dict:
    """Sales grouped by time period: hourly, day_of_week, or monthly."""
    start_dt, end_dt = _parse_range(start, end)
    store_ids = _resolve_store_ids(store_id, include_children)

    sale_time = _sale_time()

    if mode == "hourly":
        period_expr = func.strftime("%H", sale_time)
    elif mode == "day_of_week":
        period_expr = func.strftime("%w", sale_time)
    elif mode == "monthly":
        period_expr = func.strftime("%Y-%m", sale_time)
    else:
        raise ReportError("mode must be hourly, day_of_week, or monthly")

    query = db.session.query(
        period_expr.label("period"),
        func.count(func.distinct(Sale.id)).label("sales_count"),
        func.coalesce(func.sum(SaleLine.line_total_cents), 0).label("gross_sales_cents"),
        func.coalesce(func.sum(SaleLine.quantity), 0).label("items_sold"),
    ).join(SaleLine, SaleLine.sale_id == Sale.id).filter(
        Sale.status == "POSTED",
        Sale.store_id.in_(store_ids),
    )
    if start_dt:
        query = query.filter(sale_time >= start_dt)
    if end_dt:
        query = query.filter(sale_time <= end_dt)

    rows = query.group_by("period").order_by("period").all()

    return {
        "store_ids": store_ids,
        "mode": mode,
        "start": to_utc_z(start_dt) if start_dt else None,
        "end": to_utc_z(end_dt) if end_dt else None,
        "rows": [
            {
                "period": row.period,
                "sales_count": int(row.sales_count or 0),
                "gross_sales_cents": int(row.gross_sales_cents or 0),
                "items_sold": int(row.items_sold or 0),
            }
            for row in rows
        ],
    }


# ---------------------------------------------------------------------------
# 3. Sales by Employee Report
# ---------------------------------------------------------------------------

def sales_by_employee_report(
    *,
    store_id: int,
    include_children: bool,
    start: str | None,
    end: str | None,
) -> dict:
    """Per-employee sales performance with avg ticket, refund count, and discount totals."""
    start_dt, end_dt = _parse_range(start, end)
    store_ids = _resolve_store_ids(store_id, include_children)

    sale_time = _sale_time()

    # Sales aggregates per employee
    query = db.session.query(
        Sale.created_by_user_id.label("user_id"),
        User.username.label("username"),
        func.count(func.distinct(Sale.id)).label("sales_count"),
        func.coalesce(func.sum(SaleLine.line_total_cents), 0).label("gross_sales_cents"),
        func.coalesce(func.sum(SaleLine.quantity), 0).label("items_sold"),
        func.coalesce(func.sum(SaleLine.discount_cents), 0).label("discount_total_cents"),
    ).join(SaleLine, SaleLine.sale_id == Sale.id).outerjoin(
        User, Sale.created_by_user_id == User.id
    ).filter(
        Sale.status == "POSTED",
        Sale.store_id.in_(store_ids),
    )
    if start_dt:
        query = query.filter(sale_time >= start_dt)
    if end_dt:
        query = query.filter(sale_time <= end_dt)

    sales_rows = query.group_by(Sale.created_by_user_id, User.username).order_by(
        func.sum(SaleLine.line_total_cents).desc()
    ).all()

    # Refund counts per employee (who created the return)
    refund_q = db.session.query(
        Return.created_by_user_id.label("user_id"),
        func.count(Return.id).label("refund_count"),
    ).filter(
        Return.status == "COMPLETED",
        Return.store_id.in_(store_ids),
    )
    if start_dt:
        refund_q = refund_q.filter(Return.completed_at >= start_dt)
    if end_dt:
        refund_q = refund_q.filter(Return.completed_at <= end_dt)
    refund_map = {
        r.user_id: int(r.refund_count or 0)
        for r in refund_q.group_by(Return.created_by_user_id).all()
    }

    results = []
    for row in sales_rows:
        gross = int(row.gross_sales_cents or 0)
        count = int(row.sales_count or 0)
        results.append({
            "user_id": row.user_id,
            "username": row.username,
            "sales_count": count,
            "gross_sales_cents": gross,
            "items_sold": int(row.items_sold or 0),
            "discount_total_cents": int(row.discount_total_cents or 0),
            "avg_ticket_cents": (gross // count) if count else 0,
            "refund_count": refund_map.get(row.user_id, 0),
        })

    return {
        "store_ids": store_ids,
        "start": to_utc_z(start_dt) if start_dt else None,
        "end": to_utc_z(end_dt) if end_dt else None,
        "rows": results,
    }


# ---------------------------------------------------------------------------
# 4. Sales by Store Report
# ---------------------------------------------------------------------------

def sales_by_store_report(
    *,
    store_id: int,
    include_children: bool,
    start: str | None,
    end: str | None,
) -> dict:
    """Per-store sales totals with gross revenue, COGS, and margin."""
    start_dt, end_dt = _parse_range(start, end)
    store_ids = _resolve_store_ids(store_id, include_children)

    sale_time = _sale_time()

    # Revenue per store
    rev_q = db.session.query(
        Sale.store_id.label("store_id"),
        Store.name.label("store_name"),
        func.count(func.distinct(Sale.id)).label("sales_count"),
        func.coalesce(func.sum(SaleLine.line_total_cents), 0).label("gross_sales_cents"),
    ).join(SaleLine, SaleLine.sale_id == Sale.id).join(
        Store, Sale.store_id == Store.id
    ).filter(
        Sale.status == "POSTED",
        Sale.store_id.in_(store_ids),
    )
    if start_dt:
        rev_q = rev_q.filter(sale_time >= start_dt)
    if end_dt:
        rev_q = rev_q.filter(sale_time <= end_dt)
    rev_rows = rev_q.group_by(Sale.store_id, Store.name).all()

    # COGS per store
    cogs_q = db.session.query(
        InventoryTransaction.store_id.label("store_id"),
        func.coalesce(func.sum(InventoryTransaction.cogs_cents), 0).label("cogs_cents"),
    ).filter(
        InventoryTransaction.store_id.in_(store_ids),
        InventoryTransaction.status == "POSTED",
        InventoryTransaction.type.in_(["SALE", "RETURN"]),
    )
    if start_dt:
        cogs_q = cogs_q.filter(InventoryTransaction.occurred_at >= start_dt)
    if end_dt:
        cogs_q = cogs_q.filter(InventoryTransaction.occurred_at <= end_dt)
    cogs_map = {
        r.store_id: int(r.cogs_cents or 0)
        for r in cogs_q.group_by(InventoryTransaction.store_id).all()
    }

    results = []
    for row in rev_rows:
        gross = int(row.gross_sales_cents or 0)
        cogs = cogs_map.get(row.store_id, 0)
        margin = gross - cogs
        margin_pct = round(margin / gross * 100.0, 2) if gross else None
        results.append({
            "store_id": row.store_id,
            "store_name": row.store_name,
            "sales_count": int(row.sales_count or 0),
            "gross_sales_cents": gross,
            "cogs_cents": cogs,
            "margin_cents": margin,
            "margin_pct": margin_pct,
        })

    return {
        "store_ids": store_ids,
        "start": to_utc_z(start_dt) if start_dt else None,
        "end": to_utc_z(end_dt) if end_dt else None,
        "rows": results,
    }


# ---------------------------------------------------------------------------
# 5. Product Margin Outliers
# ---------------------------------------------------------------------------

def product_margin_outliers(
    *,
    store_id: int,
    include_children: bool,
    margin_threshold_pct: float = 20,
) -> dict:
    """Flag products where margin is below threshold, cost exceeds price,
    cost is zero, or cost data is missing."""
    store_ids = _resolve_store_ids(store_id, include_children)
    now = utcnow()

    products = db.session.query(Product).filter(
        Product.store_id.in_(store_ids),
        Product.is_active.is_(True),
    ).order_by(Product.name.asc()).all()

    rows = []
    for product in products:
        wac = get_weighted_average_cost_cents(product.store_id, product.id, as_of=now)
        price = product.price_cents
        flags: list[str] = []

        if wac is None:
            flags.append("MISSING_COST")
        elif wac == 0:
            flags.append("ZERO_COST")
        elif price is not None and price > 0:
            if wac >= price:
                flags.append("COST_EXCEEDS_PRICE")
            else:
                margin_pct = (price - wac) / price * 100.0
                if margin_pct < margin_threshold_pct:
                    flags.append("BELOW_THRESHOLD")
        elif price is None or price == 0:
            # No price set; cannot compute margin
            flags.append("MISSING_COST")

        if flags:
            margin_pct_val = None
            if wac is not None and price is not None and price > 0:
                margin_pct_val = round((price - wac) / price * 100.0, 2)
            rows.append({
                "store_id": product.store_id,
                "product_id": product.id,
                "sku": product.sku,
                "name": product.name,
                "price_cents": price,
                "wac_cents": wac,
                "margin_pct": margin_pct_val,
                "flags": flags,
            })

    return {
        "store_ids": store_ids,
        "margin_threshold_pct": margin_threshold_pct,
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# 6. Discount Impact Report
# ---------------------------------------------------------------------------

def discount_impact_report(
    *,
    store_id: int,
    include_children: bool,
    start: str | None,
    end: str | None,
) -> dict:
    """Aggregates discounts from POSTED sales with per-employee breakdown."""
    start_dt, end_dt = _parse_range(start, end)
    store_ids = _resolve_store_ids(store_id, include_children)

    sale_time = _sale_time()

    # Total aggregates
    total_q = db.session.query(
        func.coalesce(func.sum(SaleLine.discount_cents), 0).label("total_discount_cents"),
        func.sum(case((SaleLine.discount_cents > 0, 1), else_=0)).label("total_lines_discounted"),
    ).join(Sale, SaleLine.sale_id == Sale.id).filter(
        Sale.status == "POSTED",
        Sale.store_id.in_(store_ids),
    )
    if start_dt:
        total_q = total_q.filter(sale_time >= start_dt)
    if end_dt:
        total_q = total_q.filter(sale_time <= end_dt)
    total_row = total_q.one()

    total_discount_cents = int(total_row.total_discount_cents or 0)
    total_lines_discounted = int(total_row.total_lines_discounted or 0)

    # Margin erosion: discount reduces margin 1:1 (discount_cents that could have been profit)
    margin_erosion_cents = total_discount_cents

    # Per-employee breakdown
    emp_q = db.session.query(
        Sale.created_by_user_id.label("user_id"),
        User.username.label("username"),
        func.coalesce(func.sum(SaleLine.discount_cents), 0).label("discount_cents"),
        func.sum(case((SaleLine.discount_cents > 0, 1), else_=0)).label("lines_discounted"),
    ).join(SaleLine, SaleLine.sale_id == Sale.id).outerjoin(
        User, Sale.created_by_user_id == User.id
    ).filter(
        Sale.status == "POSTED",
        Sale.store_id.in_(store_ids),
    )
    if start_dt:
        emp_q = emp_q.filter(sale_time >= start_dt)
    if end_dt:
        emp_q = emp_q.filter(sale_time <= end_dt)
    emp_rows = emp_q.group_by(Sale.created_by_user_id, User.username).order_by(
        func.sum(SaleLine.discount_cents).desc()
    ).all()

    by_employee = [
        {
            "user_id": r.user_id,
            "username": r.username,
            "discount_cents": int(r.discount_cents or 0),
            "lines_discounted": int(r.lines_discounted or 0),
        }
        for r in emp_rows
    ]

    return {
        "store_ids": store_ids,
        "start": to_utc_z(start_dt) if start_dt else None,
        "end": to_utc_z(end_dt) if end_dt else None,
        "total_discount_cents": total_discount_cents,
        "total_lines_discounted": total_lines_discounted,
        "margin_erosion_cents": margin_erosion_cents,
        "by_employee": by_employee,
    }


# ---------------------------------------------------------------------------
# 7. Low Stock Report
# ---------------------------------------------------------------------------

def low_stock_report(
    *,
    store_id: int,
    include_children: bool,
    threshold: int = 10,
) -> dict:
    """Active products with quantity on hand at or below threshold."""
    store_ids = _resolve_store_ids(store_id, include_children)
    now = utcnow()

    products = db.session.query(Product).filter(
        Product.store_id.in_(store_ids),
        Product.is_active.is_(True),
    ).order_by(Product.name.asc()).all()

    rows = []
    for product in products:
        qty = get_quantity_on_hand(product.store_id, product.id, as_of=now)
        if qty <= threshold:
            rows.append({
                "store_id": product.store_id,
                "product_id": product.id,
                "sku": product.sku,
                "name": product.name,
                "quantity_on_hand": qty,
            })

    return {
        "store_ids": store_ids,
        "threshold": threshold,
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# 8. Shrinkage Report
# ---------------------------------------------------------------------------

def shrinkage_report(
    *,
    store_id: int,
    include_children: bool,
    start: str | None,
    end: str | None,
) -> dict:
    """Inventory shrinkage from posted physical counts (variance analysis)."""
    start_dt, end_dt = _parse_range(start, end)
    store_ids = _resolve_store_ids(store_id, include_children)

    query = db.session.query(Count).filter(
        Count.store_id.in_(store_ids),
        Count.status == "POSTED",
    )
    if start_dt:
        query = query.filter(Count.posted_at >= start_dt)
    if end_dt:
        query = query.filter(Count.posted_at <= end_dt)

    counts = query.order_by(Count.posted_at.desc()).all()

    total_counts = len(counts)
    total_variance_units = 0
    total_variance_cost_cents = 0
    breakdown = []

    for c in counts:
        v_units = c.total_variance_units or 0
        v_cost = c.total_variance_cost_cents or 0
        total_variance_units += v_units
        total_variance_cost_cents += v_cost
        breakdown.append({
            "count_id": c.id,
            "document_number": c.document_number,
            "store_id": c.store_id,
            "count_type": c.count_type,
            "posted_at": to_utc_z(c.posted_at) if c.posted_at else None,
            "variance_units": v_units,
            "variance_cost_cents": v_cost,
        })

    return {
        "store_ids": store_ids,
        "start": to_utc_z(start_dt) if start_dt else None,
        "end": to_utc_z(end_dt) if end_dt else None,
        "total_counts": total_counts,
        "total_variance_units": total_variance_units,
        "total_variance_cost_cents": total_variance_cost_cents,
        "counts": breakdown,
    }


# ---------------------------------------------------------------------------
# 9. Inventory Movement Report
# ---------------------------------------------------------------------------

def inventory_movement_report(
    *,
    store_id: int,
    include_children: bool,
    start: str | None,
    end: str | None,
) -> dict:
    """Inventory transactions grouped by type with total units and cost."""
    start_dt, end_dt = _parse_range(start, end)
    store_ids = _resolve_store_ids(store_id, include_children)

    query = db.session.query(
        InventoryTransaction.type.label("type"),
        func.coalesce(func.sum(InventoryTransaction.quantity_delta), 0).label("total_units"),
        func.coalesce(func.sum(InventoryTransaction.cogs_cents), 0).label("total_cost_cents"),
    ).filter(
        InventoryTransaction.store_id.in_(store_ids),
        InventoryTransaction.status == "POSTED",
    )
    if start_dt:
        query = query.filter(InventoryTransaction.occurred_at >= start_dt)
    if end_dt:
        query = query.filter(InventoryTransaction.occurred_at <= end_dt)

    rows = query.group_by(InventoryTransaction.type).order_by(InventoryTransaction.type).all()

    return {
        "store_ids": store_ids,
        "start": to_utc_z(start_dt) if start_dt else None,
        "end": to_utc_z(end_dt) if end_dt else None,
        "rows": [
            {
                "type": row.type,
                "total_units": int(row.total_units or 0),
                "total_cost_cents": int(row.total_cost_cents or 0),
            }
            for row in rows
        ],
    }


# ---------------------------------------------------------------------------
# 10. Vendor Spend Report
# ---------------------------------------------------------------------------

def vendor_spend_report(
    *,
    store_id: int,
    include_children: bool,
    start: str | None,
    end: str | None,
) -> dict:
    """Posted receive documents grouped by vendor with totals."""
    start_dt, end_dt = _parse_range(start, end)
    store_ids = _resolve_store_ids(store_id, include_children)

    query = db.session.query(
        ReceiveDocument.vendor_id.label("vendor_id"),
        Vendor.name.label("vendor_name"),
        func.count(func.distinct(ReceiveDocument.id)).label("document_count"),
        func.coalesce(func.sum(ReceiveDocumentLine.line_cost_cents), 0).label("total_cost_cents"),
        func.coalesce(func.sum(ReceiveDocumentLine.quantity), 0).label("total_units"),
    ).join(
        ReceiveDocumentLine, ReceiveDocumentLine.receive_document_id == ReceiveDocument.id
    ).join(
        Vendor, ReceiveDocument.vendor_id == Vendor.id
    ).filter(
        ReceiveDocument.store_id.in_(store_ids),
        ReceiveDocument.status == "POSTED",
    )
    if start_dt:
        query = query.filter(ReceiveDocument.posted_at >= start_dt)
    if end_dt:
        query = query.filter(ReceiveDocument.posted_at <= end_dt)

    rows = query.group_by(ReceiveDocument.vendor_id, Vendor.name).order_by(
        func.sum(ReceiveDocumentLine.line_cost_cents).desc()
    ).all()

    return {
        "store_ids": store_ids,
        "start": to_utc_z(start_dt) if start_dt else None,
        "end": to_utc_z(end_dt) if end_dt else None,
        "rows": [
            {
                "vendor_id": row.vendor_id,
                "vendor_name": row.vendor_name,
                "document_count": int(row.document_count or 0),
                "total_cost_cents": int(row.total_cost_cents or 0),
                "total_units": int(row.total_units or 0),
            }
            for row in rows
        ],
    }


# ---------------------------------------------------------------------------
# 11. Cost Change Report
# ---------------------------------------------------------------------------

def cost_change_report(
    *,
    store_id: int,
    include_children: bool,
    product_id: int | None = None,
) -> dict:
    """Shows cost changes over time per product from posted receive documents."""
    store_ids = _resolve_store_ids(store_id, include_children)

    query = db.session.query(
        ReceiveDocumentLine.product_id.label("product_id"),
        Product.sku.label("sku"),
        Product.name.label("product_name"),
        ReceiveDocumentLine.unit_cost_cents.label("unit_cost_cents"),
        ReceiveDocumentLine.quantity.label("quantity"),
        ReceiveDocument.document_number.label("document_number"),
        ReceiveDocument.vendor_id.label("vendor_id"),
        Vendor.name.label("vendor_name"),
        ReceiveDocument.occurred_at.label("occurred_at"),
    ).join(
        ReceiveDocument, ReceiveDocumentLine.receive_document_id == ReceiveDocument.id
    ).join(
        Product, ReceiveDocumentLine.product_id == Product.id
    ).join(
        Vendor, ReceiveDocument.vendor_id == Vendor.id
    ).filter(
        ReceiveDocument.store_id.in_(store_ids),
        ReceiveDocument.status == "POSTED",
    )
    if product_id is not None:
        query = query.filter(ReceiveDocumentLine.product_id == product_id)

    rows = query.order_by(
        ReceiveDocumentLine.product_id,
        ReceiveDocument.occurred_at.asc(),
    ).all()

    return {
        "store_ids": store_ids,
        "product_id": product_id,
        "rows": [
            {
                "product_id": r.product_id,
                "sku": r.sku,
                "product_name": r.product_name,
                "unit_cost_cents": r.unit_cost_cents,
                "quantity": r.quantity,
                "document_number": r.document_number,
                "vendor_id": r.vendor_id,
                "vendor_name": r.vendor_name,
                "occurred_at": to_utc_z(r.occurred_at),
            }
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# 12. Register Reconciliation Report
# ---------------------------------------------------------------------------

def register_reconciliation_report(
    *,
    store_id: int,
    include_children: bool,
    start: str | None,
    end: str | None,
) -> dict:
    """Closed register sessions with opening/closing/expected/variance details."""
    start_dt, end_dt = _parse_range(start, end)
    store_ids = _resolve_store_ids(store_id, include_children)

    query = db.session.query(
        RegisterSession.id.label("session_id"),
        RegisterSession.register_id.label("register_id"),
        Register.name.label("register_name"),
        RegisterSession.user_id.label("user_id"),
        User.username.label("username"),
        RegisterSession.opened_at.label("opened_at"),
        RegisterSession.closed_at.label("closed_at"),
        RegisterSession.opening_cash_cents.label("opening_cash_cents"),
        RegisterSession.closing_cash_cents.label("closing_cash_cents"),
        RegisterSession.expected_cash_cents.label("expected_cash_cents"),
        RegisterSession.variance_cents.label("variance_cents"),
        RegisterSession.notes.label("notes"),
    ).join(
        Register, RegisterSession.register_id == Register.id
    ).outerjoin(
        User, RegisterSession.user_id == User.id
    ).filter(
        RegisterSession.status == "CLOSED",
        Register.store_id.in_(store_ids),
    )
    if start_dt:
        query = query.filter(RegisterSession.closed_at >= start_dt)
    if end_dt:
        query = query.filter(RegisterSession.closed_at <= end_dt)

    rows = query.order_by(RegisterSession.closed_at.desc()).all()

    return {
        "store_ids": store_ids,
        "start": to_utc_z(start_dt) if start_dt else None,
        "end": to_utc_z(end_dt) if end_dt else None,
        "rows": [
            {
                "session_id": r.session_id,
                "register_id": r.register_id,
                "register_name": r.register_name,
                "user_id": r.user_id,
                "username": r.username,
                "opened_at": to_utc_z(r.opened_at),
                "closed_at": to_utc_z(r.closed_at) if r.closed_at else None,
                "opening_cash_cents": r.opening_cash_cents,
                "closing_cash_cents": r.closing_cash_cents,
                "expected_cash_cents": r.expected_cash_cents,
                "variance_cents": r.variance_cents,
                "notes": r.notes,
            }
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# 13. Payment Breakdown Report
# ---------------------------------------------------------------------------

def payment_breakdown_report(
    *,
    store_id: int,
    include_children: bool,
    start: str | None,
    end: str | None,
) -> dict:
    """Payments grouped by tender type for POSTED sales."""
    start_dt, end_dt = _parse_range(start, end)
    store_ids = _resolve_store_ids(store_id, include_children)

    sale_time = _sale_time()

    query = db.session.query(
        Payment.tender_type.label("tender_type"),
        func.coalesce(func.sum(Payment.amount_cents), 0).label("total_cents"),
        func.count(Payment.id).label("count"),
    ).join(Sale, Payment.sale_id == Sale.id).filter(
        Sale.status == "POSTED",
        Sale.store_id.in_(store_ids),
        Payment.status == "COMPLETED",
    )
    if start_dt:
        query = query.filter(sale_time >= start_dt)
    if end_dt:
        query = query.filter(sale_time <= end_dt)

    rows = query.group_by(Payment.tender_type).order_by(
        func.sum(Payment.amount_cents).desc()
    ).all()

    return {
        "store_ids": store_ids,
        "start": to_utc_z(start_dt) if start_dt else None,
        "end": to_utc_z(end_dt) if end_dt else None,
        "rows": [
            {
                "tender_type": r.tender_type,
                "total_cents": int(r.total_cents or 0),
                "count": int(r.count or 0),
            }
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# 14. Over/Short Report
# ---------------------------------------------------------------------------

def over_short_report(
    *,
    store_id: int,
    include_children: bool,
    start: str | None,
    end: str | None,
) -> dict:
    """Aggregates register session variance (over/short) data."""
    start_dt, end_dt = _parse_range(start, end)
    store_ids = _resolve_store_ids(store_id, include_children)

    query = db.session.query(
        RegisterSession.id.label("session_id"),
        RegisterSession.register_id.label("register_id"),
        Register.name.label("register_name"),
        RegisterSession.user_id.label("user_id"),
        User.username.label("username"),
        RegisterSession.closed_at.label("closed_at"),
        RegisterSession.expected_cash_cents.label("expected_cash_cents"),
        RegisterSession.closing_cash_cents.label("closing_cash_cents"),
        RegisterSession.variance_cents.label("variance_cents"),
    ).join(
        Register, RegisterSession.register_id == Register.id
    ).outerjoin(
        User, RegisterSession.user_id == User.id
    ).filter(
        RegisterSession.status == "CLOSED",
        Register.store_id.in_(store_ids),
    )
    if start_dt:
        query = query.filter(RegisterSession.closed_at >= start_dt)
    if end_dt:
        query = query.filter(RegisterSession.closed_at <= end_dt)

    rows = query.order_by(RegisterSession.closed_at.desc()).all()

    total_variance_cents = sum(int(r.variance_cents or 0) for r in rows)
    sessions_over = sum(1 for r in rows if (r.variance_cents or 0) > 0)
    sessions_short = sum(1 for r in rows if (r.variance_cents or 0) < 0)
    sessions_exact = sum(1 for r in rows if (r.variance_cents or 0) == 0)

    return {
        "store_ids": store_ids,
        "start": to_utc_z(start_dt) if start_dt else None,
        "end": to_utc_z(end_dt) if end_dt else None,
        "total_sessions": len(rows),
        "total_variance_cents": total_variance_cents,
        "sessions_over": sessions_over,
        "sessions_short": sessions_short,
        "sessions_exact": sessions_exact,
        "rows": [
            {
                "session_id": r.session_id,
                "register_id": r.register_id,
                "register_name": r.register_name,
                "user_id": r.user_id,
                "username": r.username,
                "closed_at": to_utc_z(r.closed_at) if r.closed_at else None,
                "expected_cash_cents": r.expected_cash_cents,
                "closing_cash_cents": r.closing_cash_cents,
                "variance_cents": r.variance_cents,
            }
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# 15. Labor Hours Report
# ---------------------------------------------------------------------------

def labor_hours_report(
    *,
    store_id: int,
    include_children: bool,
    start: str | None,
    end: str | None,
) -> dict:
    """Closed time clock entries grouped by employee with overtime flagging
    and missed-punch detection."""
    start_dt, end_dt = _parse_range(start, end)
    store_ids = _resolve_store_ids(store_id, include_children)

    # Closed entries for aggregation
    closed_q = db.session.query(
        TimeClockEntry.user_id.label("user_id"),
        User.username.label("username"),
        func.coalesce(func.sum(TimeClockEntry.total_worked_minutes), 0).label("total_minutes"),
        func.coalesce(func.sum(TimeClockEntry.total_break_minutes), 0).label("total_break_minutes"),
        func.count(TimeClockEntry.id).label("shift_count"),
        func.max(TimeClockEntry.total_worked_minutes).label("max_shift_minutes"),
    ).outerjoin(
        User, TimeClockEntry.user_id == User.id
    ).filter(
        TimeClockEntry.store_id.in_(store_ids),
        TimeClockEntry.status == "CLOSED",
    )
    if start_dt:
        closed_q = closed_q.filter(TimeClockEntry.clock_in_at >= start_dt)
    if end_dt:
        closed_q = closed_q.filter(TimeClockEntry.clock_in_at <= end_dt)

    closed_rows = closed_q.group_by(TimeClockEntry.user_id, User.username).all()

    # Detect overtime: any single shift > 480 minutes (8 hours)
    overtime_q = db.session.query(
        TimeClockEntry.user_id.label("user_id"),
        func.count(TimeClockEntry.id).label("overtime_shifts"),
    ).filter(
        TimeClockEntry.store_id.in_(store_ids),
        TimeClockEntry.status == "CLOSED",
        TimeClockEntry.total_worked_minutes > 480,
    )
    if start_dt:
        overtime_q = overtime_q.filter(TimeClockEntry.clock_in_at >= start_dt)
    if end_dt:
        overtime_q = overtime_q.filter(TimeClockEntry.clock_in_at <= end_dt)
    overtime_map = {
        r.user_id: int(r.overtime_shifts or 0)
        for r in overtime_q.group_by(TimeClockEntry.user_id).all()
    }

    # Missed punches: OPEN entries in range
    missed_q = db.session.query(
        TimeClockEntry.user_id.label("user_id"),
        func.count(TimeClockEntry.id).label("missed_punches"),
    ).filter(
        TimeClockEntry.store_id.in_(store_ids),
        TimeClockEntry.status == "OPEN",
    )
    if start_dt:
        missed_q = missed_q.filter(TimeClockEntry.clock_in_at >= start_dt)
    if end_dt:
        missed_q = missed_q.filter(TimeClockEntry.clock_in_at <= end_dt)
    missed_map = {
        r.user_id: int(r.missed_punches or 0)
        for r in missed_q.group_by(TimeClockEntry.user_id).all()
    }

    results = []
    for row in closed_rows:
        results.append({
            "user_id": row.user_id,
            "username": row.username,
            "total_minutes": int(row.total_minutes or 0),
            "total_break_minutes": int(row.total_break_minutes or 0),
            "shift_count": int(row.shift_count or 0),
            "max_shift_minutes": int(row.max_shift_minutes or 0),
            "overtime_shifts": overtime_map.get(row.user_id, 0),
            "missed_punches": missed_map.get(row.user_id, 0),
        })

    return {
        "store_ids": store_ids,
        "start": to_utc_z(start_dt) if start_dt else None,
        "end": to_utc_z(end_dt) if end_dt else None,
        "rows": results,
    }


# ---------------------------------------------------------------------------
# 16. Labor vs Sales Report
# ---------------------------------------------------------------------------

def labor_vs_sales_report(
    *,
    store_id: int,
    include_children: bool,
    start: str | None,
    end: str | None,
) -> dict:
    """Cross-references total labor minutes with total revenue."""
    start_dt, end_dt = _parse_range(start, end)
    store_ids = _resolve_store_ids(store_id, include_children)

    sale_time = _sale_time()

    # Total revenue
    rev_q = db.session.query(
        func.coalesce(func.sum(SaleLine.line_total_cents), 0),
    ).join(Sale, SaleLine.sale_id == Sale.id).filter(
        Sale.status == "POSTED",
        Sale.store_id.in_(store_ids),
    )
    if start_dt:
        rev_q = rev_q.filter(sale_time >= start_dt)
    if end_dt:
        rev_q = rev_q.filter(sale_time <= end_dt)
    total_revenue_cents = int(rev_q.scalar() or 0)

    # Total transaction count
    txn_q = db.session.query(
        func.count(func.distinct(Sale.id)),
    ).filter(
        Sale.status == "POSTED",
        Sale.store_id.in_(store_ids),
    )
    if start_dt:
        txn_q = txn_q.filter(sale_time >= start_dt)
    if end_dt:
        txn_q = txn_q.filter(sale_time <= end_dt)
    transaction_count = int(txn_q.scalar() or 0)

    # Total labor minutes
    labor_q = db.session.query(
        func.coalesce(func.sum(TimeClockEntry.total_worked_minutes), 0),
    ).filter(
        TimeClockEntry.store_id.in_(store_ids),
        TimeClockEntry.status == "CLOSED",
    )
    if start_dt:
        labor_q = labor_q.filter(TimeClockEntry.clock_in_at >= start_dt)
    if end_dt:
        labor_q = labor_q.filter(TimeClockEntry.clock_in_at <= end_dt)
    total_labor_minutes = int(labor_q.scalar() or 0)

    total_labor_hours = round(total_labor_minutes / 60.0, 2) if total_labor_minutes else 0.0
    revenue_per_labor_hour = (
        round(total_revenue_cents / total_labor_hours, 0) if total_labor_hours else None
    )
    transactions_per_labor_hour = (
        round(transaction_count / total_labor_hours, 2) if total_labor_hours else None
    )

    return {
        "store_ids": store_ids,
        "start": to_utc_z(start_dt) if start_dt else None,
        "end": to_utc_z(end_dt) if end_dt else None,
        "total_revenue_cents": total_revenue_cents,
        "transaction_count": transaction_count,
        "total_labor_minutes": total_labor_minutes,
        "total_labor_hours": total_labor_hours,
        "revenue_per_labor_hour_cents": int(revenue_per_labor_hour) if revenue_per_labor_hour is not None else None,
        "transactions_per_labor_hour": transactions_per_labor_hour,
    }


# ---------------------------------------------------------------------------
# 17. Employee Performance Report
# ---------------------------------------------------------------------------

def employee_performance_report(
    *,
    store_id: int,
    include_children: bool,
    start: str | None,
    end: str | None,
) -> dict:
    """Per-employee sales, discounts, refunds, and average ticket."""
    start_dt, end_dt = _parse_range(start, end)
    store_ids = _resolve_store_ids(store_id, include_children)

    sale_time = _sale_time()

    # Sales per employee
    sales_q = db.session.query(
        Sale.created_by_user_id.label("user_id"),
        User.username.label("username"),
        func.count(func.distinct(Sale.id)).label("sales_count"),
        func.coalesce(func.sum(SaleLine.line_total_cents), 0).label("gross_sales_cents"),
        func.coalesce(func.sum(SaleLine.quantity), 0).label("items_sold"),
        func.coalesce(func.sum(SaleLine.discount_cents), 0).label("discount_total_cents"),
    ).join(SaleLine, SaleLine.sale_id == Sale.id).outerjoin(
        User, Sale.created_by_user_id == User.id
    ).filter(
        Sale.status == "POSTED",
        Sale.store_id.in_(store_ids),
    )
    if start_dt:
        sales_q = sales_q.filter(sale_time >= start_dt)
    if end_dt:
        sales_q = sales_q.filter(sale_time <= end_dt)
    sales_rows = sales_q.group_by(Sale.created_by_user_id, User.username).all()

    # Refunds per employee
    refund_q = db.session.query(
        Return.created_by_user_id.label("user_id"),
        func.count(Return.id).label("refund_count"),
        func.coalesce(func.sum(Return.refund_amount_cents), 0).label("refund_total_cents"),
    ).filter(
        Return.status == "COMPLETED",
        Return.store_id.in_(store_ids),
    )
    if start_dt:
        refund_q = refund_q.filter(Return.completed_at >= start_dt)
    if end_dt:
        refund_q = refund_q.filter(Return.completed_at <= end_dt)
    refund_rows = refund_q.group_by(Return.created_by_user_id).all()
    refund_map = {r.user_id: (int(r.refund_count or 0), int(r.refund_total_cents or 0)) for r in refund_rows}

    results = []
    for row in sales_rows:
        gross = int(row.gross_sales_cents or 0)
        count = int(row.sales_count or 0)
        refund_count, refund_total = refund_map.get(row.user_id, (0, 0))
        results.append({
            "user_id": row.user_id,
            "username": row.username,
            "sales_count": count,
            "gross_sales_cents": gross,
            "items_sold": int(row.items_sold or 0),
            "avg_ticket_cents": (gross // count) if count else 0,
            "discount_total_cents": int(row.discount_total_cents or 0),
            "refund_count": refund_count,
            "refund_total_cents": refund_total,
        })

    return {
        "store_ids": store_ids,
        "start": to_utc_z(start_dt) if start_dt else None,
        "end": to_utc_z(end_dt) if end_dt else None,
        "rows": results,
    }


# ---------------------------------------------------------------------------
# 18. Customer CLV Report
# ---------------------------------------------------------------------------

def customer_clv_report(
    *,
    store_id: int,
    include_children: bool,
    limit: int = 50,
) -> dict:
    """Top customers by total lifetime spend (from denormalized Customer fields)."""
    store_ids = _resolve_store_ids(store_id, include_children)

    # Customers may be org-wide (store_id=NULL) or store-scoped. We need the
    # org_id from the store to match org-wide customers too.
    store = db.session.query(Store).filter_by(id=store_id).first()
    org_id = store.org_id if store else None

    query = db.session.query(Customer).filter(
        Customer.org_id == org_id,
        Customer.is_active.is_(True),
    ).order_by(Customer.total_spent_cents.desc()).limit(limit)

    customers = query.all()

    return {
        "store_ids": store_ids,
        "limit": limit,
        "rows": [
            {
                "customer_id": c.id,
                "first_name": c.first_name,
                "last_name": c.last_name,
                "email": c.email,
                "total_spent_cents": c.total_spent_cents,
                "total_visits": c.total_visits,
                "last_visit_at": to_utc_z(c.last_visit_at) if c.last_visit_at else None,
            }
            for c in customers
        ],
    }


# ---------------------------------------------------------------------------
# 19. Customer Retention Report
# ---------------------------------------------------------------------------

def customer_retention_report(
    *,
    store_id: int,
    include_children: bool,
    start: str | None,
    end: str | None,
) -> dict:
    """Count of total vs repeat customers (total_visits > 1) within scope."""
    start_dt, end_dt = _parse_range(start, end)
    store_ids = _resolve_store_ids(store_id, include_children)

    store = db.session.query(Store).filter_by(id=store_id).first()
    org_id = store.org_id if store else None

    base_q = db.session.query(Customer).filter(
        Customer.org_id == org_id,
        Customer.is_active.is_(True),
    )

    # If date range provided, only include customers whose last visit falls in range
    if start_dt:
        base_q = base_q.filter(Customer.last_visit_at >= start_dt)
    if end_dt:
        base_q = base_q.filter(Customer.last_visit_at <= end_dt)

    total_customers = base_q.count()
    repeat_customers = base_q.filter(Customer.total_visits > 1).count()
    one_time_customers = total_customers - repeat_customers
    retention_pct = round(repeat_customers / total_customers * 100.0, 2) if total_customers else None

    return {
        "store_ids": store_ids,
        "start": to_utc_z(start_dt) if start_dt else None,
        "end": to_utc_z(end_dt) if end_dt else None,
        "total_customers": total_customers,
        "repeat_customers": repeat_customers,
        "one_time_customers": one_time_customers,
        "retention_pct": retention_pct,
    }


# ---------------------------------------------------------------------------
# 20. Rewards Liability Report
# ---------------------------------------------------------------------------

def rewards_liability_report(
    *,
    store_id: int,
    include_children: bool,
) -> dict:
    """Aggregates outstanding reward points balance and lifetime activity."""
    store_ids = _resolve_store_ids(store_id, include_children)

    store = db.session.query(Store).filter_by(id=store_id).first()
    org_id = store.org_id if store else None

    query = db.session.query(
        func.count(CustomerRewardAccount.id).label("total_accounts"),
        func.coalesce(func.sum(CustomerRewardAccount.points_balance), 0).label("total_points_balance"),
        func.coalesce(func.sum(CustomerRewardAccount.lifetime_points_earned), 0).label("lifetime_earned"),
        func.coalesce(func.sum(CustomerRewardAccount.lifetime_points_redeemed), 0).label("lifetime_redeemed"),
    ).filter(
        CustomerRewardAccount.org_id == org_id,
    )
    row = query.one()

    return {
        "store_ids": store_ids,
        "total_accounts": int(row.total_accounts or 0),
        "total_points_balance": int(row.total_points_balance or 0),
        "lifetime_earned": int(row.lifetime_earned or 0),
        "lifetime_redeemed": int(row.lifetime_redeemed or 0),
    }


# ---------------------------------------------------------------------------
# 21. Refund Audit Report
# ---------------------------------------------------------------------------

def refund_audit_report(
    *,
    store_id: int,
    include_children: bool,
    start: str | None,
    end: str | None,
    limit: int = 200,
) -> dict:
    """Completed returns with user attribution for audit purposes."""
    start_dt, end_dt = _parse_range(start, end)
    store_ids = _resolve_store_ids(store_id, include_children)

    CreatedByUser = aliased(User)
    ApprovedByUser = aliased(User)

    query = db.session.query(
        Return.id.label("return_id"),
        Return.document_number.label("document_number"),
        Return.store_id.label("store_id"),
        Return.original_sale_id.label("original_sale_id"),
        Return.refund_amount_cents.label("refund_amount_cents"),
        Return.restocking_fee_cents.label("restocking_fee_cents"),
        Return.reason.label("reason"),
        Return.completed_at.label("completed_at"),
        Return.created_by_user_id.label("created_by_user_id"),
        CreatedByUser.username.label("created_by_username"),
        Return.approved_by_user_id.label("approved_by_user_id"),
        ApprovedByUser.username.label("approved_by_username"),
    ).outerjoin(
        CreatedByUser, Return.created_by_user_id == CreatedByUser.id
    ).outerjoin(
        ApprovedByUser, Return.approved_by_user_id == ApprovedByUser.id
    ).filter(
        Return.status == "COMPLETED",
        Return.store_id.in_(store_ids),
    )
    if start_dt:
        query = query.filter(Return.completed_at >= start_dt)
    if end_dt:
        query = query.filter(Return.completed_at <= end_dt)

    rows = query.order_by(Return.completed_at.desc()).limit(limit).all()

    return {
        "store_ids": store_ids,
        "start": to_utc_z(start_dt) if start_dt else None,
        "end": to_utc_z(end_dt) if end_dt else None,
        "limit": limit,
        "rows": [
            {
                "return_id": r.return_id,
                "document_number": r.document_number,
                "store_id": r.store_id,
                "original_sale_id": r.original_sale_id,
                "refund_amount_cents": r.refund_amount_cents,
                "restocking_fee_cents": r.restocking_fee_cents,
                "reason": r.reason,
                "completed_at": to_utc_z(r.completed_at) if r.completed_at else None,
                "created_by_user_id": r.created_by_user_id,
                "created_by_username": r.created_by_username,
                "approved_by_user_id": r.approved_by_user_id,
                "approved_by_username": r.approved_by_username,
            }
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# 22. Price Override Report
# ---------------------------------------------------------------------------

def price_override_report(
    *,
    store_id: int,
    include_children: bool,
    start: str | None,
    end: str | None,
    limit: int = 200,
) -> dict:
    """Sale lines where original_price_cents differs from unit_price_cents."""
    start_dt, end_dt = _parse_range(start, end)
    store_ids = _resolve_store_ids(store_id, include_children)

    sale_time = _sale_time()

    query = db.session.query(
        SaleLine.id.label("sale_line_id"),
        SaleLine.sale_id.label("sale_id"),
        Sale.document_number.label("sale_document_number"),
        SaleLine.product_id.label("product_id"),
        Product.sku.label("sku"),
        Product.name.label("product_name"),
        SaleLine.original_price_cents.label("original_price_cents"),
        SaleLine.unit_price_cents.label("unit_price_cents"),
        SaleLine.quantity.label("quantity"),
        SaleLine.discount_cents.label("discount_cents"),
        SaleLine.discount_reason.label("discount_reason"),
        SaleLine.override_approved_by_user_id.label("approved_by_user_id"),
        Sale.created_by_user_id.label("cashier_user_id"),
        sale_time.label("sale_time"),
    ).join(Sale, SaleLine.sale_id == Sale.id).join(
        Product, SaleLine.product_id == Product.id
    ).filter(
        Sale.status == "POSTED",
        Sale.store_id.in_(store_ids),
        SaleLine.original_price_cents.isnot(None),
        SaleLine.original_price_cents != SaleLine.unit_price_cents,
    )
    if start_dt:
        query = query.filter(sale_time >= start_dt)
    if end_dt:
        query = query.filter(sale_time <= end_dt)

    rows = query.order_by(sale_time.desc()).limit(limit).all()

    return {
        "store_ids": store_ids,
        "start": to_utc_z(start_dt) if start_dt else None,
        "end": to_utc_z(end_dt) if end_dt else None,
        "limit": limit,
        "rows": [
            {
                "sale_line_id": r.sale_line_id,
                "sale_id": r.sale_id,
                "sale_document_number": r.sale_document_number,
                "product_id": r.product_id,
                "sku": r.sku,
                "product_name": r.product_name,
                "original_price_cents": r.original_price_cents,
                "unit_price_cents": r.unit_price_cents,
                "difference_cents": (r.original_price_cents or 0) - (r.unit_price_cents or 0),
                "quantity": r.quantity,
                "discount_cents": r.discount_cents,
                "discount_reason": r.discount_reason,
                "approved_by_user_id": r.approved_by_user_id,
                "cashier_user_id": r.cashier_user_id,
                "sale_time": to_utc_z(r.sale_time) if r.sale_time else None,
            }
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# 23. Void Audit Report
# ---------------------------------------------------------------------------

def void_audit_report(
    *,
    store_id: int,
    include_children: bool,
    start: str | None,
    end: str | None,
    limit: int = 200,
) -> dict:
    """Voided sales with user attribution and details."""
    start_dt, end_dt = _parse_range(start, end)
    store_ids = _resolve_store_ids(store_id, include_children)

    CashierUser = aliased(User)
    VoidUser = aliased(User)

    query = db.session.query(
        Sale.id.label("sale_id"),
        Sale.document_number.label("document_number"),
        Sale.store_id.label("store_id"),
        Sale.total_due_cents.label("total_due_cents"),
        Sale.created_by_user_id.label("created_by_user_id"),
        CashierUser.username.label("cashier_username"),
        Sale.voided_by_user_id.label("voided_by_user_id"),
        VoidUser.username.label("voided_by_username"),
        Sale.voided_at.label("voided_at"),
        Sale.void_reason.label("void_reason"),
        Sale.register_id.label("register_id"),
    ).outerjoin(
        CashierUser, Sale.created_by_user_id == CashierUser.id
    ).outerjoin(
        VoidUser, Sale.voided_by_user_id == VoidUser.id
    ).filter(
        Sale.status == "VOIDED",
        Sale.store_id.in_(store_ids),
    )
    if start_dt:
        query = query.filter(Sale.voided_at >= start_dt)
    if end_dt:
        query = query.filter(Sale.voided_at <= end_dt)

    rows = query.order_by(Sale.voided_at.desc()).limit(limit).all()

    return {
        "store_ids": store_ids,
        "start": to_utc_z(start_dt) if start_dt else None,
        "end": to_utc_z(end_dt) if end_dt else None,
        "limit": limit,
        "rows": [
            {
                "sale_id": r.sale_id,
                "document_number": r.document_number,
                "store_id": r.store_id,
                "total_due_cents": r.total_due_cents,
                "created_by_user_id": r.created_by_user_id,
                "cashier_username": r.cashier_username,
                "voided_by_user_id": r.voided_by_user_id,
                "voided_by_username": r.voided_by_username,
                "voided_at": to_utc_z(r.voided_at) if r.voided_at else None,
                "void_reason": r.void_reason,
                "register_id": r.register_id,
            }
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# 24. Suspicious Activity Report
# ---------------------------------------------------------------------------

def suspicious_activity_report(
    *,
    store_id: int,
    include_children: bool,
    start: str | None,
    end: str | None,
) -> dict:
    """Flags suspicious patterns: no-sale drawer opens, failed auth attempts,
    high-void users, and cash variances."""
    start_dt, end_dt = _parse_range(start, end)
    store_ids = _resolve_store_ids(store_id, include_children)

    # 1. No-sale drawer opens
    no_sale_q = db.session.query(
        CashDrawerEvent.user_id.label("user_id"),
        User.username.label("username"),
        func.count(CashDrawerEvent.id).label("count"),
    ).outerjoin(
        User, CashDrawerEvent.user_id == User.id
    ).join(
        Register, CashDrawerEvent.register_id == Register.id
    ).filter(
        CashDrawerEvent.event_type == "NO_SALE",
        Register.store_id.in_(store_ids),
    )
    if start_dt:
        no_sale_q = no_sale_q.filter(CashDrawerEvent.occurred_at >= start_dt)
    if end_dt:
        no_sale_q = no_sale_q.filter(CashDrawerEvent.occurred_at <= end_dt)
    no_sale_opens = [
        {"user_id": r.user_id, "username": r.username, "count": int(r.count or 0)}
        for r in no_sale_q.group_by(CashDrawerEvent.user_id, User.username).all()
    ]

    # 2. Failed auth attempts (from SecurityEvent)
    store = db.session.query(Store).filter_by(id=store_id).first()
    org_id = store.org_id if store else None

    failed_q = db.session.query(
        SecurityEvent.user_id.label("user_id"),
        func.count(SecurityEvent.id).label("count"),
    ).filter(
        SecurityEvent.event_type == "LOGIN_FAILED",
        SecurityEvent.success.is_(False),
    )
    if org_id:
        failed_q = failed_q.filter(SecurityEvent.org_id == org_id)
    if start_dt:
        failed_q = failed_q.filter(SecurityEvent.occurred_at >= start_dt)
    if end_dt:
        failed_q = failed_q.filter(SecurityEvent.occurred_at <= end_dt)
    failed_auth = [
        {"user_id": r.user_id, "count": int(r.count or 0)}
        for r in failed_q.group_by(SecurityEvent.user_id).all()
    ]

    # 3. High-void users (users who voided more than 3 sales in period)
    void_q = db.session.query(
        Sale.voided_by_user_id.label("user_id"),
        User.username.label("username"),
        func.count(Sale.id).label("void_count"),
    ).outerjoin(
        User, Sale.voided_by_user_id == User.id
    ).filter(
        Sale.status == "VOIDED",
        Sale.store_id.in_(store_ids),
        Sale.voided_by_user_id.isnot(None),
    )
    if start_dt:
        void_q = void_q.filter(Sale.voided_at >= start_dt)
    if end_dt:
        void_q = void_q.filter(Sale.voided_at <= end_dt)
    high_void_users = [
        {"user_id": r.user_id, "username": r.username, "void_count": int(r.void_count or 0)}
        for r in void_q.group_by(Sale.voided_by_user_id, User.username).having(
            func.count(Sale.id) > 3
        ).all()
    ]

    # 4. Cash variances (sessions with abs(variance) > 500 cents = $5.00)
    variance_q = db.session.query(
        RegisterSession.id.label("session_id"),
        RegisterSession.register_id.label("register_id"),
        Register.name.label("register_name"),
        RegisterSession.user_id.label("user_id"),
        User.username.label("username"),
        RegisterSession.variance_cents.label("variance_cents"),
        RegisterSession.closed_at.label("closed_at"),
    ).join(
        Register, RegisterSession.register_id == Register.id
    ).outerjoin(
        User, RegisterSession.user_id == User.id
    ).filter(
        RegisterSession.status == "CLOSED",
        Register.store_id.in_(store_ids),
        RegisterSession.variance_cents.isnot(None),
        func.abs(RegisterSession.variance_cents) > 500,
    )
    if start_dt:
        variance_q = variance_q.filter(RegisterSession.closed_at >= start_dt)
    if end_dt:
        variance_q = variance_q.filter(RegisterSession.closed_at <= end_dt)
    cash_variances = [
        {
            "session_id": r.session_id,
            "register_id": r.register_id,
            "register_name": r.register_name,
            "user_id": r.user_id,
            "username": r.username,
            "variance_cents": r.variance_cents,
            "closed_at": to_utc_z(r.closed_at) if r.closed_at else None,
        }
        for r in variance_q.order_by(func.abs(RegisterSession.variance_cents).desc()).all()
    ]

    return {
        "store_ids": store_ids,
        "start": to_utc_z(start_dt) if start_dt else None,
        "end": to_utc_z(end_dt) if end_dt else None,
        "no_sale_opens": no_sale_opens,
        "failed_auth_attempts": failed_auth,
        "high_void_users": high_void_users,
        "cash_variances": cash_variances,
    }
