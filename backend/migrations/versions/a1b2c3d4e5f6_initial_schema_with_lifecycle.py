"""initial schema with lifecycle

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-01-14 00:00:00.000000

This migration creates the complete APOS schema from scratch, including:
- stores: Multi-store support table
- products: Product master with SKU, pricing
- inventory_transactions: Append-only inventory ledger with lifecycle support
- master_ledger_events: Cross-domain audit spine

Phase 5 Document Lifecycle:
- All inventory transactions have status: DRAFT, APPROVED, POSTED
- Only POSTED transactions affect inventory calculations
- Approval and posting are tracked with timestamps and user IDs
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """
    Create all tables from scratch with Phase 5 lifecycle support.

    WHY: This migration creates the foundational schema for APOS, including
    the document lifecycle fields that prevent accidental posting and enable
    review workflows.
    """

    # ============================================================================
    # stores: Multi-store deployment support
    # ============================================================================
    op.create_table(
        'stores',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
        sqlite_autoincrement=True
    )

    # ============================================================================
    # products: Product master
    # ============================================================================
    op.create_table(
        'products',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('store_id', sa.Integer(), nullable=False),
        sa.Column('sku', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('price_cents', sa.Integer(), nullable=True),  # Backend authority
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('store_id', 'sku', name='uq_products_store_sku'),
        sqlite_autoincrement=True
    )
    op.create_index('ix_products_store_id', 'products', ['store_id'])
    op.create_index('ix_products_store_name', 'products', ['store_id', 'name'])

    # ============================================================================
    # inventory_transactions: Append-only ledger with lifecycle
    # ============================================================================
    # WHY lifecycle fields:
    # - status: DRAFT allows data entry without affecting inventory
    # - APPROVED: Reviewed but not yet posted (e.g., manager approval required)
    # - POSTED: Immutable, affects inventory calculations
    # - approved_at/posted_at: Audit trail for compliance
    # - approved_by/posted_by: Accountability (user IDs once auth exists)
    # ============================================================================
    op.create_table(
        'inventory_transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('store_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),

        # Transaction type: RECEIVE, ADJUST, SALE
        sa.Column('type', sa.String(length=32), nullable=False),

        # Quantity change (positive for RECEIVE, negative for SALE, +/- for ADJUST)
        sa.Column('quantity_delta', sa.Integer(), nullable=False),

        # Cost tracking (only for RECEIVE)
        sa.Column('unit_cost_cents', sa.Integer(), nullable=True),

        # User note
        sa.Column('note', sa.String(length=255), nullable=True),

        # Business time (when it occurred) vs system time (when recorded)
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('CURRENT_TIMESTAMP')),

        # Sale traceability and idempotency (Phase 4)
        sa.Column('sale_id', sa.String(length=64), nullable=True),
        sa.Column('sale_line_id', sa.String(length=64), nullable=True),

        # COGS snapshot (immutable after posting) (Phase 4)
        sa.Column('unit_cost_cents_at_sale', sa.Integer(), nullable=True),
        sa.Column('cogs_cents', sa.Integer(), nullable=True),

        # ========================================================================
        # PHASE 5: DOCUMENT LIFECYCLE
        # ========================================================================
        # status: Current lifecycle state
        # Default POSTED for backwards compatibility with existing code
        # New transactions should explicitly set DRAFT
        sa.Column('status', sa.String(length=16), nullable=False,
                  server_default='POSTED'),

        # Approval audit trail (nullable until User model exists)
        sa.Column('approved_by_user_id', sa.Integer(), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),

        # Posting audit trail (nullable until User model exists)
        sa.Column('posted_by_user_id', sa.Integer(), nullable=True),
        sa.Column('posted_at', sa.DateTime(timezone=True), nullable=True),
        # ========================================================================

        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('store_id', 'sale_id', 'sale_line_id',
                          name='uq_invtx_store_sale_line'),
        sqlite_autoincrement=True
    )

    # Indexes for common queries (especially by status for lifecycle filtering)
    op.create_index('ix_inventory_transactions_store_id',
                   'inventory_transactions', ['store_id'])
    op.create_index('ix_inventory_transactions_product_id',
                   'inventory_transactions', ['product_id'])
    op.create_index('ix_inventory_transactions_type',
                   'inventory_transactions', ['type'])
    op.create_index('ix_inventory_transactions_occurred_at',
                   'inventory_transactions', ['occurred_at'])
    op.create_index('ix_inventory_transactions_sale_id',
                   'inventory_transactions', ['sale_id'])

    # NEW: Index on status for efficient filtering of POSTED transactions
    op.create_index('ix_inventory_transactions_status',
                   'inventory_transactions', ['status'])

    # Composite indexes for inventory queries (must filter by status='POSTED')
    op.create_index('ix_invtx_store_product_occurred',
                   'inventory_transactions',
                   ['store_id', 'product_id', 'occurred_at'])
    op.create_index('ix_invtx_store_product_type_occurred',
                   'inventory_transactions',
                   ['store_id', 'product_id', 'type', 'occurred_at'])

    # NEW: Composite index including status for lifecycle-aware queries
    op.create_index('ix_invtx_store_product_status_occurred',
                   'inventory_transactions',
                   ['store_id', 'product_id', 'status', 'occurred_at'])

    # ============================================================================
    # master_ledger_events: Cross-domain audit spine
    # ============================================================================
    op.create_table(
        'master_ledger_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('store_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('entity_type', sa.String(length=64), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('note', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sqlite_autoincrement=True
    )
    op.create_index('ix_master_ledger_events_store_id',
                   'master_ledger_events', ['store_id'])
    op.create_index('ix_master_ledger_events_event_type',
                   'master_ledger_events', ['event_type'])
    op.create_index('ix_master_ledger_events_entity_type',
                   'master_ledger_events', ['entity_type'])
    op.create_index('ix_master_ledger_events_entity_id',
                   'master_ledger_events', ['entity_id'])
    op.create_index('ix_master_ledger_events_occurred_at',
                   'master_ledger_events', ['occurred_at'])


def downgrade():
    """Drop all tables (destructive operation)."""
    op.drop_table('master_ledger_events')
    op.drop_table('inventory_transactions')
    op.drop_table('products')
    op.drop_table('stores')
