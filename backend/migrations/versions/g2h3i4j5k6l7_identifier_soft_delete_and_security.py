"""Add is_active and deactivated_at to product_identifiers for soft delete

Revision ID: g2h3i4j5k6l7
Revises: f1a2b3c4d5e6
Create Date: 2026-01-16 10:00:00.000000

WHY: Implements soft delete for product identifiers. Instead of hard-deleting
identifiers (which would lose audit history), we deactivate them. Inactive
identifiers are excluded from lookups but remain for audit purposes.

This migration adds:
- is_active: Boolean flag (default True) to mark active identifiers
- deactivated_at: Timestamp when the identifier was deactivated
- Index on is_active for efficient filtering
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "g2h3i4j5k6l7"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade():
    # Add is_active and deactivated_at columns to product_identifiers
    with op.batch_alter_table("product_identifiers", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1")
        )
        batch_op.add_column(
            sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.create_index(
            batch_op.f("ix_identifier_active"), ["is_active"], unique=False
        )


def downgrade():
    with op.batch_alter_table("product_identifiers", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_identifier_active"))
        batch_op.drop_column("deactivated_at")
        batch_op.drop_column("is_active")
