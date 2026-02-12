# Overview: Flask API routes for registers operations; parses input and returns JSON responses.

# backend/app/routes/registers.py
"""
Register Management API Routes

WHY: Enable POS register operations and shift accountability.
Provides endpoints for register setup, shift management, and cash drawer tracking.

DESIGN:
- Register CRUD operations (admin/manager only)
- Shift lifecycle: open -> close (immutable once closed)
- Cash drawer event logging (audit trail)
- Manager approval required for no-sale opens and cash drops

SECURITY:
- CREATE_REGISTER, MANAGE_REGISTER permissions for setup
- CREATE_SALE permission for shift operations (cashiers can open/close)
- Manager approval enforced for sensitive drawer operations
"""

from flask import Blueprint, request, jsonify, g, current_app
from sqlalchemy import desc
import json

from ..models import Register, RegisterSession, CashDrawerEvent, CashDrawer, Printer
from ..extensions import db
from ..services import register_service, permission_service, store_service, session_service, tenant_service
from ..services.register_service import ShiftError
from ..decorators import require_auth, require_permission
from datetime import datetime


registers_bp = Blueprint("registers", __name__, url_prefix="/api/registers")


def _is_admin() -> bool:
    return permission_service.user_has_permission(g.current_user.id, "SYSTEM_ADMIN")


def _is_global_operator() -> bool:
    return bool(getattr(g.current_user, "is_developer", False)) or _is_admin()


def _ensure_store_scope(store_id: int | None):
    if store_id is not None:
        try:
            tenant_service.require_store_in_org(store_id, g.org_id)
        except tenant_service.TenantAccessError:
            return jsonify({"error": "Store access denied"}), 403
    if _is_global_operator():
        return
    if g.store_id is not None and store_id is not None and g.store_id != store_id:
        return jsonify({"error": "Store access denied"}), 403
    return None


def _get_register_in_org(register_id: int) -> Register | None:
    return db.session.query(Register).filter_by(id=register_id, org_id=g.org_id).first()


def _get_cash_drawer_policy(store_id: int) -> str:
    config = store_service.get_store_config(store_id, "cash_drawer_approval_mode")
    if not config or not config.value:
        return "MANAGER_ONLY"
    return config.value.upper()


# =============================================================================
# REGISTER MANAGEMENT (Admin/Manager)
# =============================================================================

