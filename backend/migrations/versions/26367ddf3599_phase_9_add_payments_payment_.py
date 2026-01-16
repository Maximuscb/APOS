"""Phase 9: Add payments, payment_transactions, and update sales for payment tracking

Revision ID: 26367ddf3599
Revises: 3e5954ad8d19
Create Date: 2026-01-14 17:56:06.453452

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '26367ddf3599'
down_revision = '3e5954ad8d19'
branch_labels = None
depends_on = None


def upgrade():
    # NOTE: Phase 9 only adds payment tracking to sales and creates payment tables
    # cash_drawer_events, sale_lines already exist from earlier migrations

    # Add payment-related columns to existing sales table
    # Note: register_id and register_session_id already added in Phase 8
    with op.batch_alter_table('sales', schema=None) as batch_op:
        batch_op.add_column(sa.Column('payment_status', sa.String(length=16), nullable=False, server_default='UNPAID'))
        batch_op.add_column(sa.Column('total_due_cents', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('total_paid_cents', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('change_due_cents', sa.Integer(), nullable=False, server_default='0'))
        batch_op.create_index(batch_op.f('ix_sales_payment_status'), ['payment_status'], unique=False)

    # Create payments table
    op.create_table('payments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('sale_id', sa.Integer(), nullable=False),
    sa.Column('tender_type', sa.String(length=32), nullable=False),
    sa.Column('amount_cents', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('reference_number', sa.String(length=128), nullable=True),
    sa.Column('change_cents', sa.Integer(), nullable=True),
    sa.Column('created_by_user_id', sa.Integer(), nullable=False),
    sa.Column('voided_by_user_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('voided_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('void_reason', sa.String(length=255), nullable=True),
    sa.Column('register_id', sa.Integer(), nullable=True),
    sa.Column('register_session_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['register_id'], ['registers.id'], ),
    sa.ForeignKeyConstraint(['register_session_id'], ['register_sessions.id'], ),
    sa.ForeignKeyConstraint(['sale_id'], ['sales.id'], ),
    sa.ForeignKeyConstraint(['voided_by_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sqlite_autoincrement=True
    )
    with op.batch_alter_table('payments', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_payments_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_payments_created_by_user_id'), ['created_by_user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_payments_register_id'), ['register_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_payments_register_session_id'), ['register_session_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_payments_sale_id'), ['sale_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_payments_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_payments_tender_type'), ['tender_type'], unique=False)

    # Create payment_transactions table
    op.create_table('payment_transactions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('payment_id', sa.Integer(), nullable=False),
    sa.Column('sale_id', sa.Integer(), nullable=False),
    sa.Column('transaction_type', sa.String(length=16), nullable=False),
    sa.Column('amount_cents', sa.Integer(), nullable=False),
    sa.Column('tender_type', sa.String(length=32), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('reason', sa.String(length=255), nullable=True),
    sa.Column('occurred_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('register_id', sa.Integer(), nullable=True),
    sa.Column('register_session_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['payment_id'], ['payments.id'], ),
    sa.ForeignKeyConstraint(['register_id'], ['registers.id'], ),
    sa.ForeignKeyConstraint(['register_session_id'], ['register_sessions.id'], ),
    sa.ForeignKeyConstraint(['sale_id'], ['sales.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sqlite_autoincrement=True
    )
    with op.batch_alter_table('payment_transactions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_payment_transactions_occurred_at'), ['occurred_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_payment_transactions_payment_id'), ['payment_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_payment_transactions_register_id'), ['register_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_payment_transactions_register_session_id'), ['register_session_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_payment_transactions_sale_id'), ['sale_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_payment_transactions_tender_type'), ['tender_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_payment_transactions_transaction_type'), ['transaction_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_payment_transactions_user_id'), ['user_id'], unique=False)
        batch_op.create_index('ix_payment_txns_occurred', ['occurred_at'], unique=False)
        batch_op.create_index('ix_payment_txns_sale_occurred', ['sale_id', 'occurred_at'], unique=False)


def downgrade():
    # Remove payment-related tables and columns
    with op.batch_alter_table('payment_transactions', schema=None) as batch_op:
        batch_op.drop_index('ix_payment_txns_sale_occurred')
        batch_op.drop_index('ix_payment_txns_occurred')
        batch_op.drop_index(batch_op.f('ix_payment_transactions_user_id'))
        batch_op.drop_index(batch_op.f('ix_payment_transactions_transaction_type'))
        batch_op.drop_index(batch_op.f('ix_payment_transactions_tender_type'))
        batch_op.drop_index(batch_op.f('ix_payment_transactions_sale_id'))
        batch_op.drop_index(batch_op.f('ix_payment_transactions_register_session_id'))
        batch_op.drop_index(batch_op.f('ix_payment_transactions_register_id'))
        batch_op.drop_index(batch_op.f('ix_payment_transactions_payment_id'))
        batch_op.drop_index(batch_op.f('ix_payment_transactions_occurred_at'))

    op.drop_table('payment_transactions')

    with op.batch_alter_table('payments', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_payments_tender_type'))
        batch_op.drop_index(batch_op.f('ix_payments_status'))
        batch_op.drop_index(batch_op.f('ix_payments_sale_id'))
        batch_op.drop_index(batch_op.f('ix_payments_register_session_id'))
        batch_op.drop_index(batch_op.f('ix_payments_register_id'))
        batch_op.drop_index(batch_op.f('ix_payments_created_by_user_id'))
        batch_op.drop_index(batch_op.f('ix_payments_created_at'))

    op.drop_table('payments')

    with op.batch_alter_table('sales', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_sales_payment_status'))
        batch_op.drop_column('change_due_cents')
        batch_op.drop_column('total_paid_cents')
        batch_op.drop_column('total_due_cents')
        batch_op.drop_column('payment_status')
        # Note: register_id and register_session_id remain (from Phase 8)
