from __future__ import annotations

from flask import Blueprint, jsonify, request, g

from ..decorators import require_auth, require_any_permission
from ..services import communications_service

communications_bp = Blueprint("communications", __name__, url_prefix="/api/communications")


# --- Active (login popup) ---

@communications_bp.route("/active", methods=["GET"])
@require_auth
def get_active():
    store_id = request.args.get("store_id", type=int) or g.store_id
    result = communications_service.get_active_communications(g.org_id, store_id)
    return jsonify(result)


# --- Announcements ---

@communications_bp.route("/announcements", methods=["GET"])
@require_auth
@require_any_permission("VIEW_COMMUNICATIONS", "MANAGE_COMMUNICATIONS")
def list_announcements():
    store_id = request.args.get("store_id", type=int) or g.store_id
    result = communications_service.list_announcements(g.org_id, store_id)
    return jsonify(result)


@communications_bp.route("/announcements", methods=["POST"])
@require_auth
@require_any_permission("MANAGE_COMMUNICATIONS")
def create_announcement():
    data = request.get_json() or {}
    if not data.get("title") or not data.get("body"):
        return jsonify({"error": "title and body are required"}), 400
    result = communications_service.create_announcement(g.org_id, data, g.current_user.id)
    return jsonify(result), 201


@communications_bp.route("/announcements/<int:ann_id>", methods=["PATCH"])
@require_auth
@require_any_permission("MANAGE_COMMUNICATIONS")
def update_announcement(ann_id: int):
    data = request.get_json() or {}
    result = communications_service.update_announcement(ann_id, data)
    if not result:
        return jsonify({"error": "Not found"}), 404
    return jsonify(result)


# --- Reminders ---

@communications_bp.route("/reminders", methods=["GET"])
@require_auth
@require_any_permission("VIEW_COMMUNICATIONS", "MANAGE_COMMUNICATIONS")
def list_reminders():
    store_id = request.args.get("store_id", type=int) or g.store_id
    result = communications_service.list_reminders(g.org_id, store_id)
    return jsonify(result)


@communications_bp.route("/reminders", methods=["POST"])
@require_auth
@require_any_permission("MANAGE_COMMUNICATIONS")
def create_reminder():
    data = request.get_json() or {}
    if not data.get("title") or not data.get("body"):
        return jsonify({"error": "title and body are required"}), 400
    result = communications_service.create_reminder(g.org_id, data, g.current_user.id)
    return jsonify(result), 201


@communications_bp.route("/reminders/<int:rem_id>", methods=["PATCH"])
@require_auth
@require_any_permission("MANAGE_COMMUNICATIONS")
def update_reminder(rem_id: int):
    data = request.get_json() or {}
    result = communications_service.update_reminder(rem_id, data)
    if not result:
        return jsonify({"error": "Not found"}), 404
    return jsonify(result)


# --- Tasks ---

@communications_bp.route("/tasks", methods=["GET"])
@require_auth
@require_any_permission("VIEW_COMMUNICATIONS", "MANAGE_COMMUNICATIONS")
def list_tasks():
    store_id = request.args.get("store_id", type=int) or g.store_id
    status = request.args.get("status")
    assigned_to = request.args.get("assigned_to_user_id", type=int)
    result = communications_service.list_tasks(g.org_id, store_id, status, assigned_to)
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
@require_any_permission("VIEW_COMMUNICATIONS", "MANAGE_COMMUNICATIONS")
def update_task(task_id: int):
    data = request.get_json() or {}
    result = communications_service.update_task(task_id, data)
    if not result:
        return jsonify({"error": "Not found"}), 404
    return jsonify(result)
