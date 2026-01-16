"""Phase 15: Ledger expansion, document sequences, sale voids, and controls

Revision ID: h4i5j6k7l8m9
Revises: g2h3i4j5k6l7
Create Date: 2026-01-16 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "h4i5j6k7l8m9"
down_revision = "g2h3i4j5k6l7"
branch_labels = None
depends_on = None


def upgrade():
    # Sales void metadata
    with op.batch_alter_table("sales", schema=None) as batch_op:
        batch_op.add_column(sa.Column("voided_by_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("void_reason", sa.String(length=255), nullable=True))
        batch_op.create_foreign_key("fk_sales_voided_by_user", "users", ["voided_by_user_id"], ["id"])

    # Register session opened_by
    with op.batch_alter_table("register_sessions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("opened_by_user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_register_sessions_opened_by_user",
            "users",
            ["opened_by_user_id"],
            ["id"],
        )

    # Transfer line cost snapshot
    with op.batch_alter_table("transfer_lines", schema=None) as batch_op:
        batch_op.add_column(sa.Column("unit_cost_cents", sa.Integer(), nullable=True))

    # Count line uniqueness
    with op.batch_alter_table("count_lines", schema=None) as batch_op:
        batch_op.create_unique_constraint("uq_count_lines_count_product", ["count_id", "product_id"])

    # Document sequences
    op.create_table(
        "document_sequences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("store_id", sa.Integer(), nullable=False),
        sa.Column("document_type", sa.String(length=32), nullable=False),
        sa.Column("next_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"]),
        sa.UniqueConstraint("store_id", "document_type", name="uq_doc_sequences_store_type"),
        sqlite_autoincrement=True,
    )
    op.create_index("ix_document_sequences_store_id", "document_sequences", ["store_id"], unique=False)
    op.create_index("ix_document_sequences_document_type", "document_sequences", ["document_type"], unique=False)

    # Master ledger expansion
    with op.batch_alter_table("master_ledger_events", schema=None) as batch_op:
        batch_op.add_column(sa.Column("event_category", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("actor_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("register_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("register_session_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("sale_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("payment_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("return_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("transfer_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("count_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("cash_drawer_event_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("payload", sa.Text(), nullable=True))

        batch_op.create_foreign_key("fk_master_ledger_actor_user", "users", ["actor_user_id"], ["id"])
        batch_op.create_foreign_key("fk_master_ledger_register", "registers", ["register_id"], ["id"])
        batch_op.create_foreign_key("fk_master_ledger_register_session", "register_sessions", ["register_session_id"], ["id"])
        batch_op.create_foreign_key("fk_master_ledger_sale", "sales", ["sale_id"], ["id"])
        batch_op.create_foreign_key("fk_master_ledger_payment", "payments", ["payment_id"], ["id"])
        batch_op.create_foreign_key("fk_master_ledger_return", "returns", ["return_id"], ["id"])
        batch_op.create_foreign_key("fk_master_ledger_transfer", "transfers", ["transfer_id"], ["id"])
        batch_op.create_foreign_key("fk_master_ledger_count", "counts", ["count_id"], ["id"])
        batch_op.create_foreign_key("fk_master_ledger_drawer_event", "cash_drawer_events", ["cash_drawer_event_id"], ["id"])

        batch_op.create_index("ix_master_ledger_store_occurred", ["store_id", "occurred_at"], unique=False)

    op.execute(
        "UPDATE master_ledger_events SET event_category='product' "
        "WHERE event_category IS NULL AND (event_type LIKE 'PRODUCT_%' OR event_type LIKE 'product.%')"
    )
    op.execute(
        "UPDATE master_ledger_events SET event_category='inventory' "
        "WHERE event_category IS NULL AND (event_type IN ('INV_TX_CREATED','SALE_RECORDED') "
        "OR event_type LIKE 'inventory.%')"
    )
    op.execute(
        "UPDATE master_ledger_events SET event_category='unknown' WHERE event_category IS NULL"
    )

    with op.batch_alter_table("master_ledger_events", schema=None) as batch_op:
        batch_op.alter_column("event_category", nullable=False, server_default="unknown")


def downgrade():
    with op.batch_alter_table("master_ledger_events", schema=None) as batch_op:
        batch_op.drop_index("ix_master_ledger_store_occurred")
        batch_op.drop_constraint("fk_master_ledger_drawer_event", type_="foreignkey")
        batch_op.drop_constraint("fk_master_ledger_count", type_="foreignkey")
        batch_op.drop_constraint("fk_master_ledger_transfer", type_="foreignkey")
        batch_op.drop_constraint("fk_master_ledger_return", type_="foreignkey")
        batch_op.drop_constraint("fk_master_ledger_payment", type_="foreignkey")
        batch_op.drop_constraint("fk_master_ledger_sale", type_="foreignkey")
        batch_op.drop_constraint("fk_master_ledger_register_session", type_="foreignkey")
        batch_op.drop_constraint("fk_master_ledger_register", type_="foreignkey")
        batch_op.drop_constraint("fk_master_ledger_actor_user", type_="foreignkey")
        batch_op.drop_column("payload")
        batch_op.drop_column("cash_drawer_event_id")
        batch_op.drop_column("count_id")
        batch_op.drop_column("transfer_id")
        batch_op.drop_column("return_id")
        batch_op.drop_column("payment_id")
        batch_op.drop_column("sale_id")
        batch_op.drop_column("register_session_id")
        batch_op.drop_column("register_id")
        batch_op.drop_column("actor_user_id")
        batch_op.drop_column("event_category")

    op.drop_index("ix_document_sequences_document_type", table_name="document_sequences")
    op.drop_index("ix_document_sequences_store_id", table_name="document_sequences")
    op.drop_table("document_sequences")

    with op.batch_alter_table("count_lines", schema=None) as batch_op:
        batch_op.drop_constraint("uq_count_lines_count_product", type_="unique")

    with op.batch_alter_table("transfer_lines", schema=None) as batch_op:
        batch_op.drop_column("unit_cost_cents")

    with op.batch_alter_table("register_sessions", schema=None) as batch_op:
        batch_op.drop_constraint("fk_register_sessions_opened_by_user", type_="foreignkey")
        batch_op.drop_column("opened_by_user_id")

    with op.batch_alter_table("sales", schema=None) as batch_op:
        batch_op.drop_constraint("fk_sales_voided_by_user", type_="foreignkey")
        batch_op.drop_column("void_reason")
        batch_op.drop_column("voided_at")
        batch_op.drop_column("voided_by_user_id")
