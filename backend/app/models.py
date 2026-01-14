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
