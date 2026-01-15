# backend/app/models.py
from __future__ import annotations
from .extensions import db
from app.time_utils import to_utc_z


class Store(db.Model):
    """
    Phase 1.2: Minimal model to prove migrations work.
    This will later support multi-store deployments.
    """
    __tablename__ = "stores"
    __table_args__ = {"sqlite_autoincrement": True}

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.func.now(),
    )

    def __repr__(self) -> str:
        return f"<Store id={self.id} name={self.name!r}>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "created_at": to_utc_z(self.created_at),
        }

class Product(db.Model):
    __tablename__ = "products"
    __table_args__ = (
        db.UniqueConstraint("store_id", "sku", name="uq_products_store_sku"),
        db.Index("ix_products_store_name", "store_id", "name"),
        {"sqlite_autoincrement": True},
    )



    id = db.Column(db.Integer, primary_key=True)

    # Multi-store ready (even if you only have one store today)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False, index=True)

    sku = db.Column(db.String(64), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)

    # Authoritative storage in cents (frontend may only format for display)
    price_cents = db.Column(db.Integer, nullable=True)

    is_active = db.Column(db.Boolean, nullable=False, default=True)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.func.now(),
        onupdate=db.func.now(),
    )

    store = db.relationship("Store", backref=db.backref("products", lazy=True))

    def __repr__(self) -> str:
        return f"<Product id={self.id} sku={self.sku!r} name={self.name!r} store_id={self.store_id}>"
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "store_id": self.store_id,
            "sku": self.sku,
            "name": self.name,
            "description": self.description,
            "price_cents": self.price_cents,
            "is_active": self.is_active,
            "created_at": to_utc_z(self.created_at),
            "updated_at": to_utc_z(self.updated_at),
        }

class InventoryTransaction(db.Model):
    __tablename__ = "inventory_transactions"
    
    id = db.Column(db.Integer, primary_key=True)

    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)

    # Phase 3: "RECEIVE" | "ADJUST"
    type = db.Column(db.String(32), nullable=False, index=True)

    # Positive for RECEIVE, +/- for ADJUST
    quantity_delta = db.Column(db.Integer, nullable=False)

    # Required for RECEIVE; must be NULL for ADJUST (enforced centrally, not here)
    unit_cost_cents = db.Column(db.Integer, nullable=True)

    note = db.Column(db.String(255), nullable=True)

    # “As-of” timestamp for historical queries
    occurred_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.func.now(),
        index=True,
    )

    # Row creation timestamp
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.func.now(),
    )

    # Phase 4: SALE idempotency + traceability
    sale_id = db.Column(db.String(64), nullable=True, index=True)
    sale_line_id = db.Column(db.String(64), nullable=True)

    # Phase 4: immutable cost snapshot at sale time (COGS)
    unit_cost_cents_at_sale = db.Column(db.Integer, nullable=True)
    cogs_cents = db.Column(db.Integer, nullable=True)

    # ==================================================================================
    # Phase 5: Document Lifecycle (Draft → Approved → Posted)
    # ==================================================================================
    # WHY: Prevents accidental posting, enables review workflows, and allows
    # AI-generated drafts later without risk. Only POSTED transactions affect
    # inventory calculations (on-hand qty, WAC, COGS).
    #
    # State transition rules (see lifecycle_service.py):
    # - DRAFT → APPROVED (requires approval authority)
    # - APPROVED → POSTED (finalizes; irreversible; affects ledger)
    # - Cannot skip states (DRAFT → POSTED is forbidden)
    # - Cannot reverse transitions (POSTED → APPROVED is forbidden)
    #
    # Default: POSTED (for backwards compatibility with existing transactions)
    # New transactions default to DRAFT unless explicitly posted.
    # ==================================================================================

    status = db.Column(
        db.String(16),
        nullable=False,
        default="POSTED",  # Backwards compatibility: existing data and old code auto-posts
        index=True,  # Frequently filtered in queries
    )

    # Approval audit trail (nullable until User model exists)
    # approved_by_user_id will reference users.id once auth is implemented
    approved_by_user_id = db.Column(db.Integer, nullable=True)
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Posting audit trail (nullable until User model exists)
    # posted_by_user_id will reference users.id once auth is implemented
    posted_by_user_id = db.Column(db.Integer, nullable=True)
    posted_at = db.Column(db.DateTime(timezone=True), nullable=True)


    __table_args__ = (
        db.Index("ix_invtx_store_product_occurred", "store_id", "product_id", "occurred_at"),
        db.Index("ix_invtx_store_product_type_occurred", "store_id", "product_id", "type", "occurred_at"),
        db.UniqueConstraint("store_id", "sale_id", "sale_line_id", name="uq_invtx_store_sale_line"),
        {"sqlite_autoincrement": True},   # MUST be last
    )



    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "store_id": self.store_id,
            "product_id": self.product_id,
            "type": self.type,
            "quantity_delta": self.quantity_delta,
            "unit_cost_cents": self.unit_cost_cents,
            "note": self.note,
            "occurred_at": to_utc_z(self.occurred_at),
            "created_at": to_utc_z(self.created_at),
            "sale_id": self.sale_id,
            "sale_line_id": self.sale_line_id,
            "unit_cost_cents_at_sale": self.unit_cost_cents_at_sale,
            "cogs_cents": self.cogs_cents,
            # Phase 5: Lifecycle fields
            "status": self.status,
            "approved_by_user_id": self.approved_by_user_id,
            "approved_at": to_utc_z(self.approved_at) if self.approved_at else None,
            "posted_by_user_id": self.posted_by_user_id,
            "posted_at": to_utc_z(self.posted_at) if self.posted_at else None,
        }

