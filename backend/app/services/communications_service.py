from __future__ import annotations

from ..extensions import db
from ..models import Announcement, Reminder, Task


# --- Announcements ---

def list_announcements(org_id: int, store_id: int | None = None, active_only: bool = False) -> list[dict]:
    q = db.session.query(Announcement).filter_by(org_id=org_id)
    if store_id:
        q = q.filter((Announcement.store_id == store_id) | (Announcement.store_id.is_(None)))
    if active_only:
        q = q.filter_by(is_active=True)
    return [a.to_dict() for a in q.order_by(Announcement.created_at.desc()).all()]


def create_announcement(org_id: int, data: dict, user_id: int) -> dict:
    ann = Announcement(
        org_id=org_id,
        store_id=data.get('store_id'),
        title=data['title'],
        body=data['body'],
        priority=data.get('priority', 'NORMAL'),
        created_by_user_id=user_id,
        target_type=data.get('target_type', 'ALL'),
        target_id=data.get('target_id'),
        display_type=data.get('display_type', 'LOGIN_POPUP'),
    )
    db.session.add(ann)
    db.session.commit()
    return ann.to_dict()


def update_announcement(announcement_id: int, data: dict) -> dict | None:
    ann = db.session.query(Announcement).filter_by(id=announcement_id).first()
    if not ann:
        return None
    for key in ('title', 'body', 'priority', 'target_type', 'target_id', 'is_active', 'expires_at'):
        if key in data:
            setattr(ann, key, data[key])
    db.session.commit()
    return ann.to_dict()


# --- Reminders ---

def list_reminders(org_id: int, store_id: int | None = None) -> list[dict]:
    q = db.session.query(Reminder).filter_by(org_id=org_id)
    if store_id:
        q = q.filter((Reminder.store_id == store_id) | (Reminder.store_id.is_(None)))
    return [r.to_dict() for r in q.order_by(Reminder.created_at.desc()).all()]


def create_reminder(org_id: int, data: dict, user_id: int) -> dict:
    rem = Reminder(
        org_id=org_id,
        store_id=data.get('store_id'),
        title=data['title'],
        body=data['body'],
        created_by_user_id=user_id,
        target_type=data.get('target_type', 'ALL'),
        target_id=data.get('target_id'),
        repeat_type=data.get('repeat_type', 'ONCE'),
        repeat_until=data.get('repeat_until'),
        display_type=data.get('display_type', 'LOGIN_POPUP'),
    )
    db.session.add(rem)
    db.session.commit()
    return rem.to_dict()


def update_reminder(reminder_id: int, data: dict) -> dict | None:
    rem = db.session.query(Reminder).filter_by(id=reminder_id).first()
    if not rem:
        return None
    for key in ('title', 'body', 'target_type', 'target_id', 'repeat_type', 'repeat_until', 'is_active'):
        if key in data:
            setattr(rem, key, data[key])
    db.session.commit()
    return rem.to_dict()


# --- Tasks ---

def list_tasks(org_id: int, store_id: int | None = None, status: str | None = None, assigned_to_user_id: int | None = None) -> list[dict]:
    q = db.session.query(Task).filter_by(org_id=org_id)
    if store_id:
        q = q.filter((Task.store_id == store_id) | (Task.store_id.is_(None)))
    if status:
        q = q.filter_by(status=status)
    if assigned_to_user_id:
        q = q.filter_by(assigned_to_user_id=assigned_to_user_id)
    return [t.to_dict() for t in q.order_by(Task.created_at.desc()).all()]


def create_task(org_id: int, data: dict, user_id: int) -> dict:
    task = Task(
        org_id=org_id,
        store_id=data.get('store_id'),
        title=data['title'],
        description=data.get('description'),
        created_by_user_id=user_id,
        assigned_to_user_id=data.get('assigned_to_user_id'),
        assigned_to_register_id=data.get('assigned_to_register_id'),
        task_type=data.get('task_type', 'USER'),
        due_at=data.get('due_at'),
    )
    db.session.add(task)
    db.session.commit()
    return task.to_dict()


def update_task(task_id: int, data: dict) -> dict | None:
    task = db.session.query(Task).filter_by(id=task_id).first()
    if not task:
        return None
    for key in ('title', 'description', 'status', 'deferred_reason', 'assigned_to_user_id', 'assigned_to_register_id', 'due_at', 'completed_at'):
        if key in data:
            setattr(task, key, data[key])
    db.session.commit()
    return task.to_dict()


# --- Active communications for login popup ---

def get_active_communications(org_id: int, store_id: int | None = None) -> dict:
    announcements = list_announcements(org_id, store_id, active_only=True)
    reminders = list_reminders(org_id, store_id)
    active_reminders = [r for r in reminders if r.get('is_active')]
    return {
        'announcements': announcements,
        'reminders': active_reminders,
    }
