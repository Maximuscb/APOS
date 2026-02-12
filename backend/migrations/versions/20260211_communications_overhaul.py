"""communications overhaul for scoped notifications and dismissals

Revision ID: 20260211_communications_overhaul
Revises: 20260211_org_master_ledger
Create Date: 2026-02-11 19:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260211_communications_overhaul"
down_revision = "20260211_org_master_ledger"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "communication_dismissals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("communication_kind", sa.String(length=16), nullable=False),
        sa.Column("communication_id", sa.Integer(), nullable=False),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "communication_kind", "communication_id", name="uq_comm_dismissal_user_kind_id"),
        sqlite_autoincrement=True,
    )
    op.create_index("ix_comm_dismissal_user", "communication_dismissals", ["user_id"], unique=False)

    # Normalize legacy target semantics.
    op.execute("UPDATE announcements SET target_type = 'ORG', target_id = NULL, store_id = NULL WHERE target_type = 'ALL'")
    op.execute("UPDATE reminders SET target_type = 'ORG', target_id = NULL, store_id = NULL WHERE target_type = 'ALL'")

    # If STORE is selected but target_id is null, use store_id as target_id.
    op.execute("UPDATE announcements SET target_id = store_id WHERE target_type = 'STORE' AND target_id IS NULL AND store_id IS NOT NULL")
    op.execute("UPDATE reminders SET target_id = store_id WHERE target_type = 'STORE' AND target_id IS NULL AND store_id IS NOT NULL")

    # Default display style to login banner.
    op.execute("UPDATE announcements SET display_type = 'LOGIN_BANNER' WHERE display_type IS NULL OR display_type = 'LOGIN_POPUP'")
    op.execute("UPDATE reminders SET display_type = 'LOGIN_BANNER' WHERE display_type IS NULL OR display_type = 'LOGIN_POPUP'")


def downgrade():
    op.drop_index("ix_comm_dismissal_user", table_name="communication_dismissals")
    op.drop_table("communication_dismissals")
