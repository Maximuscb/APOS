"""Drop device_id from registers

Revision ID: 20260211_drop_reg_device
Revises: 20260211_register_org
Create Date: 2026-02-11
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260211_drop_reg_device"
down_revision = "20260211_register_org"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("registers", schema=None) as batch_op:
        batch_op.drop_column("device_id")


def downgrade():
    with op.batch_alter_table("registers", schema=None) as batch_op:
        batch_op.add_column(sa.Column("device_id", sa.String(length=128), nullable=True))

