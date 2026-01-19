# backend/app/services/products_service.py
"""
Products Service with Multi-Tenant Support

MULTI-TENANT: All product operations are tenant-scoped.
- list_products requires org_id to filter stores
- create_product requires validated store_id within tenant
- update_product and delete_product validate store ownership
"""
from __future__ import annotations
from flask import g
from ..extensions import db
from ..models import Product, Store
from ..validation import ConflictError
from ..services.ledger_service import append_ledger_event
from ..services.tenant_service import require_store_in_org, get_org_store_ids, TenantAccessError
from app.time_utils import utcnow

PRODUCT_MUTABLE_FIELDS = {"sku", "name", "description", "price_cents", "is_active"}


def apply_product_patch(p: Product, patch: dict) -> None:
    for k, v in patch.items():
        if k not in PRODUCT_MUTABLE_FIELDS:
            continue
        setattr(p, k, v)


def list_products(
    org_id: int | None = None,
    store_id: int | None = None,
    page: int | None = None,
    per_page: int | None = None,
) -> dict:
    """
    Tenant-scoped product listing with optional pagination.

    MULTI-TENANT: Products are filtered to stores within the organization.
    If store_id is provided, it must belong to the organization.

    Args:
        org_id: Organization ID for tenant scoping (uses g.org_id if None)
        store_id: Filter by specific store (must belong to org)
        page: Page number (1-indexed). If None, returns all items.
        per_page: Items per page (default 20, max 100)

    Returns:
        Dict with 'items', 'count', and pagination metadata if paginated.

    Raises:
        TenantAccessError: If store_id doesn't belong to org
    """
    # Get org_id from context if not provided
    if org_id is None:
        org_id = getattr(g, 'org_id', None)

    if org_id is None:
        # Fallback for backwards compatibility during migration
        # In production, org_id should always be set
        default_store = db.session.query(Store).order_by(Store.id.asc()).first()
        if default_store is None:
            return {"items": [], "count": 0}
        store_id = default_store.id
        store_ids = {store_id}
    else:
        # MULTI-TENANT: Get stores for this organization
        store_ids = get_org_store_ids(org_id)

        if not store_ids:
            return {"items": [], "count": 0}

        # If specific store requested, validate it belongs to org
        if store_id is not None:
            require_store_in_org(store_id, org_id)
            store_ids = {store_id}

    # Build query filtered to tenant's stores
    base_query = (
        db.session.query(Product)
        .filter(Product.store_id.in_(store_ids))
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


def create_product(*, patch: dict, org_id: int | None = None, store_id: int | None = None) -> dict:
    """
    Create product using a validated patch dict.

    MULTI-TENANT: Product is created in a store belonging to the organization.
    If store_id is provided, it must belong to the organization.

    Args:
        patch: Product data (sku, name, etc.)
        org_id: Organization ID (uses g.org_id if None)
        store_id: Store ID to create product in (uses first org store if None)

    Returns:
        Created product dict

    Raises:
        TenantAccessError: If store_id doesn't belong to org
        ConflictError: If SKU already exists in the store
    """
    # Get org_id from context if not provided
    if org_id is None:
        org_id = getattr(g, 'org_id', None)

    # Determine which store to use
    if store_id is not None:
        if org_id is not None:
            # Validate store belongs to org
            store = require_store_in_org(store_id, org_id)
        else:
            store = db.session.query(Store).filter_by(id=store_id).first()
            if not store:
                raise ValueError("Store not found")
    else:
        # Use first store in org (or first store overall for backwards compat)
        if org_id is not None:
            store = db.session.query(Store).filter_by(org_id=org_id).order_by(Store.id.asc()).first()
        else:
            store = db.session.query(Store).order_by(Store.id.asc()).first()

        if store is None:
            raise ValueError("No store available. Create a store first.")

    # SKU uniqueness (store_id, sku)
    sku = patch.get("sku")
    if sku is None:
        raise ValueError("sku is required")

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

def delete_product(*, product_id: int, org_id: int | None = None) -> bool:
    """
    Soft-delete a product.

    MULTI-TENANT: Validates product belongs to a store in the organization.

    Args:
        product_id: Product ID to delete
        org_id: Organization ID (uses g.org_id if None)

    Returns:
        True if deleted, False if not found

    Raises:
        TenantAccessError: If product belongs to different org
    """
    # Get org_id from context if not provided
    if org_id is None:
        org_id = getattr(g, 'org_id', None)

    p = db.session.query(Product).filter(Product.id == product_id).first()
    if not p:
        return False

    # MULTI-TENANT: Verify product's store belongs to org
    if org_id is not None:
        require_store_in_org(p.store_id, org_id)

    # Soft-delete only: preserve IDs and historical references.
    if p.is_active:
        p.is_active = False

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

def update_product(*, product_id: int, patch: dict, org_id: int | None = None) -> dict | None:
    """
    Update a product.

    MULTI-TENANT: Validates product belongs to a store in the organization.

    Args:
        product_id: Product ID to update
        patch: Fields to update
        org_id: Organization ID (uses g.org_id if None)

    Returns:
        Updated product dict, or None if not found

    Raises:
        TenantAccessError: If product belongs to different org
        ConflictError: If new SKU already exists in store
    """
    # Get org_id from context if not provided
    if org_id is None:
        org_id = getattr(g, 'org_id', None)

    p = db.session.query(Product).filter(Product.id == product_id).first()
    if not p:
        return None

    # MULTI-TENANT: Verify product's store belongs to org
    if org_id is not None:
        require_store_in_org(p.store_id, org_id)

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