@registers_bp.post("/")
@registers_bp.post("")
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
        "register_number": "REG-01",  // optional (auto-assigned if omitted)
        "name": "Front Counter Register 1",
        "location": "Main Floor"
    }
    """
    try:
        data = request.get_json(silent=True) or {}

        store_id = data.get("store_id")
        register_number = data.get("register_number")
        name = data.get("name")
        location = data.get("location")

        if not all([store_id, name]):
            return jsonify({"error": "store_id and name required"}), 400
        try:
            tenant_service.require_store_in_org(store_id, g.org_id)
        except tenant_service.TenantAccessError:
            return jsonify({"error": "Store access denied"}), 403

        register = register_service.create_register(
            store_id=store_id,
            register_number=register_number,
            name=name,
            location=location,
            org_id=g.org_id,
            actor_user_id=g.current_user.id,
        )

        return jsonify({"register": register.to_dict()}), 201

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        current_app.logger.exception("Failed to create register")
        return jsonify({"error": "Internal server error"}), 500


@registers_bp.get("/")
@registers_bp.get("")
@require_auth
@require_permission("CREATE_SALE")  # Anyone who can create sales can view registers
def list_registers_route():
    """
    List all active registers.

    Requires: CREATE_SALE permission
    Available to: admin, manager, cashier
    """
    store_id = request.args.get("store_id", type=int)
    if store_id is None:
        return jsonify({"error": "store_id is required"}), 400

    scope_error = _ensure_store_scope(store_id)
    if scope_error:
        return scope_error

    query = db.session.query(Register).filter_by(is_active=True, org_id=g.org_id)
    query = query.filter_by(store_id=store_id)

    registers = query.order_by(Register.register_number).all()

    result = []
    for r in registers:
        d = r.to_dict()
        current_session = db.session.query(RegisterSession).filter_by(
            register_id=r.id,
            status="OPEN"
        ).first()
        d["current_session"] = current_session.to_dict() if current_session else None
        result.append(d)

    return jsonify({
        "registers": result
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
    register = _get_register_in_org(register_id)

    if not register:
        return jsonify({"error": "Register not found"}), 404
    scope_error = _ensure_store_scope(register.store_id)
    if scope_error:
        return scope_error

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
        register = _get_register_in_org(register_id)

        if not register:
            return jsonify({"error": "Register not found"}), 404

        data = request.get_json() or {}
        changed: dict[str, object] = {}

        # Update allowed fields
        if "name" in data:
            new_name = data["name"]
            if register.name != new_name:
                changed["name"] = {"from": register.name, "to": new_name}
                register.name = new_name
        if "location" in data:
            new_location = data["location"]
            if register.location != new_location:
                changed["location"] = {"from": register.location, "to": new_location}
                register.location = new_location
        if "is_active" in data:
            new_is_active = bool(data["is_active"])
            if register.is_active != new_is_active:
                changed["is_active"] = {"from": register.is_active, "to": new_is_active}
                register.is_active = new_is_active

        register.updated_at = datetime.utcnow()
        if changed:
            register_service.append_ledger_event(
                store_id=register.store_id,
                event_type="device.register_updated",
                event_category="device",
                entity_type="register",
                entity_id=register.id,
                actor_user_id=g.current_user.id,
                register_id=register.id,
                note=f"Register {register.register_number} updated",
                payload=json.dumps(changed),
            )
        db.session.commit()

        return jsonify({"register": register.to_dict()}), 200

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to update register")
        return jsonify({"error": "Internal server error"}), 500


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

        register = _get_register_in_org(register_id)
        if not register:
            return jsonify({"error": "Register not found"}), 404
        scope_error = _ensure_store_scope(register.store_id)
        if scope_error:
            return scope_error

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
    except Exception:
        current_app.logger.exception("Failed to open shift")
        return jsonify({"error": "Internal server error"}), 500


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

        session = db.session.query(RegisterSession).get(session_id)
        if not session:
            return jsonify({"error": "Session not found"}), 404
        scope_error = _ensure_store_scope(session.register.store_id)
        if scope_error:
            return scope_error

        manager_override = permission_service.user_has_permission(g.current_user.id, "MANAGE_REGISTER")

        session = register_service.close_shift(
            session_id=session_id,
            closing_cash_cents=closing_cash_cents,
            notes=notes,
            current_user_id=g.current_user.id,
            manager_override=manager_override,
        )

        return jsonify({"session": session.to_dict()}), 200

    except ShiftError as e:
        return jsonify({"error": str(e)}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        current_app.logger.exception("Failed to close shift")
        return jsonify({"error": "Internal server error"}), 500


@registers_bp.post("/<int:register_id>/force-close")
@require_auth
@require_permission("MANAGE_REGISTER")
def force_close_register_route(register_id: int):
    """
    Force-close the currently open shift on a register (admin/manager action).

    Request body (optional):
    {
        "closing_cash_cents": 0,
        "notes": "Forced close by admin"
    }
    """
    try:
        register = _get_register_in_org(register_id)
        if not register:
            return jsonify({"error": "Register not found"}), 404
        scope_error = _ensure_store_scope(register.store_id)
        if scope_error:
            return scope_error

        open_session = db.session.query(RegisterSession).filter_by(
            register_id=register_id,
            status="OPEN",
        ).first()
        if not open_session:
            return jsonify({"error": "No open session on this register"}), 404

        data = request.get_json(silent=True) or {}
        closing_cash_cents = data.get("closing_cash_cents")
        notes = data.get("notes")

        if closing_cash_cents is None:
            closing_cash_cents = open_session.expected_cash_cents or open_session.opening_cash_cents or 0
        if closing_cash_cents < 0:
            return jsonify({"error": "closing_cash_cents cannot be negative"}), 400

        session = register_service.close_shift(
            session_id=open_session.id,
            closing_cash_cents=closing_cash_cents,
            notes=notes or "Forced close by manager/admin",
            current_user_id=g.current_user.id,
            manager_override=True,
        )

        return jsonify({"session": session.to_dict()}), 200
    except ShiftError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        current_app.logger.exception("Failed to force-close register")
        return jsonify({"error": "Internal server error"}), 500


@registers_bp.get("/sessions/<int:session_id>")
@require_auth
@require_permission("MANAGE_REGISTER")
def get_session_route(session_id: int):
    """
    Get session details with all drawer events.

    Requires: CREATE_SALE permission
    Available to: admin, manager, cashier
    """
    session = db.session.query(RegisterSession).get(session_id)

    if not session:
        return jsonify({"error": "Session not found"}), 404
    scope_error = _ensure_store_scope(session.register.store_id)
    if scope_error:
        return scope_error

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
@require_permission("MANAGE_REGISTER")
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
    register = _get_register_in_org(register_id)
    if not register:
        return jsonify({"error": "Register not found"}), 404
    scope_error = _ensure_store_scope(register.store_id)
    if scope_error:
        return scope_error

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
        reason = data.get("reason")
        manager_token = data.get("manager_token")

        if not reason:
            return jsonify({"error": "reason required"}), 400

        policy = _get_cash_drawer_policy(session.register.store_id)
        approved_by_user_id = None

        if policy == "DUAL_AUTH":
            if not manager_token:
                return jsonify({"error": "manager_token required for dual-auth policy"}), 400
            manager_user = session_service.validate_session(manager_token)
            if not manager_user:
                return jsonify({"error": "Invalid manager token"}), 403
            if not permission_service.user_has_permission(manager_user.id, "MANAGE_REGISTER"):
                return jsonify({"error": "Manager permission required for approval"}), 403
            approved_by_user_id = manager_user.id
        else:
            if not permission_service.user_has_permission(g.current_user.id, "MANAGE_REGISTER"):
                return jsonify({"error": "Manager permission required"}), 403
            approved_by_user_id = g.current_user.id

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
    except Exception:
        current_app.logger.exception("Failed to log no-sale drawer open")
        return jsonify({"error": "Internal server error"}), 500


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
        reason = data.get("reason")
        manager_token = data.get("manager_token")

        if not all([amount_cents, reason]):
            return jsonify({"error": "amount_cents and reason required"}), 400

        if amount_cents <= 0:
            return jsonify({"error": "amount_cents must be positive"}), 400

        policy = _get_cash_drawer_policy(session.register.store_id)
        approved_by_user_id = None

        if policy == "DUAL_AUTH":
            if not manager_token:
                return jsonify({"error": "manager_token required for dual-auth policy"}), 400
            manager_user = session_service.validate_session(manager_token)
            if not manager_user:
                return jsonify({"error": "Invalid manager token"}), 403
            if not permission_service.user_has_permission(manager_user.id, "MANAGE_REGISTER"):
                return jsonify({"error": "Manager permission required for approval"}), 403
            approved_by_user_id = manager_user.id
        else:
            if not permission_service.user_has_permission(g.current_user.id, "MANAGE_REGISTER"):
                return jsonify({"error": "Manager permission required"}), 403
            approved_by_user_id = g.current_user.id

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
    except Exception:
        current_app.logger.exception("Failed to record cash drop")
        return jsonify({"error": "Internal server error"}), 500


# =============================================================================
# AUDIT & REPORTING
# =============================================================================

@registers_bp.get("/<int:register_id>/events")
@require_auth
@require_permission("MANAGE_REGISTER")
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

    register = _get_register_in_org(register_id)
    if not register:
        return jsonify({"error": "Register not found"}), 404
    scope_error = _ensure_store_scope(register.store_id)
    if scope_error:
        return scope_error

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


# =============================================================================
# CASH DRAWER HARDWARE CRUD
# =============================================================================

@registers_bp.get("/<int:register_id>/cash-drawer")
@require_auth
@require_permission("CREATE_SALE")
def get_cash_drawer(register_id: int):
    """Get the cash drawer config for a register."""
    register = _get_register_in_org(register_id)
    if not register:
        return jsonify({"error": "Register not found"}), 404
    scope_error = _ensure_store_scope(register.store_id)
    if scope_error:
        return scope_error

    drawer = db.session.query(CashDrawer).filter_by(register_id=register_id).first()
    return jsonify({"cash_drawer": drawer.to_dict() if drawer else None}), 200


@registers_bp.route("/<int:register_id>/cash-drawer", methods=["POST", "PUT"])
@require_auth
@require_permission("MANAGE_REGISTER")
def upsert_cash_drawer(register_id: int):
    """Create or update the cash drawer for a register."""
    register = _get_register_in_org(register_id)
    if not register:
        return jsonify({"error": "Register not found"}), 404
    scope_error = _ensure_store_scope(register.store_id)
    if scope_error:
        return scope_error

    data = request.get_json() or {}
    drawer = db.session.query(CashDrawer).filter_by(register_id=register_id).first()

    is_create = drawer is None
    changed: dict[str, object] = {}
    if not drawer:
        drawer = CashDrawer(register_id=register_id)
        db.session.add(drawer)

    if "model" in data:
        new_model = (data["model"] or "").strip() or None
        if drawer.model != new_model:
            changed["model"] = {"from": drawer.model, "to": new_model}
            drawer.model = new_model
    if "serial_number" in data:
        new_serial_number = (data["serial_number"] or "").strip() or None
        if drawer.serial_number != new_serial_number:
            changed["serial_number"] = {"from": drawer.serial_number, "to": new_serial_number}
            drawer.serial_number = new_serial_number
    if "connection_type" in data:
        new_connection_type = (data["connection_type"] or "").strip() or None
        if drawer.connection_type != new_connection_type:
            changed["connection_type"] = {"from": drawer.connection_type, "to": new_connection_type}
            drawer.connection_type = new_connection_type
    if "connection_address" in data:
        new_connection_address = (data["connection_address"] or "").strip() or None
        if drawer.connection_address != new_connection_address:
            changed["connection_address"] = {"from": drawer.connection_address, "to": new_connection_address}
            drawer.connection_address = new_connection_address
    if "is_active" in data:
        new_is_active = bool(data["is_active"])
        if drawer.is_active != new_is_active:
            changed["is_active"] = {"from": drawer.is_active, "to": new_is_active}
            drawer.is_active = new_is_active

    db.session.flush()
    register_service.append_ledger_event(
        store_id=register.store_id,
        event_type="device.cash_drawer_created" if is_create else "device.cash_drawer_updated",
        event_category="device",
        entity_type="cash_drawer",
        entity_id=drawer.id,
        actor_user_id=g.current_user.id,
        register_id=register.id,
        note=f"Cash drawer {'configured' if is_create else 'updated'} for register {register.register_number}",
        payload=json.dumps(changed) if changed else None,
    )

    db.session.commit()
    return jsonify({"cash_drawer": drawer.to_dict()}), 200


@registers_bp.delete("/<int:register_id>/cash-drawer")
@require_auth
@require_permission("MANAGE_REGISTER")
def delete_cash_drawer(register_id: int):
    """Remove cash drawer config from a register."""
    register = _get_register_in_org(register_id)
    if not register:
        return jsonify({"error": "Register not found"}), 404
    scope_error = _ensure_store_scope(register.store_id)
    if scope_error:
        return scope_error

    drawer = db.session.query(CashDrawer).filter_by(register_id=register_id).first()
    if not drawer:
        return jsonify({"error": "No cash drawer configured"}), 404

    register_service.append_ledger_event(
        store_id=register.store_id,
        event_type="device.cash_drawer_deleted",
        event_category="device",
        entity_type="cash_drawer",
        entity_id=drawer.id,
        actor_user_id=g.current_user.id,
        register_id=register.id,
        note=f"Cash drawer removed from register {register.register_number}",
    )
    db.session.delete(drawer)
    db.session.commit()
    return jsonify({"message": "Cash drawer removed"}), 200


# =============================================================================
# PRINTER CRUD
# =============================================================================

@registers_bp.get("/<int:register_id>/printers")
@require_auth
@require_permission("CREATE_SALE")
def list_printers(register_id: int):
    """List all printers for a register."""
    register = _get_register_in_org(register_id)
    if not register:
        return jsonify({"error": "Register not found"}), 404
    scope_error = _ensure_store_scope(register.store_id)
    if scope_error:
        return scope_error

    printers = db.session.query(Printer).filter_by(register_id=register_id).order_by(Printer.name).all()
    return jsonify({"printers": [p.to_dict() for p in printers]}), 200


@registers_bp.post("/<int:register_id>/printers")
@require_auth
@require_permission("MANAGE_REGISTER")
def create_printer(register_id: int):
    """Add a printer to a register."""
    register = _get_register_in_org(register_id)
    if not register:
        return jsonify({"error": "Register not found"}), 404
    scope_error = _ensure_store_scope(register.store_id)
    if scope_error:
        return scope_error

    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    printer_type = (data.get("printer_type") or "").strip().upper()

    if not name or not printer_type:
        return jsonify({"error": "name and printer_type are required"}), 400

    valid_types = {"RECEIPT", "KITCHEN", "LABEL", "REPORT"}
    if printer_type not in valid_types:
        return jsonify({"error": f"printer_type must be one of: {', '.join(sorted(valid_types))}"}), 400

    printer = Printer(
        register_id=register_id,
        name=name,
        printer_type=printer_type,
        model=(data.get("model") or "").strip() or None,
        serial_number=(data.get("serial_number") or "").strip() or None,
        connection_type=(data.get("connection_type") or "").strip() or None,
        connection_address=(data.get("connection_address") or "").strip() or None,
        paper_width_mm=data.get("paper_width_mm"),
        supports_cut=data.get("supports_cut", True),
        supports_cash_drawer=data.get("supports_cash_drawer", False),
    )
    db.session.add(printer)
    db.session.flush()
    register_service.append_ledger_event(
        store_id=register.store_id,
        event_type="device.printer_created",
        event_category="device",
        entity_type="printer",
        entity_id=printer.id,
        actor_user_id=g.current_user.id,
        register_id=register.id,
        note=f"Printer {printer.name} created for register {register.register_number}",
    )
    db.session.commit()
    return jsonify({"printer": printer.to_dict()}), 201


@registers_bp.patch("/printers/<int:printer_id>")
@require_auth
@require_permission("MANAGE_REGISTER")
def update_printer(printer_id: int):
    """Update a printer's configuration."""
    printer = db.session.query(Printer).filter_by(id=printer_id).first()
    if not printer:
        return jsonify({"error": "Printer not found"}), 404

    register = _get_register_in_org(printer.register_id)
    if not register:
        return jsonify({"error": "Register not found"}), 404
    scope_error = _ensure_store_scope(register.store_id)
    if scope_error:
        return scope_error

    data = request.get_json() or {}
    changed: dict[str, object] = {}

    if "name" in data:
        new_name = (data["name"] or "").strip() or printer.name
        if printer.name != new_name:
            changed["name"] = {"from": printer.name, "to": new_name}
            printer.name = new_name
    if "printer_type" in data:
        pt = (data["printer_type"] or "").strip().upper()
        valid_types = {"RECEIPT", "KITCHEN", "LABEL", "REPORT"}
        if pt not in valid_types:
            return jsonify({"error": f"printer_type must be one of: {', '.join(sorted(valid_types))}"}), 400
        if printer.printer_type != pt:
            changed["printer_type"] = {"from": printer.printer_type, "to": pt}
            printer.printer_type = pt
    if "model" in data:
        new_model = (data["model"] or "").strip() or None
        if printer.model != new_model:
            changed["model"] = {"from": printer.model, "to": new_model}
            printer.model = new_model
    if "serial_number" in data:
        new_serial_number = (data["serial_number"] or "").strip() or None
        if printer.serial_number != new_serial_number:
            changed["serial_number"] = {"from": printer.serial_number, "to": new_serial_number}
            printer.serial_number = new_serial_number
    if "connection_type" in data:
        new_connection_type = (data["connection_type"] or "").strip() or None
        if printer.connection_type != new_connection_type:
            changed["connection_type"] = {"from": printer.connection_type, "to": new_connection_type}
            printer.connection_type = new_connection_type
    if "connection_address" in data:
        new_connection_address = (data["connection_address"] or "").strip() or None
        if printer.connection_address != new_connection_address:
            changed["connection_address"] = {"from": printer.connection_address, "to": new_connection_address}
            printer.connection_address = new_connection_address
    if "paper_width_mm" in data:
        new_paper_width_mm = data["paper_width_mm"]
        if printer.paper_width_mm != new_paper_width_mm:
            changed["paper_width_mm"] = {"from": printer.paper_width_mm, "to": new_paper_width_mm}
            printer.paper_width_mm = new_paper_width_mm
    if "supports_cut" in data:
        new_supports_cut = bool(data["supports_cut"])
        if printer.supports_cut != new_supports_cut:
            changed["supports_cut"] = {"from": printer.supports_cut, "to": new_supports_cut}
            printer.supports_cut = new_supports_cut
    if "supports_cash_drawer" in data:
        new_supports_cash_drawer = bool(data["supports_cash_drawer"])
        if printer.supports_cash_drawer != new_supports_cash_drawer:
            changed["supports_cash_drawer"] = {"from": printer.supports_cash_drawer, "to": new_supports_cash_drawer}
            printer.supports_cash_drawer = new_supports_cash_drawer
    if "is_active" in data:
        new_is_active = bool(data["is_active"])
        if printer.is_active != new_is_active:
            changed["is_active"] = {"from": printer.is_active, "to": new_is_active}
            printer.is_active = new_is_active

    register_service.append_ledger_event(
        store_id=register.store_id,
        event_type="device.printer_updated",
        event_category="device",
        entity_type="printer",
        entity_id=printer.id,
        actor_user_id=g.current_user.id,
        register_id=register.id,
        note=f"Printer {printer.name} updated",
        payload=json.dumps(changed) if changed else None,
    )
    db.session.commit()
    return jsonify({"printer": printer.to_dict()}), 200


@registers_bp.delete("/printers/<int:printer_id>")
@require_auth
@require_permission("MANAGE_REGISTER")
def delete_printer(printer_id: int):
    """Remove a printer from a register."""
    printer = db.session.query(Printer).filter_by(id=printer_id).first()
    if not printer:
        return jsonify({"error": "Printer not found"}), 404

    register = _get_register_in_org(printer.register_id)
    if not register:
        return jsonify({"error": "Register not found"}), 404
    scope_error = _ensure_store_scope(register.store_id)
    if scope_error:
        return scope_error

    register_service.append_ledger_event(
        store_id=register.store_id,
        event_type="device.printer_deleted",
        event_category="device",
        entity_type="printer",
        entity_id=printer.id,
        actor_user_id=g.current_user.id,
        register_id=register.id,
        note=f"Printer {printer.name} removed",
    )
    db.session.delete(printer)
    db.session.commit()
    return jsonify({"message": "Printer removed"}), 200
