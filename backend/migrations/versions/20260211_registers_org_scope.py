"""Add org_id to registers and backfill from stores

Revision ID: 20260211_register_org
Revises: 8b4807ada400
Create Date: 2026-02-11
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260211_register_org"
down_revision = "8b4807ada400"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("registers", sa.Column("org_id", sa.Integer(), nullable=True))

    # Backfill org_id from owning store
    op.execute(
        """
        UPDATE registers
        SET org_id = (
            SELECT stores.org_id
            FROM stores
            WHERE stores.id = registers.store_id
        )
        """
    )

    op.alter_column("registers", "org_id", existing_type=sa.Integer(), nullable=False)
    op.create_index("ix_registers_org_id", "registers", ["org_id"], unique=False)
    op.create_foreign_key("fk_registers_org_id_organizations", "registers", "organizations", ["org_id"], ["id"])


def downgrade():
    op.drop_constraint("fk_registers_org_id_organizations", "registers", type_="foreignkey")
    op.drop_index("ix_registers_org_id", table_name="registers")
    op.drop_column("registers", "org_id")

