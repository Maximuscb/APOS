"""
Phase 8: Register and Shift Management Service

WHY: Track POS terminals, cashier shifts, and cash accountability.
Essential for multi-register stores and audit trails.

DESIGN PRINCIPLES:
- One active session per register at a time
- Sessions are immutable once closed
- All cash drawer opens are logged
- Variance tracking (expected vs actual cash)
"""

from ..extensions import db
from ..models import Register, RegisterSession, CashDrawerEvent, Sale
from app.time_utils import utcnow
from sqlalchemy import and_
from .concurrency import lock_for_update
from .ledger_service import append_ledger_event


class RegisterError(Exception):
    """Raised for register operation errors."""
    pass


class ShiftError(Exception):
    """Raised for shift management errors."""
    pass


# =============================================================================
# REGISTER MANAGEMENT
# =============================================================================

def create_register(
    store_id: int,
    register_number: str,
    name: str,
    location: str | None = None,
    device_id: str | None = None
) -> Register:
    """
    Create a new POS register.

    WHY: Registers must be created before shifts can be opened.
    Each register represents a physical POS terminal.

    Args:
        store_id: Store this register belongs to
        register_number: Unique identifier (e.g., "REG-01", "FRONT")
        name: Display name
        location: Physical location in store
        device_id: Device identifier (MAC, serial, etc.)
    """
    # Check for duplicate register_number in store
    existing = db.session.query(Register).filter_by(
        store_id=store_id,
        register_number=register_number
    ).first()

    if existing:
        raise RegisterError(f"Register '{register_number}' already exists in this store")

    register = Register(
        store_id=store_id,
        register_number=register_number,
        name=name,
        location=location,
        device_id=device_id,
        is_active=True
    )

    db.session.add(register)
    db.session.commit()

    return register


def get_active_registers(store_id: int) -> list[Register]:
    """Get all active registers for a store."""
    return db.session.query(Register).filter_by(
        store_id=store_id,
        is_active=True
    ).order_by(Register.register_number).all()


def deactivate_register(register_id: int) -> Register:
    """
    Deactivate a register (soft delete).

    WHY: Registers are never deleted (preserve historical data).
    Inactive registers cannot open new shifts.
    """
    register = db.session.query(Register).get(register_id)

    if not register:
        raise RegisterError("Register not found")

    # Check for open sessions
    open_session = db.session.query(RegisterSession).filter_by(
        register_id=register_id,
        status="OPEN"
    ).first()

    if open_session:
        raise RegisterError("Cannot deactivate register with open session. Close shift first.")

    register.is_active = False
    db.session.commit()

    return register


# =============================================================================
# SHIFT MANAGEMENT
# =============================================================================

def open_shift(
    register_id: int,
    user_id: int,
    opening_cash_cents: int
) -> RegisterSession:
    """
    Open a new shift on a register.

    WHY: Each shift is a period of accountability for one cashier.
    Only one shift can be open per register at a time.

    Args:
        register_id: Register to open shift on
        user_id: Cashier opening the shift
        opening_cash_cents: Starting cash in drawer (in cents)

    Raises:
        ShiftError: If register has open shift or is inactive
    """
    # Check register exists and is active
    register = db.session.query(Register).get(register_id)

    if not register:
        raise ShiftError("Register not found")

    if not register.is_active:
        raise ShiftError("Cannot open shift on inactive register")

    # Check for existing open session
    existing_open = db.session.query(RegisterSession).filter_by(
        register_id=register_id,
        status="OPEN"
    ).first()

    if existing_open:
        raise ShiftError(f"Register already has open shift (session {existing_open.id})")

    # Create new session
    session = RegisterSession(
        register_id=register_id,
        user_id=user_id,
        opened_by_user_id=user_id,
        status="OPEN",
        opening_cash_cents=opening_cash_cents,
        expected_cash_cents=opening_cash_cents,  # Initially same as opening cash
        opened_at=utcnow()
    )

    db.session.add(session)
    db.session.commit()

    append_ledger_event(
        store_id=register.store_id,
        event_type="register.session_opened",
        event_category="register",
        entity_type="register_session",
        entity_id=session.id,
        actor_user_id=user_id,
        register_id=register_id,
        register_session_id=session.id,
        occurred_at=session.opened_at,
        note="Shift opened",
    )

    # Log drawer open event
    log_drawer_event(
        register_session_id=session.id,
        register_id=register_id,
        user_id=user_id,
        event_type="SHIFT_OPEN",
        amount_cents=opening_cash_cents,
        reason="Shift opened"
    )

    return session


