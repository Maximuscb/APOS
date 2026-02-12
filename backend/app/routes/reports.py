# Overview: Flask API routes for reports operations; parses input and returns JSON responses.

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


@reports_bp.get("/sales-summary")
@require_auth
@require_permission("VIEW_SALES_REPORTS")
def sales_summary_report():
    store_id = request.args.get("store_id", type=int)
    if not store_id:
        return jsonify({"error": "store_id is required"}), 400

    include_children = request.args.get("include_children", "false").lower() == "true"
    start = request.args.get("start")
    end = request.args.get("end")

    try:
        report = reporting_service.sales_summary_report(
            store_id=store_id,
            include_children=include_children,
            start=start,
            end=end,
        )
        return jsonify(report), 200
    except reporting_service.ReportError as exc:
        return jsonify({"error": str(exc)}), 400


@reports_bp.get("/sales-by-time")
@require_auth
@require_permission("VIEW_SALES_REPORTS")
def sales_by_time_report():
    store_id = request.args.get("store_id", type=int)
    if not store_id:
        return jsonify({"error": "store_id is required"}), 400

    include_children = request.args.get("include_children", "false").lower() == "true"
    start = request.args.get("start")
    end = request.args.get("end")
    mode = request.args.get("mode", "hourly")

    try:
        report = reporting_service.sales_by_time_report(
            store_id=store_id,
            include_children=include_children,
            start=start,
            end=end,
            mode=mode,
        )
        return jsonify(report), 200
    except reporting_service.ReportError as exc:
        return jsonify({"error": str(exc)}), 400


@reports_bp.get("/sales-by-employee")
@require_auth
@require_permission("VIEW_SALES_REPORTS")
def sales_by_employee_report():
    store_id = request.args.get("store_id", type=int)
    if not store_id:
        return jsonify({"error": "store_id is required"}), 400

    include_children = request.args.get("include_children", "false").lower() == "true"
    start = request.args.get("start")
    end = request.args.get("end")

    try:
        report = reporting_service.sales_by_employee_report(
            store_id=store_id,
            include_children=include_children,
            start=start,
            end=end,
        )
        return jsonify(report), 200
    except reporting_service.ReportError as exc:
        return jsonify({"error": str(exc)}), 400


