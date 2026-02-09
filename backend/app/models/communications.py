from __future__ import annotations

from ..extensions import db
from app.time_utils import to_utc_z


class Announcement(db.Model):
    """
    Push announcements from admins/managers to users.

    Display via pop-up screen on login.
    Admins may push to any user/register.
    Managers may push to any non-manager/register.
    """
    __tablename__ = "announcements"
    __table_args__ = {"sqlite_autoincrement": True}

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=True, index=True)

    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    priority = db.Column(db.String(16), nullable=False, default="NORMAL")  # LOW, NORMAL, HIGH, URGENT

    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    target_type = db.Column(db.String(16), nullable=False, default="ALL")  # ALL, STORE, USER, ROLE
    target_id = db.Column(db.Integer, nullable=True)  # user_id or role_id depending on target_type

    display_type = db.Column(db.String(32), nullable=False, default="LOGIN_POPUP")
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now(), onupdate=db.func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "org_id": self.org_id,
            "store_id": self.store_id,
            "title": self.title,
            "body": self.body,
            "priority": self.priority,
            "created_by_user_id": self.created_by_user_id,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "display_type": self.display_type,
            "is_active": self.is_active,
            "expires_at": to_utc_z(self.expires_at),
            "created_at": to_utc_z(self.created_at),
            "updated_at": to_utc_z(self.updated_at),
        }


class Reminder(db.Model):
    """
    Scheduled reminders pushed to users.

    May be scheduled to repeat over a specified period.
    Display via pop-up screen on login.
    """
    __tablename__ = "reminders"
    __table_args__ = {"sqlite_autoincrement": True}

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=True, index=True)

    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)

    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    target_type = db.Column(db.String(16), nullable=False, default="ALL")  # ALL, STORE, USER, ROLE
    target_id = db.Column(db.Integer, nullable=True)

    repeat_type = db.Column(db.String(16), nullable=False, default="ONCE")  # ONCE, DAILY, WEEKLY, MONTHLY
    repeat_until = db.Column(db.DateTime(timezone=True), nullable=True)

    display_type = db.Column(db.String(32), nullable=False, default="LOGIN_POPUP")
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now(), onupdate=db.func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "org_id": self.org_id,
            "store_id": self.store_id,
            "title": self.title,
            "body": self.body,
            "created_by_user_id": self.created_by_user_id,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "repeat_type": self.repeat_type,
            "repeat_until": to_utc_z(self.repeat_until),
            "display_type": self.display_type,
            "is_active": self.is_active,
            "created_at": to_utc_z(self.created_at),
            "updated_at": to_utc_z(self.updated_at),
        }


class Task(db.Model):
    """
    Assigned tasks for users or registers.

    Register tasks must be completed or deferred (with reason) before register closeout.
    User tasks must be completed or deferred before clock-out.
    Display via panel in sales workspace.
    """
    __tablename__ = "tasks"
    __table_args__ = {"sqlite_autoincrement": True}

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=True, index=True)

    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)

    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    assigned_to_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    assigned_to_register_id = db.Column(db.Integer, db.ForeignKey("registers.id"), nullable=True, index=True)

    task_type = db.Column(db.String(16), nullable=False, default="USER")  # USER, REGISTER
    status = db.Column(db.String(16), nullable=False, default="PENDING", index=True)  # PENDING, COMPLETED, DEFERRED
    deferred_reason = db.Column(db.Text, nullable=True)

    due_at = db.Column(db.DateTime(timezone=True), nullable=True)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "org_id": self.org_id,
            "store_id": self.store_id,
            "title": self.title,
            "description": self.description,
            "created_by_user_id": self.created_by_user_id,
            "assigned_to_user_id": self.assigned_to_user_id,
            "assigned_to_register_id": self.assigned_to_register_id,
            "task_type": self.task_type,
            "status": self.status,
            "deferred_reason": self.deferred_reason,
            "due_at": to_utc_z(self.due_at),
            "completed_at": to_utc_z(self.completed_at),
            "created_at": to_utc_z(self.created_at),
        }
