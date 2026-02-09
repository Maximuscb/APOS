from __future__ import annotations

from ..extensions import db
from app.time_utils import to_utc_z

class Product(db.Model):
    """
    Product master data.

    MULTI-TENANT: Products are scoped to stores via store_id.
    Store belongs to an organization, so products are transitively org-scoped.

    SKU DESIGN DECISION:
    Product.sku is the CANONICAL source of truth for store-scoped SKUs.
    - SKUs are unique within a store: UniqueConstraint("store_id", "sku")
    - Do NOT create ProductIdentifier rows with type='SKU'
    - ProductIdentifier is for scannable codes (UPC, ALT_BARCODE) and vendor codes

    WHY:
    1. SKUs are store-assigned internal codes, not external scannable identifiers
    2. Every product must have exactly one SKU (required field)
    3. Storing SKU in both places creates sync risk and ambiguity
    4. Lookups by SKU are always store-scoped (you scan at a specific store)

    LOOKUP PATTERN:
    - SKU lookup: Product.query.filter_by(store_id=X, sku=Y)
    - Barcode lookup: ProductIdentifier.query.filter_by(org_id=X, value=Y, is_active=True)
    """
    __tablename__ = "products"
    __table_args__ = (
        # SKUs are unique within a store (canonical source of truth)
        db.UniqueConstraint("store_id", "sku", name="uq_products_store_sku"),
        db.Index("ix_products_store_name", "store_id", "name"),
        db.Index("ix_products_store_active", "store_id", "is_active"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)

    # Multi-store ready (even if you only have one store today)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False, index=True)

    # CANONICAL SKU: Store-scoped, required. Do not duplicate in ProductIdentifier.
    sku = db.Column(db.String(64), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)

    # Authoritative storage in cents (frontend may only format for display)
    price_cents = db.Column(db.Integer, nullable=True)

    is_active = db.Column(db.Boolean, nullable=False, default=True)
    imported_from_batch_id = db.Column(db.Integer, db.ForeignKey("import_batches.id"), nullable=True, index=True)

    version_id = db.Column(db.Integer, nullable=False, default=1)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.func.now(),
        onupdate=db.func.now(),
    )

    store = db.relationship("Store", backref=db.backref("products", lazy=True))
    imported_from_batch = db.relationship("ImportBatch", foreign_keys=[imported_from_batch_id])
    __mapper_args__ = {"version_id_col": version_id}

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
            "version_id": self.version_id,
            "created_at": to_utc_z(self.created_at),
            "updated_at": to_utc_z(self.updated_at),
            "imported_from_batch_id": self.imported_from_batch_id,
        }

class InventoryTransaction(db.Model):
    __tablename__ = "inventory_transactions"
    
    id = db.Column(db.Integer, primary_key=True)

    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)

    type = db.Column(db.String(32), nullable=False, index=True)

    quantity_delta = db.Column(db.Integer, nullable=False)

    unit_cost_cents = db.Column(db.Integer, nullable=True)

    note = db.Column(db.String(255), nullable=True)

    occurred_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.func.now(),
        index=True,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.func.now(),
    )

    sale_id = db.Column(db.String(64), nullable=True, index=True)
    sale_line_id = db.Column(db.String(64), nullable=True)

    unit_cost_cents_at_sale = db.Column(db.Integer, nullable=True)
    cogs_cents = db.Column(db.Integer, nullable=True)

    status = db.Column(
        db.String(16),
        nullable=False,
        default="POSTED",  # Backwards compatibility: existing data and old code auto-posts
        index=True,  # Frequently filtered in queries
    )

    approved_by_user_id = db.Column(db.Integer, nullable=True)
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True)

    posted_by_user_id = db.Column(db.Integer, nullable=True)
    posted_at = db.Column(db.DateTime(timezone=True), nullable=True)

    inventory_state = db.Column(
        db.String(16),
        nullable=False,
        default="SELLABLE",
        index=True, 
    )

    __table_args__ = (
        db.Index("ix_invtx_store_product_occurred", "store_id", "product_id", "occurred_at"),
        db.Index("ix_invtx_store_product_type_occurred", "store_id", "product_id", "type", "occurred_at"),
        db.UniqueConstraint("store_id", "sale_id", "sale_line_id", name="uq_invtx_store_sale_line"),
        {"sqlite_autoincrement": True},  
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
            # Lifecycle fields
            "status": self.status,
            "approved_by_user_id": self.approved_by_user_id,
            "approved_at": to_utc_z(self.approved_at) if self.approved_at else None,
            "posted_by_user_id": self.posted_by_user_id,
            "posted_at": to_utc_z(self.posted_at) if self.posted_at else None,
            # Inventory state
            "inventory_state": self.inventory_state,
        }

