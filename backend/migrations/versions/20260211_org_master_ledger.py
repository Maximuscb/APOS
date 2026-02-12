"""Add organization master ledger and consolidate ledger-style events

Revision ID: 20260211_org_master_ledger
Revises: 20260211_user_store_mgr
Create Date: 2026-02-11 18:45:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260211_org_master_ledger"
down_revision = "20260211_user_store_mgr"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "organization_master_ledgers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False, server_default="Master Ledger"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", name="uq_org_master_ledgers_org"),
        sqlite_autoincrement=True,
    )
    op.create_index("ix_org_master_ledgers_org_id", "organization_master_ledgers", ["org_id"], unique=False)

    with op.batch_alter_table("master_ledger_events", schema=None) as batch_op:
        batch_op.add_column(sa.Column("org_ledger_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_master_ledger_events_org_ledger_id", ["org_ledger_id"], unique=False)
        batch_op.create_index("ix_master_ledger_org_ledger_occurred", ["org_ledger_id", "occurred_at"], unique=False)
        batch_op.create_foreign_key(
            "fk_master_ledger_events_org_ledger",
            "organization_master_ledgers",
            ["org_ledger_id"],
            ["id"],
        )

    # Ensure each organization has one master ledger.
    op.execute(
        """
        INSERT INTO organization_master_ledgers (org_id, name, created_at, updated_at)
        SELECT o.id, 'Master Ledger', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        FROM organizations o
        LEFT JOIN organization_master_ledgers l ON l.org_id = o.id
        WHERE l.id IS NULL
        """
    )

    # Backfill existing master ledger events with org_ledger_id via store -> org mapping.
    op.execute(
        """
        UPDATE master_ledger_events
        SET org_ledger_id = (
            SELECT l.id
            FROM stores s
            JOIN organization_master_ledgers l ON l.org_id = s.org_id
            WHERE s.id = master_ledger_events.store_id
            LIMIT 1
        )
        WHERE org_ledger_id IS NULL
        """
    )

    # Consolidate inventory transaction ledger rows into master ledger where missing.
    op.execute(
        """
        INSERT INTO master_ledger_events (
            org_ledger_id, store_id, event_type, event_category, entity_type, entity_id,
            actor_user_id, occurred_at, created_at, note, payload
        )
        SELECT
            l.id,
            it.store_id,
            CASE it.type
                WHEN 'RECEIVE' THEN 'inventory.received'
                WHEN 'ADJUST' THEN 'inventory.adjusted'
                WHEN 'SALE' THEN 'inventory.sale_recorded'
                WHEN 'RETURN' THEN 'inventory.return_posted'
                WHEN 'TRANSFER' THEN 'inventory.transfer'
                ELSE 'inventory.transaction'
            END,
            'inventory',
            'inventory_transaction',
            it.id,
            COALESCE(it.posted_by_user_id, it.approved_by_user_id),
            it.occurred_at,
            CURRENT_TIMESTAMP,
            it.note,
            'source=inventory_transactions'
        FROM inventory_transactions it
        JOIN stores s ON s.id = it.store_id
        JOIN organization_master_ledgers l ON l.org_id = s.org_id
        WHERE it.status = 'POSTED'
          AND NOT EXISTS (
            SELECT 1
            FROM master_ledger_events me
            WHERE me.entity_type = 'inventory_transaction'
              AND me.entity_id = it.id
          )
        """
    )

    # Consolidate payment transaction ledger rows into master ledger where missing.
    op.execute(
        """
        INSERT INTO master_ledger_events (
            org_ledger_id, store_id, event_type, event_category, entity_type, entity_id,
            actor_user_id, register_id, register_session_id, sale_id, payment_id,
            occurred_at, created_at, note, payload
        )
        SELECT
            l.id,
            sa.store_id,
            CASE pt.transaction_type
                WHEN 'PAYMENT' THEN 'payment.created'
                WHEN 'VOID' THEN 'payment.voided'
                WHEN 'REFUND' THEN 'payment.refunded'
                ELSE 'payment.event'
            END,
            'payment',
            'payment_transaction',
            pt.id,
            pt.user_id,
            pt.register_id,
            pt.register_session_id,
            pt.sale_id,
            pt.payment_id,
            pt.occurred_at,
            CURRENT_TIMESTAMP,
            pt.reason,
            'source=payment_transactions'
        FROM payment_transactions pt
        JOIN sales sa ON sa.id = pt.sale_id
        JOIN stores s ON s.id = sa.store_id
        JOIN organization_master_ledgers l ON l.org_id = s.org_id
        WHERE NOT EXISTS (
            SELECT 1
            FROM master_ledger_events me
            WHERE me.entity_type = 'payment_transaction'
              AND me.entity_id = pt.id
        )
        """
    )

    # Consolidate store-scoped security events into master ledger where missing.
    op.execute(
        """
        INSERT INTO master_ledger_events (
            org_ledger_id, store_id, event_type, event_category, entity_type, entity_id,
            actor_user_id, occurred_at, created_at, note, payload
        )
        SELECT
            l.id,
            se.store_id,
            'security.' || lower(se.event_type),
            'security',
            'security_event',
            se.id,
            se.user_id,
            se.occurred_at,
            CURRENT_TIMESTAMP,
            se.reason,
            'source=security_events'
        FROM security_events se
        JOIN stores s ON s.id = se.store_id
        JOIN organization_master_ledgers l ON l.org_id = s.org_id
        WHERE se.store_id IS NOT NULL
          AND NOT EXISTS (
            SELECT 1
            FROM master_ledger_events me
            WHERE me.entity_type = 'security_event'
              AND me.entity_id = se.id
          )
        """
    )

    # Enforce required org ledger linkage after backfill.
    with op.batch_alter_table("master_ledger_events", schema=None) as batch_op:
        batch_op.alter_column("org_ledger_id", nullable=False)


def downgrade():
    with op.batch_alter_table("master_ledger_events", schema=None) as batch_op:
        batch_op.drop_constraint("fk_master_ledger_events_org_ledger", type_="foreignkey")
        batch_op.drop_index("ix_master_ledger_org_ledger_occurred")
        batch_op.drop_index("ix_master_ledger_events_org_ledger_id")
        batch_op.drop_column("org_ledger_id")

    op.drop_index("ix_org_master_ledgers_org_id", table_name="organization_master_ledgers")
    op.drop_table("organization_master_ledgers")
