from __future__ import annotations

from flask import Blueprint, jsonify, request, g

from ..decorators import require_auth, require_any_permission
from ..services import settings_service, permission_service
from ..models import Register

settings_bp = Blueprint("settings", __name__, url_prefix="/api")

def _is_global_operator() -> bool:
    return bool(getattr(g.current_user, "is_developer", False)) or permission_service.user_has_permission(g.current_user.id, "SYSTEM_ADMIN")


@settings_bp.route("/organizations/<int:org_id>/settings", methods=["GET"])
@require_auth
@require_any_permission("MANAGE_ORGANIZATION", "VIEW_ORGANIZATION")
def get_org_settings(org_id: int):
    if g.org_id != org_id:
        return jsonify({"error": "Access denied"}), 403
    settings = settings_service.get_org_settings(org_id)
    return jsonify(settings)


@settings_bp.route("/organizations/<int:org_id>/settings", methods=["PUT"])
@require_auth
@require_any_permission("MANAGE_ORGANIZATION")
def upsert_org_setting(org_id: int):
    if g.org_id != org_id:
        return jsonify({"error": "Access denied"}), 403
    data = request.get_json() or {}
    key = data.get("key")
    value = data.get("value")
    if not key:
        return jsonify({"error": "key is required"}), 400
    result = settings_service.upsert_org_setting(org_id, key, value, g.current_user.id)
    return jsonify(result)


@settings_bp.route("/devices/<int:device_id>/settings", methods=["GET"])
@require_auth
@require_any_permission("VIEW_DEVICE_SETTINGS", "MANAGE_DEVICE_SETTINGS")
def get_device_settings(device_id: int):
    device = Register.query.filter_by(id=device_id, org_id=g.org_id).first()
    if not device:
        return jsonify({"error": "Device not found"}), 404
    if g.store_id and g.store_id != device.store_id and not _is_global_operator():
        return jsonify({"error": "Access denied"}), 403
    settings = settings_service.get_device_settings(device_id, g.org_id)
    return jsonify(settings)


@settings_bp.route("/devices/<int:device_id>/settings", methods=["PUT"])
@require_auth
@require_any_permission("MANAGE_DEVICE_SETTINGS")
def upsert_device_setting(device_id: int):
    data = request.get_json() or {}
    key = data.get("key")
    value = data.get("value")
    if not key:
        return jsonify({"error": "key is required"}), 400
    device = Register.query.filter_by(id=device_id, org_id=g.org_id).first()
    if not device:
        return jsonify({"error": "Device not found"}), 404
    if g.store_id and g.store_id != device.store_id and not _is_global_operator():
        return jsonify({"error": "Access denied"}), 403
    result = settings_service.upsert_device_setting(device_id, g.org_id, key, value, g.current_user.id)
    return jsonify(result)
