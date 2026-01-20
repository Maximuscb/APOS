# Overview: Flask API routes for stores operations; parses input and returns JSON responses.

from flask import Blueprint, jsonify, request

from app.decorators import require_auth, require_permission
from app.services import store_service, permission_service
from flask import g


stores_bp = Blueprint("stores", __name__, url_prefix="/api/stores")


@stores_bp.get("")
@require_auth
@require_permission("VIEW_STORES")
def list_stores():
    stores = store_service.list_stores()
    return jsonify([store.to_dict() for store in stores]), 200


@stores_bp.post("")
@require_auth
@require_permission("MANAGE_STORES")
def create_store():
    data = request.get_json()
    try:
        store = store_service.create_store(
            name=data.get("name"),
            code=data.get("code"),
            parent_store_id=data.get("parent_store_id"),
        )
        return jsonify(store.to_dict()), 201
    except store_service.StoreError as exc:
        return jsonify({"error": str(exc)}), 400


@stores_bp.get("/<int:store_id>")
@require_auth
@require_permission("VIEW_STORES")
def get_store(store_id: int):
    store = store_service.get_store(store_id)
    if not store:
        return jsonify({"error": "Store not found"}), 404
    return jsonify(store.to_dict()), 200


@stores_bp.put("/<int:store_id>")
@require_auth
@require_permission("MANAGE_STORES")
def update_store(store_id: int):
    data = request.get_json()
    try:
        store = store_service.update_store(
            store_id,
            name=data.get("name"),
            code=data.get("code"),
            parent_store_id=data.get("parent_store_id"),
        )
        return jsonify(store.to_dict()), 200
    except store_service.StoreError as exc:
        return jsonify({"error": str(exc)}), 400


@stores_bp.get("/<int:store_id>/configs")
@require_auth
@require_permission("VIEW_STORES")
def list_store_configs(store_id: int):
    configs = store_service.get_store_configs(store_id)
    return jsonify([config.to_dict() for config in configs]), 200


@stores_bp.put("/<int:store_id>/configs")
@require_auth
@require_permission("MANAGE_STORES")
def set_store_config(store_id: int):
    data = request.get_json()
    key = data.get("key")
    value = data.get("value")
    if key == "cash_drawer_approval_mode":
        if not permission_service.user_has_permission(g.current_user.id, "SYSTEM_ADMIN"):
            return jsonify({"error": "System admin permission required"}), 403
        if value is not None and value.upper() not in ["MANAGER_ONLY", "DUAL_AUTH"]:
            return jsonify({"error": "Invalid cash_drawer_approval_mode value"}), 400
    try:
        config = store_service.set_store_config(store_id, key, value)
        return jsonify(config.to_dict()), 200
    except store_service.StoreError as exc:
        return jsonify({"error": str(exc)}), 400


@stores_bp.get("/<int:store_id>/tree")
@require_auth
@require_permission("VIEW_STORES")
def get_store_tree(store_id: int):
    try:
        tree = store_service.get_store_tree(store_id)
        return jsonify(tree), 200
    except store_service.StoreError as exc:
        return jsonify({"error": str(exc)}), 400
