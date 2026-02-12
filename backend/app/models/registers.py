from __future__ import annotations

from ..extensions import db
from app.time_utils import to_utc_z

class Register(db.Model):
    """
    Physical POS register/terminal.

    WHY: Track which device processed each transaction. Essential for
    multi-register stores and cash accountability. Each register has
    its own cash drawer and shift tracking.

    DESIGN: Registers are persistent (not deleted when inactive).
    Each register can have multiple sessions (shifts) over time.
    """
    __tablename__ = "registers"
    __table_args__ = (
        db.UniqueConstraint("store_id", "register_number", name="uq_registers_store_number"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False, index=True)

    # Human-readable identifier (e.g., "REG-01", "FRONT", "DRIVE-THRU")
    register_number = db.Column(db.String(32), nullable=False)
    name = db.Column(db.String(128), nullable=False)  # Display name
    location = db.Column(db.String(128), nullable=True)  # Physical location in store

    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    version_id = db.Column(db.Integer, nullable=False, default=1)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now(), onupdate=db.func.now())

    organization = db.relationship("Organization", backref=db.backref("registers", lazy=True))
    store = db.relationship("Store", backref=db.backref("registers", lazy=True))
    __mapper_args__ = {"version_id_col": version_id}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "org_id": self.org_id,
            "store_id": self.store_id,
            "register_number": self.register_number,
            "name": self.name,
            "location": self.location,
            "is_active": self.is_active,
            "version_id": self.version_id,
            "created_at": to_utc_z(self.created_at),
            "updated_at": to_utc_z(self.updated_at),
        }

class RegisterSession(db.Model):
    """
    Register shift/session tracking.

    WHY: Cashier accountability. Each shift has opening/closing cash counts,
    tracks all transactions during shift, and provides variance reporting.

    LIFECYCLE:
    - OPEN: Shift is active, can process transactions
    - CLOSED: Shift ended, cash counted, variance calculated

    IMMUTABLE: Once closed, session cannot be reopened or modified.
    """
    __tablename__ = "register_sessions"
    __table_args__ = {"sqlite_autoincrement": True}

    id = db.Column(db.Integer, primary_key=True)
    register_id = db.Column(db.Integer, db.ForeignKey("registers.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    opened_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    # Session status
    status = db.Column(db.String(16), nullable=False, default="OPEN", index=True)  # OPEN, CLOSED

    # Cash tracking (all amounts in cents)
    opening_cash_cents = db.Column(db.Integer, nullable=False, default=0)
    closing_cash_cents = db.Column(db.Integer, nullable=True)  # Set when closing

    # Expected vs actual (calculated when closing)
    expected_cash_cents = db.Column(db.Integer, nullable=True)  # opening + cash sales - change
    variance_cents = db.Column(db.Integer, nullable=True)  # closing - expected

    # Timestamps
    opened_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now(), index=True)
    closed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Closing notes
    notes = db.Column(db.Text, nullable=True)
    version_id = db.Column(db.Integer, nullable=False, default=1)

    register = db.relationship("Register", backref=db.backref("sessions", lazy=True))
    user = db.relationship("User", foreign_keys=[user_id], backref=db.backref("register_sessions", lazy=True))
    opened_by = db.relationship("User", foreign_keys=[opened_by_user_id], backref=db.backref("register_sessions_opened", lazy=True))
    __mapper_args__ = {"version_id_col": version_id}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "register_id": self.register_id,
            "user_id": self.user_id,
            "opened_by_user_id": self.opened_by_user_id,
            "status": self.status,
            "opening_cash_cents": self.opening_cash_cents,
            "closing_cash_cents": self.closing_cash_cents,
            "expected_cash_cents": self.expected_cash_cents,
            "variance_cents": self.variance_cents,
            "opened_at": to_utc_z(self.opened_at),
            "closed_at": to_utc_z(self.closed_at) if self.closed_at else None,
            "notes": self.notes,
            "version_id": self.version_id,
        }

