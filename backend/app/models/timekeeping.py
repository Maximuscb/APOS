from __future__ import annotations

from ..extensions import db
from app.time_utils import to_utc_z

class TimeClockEntry(db.Model):
    """
    Time clock entry for shift-based timekeeping.

    WHY: Employees need to clock in/out. Shifts are the unit of accountability.

    LIFECYCLE:
    - OPEN: Clock-in happened, shift in progress
    - CLOSED: Clock-out happened, shift complete

    IMMUTABLE: Once CLOSED, entry cannot be modified. Corrections are
    handled via append-only TimeClockCorrection records requiring manager approval.

    DESIGN:
    - Clock-in/out occurs in Register Mode
    - Timekeeping analytics/admin occurs in Operations Suite
    - Optional linking to RegisterSession for cross-reference
    """
    __tablename__ = "time_clock_entries"
    __table_args__ = (
        db.Index("ix_time_clock_user_status", "user_id", "status"),
        db.Index("ix_time_clock_store_date", "store_id", "clock_in_at"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False, index=True)

    # Clock times
    clock_in_at = db.Column(db.DateTime(timezone=True), nullable=False)
    clock_out_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Status: OPEN (clocked in), CLOSED (clocked out)
    status = db.Column(db.String(16), nullable=False, default="OPEN", index=True)

    # Total worked time in minutes (calculated on clock-out, excludes breaks)
    total_worked_minutes = db.Column(db.Integer, nullable=True)

    # Total break time in minutes (sum of breaks)
    total_break_minutes = db.Column(db.Integer, nullable=True, default=0)

    # Optional link to register session
    register_session_id = db.Column(db.Integer, db.ForeignKey("register_sessions.id"), nullable=True, index=True)

    # Notes
    notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    version_id = db.Column(db.Integer, nullable=False, default=1)

    # Relationships
    user = db.relationship("User", backref=db.backref("time_clock_entries", lazy=True))
    store = db.relationship("Store", backref=db.backref("time_clock_entries", lazy=True))
    register_session = db.relationship("RegisterSession", backref=db.backref("time_clock_entries", lazy=True))

    __mapper_args__ = {"version_id_col": version_id}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "store_id": self.store_id,
            "clock_in_at": to_utc_z(self.clock_in_at),
            "clock_out_at": to_utc_z(self.clock_out_at) if self.clock_out_at else None,
            "status": self.status,
            "total_worked_minutes": self.total_worked_minutes,
            "total_break_minutes": self.total_break_minutes,
            "register_session_id": self.register_session_id,
            "notes": self.notes,
            "created_at": to_utc_z(self.created_at),
            "version_id": self.version_id,
        }

class TimeClockBreak(db.Model):
    """
    Break periods within a time clock entry.

    WHY: Track break start/end times separately for accurate work time calculation.
    """
    __tablename__ = "time_clock_breaks"
    __table_args__ = (
        db.Index("ix_time_clock_breaks_entry", "time_clock_entry_id"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    time_clock_entry_id = db.Column(db.Integer, db.ForeignKey("time_clock_entries.id"), nullable=False, index=True)

    # Break times
    start_at = db.Column(db.DateTime(timezone=True), nullable=False)
    end_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Break type: PAID, UNPAID
    break_type = db.Column(db.String(16), nullable=False, default="UNPAID")

    # Duration in minutes (calculated on end)
    duration_minutes = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())

    # Relationships
    time_clock_entry = db.relationship("TimeClockEntry", backref=db.backref("breaks", lazy=True))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "time_clock_entry_id": self.time_clock_entry_id,
            "start_at": to_utc_z(self.start_at),
            "end_at": to_utc_z(self.end_at) if self.end_at else None,
            "break_type": self.break_type,
            "duration_minutes": self.duration_minutes,
            "created_at": to_utc_z(self.created_at),
        }

class TimeClockCorrection(db.Model):
    """
    Append-only correction records for time clock entries.

    WHY: Shifts are immutable once closed. Corrections must be documented
    and require manager approval for compliance.

    DESIGN:
    - Each correction is a separate record (append-only)
    - Manager approval required before correction is applied
    - Original entry remains unchanged; correction stores adjusted values
    - Multiple corrections can exist for same entry (only latest approved applies)
    """
    __tablename__ = "time_clock_corrections"
    __table_args__ = (
        db.Index("ix_time_clock_corrections_entry", "time_clock_entry_id"),
        db.Index("ix_time_clock_corrections_status", "status"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    time_clock_entry_id = db.Column(db.Integer, db.ForeignKey("time_clock_entries.id"), nullable=False, index=True)

    # Original values (for audit trail)
    original_clock_in_at = db.Column(db.DateTime(timezone=True), nullable=False)
    original_clock_out_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Corrected values
    corrected_clock_in_at = db.Column(db.DateTime(timezone=True), nullable=False)
    corrected_clock_out_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Reason for correction (required)
    reason = db.Column(db.Text, nullable=False)

    # Who submitted the correction
    submitted_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    submitted_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())

    # Approval status: PENDING, APPROVED, REJECTED
    status = db.Column(db.String(16), nullable=False, default="PENDING", index=True)

    # Manager approval
    approved_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    approval_notes = db.Column(db.Text, nullable=True)

    # Relationships
    time_clock_entry = db.relationship("TimeClockEntry", backref=db.backref("corrections", lazy=True))
    submitted_by = db.relationship("User", foreign_keys=[submitted_by_user_id])
    approved_by = db.relationship("User", foreign_keys=[approved_by_user_id])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "time_clock_entry_id": self.time_clock_entry_id,
            "original_clock_in_at": to_utc_z(self.original_clock_in_at),
            "original_clock_out_at": to_utc_z(self.original_clock_out_at) if self.original_clock_out_at else None,
            "corrected_clock_in_at": to_utc_z(self.corrected_clock_in_at),
            "corrected_clock_out_at": to_utc_z(self.corrected_clock_out_at) if self.corrected_clock_out_at else None,
            "reason": self.reason,
            "submitted_by_user_id": self.submitted_by_user_id,
            "submitted_at": to_utc_z(self.submitted_at),
            "status": self.status,
            "approved_by_user_id": self.approved_by_user_id,
            "approved_at": to_utc_z(self.approved_at) if self.approved_at else None,
            "approval_notes": self.approval_notes,
        }


# =============================================================================
# IMPORT STAGING (Enterprise-Scale Onboarding)
# =============================================================================
