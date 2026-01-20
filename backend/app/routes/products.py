# Overview: Flask API routes for products operations; parses input and returns JSON responses.

# backend/app/routes/products.py
"""
Product management routes with multi-tenant support.

MULTI-TENANT: All product operations are scoped to the caller's organization.
The org_id is derived from g.org_id (set by @require_auth).

SECURITY: All routes require authentication.
- Read operations require VIEW_INVENTORY permission
- Write operations require MANAGE_PRODUCTS permission
"""
from flask import Blueprint, request, g
from ..services.products_service import (
    list_products as list_products_service,
    get_products_module_status,
)
from ..services.tenant_service import TenantAccessError
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

    MULTI-TENANT: Products are filtered to the caller's organization.
    If store_id is provided, it must belong to the caller's organization.

    Query params:
    - store_id: int (optional) - filter by store (must belong to caller's org)
    - page: int (optional) - page number (1-indexed). If omitted, returns all items.
    - per_page: int (optional) - items per page (default 20, max 100)
    """
    store_id = request.args.get("store_id", type=int)
    page = request.args.get("page", type=int)
    per_page = request.args.get("per_page", type=int)

    try:
        result = list_products_service(
            org_id=g.org_id,
            store_id=store_id,
            page=page,
            per_page=per_page
        )
        return result
    except TenantAccessError as e:
        return {"error": "Store not found"}, 404


@products_bp.post("")
@require_auth
@require_permission("MANAGE_PRODUCTS")
def create_product_route():
    """
    Create a new product.

    MULTI-TENANT: Product is created in the caller's organization.
    If store_id is provided in payload, it must belong to caller's org.

    Requires MANAGE_PRODUCTS permission.
    """
    payload = request.get_json(silent=True) or {}

    try:
        patch = validate_payload(model=Product, payload=payload, policy=PRODUCT_POLICY, partial=False)
        enforce_rules_product(patch)  # Handles price validation including max check
    except ValidationError as e:
        return {"error": str(e)}, 400

    from ..services.products_service import create_product

    # Extract store_id from payload if provided
    store_id = payload.get("store_id")

    try:
        created = create_product(patch=patch, org_id=g.org_id, store_id=store_id)
    except ConflictError as e:
        return {"error": str(e)}, 409
    except TenantAccessError as e:
        return {"error": "Store not found"}, 404
    except ValueError as e:
        return {"error": str(e)}, 400

    return created, 201


@products_bp.delete("/<int:product_id>")
@require_auth
@require_permission("MANAGE_PRODUCTS")
def delete_product_route(product_id: int):
    """
    Delete a product.

    MULTI-TENANT: Only products in caller's organization can be deleted.

    Requires MANAGE_PRODUCTS permission.
    """
    from ..services.products_service import delete_product

    try:
        deleted = delete_product(product_id=product_id, org_id=g.org_id)
    except TenantAccessError:
        return {"error": "Product not found"}, 404

    if not deleted:
        return {"error": "Product not found"}, 404

    return {"ok": True}, 200


@products_bp.put("/<int:product_id>")
@require_auth
@require_permission("MANAGE_PRODUCTS")
def update_product_route(product_id: int):
    """
    Update a product.

    MULTI-TENANT: Only products in caller's organization can be updated.

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
        updated = update_product(product_id=product_id, patch=patch, org_id=g.org_id)
    except ConflictError as e:
        return {"error": str(e)}, 409
    except TenantAccessError:
        return {"error": "Product not found"}, 404

    if not updated:
        return {"error": "Product not found"}, 404

    return updated, 200