class CashDrawerEvent(db.Model):
    """
    Cash drawer open/close audit trail.

    WHY: Security and accountability. Every drawer open is logged with reason.
    Unusual patterns (too many opens, opens without sales) can indicate issues.

    EVENT TYPES:
    - SHIFT_OPEN: Drawer opened at shift start
    - SALE: Drawer opened for sale (automatic)
    - NO_SALE: Drawer opened without sale (requires manager approval)
    - CASH_DROP: Remove excess cash (requires manager approval)
    - SHIFT_CLOSE: Final count at shift end
    """
    __tablename__ = "cash_drawer_events"
    __table_args__ = (
        db.Index("ix_drawer_events_register_occurred", "register_id", "occurred_at"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    register_session_id = db.Column(db.Integer, db.ForeignKey("register_sessions.id"), nullable=False, index=True)
    register_id = db.Column(db.Integer, db.ForeignKey("registers.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    event_type = db.Column(db.String(32), nullable=False, index=True)

    # Amount involved (for CASH_DROP, etc.)
    amount_cents = db.Column(db.Integer, nullable=True)

    # Reference to related transaction
    sale_id = db.Column(db.Integer, db.ForeignKey("sales.id"), nullable=True)

    # Approval tracking (for NO_SALE, CASH_DROP)
    approved_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    reason = db.Column(db.String(255), nullable=True)

    occurred_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now(), index=True)

    register_session = db.relationship("RegisterSession", backref=db.backref("drawer_events", lazy=True))
    register = db.relationship("Register", backref=db.backref("drawer_events", lazy=True))
    user = db.relationship("User", foreign_keys=[user_id], backref=db.backref("drawer_events", lazy=True))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "register_session_id": self.register_session_id,
            "register_id": self.register_id,
            "user_id": self.user_id,
            "event_type": self.event_type,
            "amount_cents": self.amount_cents,
            "sale_id": self.sale_id,
            "approved_by_user_id": self.approved_by_user_id,
            "reason": self.reason,
            "occurred_at": to_utc_z(self.occurred_at),
        }


class CashDrawer(db.Model):
    """
    Physical cash drawer attached to a register.

    WHY: Registers may have different drawer configurations (single vs dual,
    different capacities). Modeling the drawer separately allows tracking
    hardware state and connection config independently from session logic.

    DESIGN: One drawer per register (enforced by unique constraint).
    Drawers persist across sessions and are not deleted when inactive.
    """
    __tablename__ = "cash_drawers"
    __table_args__ = (
        db.UniqueConstraint("register_id", name="uq_cash_drawers_register"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    register_id = db.Column(db.Integer, db.ForeignKey("registers.id"), nullable=False, index=True)

    # Hardware identification
    model = db.Column(db.String(128), nullable=True)  # e.g., "APG VB320-BL1616"
    serial_number = db.Column(db.String(128), nullable=True)

    # Connection info
    connection_type = db.Column(db.String(32), nullable=True)  # USB, SERIAL, NETWORK, PRINTER_DRIVEN
    connection_address = db.Column(db.String(255), nullable=True)  # COM port, IP, or null if printer-driven

    is_active = db.Column(db.Boolean, nullable=False, default=True)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now(), onupdate=db.func.now())

    register = db.relationship("Register", backref=db.backref("cash_drawer", uselist=False, lazy=True))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "register_id": self.register_id,
            "model": self.model,
            "serial_number": self.serial_number,
            "connection_type": self.connection_type,
            "connection_address": self.connection_address,
            "is_active": self.is_active,
            "created_at": to_utc_z(self.created_at),
            "updated_at": to_utc_z(self.updated_at),
        }


class Printer(db.Model):
    """
    Receipt/label printer attached to a register.

    WHY: Registers need printers for receipts, kitchen tickets, labels, etc.
    A register may have multiple printers (e.g., receipt + kitchen), each
    with its own connection and capability configuration.

    PRINTER TYPES:
    - RECEIPT: Customer-facing receipt printer
    - KITCHEN: Kitchen/prep area ticket printer
    - LABEL: Barcode/price label printer
    - REPORT: Back-office report printer
    """
    __tablename__ = "printers"
    __table_args__ = {"sqlite_autoincrement": True}

    id = db.Column(db.Integer, primary_key=True)
    register_id = db.Column(db.Integer, db.ForeignKey("registers.id"), nullable=False, index=True)

    name = db.Column(db.String(128), nullable=False)  # e.g., "Front Receipt Printer"
    printer_type = db.Column(db.String(32), nullable=False, index=True)  # RECEIPT, KITCHEN, LABEL, REPORT

    # Hardware identification
    model = db.Column(db.String(128), nullable=True)  # e.g., "Epson TM-T88VI"
    serial_number = db.Column(db.String(128), nullable=True)

    # Connection info
    connection_type = db.Column(db.String(32), nullable=True)  # USB, SERIAL, NETWORK, BLUETOOTH
    connection_address = db.Column(db.String(255), nullable=True)  # IP:port, COM port, BT address

    # Capabilities
    paper_width_mm = db.Column(db.Integer, nullable=True)  # 58, 80, etc.
    supports_cut = db.Column(db.Boolean, nullable=False, default=True)
    supports_cash_drawer = db.Column(db.Boolean, nullable=False, default=False)  # Can kick a connected drawer

    is_active = db.Column(db.Boolean, nullable=False, default=True)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now(), onupdate=db.func.now())

    register = db.relationship("Register", backref=db.backref("printers", lazy=True))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "register_id": self.register_id,
            "name": self.name,
            "printer_type": self.printer_type,
            "model": self.model,
            "serial_number": self.serial_number,
            "connection_type": self.connection_type,
            "connection_address": self.connection_address,
            "paper_width_mm": self.paper_width_mm,
            "supports_cut": self.supports_cut,
            "supports_cash_drawer": self.supports_cash_drawer,
            "is_active": self.is_active,
            "created_at": to_utc_z(self.created_at),
            "updated_at": to_utc_z(self.updated_at),
        }
