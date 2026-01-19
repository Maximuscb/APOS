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

# NOTE: MAX_PRICE_CENTS is now defined in validation.py and enforced by enforce_rules_product()

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
    List all products with optional pagination.

    Query params:
    - store_id: int (optional) - filter by store
    - page: int (optional) - page number (1-indexed). If omitted, returns all items.
    - per_page: int (optional) - items per page (default 20, max 100)
    """
    store_id = request.args.get("store_id", type=int)
    page = request.args.get("page", type=int)
    per_page = request.args.get("per_page", type=int)

    result = list_products_service(store_id=store_id, page=page, per_page=per_page)
    return result


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
        enforce_rules_product(patch)  # Handles price validation including max check
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
        enforce_rules_product(patch)  # Handles price validation including max check
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


