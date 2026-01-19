"""Multi-tenant: Add organizations table and org_id to stores/users/sessions

MULTI-TENANT MIGRATION:
1. Creates 'organizations' table as the tenant root
2. Adds org_id to stores, users, session_tokens, security_events
3. Creates default organization and backfills existing data
4. Updates uniqueness constraints to be tenant-scoped
5. Adds indexes for efficient tenant-scoped queries

Revision ID: mt001_multi_tenant
Revises: h4i5j6k7l8m9
Create Date: 2026-01-19

ROLLBACK WARNING: This migration modifies foreign key constraints.
Test rollback in a non-production environment first.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column


# revision identifiers, used by Alembic.
revision = 'mt001_multi_tenant'
down_revision = 'h4i5j6k7l8m9'
branch_labels = None
depends_on = None


def upgrade():
    # ==========================================================================
    # STEP 1: Create organizations table
    # ==========================================================================
    op.create_table('organizations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('code', sa.String(length=32), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_organizations_code', 'organizations', ['code'], unique=True)
    op.create_index('ix_organizations_is_active', 'organizations', ['is_active'])

    # ==========================================================================
    # STEP 2: Create default organization and backfill
    # ==========================================================================
    # Insert default organization for existing data
    organizations = table('organizations',
        column('id', sa.Integer),
        column('name', sa.String),
        column('code', sa.String),
        column('is_active', sa.Boolean)
    )
    op.execute(
        organizations.insert().values(
            id=1,
            name='Default Organization',
            code='DEFAULT',
            is_active=True
        )
    )

    # ==========================================================================
    # STEP 3: Add org_id to stores table
    # ==========================================================================
    # Add column as nullable first for backfill
    op.add_column('stores', sa.Column('org_id', sa.Integer(), nullable=True))

    # Backfill existing stores to default org
    op.execute("UPDATE stores SET org_id = 1 WHERE org_id IS NULL")

    # Make column non-nullable
    op.alter_column('stores', 'org_id', nullable=False)

    # Add foreign key and index
    op.create_foreign_key('fk_stores_org_id', 'stores', 'organizations', ['org_id'], ['id'])
    op.create_index('ix_stores_org_id', 'stores', ['org_id'])

    # Drop old global uniqueness constraints
    op.drop_constraint('uq_stores_name', 'stores', type_='unique')
    op.drop_index('ix_stores_code', 'stores')
    op.drop_constraint('uq_stores_code', 'stores', type_='unique')

    # Add tenant-scoped uniqueness constraints
    op.create_unique_constraint('uq_stores_org_name', 'stores', ['org_id', 'name'])
    op.create_unique_constraint('uq_stores_org_code', 'stores', ['org_id', 'code'])

    # ==========================================================================
    # STEP 4: Add org_id to users table
    # ==========================================================================
    op.add_column('users', sa.Column('org_id', sa.Integer(), nullable=True))

    # Backfill existing users to default org
    op.execute("UPDATE users SET org_id = 1 WHERE org_id IS NULL")

    # Make column non-nullable
    op.alter_column('users', 'org_id', nullable=False)

    # Add foreign key and index
    op.create_foreign_key('fk_users_org_id', 'users', 'organizations', ['org_id'], ['id'])
    op.create_index('ix_users_org_id', 'users', ['org_id'])

    # Drop old global uniqueness constraints
    op.drop_constraint('uq_users_username', 'users', type_='unique')
    op.drop_constraint('uq_users_email', 'users', type_='unique')

    # Add tenant-scoped uniqueness constraints
    op.create_unique_constraint('uq_users_org_username', 'users', ['org_id', 'username'])
    op.create_unique_constraint('uq_users_org_email', 'users', ['org_id', 'email'])

    # ==========================================================================
    # STEP 5: Add org_id and store_id to session_tokens table
    # ==========================================================================
    op.add_column('session_tokens', sa.Column('org_id', sa.Integer(), nullable=True))
    op.add_column('session_tokens', sa.Column('store_id', sa.Integer(), nullable=True))

    # Backfill from user's org_id and store_id
    op.execute("""
        UPDATE session_tokens
        SET org_id = (SELECT org_id FROM users WHERE users.id = session_tokens.user_id),
            store_id = (SELECT store_id FROM users WHERE users.id = session_tokens.user_id)
        WHERE org_id IS NULL
    """)

    # Make org_id non-nullable (store_id can remain nullable for org-level users)
    op.alter_column('session_tokens', 'org_id', nullable=False)

    # Add foreign keys and indexes
    op.create_foreign_key('fk_session_tokens_org_id', 'session_tokens', 'organizations', ['org_id'], ['id'])
    op.create_foreign_key('fk_session_tokens_store_id', 'session_tokens', 'stores', ['store_id'], ['id'])
    op.create_index('ix_session_tokens_org_id', 'session_tokens', ['org_id'])

    # ==========================================================================
    # STEP 6: Add org_id and store_id to security_events table
    # ==========================================================================
    op.add_column('security_events', sa.Column('org_id', sa.Integer(), nullable=True))
    op.add_column('security_events', sa.Column('store_id', sa.Integer(), nullable=True))

    # Backfill from user's org_id (nullable - some events may be pre-auth)
    op.execute("""
        UPDATE security_events
        SET org_id = (SELECT org_id FROM users WHERE users.id = security_events.user_id)
        WHERE org_id IS NULL AND user_id IS NOT NULL
    """)

    # Add foreign keys and indexes (org_id remains nullable for pre-auth events)
    op.create_foreign_key('fk_security_events_org_id', 'security_events', 'organizations', ['org_id'], ['id'])
    op.create_foreign_key('fk_security_events_store_id', 'security_events', 'stores', ['store_id'], ['id'])
    op.create_index('ix_security_events_org_occurred', 'security_events', ['org_id', 'occurred_at'])


def downgrade():
    # ==========================================================================
    # REVERSE STEP 6: Remove org_id/store_id from security_events
    # ==========================================================================
    op.drop_index('ix_security_events_org_occurred', 'security_events')
    op.drop_constraint('fk_security_events_store_id', 'security_events', type_='foreignkey')
    op.drop_constraint('fk_security_events_org_id', 'security_events', type_='foreignkey')
    op.drop_column('security_events', 'store_id')
    op.drop_column('security_events', 'org_id')

    # ==========================================================================
    # REVERSE STEP 5: Remove org_id/store_id from session_tokens
    # ==========================================================================
    op.drop_index('ix_session_tokens_org_id', 'session_tokens')
    op.drop_constraint('fk_session_tokens_store_id', 'session_tokens', type_='foreignkey')
    op.drop_constraint('fk_session_tokens_org_id', 'session_tokens', type_='foreignkey')
    op.drop_column('session_tokens', 'store_id')
    op.drop_column('session_tokens', 'org_id')

    # ==========================================================================
    # REVERSE STEP 4: Remove org_id from users, restore global uniqueness
    # ==========================================================================
    op.drop_constraint('uq_users_org_email', 'users', type_='unique')
    op.drop_constraint('uq_users_org_username', 'users', type_='unique')
    op.drop_index('ix_users_org_id', 'users')
    op.drop_constraint('fk_users_org_id', 'users', type_='foreignkey')
    op.drop_column('users', 'org_id')
    op.create_unique_constraint('uq_users_email', 'users', ['email'])
    op.create_unique_constraint('uq_users_username', 'users', ['username'])

    # ==========================================================================
    # REVERSE STEP 3: Remove org_id from stores, restore global uniqueness
    # ==========================================================================
    op.drop_constraint('uq_stores_org_code', 'stores', type_='unique')
    op.drop_constraint('uq_stores_org_name', 'stores', type_='unique')
    op.drop_index('ix_stores_org_id', 'stores')
    op.drop_constraint('fk_stores_org_id', 'stores', type_='foreignkey')
    op.drop_column('stores', 'org_id')
    op.create_unique_constraint('uq_stores_code', 'stores', ['code'])
    op.create_index('ix_stores_code', 'stores', ['code'], unique=True)
    op.create_unique_constraint('uq_stores_name', 'stores', ['name'])

    # ==========================================================================
    # REVERSE STEP 1-2: Drop organizations table
    # ==========================================================================
    op.drop_index('ix_organizations_is_active', 'organizations')
    op.drop_index('ix_organizations_code', 'organizations')
    op.drop_table('organizations')
