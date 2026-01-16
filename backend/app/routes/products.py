# backend/app/routes/products.py
"""
Product management routes.

SECURITY: All routes require authentication.
- Read operations require VIEW_INVENTORY permission
- Write operations require MANAGE_PRODUCTS permission
"""
from flask import Blueprint, request
from ..services.products_service import (
    list_products as list_products_service,
    get_products_module_status,
)
from ..models import Product
from ..validation import (
    ModelValidationPolicy,
    validate_payload,
    enforce_rules_product,
    ValidationError,
    ConflictError,
)
from ..decorators import require_auth, require_permission

PRODUCT_POLICY = ModelValidationPolicy(
    writable_fields={"sku", "name", "description", "price_cents", "is_active"},
    required_on_create={"sku", "name"},
)

# Maximum price: $10,000,000.00 (1 billion cents)
MAX_PRICE_CENTS = 1_000_000_000

products_bp = Blueprint("products", __name__, url_prefix="/api/products")


@products_bp.get("/status")
@require_auth
def products_status():
    """Get product module status (requires authentication)."""
    return get_products_module_status()


@products_bp.get("")
@require_auth
@require_permission("VIEW_INVENTORY")
def list_products():
    """
    List all products.

    Query params:
    - store_id: int (optional) - filter by store
    """
    store_id = request.args.get("store_id", type=int)  # optional
    items = list_products_service(store_id=store_id)
    return {
        "items": items,
        "count": len(items),
    }


@products_bp.post("")
@require_auth
@require_permission("MANAGE_PRODUCTS")
def create_product_route():
    """
    Create a new product.

    Requires MANAGE_PRODUCTS permission.
    """
    payload = request.get_json(silent=True) or {}

    try:
        patch = validate_payload(model=Product, payload=payload, policy=PRODUCT_POLICY, partial=False)
        enforce_rules_product(patch)

        # Validate max price
        if "price_cents" in patch and patch["price_cents"] is not None:
            if patch["price_cents"] > MAX_PRICE_CENTS:
                return {"error": f"Price cannot exceed ${MAX_PRICE_CENTS / 100:,.2f}"}, 400
            if patch["price_cents"] < 0:
                return {"error": "Price cannot be negative"}, 400

    except ValidationError as e:
        return {"error": str(e)}, 400

    from ..services.products_service import create_product

    try:
        created = create_product(patch=patch)
    except ConflictError as e:
        return {"error": str(e)}, 409

    return created, 201


@products_bp.delete("/<int:product_id>")
@require_auth
@require_permission("MANAGE_PRODUCTS")
def delete_product_route(product_id: int):
    """
    Delete a product.

    Requires MANAGE_PRODUCTS permission.
    """
    from ..services.products_service import delete_product  # local import

    deleted = delete_product(product_id=product_id)
    if not deleted:
        return {"error": "Product not found"}, 404

    return {"ok": True}, 200


@products_bp.put("/<int:product_id>")
@require_auth
@require_permission("MANAGE_PRODUCTS")
def update_product_route(product_id: int):
    """
    Update a product.

    Requires MANAGE_PRODUCTS permission.
    """
    payload = request.get_json(silent=True) or {}

    try:
        patch = validate_payload(model=Product, payload=payload, policy=PRODUCT_POLICY, partial=True)
        enforce_rules_product(patch)

        # Validate max price
        if "price_cents" in patch and patch["price_cents"] is not None:
            if patch["price_cents"] > MAX_PRICE_CENTS:
                return {"error": f"Price cannot exceed ${MAX_PRICE_CENTS / 100:,.2f}"}, 400
            if patch["price_cents"] < 0:
                return {"error": "Price cannot be negative"}, 400

    except ValidationError as e:
        return {"error": str(e)}, 400

    from ..services.products_service import update_product

    try:
        updated = update_product(product_id=product_id, patch=patch)
    except ConflictError as e:
        return {"error": str(e)}, 409

    if not updated:
        return {"error": "Product not found"}, 404

    return updated, 200


