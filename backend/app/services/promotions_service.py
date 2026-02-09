from __future__ import annotations

from ..extensions import db
from ..models import Promotion


def list_promotions(org_id: int, store_id: int | None = None, active_only: bool = False) -> list[dict]:
    q = db.session.query(Promotion).filter_by(org_id=org_id)
    if store_id:
        q = q.filter((Promotion.store_id == store_id) | (Promotion.store_id.is_(None)))
    if active_only:
        q = q.filter_by(is_active=True)
    return [p.to_dict() for p in q.order_by(Promotion.created_at.desc()).all()]


def create_promotion(org_id: int, data: dict, user_id: int) -> dict:
    promo = Promotion(
        org_id=org_id,
        store_id=data.get('store_id'),
        name=data['name'],
        description=data.get('description'),
        promo_type=data['promo_type'],
        discount_value=data['discount_value'],
        applies_to=data.get('applies_to', 'ALL_PRODUCTS'),
        product_ids=data.get('product_ids'),
        min_quantity=data.get('min_quantity'),
        min_amount_cents=data.get('min_amount_cents'),
        start_date=data.get('start_date'),
        end_date=data.get('end_date'),
        created_by_user_id=user_id,
    )
    db.session.add(promo)
    db.session.commit()
    return promo.to_dict()


def update_promotion(promo_id: int, data: dict) -> dict | None:
    promo = db.session.query(Promotion).filter_by(id=promo_id).first()
    if not promo:
        return None
    for key in ('name', 'description', 'promo_type', 'discount_value', 'applies_to',
                'product_ids', 'min_quantity', 'min_amount_cents', 'start_date', 'end_date', 'is_active'):
        if key in data:
            setattr(promo, key, data[key])
    db.session.commit()
    return promo.to_dict()


def get_active_promotions(org_id: int, store_id: int | None = None) -> list[dict]:
    return list_promotions(org_id, store_id, active_only=True)
