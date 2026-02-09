from __future__ import annotations

from ..extensions import db
from app.time_utils import to_utc_z

class Return(db.Model):
    """
    Product return document.

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
        # Index for document number lookups
        db.Index("ix_returns_document_number", "document_number"),
        # Composite index for store-scoped queries by status and date
        db.Index("ix_returns_store_status_created", "store_id", "status", "created_at"),
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

    # Register tracking
    register_id = db.Column(db.Integer, db.ForeignKey("registers.id"), nullable=True, index=True)
    register_session_id = db.Column(db.Integer, db.ForeignKey("register_sessions.id"), nullable=True, index=True)
    imported_from_batch_id = db.Column(db.Integer, db.ForeignKey("import_batches.id"), nullable=True, index=True)
    version_id = db.Column(db.Integer, nullable=False, default=1)

    store = db.relationship("Store", backref=db.backref("returns", lazy=True))
    original_sale = db.relationship("Sale", backref=db.backref("returns", lazy=True))
    imported_from_batch = db.relationship("ImportBatch", foreign_keys=[imported_from_batch_id])
    created_by = db.relationship("User", foreign_keys=[created_by_user_id], backref=db.backref("returns_created", lazy=True))
    approved_by = db.relationship("User", foreign_keys=[approved_by_user_id], backref=db.backref("returns_approved", lazy=True))
    __mapper_args__ = {"version_id_col": version_id}

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
            "imported_from_batch_id": self.imported_from_batch_id,
            "version_id": self.version_id,
        }

class ReturnLine(db.Model):
    """
    Individual line items on a return document.

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
    version_id = db.Column(db.Integer, nullable=False, default=1)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())

    return_doc = db.relationship("Return", backref=db.backref("lines", lazy=True))
    original_sale_line = db.relationship("SaleLine", backref=db.backref("return_lines", lazy=True))
    product = db.relationship("Product")
    __mapper_args__ = {"version_id_col": version_id}

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
            "version_id": self.version_id,
            "created_at": to_utc_z(self.created_at),
        }

class Transfer(db.Model):
    """
    Inter-store inventory transfer document.

    LIFECYCLE:
    1. PENDING: Transfer created, awaiting manager approval
    2. APPROVED: Manager approved, ready to ship
    3. IN_TRANSIT: Shipped from source, not yet received
    4. RECEIVED: Received at destination, inventory updated
    5. CANCELLED: Transfer cancelled before shipping

    WHY: Enables moving inventory between stores with proper approval,
    tracking, and accountability. Creates TRANSFER transactions at both
    source (negative, state=IN_TRANSIT) and destination (positive,
    state=SELLABLE when received).

    MULTI-TENANT: Document numbers are unique per source store (from_store_id),
    consistent with Sale/Return/Count document numbering patterns.
    DocumentSequence generates unique numbers per store.
    """
    __tablename__ = "transfers"
    __table_args__ = (
        # Document numbers unique per source store (like Sale/Return)
        db.UniqueConstraint("from_store_id", "document_number", name="uq_transfers_store_docnum"),
        db.Index("ix_transfers_document_number", "document_number"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)

    # Source and destination stores
    from_store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False, index=True)
    to_store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False, index=True)

    # Document number (e.g., "T-000001") - unique per source store
    document_number = db.Column(db.String(64), nullable=False)

    # PENDING, APPROVED, IN_TRANSIT, RECEIVED, CANCELLED
    status = db.Column(db.String(16), nullable=False, default="PENDING", index=True)

    # Reason for transfer
    reason = db.Column(db.Text, nullable=True)

    # User attribution for accountability
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    approved_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    shipped_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    received_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    cancelled_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    # Timestamps for each lifecycle stage
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    shipped_at = db.Column(db.DateTime(timezone=True), nullable=True)
    received_at = db.Column(db.DateTime(timezone=True), nullable=True)
    cancelled_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Cancellation reason
    cancellation_reason = db.Column(db.Text, nullable=True)
    imported_from_batch_id = db.Column(db.Integer, db.ForeignKey("import_batches.id"), nullable=True, index=True)
    version_id = db.Column(db.Integer, nullable=False, default=1)

    from_store = db.relationship("Store", foreign_keys=[from_store_id])
    to_store = db.relationship("Store", foreign_keys=[to_store_id])
    imported_from_batch = db.relationship("ImportBatch", foreign_keys=[imported_from_batch_id])
    __mapper_args__ = {"version_id_col": version_id}
    created_by = db.relationship("User", foreign_keys=[created_by_user_id])
    approved_by = db.relationship("User", foreign_keys=[approved_by_user_id])
    shipped_by = db.relationship("User", foreign_keys=[shipped_by_user_id])
    received_by = db.relationship("User", foreign_keys=[received_by_user_id])
    cancelled_by = db.relationship("User", foreign_keys=[cancelled_by_user_id])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "from_store_id": self.from_store_id,
            "to_store_id": self.to_store_id,
            "document_number": self.document_number,
            "status": self.status,
            "reason": self.reason,
            "created_by_user_id": self.created_by_user_id,
            "approved_by_user_id": self.approved_by_user_id,
            "shipped_by_user_id": self.shipped_by_user_id,
            "received_by_user_id": self.received_by_user_id,
            "cancelled_by_user_id": self.cancelled_by_user_id,
            "created_at": to_utc_z(self.created_at),
            "approved_at": to_utc_z(self.approved_at) if self.approved_at else None,
            "shipped_at": to_utc_z(self.shipped_at) if self.shipped_at else None,
            "received_at": to_utc_z(self.received_at) if self.received_at else None,
            "cancelled_at": to_utc_z(self.cancelled_at) if self.cancelled_at else None,
            "cancellation_reason": self.cancellation_reason,
            "imported_from_batch_id": self.imported_from_batch_id,
            "version_id": self.version_id,
        }