class ProductIdentifier(db.Model):
    """
    Product identifiers for barcode/code lookups.

    MULTI-TENANT SCOPING:
    - org_id: Required for tenant isolation. Backfilled from Product.store_id -> Store.org_id.
    - store_id: Optional, for store-specific identifiers. Backfilled from Product.store_id.

    UNIQUENESS RULES BY TYPE:
    - UPC, ALT_BARCODE: Org-scoped. Same UPC cannot be used by two products in same org.
      Constraint: (org_id, type, value) for active identifiers
    - VENDOR_CODE: Vendor-scoped within org. Same vendor code can exist for different vendors.
      Constraint: (org_id, vendor_id, type, value) for active identifiers
    - SKU: DEPRECATED in this table. Product.sku is the canonical source for store-scoped SKUs.
      Do NOT create type=SKU identifiers; use Product.sku instead.

    VALUE NORMALIZATION:
    All identifier values are normalized to uppercase with whitespace stripped.
    This ensures consistent lookups regardless of input case.

    WHY NOT STORE-SCOPED FOR ALL:
    UPCs are manufacturer-assigned and globally unique within retail. An org may
    sell the same UPC from different stores. Store-scoping UPCs would allow the
    same barcode to resolve to different products depending on which store is
    scanning, which is confusing and error-prone.
    """
    __tablename__ = "product_identifiers"
    __table_args__ = (
        # Org-scoped uniqueness for scannable identifiers (UPC, ALT_BARCODE)
        # Only enforced for active identifiers (is_active=True checked at application layer)
        # Note: SKU type is deprecated; use Product.sku instead
        db.UniqueConstraint("org_id", "type", "value", name="uq_identifier_org_type_value"),

        # Vendor-scoped uniqueness for vendor codes (allows same code from different vendors)
        # Applied via partial index or application-layer check since vendor_id is nullable
        db.Index("ix_identifier_org_vendor_value", "org_id", "vendor_id", "value"),

        # Lookup indexes matching common query patterns
        db.Index("ix_identifier_value", "value"),
        db.Index("ix_identifier_org_value", "org_id", "value"),
        db.Index("ix_identifier_org_type_active", "org_id", "type", "is_active"),
        db.Index("ix_identifier_product", "product_id"),
        db.Index("ix_identifier_active", "is_active"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)

    # MULTI-TENANT: Org scope for tenant isolation (backfilled from Product.store_id -> Store.org_id)
    org_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True)

    # Store scope (optional, backfilled from Product.store_id)
    # Kept for reference/audit but uniqueness is org-scoped for most identifier types
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=True, index=True)

    # Identifier type: UPC, ALT_BARCODE, VENDOR_CODE
    # NOTE: SKU type is DEPRECATED. Use Product.sku for store-scoped SKUs.
    type = db.Column(db.String(32), nullable=False, index=True)

    # Normalized value (uppercase, whitespace stripped)
    value = db.Column(db.String(128), nullable=False)

    # Vendor scope for VENDOR_CODE type (required when type=VENDOR_CODE)
    vendor_id = db.Column(db.Integer, nullable=True, index=True)

    is_primary = db.Column(db.Boolean, nullable=False, default=False)

    # Soft delete flag - inactive identifiers are excluded from lookups
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    deactivated_at = db.Column(db.DateTime(timezone=True), nullable=True)

    product = db.relationship("Product", backref=db.backref("identifiers", lazy=True))
    organization = db.relationship("Organization", backref=db.backref("product_identifiers", lazy=True))
    store = db.relationship("Store", backref=db.backref("product_identifiers", lazy=True))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "product_id": self.product_id,
            "org_id": self.org_id,
            "store_id": self.store_id,
            "type": self.type,
            "value": self.value,
            "vendor_id": self.vendor_id,
            "is_primary": self.is_primary,
            "is_active": self.is_active,
            "created_at": to_utc_z(self.created_at),
            "deactivated_at": to_utc_z(self.deactivated_at) if self.deactivated_at else None,
        }