@reports_bp.get("/sales-by-store")
@require_auth
@require_permission("VIEW_SALES_REPORTS")
def sales_by_store_report():
    store_id = request.args.get("store_id", type=int)
    if not store_id:
        return jsonify({"error": "store_id is required"}), 400

    include_children = request.args.get("include_children", "false").lower() == "true"
    start = request.args.get("start")
    end = request.args.get("end")

    try:
        report = reporting_service.sales_by_store_report(
            store_id=store_id,
            include_children=include_children,
            start=start,
            end=end,
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


@reports_bp.get("/product-margin-outliers")
@require_auth
@require_permission("VIEW_COGS")
def product_margin_outliers_report():
    store_id = request.args.get("store_id", type=int)
    if not store_id:
        return jsonify({"error": "store_id is required"}), 400

    include_children = request.args.get("include_children", "false").lower() == "true"
    margin_threshold_pct = request.args.get("margin_threshold_pct", 20, type=int)

    try:
        report = reporting_service.product_margin_outliers(
            store_id=store_id,
            include_children=include_children,
            margin_threshold_pct=margin_threshold_pct,
        )
        return jsonify(report), 200
    except reporting_service.ReportError as exc:
        return jsonify({"error": str(exc)}), 400


@reports_bp.get("/discount-impact")
@require_auth
@require_permission("VIEW_SALES_REPORTS")
def discount_impact_report():
    store_id = request.args.get("store_id", type=int)
    if not store_id:
        return jsonify({"error": "store_id is required"}), 400

    include_children = request.args.get("include_children", "false").lower() == "true"
    start = request.args.get("start")
    end = request.args.get("end")

    try:
        report = reporting_service.discount_impact_report(
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


@reports_bp.get("/low-stock")
@require_auth
@require_permission("VIEW_INVENTORY")
def low_stock_report():
    store_id = request.args.get("store_id", type=int)
    if not store_id:
        return jsonify({"error": "store_id is required"}), 400

    include_children = request.args.get("include_children", "false").lower() == "true"
    threshold = request.args.get("threshold", 10, type=int)

    try:
        report = reporting_service.low_stock_report(
            store_id=store_id,
            include_children=include_children,
            threshold=threshold,
        )
        return jsonify(report), 200
    except reporting_service.ReportError as exc:
        return jsonify({"error": str(exc)}), 400


@reports_bp.get("/shrinkage")
@require_auth
@require_permission("VIEW_INVENTORY")
def shrinkage_report():
    store_id = request.args.get("store_id", type=int)
    if not store_id:
        return jsonify({"error": "store_id is required"}), 400

    include_children = request.args.get("include_children", "false").lower() == "true"
    start = request.args.get("start")
    end = request.args.get("end")

    try:
        report = reporting_service.shrinkage_report(
            store_id=store_id,
            include_children=include_children,
            start=start,
            end=end,
        )
        return jsonify(report), 200
    except reporting_service.ReportError as exc:
        return jsonify({"error": str(exc)}), 400


@reports_bp.get("/inventory-movement")
@require_auth
@require_permission("VIEW_INVENTORY")
def inventory_movement_report():
    store_id = request.args.get("store_id", type=int)
    if not store_id:
        return jsonify({"error": "store_id is required"}), 400

    include_children = request.args.get("include_children", "false").lower() == "true"
    start = request.args.get("start")
    end = request.args.get("end")

    try:
        report = reporting_service.inventory_movement_report(
            store_id=store_id,
            include_children=include_children,
            start=start,
            end=end,
        )
        return jsonify(report), 200
    except reporting_service.ReportError as exc:
        return jsonify({"error": str(exc)}), 400


@reports_bp.get("/vendor-spend")
@require_auth
@require_permission("VIEW_VENDORS")
def vendor_spend_report():
    store_id = request.args.get("store_id", type=int)
    if not store_id:
        return jsonify({"error": "store_id is required"}), 400

    include_children = request.args.get("include_children", "false").lower() == "true"
    start = request.args.get("start")
    end = request.args.get("end")

    try:
        report = reporting_service.vendor_spend_report(
            store_id=store_id,
            include_children=include_children,
            start=start,
            end=end,
        )
        return jsonify(report), 200
    except reporting_service.ReportError as exc:
        return jsonify({"error": str(exc)}), 400


@reports_bp.get("/cost-changes")
@require_auth
@require_permission("VIEW_COGS")
def cost_changes_report():
    store_id = request.args.get("store_id", type=int)
    if not store_id:
        return jsonify({"error": "store_id is required"}), 400

    include_children = request.args.get("include_children", "false").lower() == "true"
    product_id = request.args.get("product_id", type=int)

    try:
        report = reporting_service.cost_change_report(
            store_id=store_id,
            include_children=include_children,
            product_id=product_id,
        )
        return jsonify(report), 200
    except reporting_service.ReportError as exc:
        return jsonify({"error": str(exc)}), 400


@reports_bp.get("/register-reconciliation")
@require_auth
@require_permission("MANAGE_REGISTER")
def register_reconciliation_report():
    store_id = request.args.get("store_id", type=int)
    if not store_id:
        return jsonify({"error": "store_id is required"}), 400

    include_children = request.args.get("include_children", "false").lower() == "true"
    start = request.args.get("start")
    end = request.args.get("end")

    try:
        report = reporting_service.register_reconciliation_report(
            store_id=store_id,
            include_children=include_children,
            start=start,
            end=end,
        )
        return jsonify(report), 200
    except reporting_service.ReportError as exc:
        return jsonify({"error": str(exc)}), 400


@reports_bp.get("/payment-breakdown")
@require_auth
@require_permission("VIEW_SALES_REPORTS")
def payment_breakdown_report():
    store_id = request.args.get("store_id", type=int)
    if not store_id:
        return jsonify({"error": "store_id is required"}), 400

    include_children = request.args.get("include_children", "false").lower() == "true"
    start = request.args.get("start")
    end = request.args.get("end")

    try:
        report = reporting_service.payment_breakdown_report(
            store_id=store_id,
            include_children=include_children,
            start=start,
            end=end,
        )
        return jsonify(report), 200
    except reporting_service.ReportError as exc:
        return jsonify({"error": str(exc)}), 400


@reports_bp.get("/over-short")
@require_auth
@require_permission("MANAGE_REGISTER")
def over_short_report():
    store_id = request.args.get("store_id", type=int)
    if not store_id:
        return jsonify({"error": "store_id is required"}), 400

    include_children = request.args.get("include_children", "false").lower() == "true"
    start = request.args.get("start")
    end = request.args.get("end")

    try:
        report = reporting_service.over_short_report(
            store_id=store_id,
            include_children=include_children,
            start=start,
            end=end,
        )
        return jsonify(report), 200
    except reporting_service.ReportError as exc:
        return jsonify({"error": str(exc)}), 400


@reports_bp.get("/labor-hours")
@require_auth
@require_permission("VIEW_TIMEKEEPING")
def labor_hours_report():
    store_id = request.args.get("store_id", type=int)
    if not store_id:
        return jsonify({"error": "store_id is required"}), 400

    include_children = request.args.get("include_children", "false").lower() == "true"
    start = request.args.get("start")
    end = request.args.get("end")

    try:
        report = reporting_service.labor_hours_report(
            store_id=store_id,
            include_children=include_children,
            start=start,
            end=end,
        )
        return jsonify(report), 200
    except reporting_service.ReportError as exc:
        return jsonify({"error": str(exc)}), 400


@reports_bp.get("/labor-vs-sales")
@require_auth
@require_permission("VIEW_TIMEKEEPING")
def labor_vs_sales_report():
    store_id = request.args.get("store_id", type=int)
    if not store_id:
        return jsonify({"error": "store_id is required"}), 400

    include_children = request.args.get("include_children", "false").lower() == "true"
    start = request.args.get("start")
    end = request.args.get("end")

    try:
        report = reporting_service.labor_vs_sales_report(
            store_id=store_id,
            include_children=include_children,
            start=start,
            end=end,
        )
        return jsonify(report), 200
    except reporting_service.ReportError as exc:
        return jsonify({"error": str(exc)}), 400


@reports_bp.get("/employee-performance")
@require_auth
@require_permission("VIEW_SALES_REPORTS")
def employee_performance_report():
    store_id = request.args.get("store_id", type=int)
    if not store_id:
        return jsonify({"error": "store_id is required"}), 400

    include_children = request.args.get("include_children", "false").lower() == "true"
    start = request.args.get("start")
    end = request.args.get("end")

    try:
        report = reporting_service.employee_performance_report(
            store_id=store_id,
            include_children=include_children,
            start=start,
            end=end,
        )
        return jsonify(report), 200
    except reporting_service.ReportError as exc:
        return jsonify({"error": str(exc)}), 400


@reports_bp.get("/customer-clv")
@require_auth
@require_permission("VIEW_SALES_REPORTS")
def customer_clv_report():
    store_id = request.args.get("store_id", type=int)
    if not store_id:
        return jsonify({"error": "store_id is required"}), 400

    include_children = request.args.get("include_children", "false").lower() == "true"
    limit = request.args.get("limit", 50, type=int)

    try:
        report = reporting_service.customer_clv_report(
            store_id=store_id,
            include_children=include_children,
            limit=limit,
        )
        return jsonify(report), 200
    except reporting_service.ReportError as exc:
        return jsonify({"error": str(exc)}), 400


@reports_bp.get("/customer-retention")
@require_auth
@require_permission("VIEW_SALES_REPORTS")
def customer_retention_report():
    store_id = request.args.get("store_id", type=int)
    if not store_id:
        return jsonify({"error": "store_id is required"}), 400

    include_children = request.args.get("include_children", "false").lower() == "true"
    start = request.args.get("start")
    end = request.args.get("end")

    try:
        report = reporting_service.customer_retention_report(
            store_id=store_id,
            include_children=include_children,
            start=start,
            end=end,
        )
        return jsonify(report), 200
    except reporting_service.ReportError as exc:
        return jsonify({"error": str(exc)}), 400


@reports_bp.get("/rewards-liability")
@require_auth
@require_permission("VIEW_SALES_REPORTS")
def rewards_liability_report():
    store_id = request.args.get("store_id", type=int)
    if not store_id:
        return jsonify({"error": "store_id is required"}), 400

    include_children = request.args.get("include_children", "false").lower() == "true"

    try:
        report = reporting_service.rewards_liability_report(
            store_id=store_id,
            include_children=include_children,
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


@reports_bp.get("/refund-audit")
@require_auth
@require_permission("VIEW_AUDIT_LOG")
def refund_audit_report():
    store_id = request.args.get("store_id", type=int)
    if not store_id:
        return jsonify({"error": "store_id is required"}), 400

    include_children = request.args.get("include_children", "false").lower() == "true"
    start = request.args.get("start")
    end = request.args.get("end")
    limit = request.args.get("limit", 200, type=int)

    try:
        report = reporting_service.refund_audit_report(
            store_id=store_id,
            include_children=include_children,
            start=start,
            end=end,
            limit=limit,
        )
        return jsonify(report), 200
    except reporting_service.ReportError as exc:
        return jsonify({"error": str(exc)}), 400


@reports_bp.get("/price-overrides")
@require_auth
@require_permission("VIEW_AUDIT_LOG")
def price_overrides_report():
    store_id = request.args.get("store_id", type=int)
    if not store_id:
        return jsonify({"error": "store_id is required"}), 400

    include_children = request.args.get("include_children", "false").lower() == "true"
    start = request.args.get("start")
    end = request.args.get("end")
    limit = request.args.get("limit", 200, type=int)

    try:
        report = reporting_service.price_override_report(
            store_id=store_id,
            include_children=include_children,
            start=start,
            end=end,
            limit=limit,
        )
        return jsonify(report), 200
    except reporting_service.ReportError as exc:
        return jsonify({"error": str(exc)}), 400


@reports_bp.get("/void-audit")
@require_auth
@require_permission("VIEW_AUDIT_LOG")
def void_audit_report():
    store_id = request.args.get("store_id", type=int)
    if not store_id:
        return jsonify({"error": "store_id is required"}), 400

    include_children = request.args.get("include_children", "false").lower() == "true"
    start = request.args.get("start")
    end = request.args.get("end")
    limit = request.args.get("limit", 200, type=int)

    try:
        report = reporting_service.void_audit_report(
            store_id=store_id,
            include_children=include_children,
            start=start,
            end=end,
            limit=limit,
        )
        return jsonify(report), 200
    except reporting_service.ReportError as exc:
        return jsonify({"error": str(exc)}), 400


@reports_bp.get("/suspicious-activity")
@require_auth
@require_permission("VIEW_AUDIT_LOG")
def suspicious_activity_report():
    store_id = request.args.get("store_id", type=int)
    if not store_id:
        return jsonify({"error": "store_id is required"}), 400

    include_children = request.args.get("include_children", "false").lower() == "true"
    start = request.args.get("start")
    end = request.args.get("end")

    try:
        report = reporting_service.suspicious_activity_report(
            store_id=store_id,
            include_children=include_children,
            start=start,
            end=end,
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