class TransferLine(db.Model):
    """
    Individual line items on a transfer document.

    WHY: Track which specific products and quantities are being transferred.
    Links to inventory transactions at source and destination stores.
    """
    __tablename__ = "transfer_lines"
    __table_args__ = {"sqlite_autoincrement": True}

    id = db.Column(db.Integer, primary_key=True)
    transfer_id = db.Column(db.Integer, db.ForeignKey("transfers.id"), nullable=False, index=True)

    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)

    # Quantity being transferred
    quantity = db.Column(db.Integer, nullable=False)

    # Cost snapshot captured at ship time (from source store WAC)
    unit_cost_cents = db.Column(db.Integer, nullable=True)

    # Links to inventory transactions (created when shipped and received)
    # out_transaction_id: negative TRANSFER at source store (inventory_state=IN_TRANSIT)
    # in_transaction_id: positive TRANSFER at destination store (inventory_state=SELLABLE)
    out_transaction_id = db.Column(db.Integer, db.ForeignKey("inventory_transactions.id"), nullable=True)
    in_transaction_id = db.Column(db.Integer, db.ForeignKey("inventory_transactions.id"), nullable=True)
    version_id = db.Column(db.Integer, nullable=False, default=1)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())

    transfer = db.relationship("Transfer", backref=db.backref("lines", lazy=True))
    product = db.relationship("Product")
    out_transaction = db.relationship("InventoryTransaction", foreign_keys=[out_transaction_id])
    in_transaction = db.relationship("InventoryTransaction", foreign_keys=[in_transaction_id])
    __mapper_args__ = {"version_id_col": version_id}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "transfer_id": self.transfer_id,
            "product_id": self.product_id,
            "quantity": self.quantity,
            "unit_cost_cents": self.unit_cost_cents,
            "out_transaction_id": self.out_transaction_id,
            "in_transaction_id": self.in_transaction_id,
            "version_id": self.version_id,
            "created_at": to_utc_z(self.created_at),
        }

