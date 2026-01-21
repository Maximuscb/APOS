# Overview: Flask API routes for timekeeping operations; parses input and returns JSON responses.

"""
Timekeeping Routes

SECURITY:
- Clock in/out and breaks require CLOCK_IN_OUT permission.
- Corrections require CLOCK_IN_OUT to submit and APPROVE_TIME_CORRECTIONS to approve.
- Viewing entries requires VIEW_TIMEKEEPING or MANAGE_TIMEKEEPING.
"""

from flask import Blueprint, request, jsonify, g

from ..decorators import require_auth, require_permission, require_any_permission
from ..services import timekeeping_service
from ..extensions import db
from ..models import TimeClockEntry
from ..services.timekeeping_service import TimekeepingError
from ..services.tenant_service import require_store_in_org, TenantAccessError, get_org_store_ids
from app.time_utils import parse_iso_datetime


timekeeping_bp = Blueprint("timekeeping", __name__, url_prefix="/api/timekeeping")


@timekeeping_bp.post("/clock-in")
@require_auth
@require_permission("CLOCK_IN_OUT")
def clock_in_route():
    data = request.get_json(silent=True) or {}
    store_id = data.get("store_id")
    register_session_id = data.get("register_session_id")
    notes = data.get("notes")

    if not store_id:
        return jsonify({"error": "store_id is required"}), 400

    try:
        require_store_in_org(store_id, g.org_id)
        entry = timekeeping_service.clock_in(
            user_id=g.current_user.id,
            store_id=store_id,
            register_session_id=register_session_id,
            notes=notes,
        )
        return jsonify({"entry": entry.to_dict()}), 201
    except TenantAccessError:
        return jsonify({"error": "Store not found"}), 404
    except TimekeepingError as e:
        return jsonify({"error": str(e)}), 400


@timekeeping_bp.post("/clock-out")
@require_auth
@require_permission("CLOCK_IN_OUT")
def clock_out_route():
    try:
        entry = timekeeping_service.clock_out(user_id=g.current_user.id)
        return jsonify({"entry": entry.to_dict()})
    except TimekeepingError as e:
        return jsonify({"error": str(e)}), 400


@timekeeping_bp.post("/break/start")
@require_auth
@require_permission("CLOCK_IN_OUT")
def start_break_route():
    data = request.get_json(silent=True) or {}
    break_type = data.get("break_type", "UNPAID")

    try:
        brk = timekeeping_service.start_break(user_id=g.current_user.id, break_type=break_type)
        return jsonify({"break": brk.to_dict()}), 201
    except TimekeepingError as e:
        return jsonify({"error": str(e)}), 400


@timekeeping_bp.post("/break/end")
@require_auth
@require_permission("CLOCK_IN_OUT")
def end_break_route():
    try:
        brk = timekeeping_service.end_break(user_id=g.current_user.id)
        return jsonify({"break": brk.to_dict()})
    except TimekeepingError as e:
        return jsonify({"error": str(e)}), 400


@timekeeping_bp.get("/status")
@require_auth
@require_permission("CLOCK_IN_OUT")
def get_status_route():
    return jsonify(timekeeping_service.get_current_status(g.current_user.id))


@timekeeping_bp.get("/entries")
@require_auth
@require_any_permission("VIEW_TIMEKEEPING", "MANAGE_TIMEKEEPING")
def list_entries_route():
    user_id = request.args.get("user_id", type=int)
    store_id = request.args.get("store_id", type=int)

    query = db.session.query(TimeClockEntry)
    if user_id:
        query = query.filter_by(user_id=user_id)
    if store_id:
        try:
            require_store_in_org(store_id, g.org_id)
        except TenantAccessError:
            return jsonify({"error": "Store not found"}), 404
        query = query.filter_by(store_id=store_id)
    else:
        store_ids = get_org_store_ids(g.org_id)
        query = query.filter(TimeClockEntry.store_id.in_(store_ids))

    entries = query.order_by(TimeClockEntry.clock_in_at.desc()).limit(500).all()
    return jsonify({"entries": [e.to_dict() for e in entries], "count": len(entries)})


@timekeeping_bp.post("/corrections")
@require_auth
@require_permission("CLOCK_IN_OUT")
def create_correction_route():
    data = request.get_json(silent=True) or {}
    entry_id = data.get("entry_id")
    corrected_clock_in_at = data.get("corrected_clock_in_at")
    corrected_clock_out_at = data.get("corrected_clock_out_at")
    reason = data.get("reason")

    if not entry_id or not corrected_clock_in_at or not reason:
        return jsonify({"error": "entry_id, corrected_clock_in_at, and reason are required"}), 400

    corrected_in = parse_iso_datetime(corrected_clock_in_at)
    if not corrected_in:
        return jsonify({"error": "Invalid corrected_clock_in_at"}), 400

    corrected_out = None
    if corrected_clock_out_at:
        corrected_out = parse_iso_datetime(corrected_clock_out_at)
        if not corrected_out:
            return jsonify({"error": "Invalid corrected_clock_out_at"}), 400

    try:
        correction = timekeeping_service.create_correction(
            entry_id=entry_id,
            corrected_clock_in_at=corrected_in,
            corrected_clock_out_at=corrected_out,
            reason=reason,
            submitted_by_user_id=g.current_user.id,
        )
        return jsonify({"correction": correction.to_dict()}), 201
    except TimekeepingError as e:
        return jsonify({"error": str(e)}), 400


@timekeeping_bp.post("/corrections/<int:correction_id>/approve")
@require_auth
@require_permission("APPROVE_TIME_CORRECTIONS")
def approve_correction_route(correction_id: int):
    data = request.get_json(silent=True) or {}
    approval_notes = data.get("approval_notes")

    try:
        correction = timekeeping_service.approve_correction(
            correction_id=correction_id,
            approved_by_user_id=g.current_user.id,
            approval_notes=approval_notes,
        )
        return jsonify({"correction": correction.to_dict()})
    except TimekeepingError as e:
        return jsonify({"error": str(e)}), 400
