from flask import Blueprint, jsonify, request

from app.decorators import require_auth, require_permission
from app.services import reporting_service


reports_bp = Blueprint("reports", __name__, url_prefix="/api/reports")


@reports_bp.get("/sales")
@require_auth
@require_permission("VIEW_SALES_REPORTS")
def sales_report():
    store_id = request.args.get("store_id", type=int)
    if not store_id:
        return jsonify({"error": "store_id is required"}), 400

    include_children = request.args.get("include_children", "false").lower() == "true"
    group_by = request.args.get("group_by", "day")
    start = request.args.get("start")
    end = request.args.get("end")

    try:
        report = reporting_service.sales_report(
            store_id=store_id,
            include_children=include_children,
            start=start,
            end=end,
            group_by=group_by,
        )
        return jsonify(report), 200
    except reporting_service.ReportError as exc:
        return jsonify({"error": str(exc)}), 400


@reports_bp.get("/inventory-valuation")
@require_auth
@require_permission("VIEW_INVENTORY")
def inventory_valuation_report():
    store_id = request.args.get("store_id", type=int)
    if not store_id:
        return jsonify({"error": "store_id is required"}), 400

    include_children = request.args.get("include_children", "false").lower() == "true"
    as_of = request.args.get("as_of")

    try:
        report = reporting_service.inventory_valuation(
            store_id=store_id,
            include_children=include_children,
            as_of=as_of,
        )
        return jsonify(report), 200
    except reporting_service.ReportError as exc:
        return jsonify({"error": str(exc)}), 400


@reports_bp.get("/cogs-margin")
@require_auth
@require_permission("VIEW_COGS")
def cogs_margin_report():
    store_id = request.args.get("store_id", type=int)
    if not store_id:
        return jsonify({"error": "store_id is required"}), 400

    include_children = request.args.get("include_children", "false").lower() == "true"
    start = request.args.get("start")
    end = request.args.get("end")

    try:
        report = reporting_service.cogs_margin_report(
            store_id=store_id,
            include_children=include_children,
            start=start,
            end=end,
        )
        return jsonify(report), 200
    except reporting_service.ReportError as exc:
        return jsonify({"error": str(exc)}), 400


@reports_bp.get("/abc-analysis")
@require_auth
@require_permission("VIEW_SALES_REPORTS")
def abc_report():
    store_id = request.args.get("store_id", type=int)
    if not store_id:
        return jsonify({"error": "store_id is required"}), 400

    include_children = request.args.get("include_children", "false").lower() == "true"
    start = request.args.get("start")
    end = request.args.get("end")

    try:
        report = reporting_service.abc_analysis(
            store_id=store_id,
            include_children=include_children,
            start=start,
            end=end,
        )
        return jsonify(report), 200
    except reporting_service.ReportError as exc:
        return jsonify({"error": str(exc)}), 400


@reports_bp.get("/slow-dead-stock")
@require_auth
@require_permission("VIEW_INVENTORY")
def slow_dead_stock_report():
    store_id = request.args.get("store_id", type=int)
    if not store_id:
        return jsonify({"error": "store_id is required"}), 400

    include_children = request.args.get("include_children", "false").lower() == "true"
    as_of = request.args.get("as_of")
    slow_days = request.args.get("slow_days", 30, type=int)
    dead_days = request.args.get("dead_days", 90, type=int)

    try:
        report = reporting_service.slow_dead_stock(
            store_id=store_id,
            include_children=include_children,
            as_of=as_of,
            slow_days=slow_days,
            dead_days=dead_days,
        )
        return jsonify(report), 200
    except reporting_service.ReportError as exc:
        return jsonify({"error": str(exc)}), 400


@reports_bp.get("/audit")
@require_auth
@require_permission("VIEW_AUDIT_LOG")
def audit_trail_report():
    store_id = request.args.get("store_id", type=int)
    event_type = request.args.get("event_type")
    entity_type = request.args.get("entity_type")
    start = request.args.get("start")
    end = request.args.get("end")
    limit = request.args.get("limit", 200, type=int)

    try:
        report = reporting_service.audit_trail(
            store_id=store_id,
            event_type=event_type,
            entity_type=entity_type,
            start=start,
            end=end,
            limit=limit,
        )
        return jsonify(report), 200
    except reporting_service.ReportError as exc:
        return jsonify({"error": str(exc)}), 400


@reports_bp.get("/security-events")
@require_auth
@require_permission("VIEW_AUDIT_LOG")
def security_events_report():
    user_id = request.args.get("user_id", type=int)
    event_type = request.args.get("event_type")
    start = request.args.get("start")
    end = request.args.get("end")
    limit = request.args.get("limit", 200, type=int)

    try:
        report = reporting_service.security_events(
            user_id=user_id,
            event_type=event_type,
            start=start,
            end=end,
            limit=limit,
        )
        return jsonify(report), 200
    except reporting_service.ReportError as exc:
        return jsonify({"error": str(exc)}), 400
