from __future__ import annotations

from ..extensions import db
from app.time_utils import to_utc_z


class Customer(db.Model):
    """
    Customer master data for tracking purchases and loyalty.

    MULTI-TENANT: Customers are scoped to organizations via org_id.
    A customer may optionally be associated with a specific store, or
    be org-wide (store_id=NULL).

    WHY: Enables customer lifetime value tracking, repeat purchase
    analysis, and loyalty/rewards programs.
    """
    __tablename__ = "customers"
    __table_args__ = (
        db.UniqueConstraint("org_id", "email", name="uq_customers_org_email"),
        db.Index("ix_customers_org_id", "org_id"),
        db.Index("ix_customers_org_active", "org_id", "is_active"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=True, index=True)

    first_name = db.Column(db.String(128), nullable=False)
    last_name = db.Column(db.String(128), nullable=False)
    email = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(32), nullable=True)

    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)

    # Denormalized aggregates (updated when sales are completed)
    total_spent_cents = db.Column(db.Integer, nullable=False, default=0)
    total_visits = db.Column(db.Integer, nullable=False, default=0)
    last_visit_at = db.Column(db.DateTime(timezone=True), nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now(), onupdate=db.func.now())
    version_id = db.Column(db.Integer, nullable=False, default=1)

    organization = db.relationship("Organization", backref=db.backref("customers", lazy=True))
    store = db.relationship("Store", backref=db.backref("customers", lazy=True))
    __mapper_args__ = {"version_id_col": version_id}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "org_id": self.org_id,
            "store_id": self.store_id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "phone": self.phone,
            "is_active": self.is_active,
            "total_spent_cents": self.total_spent_cents,
            "total_visits": self.total_visits,
            "last_visit_at": to_utc_z(self.last_visit_at) if self.last_visit_at else None,
            "created_at": to_utc_z(self.created_at),
            "updated_at": to_utc_z(self.updated_at),
            "version_id": self.version_id,
        }


class CustomerRewardAccount(db.Model):
    """
    Loyalty/rewards account for a customer.

    WHY: Tracks points balance and lifetime earning/redemption.
    One account per customer per org.
    """
    __tablename__ = "customer_reward_accounts"
    __table_args__ = (
        db.UniqueConstraint("customer_id", name="uq_reward_accounts_customer"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False, index=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True)

    points_balance = db.Column(db.Integer, nullable=False, default=0)
    lifetime_points_earned = db.Column(db.Integer, nullable=False, default=0)
    lifetime_points_redeemed = db.Column(db.Integer, nullable=False, default=0)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now(), onupdate=db.func.now())
    version_id = db.Column(db.Integer, nullable=False, default=1)

    customer = db.relationship("Customer", backref=db.backref("reward_account", uselist=False, lazy=True))
    organization = db.relationship("Organization", backref=db.backref("reward_accounts", lazy=True))
    __mapper_args__ = {"version_id_col": version_id}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "org_id": self.org_id,
            "points_balance": self.points_balance,
            "lifetime_points_earned": self.lifetime_points_earned,
            "lifetime_points_redeemed": self.lifetime_points_redeemed,
            "created_at": to_utc_z(self.created_at),
            "updated_at": to_utc_z(self.updated_at),
            "version_id": self.version_id,
        }


class CustomerRewardTransaction(db.Model):
    """
    Append-only ledger of reward point events.

    TRANSACTION TYPES:
    - EARN: Points earned from a sale
    - REDEEM: Points redeemed for a discount
    - ADJUST: Manual adjustment by manager
    - EXPIRE: Points expired per policy

    IMMUTABLE: Records are never updated or deleted.
    """
    __tablename__ = "customer_reward_transactions"
    __table_args__ = (
        db.Index("ix_reward_txns_account_occurred", "reward_account_id", "occurred_at"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    reward_account_id = db.Column(db.Integer, db.ForeignKey("customer_reward_accounts.id"), nullable=False, index=True)

    transaction_type = db.Column(db.String(16), nullable=False, index=True)  # EARN, REDEEM, ADJUST, EXPIRE
    points = db.Column(db.Integer, nullable=False)  # Positive for earn, negative for redeem/expire

    sale_id = db.Column(db.Integer, db.ForeignKey("sales.id"), nullable=True, index=True)
    reason = db.Column(db.String(255), nullable=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    occurred_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now(), index=True)

    reward_account = db.relationship("CustomerRewardAccount", backref=db.backref("transactions", lazy=True))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "reward_account_id": self.reward_account_id,
            "transaction_type": self.transaction_type,
            "points": self.points,
            "sale_id": self.sale_id,
            "reason": self.reason,
            "user_id": self.user_id,
            "occurred_at": to_utc_z(self.occurred_at),
        }
