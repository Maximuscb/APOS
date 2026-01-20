# Overview: Service-layer operations for reporting; encapsulates business logic and database work.

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from sqlalchemy import func

from app.extensions import db
from app.models import (
    Sale,
    SaleLine,
    InventoryTransaction,
    Product,
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
