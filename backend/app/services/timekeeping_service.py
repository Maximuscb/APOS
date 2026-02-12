# Overview: Service-layer operations for timekeeping; encapsulates business logic.

"""
Timekeeping Service (Shift-Based)

WHY: Employees clock in/out to open/close a shift. Shifts are immutable once closed.
Corrections are append-only records that require manager approval.
"""

from datetime import datetime

from ..extensions import db
from ..models import TimeClockEntry, TimeClockBreak, TimeClockCorrection, User
from .ledger_service import append_ledger_event
from . import communications_service
from app.time_utils import utcnow


class TimekeepingError(ValueError):
    """Raised for invalid timekeeping operations."""
    pass


def _get_open_entry(user_id: int) -> TimeClockEntry | None:
    return db.session.query(TimeClockEntry).filter_by(user_id=user_id, status="OPEN").first()


def clock_in(*, user_id: int, store_id: int, register_session_id: int | None = None, notes: str | None = None) -> TimeClockEntry:
    if _get_open_entry(user_id):
        raise TimekeepingError("User is already clocked in")

    entry = TimeClockEntry(
        user_id=user_id,
        store_id=store_id,
        clock_in_at=utcnow(),
        status="OPEN",
        register_session_id=register_session_id,
        notes=notes,
    )
    db.session.add(entry)
    db.session.flush()

    append_ledger_event(
        store_id=store_id,
        event_type="timeclock.clock_in",
        event_category="timekeeping",
        entity_type="time_clock_entry",
        entity_id=entry.id,
        actor_user_id=user_id,
        occurred_at=entry.clock_in_at,
    )

    db.session.commit()
    return entry


def clock_out(*, user_id: int) -> TimeClockEntry:
    entry = _get_open_entry(user_id)
    if not entry:
        raise TimekeepingError("User is not clocked in")

    user = db.session.query(User).filter_by(id=user_id).first()
    if user and user.org_id:
        pending = communications_service.pending_tasks_for_clockout(
            org_id=user.org_id,
            user_id=user_id,
            store_id=entry.store_id,
        )
        if pending:
            raise TimekeepingError(
                "You have pending tasks. Complete or defer assigned tasks before clocking out."
            )

    open_break = db.session.query(TimeClockBreak).filter_by(
        time_clock_entry_id=entry.id,
        end_at=None,
    ).first()
    if open_break:
        raise TimekeepingError("Cannot clock out while on break")

    entry.clock_out_at = utcnow()
    entry.status = "CLOSED"

    total_minutes = int((entry.clock_out_at - entry.clock_in_at).total_seconds() // 60)
    total_break = entry.total_break_minutes or 0
    entry.total_worked_minutes = max(total_minutes - total_break, 0)

    db.session.flush()

    append_ledger_event(
        store_id=entry.store_id,
        event_type="timeclock.clock_out",
        event_category="timekeeping",
        entity_type="time_clock_entry",
        entity_id=entry.id,
        actor_user_id=user_id,
        occurred_at=entry.clock_out_at,
    )

    db.session.commit()
    return entry


def start_break(*, user_id: int, break_type: str = "UNPAID") -> TimeClockBreak:
    entry = _get_open_entry(user_id)
    if not entry:
        raise TimekeepingError("User is not clocked in")

    open_break = db.session.query(TimeClockBreak).filter_by(
        time_clock_entry_id=entry.id,
        end_at=None,
    ).first()
    if open_break:
        raise TimekeepingError("Break already in progress")

    brk = TimeClockBreak(
        time_clock_entry_id=entry.id,
        start_at=utcnow(),
        break_type=break_type or "UNPAID",
    )
    db.session.add(brk)
    db.session.flush()

    append_ledger_event(
        store_id=entry.store_id,
        event_type="timeclock.break_start",
        event_category="timekeeping",
        entity_type="time_clock_break",
        entity_id=brk.id,
        actor_user_id=user_id,
        occurred_at=brk.start_at,
    )

    db.session.commit()
    return brk


def end_break(*, user_id: int) -> TimeClockBreak:
    entry = _get_open_entry(user_id)
    if not entry:
        raise TimekeepingError("User is not clocked in")

    brk = db.session.query(TimeClockBreak).filter_by(
        time_clock_entry_id=entry.id,
        end_at=None,
    ).first()
    if not brk:
        raise TimekeepingError("No active break")

    brk.end_at = utcnow()
    brk.duration_minutes = int((brk.end_at - brk.start_at).total_seconds() // 60)

    entry.total_break_minutes = (entry.total_break_minutes or 0) + brk.duration_minutes

    db.session.flush()

    append_ledger_event(
        store_id=entry.store_id,
        event_type="timeclock.break_end",
        event_category="timekeeping",
        entity_type="time_clock_break",
        entity_id=brk.id,
        actor_user_id=user_id,
        occurred_at=brk.end_at,
    )

    db.session.commit()
    return brk


def get_current_status(user_id: int) -> dict:
    entry = _get_open_entry(user_id)
    if not entry:
        return {"status": "CLOCKED_OUT", "entry": None, "on_break": False}

    open_break = db.session.query(TimeClockBreak).filter_by(
        time_clock_entry_id=entry.id,
        end_at=None,
    ).first()

    return {
        "status": "ON_BREAK" if open_break else "CLOCKED_IN",
        "entry": entry.to_dict(),
        "on_break": bool(open_break),
    }


def create_correction(
    *,
    entry_id: int,
    corrected_clock_in_at: datetime,
    corrected_clock_out_at: datetime | None,
    reason: str,
    submitted_by_user_id: int,
) -> TimeClockCorrection:
    entry = db.session.query(TimeClockEntry).filter_by(id=entry_id).first()
    if not entry:
        raise TimekeepingError("Time clock entry not found")

    if not reason:
        raise TimekeepingError("reason is required")

    correction = TimeClockCorrection(
        time_clock_entry_id=entry.id,
        original_clock_in_at=entry.clock_in_at,
        original_clock_out_at=entry.clock_out_at,
        corrected_clock_in_at=corrected_clock_in_at,
        corrected_clock_out_at=corrected_clock_out_at,
        reason=reason,
        submitted_by_user_id=submitted_by_user_id,
        status="PENDING",
    )
    db.session.add(correction)
    db.session.flush()

    append_ledger_event(
        store_id=entry.store_id,
        event_type="timeclock.correction_submitted",
        event_category="timekeeping",
        entity_type="time_clock_correction",
        entity_id=correction.id,
        actor_user_id=submitted_by_user_id,
        occurred_at=utcnow(),
        note=reason,
    )

    db.session.commit()
    return correction


def approve_correction(
    *,
    correction_id: int,
    approved_by_user_id: int,
    approval_notes: str | None = None,
) -> TimeClockCorrection:
    correction = db.session.query(TimeClockCorrection).filter_by(id=correction_id).first()
    if not correction:
        raise TimekeepingError("Time clock correction not found")

    if correction.status != "PENDING":
        raise TimekeepingError("Correction already processed")

    correction.status = "APPROVED"
    correction.approved_by_user_id = approved_by_user_id
    correction.approved_at = utcnow()
    correction.approval_notes = approval_notes

    db.session.flush()

    entry = correction.entry
    append_ledger_event(
        store_id=entry.store_id,
        event_type="timeclock.correction_approved",
        event_category="timekeeping",
        entity_type="time_clock_correction",
        entity_id=correction.id,
        actor_user_id=approved_by_user_id,
        occurred_at=utcnow(),
        note=approval_notes,
    )

    db.session.commit()
    return correction
