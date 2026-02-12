from __future__ import annotations

from datetime import datetime

from sqlalchemy import or_

from ..extensions import db
from ..models import (
    Announcement,
    Reminder,
    Task,
    CommunicationDismissal,
    UserRole,
    Role,
)
from app.time_utils import utcnow


TARGET_USER = "USER"
TARGET_STORE = "STORE"
TARGET_ORG = "ORG"
TARGET_ROLE = "ROLE"
VALID_TARGET_TYPES = {TARGET_USER, TARGET_STORE, TARGET_ORG, TARGET_ROLE}

KIND_ANNOUNCEMENT = "ANNOUNCEMENT"
KIND_REMINDER = "REMINDER"
VALID_NOTIFICATION_KINDS = {KIND_ANNOUNCEMENT, KIND_REMINDER}


def _normalize_target_scope(data: dict) -> tuple[str, int | None, int | None]:
    """
    Normalize target scope from request payload to USER/STORE/ORG only.
    """
    target_type = (data.get("target_type") or "").upper().strip() or TARGET_STORE
    target_id = data.get("target_id")
    store_id = data.get("store_id")

    # Legacy compatibility: ALL -> ORG, STORE with target_id missing -> use store_id.
    if target_type == "ALL":
        target_type = TARGET_ORG
    if target_type == TARGET_STORE and target_id is None and store_id is not None:
        target_id = store_id

    if target_type not in VALID_TARGET_TYPES:
        raise ValueError("target_type must be USER, STORE, or ORG")

    if target_type in {TARGET_USER, TARGET_STORE, TARGET_ROLE} and not target_id:
        raise ValueError("target_id is required for USER, STORE, and ROLE target_type")

    if target_type == TARGET_ORG:
        target_id = None
        store_id = None
    elif target_type == TARGET_STORE:
        store_id = int(target_id)
    elif target_type == TARGET_ROLE:
        # ROLE with store_id set means role recipients in that store.
        store_id = int(store_id) if store_id is not None else None

    return target_type, (int(target_id) if target_id is not None else None), (int(store_id) if store_id is not None else None)


