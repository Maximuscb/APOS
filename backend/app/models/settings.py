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


class SettingRegistry(db.Model):
    """
    Static registry describing each supported setting key.

    WHY: Centralizes schema, validation, access policy, and metadata so the
    backend and UI can render and validate settings consistently.
    """
    __tablename__ = "settings_registry"
    __table_args__ = (
        db.Index("ix_settings_registry_category", "category"),
        db.Index("ix_settings_registry_scope_allowed", "scope_allowed"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(255), nullable=False, unique=True, index=True)
    # JSON array of scopes: ["ORG", "STORE", "DEVICE", "USER"]
    scope_allowed = db.Column(db.JSON, nullable=False)
    value_type = db.Column("type", db.String(64), nullable=False)
    default_value_json = db.Column(db.JSON, nullable=True)
    validation_json = db.Column(db.JSON, nullable=True)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(128), nullable=False)
    subcategory = db.Column(db.String(128), nullable=True)
    is_sensitive = db.Column(db.Boolean, nullable=False, default=False)
    is_developer_only = db.Column(db.Boolean, nullable=False, default=False)
    requires_restart = db.Column(db.Boolean, nullable=False, default=False)
    requires_reprice = db.Column(db.Boolean, nullable=False, default=False)
    requires_recalc = db.Column(db.Boolean, nullable=False, default=False)
    min_role_to_view = db.Column(db.String(32), nullable=True)
    min_role_to_edit = db.Column(db.String(32), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.func.now(),
        onupdate=db.func.now(),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "key": self.key,
            "scope_allowed": self.scope_allowed or [],
            "type": self.value_type,
            "default_value_json": self.default_value_json,
            "validation_json": self.validation_json,
            "description": self.description,
            "category": self.category,
            "subcategory": self.subcategory,
            "is_sensitive": bool(self.is_sensitive),
            "is_developer_only": bool(self.is_developer_only),
            "requires_restart": bool(self.requires_restart),
            "requires_reprice": bool(self.requires_reprice),
            "requires_recalc": bool(self.requires_recalc),
            "min_role_to_view": self.min_role_to_view,
            "min_role_to_edit": self.min_role_to_edit,
            "created_at": to_utc_z(self.created_at),
            "updated_at": to_utc_z(self.updated_at),
        }


class SettingValue(db.Model):
    """
    Dynamic setting value bound to an explicit scope.
    """
    __tablename__ = "settings_values"
    __table_args__ = (
        db.UniqueConstraint("key", "scope_type", "scope_id", name="uq_settings_values_scope_key"),
        db.ForeignKeyConstraint(["key"], ["settings_registry.key"], name="fk_settings_values_key"),
        db.Index("ix_settings_values_scope", "scope_type", "scope_id"),
        db.Index("ix_settings_values_key", "key"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(255), nullable=False)
    scope_type = db.Column(db.String(16), nullable=False)  # ORG/STORE/DEVICE/USER
    scope_id = db.Column(db.Integer, nullable=False)
    value_json = db.Column(db.JSON, nullable=True)
    updated_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    source = db.Column(db.String(32), nullable=False, default="UI")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.func.now(),
        onupdate=db.func.now(),
    )

    registry = db.relationship("SettingRegistry", primaryjoin="SettingValue.key==SettingRegistry.key")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "key": self.key,
            "scope_type": self.scope_type,
            "scope_id": self.scope_id,
            "value_json": self.value_json,
            "updated_by_user_id": self.updated_by_user_id,
            "source": self.source,
            "created_at": to_utc_z(self.created_at),
            "updated_at": to_utc_z(self.updated_at),
        }


class SettingAudit(db.Model):
    """
    Immutable audit log for setting changes.
    """
    __tablename__ = "settings_audit"
    __table_args__ = (
        db.Index("ix_settings_audit_scope", "scope_type", "scope_id"),
        db.Index("ix_settings_audit_key", "key"),
        db.Index("ix_settings_audit_changed_at", "changed_at"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(255), nullable=False)
    scope_type = db.Column(db.String(16), nullable=False)
    scope_id = db.Column(db.Integer, nullable=False)
    old_value_json = db.Column(db.JSON, nullable=True)
    new_value_json = db.Column(db.JSON, nullable=True)
    changed_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    changed_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    change_reason = db.Column(db.Text, nullable=True)
    request_metadata_json = db.Column(db.JSON, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "key": self.key,
            "scope_type": self.scope_type,
            "scope_id": self.scope_id,
            "old_value_json": self.old_value_json,
            "new_value_json": self.new_value_json,
            "changed_by_user_id": self.changed_by_user_id,
            "changed_at": to_utc_z(self.changed_at),
            "change_reason": self.change_reason,
            "request_metadata_json": self.request_metadata_json,
        }