class ProductIdentifier(db.Model):
    """
    Phase 2: First-class identifier system for products.

    WHY: Prevents silent mis-scans and barcode chaos. Identifiers are NOT just
    strings on products - they have type, scope, and uniqueness rules.

    Types:
    - SKU: Store-level unique identifier (internal)
    - UPC: Universal Product Code (scannable, globally unique)
    - ALT_BARCODE: Alternative barcode (e.g., case barcode)
    - VENDOR_CODE: Supplier's product code (scoped to vendor)

    Uniqueness rules:
    - SKU/UPC: Globally unique across organization
    - VENDOR_CODE: Unique within vendor scope
    """
    __tablename__ = "product_identifiers"
    __table_args__ = (
        db.UniqueConstraint("type", "value", name="uq_identifier_type_value"),
        db.Index("ix_identifier_value", "value"),
        db.Index("ix_identifier_product", "product_id"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)

    # Identifier type: SKU, UPC, ALT_BARCODE, VENDOR_CODE
    type = db.Column(db.String(32), nullable=False, index=True)

    # Normalized value (uppercase, no spaces)
    value = db.Column(db.String(128), nullable=False)

    # Optional vendor scope for VENDOR_CODE type
    vendor_id = db.Column(db.Integer, nullable=True)

    is_primary = db.Column(db.Boolean, nullable=False, default=False)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())

    product = db.relationship("Product", backref=db.backref("identifiers", lazy=True))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "product_id": self.product_id,
            "type": self.type,
            "value": self.value,
            "vendor_id": self.vendor_id,
            "is_primary": self.is_primary,
            "created_at": to_utc_z(self.created_at),
        }


class Sale(db.Model):
    """
    Phase 3: Sale document model (document-first, not inventory-first).

    WHY: Sales are documents with lifecycle, not just inventory decrements.
    Enables cart editing, suspend/recall, quotes/estimates.
    """
    __tablename__ = "sales"
    __table_args__ = (
        db.UniqueConstraint("store_id", "document_number", name="uq_sales_store_docnum"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False, index=True)

    # Human-readable document number (e.g., "S-001234")
    document_number = db.Column(db.String(64), nullable=False)

    # Lifecycle status
    status = db.Column(db.String(16), nullable=False, default="DRAFT", index=True)

    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # User attribution (nullable until Phase 4 complete)
    created_by_user_id = db.Column(db.Integer, nullable=True)

    # Phase 8: Register tracking
    register_id = db.Column(db.Integer, db.ForeignKey("registers.id"), nullable=True, index=True)
    register_session_id = db.Column(db.Integer, db.ForeignKey("register_sessions.id"), nullable=True, index=True)

    # Phase 9: Payment tracking (all amounts in cents)
    payment_status = db.Column(db.String(16), nullable=False, default="UNPAID", index=True)  # UNPAID, PARTIAL, PAID, OVERPAID
    total_due_cents = db.Column(db.Integer, nullable=True)  # Calculated from sale lines
    total_paid_cents = db.Column(db.Integer, nullable=False, default=0)  # Sum of completed payments
    change_due_cents = db.Column(db.Integer, nullable=False, default=0)  # For overpayment

    store = db.relationship("Store", backref=db.backref("sales", lazy=True))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "store_id": self.store_id,
            "document_number": self.document_number,
            "status": self.status,
            "created_at": to_utc_z(self.created_at),
            "completed_at": to_utc_z(self.completed_at) if self.completed_at else None,
            "created_by_user_id": self.created_by_user_id,
            "register_id": self.register_id,
            "register_session_id": self.register_session_id,
            "payment_status": self.payment_status,
            "total_due_cents": self.total_due_cents,
            "total_paid_cents": self.total_paid_cents,
            "change_due_cents": self.change_due_cents,
        }


