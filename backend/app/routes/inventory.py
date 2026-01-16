# backend/app/routes/inventory.py
"""
Inventory management routes.

SECURITY: All routes require authentication.
- View operations require VIEW_INVENTORY permission
- Receive operations require RECEIVE_INVENTORY permission
- Adjust operations require ADJUST_INVENTORY permission
- Sale operations require CREATE_SALE permission (called internally)

Time semantics:
- API accepts ISO-8601 datetimes with Z/offsets; backend normalizes to UTC-naive internally.
- as_of filtering is inclusive: occurred_at <= as_of.
"""
from flask import Blueprint, request

from ..models import InventoryTransaction
from app.time_utils import parse_iso_datetime
from ..validation import (
    ModelValidationPolicy,
    validate_payload,
    ValidationError,
    enforce_rules_inventory_receive,
    enforce_rules_inventory_adjust,
    enforce_rules_inventory_sale,
)
from ..decorators import require_auth, require_permission


inventory_bp = Blueprint("inventory", __name__, url_prefix="/api/inventory")

INVENTORY_RECEIVE_POLICY = ModelValidationPolicy(
    writable_fields={"store_id", "product_id", "quantity_delta", "unit_cost_cents", "occurred_at", "note"},
    required_on_create={"store_id", "product_id", "quantity_delta", "unit_cost_cents"},
)

INVENTORY_ADJUST_POLICY = ModelValidationPolicy(
    writable_fields={"store_id", "product_id", "quantity_delta", "occurred_at", "note"},
    required_on_create={"store_id", "product_id", "quantity_delta"},
)

INVENTORY_SALE_POLICY = ModelValidationPolicy(
    writable_fields={
        "store_id",
        "product_id",
        "quantity_delta",
        "occurred_at",
        "note",
        "sale_id",
        "sale_line_id",
    },
    required_on_create={"store_id", "product_id", "quantity_delta", "sale_id", "sale_line_id"},
)


@inventory_bp.post("/receive")
@require_auth
@require_permission("RECEIVE_INVENTORY")
def receive_inventory_route():
    """
    Receive inventory into stock.

    Requires RECEIVE_INVENTORY permission.
    """
    payload = request.get_json(silent=True) or {}

    try:
        patch = validate_payload(
            model=InventoryTransaction,
            payload=payload,
            policy=INVENTORY_RECEIVE_POLICY,
            partial=False,
        )
        enforce_rules_inventory_receive(patch)
    except ValidationError as e:
        return {"error": str(e)}, 400

    from ..services.inventory_service import receive_inventory, get_inventory_summary

    try:
        created_tx = receive_inventory(
            store_id=patch["store_id"],
            product_id=patch["product_id"],
            quantity=patch["quantity_delta"],
            unit_cost_cents=patch["unit_cost_cents"],
            occurred_at=patch.get("occurred_at"),
            note=patch.get("note"),
        )
    except ValueError as e:
        return {"error": str(e)}, 400

    summary = get_inventory_summary(store_id=patch["store_id"], product_id=patch["product_id"])
    return {"transaction": created_tx.to_dict(), "summary": summary}, 201


@inventory_bp.post("/adjust")
@require_auth
@require_permission("ADJUST_INVENTORY")
def adjust_inventory_route():
    """
    Adjust inventory (corrections, shrink, etc.).

    Requires ADJUST_INVENTORY permission.

    WHY DRAFT: Manual adjustments default to DRAFT status to require
    manager approval before affecting inventory. This prevents accidental
    or unauthorized changes to inventory levels.

    To post immediately (e.g., from approved cycle counts), include
    {"status": "POSTED"} in the request body.
    """
    payload = request.get_json(silent=True) or {}

    try:
        patch = validate_payload(
            model=InventoryTransaction,
            payload=payload,
            policy=INVENTORY_ADJUST_POLICY,
            partial=False,
        )
        enforce_rules_inventory_adjust(patch)
    except ValidationError as e:
        return {"error": str(e)}, 400

    from ..services.inventory_service import adjust_inventory, get_inventory_summary

    # Default to DRAFT for adjustments - requires approval workflow
    # Client can override with status="POSTED" for pre-approved adjustments
    status = payload.get("status", "DRAFT")
    if status not in ("DRAFT", "POSTED"):
        return {"error": "status must be DRAFT or POSTED"}, 400

    try:
        created_tx = adjust_inventory(
            store_id=patch["store_id"],
            product_id=patch["product_id"],
            quantity_delta=patch["quantity_delta"],
            occurred_at=patch.get("occurred_at"),
            note=patch.get("note"),
            status=status,  # Pass the status to the service
        )
    except ValueError as e:
        return {"error": str(e)}, 400

    summary = get_inventory_summary(store_id=patch["store_id"], product_id=patch["product_id"])
    return {"transaction": created_tx.to_dict(), "summary": summary}, 201