class Vendor(db.Model):
    """
    First-class Vendor entity for inventory receiving.

    MULTI-TENANT: Vendors are scoped to organizations via org_id.
    Vendor codes are unique within an organization when specified.

    WHY: Every inventory receive must have exactly one vendor, regardless
    of source (purchase, donation, found stock, etc.). This provides
    traceability and supports vendor-specific analytics.

    DESIGN:
    - Products may be sourced from multiple vendors (no required join)
    - Vendor-product relationships are implicit via ReceiveDocument history
    - Vendor is stored on receive document header, not per line item
    """
    __tablename__ = "vendors"
    __table_args__ = (
        db.UniqueConstraint("org_id", "code", name="uq_vendors_org_code"),
        db.Index("ix_vendors_org_id", "org_id"),
        db.Index("ix_vendors_org_active", "org_id", "is_active"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True)

    name = db.Column(db.String(255), nullable=False)
    code = db.Column(db.String(64), nullable=True, index=True)  # Optional short code for quick lookup

    # Contact information
    contact_name = db.Column(db.String(255), nullable=True)
    contact_email = db.Column(db.String(255), nullable=True)
    contact_phone = db.Column(db.String(64), nullable=True)
    address = db.Column(db.Text, nullable=True)

    # Status
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)

    # Notes and metadata
    notes = db.Column(db.Text, nullable=True)

    # Audit fields
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now(), onupdate=db.func.now())
    version_id = db.Column(db.Integer, nullable=False, default=1)

    organization = db.relationship("Organization", backref=db.backref("vendors", lazy=True))
    __mapper_args__ = {"version_id_col": version_id}

    def __repr__(self) -> str:
        return f"<Vendor id={self.id} name={self.name!r} org_id={self.org_id}>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "org_id": self.org_id,
            "name": self.name,
            "code": self.code,
            "contact_name": self.contact_name,
            "contact_email": self.contact_email,
            "contact_phone": self.contact_phone,
            "address": self.address,
            "is_active": self.is_active,
            "notes": self.notes,
            "created_at": to_utc_z(self.created_at),
            "updated_at": to_utc_z(self.updated_at),
            "version_id": self.version_id,
        }


# =============================================================================
# RECEIVE DOCUMENT (Document-First Inventory Receiving)
# =============================================================================

