"""Unified settings framework across org/store/device/user scopes

Revision ID: 20260212_unified_settings
Revises: 20260212_vendor_reorder
Create Date: 2026-02-12 15:15:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
import json


# revision identifiers, used by Alembic.
revision = "20260212_unified_settings"
down_revision = "20260212_vendor_reorder"
branch_labels = None
depends_on = None


def _to_json_value(value):
    if value is None:
        return None
    if isinstance(value, (dict, list, bool, int, float)):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if raw == "":
            return None
        # Preserve legacy scalar strings, but parse obvious JSON payloads.
        if raw in {"true", "false"}:
            return raw == "true"
        try:
            return int(raw)
        except Exception:
            pass
        try:
            return float(raw)
        except Exception:
            pass
        if (raw.startswith("{") and raw.endswith("}")) or (raw.startswith("[") and raw.endswith("]")):
            try:
                return json.loads(raw)
            except Exception:
                return raw
        return raw
    return value


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("settings_registry"):
        op.create_table(
            "settings_registry",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("key", sa.String(length=255), nullable=False),
            sa.Column("scope_allowed", sa.JSON(), nullable=False),
            sa.Column("type", sa.String(length=64), nullable=False),
            sa.Column("default_value_json", sa.JSON(), nullable=True),
            sa.Column("validation_json", sa.JSON(), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("category", sa.String(length=128), nullable=False),
            sa.Column("subcategory", sa.String(length=128), nullable=True),
            sa.Column("is_sensitive", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("is_developer_only", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("requires_restart", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("requires_reprice", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("requires_recalc", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("min_role_to_view", sa.String(length=32), nullable=True),
            sa.Column("min_role_to_edit", sa.String(length=32), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("key"),
            sqlite_autoincrement=True,
        )
    if not inspector.has_table("settings_values"):
        op.create_table(
            "settings_values",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("key", sa.String(length=255), nullable=False),
            sa.Column("scope_type", sa.String(length=16), nullable=False),
            sa.Column("scope_id", sa.Integer(), nullable=False),
            sa.Column("value_json", sa.JSON(), nullable=True),
            sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
            sa.Column("source", sa.String(length=32), nullable=False, server_default="UI"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.ForeignKeyConstraint(["key"], ["settings_registry.key"], name="fk_settings_values_key"),
            sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("key", "scope_type", "scope_id", name="uq_settings_values_scope_key"),
            sqlite_autoincrement=True,
        )
    if not inspector.has_table("settings_audit"):
        op.create_table(
            "settings_audit",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("key", sa.String(length=255), nullable=False),
            sa.Column("scope_type", sa.String(length=16), nullable=False),
            sa.Column("scope_id", sa.Integer(), nullable=False),
            sa.Column("old_value_json", sa.JSON(), nullable=True),
            sa.Column("new_value_json", sa.JSON(), nullable=True),
            sa.Column("changed_by_user_id", sa.Integer(), nullable=True),
            sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.Column("change_reason", sa.Text(), nullable=True),
            sa.Column("request_metadata_json", sa.JSON(), nullable=True),
            sa.ForeignKeyConstraint(["changed_by_user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sqlite_autoincrement=True,
        )

    inspector = sa.inspect(bind)
    registry_indexes = {ix["name"] for ix in inspector.get_indexes("settings_registry")}
    if "ix_settings_registry_key" not in registry_indexes:
        with op.batch_alter_table("settings_registry", schema=None) as batch_op:
            batch_op.create_index("ix_settings_registry_key", ["key"], unique=False)
    if "ix_settings_registry_category" not in registry_indexes:
        with op.batch_alter_table("settings_registry", schema=None) as batch_op:
            batch_op.create_index("ix_settings_registry_category", ["category"], unique=False)

    values_indexes = {ix["name"] for ix in inspector.get_indexes("settings_values")}
    if "ix_settings_values_scope" not in values_indexes:
        with op.batch_alter_table("settings_values", schema=None) as batch_op:
            batch_op.create_index("ix_settings_values_scope", ["scope_type", "scope_id"], unique=False)
    if "ix_settings_values_key" not in values_indexes:
        with op.batch_alter_table("settings_values", schema=None) as batch_op:
            batch_op.create_index("ix_settings_values_key", ["key"], unique=False)

    audit_indexes = {ix["name"] for ix in inspector.get_indexes("settings_audit")}
    if "ix_settings_audit_scope" not in audit_indexes:
        with op.batch_alter_table("settings_audit", schema=None) as batch_op:
            batch_op.create_index("ix_settings_audit_scope", ["scope_type", "scope_id"], unique=False)
    if "ix_settings_audit_key" not in audit_indexes:
        with op.batch_alter_table("settings_audit", schema=None) as batch_op:
            batch_op.create_index("ix_settings_audit_key", ["key"], unique=False)
    if "ix_settings_audit_changed_at" not in audit_indexes:
        with op.batch_alter_table("settings_audit", schema=None) as batch_op:
            batch_op.create_index("ix_settings_audit_changed_at", ["changed_at"], unique=False)

    from app.settings_catalog import SETTINGS_CATALOG

    registry_table = table(
        "settings_registry",
        column("key", sa.String),
        column("scope_allowed", sa.JSON),
        column("type", sa.String),
        column("default_value_json", sa.JSON),
        column("validation_json", sa.JSON),
        column("description", sa.Text),
        column("category", sa.String),
        column("subcategory", sa.String),
        column("is_sensitive", sa.Boolean),
        column("is_developer_only", sa.Boolean),
        column("requires_restart", sa.Boolean),
        column("requires_reprice", sa.Boolean),
        column("requires_recalc", sa.Boolean),
        column("min_role_to_view", sa.String),
        column("min_role_to_edit", sa.String),
    )
    existing_registry_keys = {
        row[0] for row in bind.execute(sa.text("SELECT key FROM settings_registry")).fetchall()
    }
    rows_to_insert = [row for row in SETTINGS_CATALOG if row["key"] not in existing_registry_keys]
    if rows_to_insert:
        op.bulk_insert(registry_table, rows_to_insert)

    keys = {row["key"] for row in SETTINGS_CATALOG}
    value_table = table(
        "settings_values",
        column("key", sa.String),
        column("scope_type", sa.String),
        column("scope_id", sa.Integer),
        column("value_json", sa.JSON),
        column("updated_by_user_id", sa.Integer),
        column("source", sa.String),
    )

    existing_pairs = {
        (row[0], row[1], row[2])
        for row in bind.execute(sa.text("SELECT key, scope_type, scope_id FROM settings_values")).fetchall()
    }

    org_rows = []
    if inspector.has_table("organization_settings"):
        org_rows = bind.execute(sa.text("SELECT org_id, key, value, updated_by_user_id FROM organization_settings")).mappings().all()
    org_inserts = []
    for row in org_rows:
        if row["key"] not in keys:
            continue
        pair = (row["key"], "ORG", int(row["org_id"]))
        if pair in existing_pairs:
            continue
        org_inserts.append(
            {
                "key": row["key"],
                "scope_type": "ORG",
                "scope_id": int(row["org_id"]),
                "value_json": _to_json_value(row["value"]),
                "updated_by_user_id": row["updated_by_user_id"],
                "source": "system_migration",
            }
        )
    if org_inserts:
        op.bulk_insert(value_table, org_inserts)

    dev_rows = []
    if inspector.has_table("device_settings"):
        dev_rows = bind.execute(sa.text("SELECT device_id, key, value, updated_by_user_id FROM device_settings")).mappings().all()
    dev_inserts = []
    for row in dev_rows:
        if row["key"] not in keys:
            continue
        pair = (row["key"], "DEVICE", int(row["device_id"]))
        if pair in existing_pairs:
            continue
        dev_inserts.append(
            {
                "key": row["key"],
                "scope_type": "DEVICE",
                "scope_id": int(row["device_id"]),
                "value_json": _to_json_value(row["value"]),
                "updated_by_user_id": row["updated_by_user_id"],
                "source": "system_migration",
            }
        )
    if dev_inserts:
        op.bulk_insert(value_table, dev_inserts)

    store_rows = []
    if inspector.has_table("store_configs"):
        store_rows = bind.execute(sa.text("SELECT store_id, key, value FROM store_configs")).mappings().all()
    store_inserts = []
    for row in store_rows:
        if row["key"] not in keys:
            continue
        pair = (row["key"], "STORE", int(row["store_id"]))
        if pair in existing_pairs:
            continue
        store_inserts.append(
            {
                "key": row["key"],
                "scope_type": "STORE",
                "scope_id": int(row["store_id"]),
                "value_json": _to_json_value(row["value"]),
                "updated_by_user_id": None,
                "source": "system_migration",
            }
        )
    if store_inserts:
        op.bulk_insert(value_table, store_inserts)


def downgrade():
    op.drop_table("settings_audit")
    op.drop_table("settings_values")
    op.drop_table("settings_registry")
