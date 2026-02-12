from __future__ import annotations

from flask import Blueprint, jsonify, request, g

from ..decorators import require_auth
from ..services import settings_service, permission_service
from ..services.settings_service import (
    SettingsAuthorizationError,
    SettingsValidationError,
    SettingsNotFoundError,
    SCOPE_ORG,
    SCOPE_STORE,
    SCOPE_DEVICE,
    SCOPE_USER,
)
from ..models import Register, Store, User


settings_bp = Blueprint("settings", __name__, url_prefix="/api")


def _actor():
    return settings_service.make_actor(user_id=g.current_user.id)


def _parse_updates(payload: dict) -> list[dict]:
    if isinstance(payload.get("updates"), list):
        return payload["updates"]
    key = payload.get("key")
    if not key:
        return []
    return [
        {
            "key": key,
            "value_json": payload.get("value_json", payload.get("value")),
            "unset": bool(payload.get("unset", False)),
        }
    ]


def _scope_org(scope_type: str, scope_id: int) -> int | None:
    if scope_type == SCOPE_ORG:
        return scope_id
    if scope_type == SCOPE_STORE:
        store = Store.query.filter_by(id=scope_id).first()
        return store.org_id if store else None
    if scope_type == SCOPE_DEVICE:
        device = Register.query.filter_by(id=scope_id).first()
        return device.org_id if device else None
    if scope_type == SCOPE_USER:
        user = User.query.filter_by(id=scope_id).first()
        return user.org_id if user else None
    return None


def _json_error(exc: Exception):
    if isinstance(exc, SettingsValidationError):
        return jsonify({"error": str(exc)}), 400
    if isinstance(exc, SettingsAuthorizationError):
        return jsonify({"error": str(exc)}), 403
    if isinstance(exc, SettingsNotFoundError):
        return jsonify({"error": str(exc)}), 404
    return jsonify({"error": "Internal server error"}), 500


@settings_bp.get("/settings/registry")
@require_auth
def get_settings_registry():
    actor = _actor()
    # Visibility: managers+ for org-wide settings pages, but registry itself can be
    # loaded by authenticated users; edit permissions are enforced per key/scope.
    data = settings_service.list_registry(actor)
    return jsonify({"items": data, "count": len(data)})


@settings_bp.get("/settings/effective")
@require_auth
def get_effective_settings():
    actor = _actor()
    org_id = g.org_id
    store_id = request.args.get("store_id", type=int) or g.store_id
    device_id = request.args.get("device_id", type=int)
    user_id = request.args.get("user_id", type=int) or g.current_user.id

    # Cross-user reads require VIEW_USERS.
    if user_id != g.current_user.id and not (
        actor.is_developer or permission_service.user_has_permission(g.current_user.id, "VIEW_USERS")
    ):
        return jsonify({"error": "Access denied"}), 403

    # Tenant guard
    for scope_type, scope_id in [(SCOPE_STORE, store_id), (SCOPE_DEVICE, device_id), (SCOPE_USER, user_id)]:
        if not scope_id:
            continue
        scoped_org = _scope_org(scope_type, scope_id)
        if scoped_org is None:
            return jsonify({"error": f"{scope_type.title()} not found"}), 404
        if scoped_org != org_id:
            return jsonify({"error": "Cross-organization access denied"}), 403

    effective = settings_service.resolve_effective_settings(
        org_id=org_id,
        store_id=store_id,
        device_id=device_id,
        user_id=user_id,
        include_sensitive=False,
        include_developer=actor.is_developer,
    )
    return jsonify(
        {
            "org_id": org_id,
            "store_id": store_id,
            "device_id": device_id,
            "user_id": user_id,
            "effective": effective,
            "count": len(effective),
        }
    )


@settings_bp.get("/settings/org/<int:org_id>")
@require_auth
def get_org_scope_settings(org_id: int):
    try:
        data = settings_service.get_scope_settings(actor=_actor(), scope_type=SCOPE_ORG, scope_id=org_id)
        return jsonify(data)
    except Exception as exc:
        return _json_error(exc)


@settings_bp.get("/settings/org/current")
@require_auth
def get_current_org_scope_settings():
    try:
        data = settings_service.get_scope_settings(actor=_actor(), scope_type=SCOPE_ORG, scope_id=g.org_id)
        return jsonify(data)
    except Exception as exc:
        return _json_error(exc)


@settings_bp.get("/settings/store/<int:store_id>")
@require_auth
def get_store_scope_settings(store_id: int):
    try:
        data = settings_service.get_scope_settings(actor=_actor(), scope_type=SCOPE_STORE, scope_id=store_id)
        return jsonify(data)
    except Exception as exc:
        return _json_error(exc)


@settings_bp.get("/settings/device/<int:device_id>")
@require_auth
def get_device_scope_settings(device_id: int):
    try:
        data = settings_service.get_scope_settings(actor=_actor(), scope_type=SCOPE_DEVICE, scope_id=device_id)
        return jsonify(data)
    except Exception as exc:
        return _json_error(exc)


@settings_bp.get("/settings/user/<int:user_id>")
@require_auth
def get_user_scope_settings(user_id: int):
    try:
        data = settings_service.get_scope_settings(actor=_actor(), scope_type=SCOPE_USER, scope_id=user_id)
        return jsonify(data)
    except Exception as exc:
        return _json_error(exc)