class ReceiveDocument(db.Model):
    """
    Inventory receive document with required vendor.

    WHY: Every inventory receive must require exactly one vendor, regardless
    of source. This is the document header; line items are in ReceiveDocumentLine.

    LIFECYCLE:
    1. DRAFT: Created, lines being added
    2. APPROVED: Manager approved, ready to post
    3. POSTED: Posted to inventory ledger (creates InventoryTransactions)
    4. CANCELLED: Cancelled before posting

    IMMUTABLE: Once POSTED, document cannot be modified. Corrections require
    new documents (adjustments, voids).

    DESIGN:
    - Vendor is REQUIRED on the document header, not per line
    - receive_type tracks source: PURCHASE, DONATION, FOUND, TRANSFER_IN, OTHER
    - Document number follows standard format: RCV-{store}-{number}
    """
    __tablename__ = "receive_documents"
    __table_args__ = (
        db.UniqueConstraint("store_id", "document_number", name="uq_receive_docs_store_docnum"),
        db.Index("ix_receive_docs_document_number", "document_number"),
        db.Index("ix_receive_docs_store_status", "store_id", "status"),
        db.Index("ix_receive_docs_vendor", "vendor_id"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False, index=True)

    # REQUIRED: Every receive must have a vendor
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendors.id"), nullable=False, index=True)

    # Human-readable document number (e.g., "RCV-001-0042")
    document_number = db.Column(db.String(64), nullable=False)

    # Source type: PURCHASE, DONATION, FOUND, TRANSFER_IN, OTHER
    receive_type = db.Column(db.String(32), nullable=False, index=True)

    # Document lifecycle status
    status = db.Column(db.String(16), nullable=False, default="DRAFT", index=True)

    # Business date/time of the receive
    occurred_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())

    # Notes
    notes = db.Column(db.Text, nullable=True)

    # Reference number (PO number, invoice number, etc.)
    reference_number = db.Column(db.String(128), nullable=True)

    # Lifecycle user attribution
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    approved_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    posted_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    cancelled_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    # Lifecycle timestamps
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    posted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    cancelled_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Cancellation reason
    cancellation_reason = db.Column(db.Text, nullable=True)

    imported_from_batch_id = db.Column(db.Integer, db.ForeignKey("import_batches.id"), nullable=True, index=True)

    version_id = db.Column(db.Integer, nullable=False, default=1)

    # Relationships
    store = db.relationship("Store", backref=db.backref("receive_documents", lazy=True))
    vendor = db.relationship("Vendor", backref=db.backref("receive_documents", lazy=True))
    imported_from_batch = db.relationship("ImportBatch", foreign_keys=[imported_from_batch_id])
    created_by = db.relationship("User", foreign_keys=[created_by_user_id])
    approved_by = db.relationship("User", foreign_keys=[approved_by_user_id])
    posted_by = db.relationship("User", foreign_keys=[posted_by_user_id])
    cancelled_by = db.relationship("User", foreign_keys=[cancelled_by_user_id])

    __mapper_args__ = {"version_id_col": version_id}

    def __repr__(self) -> str:
        return f"<ReceiveDocument id={self.id} doc_num={self.document_number!r} status={self.status}>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "store_id": self.store_id,
            "vendor_id": self.vendor_id,
            "document_number": self.document_number,
            "receive_type": self.receive_type,
            "status": self.status,
            "occurred_at": to_utc_z(self.occurred_at),
            "notes": self.notes,
            "reference_number": self.reference_number,
            "created_by_user_id": self.created_by_user_id,
            "approved_by_user_id": self.approved_by_user_id,
            "posted_by_user_id": self.posted_by_user_id,
            "cancelled_by_user_id": self.cancelled_by_user_id,
            "created_at": to_utc_z(self.created_at),
            "approved_at": to_utc_z(self.approved_at) if self.approved_at else None,
            "posted_at": to_utc_z(self.posted_at) if self.posted_at else None,
            "cancelled_at": to_utc_z(self.cancelled_at) if self.cancelled_at else None,
            "cancellation_reason": self.cancellation_reason,
            "version_id": self.version_id,
            "imported_from_batch_id": self.imported_from_batch_id,
        }

class ReceiveDocumentLine(db.Model):
    """
    Individual line items on a receive document.

    WHY: Track which products and quantities are being received.
    Links to InventoryTransaction when document is posted.
    """
    __tablename__ = "receive_document_lines"
    __table_args__ = (
        db.UniqueConstraint("receive_document_id", "product_id", name="uq_receive_lines_doc_product"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    receive_document_id = db.Column(db.Integer, db.ForeignKey("receive_documents.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)

    # Quantity received (always positive)
    quantity = db.Column(db.Integer, nullable=False)

    # Unit cost in cents (required for COGS calculation)
    unit_cost_cents = db.Column(db.Integer, nullable=False)

    # Line total (quantity * unit_cost_cents)
    line_cost_cents = db.Column(db.Integer, nullable=False)

    # Optional notes for this line
    note = db.Column(db.String(255), nullable=True)

    # Link to inventory transaction (created when document is posted)
    inventory_transaction_id = db.Column(db.Integer, db.ForeignKey("inventory_transactions.id"), nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    version_id = db.Column(db.Integer, nullable=False, default=1)

    # Relationships
    receive_document = db.relationship("ReceiveDocument", backref=db.backref("lines", lazy=True))
    product = db.relationship("Product")
    inventory_transaction = db.relationship("InventoryTransaction")

    __mapper_args__ = {"version_id_col": version_id}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "receive_document_id": self.receive_document_id,
            "product_id": self.product_id,
            "quantity": self.quantity,
            "unit_cost_cents": self.unit_cost_cents,
            "line_cost_cents": self.line_cost_cents,
            "note": self.note,
            "inventory_transaction_id": self.inventory_transaction_id,
            "created_at": to_utc_z(self.created_at),
            "version_id": self.version_id,
        }


# =============================================================================
# USER PERMISSION OVERRIDES
# =============================================================================
