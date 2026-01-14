# backend/app/routes/registers.py
"""
Phase 8: Register Management API Routes

WHY: Enable POS register operations and shift accountability.
Provides endpoints for register setup, shift management, and cash drawer tracking.

DESIGN:
- Register CRUD operations (admin/manager only)
- Shift lifecycle: open → close (immutable once closed)
- Cash drawer event logging (audit trail)
- Manager approval required for no-sale opens and cash drops

SECURITY:
- CREATE_REGISTER, MANAGE_REGISTER permissions for setup
- CREATE_SALE permission for shift operations (cashiers can open/close)
- Manager approval enforced for sensitive drawer operations
"""

from flask import Blueprint, request, jsonify, g
from sqlalchemy import desc

from ..models import Register, RegisterSession, CashDrawerEvent
from ..extensions import db
from ..services import register_service
from ..services.register_service import ShiftError
from ..decorators import require_auth, require_permission
from datetime import datetime


registers_bp = Blueprint("registers", __name__, url_prefix="/api/registers")


# =============================================================================
# REGISTER MANAGEMENT (Admin/Manager)
# =============================================================================

@registers_bp.post("/")
@require_auth
@require_permission("MANAGE_REGISTER")
def create_register_route():
    """
    Create a new POS register.

    Requires: MANAGE_REGISTER permission
    Available to: admin, manager

    Request body:
    {
        "store_id": 1,
        "register_number": "REG-01",
        "name": "Front Counter Register 1",
        "location": "Main Floor",
        "device_id": "DEVICE-12345"  (optional)
    }
    """
    try:
        data = request.get_json()

        store_id = data.get("store_id")
        register_number = data.get("register_number")
        name = data.get("name")
        location = data.get("location")
        device_id = data.get("device_id")

        if not all([store_id, register_number, name]):
            return jsonify({"error": "store_id, register_number, and name required"}), 400

        register = register_service.create_register(
            store_id=store_id,
            register_number=register_number,
            name=name,
            location=location,
            device_id=device_id
        )

        return jsonify({"register": register.to_dict()}), 201

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@registers_bp.get("/")
@require_auth
@require_permission("CREATE_SALE")  # Anyone who can create sales can view registers
def list_registers_route():
    """
    List all active registers.

    Requires: CREATE_SALE permission
    Available to: admin, manager, cashier
    """
    store_id = request.args.get("store_id", type=int)

    query = db.session.query(Register).filter_by(is_active=True)

    if store_id:
        query = query.filter_by(store_id=store_id)

    registers = query.order_by(Register.register_number).all()

    return jsonify({
        "registers": [r.to_dict() for r in registers]
    }), 200


@registers_bp.get("/<int:register_id>")
@require_auth
@require_permission("CREATE_SALE")
def get_register_route(register_id: int):
    """
    Get register details including current session status.

    Requires: CREATE_SALE permission
    Available to: admin, manager, cashier
    """
    register = db.session.query(Register).get(register_id)

    if not register:
        return jsonify({"error": "Register not found"}), 404

    # Get current open session if any
    current_session = db.session.query(RegisterSession).filter_by(
        register_id=register_id,
        status="OPEN"
    ).first()

    result = register.to_dict()

    if current_session:
        result["current_session"] = current_session.to_dict()
    else:
        result["current_session"] = None

    return jsonify(result), 200


