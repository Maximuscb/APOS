# Overview: Flask API routes for analytics; parses input and returns JSON responses.

"""
Analytics Routes

Provides sales trends, inventory valuation, margin/COGS, slow/dead stock,
cashier performance, and register performance.
"""

from flask import Blueprint, request, jsonify, g

from ..decorators import require_auth, require_permission
from ..extensions import db
from ..models import Sale, RegisterSession, User, Task
from ..services import reporting_service, permission_service
from ..services.reporting_service import ReportError
from ..services.tenant_service import require_store_in_org, TenantAccessError


analytics_bp = Blueprint("analytics", __name__, url_prefix="/api/analytics")


def _check_store_access(store_id: int) -> None:
    require_store_in_org(store_id, g.org_id)


def _parse_include_children() -> bool:
    include_children = request.args.get("include_children", "false").lower() == "true"
    if include_children and not permission_service.user_has_permission(g.current_user.id, "VIEW_CROSS_STORE_ANALYTICS"):
        raise PermissionError("Cross-store analytics permission required")
    return include_children


@analytics_bp.get("/sales-trends")
@require_auth
@require_permission("VIEW_ANALYTICS")
def sales_trends_route():
    store_id = request.args.get("store_id", type=int)
    if not store_id:
        return jsonify({"error": "store_id is required"}), 400

    try:
        _check_store_access(store_id)
        include_children = _parse_include_children()
        result = reporting_service.sales_report(
            store_id=store_id,
            include_children=include_children,
            start=request.args.get("start"),
            end=request.args.get("end"),
            group_by=request.args.get("group_by", "day"),
        )
        return jsonify(result)
    except TenantAccessError:
        return jsonify({"error": "Store not found"}), 404
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except ReportError as e:
        return jsonify({"error": str(e)}), 400


@analytics_bp.get("/inventory-valuation")
@require_auth
@require_permission("VIEW_ANALYTICS")
def inventory_valuation_route():
    store_id = request.args.get("store_id", type=int)
    if not store_id:
        return jsonify({"error": "store_id is required"}), 400

    try:
        _check_store_access(store_id)
        include_children = _parse_include_children()
        result = reporting_service.inventory_valuation(
            store_id=store_id,
            include_children=include_children,
            as_of=request.args.get("as_of"),
        )
        return jsonify(result)
    except TenantAccessError:
        return jsonify({"error": "Store not found"}), 404
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except ReportError as e:
        return jsonify({"error": str(e)}), 400


@analytics_bp.get("/margin-cogs")
@require_auth
@require_permission("VIEW_ANALYTICS")
def margin_cogs_route():
    store_id = request.args.get("store_id", type=int)
    if not store_id:
        return jsonify({"error": "store_id is required"}), 400

    try:
        _check_store_access(store_id)
        include_children = _parse_include_children()
        result = reporting_service.cogs_margin_report(
            store_id=store_id,
            include_children=include_children,
            start=request.args.get("start"),
            end=request.args.get("end"),
        )
        return jsonify(result)
    except TenantAccessError:
        return jsonify({"error": "Store not found"}), 404
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except ReportError as e:
        return jsonify({"error": str(e)}), 400


@analytics_bp.get("/slow-stock")
@require_auth
@require_permission("VIEW_ANALYTICS")
def slow_stock_route():
    store_id = request.args.get("store_id", type=int)
    if not store_id:
        return jsonify({"error": "store_id is required"}), 400

    try:
        _check_store_access(store_id)
        include_children = _parse_include_children()
        slow_days = request.args.get("slow_days", 30, type=int)
        dead_days = request.args.get("dead_days", 90, type=int)
        result = reporting_service.slow_dead_stock(
            store_id=store_id,
            include_children=include_children,
            as_of=request.args.get("as_of"),
            slow_days=slow_days,
            dead_days=dead_days,
        )
        return jsonify(result)
    except TenantAccessError:
        return jsonify({"error": "Store not found"}), 404
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except ReportError as e:
        return jsonify({"error": str(e)}), 400


@analytics_bp.get("/cashier-performance")
@require_auth
@require_permission("VIEW_ANALYTICS")
def cashier_performance_route():
    store_id = request.args.get("store_id", type=int)
    if not store_id:
        return jsonify({"error": "store_id is required"}), 400

    try:
        _check_store_access(store_id)
        include_children = _parse_include_children()
        result = reporting_service.cashier_performance(
            store_id=store_id,
            include_children=include_children,
            start=request.args.get("start"),
            end=request.args.get("end"),
        )
        return jsonify(result)
    except TenantAccessError:
        return jsonify({"error": "Store not found"}), 404
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except ReportError as e:
        return jsonify({"error": str(e)}), 400


@analytics_bp.get("/register-performance")
@require_auth
@require_permission("VIEW_ANALYTICS")
def register_performance_route():
    store_id = request.args.get("store_id", type=int)
    if not store_id:
        return jsonify({"error": "store_id is required"}), 400

    try:
        _check_store_access(store_id)
        include_children = _parse_include_children()
        result = reporting_service.register_performance(
            store_id=store_id,
            include_children=include_children,
            start=request.args.get("start"),
            end=request.args.get("end"),
        )
        return jsonify(result)
    except TenantAccessError:
        return jsonify({"error": "Store not found"}), 404
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except ReportError as e:
        return jsonify({"error": str(e)}), 400


@analytics_bp.get("/dashboard-summary")
@require_auth
def dashboard_summary_route():
    """Dashboard summary: today's sales count, open registers, pending tasks."""
    store_id = request.args.get("store_id", type=int) or g.store_id
    if not store_id:
        return jsonify({"error": "store_id is required"}), 400

    from datetime import datetime, timezone as tz
    today_start = datetime.now(tz.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    sales_today = db.session.query(db.func.count(Sale.id)).filter(
        Sale.store_id == store_id,
        Sale.created_at >= today_start,
        Sale.status != "VOIDED",
    ).scalar() or 0

    sales_total_cents = db.session.query(db.func.coalesce(db.func.sum(Sale.total_due_cents), 0)).filter(
        Sale.store_id == store_id,
        Sale.created_at >= today_start,
        Sale.status == "COMPLETED",
    ).scalar() or 0

    open_registers = db.session.query(db.func.count(RegisterSession.id)).filter(
        RegisterSession.status == "OPEN",
    ).scalar() or 0

    pending_tasks = db.session.query(db.func.count(Task.id)).filter(
        Task.org_id == g.org_id,
        Task.status == "PENDING",
    ).scalar() or 0

    return jsonify({
        "sales_today": sales_today,
        "sales_total_cents": sales_total_cents,
        "open_registers": open_registers,
        "pending_tasks": pending_tasks,
    })