def _user_role_names(user_id: int) -> set[str]:
    rows = (
        db.session.query(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .filter(UserRole.user_id == user_id)
        .all()
    )
    return {r[0] for r in rows}


def _notification_visible_to_user(item: dict, *, user_id: int, store_id: int | None) -> bool:
    target_type = (item.get("target_type") or "").upper()
    target_id = item.get("target_id")
    item_store_id = item.get("store_id")

    if not item.get("is_active", True):
        return False

    expires_at = item.get("expires_at")
    if expires_at:
        try:
            if datetime.fromisoformat(expires_at.replace("Z", "+00:00")) < utcnow().replace(tzinfo=None):
                return False
        except Exception:
            pass

    if target_type == TARGET_ORG:
        return True
    if target_type == TARGET_STORE:
        return bool(store_id and target_id and int(target_id) == int(store_id))
    if target_type == TARGET_USER:
        return bool(target_id and int(target_id) == int(user_id))
    if target_type == TARGET_ROLE:
        if not target_id:
            return False
        role_ids = (
            db.session.query(UserRole.role_id)
            .filter(UserRole.user_id == user_id)
            .all()
        )
        role_id_set = {r[0] for r in role_ids}
        if int(target_id) not in role_id_set:
            return False
        # Optional store scoping for role recipients
        if item_store_id is not None:
            return bool(store_id and int(item_store_id) == int(store_id))
        return True

    # Legacy fallback behavior for older records.
    if target_type == "STORE":
        return bool(store_id and ((item_store_id is None) or int(item_store_id) == int(store_id)))
    if target_type == "ALL":
        return True
    return False


def _notification_to_dict(kind: str, payload: dict) -> dict:
    return {
        "kind": kind,
        "id": payload["id"],
        "title": payload["title"],
        "body": payload["body"],
        "priority": payload.get("priority", "NORMAL"),
        "target_type": payload.get("target_type"),
        "target_id": payload.get("target_id"),
        "store_id": payload.get("store_id"),
        "is_active": payload.get("is_active", True),
        "created_at": payload.get("created_at"),
        "updated_at": payload.get("updated_at"),
        "expires_at": payload.get("expires_at"),
        "display_type": payload.get("display_type", "LOGIN_BANNER"),
    }


def list_announcements(org_id: int, store_id: int | None = None, active_only: bool = False) -> list[dict]:
    q = db.session.query(Announcement).filter_by(org_id=org_id)
    if store_id:
        q = q.filter((Announcement.store_id == store_id) | (Announcement.store_id.is_(None)))
    if active_only:
        q = q.filter_by(is_active=True)
    return [a.to_dict() for a in q.order_by(Announcement.created_at.desc()).all()]


def create_announcement(org_id: int, data: dict, user_id: int) -> dict:
    target_type, target_id, store_id = _normalize_target_scope(data)
    ann = Announcement(
        org_id=org_id,
        store_id=store_id,
        title=data["title"],
        body=data["body"],
        priority=data.get("priority", "NORMAL"),
        created_by_user_id=user_id,
        target_type=target_type,
        target_id=target_id,
        display_type=data.get("display_type", "LOGIN_BANNER"),
        expires_at=data.get("expires_at"),
        is_active=bool(data.get("is_active", True)),
    )
    db.session.add(ann)
    db.session.commit()
    return ann.to_dict()


def update_announcement(announcement_id: int, data: dict) -> dict | None:
    ann = db.session.query(Announcement).filter_by(id=announcement_id).first()
    if not ann:
        return None

    if "target_type" in data or "target_id" in data or "store_id" in data:
        target_type, target_id, store_id = _normalize_target_scope({
            "target_type": data.get("target_type", ann.target_type),
            "target_id": data.get("target_id", ann.target_id),
            "store_id": data.get("store_id", ann.store_id),
        })
        ann.target_type = target_type
        ann.target_id = target_id
        ann.store_id = store_id

    for key in ("title", "body", "priority", "is_active", "expires_at"):
        if key in data:
            setattr(ann, key, data[key])
    db.session.commit()
    return ann.to_dict()


def list_reminders(org_id: int, store_id: int | None = None) -> list[dict]:
    q = db.session.query(Reminder).filter_by(org_id=org_id)
    if store_id:
        q = q.filter((Reminder.store_id == store_id) | (Reminder.store_id.is_(None)))
    return [r.to_dict() for r in q.order_by(Reminder.created_at.desc()).all()]


def create_reminder(org_id: int, data: dict, user_id: int) -> dict:
    target_type, target_id, store_id = _normalize_target_scope(data)
    rem = Reminder(
        org_id=org_id,
        store_id=store_id,
        title=data["title"],
        body=data["body"],
        created_by_user_id=user_id,
        target_type=target_type,
        target_id=target_id,
        repeat_type=data.get("repeat_type", "ONCE"),
        repeat_until=data.get("repeat_until"),
        display_type=data.get("display_type", "LOGIN_BANNER"),
        is_active=bool(data.get("is_active", True)),
    )
    db.session.add(rem)
    db.session.commit()
    return rem.to_dict()


def update_reminder(reminder_id: int, data: dict) -> dict | None:
    rem = db.session.query(Reminder).filter_by(id=reminder_id).first()
    if not rem:
        return None

    if "target_type" in data or "target_id" in data or "store_id" in data:
        target_type, target_id, store_id = _normalize_target_scope({
            "target_type": data.get("target_type", rem.target_type),
            "target_id": data.get("target_id", rem.target_id),
            "store_id": data.get("store_id", rem.store_id),
        })
        rem.target_type = target_type
        rem.target_id = target_id
        rem.store_id = store_id

    for key in ("title", "body", "repeat_type", "repeat_until", "is_active"):
        if key in data:
            setattr(rem, key, data[key])
    db.session.commit()
    return rem.to_dict()


def list_notifications(org_id: int, store_id: int | None = None) -> list[dict]:
    notifications: list[dict] = []
    notifications.extend(
        [_notification_to_dict(KIND_ANNOUNCEMENT, a) for a in list_announcements(org_id, store_id=store_id)]
    )
    notifications.extend(
        [_notification_to_dict(KIND_REMINDER, r) for r in list_reminders(org_id, store_id=store_id)]
    )
    notifications.sort(key=lambda n: n.get("created_at") or "", reverse=True)
    return notifications


def get_active_notifications_for_user(org_id: int, user_id: int, store_id: int | None = None) -> list[dict]:
    dismissals = db.session.query(CommunicationDismissal).filter_by(org_id=org_id, user_id=user_id).all()
    dismissed_keys = {(d.communication_kind, d.communication_id) for d in dismissals}

    all_notifications = list_notifications(org_id, store_id=store_id)
    visible = []
    for n in all_notifications:
        key = (n["kind"], n["id"])
        if key in dismissed_keys:
            continue
        if _notification_visible_to_user(n, user_id=user_id, store_id=store_id):
            visible.append(n)
    return visible


def dismiss_notification(org_id: int, user_id: int, kind: str, communication_id: int) -> dict:
    normalized_kind = (kind or "").upper().strip()
    if normalized_kind not in VALID_NOTIFICATION_KINDS:
        raise ValueError("kind must be ANNOUNCEMENT or REMINDER")

    existing = db.session.query(CommunicationDismissal).filter_by(
        org_id=org_id,
        user_id=user_id,
        communication_kind=normalized_kind,
        communication_id=communication_id,
    ).first()
    if existing:
        return existing.to_dict()

    row = CommunicationDismissal(
        org_id=org_id,
        user_id=user_id,
        communication_kind=normalized_kind,
        communication_id=communication_id,
    )
    db.session.add(row)
    db.session.commit()
    return row.to_dict()


def list_tasks(
    org_id: int,
    store_id: int | None = None,
    status: str | None = None,
    assigned_to_user_id: int | None = None,
    assigned_to_register_id: int | None = None,
) -> list[dict]:
    q = db.session.query(Task).filter_by(org_id=org_id)
    if store_id:
        q = q.filter((Task.store_id == store_id) | (Task.store_id.is_(None)))
    if status:
        q = q.filter_by(status=status)
    if assigned_to_user_id:
        q = q.filter_by(assigned_to_user_id=assigned_to_user_id)
    if assigned_to_register_id:
        q = q.filter_by(assigned_to_register_id=assigned_to_register_id)
    return [t.to_dict() for t in q.order_by(Task.created_at.desc()).all()]


def list_tasks_for_user(org_id: int, user_id: int, store_id: int | None = None, register_id: int | None = None) -> list[dict]:
    q = db.session.query(Task).filter(Task.org_id == org_id)
    if store_id:
        q = q.filter(or_(Task.store_id == store_id, Task.store_id.is_(None)))
    q = q.filter(
        or_(
            Task.assigned_to_user_id == user_id,
            Task.assigned_to_register_id == register_id if register_id else sa_false(),
            (Task.assigned_to_user_id.is_(None) & Task.assigned_to_register_id.is_(None)),
        )
    )
    return [t.to_dict() for t in q.order_by(Task.created_at.desc()).all()]


def pending_tasks_for_clockout(org_id: int, user_id: int, store_id: int | None = None) -> list[dict]:
    q = db.session.query(Task).filter(
        Task.org_id == org_id,
        Task.status == "PENDING",
        Task.assigned_to_user_id == user_id,
    )
    if store_id:
        q = q.filter(or_(Task.store_id == store_id, Task.store_id.is_(None)))
    return [t.to_dict() for t in q.order_by(Task.created_at.desc()).all()]


def create_task(org_id: int, data: dict, user_id: int) -> dict:
    task = Task(
        org_id=org_id,
        store_id=data.get("store_id"),
        title=data["title"],
        description=data.get("description"),
        created_by_user_id=user_id,
        assigned_to_user_id=data.get("assigned_to_user_id"),
        assigned_to_register_id=data.get("assigned_to_register_id"),
        task_type=data.get("task_type", "USER"),
        due_at=data.get("due_at"),
    )
    db.session.add(task)
    db.session.commit()
    return task.to_dict()


def update_task(task_id: int, data: dict) -> dict | None:
    task = db.session.query(Task).filter_by(id=task_id).first()
    if not task:
        return None

    for key in ("title", "description", "assigned_to_user_id", "assigned_to_register_id", "task_type", "due_at"):
        if key in data:
            setattr(task, key, data[key])

    if "status" in data:
        status = (data["status"] or "").upper().strip()
        if status not in {"PENDING", "COMPLETED", "DEFERRED"}:
            raise ValueError("status must be PENDING, COMPLETED, or DEFERRED")
        task.status = status
        if status == "COMPLETED":
            task.completed_at = utcnow()
            task.deferred_reason = None
        elif status == "DEFERRED":
            task.completed_at = None
            task.deferred_reason = data.get("deferred_reason")
        else:
            task.completed_at = None
            task.deferred_reason = None

    if "deferred_reason" in data and task.status == "DEFERRED":
        task.deferred_reason = data.get("deferred_reason")

    db.session.commit()
    return task.to_dict()


def get_active_communications(org_id: int, user_id: int, store_id: int | None = None) -> dict:
    notifications = get_active_notifications_for_user(org_id=org_id, user_id=user_id, store_id=store_id)
    return {"notifications": notifications}


def sa_false():
    # Avoid importing sqlalchemy.sql.false at module import time for lightweight service load.
    from sqlalchemy.sql import false
    return false()