class Count(db.Model):
    """
    Physical inventory count document (cycle count or full count).

    LIFECYCLE:
    1. PENDING: Count created, lines being entered
    2. APPROVED: Manager approved, ready to post variances
    3. POSTED: Variances posted to inventory ledger
    4. CANCELLED: Count cancelled before posting

    WHY: Regular physical counts ensure inventory accuracy. Variances
    between expected (system) and actual (counted) quantities are posted
    as ADJUST transactions. Manager approval required before posting
    ensures review of significant discrepancies.

    MULTI-TENANT: Document numbers are unique per store (store_id),
    consistent with Sale/Return/Transfer document numbering patterns.
    DocumentSequence generates unique numbers per store.
    """
    __tablename__ = "counts"
    __table_args__ = (
        # Document numbers unique per store (like Sale/Return)
        db.UniqueConstraint("store_id", "document_number", name="uq_counts_store_docnum"),
        db.Index("ix_counts_document_number", "document_number"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)

    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False, index=True)

    # Document number (e.g., "C-000001") - unique per store
    document_number = db.Column(db.String(64), nullable=False)

    # CYCLE (subset of products) or FULL (all products)
    count_type = db.Column(db.String(16), nullable=False, index=True)

    # PENDING, APPROVED, POSTED, CANCELLED
    status = db.Column(db.String(16), nullable=False, default="PENDING", index=True)

    # Reason/notes
    reason = db.Column(db.Text, nullable=True)

    # Total variance (sum of all line variances)
    total_variance_units = db.Column(db.Integer, nullable=True)
    total_variance_cost_cents = db.Column(db.Integer, nullable=True)

    # User attribution for accountability
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    approved_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    posted_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    cancelled_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    # Timestamps for each lifecycle stage
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    posted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    cancelled_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Cancellation reason
    cancellation_reason = db.Column(db.Text, nullable=True)
    imported_from_batch_id = db.Column(db.Integer, db.ForeignKey("import_batches.id"), nullable=True, index=True)
    version_id = db.Column(db.Integer, nullable=False, default=1)

    store = db.relationship("Store")
    imported_from_batch = db.relationship("ImportBatch", foreign_keys=[imported_from_batch_id])
    created_by = db.relationship("User", foreign_keys=[created_by_user_id])
    approved_by = db.relationship("User", foreign_keys=[approved_by_user_id])
    posted_by = db.relationship("User", foreign_keys=[posted_by_user_id])
    cancelled_by = db.relationship("User", foreign_keys=[cancelled_by_user_id])
    __mapper_args__ = {"version_id_col": version_id}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "store_id": self.store_id,
            "document_number": self.document_number,
            "count_type": self.count_type,
            "status": self.status,
            "reason": self.reason,
            "total_variance_units": self.total_variance_units,
            "total_variance_cost_cents": self.total_variance_cost_cents,
            "created_by_user_id": self.created_by_user_id,
            "approved_by_user_id": self.approved_by_user_id,
            "posted_by_user_id": self.posted_by_user_id,
            "cancelled_by_user_id": self.cancelled_by_user_id,
            "created_at": to_utc_z(self.created_at),
            "approved_at": to_utc_z(self.approved_at) if self.approved_at else None,
            "posted_at": to_utc_z(self.posted_at) if self.posted_at else None,
            "cancelled_at": to_utc_z(self.cancelled_at) if self.cancelled_at else None,
            "cancellation_reason": self.cancellation_reason,
            "imported_from_batch_id": self.imported_from_batch_id,
            "version_id": self.version_id,
        }

class CountLine(db.Model):
    """
    Individual line items on a count document.

    WHY: Track expected vs. actual quantities for each product.
    Variance (actual - expected) is posted as ADJUST transaction.
    """
    __tablename__ = "count_lines"
    __table_args__ = (
        db.UniqueConstraint("count_id", "product_id", name="uq_count_lines_count_product"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    count_id = db.Column(db.Integer, db.ForeignKey("counts.id"), nullable=False, index=True)

    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)

    # Expected quantity (from system)
    expected_quantity = db.Column(db.Integer, nullable=False)

    # Actual quantity (physically counted)
    actual_quantity = db.Column(db.Integer, nullable=False)

    # Variance (actual - expected)
    variance_quantity = db.Column(db.Integer, nullable=False)

    # WAC at time of count (for variance cost calculation)
    unit_cost_cents = db.Column(db.Integer, nullable=True)

    # Variance cost (variance_quantity * unit_cost_cents)
    variance_cost_cents = db.Column(db.Integer, nullable=True)

    # Link to inventory transaction (created when count is posted)
    inventory_transaction_id = db.Column(db.Integer, db.ForeignKey("inventory_transactions.id"), nullable=True)
    version_id = db.Column(db.Integer, nullable=False, default=1)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())

    count = db.relationship("Count", backref=db.backref("lines", lazy=True))
    product = db.relationship("Product")
    inventory_transaction = db.relationship("InventoryTransaction")
    __mapper_args__ = {"version_id_col": version_id}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "count_id": self.count_id,
            "product_id": self.product_id,
            "expected_quantity": self.expected_quantity,
            "actual_quantity": self.actual_quantity,
            "variance_quantity": self.variance_quantity,
            "unit_cost_cents": self.unit_cost_cents,
            "variance_cost_cents": self.variance_cost_cents,
            "inventory_transaction_id": self.inventory_transaction_id,
            "version_id": self.version_id,
            "created_at": to_utc_z(self.created_at),
        }