@settings_bp.patch("/settings/org/<int:org_id>")
@settings_bp.put("/settings/org/<int:org_id>")
@require_auth
def patch_org_scope_settings(org_id: int):
    payload = request.get_json(silent=True) or {}
    updates = _parse_updates(payload)
    if not updates:
        return jsonify({"error": "updates are required"}), 400
    try:
        result = settings_service.bulk_upsert_scope_settings(
            actor=_actor(),
            scope_type=SCOPE_ORG,
            scope_id=org_id,
            updates=updates,
            source=payload.get("source", "UI"),
            change_reason=payload.get("change_reason"),
            request_metadata_json=payload.get("request_metadata_json"),
        )
        status = 200 if not result["errors"] else 400
        return jsonify(result), status
    except Exception as exc:
        return _json_error(exc)


@settings_bp.patch("/settings/org/current")
@settings_bp.put("/settings/org/current")
@require_auth
def patch_current_org_scope_settings():
    payload = request.get_json(silent=True) or {}
    updates = _parse_updates(payload)
    if not updates:
        return jsonify({"error": "updates are required"}), 400
    try:
        result = settings_service.bulk_upsert_scope_settings(
            actor=_actor(),
            scope_type=SCOPE_ORG,
            scope_id=g.org_id,
            updates=updates,
            source=payload.get("source", "UI"),
            change_reason=payload.get("change_reason"),
            request_metadata_json=payload.get("request_metadata_json"),
        )
        status = 200 if not result["errors"] else 400
        return jsonify(result), status
    except Exception as exc:
        return _json_error(exc)


@settings_bp.patch("/settings/store/<int:store_id>")
@settings_bp.put("/settings/store/<int:store_id>")
@require_auth
def patch_store_scope_settings(store_id: int):
    payload = request.get_json(silent=True) or {}
    updates = _parse_updates(payload)
    if not updates:
        return jsonify({"error": "updates are required"}), 400
    try:
        result = settings_service.bulk_upsert_scope_settings(
            actor=_actor(),
            scope_type=SCOPE_STORE,
            scope_id=store_id,
            updates=updates,
            source=payload.get("source", "UI"),
            change_reason=payload.get("change_reason"),
            request_metadata_json=payload.get("request_metadata_json"),
        )
        status = 200 if not result["errors"] else 400
        return jsonify(result), status
    except Exception as exc:
        return _json_error(exc)


@settings_bp.patch("/settings/device/<int:device_id>")
@settings_bp.put("/settings/device/<int:device_id>")
@require_auth
def patch_device_scope_settings(device_id: int):
    payload = request.get_json(silent=True) or {}
    updates = _parse_updates(payload)
    if not updates:
        return jsonify({"error": "updates are required"}), 400
    try:
        result = settings_service.bulk_upsert_scope_settings(
            actor=_actor(),
            scope_type=SCOPE_DEVICE,
            scope_id=device_id,
            updates=updates,
            source=payload.get("source", "UI"),
            change_reason=payload.get("change_reason"),
            request_metadata_json=payload.get("request_metadata_json"),
        )
        status = 200 if not result["errors"] else 400
        return jsonify(result), status
    except Exception as exc:
        return _json_error(exc)


@settings_bp.patch("/settings/user/<int:user_id>")
@settings_bp.put("/settings/user/<int:user_id>")
@require_auth
def patch_user_scope_settings(user_id: int):
    payload = request.get_json(silent=True) or {}
    updates = _parse_updates(payload)
    if not updates:
        return jsonify({"error": "updates are required"}), 400
    try:
        result = settings_service.bulk_upsert_scope_settings(
            actor=_actor(),
            scope_type=SCOPE_USER,
            scope_id=user_id,
            updates=updates,
            source=payload.get("source", "UI"),
            change_reason=payload.get("change_reason"),
            request_metadata_json=payload.get("request_metadata_json"),
        )
        status = 200 if not result["errors"] else 400
        return jsonify(result), status
    except Exception as exc:
        return _json_error(exc)


# -----------------------------------------------------------------------------
# Legacy endpoints kept for backward compatibility
# -----------------------------------------------------------------------------

@settings_bp.route("/organizations/<int:org_id>/settings", methods=["GET"])
@require_auth
def get_org_settings_legacy(org_id: int):
    if g.org_id != org_id and not getattr(g.current_user, "is_developer", False):
        return jsonify({"error": "Access denied"}), 403
    settings = settings_service.get_org_settings(org_id)
    return jsonify(settings)


@settings_bp.route("/organizations/<int:org_id>/settings", methods=["PUT"])
@require_auth
def upsert_org_setting_legacy(org_id: int):
    if g.org_id != org_id and not getattr(g.current_user, "is_developer", False):
        return jsonify({"error": "Access denied"}), 403
    if not permission_service.user_has_permission(g.current_user.id, "MANAGE_ORGANIZATION"):
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
def get_device_settings_legacy(device_id: int):
    if not permission_service.user_has_permission(g.current_user.id, "VIEW_DEVICE_SETTINGS"):
        return jsonify({"error": "Access denied"}), 403
    device = Register.query.filter_by(id=device_id, org_id=g.org_id).first()
    if not device:
        return jsonify({"error": "Device not found"}), 404
    settings = settings_service.get_device_settings(device_id, g.org_id)
    return jsonify(settings)


@settings_bp.route("/devices/<int:device_id>/settings", methods=["PUT"])
@require_auth
def upsert_device_setting_legacy(device_id: int):
    if not permission_service.user_has_permission(g.current_user.id, "MANAGE_DEVICE_SETTINGS"):
        return jsonify({"error": "Access denied"}), 403
    data = request.get_json() or {}
    key = data.get("key")
    value = data.get("value")
    if not key:
        return jsonify({"error": "key is required"}), 400
    device = Register.query.filter_by(id=device_id, org_id=g.org_id).first()
    if not device:
        return jsonify({"error": "Device not found"}), 404
    result = settings_service.upsert_device_setting(device_id, g.org_id, key, value, g.current_user.id)
    return jsonify(result)
