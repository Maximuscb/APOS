"""Import posting provenance and staging normalization

Revision ID: 20260212_import_posting
Revises: 20260211_sale_tax
Create Date: 2026-02-12 10:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260212_import_posting"
down_revision = "20260211_sale_tax"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("import_staging_rows", schema=None) as batch_op:
        batch_op.add_column(sa.Column("normalized_data", sa.JSON(), nullable=True))

    with op.batch_alter_table("master_ledger_events", schema=None) as batch_op:
        batch_op.add_column(sa.Column("source", sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column("import_batch_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("source_row_number", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("source_foreign_id", sa.String(length=128), nullable=True))
        batch_op.create_index("ix_master_ledger_source", ["source"], unique=False)
        batch_op.create_index("ix_master_ledger_import_batch_id", ["import_batch_id"], unique=False)
        batch_op.create_index("ix_master_ledger_source_row_number", ["source_row_number"], unique=False)
        batch_op.create_index("ix_master_ledger_source_foreign_id", ["source_foreign_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_master_ledger_import_batch",
            "import_batches",
            ["import_batch_id"],
            ["id"],
        )
        batch_op.create_unique_constraint(
            "uq_master_ledger_import_row",
            ["org_ledger_id", "import_batch_id", "source_row_number"],
        )


def downgrade():
    with op.batch_alter_table("master_ledger_events", schema=None) as batch_op:
        batch_op.drop_constraint("uq_master_ledger_import_row", type_="unique")
        batch_op.drop_constraint("fk_master_ledger_import_batch", type_="foreignkey")
        batch_op.drop_index("ix_master_ledger_source_foreign_id")
        batch_op.drop_index("ix_master_ledger_source_row_number")
        batch_op.drop_index("ix_master_ledger_import_batch_id")
        batch_op.drop_index("ix_master_ledger_source")
        batch_op.drop_column("source_foreign_id")
        batch_op.drop_column("source_row_number")
        batch_op.drop_column("import_batch_id")
        batch_op.drop_column("source")

    with op.batch_alter_table("import_staging_rows", schema=None) as batch_op:
        batch_op.drop_column("normalized_data")
