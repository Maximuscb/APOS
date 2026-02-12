"""Add price override and discount tracking to sale_lines

Revision ID: 20260211_sale_pricing
Revises: 20260211_customers
Create Date: 2026-02-11
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260211_sale_pricing"
down_revision = "20260211_customers"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("sale_lines", schema=None) as batch_op:
        batch_op.add_column(sa.Column("original_price_cents", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("discount_cents", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("discount_reason", sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("override_approved_by_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("tax_cents", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_sale_lines_override_user",
            "users",
            ["override_approved_by_user_id"],
            ["id"],
        )


def downgrade():
    with op.batch_alter_table("sale_lines", schema=None) as batch_op:
        batch_op.drop_constraint("fk_sale_lines_override_user", type_="foreignkey")
        batch_op.drop_column("tax_cents")
        batch_op.drop_column("override_approved_by_user_id")
        batch_op.drop_column("discount_reason")
        batch_op.drop_column("discount_cents")
        batch_op.drop_column("original_price_cents")
