from __future__ import annotations

from ..extensions import db
from app.time_utils import to_utc_z

class Sale(db.Model):
    """
    Sale document model (document-first, not inventory-first).

    WHY: Sales are documents with lifecycle, not just inventory decrements.
    Enables cart editing, suspend/recall, quotes/estimates.
    """
    __tablename__ = "sales"
    __table_args__ = (
        db.UniqueConstraint("store_id", "document_number", name="uq_sales_store_docnum"),
        # Index for document number lookups (supports prefix searching)
        db.Index("ix_sales_document_number", "document_number"),
        # Composite index for store-scoped queries by status and date
        db.Index("ix_sales_store_status_created", "store_id", "status", "created_at"),
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

    # User attribution (nullable until complete)
    created_by_user_id = db.Column(db.Integer, nullable=True)

    # Void audit trail
    voided_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    voided_at = db.Column(db.DateTime(timezone=True), nullable=True)
    void_reason = db.Column(db.String(255), nullable=True)

    # Register tracking
    register_id = db.Column(db.Integer, db.ForeignKey("registers.id"), nullable=True, index=True)
    register_session_id = db.Column(db.Integer, db.ForeignKey("register_sessions.id"), nullable=True, index=True)

    # Payment tracking (all amounts in cents)
    payment_status = db.Column(db.String(16), nullable=False, default="UNPAID", index=True)  # UNPAID, PARTIAL, PAID, OVERPAID
    total_due_cents = db.Column(db.Integer, nullable=True)  # Calculated from sale lines
    total_paid_cents = db.Column(db.Integer, nullable=False, default=0)  # Sum of completed payments
    change_due_cents = db.Column(db.Integer, nullable=False, default=0)  # For overpayment
    imported_from_batch_id = db.Column(db.Integer, db.ForeignKey("import_batches.id"), nullable=True, index=True)
    version_id = db.Column(db.Integer, nullable=False, default=1)

    store = db.relationship("Store", backref=db.backref("sales", lazy=True))
    imported_from_batch = db.relationship("ImportBatch", foreign_keys=[imported_from_batch_id])
    __mapper_args__ = {"version_id_col": version_id}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "store_id": self.store_id,
            "document_number": self.document_number,
            "status": self.status,
            "created_at": to_utc_z(self.created_at),
            "completed_at": to_utc_z(self.completed_at) if self.completed_at else None,
            "created_by_user_id": self.created_by_user_id,
            "voided_by_user_id": self.voided_by_user_id,
            "voided_at": to_utc_z(self.voided_at) if self.voided_at else None,
            "void_reason": self.void_reason,
            "register_id": self.register_id,
            "register_session_id": self.register_session_id,
            "payment_status": self.payment_status,
            "total_due_cents": self.total_due_cents,
            "total_paid_cents": self.total_paid_cents,
            "change_due_cents": self.change_due_cents,
            "version_id": self.version_id,
            "imported_from_batch_id": self.imported_from_batch_id,
        }

class SaleLine(db.Model):
    """Individual line items on a sale document."""
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
    version_id = db.Column(db.Integer, nullable=False, default=1)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())

    sale = db.relationship("Sale", backref=db.backref("lines", lazy=True))
    product = db.relationship("Product")
    __mapper_args__ = {"version_id_col": version_id}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "sale_id": self.sale_id,
            "product_id": self.product_id,
            "quantity": self.quantity,
            "unit_price_cents": self.unit_price_cents,
            "line_total_cents": self.line_total_cents,
            "inventory_transaction_id": self.inventory_transaction_id,
            "version_id": self.version_id,
            "created_at": to_utc_z(self.created_at),
        }

class Payment(db.Model):
    """
    Payment record for sales.

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

    # Register tracking
    register_id = db.Column(db.Integer, db.ForeignKey("registers.id"), nullable=True, index=True)
    register_session_id = db.Column(db.Integer, db.ForeignKey("register_sessions.id"), nullable=True, index=True)
    version_id = db.Column(db.Integer, nullable=False, default=1)

    sale = db.relationship("Sale", backref=db.backref("payments", lazy=True))
    created_by = db.relationship("User", foreign_keys=[created_by_user_id], backref=db.backref("payments_created", lazy=True))
    voided_by = db.relationship("User", foreign_keys=[voided_by_user_id], backref=db.backref("payments_voided", lazy=True))
    __mapper_args__ = {"version_id_col": version_id}

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
            "version_id": self.version_id,
        }

class PaymentTransaction(db.Model):
    """
    Append-only ledger of payment events.

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

    # Register tracking
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
