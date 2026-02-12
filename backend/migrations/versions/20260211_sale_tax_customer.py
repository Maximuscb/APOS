"""Add tax_cents and customer_id to sales

Revision ID: 20260211_sale_tax
Revises: 20260211_sale_pricing
Create Date: 2026-02-11
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260211_sale_tax"
down_revision = "20260211_sale_pricing"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("sales", schema=None) as batch_op:
        batch_op.add_column(sa.Column("tax_cents", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("customer_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_sales_customer",
            "customers",
            ["customer_id"],
            ["id"],
        )
        batch_op.create_index("ix_sales_customer_id", ["customer_id"], unique=False)


def downgrade():
    with op.batch_alter_table("sales", schema=None) as batch_op:
        batch_op.drop_index("ix_sales_customer_id")
        batch_op.drop_constraint("fk_sales_customer", type_="foreignkey")
        batch_op.drop_column("customer_id")
        batch_op.drop_column("tax_cents")