def close_shift(
    session_id: int,
    closing_cash_cents: int,
    notes: str | None = None,
    *,
    current_user_id: int | None = None,
    manager_override: bool = False,
) -> RegisterSession:
    """
    Close a shift and calculate cash variance.

    WHY: Shift close calculates expected vs actual cash to detect
    discrepancies (theft, errors, etc.).

    IMMUTABLE: Once closed, session cannot be reopened or modified.

    Args:
        session_id: Session to close
        closing_cash_cents: Actual cash counted in drawer
        notes: Optional closing notes

    Returns:
        Closed session with variance calculated
    """
    session = lock_for_update(db.session.query(RegisterSession).filter_by(id=session_id)).first()

    if not session:
        raise ShiftError("Session not found")

    if session.status != "OPEN":
        raise ShiftError(f"Session already closed")

    if current_user_id is not None and session.user_id != current_user_id and not manager_override:
        raise ShiftError("Only the session owner can close this shift without manager approval")

    # Use expected_cash_cents from session (updated by sales and cash drops)
    expected_cash = session.expected_cash_cents or session.opening_cash_cents

    # Calculate variance
    variance = closing_cash_cents - expected_cash

    # Close session
    session.status = "CLOSED"
    session.closed_at = utcnow()
    session.closing_cash_cents = closing_cash_cents
    session.expected_cash_cents = expected_cash
    session.variance_cents = variance
    session.notes = notes

    # Log drawer close event
    log_drawer_event(
        register_session_id=session.id,
        register_id=session.register_id,
        user_id=current_user_id or session.user_id,
        event_type="SHIFT_CLOSE",
        amount_cents=closing_cash_cents,
        reason=f"Shift closed. Variance: {variance/100:.2f}",
        commit=False,
    )

    append_ledger_event(
        store_id=session.register.store_id,
        event_type="register.session_closed",
        event_category="register",
        entity_type="register_session",
        entity_id=session.id,
        actor_user_id=current_user_id or session.user_id,
        register_id=session.register_id,
        register_session_id=session.id,
        occurred_at=session.closed_at,
        note=notes,
    )

    db.session.commit()

    return session


def get_open_session(register_id: int) -> RegisterSession | None:
    """Get the currently open session for a register, if any."""
    return db.session.query(RegisterSession).filter_by(
        register_id=register_id,
        status="OPEN"
    ).first()


def get_user_open_sessions(user_id: int) -> list[RegisterSession]:
    """Get all open sessions for a user (should normally be 0 or 1)."""
    return db.session.query(RegisterSession).filter_by(
        user_id=user_id,
        status="OPEN"
    ).all()


# =============================================================================
# CASH DRAWER EVENTS
# =============================================================================

def log_drawer_event(
    register_session_id: int,
    register_id: int,
    user_id: int,
    event_type: str,
    amount_cents: int | None = None,
    sale_id: int | None = None,
    approved_by_user_id: int | None = None,
    reason: str | None = None,
    *,
    commit: bool = True,
) -> CashDrawerEvent:
    """
    Log cash drawer event.

    WHY: Audit trail for all drawer opens. Helps detect suspicious patterns.

    EVENT TYPES:
    - SHIFT_OPEN: Drawer opened at shift start
    - SALE: Drawer opened for sale (automatic)
    - NO_SALE: Drawer opened without sale (manager approval required)
    - CASH_DROP: Remove excess cash (manager approval required)
    - SHIFT_CLOSE: Final count at shift end
    """
    event = CashDrawerEvent(
        register_session_id=register_session_id,
        register_id=register_id,
        user_id=user_id,
        event_type=event_type,
        amount_cents=amount_cents,
        sale_id=sale_id,
        approved_by_user_id=approved_by_user_id,
        reason=reason,
        occurred_at=utcnow()
    )

    db.session.add(event)
    db.session.flush()

    register = db.session.query(Register).get(register_id)
    if not register:
        raise ShiftError("Register not found")
    store_id = register.store_id

    append_ledger_event(
        store_id=store_id,
        event_type=f"cash_drawer.{event_type.lower()}",
        event_category="cash_drawer",
        entity_type="cash_drawer_event",
        entity_id=event.id,
        actor_user_id=user_id,
        register_id=register_id,
        register_session_id=register_session_id,
        cash_drawer_event_id=event.id,
        occurred_at=event.occurred_at,
        note=reason,
        payload=f"amount_cents={amount_cents}" if amount_cents is not None else None,
    )

    if commit:
        db.session.commit()
    else:
        db.session.flush()

    return event


