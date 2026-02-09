from __future__ import annotations

from ..extensions import db
from app.time_utils import to_utc_z


class OrganizationSetting(db.Model):
    """
    Key-value settings at the organization level.

    Organization-level settings exist only when multiple stores are present.
    If a single store exists, these are surfaced within Store Settings instead.
    """
    __tablename__ = "organization_settings"
    __table_args__ = (
        db.UniqueConstraint("org_id", "key", name="uq_org_settings_key"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True)

    key = db.Column(db.String(128), nullable=False)
    value = db.Column(db.Text, nullable=True)

    updated_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now(), onupdate=db.func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "org_id": self.org_id,
            "key": self.key,
            "value": self.value,
            "updated_by_user_id": self.updated_by_user_id,
            "updated_at": to_utc_z(self.updated_at),
        }


class DeviceSetting(db.Model):
    """
    Key-value settings at the device (register) level.

    Device settings include auto-logout, device configuration, etc.
    """
    __tablename__ = "device_settings"
    __table_args__ = (
        db.UniqueConstraint("device_id", "key", name="uq_device_settings_key"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey("registers.id"), nullable=False, index=True)

    key = db.Column(db.String(128), nullable=False)
    value = db.Column(db.Text, nullable=True)

    updated_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now(), onupdate=db.func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "device_id": self.device_id,
            "key": self.key,
            "value": self.value,
            "updated_by_user_id": self.updated_by_user_id,
            "updated_at": to_utc_z(self.updated_at),
        }