class MasterLedgerEvent(db.Model):
    __tablename__ = "master_ledger_events"
    __table_args__ = (
        db.Index("ix_master_ledger_store_occurred", "store_id", "occurred_at"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)

    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False, index=True)

    # What happened
    event_type = db.Column(db.String(64), nullable=False, index=True)  # e.g., PRODUCT_CREATED, PRODUCT_DELETED, INV_TX_CREATED
    event_category = db.Column(db.String(32), nullable=False, index=True)  # inventory, product, payment, register, cash_drawer, sales, returns, transfers, counts

    # What it refers to (generic pointer)
    entity_type = db.Column(db.String(64), nullable=False, index=True)  # e.g., product, inventory_transaction
    entity_id = db.Column(db.Integer, nullable=False, index=True)

    # Actor and cross-module references
    actor_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    register_id = db.Column(db.Integer, db.ForeignKey("registers.id"), nullable=True, index=True)
    register_session_id = db.Column(db.Integer, db.ForeignKey("register_sessions.id"), nullable=True, index=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("sales.id"), nullable=True, index=True)
    payment_id = db.Column(db.Integer, db.ForeignKey("payments.id"), nullable=True, index=True)
    return_id = db.Column(db.Integer, db.ForeignKey("returns.id"), nullable=True, index=True)
    transfer_id = db.Column(db.Integer, db.ForeignKey("transfers.id"), nullable=True, index=True)
    count_id = db.Column(db.Integer, db.ForeignKey("counts.id"), nullable=True, index=True)
    cash_drawer_event_id = db.Column(db.Integer, db.ForeignKey("cash_drawer_events.id"), nullable=True, index=True)

    # Business vs system time (same timestamp policy as inventory)
    occurred_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now(), index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())

    # Optional structured metadata (keep small; do not denormalize domain state)
    note = db.Column(db.String(255), nullable=True)
    payload = db.Column(db.Text, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "store_id": self.store_id,
            "event_type": self.event_type,
            "event_category": self.event_category,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "actor_user_id": self.actor_user_id,
            "register_id": self.register_id,
            "register_session_id": self.register_session_id,
            "sale_id": self.sale_id,
            "payment_id": self.payment_id,
            "return_id": self.return_id,
            "transfer_id": self.transfer_id,
            "count_id": self.count_id,
            "cash_drawer_event_id": self.cash_drawer_event_id,
            "occurred_at": to_utc_z(self.occurred_at),
            "created_at": to_utc_z(self.created_at),
            "note": self.note,
            "payload": self.payload,
        }

class DocumentSequence(db.Model):
    """
    Atomic per-store document sequences.

    WHY: Prevent race conditions when generating document numbers
    (sales, returns, transfers, counts).
    """
    __tablename__ = "document_sequences"
    __table_args__ = (
        db.UniqueConstraint("store_id", "document_type", name="uq_doc_sequences_store_type"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False, index=True)
    document_type = db.Column(db.String(32), nullable=False, index=True)
    next_number = db.Column(db.Integer, nullable=False, default=1)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now(), onupdate=db.func.now())

    store = db.relationship("Store", backref=db.backref("document_sequences", lazy=True))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "store_id": self.store_id,
            "document_type": self.document_type,
            "next_number": self.next_number,
            "updated_at": to_utc_z(self.updated_at),
        }


# =============================================================================
# VENDOR ENTITY
# =============================================================================