@registers_bp.patch("/<int:register_id>")
@require_auth
@require_permission("MANAGE_REGISTER")
def update_register_route(register_id: int):
    """
    Update register details.

    Requires: MANAGE_REGISTER permission
    Available to: admin, manager
    """
    try:
        register = db.session.query(Register).get(register_id)

        if not register:
            return jsonify({"error": "Register not found"}), 404

        data = request.get_json()

        # Update allowed fields
        if "name" in data:
            register.name = data["name"]
        if "location" in data:
            register.location = data["location"]
        if "device_id" in data:
            register.device_id = data["device_id"]
        if "is_active" in data:
            register.is_active = data["is_active"]

        register.updated_at = datetime.utcnow()
        db.session.commit()

        return jsonify({"register": register.to_dict()}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# =============================================================================
# SHIFT MANAGEMENT
# =============================================================================

@registers_bp.post("/<int:register_id>/shifts/open")
@require_auth
@require_permission("CREATE_SALE")  # Cashiers can open shifts
def open_shift_route(register_id: int):
    """
    Open a new shift on a register.

    Requires: CREATE_SALE permission
    Available to: admin, manager, cashier

    Request body:
    {
        "opening_cash_cents": 10000  // Starting cash (e.g., $100.00)
    }

    Returns 400 if register already has an open shift.
    """
    try:
        data = request.get_json()
        opening_cash_cents = data.get("opening_cash_cents", 0)

        if opening_cash_cents < 0:
            return jsonify({"error": "opening_cash_cents cannot be negative"}), 400

        session = register_service.open_shift(
            register_id=register_id,
            user_id=g.current_user.id,
            opening_cash_cents=opening_cash_cents
        )

        return jsonify({"session": session.to_dict()}), 201

    except ShiftError as e:
        return jsonify({"error": str(e)}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@registers_bp.post("/sessions/<int:session_id>/close")
@require_auth
@require_permission("CREATE_SALE")
def close_shift_route(session_id: int):
    """
    Close a shift and calculate cash variance.

    Requires: CREATE_SALE permission
    Available to: admin, manager, cashier

    Request body:
    {
        "closing_cash_cents": 12500,  // Actual cash counted
        "notes": "Shift went well, no issues"  (optional)
    }

    Calculates variance: closing_cash - expected_cash
    Session becomes immutable after closing.
    """
    try:
        data = request.get_json()
        closing_cash_cents = data.get("closing_cash_cents")
        notes = data.get("notes")

        if closing_cash_cents is None:
            return jsonify({"error": "closing_cash_cents required"}), 400

        if closing_cash_cents < 0:
            return jsonify({"error": "closing_cash_cents cannot be negative"}), 400

        session = register_service.close_shift(
            session_id=session_id,
            closing_cash_cents=closing_cash_cents,
            notes=notes
        )

        return jsonify({"session": session.to_dict()}), 200

    except ShiftError as e:
        return jsonify({"error": str(e)}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@registers_bp.get("/sessions/<int:session_id>")
@require_auth
@require_permission("CREATE_SALE")
def get_session_route(session_id: int):
    """
    Get session details with all drawer events.

    Requires: CREATE_SALE permission
    Available to: admin, manager, cashier
    """
    session = db.session.query(RegisterSession).get(session_id)

    if not session:
        return jsonify({"error": "Session not found"}), 404

    # Get all drawer events for this session
    events = db.session.query(CashDrawerEvent).filter_by(
        register_session_id=session_id
    ).order_by(CashDrawerEvent.occurred_at).all()

    return jsonify({
        "session": session.to_dict(),
        "events": [e.to_dict() for e in events]
    }), 200


@registers_bp.get("/<int:register_id>/sessions")
@require_auth
@require_permission("CREATE_SALE")
def list_sessions_route(register_id: int):
    """
    List all sessions for a register.

    Requires: CREATE_SALE permission
    Available to: admin, manager, cashier

    Query params:
    - status: Filter by status (OPEN or CLOSED)
    - limit: Max number of sessions to return (default: 50)
    """
    status = request.args.get("status")
    limit = request.args.get("limit", 50, type=int)

    query = db.session.query(RegisterSession).filter_by(register_id=register_id)

    if status:
        query = query.filter_by(status=status)

    sessions = query.order_by(desc(RegisterSession.opened_at)).limit(limit).all()

    return jsonify({
        "sessions": [s.to_dict() for s in sessions]
    }), 200


# =============================================================================
# CASH DRAWER OPERATIONS
# =============================================================================

@registers_bp.post("/sessions/<int:session_id>/drawer/no-sale")
@require_auth
@require_permission("CREATE_SALE")
def no_sale_drawer_open_route(session_id: int):
    """
    Open cash drawer without a sale (requires manager approval).

    Requires: CREATE_SALE permission (but approval requires manager)
    Available to: admin, manager, cashier

    Request body:
    {
        "approved_by_user_id": 2,  // Manager's user ID
        "reason": "Customer needed change"
    }

    WHY: Accountability for non-sale drawer opens.
    Prevents unauthorized drawer access.
    """
    try:
        session = db.session.query(RegisterSession).get(session_id)

        if not session:
            return jsonify({"error": "Session not found"}), 404

        if session.status != "OPEN":
            return jsonify({"error": "Session is not open"}), 400

        data = request.get_json()
        approved_by_user_id = data.get("approved_by_user_id")
        reason = data.get("reason")

        if not all([approved_by_user_id, reason]):
            return jsonify({"error": "approved_by_user_id and reason required"}), 400

        event = register_service.open_drawer_no_sale(
            register_session_id=session_id,
            register_id=session.register_id,
            user_id=g.current_user.id,
            approved_by_user_id=approved_by_user_id,
            reason=reason
        )

        return jsonify({"event": event.to_dict()}), 201

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@registers_bp.post("/sessions/<int:session_id>/drawer/cash-drop")
@require_auth
@require_permission("CREATE_SALE")
def cash_drop_route(session_id: int):
    """
    Remove excess cash from drawer (requires manager approval).

    Requires: CREATE_SALE permission (but approval requires manager)
    Available to: admin, manager, cashier

    Request body:
    {
        "amount_cents": 10000,  // Amount removed (e.g., $100.00)
        "approved_by_user_id": 2,  // Manager's user ID
        "reason": "Safe drop - drawer over $200"
    }

    WHY: Reduces cash-on-hand risk. Maintains audit trail.
    Requires manager approval for accountability.
    """
    try:
        session = db.session.query(RegisterSession).get(session_id)

        if not session:
            return jsonify({"error": "Session not found"}), 404

        if session.status != "OPEN":
            return jsonify({"error": "Session is not open"}), 400

        data = request.get_json()
        amount_cents = data.get("amount_cents")
        approved_by_user_id = data.get("approved_by_user_id")
        reason = data.get("reason")

        if not all([amount_cents, approved_by_user_id, reason]):
            return jsonify({"error": "amount_cents, approved_by_user_id, and reason required"}), 400

        if amount_cents <= 0:
            return jsonify({"error": "amount_cents must be positive"}), 400

        event = register_service.cash_drop(
            register_session_id=session_id,
            register_id=session.register_id,
            user_id=g.current_user.id,
            amount_cents=amount_cents,
            approved_by_user_id=approved_by_user_id,
            reason=reason
        )

        return jsonify({"event": event.to_dict()}), 201

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =============================================================================
# AUDIT & REPORTING
# =============================================================================

@registers_bp.get("/<int:register_id>/events")
@require_auth
@require_permission("CREATE_SALE")
def list_drawer_events_route(register_id: int):
    """
    List all drawer events for a register.

    Requires: CREATE_SALE permission
    Available to: admin, manager, cashier

    Query params:
    - event_type: Filter by event type
    - start_date: Filter events after this date (ISO 8601)
    - end_date: Filter events before this date (ISO 8601)
    - limit: Max number of events (default: 100)
    """
    event_type = request.args.get("event_type")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    limit = request.args.get("limit", 100, type=int)

    query = db.session.query(CashDrawerEvent).filter_by(register_id=register_id)

    if event_type:
        query = query.filter_by(event_type=event_type)

    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            query = query.filter(CashDrawerEvent.occurred_at >= start_dt)
        except ValueError:
            return jsonify({"error": "Invalid start_date format"}), 400

    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            query = query.filter(CashDrawerEvent.occurred_at <= end_dt)
        except ValueError:
            return jsonify({"error": "Invalid end_date format"}), 400

    events = query.order_by(desc(CashDrawerEvent.occurred_at)).limit(limit).all()

    return jsonify({
        "events": [e.to_dict() for e in events]
    }), 200
