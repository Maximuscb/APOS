# backend/app/services/products_service.py
from __future__ import annotations
from ..extensions import db
from ..models import Product, Store
from ..validation import ConflictError
from ..services.ledger_service import append_ledger_event
from app.time_utils import utcnow

PRODUCT_MUTABLE_FIELDS = {"sku", "name", "description", "price_cents", "is_active"}

def apply_product_patch(p: Product, patch: dict) -> None:
    for k, v in patch.items():
        if k not in PRODUCT_MUTABLE_FIELDS:
            continue
        setattr(p, k, v)

def list_products(
    store_id: int | None = None,
    page: int | None = None,
    per_page: int | None = None,
) -> dict:
    """
    Real DB-backed product listing with optional pagination.

    Args:
        store_id: Filter by store (uses first store if None)
        page: Page number (1-indexed). If None, returns all items.
        per_page: Items per page (default 20, max 100)

    Returns:
        Dict with 'items', 'count', and pagination metadata if paginated.
    """
    # Default store resolution: if no store_id provided, pick the first store.
    if store_id is None:
        default_store = db.session.query(Store).order_by(Store.id.asc()).first()
        if default_store is None:
            return {"items": [], "count": 0}
        store_id = default_store.id

    base_query = (
        db.session.query(Product)
        .filter(Product.store_id == store_id)
        .order_by(Product.name.asc(), Product.id.asc())
    )

    # If no pagination requested, return all items
    if page is None:
        products = base_query.all()
        return {
            "items": [p.to_dict() for p in products],
            "count": len(products),
        }

    # Pagination logic
    per_page = min(per_page or 20, 100)  # Default 20, max 100
    page = max(page, 1)  # Ensure page >= 1

    total = base_query.count()
    total_pages = (total + per_page - 1) // per_page if total > 0 else 1

    products = base_query.offset((page - 1) * per_page).limit(per_page).all()

    return {
        "items": [p.to_dict() for p in products],
        "count": len(products),
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        },
    }


def create_product(*, patch: dict) -> dict:
    """
    Create using a validated patch dict.
    Expects patch includes at least sku and name (enforced by validation layer).
    """
    store = db.session.query(Store).order_by(Store.id.asc()).first()
    if store is None:
        store = Store(name="Default Store")
        db.session.add(store)
        db.session.commit()

    # SKU uniqueness (store_id, sku)
    sku = patch.get("sku")
    if sku is None:
        raise ValueError("sku is required")  # should not happen if validated

    existing = (
        db.session.query(Product)
        .filter(Product.store_id == store.id, Product.sku == sku)
        .first()
    )
    if existing:
        raise ConflictError("SKU already exists for this store.")

    p = Product(store_id=store.id)
    apply_product_patch(p, patch)

    db.session.add(p)
    db.session.flush()  # ensure p.id exists before ledger append

    from ..services.ledger_service import append_ledger_event
    from app.time_utils import utcnow

    append_ledger_event(
        store_id=p.store_id,
        event_type="product.created",
        event_category="product",
        entity_type="product",
        entity_id=p.id,
        occurred_at=utcnow(),
        note=f"Created product sku={p.sku} name={p.name}",
    )

    db.session.commit()
    return p.to_dict()


def get_products_module_status() -> dict:
    """
    A tiny status payload the frontend can use to confirm module wiring.
    """
    return {
    "module": "products",
    "status": "db-ready",
    "notes": "Product model exists; list endpoint can query DB (may be empty until seeded).",
    }

def delete_product(*, product_id: int) -> bool:
    p = db.session.query(Product).filter(Product.id == product_id).first()
    if not p:
        return False

    # Soft-delete only: preserve IDs and historical references.
    if p.is_active:
        p.is_active = False

        # Append audit event in the same transaction.
        from ..services.ledger_service import append_ledger_event
        from app.time_utils import utcnow

        append_ledger_event(
            store_id=p.store_id,
            event_type="product.deactivated",
            event_category="product",
            entity_type="product",
            entity_id=p.id,
            occurred_at=utcnow(),
            note=f"Soft-deleted (is_active=false) product sku={p.sku}",
        )

    db.session.commit()
    return True

def update_product(*, product_id: int, patch: dict) -> dict | None:
    p = db.session.query(Product).filter(Product.id == product_id).first()
    if not p:
        return None

    # SKU uniqueness enforcement if changing SKU
    if "sku" in patch and patch["sku"] != p.sku:
        sku = patch["sku"]
        existing = (
            db.session.query(Product)
            .filter(
                Product.store_id == p.store_id,
                Product.sku == sku,
                Product.id != p.id,
            )
            .first()
        )
        if existing:
            raise ConflictError("SKU already exists for this store.")

    apply_product_patch(p, patch)
    append_ledger_event(
        store_id=p.store_id,
        event_type="product.updated",
        event_category="product",
        entity_type="product",
        entity_id=p.id,
        occurred_at=utcnow(),
        note=f"Updated fields: {', '.join(sorted(patch.keys()))}",
    )
    db.session.commit()
    return p.to_dict()



