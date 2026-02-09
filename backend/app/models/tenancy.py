from __future__ import annotations

from ..extensions import db
from app.time_utils import to_utc_z

class Organization(db.Model):
    """
    Multi-tenant root: Every tenant is an Organization.

    WHY: Enables shared-database multi-tenancy with strict isolation.
    All stores, users, and data belong to exactly one organization.
    No data may cross organization boundaries.

    DESIGN:
    - Organizations are the tenant boundary
    - Stores belong to organizations (org_id FK)
    - All queries must be scoped by org_id (via store or directly)
    - Users belong to organizations (org_id FK)
    """
    __tablename__ = "organizations"
    __table_args__ = {"sqlite_autoincrement": True}

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    code = db.Column(db.String(32), nullable=True, unique=True, index=True)  # Short code for lookups

    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.func.now(),
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.func.now(),
        onupdate=db.func.now(),
    )

    def __repr__(self) -> str:
        return f"<Organization id={self.id} name={self.name!r}>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "is_active": self.is_active,
            "created_at": to_utc_z(self.created_at),
            "updated_at": to_utc_z(self.updated_at),
        }

class Store(db.Model):
    """
    Store within an organization.

    MULTI-TENANT: Stores are scoped to organizations via org_id.
    Store names and codes are unique within an organization, not globally.
    """
    __tablename__ = "stores"
    __table_args__ = (
        db.UniqueConstraint("org_id", "name", name="uq_stores_org_name"),
        db.UniqueConstraint("org_id", "code", name="uq_stores_org_code"),
        db.Index("ix_stores_org_id", "org_id"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    code = db.Column(db.String(32), nullable=True, index=True)
    parent_store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=True, index=True)

    # Store-level configuration
    timezone = db.Column(db.String(64), nullable=False, default='UTC')
    tax_rate_bps = db.Column(db.Integer, nullable=False, default=0)  # Basis points (e.g., 825 = 8.25%)

    version_id = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.func.now(),
    )

    organization = db.relationship("Organization", backref=db.backref("stores", lazy=True))
    parent_store = db.relationship("Store", remote_side=[id], backref=db.backref("child_stores", lazy=True))

    __mapper_args__ = {"version_id_col": version_id}

    def __repr__(self) -> str:
        return f"<Store id={self.id} name={self.name!r} org_id={self.org_id}>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "org_id": self.org_id,
            "name": self.name,
            "code": self.code,
            "parent_store_id": self.parent_store_id,
            "timezone": self.timezone,
            "tax_rate_bps": self.tax_rate_bps,
            "version_id": self.version_id,
            "created_at": to_utc_z(self.created_at),
        }

class StoreConfig(db.Model):
    __tablename__ = "store_configs"
    __table_args__ = (
        db.UniqueConstraint("store_id", "key", name="uq_store_configs_store_key"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False, index=True)
    key = db.Column(db.String(128), nullable=False)
    value = db.Column(db.Text, nullable=True)
    version_id = db.Column(db.Integer, nullable=False, default=1)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now(), onupdate=db.func.now())

    store = db.relationship("Store", backref=db.backref("configs", lazy=True))

    __mapper_args__ = {"version_id_col": version_id}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "store_id": self.store_id,
            "key": self.key,
            "value": self.value,
            "version_id": self.version_id,
            "created_at": to_utc_z(self.created_at),
            "updated_at": to_utc_z(self.updated_at),
        }