def open_drawer_no_sale(
    register_session_id: int,
    register_id: int,
    user_id: int,
    approved_by_user_id: int,
    reason: str
) -> CashDrawerEvent:
    """
    Open cash drawer without a sale (requires manager approval).

    WHY: Drawer opens without sales are suspicious and must be logged
    with manager approval and reason.

    Common reasons: Make change, give refund, fix error, etc.
    """
    # Verify session is open
    session = db.session.query(RegisterSession).get(register_session_id)

    if not session or session.status != "OPEN":
        raise ShiftError("Session not open")

    return log_drawer_event(
        register_session_id=register_session_id,
        register_id=register_id,
        user_id=user_id,
        event_type="NO_SALE",
        approved_by_user_id=approved_by_user_id,
        reason=reason
    )


def cash_drop(
    register_session_id: int,
    register_id: int,
    user_id: int,
    amount_cents: int,
    approved_by_user_id: int,
    reason: str | None = None
) -> CashDrawerEvent:
    """
    Remove excess cash from drawer (requires manager approval).

    WHY: Security best practice. Remove large bills to safe regularly.
    Must be logged with manager approval.

    IMPORTANT: Reduces expected_cash_cents in session by the drop amount.
    """
    session = lock_for_update(db.session.query(RegisterSession).filter_by(id=register_session_id)).first()

    if not session or session.status != "OPEN":
        raise ShiftError("Session not open")

    if amount_cents <= 0:
        raise ValueError("Cash drop amount must be positive")

    # Reduce expected cash by drop amount
    session.expected_cash_cents = (session.expected_cash_cents or session.opening_cash_cents) - amount_cents

    event = log_drawer_event(
        register_session_id=register_session_id,
        register_id=register_id,
        user_id=user_id,
        event_type="CASH_DROP",
        amount_cents=amount_cents,
        approved_by_user_id=approved_by_user_id,
        reason=reason or f"Cash drop: ${amount_cents/100:.2f}",
        commit=False,
    )

    db.session.commit()

    return event


# =============================================================================
# REPORTING
# =============================================================================

def get_session_sales(session_id: int) -> list[Sale]:
    """Get all sales for a session."""
    return db.session.query(Sale).filter_by(
        register_session_id=session_id
    ).order_by(Sale.created_at).all()


def get_session_drawer_events(session_id: int) -> list[CashDrawerEvent]:
    """Get all drawer events for a session."""
    return db.session.query(CashDrawerEvent).filter_by(
        register_session_id=session_id
    ).order_by(CashDrawerEvent.occurred_at).all()


def get_shift_summary(session_id: int) -> dict:
    """
    Get comprehensive shift summary.

    Returns:
        - Session details
        - Sales count and total
        - Cash drawer event count
        - Variance information
    """
    session = db.session.query(RegisterSession).get(session_id)

    if not session:
        raise ShiftError("Session not found")

    sales = get_session_sales(session_id)
    drawer_events = get_session_drawer_events(session_id)

    return {
        "session": session.to_dict(),
        "sales_count": len(sales),
        "drawer_events_count": len(drawer_events),
        "is_closed": session.status == "CLOSED",
        "variance_cents": session.variance_cents,
    }
