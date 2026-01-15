"""Phase 12-14: Concurrency fields, store hierarchy/configs, reporting foundations

Revision ID: f1a2b3c4d5e6
Revises: abc9abff25a0
Create Date: 2026-01-15 18:25:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f1a2b3c4d5e6"
down_revision = "abc9abff25a0"
branch_labels = None
depends_on = None


def upgrade():
    # Store hierarchy + config
    with op.batch_alter_table("stores", schema=None) as batch_op:
        batch_op.add_column(sa.Column("code", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("parent_store_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("version_id", sa.Integer(), nullable=False, server_default="1"))
        batch_op.create_index(batch_op.f("ix_stores_code"), ["code"], unique=True)
        batch_op.create_index(batch_op.f("ix_stores_parent_store_id"), ["parent_store_id"], unique=False)
        batch_op.create_foreign_key("fk_stores_parent_store_id", "stores", ["parent_store_id"], ["id"])

    op.create_table(
        "store_configs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("store_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("version_id", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("store_id", "key", name="uq_store_configs_store_key"),
        sqlite_autoincrement=True,
    )
    with op.batch_alter_table("store_configs", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_store_configs_store_id"), ["store_id"], unique=False)

    # Optimistic locking version columns
    for table_name in [
        "products",
        "sales",
        "sale_lines",
        "registers",
        "register_sessions",
        "payments",
        "returns",
        "return_lines",
        "transfers",
        "transfer_lines",
        "counts",
        "count_lines",
    ]:
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.add_column(sa.Column("version_id", sa.Integer(), nullable=False, server_default="1"))


def downgrade():
    for table_name in [
        "count_lines",
        "counts",
        "transfer_lines",
        "transfers",
        "return_lines",
        "returns",
        "payments",
        "register_sessions",
        "registers",
        "sale_lines",
        "sales",
        "products",
    ]:
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.drop_column("version_id")

    with op.batch_alter_table("store_configs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_store_configs_store_id"))
    op.drop_table("store_configs")

    with op.batch_alter_table("stores", schema=None) as batch_op:
        batch_op.drop_constraint("fk_stores_parent_store_id", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_stores_parent_store_id"))
        batch_op.drop_index(batch_op.f("ix_stores_code"))
        batch_op.drop_column("version_id")
        batch_op.drop_column("parent_store_id")
        batch_op.drop_column("code")
