# Overview: Flask API routes for ledger operations; parses input and returns JSON responses.

from flask import Blueprint, request, jsonify, g, current_app
from sqlalchemy import or_, and_

from ..models import MasterLedgerEvent, OrganizationMasterLedger
from app.time_utils import parse_iso_datetime, to_utc_z
from ..decorators import require_auth, require_permission
from ..services import permission_service

"""
Time semantics:
- API accepts ISO-8601 datetimes with Z/offsets; backend normalizes to UTC-naive internally.
- as_of filtering is inclusive: occurred_at <= as_of.
"""

ledger_bp = Blueprint("ledger", __name__, url_prefix="/api/ledger")


@ledger_bp.get("")
@require_auth
@require_permission("VIEW_AUDIT_LOG")
def list_ledger_events_route():
    def _is_admin() -> bool:
        return permission_service.user_has_permission(g.current_user.id, "SYSTEM_ADMIN")

    def _is_global_operator() -> bool:
        return bool(getattr(g.current_user, "is_developer", False)) or _is_admin()

    store_id = request.args.get("store_id", type=int)

    if not _is_global_operator():
        if g.store_id is None:
            return jsonify({"error": "Store assignment required"}), 403
        if store_id is not None and store_id != g.store_id:
            return jsonify({"error": "Store access denied"}), 403
        store_id = g.store_id

    limit = request.args.get("limit", default=100, type=int)
    limit = max(1, min(limit, 500))

    as_of_raw = request.args.get("as_of")
    try:
        as_of_dt = parse_iso_datetime(as_of_raw)
    except Exception:
        return jsonify({"error": "as_of must be an ISO-8601 datetime"}), 400

    start_raw = request.args.get("start_date")
    end_raw = request.args.get("end_date")

    try:
        start_dt = parse_iso_datetime(start_raw)
        end_dt = parse_iso_datetime(end_raw)
    except Exception:
        return jsonify({"error": "start_date and end_date must be ISO-8601 datetimes"}), 400

    cursor_raw = request.args.get("cursor")
    cursor_dt = None
    cursor_id = None
    if cursor_raw:
        try:
            cursor_parts = cursor_raw.split("|")
            cursor_dt = parse_iso_datetime(cursor_parts[0])
            cursor_id = int(cursor_parts[1])
        except Exception:
            return jsonify({"error": "cursor must be in format <ISO-8601>|<id>"}), 400

    q = MasterLedgerEvent.query
    if g.org_id is not None:
        org_ledger = OrganizationMasterLedger.query.filter_by(org_id=g.org_id).first()
        if org_ledger:
            q = q.filter(MasterLedgerEvent.org_ledger_id == org_ledger.id)
        else:
            return jsonify({"items": [], "next_cursor": None, "limit": limit}), 200

    if store_id is not None:
        q = q.filter(MasterLedgerEvent.store_id == store_id)

    category = request.args.get("category")
    if category:
        q = q.filter(MasterLedgerEvent.event_category == category)

    event_type = request.args.get("event_type")
    if event_type:
        q = q.filter(MasterLedgerEvent.event_type == event_type)

    if as_of_dt is not None:
        q = q.filter(MasterLedgerEvent.occurred_at <= as_of_dt)

    if start_dt is not None:
        q = q.filter(MasterLedgerEvent.occurred_at >= start_dt)

    if end_dt is not None:
        q = q.filter(MasterLedgerEvent.occurred_at <= end_dt)

    if cursor_dt is not None and cursor_id is not None:
        q = q.filter(
            or_(
                MasterLedgerEvent.occurred_at < cursor_dt,
                and_(MasterLedgerEvent.occurred_at == cursor_dt, MasterLedgerEvent.id < cursor_id),
            )
        )

    rows = (
        q.order_by(MasterLedgerEvent.occurred_at.desc(), MasterLedgerEvent.id.desc())
        .limit(limit)
        .all()
    )

    next_cursor = None
    if rows:
        last = rows[-1]
        next_cursor = f"{to_utc_z(last.occurred_at)}|{last.id}"

    return jsonify({
        "items": [r.to_dict() for r in rows],
        "next_cursor": next_cursor,
        "limit": limit,
    }), 200
