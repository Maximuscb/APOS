"""Repair missing security_events table in legacy DBs

Revision ID: 20260212_repair_security
Revises: 20260212_unified_settings
Create Date: 2026-02-12 14:15:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260212_repair_security"
down_revision = "20260212_unified_settings"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("security_events"):
        op.create_table(
            "security_events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("org_id", sa.Integer(), nullable=True),
            sa.Column("store_id", sa.Integer(), nullable=True),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("event_type", sa.String(length=64), nullable=False),
            sa.Column("resource", sa.String(length=128), nullable=True),
            sa.Column("action", sa.String(length=64), nullable=True),
            sa.Column("success", sa.Boolean(), nullable=False),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("ip_address", sa.String(length=45), nullable=True),
            sa.Column("user_agent", sa.String(length=512), nullable=True),
            sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("(CURRENT_TIMESTAMP)")),
            sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
            sa.ForeignKeyConstraint(["store_id"], ["stores.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sqlite_autoincrement=True,
        )

    inspector = sa.inspect(bind)
    indexes = {ix["name"] for ix in inspector.get_indexes("security_events")}
    with op.batch_alter_table("security_events", schema=None) as batch_op:
        if "ix_security_events_user_type" not in indexes:
            batch_op.create_index("ix_security_events_user_type", ["user_id", "event_type"], unique=False)
        if "ix_security_events_occurred" not in indexes:
            batch_op.create_index("ix_security_events_occurred", ["occurred_at"], unique=False)
        if "ix_security_events_org_occurred" not in indexes:
            batch_op.create_index("ix_security_events_org_occurred", ["org_id", "occurred_at"], unique=False)
        if "ix_security_events_event_type" not in indexes:
            batch_op.create_index("ix_security_events_event_type", ["event_type"], unique=False)
        if "ix_security_events_action" not in indexes:
            batch_op.create_index("ix_security_events_action", ["action"], unique=False)


def downgrade():
    # Safety: only drop if present.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("security_events"):
        op.drop_table("security_events")