class SaleLine(db.Model):
    """Phase 3: Individual line items on a sale document."""
    __tablename__ = "sale_lines"
    __table_args__ = {"sqlite_autoincrement": True}

    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("sales.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)

    quantity = db.Column(db.Integer, nullable=False)
    unit_price_cents = db.Column(db.Integer, nullable=False)
    line_total_cents = db.Column(db.Integer, nullable=False)

    # Links to inventory transaction (when posted)
    inventory_transaction_id = db.Column(db.Integer, db.ForeignKey("inventory_transactions.id"), nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())

    sale = db.relationship("Sale", backref=db.backref("lines", lazy=True))
    product = db.relationship("Product")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "sale_id": self.sale_id,
            "product_id": self.product_id,
            "quantity": self.quantity,
            "unit_price_cents": self.unit_price_cents,
            "line_total_cents": self.line_total_cents,
            "inventory_transaction_id": self.inventory_transaction_id,
            "created_at": to_utc_z(self.created_at),
        }


class Register(db.Model):
    """
    Phase 8: Physical POS register/terminal.

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
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False, index=True)

    # Human-readable identifier (e.g., "REG-01", "FRONT", "DRIVE-THRU")
    register_number = db.Column(db.String(32), nullable=False)
    name = db.Column(db.String(128), nullable=False)  # Display name
    location = db.Column(db.String(128), nullable=True)  # Physical location in store

    # Device identification
    device_id = db.Column(db.String(128), nullable=True)  # MAC address, serial, etc.

    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now(), onupdate=db.func.now())

    store = db.relationship("Store", backref=db.backref("registers", lazy=True))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "store_id": self.store_id,
            "register_number": self.register_number,
            "name": self.name,
            "location": self.location,
            "device_id": self.device_id,
            "is_active": self.is_active,
            "created_at": to_utc_z(self.created_at),
            "updated_at": to_utc_z(self.updated_at),
        }


class RegisterSession(db.Model):
    """
    Phase 8: Register shift/session tracking.

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

    register = db.relationship("Register", backref=db.backref("sessions", lazy=True))
    user = db.relationship("User", backref=db.backref("register_sessions", lazy=True))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "register_id": self.register_id,
            "user_id": self.user_id,
            "status": self.status,
            "opening_cash_cents": self.opening_cash_cents,
            "closing_cash_cents": self.closing_cash_cents,
            "expected_cash_cents": self.expected_cash_cents,
            "variance_cents": self.variance_cents,
            "opened_at": to_utc_z(self.opened_at),
            "closed_at": to_utc_z(self.closed_at) if self.closed_at else None,
            "notes": self.notes,
        }