@inventory_bp.get("/<int:product_id>/summary")
@require_auth
@require_permission("VIEW_INVENTORY")
def inventory_summary_route(product_id: int):
    """
    Get inventory summary for a product.

    Requires VIEW_INVENTORY permission.
    """
    store_id = request.args.get("store_id", type=int)

    as_of_raw = request.args.get("as_of")  # optional ISO string
    try:
        as_of_dt = parse_iso_datetime(as_of_raw)
    except Exception:
        return {"error": "as_of must be an ISO-8601 datetime"}, 400

    if store_id is None:
        return {"error": "store_id is required"}, 400

    from ..services.inventory_service import get_inventory_summary

    try:
        # IMPORTANT: pass datetime (not string) so service doesn't need to parse 'Z'
        return get_inventory_summary(store_id=store_id, product_id=product_id, as_of=as_of_dt), 200
    except ValueError as e:
        return {"error": str(e)}, 400


@inventory_bp.get("/<int:product_id>/transactions")
@require_auth
@require_permission("VIEW_INVENTORY")
def inventory_transactions_route(product_id: int):
    """
    List inventory transactions for a product.

    Requires VIEW_INVENTORY permission.
    """
    store_id = request.args.get("store_id", type=int)
    if store_id is None:
        return {"error": "store_id is required"}, 400

    as_of_raw = request.args.get("as_of")  # optional ISO string
    try:
        as_of_dt = parse_iso_datetime(as_of_raw)
    except Exception:
        return {"error": "as_of must be an ISO-8601 datetime"}, 400

    from ..services.inventory_service import list_inventory_transactions

    try:
        # NOTE: this expects list_inventory_transactions to accept as_of=...
        rows = list_inventory_transactions(store_id=store_id, product_id=product_id, as_of=as_of_dt)
        return [r.to_dict() for r in rows], 200
    except TypeError:
        # Backward-compatible fallback if service has not been updated yet
        rows = list_inventory_transactions(store_id=store_id, product_id=product_id)
        if as_of_dt is not None:
            rows = [r for r in rows if r.occurred_at and r.occurred_at <= as_of_dt]
        return [r.to_dict() for r in rows], 200
    except ValueError as e:
        return {"error": str(e)}, 400


@inventory_bp.post("/sale")
@require_auth
@require_permission("CREATE_SALE")
def sale_inventory_route():
    """
    Record a sale transaction (inventory decrement).

    Requires CREATE_SALE permission.
    Note: This is typically called internally by the sales service.
    """
    payload = request.get_json(silent=True) or {}

    try:
        patch = validate_payload(
            model=InventoryTransaction,
            payload=payload,
            policy=INVENTORY_SALE_POLICY,
            partial=False,
        )
        enforce_rules_inventory_sale(patch)
    except ValidationError as e:
        return {"error": str(e)}, 400

    from ..services.inventory_service import sell_inventory, get_inventory_summary

    try:
        created_tx = sell_inventory(
            store_id=patch["store_id"],
            product_id=patch["product_id"],
            quantity=patch["quantity_delta"],   # positive integer input
            sale_id=patch["sale_id"],
            sale_line_id=patch["sale_line_id"],
            occurred_at=patch.get("occurred_at"),
            note=patch.get("note"),
        )
    except ValueError as e:
        # Oversell / idempotency misuse / missing cost basis are business conflicts
        return {"error": str(e)}, 409

    summary = get_inventory_summary(store_id=patch["store_id"], product_id=patch["product_id"])
    return {"transaction": created_tx.to_dict(), "summary": summary}, 201
