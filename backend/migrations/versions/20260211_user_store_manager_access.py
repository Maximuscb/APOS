"""Add per-user manager access mapping to multiple stores

Revision ID: 20260211_user_store_mgr
Revises: 2f278182c655
Create Date: 2026-02-11
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260211_user_store_mgr"
down_revision = "2f278182c655"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_store_manager_access",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("store_id", sa.Integer(), nullable=False),
        sa.Column("granted_by_user_id", sa.Integer(), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["granted_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "store_id", name="uq_user_store_manager_access"),
        sqlite_autoincrement=True,
    )

    with op.batch_alter_table("user_store_manager_access", schema=None) as batch_op:
        batch_op.create_index("ix_user_store_manager_access_user", ["user_id"], unique=False)
        batch_op.create_index("ix_user_store_manager_access_store", ["store_id"], unique=False)


def downgrade():
    with op.batch_alter_table("user_store_manager_access", schema=None) as batch_op:
        batch_op.drop_index("ix_user_store_manager_access_store")
        batch_op.drop_index("ix_user_store_manager_access_user")

    op.drop_table("user_store_manager_access")
