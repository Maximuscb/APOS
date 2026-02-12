"""Add reorder mechanism to vendors

Revision ID: 20260212_vendor_reorder
Revises: 20260212_import_posting
Create Date: 2026-02-12 13:45:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260212_vendor_reorder"
down_revision = "20260212_import_posting"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("vendors", schema=None) as batch_op:
        batch_op.add_column(sa.Column("reorder_mechanism", sa.String(length=255), nullable=True))


def downgrade():
    with op.batch_alter_table("vendors", schema=None) as batch_op:
        batch_op.drop_column("reorder_mechanism")

