from __future__ import annotations

from ..extensions import db
from app.time_utils import to_utc_z


class Promotion(db.Model):
    """
    Promotions and discounts.

    Can be org-wide (store_id=NULL) or store-specific.
    Supports percentage, fixed amount, BOGO, and bundle types.
    """
    __tablename__ = "promotions"
    __table_args__ = {"sqlite_autoincrement": True}

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=True, index=True)

    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)

    promo_type = db.Column(db.String(32), nullable=False)  # PERCENTAGE, FIXED_AMOUNT, BOGO, BUNDLE
    discount_value = db.Column(db.Integer, nullable=False, default=0)  # cents for FIXED_AMOUNT, basis points for PERCENTAGE

    applies_to = db.Column(db.String(32), nullable=False, default="ALL_PRODUCTS")  # ALL_PRODUCTS, CATEGORY, SPECIFIC_PRODUCTS
    product_ids = db.Column(db.Text, nullable=True)  # JSON array of product IDs when applies_to=SPECIFIC_PRODUCTS

    min_quantity = db.Column(db.Integer, nullable=True)
    min_amount_cents = db.Column(db.Integer, nullable=True)

    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)

    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)

    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now(), onupdate=db.func.now())

    version_id = db.Column(db.Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version_id}

    def to_dict(self):
        return {
            "id": self.id,
            "org_id": self.org_id,
            "store_id": self.store_id,
            "name": self.name,
            "description": self.description,
            "promo_type": self.promo_type,
            "discount_value": self.discount_value,
            "applies_to": self.applies_to,
            "product_ids": self.product_ids,
            "min_quantity": self.min_quantity,
            "min_amount_cents": self.min_amount_cents,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "is_active": self.is_active,
            "created_by_user_id": self.created_by_user_id,
            "created_at": to_utc_z(self.created_at),
            "updated_at": to_utc_z(self.updated_at),
        }
