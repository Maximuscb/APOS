# Overview: Flask API routes for analytics; parses input and returns JSON responses.

"""
Analytics Routes

Provides sales trends, inventory valuation, margin/COGS, slow/dead stock,
cashier performance, and register performance.
"""

from flask import Blueprint, request, jsonify, g

from ..decorators import require_auth, require_permission
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
