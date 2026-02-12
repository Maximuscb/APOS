from __future__ import annotations

from flask import Blueprint, jsonify, request, g

from ..decorators import require_auth, require_any_permission
from ..models import Task
from ..services import communications_service
from ..services.user_store_access_service import user_can_manage_store

communications_bp = Blueprint("communications", __name__, url_prefix="/api/communications")


def _resolve_store_id() -> int | None:
    return request.args.get("store_id", type=int) or g.store_id


@communications_bp.route("/active", methods=["GET"])
@require_auth
def get_active():
    store_id = _resolve_store_id()
    result = communications_service.get_active_communications(g.org_id, g.current_user.id, store_id)
    return jsonify(result)


@communications_bp.route("/notifications", methods=["GET"])
@require_auth
@require_any_permission("VIEW_COMMUNICATIONS", "MANAGE_COMMUNICATIONS")
def list_notifications():
    store_id = _resolve_store_id()
    result = communications_service.list_notifications(g.org_id, store_id)
    return jsonify(result)


@communications_bp.route("/notifications", methods=["POST"])
@require_auth
@require_any_permission("MANAGE_COMMUNICATIONS")
def create_notification():
    data = request.get_json() or {}
    if not data.get("title") or not data.get("body"):
        return jsonify({"error": "title and body are required"}), 400

    comm_type = (data.get("communication_type") or "ANNOUNCEMENT").upper().strip()
    try:
        if comm_type == "ANNOUNCEMENT":
            result = communications_service.create_announcement(g.org_id, data, g.current_user.id)
            return jsonify({"kind": "ANNOUNCEMENT", **result}), 201
        if comm_type == "REMINDER":
            result = communications_service.create_reminder(g.org_id, data, g.current_user.id)
            return jsonify({"kind": "REMINDER", **result}), 201
        return jsonify({"error": "communication_type must be ANNOUNCEMENT or REMINDER"}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@communications_bp.route("/notifications/<kind>/<int:notification_id>", methods=["PATCH"])
@require_auth
@require_any_permission("MANAGE_COMMUNICATIONS")
def update_notification(kind: str, notification_id: int):
    data = request.get_json() or {}
    normalized = (kind or "").upper().strip()
    try:
        if normalized == "ANNOUNCEMENT":
            result = communications_service.update_announcement(notification_id, data)
        elif normalized == "REMINDER":
            result = communications_service.update_reminder(notification_id, data)
        else:
            return jsonify({"error": "kind must be ANNOUNCEMENT or REMINDER"}), 400
        if not result:
            return jsonify({"error": "Not found"}), 404
        return jsonify({"kind": normalized, **result})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@communications_bp.route("/notifications/<kind>/<int:notification_id>/dismiss", methods=["POST"])
@require_auth
def dismiss_notification(kind: str, notification_id: int):
    try:
        result = communications_service.dismiss_notification(
            org_id=g.org_id,
            user_id=g.current_user.id,
            kind=kind,
            communication_id=notification_id,
        )
        return jsonify(result), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


# Legacy endpoints retained for compatibility with existing screens.
@communications_bp.route("/announcements", methods=["GET"])
@require_auth
@require_any_permission("VIEW_COMMUNICATIONS", "MANAGE_COMMUNICATIONS")
def list_announcements():
    store_id = _resolve_store_id()
    return jsonify(communications_service.list_announcements(g.org_id, store_id))


@communications_bp.route("/announcements", methods=["POST"])
@require_auth
@require_any_permission("MANAGE_COMMUNICATIONS")
def create_announcement():
    data = request.get_json() or {}
    if not data.get("title") or not data.get("body"):
        return jsonify({"error": "title and body are required"}), 400
    try:
        result = communications_service.create_announcement(g.org_id, data, g.current_user.id)
        return jsonify(result), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@communications_bp.route("/announcements/<int:ann_id>", methods=["PATCH"])
@require_auth
@require_any_permission("MANAGE_COMMUNICATIONS")
def update_announcement(ann_id: int):
    data = request.get_json() or {}
    try:
        result = communications_service.update_announcement(ann_id, data)
        if not result:
            return jsonify({"error": "Not found"}), 404
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@communications_bp.route("/reminders", methods=["GET"])
@require_auth
@require_any_permission("VIEW_COMMUNICATIONS", "MANAGE_COMMUNICATIONS")
def list_reminders():
    store_id = _resolve_store_id()
    return jsonify(communications_service.list_reminders(g.org_id, store_id))


@communications_bp.route("/reminders", methods=["POST"])
@require_auth
@require_any_permission("MANAGE_COMMUNICATIONS")
def create_reminder():
    data = request.get_json() or {}
    if not data.get("title") or not data.get("body"):
        return jsonify({"error": "title and body are required"}), 400
    try:
        result = communications_service.create_reminder(g.org_id, data, g.current_user.id)
        return jsonify(result), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@communications_bp.route("/reminders/<int:rem_id>", methods=["PATCH"])
@require_auth
@require_any_permission("MANAGE_COMMUNICATIONS")
def update_reminder(rem_id: int):
    data = request.get_json() or {}
    try:
        result = communications_service.update_reminder(rem_id, data)
        if not result:
            return jsonify({"error": "Not found"}), 404
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@communications_bp.route("/tasks", methods=["GET"])
@require_auth
def list_tasks():
    store_id = _resolve_store_id()
    status = request.args.get("status")
    assigned_to = request.args.get("assigned_to_user_id", type=int)
    assigned_to_register_id = request.args.get("assigned_to_register_id", type=int)

    can_manage = bool(getattr(g.current_user, "is_developer", False)) or (user_can_manage_store(g.current_user.id, store_id) if store_id else True)
    if can_manage and request.args.get("mine") != "true":
        result = communications_service.list_tasks(
            g.org_id,
            store_id,
            status,
            assigned_to,
            assigned_to_register_id=assigned_to_register_id,
        )
        return jsonify(result)

    result = communications_service.list_tasks_for_user(
        org_id=g.org_id,
        user_id=g.current_user.id,
        store_id=store_id,
        register_id=assigned_to_register_id,
    )
    if status:
        result = [r for r in result if (r.get("status") or "").upper() == status.upper()]
    return jsonify(result)


@communications_bp.route("/tasks", methods=["POST"])
@require_auth
@require_any_permission("MANAGE_COMMUNICATIONS")
def create_task():
    data = request.get_json() or {}
    if not data.get("title"):
        return jsonify({"error": "title is required"}), 400
    result = communications_service.create_task(g.org_id, data, g.current_user.id)
    return jsonify(result), 201


@communications_bp.route("/tasks/<int:task_id>", methods=["PATCH"])
@require_auth
def update_task(task_id: int):
    data = request.get_json() or {}
    task = Task.query.filter_by(id=task_id, org_id=g.org_id).first()
    if not task:
        return jsonify({"error": "Not found"}), 404

    is_manage = bool(getattr(g.current_user, "is_developer", False)) or (user_can_manage_store(g.current_user.id, task.store_id) if task.store_id else False)
    is_assignee = task.assigned_to_user_id == g.current_user.id
    if not is_manage and not is_assignee:
        return jsonify({"error": "Forbidden"}), 403

    if not is_manage:
        # Non-managers may only resolve their task state.
        allowed = {"status", "deferred_reason"}
        unknown = [k for k in data.keys() if k not in allowed]
        if unknown:
            return jsonify({"error": "Only status and deferred_reason can be updated"}), 403

    try:
        result = communications_service.update_task(task_id, data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(result)
