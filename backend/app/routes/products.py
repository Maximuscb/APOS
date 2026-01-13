# backend/app/routes/products.py
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

PRODUCT_POLICY = ModelValidationPolicy(
    writable_fields={"sku", "name", "description", "price_cents", "is_active"},
    required_on_create={"sku", "name"},
)

products_bp = Blueprint("products", __name__, url_prefix="/api/products")


@products_bp.get("/status")
def products_status():
    return get_products_module_status()


@products_bp.get("")
def list_products():
    store_id = request.args.get("store_id", type=int)  # optional
    items = list_products_service(store_id=store_id)
    return {
        "items": items,
        "count": len(items),
    }

@products_bp.post("")
def create_product_route():
    payload = request.get_json(silent=True) or {}

    try:
        patch = validate_payload(model=Product, payload=payload, policy=PRODUCT_POLICY, partial=False)
        enforce_rules_product(patch)
    except ValidationError as e:
        return {"error": str(e)}, 400

    from ..services.products_service import create_product

    try:
        created = create_product(patch=patch)
    except ConflictError as e:
        return {"error": str(e)}, 409

    return created, 201


@products_bp.delete("/<int:product_id>")
def delete_product_route(product_id: int):
    from ..services.products_service import delete_product  # local import

    deleted = delete_product(product_id=product_id)
    if not deleted:
        return {"error": "Product not found"}, 404

    return {"ok": True}, 200

@products_bp.put("/<int:product_id>")
def update_product_route(product_id: int):
    payload = request.get_json(silent=True) or {}

    try:
        patch = validate_payload(model=Product, payload=payload, policy=PRODUCT_POLICY, partial=True)
        enforce_rules_product(patch)
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


