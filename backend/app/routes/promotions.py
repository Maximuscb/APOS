from __future__ import annotations

from flask import Blueprint, jsonify, request, g

from ..decorators import require_auth, require_any_permission
from ..services import promotions_service

promotions_bp = Blueprint("promotions", __name__, url_prefix="/api/promotions")


@promotions_bp.route("", methods=["GET"])
@require_auth
@require_any_permission("VIEW_PROMOTIONS", "MANAGE_PROMOTIONS")
def list_promotions():
    store_id = request.args.get("store_id", type=int) or g.store_id
    active_only = request.args.get("active_only", "false").lower() == "true"
    result = promotions_service.list_promotions(g.org_id, store_id, active_only)
    return jsonify(result)


@promotions_bp.route("", methods=["POST"])
@require_auth
@require_any_permission("MANAGE_PROMOTIONS")
def create_promotion():
    data = request.get_json() or {}
    required = ("name", "promo_type", "discount_value")
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400
    result = promotions_service.create_promotion(g.org_id, data, g.current_user.id)
    return jsonify(result), 201


@promotions_bp.route("/<int:promo_id>", methods=["PATCH"])
@require_auth
@require_any_permission("MANAGE_PROMOTIONS")
def update_promotion(promo_id: int):
    data = request.get_json() or {}
    result = promotions_service.update_promotion(promo_id, data)
    if not result:
        return jsonify({"error": "Not found"}), 404
    return jsonify(result)


@promotions_bp.route("/active", methods=["GET"])
@require_auth
def get_active_promotions():
    store_id = request.args.get("store_id", type=int) or g.store_id
    result = promotions_service.get_active_promotions(g.org_id, store_id)
    return jsonify(result)