class CashDrawerEvent(db.Model):
    """
    Phase 8: Cash drawer open/close audit trail.

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


class Payment(db.Model):
    """
    Phase 9: Payment record for sales.

    WHY: Track how customers pay for sales. Supports multiple payment types
    (cash, card, check, etc.) and split payments.

    TENDER TYPES:
    - CASH: Physical currency
    - CARD: Credit/debit card
    - CHECK: Paper check
    - GIFT_CARD: Store gift card
    - STORE_CREDIT: Store credit/account

    DESIGN: Payments are separate from sales to support:
    - Split payments (multiple payments for one sale)
    - Partial payments (layaway, deposits)
    - Payment voids (mistake correction)
    - Change calculation (cash over-tender)
    """
    __tablename__ = "payments"
    __table_args__ = {"sqlite_autoincrement": True}

    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("sales.id"), nullable=False, index=True)

    # Tender type (what form of payment)
    tender_type = db.Column(db.String(32), nullable=False, index=True)

    # Amount tendered (in cents)
    amount_cents = db.Column(db.Integer, nullable=False)

    # Payment status
    status = db.Column(db.String(16), nullable=False, default="COMPLETED", index=True)  # COMPLETED, VOIDED

    # Reference info (card auth code, check number, etc.)
    reference_number = db.Column(db.String(128), nullable=True)

    # Change given (for cash over-tender)
    change_cents = db.Column(db.Integer, nullable=True, default=0)

    # Attribution
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    voided_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now(), index=True)
    voided_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Void reason
    void_reason = db.Column(db.String(255), nullable=True)

    # Phase 8: Register tracking
    register_id = db.Column(db.Integer, db.ForeignKey("registers.id"), nullable=True, index=True)
    register_session_id = db.Column(db.Integer, db.ForeignKey("register_sessions.id"), nullable=True, index=True)

    sale = db.relationship("Sale", backref=db.backref("payments", lazy=True))
    created_by = db.relationship("User", foreign_keys=[created_by_user_id], backref=db.backref("payments_created", lazy=True))
    voided_by = db.relationship("User", foreign_keys=[voided_by_user_id], backref=db.backref("payments_voided", lazy=True))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "sale_id": self.sale_id,
            "tender_type": self.tender_type,
            "amount_cents": self.amount_cents,
            "status": self.status,
            "reference_number": self.reference_number,
            "change_cents": self.change_cents,
            "created_by_user_id": self.created_by_user_id,
            "voided_by_user_id": self.voided_by_user_id,
            "created_at": to_utc_z(self.created_at),
            "voided_at": to_utc_z(self.voided_at) if self.voided_at else None,
            "void_reason": self.void_reason,
            "register_id": self.register_id,
            "register_session_id": self.register_session_id,
        }


class PaymentTransaction(db.Model):
    """
    Phase 9: Append-only ledger of payment events.

    WHY: Immutable audit trail for all payment activity.
    Every payment creation, void, or refund is logged here.

    TRANSACTION TYPES:
    - PAYMENT: New payment created
    - VOID: Payment voided (reversal)
    - REFUND: Money returned to customer

    IMMUTABLE: Records are never updated or deleted.
    """
    __tablename__ = "payment_transactions"
    __table_args__ = (
        db.Index("ix_payment_txns_occurred", "occurred_at"),
        db.Index("ix_payment_txns_sale_occurred", "sale_id", "occurred_at"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, db.ForeignKey("payments.id"), nullable=False, index=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("sales.id"), nullable=False, index=True)

    # Transaction type
    transaction_type = db.Column(db.String(16), nullable=False, index=True)  # PAYMENT, VOID, REFUND

    # Amount of this transaction (in cents)
    # Positive for payments, negative for voids/refunds
    amount_cents = db.Column(db.Integer, nullable=False)

    # Tender type (copied from Payment for reporting)
    tender_type = db.Column(db.String(32), nullable=False, index=True)

    # Attribution
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    # Reason for voids/refunds
    reason = db.Column(db.String(255), nullable=True)

    # Timestamp (immutable)
    occurred_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now(), index=True)

    # Phase 8: Register tracking
    register_id = db.Column(db.Integer, db.ForeignKey("registers.id"), nullable=True, index=True)
    register_session_id = db.Column(db.Integer, db.ForeignKey("register_sessions.id"), nullable=True, index=True)

    payment = db.relationship("Payment", backref=db.backref("transactions", lazy=True))
    sale = db.relationship("Sale", backref=db.backref("payment_transactions", lazy=True))
    user = db.relationship("User", backref=db.backref("payment_transactions", lazy=True))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "payment_id": self.payment_id,
            "sale_id": self.sale_id,
            "transaction_type": self.transaction_type,
            "amount_cents": self.amount_cents,
            "tender_type": self.tender_type,
            "user_id": self.user_id,
            "reason": self.reason,
            "occurred_at": to_utc_z(self.occurred_at),
            "register_id": self.register_id,
            "register_session_id": self.register_session_id,
        }


class Return(db.Model):
    """
    Phase 10: Product return document.

    WHY: Retail returns are common and require careful COGS handling.
    Must credit the ORIGINAL sale cost, not current WAC, for accurate accounting.

    LIFECYCLE:
    1. PENDING: Return created, awaiting manager approval
    2. APPROVED: Manager approved, ready to process
    3. COMPLETED: Return processed, inventory restored, refund issued
    4. REJECTED: Manager rejected return request

    DESIGN PRINCIPLES:
    - Returns reference original Sale for traceability
    - ReturnLines reference original SaleLines to track which items
    - COGS reversal uses original sale cost (from inventory_transaction)
    - Restocking fee optional (deducted from refund)
    - Manager approval required before processing
    """
    __tablename__ = "returns"
    __table_args__ = (
        db.UniqueConstraint("store_id", "document_number", name="uq_returns_store_docnum"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False, index=True)

    # Human-readable document number (e.g., "R-001234")
    document_number = db.Column(db.String(64), nullable=False)

    # Reference to original sale
    original_sale_id = db.Column(db.Integer, db.ForeignKey("sales.id"), nullable=False, index=True)

    # Return status
    status = db.Column(db.String(16), nullable=False, default="PENDING", index=True)  # PENDING, APPROVED, COMPLETED, REJECTED

    # Return reason (customer explanation)
    reason = db.Column(db.Text, nullable=True)

    # Restocking fee (in cents, deducted from refund)
    restocking_fee_cents = db.Column(db.Integer, nullable=False, default=0)

    # Refund amount (calculated from returned items minus restocking fee)
    refund_amount_cents = db.Column(db.Integer, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now(), index=True)
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    rejected_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # User attribution
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    approved_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    completed_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    rejected_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    # Rejection reason (manager explanation)
    rejection_reason = db.Column(db.Text, nullable=True)

    # Phase 8: Register tracking
    register_id = db.Column(db.Integer, db.ForeignKey("registers.id"), nullable=True, index=True)
    register_session_id = db.Column(db.Integer, db.ForeignKey("register_sessions.id"), nullable=True, index=True)

    store = db.relationship("Store", backref=db.backref("returns", lazy=True))
    original_sale = db.relationship("Sale", backref=db.backref("returns", lazy=True))
    created_by = db.relationship("User", foreign_keys=[created_by_user_id], backref=db.backref("returns_created", lazy=True))
    approved_by = db.relationship("User", foreign_keys=[approved_by_user_id], backref=db.backref("returns_approved", lazy=True))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "store_id": self.store_id,
            "document_number": self.document_number,
            "original_sale_id": self.original_sale_id,
            "status": self.status,
            "reason": self.reason,
            "restocking_fee_cents": self.restocking_fee_cents,
            "refund_amount_cents": self.refund_amount_cents,
            "created_at": to_utc_z(self.created_at),
            "approved_at": to_utc_z(self.approved_at) if self.approved_at else None,
            "completed_at": to_utc_z(self.completed_at) if self.completed_at else None,
            "rejected_at": to_utc_z(self.rejected_at) if self.rejected_at else None,
            "created_by_user_id": self.created_by_user_id,
            "approved_by_user_id": self.approved_by_user_id,
            "completed_by_user_id": self.completed_by_user_id,
            "rejected_by_user_id": self.rejected_by_user_id,
            "rejection_reason": self.rejection_reason,
            "register_id": self.register_id,
            "register_session_id": self.register_session_id,
        }


class ReturnLine(db.Model):
    """
    Phase 10: Individual line items on a return document.

    WHY: Track which specific items from the original sale are being returned.
    Links to original SaleLine for COGS reversal.

    CRITICAL: For COGS reversal, we credit the ORIGINAL sale cost
    (from the inventory_transaction created when the sale was posted),
    NOT the current weighted average cost.
    """
    __tablename__ = "return_lines"
    __table_args__ = {"sqlite_autoincrement": True}

    id = db.Column(db.Integer, primary_key=True)
    return_id = db.Column(db.Integer, db.ForeignKey("returns.id"), nullable=False, index=True)

    # Reference to original sale line being returned
    original_sale_line_id = db.Column(db.Integer, db.ForeignKey("sale_lines.id"), nullable=False, index=True)

    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)

    # Quantity being returned (must be <= original quantity sold)
    quantity = db.Column(db.Integer, nullable=False)

    # Original unit price from sale (for refund calculation)
    unit_price_cents = db.Column(db.Integer, nullable=False)

    # Refund for this line (quantity * unit_price_cents)
    line_refund_cents = db.Column(db.Integer, nullable=False)

    # CRITICAL: Original COGS from sale transaction (for reversal)
    # This comes from the inventory_transaction created when sale was posted
    original_unit_cost_cents = db.Column(db.Integer, nullable=True)
    original_cogs_cents = db.Column(db.Integer, nullable=True)

    # Links to inventory transaction (when return is completed)
    inventory_transaction_id = db.Column(db.Integer, db.ForeignKey("inventory_transactions.id"), nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())

    return_doc = db.relationship("Return", backref=db.backref("lines", lazy=True))
    original_sale_line = db.relationship("SaleLine", backref=db.backref("return_lines", lazy=True))
    product = db.relationship("Product")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "return_id": self.return_id,
            "original_sale_line_id": self.original_sale_line_id,
            "product_id": self.product_id,
            "quantity": self.quantity,
            "unit_price_cents": self.unit_price_cents,
            "line_refund_cents": self.line_refund_cents,
            "original_unit_cost_cents": self.original_unit_cost_cents,
            "original_cogs_cents": self.original_cogs_cents,
            "inventory_transaction_id": self.inventory_transaction_id,
            "created_at": to_utc_z(self.created_at),
        }


class User(db.Model):
    """
    Phase 4: User accounts for authentication and attribution.

    WHY: Every action must be attributable. No shared logins.
    """
    __tablename__ = "users"
    __table_args__ = {"sqlite_autoincrement": True}

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(64), nullable=False, unique=True, index=True)
    email = db.Column(db.String(255), nullable=False, unique=True)

    # Bcrypt hashed password
    password_hash = db.Column(db.String(255), nullable=False)

    # Store association (nullable for org-level users)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=True)

    is_active = db.Column(db.Boolean, nullable=False, default=True)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True)

    store = db.relationship("Store", backref=db.backref("users", lazy=True))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "store_id": self.store_id,
            "is_active": self.is_active,
            "created_at": to_utc_z(self.created_at),
            "last_login_at": to_utc_z(self.last_login_at) if self.last_login_at else None,
        }


class Role(db.Model):
    """Phase 4: Role-based permissions."""
    __tablename__ = "roles"
    __table_args__ = {"sqlite_autoincrement": True}

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": to_utc_z(self.created_at),
        }


class UserRole(db.Model):
    """Phase 4: User-Role association."""
    __tablename__ = "user_roles"
    __table_args__ = (
        db.UniqueConstraint("user_id", "role_id", name="uq_user_roles"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False, index=True)

    assigned_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())

    user = db.relationship("User", backref=db.backref("user_roles", lazy=True))
    role = db.relationship("Role", backref=db.backref("user_roles", lazy=True))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "role_id": self.role_id,
            "assigned_at": to_utc_z(self.assigned_at),
        }


class Permission(db.Model):
    """
    Phase 7: Permissions for role-based access control.

    WHY: Roles need enforceable permissions. This table defines what actions exist.
    RolePermission links these to roles.

    DESIGN: Permissions are identified by unique codes (e.g., "APPROVE_ADJUSTMENTS").
    Categories group related permissions for UI display.
    """
    __tablename__ = "permissions"
    __table_args__ = {"sqlite_autoincrement": True}

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64), nullable=False, unique=True, index=True)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(64), nullable=False, index=True)  # INVENTORY, SALES, USERS, SYSTEM

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "created_at": to_utc_z(self.created_at),
        }


class RolePermission(db.Model):
    """
    Phase 7: Role-Permission association.

    WHY: Defines which roles have which permissions.
    Many-to-many relationship between roles and permissions.
    """
    __tablename__ = "role_permissions"
    __table_args__ = (
        db.UniqueConstraint("role_id", "permission_id", name="uq_role_permissions"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False, index=True)
    permission_id = db.Column(db.Integer, db.ForeignKey("permissions.id"), nullable=False, index=True)

    granted_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())

    role = db.relationship("Role", backref=db.backref("role_permissions", lazy=True))
    permission = db.relationship("Permission", backref=db.backref("role_permissions", lazy=True))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "role_id": self.role_id,
            "permission_id": self.permission_id,
            "granted_at": to_utc_z(self.granted_at),
        }


class SecurityEvent(db.Model):
    """
    Phase 7: Security event audit log.

    WHY: Track permission checks, failed attempts, and security-relevant actions.
    Critical for detecting unauthorized access attempts and compliance.

    IMMUTABLE: Never update or delete. Append-only for audit integrity.
    """
    __tablename__ = "security_events"
    __table_args__ = (
        db.Index("ix_security_events_user_type", "user_id", "event_type"),
        db.Index("ix_security_events_occurred", "occurred_at"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)  # Nullable for anonymous

    # Event classification
    event_type = db.Column(db.String(64), nullable=False, index=True)  # PERMISSION_DENIED, PERMISSION_GRANTED, LOGIN_FAILED, etc.
    resource = db.Column(db.String(128), nullable=True)  # e.g., "/api/inventory/adjust"
    action = db.Column(db.String(64), nullable=True)     # e.g., "POST", "APPROVE_ADJUSTMENT"

    # Event details
    success = db.Column(db.Boolean, nullable=False, index=True)
    reason = db.Column(db.Text, nullable=True)  # e.g., "Missing permission: APPROVE_ADJUSTMENTS"

    # Client context
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(512), nullable=True)

    occurred_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now(), index=True)

    user = db.relationship("User", backref=db.backref("security_events", lazy=True))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "event_type": self.event_type,
            "resource": self.resource,
            "action": self.action,
            "success": self.success,
            "reason": self.reason,
            "ip_address": self.ip_address,
            "occurred_at": to_utc_z(self.occurred_at),
        }


class SessionToken(db.Model):
    """
    Phase 6: Secure session token management.

    WHY: Stateless auth tokens with timeout and revocation support.
    Tokens are cryptographically secure random strings (32 bytes = 64 hex chars).

    SECURITY NOTES:
    - Tokens stored hashed in database (bcrypt)
    - 24-hour absolute timeout
    - 2-hour idle timeout
    - Revocable on logout or suspicious activity
    """
    __tablename__ = "session_tokens"
    __table_args__ = (
        db.Index("ix_session_tokens_user_active", "user_id", "is_revoked"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    # Token hash (never store plaintext tokens!)
    token_hash = db.Column(db.String(255), nullable=False, unique=True, index=True)

    # Session metadata
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    last_used_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)

    # Revocation support
    is_revoked = db.Column(db.Boolean, nullable=False, default=False, index=True)
    revoked_at = db.Column(db.DateTime(timezone=True), nullable=True)
    revoked_reason = db.Column(db.String(255), nullable=True)

    # Client information (for security monitoring)
    user_agent = db.Column(db.String(512), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)  # IPv6 max length

    user = db.relationship("User", backref=db.backref("session_tokens", lazy=True))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "created_at": to_utc_z(self.created_at),
            "last_used_at": to_utc_z(self.last_used_at),
            "expires_at": to_utc_z(self.expires_at),
            "is_revoked": self.is_revoked,
            "revoked_at": to_utc_z(self.revoked_at) if self.revoked_at else None,
        }


class MasterLedgerEvent(db.Model):
    __tablename__ = "master_ledger_events"
    __table_args__ = {"sqlite_autoincrement": True}

    id = db.Column(db.Integer, primary_key=True)

    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False, index=True)

    # What happened
    event_type = db.Column(db.String(64), nullable=False, index=True)  # e.g., PRODUCT_CREATED, PRODUCT_DELETED, INV_TX_CREATED

    # What it refers to (generic pointer)
    entity_type = db.Column(db.String(64), nullable=False, index=True)  # e.g., product, inventory_transaction
    entity_id = db.Column(db.Integer, nullable=False, index=True)

    # Business vs system time (same timestamp policy as inventory)
    occurred_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now(), index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())

    # Optional structured metadata (keep small; do not denormalize domain state)
    note = db.Column(db.String(255), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "store_id": self.store_id,
            "event_type": self.event_type,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "occurred_at": to_utc_z(self.occurred_at),
            "created_at": to_utc_z(self.created_at),
            "note": self.note,
        }
