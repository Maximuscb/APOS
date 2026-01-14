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
