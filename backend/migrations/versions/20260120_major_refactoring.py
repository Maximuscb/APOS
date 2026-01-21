"""Major refactoring: vendors, receives, permissions, timekeeping, imports

Revision ID: 20260120_major
Revises: 13500e977217
Create Date: 2026-01-20

This migration adds:
1. Vendor entity (required for all inventory receives)
2. ReceiveDocument and ReceiveDocumentLine (document-first receiving)
3. User PIN hash (optional 6-digit PIN for Register Mode)
4. UserPermissionOverride (per-user permission grants/denies)
5. TimeClockEntry, TimeClockBreak, TimeClockCorrection (shift-based timekeeping)
6. ImportBatch, ImportStagingRow, ImportEntityMapping (enterprise-scale imports)
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260120_major'
down_revision = '13500e977217'
branch_labels = None
depends_on = None


def upgrade():
    # ==========================================================================
    # 1. VENDORS TABLE
    # ==========================================================================
    op.create_table('vendors',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('code', sa.String(length=64), nullable=True),
        sa.Column('contact_name', sa.String(length=255), nullable=True),
        sa.Column('contact_email', sa.String(length=255), nullable=True),
        sa.Column('contact_phone', sa.String(length=64), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('version_id', sa.Integer(), nullable=False, server_default='1'),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('org_id', 'code', name='uq_vendors_org_code'),
        sqlite_autoincrement=True
    )
    with op.batch_alter_table('vendors', schema=None) as batch_op:
        batch_op.create_index('ix_vendors_org_id', ['org_id'], unique=False)
        batch_op.create_index('ix_vendors_org_active', ['org_id', 'is_active'], unique=False)
        batch_op.create_index(batch_op.f('ix_vendors_code'), ['code'], unique=False)

    # ==========================================================================
    # 2. RECEIVE DOCUMENTS TABLE
    # ==========================================================================
    op.create_table('receive_documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('store_id', sa.Integer(), nullable=False),
        sa.Column('vendor_id', sa.Integer(), nullable=False),
        sa.Column('document_number', sa.String(length=64), nullable=False),
        sa.Column('receive_type', sa.String(length=32), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='DRAFT'),
        sa.Column('occurred_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('reference_number', sa.String(length=128), nullable=True),
        sa.Column('created_by_user_id', sa.Integer(), nullable=False),
        sa.Column('approved_by_user_id', sa.Integer(), nullable=True),
        sa.Column('posted_by_user_id', sa.Integer(), nullable=True),
        sa.Column('cancelled_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('posted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancellation_reason', sa.Text(), nullable=True),
        sa.Column('version_id', sa.Integer(), nullable=False, server_default='1'),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ),
        sa.ForeignKeyConstraint(['vendor_id'], ['vendors.id'], ),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['approved_by_user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['posted_by_user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['cancelled_by_user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('store_id', 'document_number', name='uq_receive_docs_store_docnum'),
        sqlite_autoincrement=True
    )
    with op.batch_alter_table('receive_documents', schema=None) as batch_op:
        batch_op.create_index('ix_receive_docs_store_id', ['store_id'], unique=False)
        batch_op.create_index('ix_receive_docs_vendor', ['vendor_id'], unique=False)
        batch_op.create_index('ix_receive_docs_document_number', ['document_number'], unique=False)
        batch_op.create_index('ix_receive_docs_store_status', ['store_id', 'status'], unique=False)
        batch_op.create_index('ix_receive_docs_receive_type', ['receive_type'], unique=False)
        batch_op.create_index('ix_receive_docs_status', ['status'], unique=False)
        batch_op.create_index('ix_receive_docs_created_by', ['created_by_user_id'], unique=False)

    # ==========================================================================
    # 3. RECEIVE DOCUMENT LINES TABLE
    # ==========================================================================
    op.create_table('receive_document_lines',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('receive_document_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('unit_cost_cents', sa.Integer(), nullable=False),
        sa.Column('line_cost_cents', sa.Integer(), nullable=False),
        sa.Column('note', sa.String(length=255), nullable=True),
        sa.Column('inventory_transaction_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('version_id', sa.Integer(), nullable=False, server_default='1'),
        sa.ForeignKeyConstraint(['receive_document_id'], ['receive_documents.id'], ),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
        sa.ForeignKeyConstraint(['inventory_transaction_id'], ['inventory_transactions.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('receive_document_id', 'product_id', name='uq_receive_lines_doc_product'),
        sqlite_autoincrement=True
    )
    with op.batch_alter_table('receive_document_lines', schema=None) as batch_op:
        batch_op.create_index('ix_receive_lines_document', ['receive_document_id'], unique=False)
        batch_op.create_index('ix_receive_lines_product', ['product_id'], unique=False)

    # ==========================================================================
    # 4. USER PIN HASH (add column to users table)
    # ==========================================================================
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('pin_hash', sa.String(length=255), nullable=True))

    # ==========================================================================
    # 5. USER PERMISSION OVERRIDES TABLE
    # ==========================================================================
    op.create_table('user_permission_overrides',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('permission_code', sa.String(length=64), nullable=False),
        sa.Column('override_type', sa.String(length=8), nullable=False),
        sa.Column('granted_by_user_id', sa.Integer(), nullable=False),
        sa.Column('granted_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('revoked_by_user_id', sa.Integer(), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revocation_reason', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['granted_by_user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['revoked_by_user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'permission_code', name='uq_user_perm_override'),
        sqlite_autoincrement=True
    )
    with op.batch_alter_table('user_permission_overrides', schema=None) as batch_op:
        batch_op.create_index('ix_user_perm_overrides_user', ['user_id'], unique=False)
        batch_op.create_index('ix_user_perm_overrides_code', ['permission_code'], unique=False)
        batch_op.create_index('ix_user_perm_overrides_active', ['is_active'], unique=False)

    # ==========================================================================
    # 6. TIME CLOCK ENTRIES TABLE
    # ==========================================================================
    op.create_table('time_clock_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('store_id', sa.Integer(), nullable=False),
        sa.Column('clock_in_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('clock_out_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='OPEN'),
        sa.Column('total_worked_minutes', sa.Integer(), nullable=True),
        sa.Column('total_break_minutes', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('register_session_id', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('version_id', sa.Integer(), nullable=False, server_default='1'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ),
        sa.ForeignKeyConstraint(['register_session_id'], ['register_sessions.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sqlite_autoincrement=True
    )
    with op.batch_alter_table('time_clock_entries', schema=None) as batch_op:
        batch_op.create_index('ix_time_clock_user_id', ['user_id'], unique=False)
        batch_op.create_index('ix_time_clock_store_id', ['store_id'], unique=False)
        batch_op.create_index('ix_time_clock_user_status', ['user_id', 'status'], unique=False)
        batch_op.create_index('ix_time_clock_store_date', ['store_id', 'clock_in_at'], unique=False)
        batch_op.create_index('ix_time_clock_status', ['status'], unique=False)
        batch_op.create_index('ix_time_clock_register_session', ['register_session_id'], unique=False)

    # ==========================================================================
    # 7. TIME CLOCK BREAKS TABLE
    # ==========================================================================
    op.create_table('time_clock_breaks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('time_clock_entry_id', sa.Integer(), nullable=False),
        sa.Column('start_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('break_type', sa.String(length=16), nullable=False, server_default='UNPAID'),
        sa.Column('duration_minutes', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['time_clock_entry_id'], ['time_clock_entries.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sqlite_autoincrement=True
    )
    with op.batch_alter_table('time_clock_breaks', schema=None) as batch_op:
        batch_op.create_index('ix_time_clock_breaks_entry', ['time_clock_entry_id'], unique=False)

    # ==========================================================================
    # 8. TIME CLOCK CORRECTIONS TABLE
    # ==========================================================================
    op.create_table('time_clock_corrections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('time_clock_entry_id', sa.Integer(), nullable=False),
        sa.Column('original_clock_in_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('original_clock_out_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('corrected_clock_in_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('corrected_clock_out_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('submitted_by_user_id', sa.Integer(), nullable=False),
        sa.Column('submitted_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='PENDING'),
        sa.Column('approved_by_user_id', sa.Integer(), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('approval_notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['time_clock_entry_id'], ['time_clock_entries.id'], ),
        sa.ForeignKeyConstraint(['submitted_by_user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['approved_by_user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sqlite_autoincrement=True
    )
    with op.batch_alter_table('time_clock_corrections', schema=None) as batch_op:
        batch_op.create_index('ix_time_clock_corrections_entry', ['time_clock_entry_id'], unique=False)
        batch_op.create_index('ix_time_clock_corrections_status', ['status'], unique=False)

    # ==========================================================================
    # 9. IMPORT BATCHES TABLE
    # ==========================================================================
    op.create_table('import_batches',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('import_type', sa.String(length=32), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='CREATED'),
        sa.Column('source_file_name', sa.String(length=255), nullable=True),
        sa.Column('source_file_format', sa.String(length=16), nullable=True),
        sa.Column('total_rows', sa.Integer(), nullable=True),
        sa.Column('staged_rows', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('mapped_rows', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('posted_rows', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('error_rows', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('quarantined_rows', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('last_processed_row', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_by_user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version_id', sa.Integer(), nullable=False, server_default='1'),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sqlite_autoincrement=True
    )
    with op.batch_alter_table('import_batches', schema=None) as batch_op:
        batch_op.create_index('ix_import_batches_org_id', ['org_id'], unique=False)
        batch_op.create_index('ix_import_batches_org_status', ['org_id', 'status'], unique=False)
        batch_op.create_index('ix_import_batches_import_type', ['import_type'], unique=False)
        batch_op.create_index('ix_import_batches_status', ['status'], unique=False)

    # ==========================================================================
    # 10. IMPORT STAGING ROWS TABLE
    # ==========================================================================
    op.create_table('import_staging_rows',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('batch_id', sa.Integer(), nullable=False),
        sa.Column('row_number', sa.Integer(), nullable=False),
        sa.Column('raw_data', sa.Text(), nullable=False),
        sa.Column('foreign_id', sa.String(length=128), nullable=True),
        sa.Column('mapping_status', sa.String(length=16), nullable=False, server_default='PENDING'),
        sa.Column('posting_status', sa.String(length=16), nullable=False, server_default='PENDING'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('unmapped_references', sa.Text(), nullable=True),
        sa.Column('posted_entity_type', sa.String(length=64), nullable=True),
        sa.Column('posted_entity_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('posted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['batch_id'], ['import_batches.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sqlite_autoincrement=True
    )
    with op.batch_alter_table('import_staging_rows', schema=None) as batch_op:
        batch_op.create_index('ix_import_staging_batch_id', ['batch_id'], unique=False)
        batch_op.create_index('ix_import_staging_batch_status', ['batch_id', 'mapping_status'], unique=False)
        batch_op.create_index('ix_import_staging_batch_row', ['batch_id', 'row_number'], unique=False)
        batch_op.create_index('ix_import_staging_foreign_id', ['foreign_id'], unique=False)
        batch_op.create_index('ix_import_staging_mapping_status', ['mapping_status'], unique=False)
        batch_op.create_index('ix_import_staging_posting_status', ['posting_status'], unique=False)

    # ==========================================================================
    # 11. IMPORT ENTITY MAPPINGS TABLE
    # ==========================================================================
    op.create_table('import_entity_mappings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('batch_id', sa.Integer(), nullable=False),
        sa.Column('entity_type', sa.String(length=32), nullable=False),
        sa.Column('foreign_id', sa.String(length=128), nullable=False),
        sa.Column('local_entity_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='PENDING'),
        sa.Column('creation_data', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('mapped_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['batch_id'], ['import_batches.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('batch_id', 'entity_type', 'foreign_id', name='uq_import_mapping'),
        sqlite_autoincrement=True
    )
    with op.batch_alter_table('import_entity_mappings', schema=None) as batch_op:
        batch_op.create_index('ix_import_mapping_batch_id', ['batch_id'], unique=False)
        batch_op.create_index('ix_import_mapping_batch_entity', ['batch_id', 'entity_type'], unique=False)


def downgrade():
    # Drop tables in reverse order of creation (respect foreign keys)
    op.drop_table('import_entity_mappings')
    op.drop_table('import_staging_rows')
    op.drop_table('import_batches')
    op.drop_table('time_clock_corrections')
    op.drop_table('time_clock_breaks')
    op.drop_table('time_clock_entries')
    op.drop_table('user_permission_overrides')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('pin_hash')

    op.drop_table('receive_document_lines')
    op.drop_table('receive_documents')
    op.drop_table('vendors')
