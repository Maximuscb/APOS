"""Add Customer and Rewards models

Revision ID: 20260211_customers
Revises: 20260211_communications_overhaul
Create Date: 2026-02-11
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260211_customers"
down_revision = "20260211_communications_overhaul"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=False),
        sa.Column("store_id", sa.Integer(), nullable=True),
        sa.Column("first_name", sa.String(128), nullable=False),
        sa.Column("last_name", sa.String(128), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(32), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("total_spent_cents", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_visits", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_visit_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("version_id", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "email", name="uq_customers_org_email"),
        sqlite_autoincrement=True,
    )

    with op.batch_alter_table("customers", schema=None) as batch_op:
        batch_op.create_index("ix_customers_org_id", ["org_id"], unique=False)
        batch_op.create_index("ix_customers_org_active", ["org_id", "is_active"], unique=False)

    op.create_table(
        "customer_reward_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=False),
        sa.Column("points_balance", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("lifetime_points_earned", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("lifetime_points_redeemed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("version_id", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("customer_id", name="uq_reward_accounts_customer"),
        sqlite_autoincrement=True,
    )

    with op.batch_alter_table("customer_reward_accounts", schema=None) as batch_op:
        batch_op.create_index("ix_reward_accounts_customer", ["customer_id"], unique=False)
        batch_op.create_index("ix_reward_accounts_org", ["org_id"], unique=False)

    op.create_table(
        "customer_reward_transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("reward_account_id", sa.Integer(), nullable=False),
        sa.Column("transaction_type", sa.String(16), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("sale_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["reward_account_id"], ["customer_reward_accounts.id"]),
        sa.ForeignKeyConstraint(["sale_id"], ["sales.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sqlite_autoincrement=True,
    )

    with op.batch_alter_table("customer_reward_transactions", schema=None) as batch_op:
        batch_op.create_index("ix_reward_txns_account", ["reward_account_id"], unique=False)
        batch_op.create_index("ix_reward_txns_account_occurred", ["reward_account_id", "occurred_at"], unique=False)
        batch_op.create_index("ix_reward_txns_type", ["transaction_type"], unique=False)


def downgrade():
    op.drop_table("customer_reward_transactions")
    op.drop_table("customer_reward_accounts")
    op.drop_table("customers")
