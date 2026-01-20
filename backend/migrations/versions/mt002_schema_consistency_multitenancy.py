# Overview: Alembic migration for schema consistency multitenancy.

"""Multi-tenant schema consistency: document numbers, identifiers, roles

MIGRATION OVERVIEW:
This migration fixes schema inconsistencies for proper multi-tenant isolation:

1. DOCUMENT NUMBERS (Transfer, Count):
   - Remove global unique constraint on document_number
   - Add composite uniqueness per store: (from_store_id, document_number) for Transfer
   - Add composite uniqueness per store: (store_id, document_number) for Count
   - Add index on document_number for lookup performance

2. PRODUCT IDENTIFIERS:
   - Add org_id (required) and store_id (optional) columns
   - Backfill from Product.store_id -> Store.org_id
   - Replace global uniqueness with org-scoped: (org_id, type, value)
   - Add lookup indexes for common query patterns
   - Normalize values to uppercase (application layer recommendation)
   - Handle duplicates by deactivating older records

3. ROLES (RBAC):
   - Add org_id column to roles table
   - Backfill existing roles to default org
   - Change uniqueness from global to org-scoped: (org_id, name)

4. INDEXES:
   - Add missing composite indexes on high-volume tables
   - Sales: (store_id, status, created_at), document_number
   - Returns: (store_id, status, created_at), document_number

ROLLBACK WARNING:
This migration modifies constraints and adds columns. Test in non-production first.
Backfilled data will be lost on downgrade (org_id columns dropped).

Revision ID: mt002_schema_consistency
Revises: mt001_multi_tenant
Create Date: 2026-01-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column, select, and_, or_, func
from sqlalchemy import Integer, String, Boolean, DateTime


# revision identifiers, used by Alembic.
revision = 'mt002_schema_consistency'
down_revision = 'mt001_multi_tenant'
branch_labels = None
depends_on = None


def upgrade():
    # ==========================================================================
    # Fix Transfer document_number uniqueness
    # ==========================================================================
    print("Fixing Transfer.document_number uniqueness...")

    # Check if old unique constraint exists and drop it
    # Note: SQLite doesn't support DROP CONSTRAINT directly, need batch mode
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == 'sqlite':
        # SQLite requires batch mode for constraint changes
        with op.batch_alter_table('transfers', schema=None) as batch_op:
            # Try to drop the old unique constraint/index if it exists
            try:
                batch_op.drop_constraint('uq_transfers_document_number', type_='unique')
            except Exception:
                pass
            try:
                batch_op.drop_index('ix_transfers_document_number')
            except Exception:
                pass
    else:
        # PostgreSQL/MySQL
        try:
            op.drop_constraint('uq_transfers_document_number', 'transfers', type_='unique')
        except Exception:
            pass
        try:
            op.drop_index('ix_transfers_document_number', 'transfers')
        except Exception:
            pass

    # Add new composite uniqueness constraint and lookup index
    op.create_unique_constraint(
        'uq_transfers_store_docnum',
        'transfers',
        ['from_store_id', 'document_number']
    )
    op.create_index(
        'ix_transfers_document_number',
        'transfers',
        ['document_number']
    )

    # ==========================================================================
    # Fix Count document_number uniqueness
    # ==========================================================================
    print("Fixing Count.document_number uniqueness...")

    if dialect == 'sqlite':
        with op.batch_alter_table('counts', schema=None) as batch_op:
            try:
                batch_op.drop_constraint('uq_counts_document_number', type_='unique')
            except Exception:
                pass
            try:
                batch_op.drop_index('ix_counts_document_number')
            except Exception:
                pass
    else:
        try:
            op.drop_constraint('uq_counts_document_number', 'counts', type_='unique')
        except Exception:
            pass
        try:
            op.drop_index('ix_counts_document_number', 'counts')
        except Exception:
            pass

    # Add new composite uniqueness constraint and lookup index
    op.create_unique_constraint(
        'uq_counts_store_docnum',
        'counts',
        ['store_id', 'document_number']
    )
    op.create_index(
        'ix_counts_document_number',
        'counts',
        ['document_number']
    )

    # ==========================================================================
    # Add scoping columns to ProductIdentifier
    # ==========================================================================
    print("Adding org_id and store_id to product_identifiers...")

    # Add columns as nullable first
    op.add_column('product_identifiers',
        sa.Column('org_id', sa.Integer(), nullable=True))
    op.add_column('product_identifiers',
        sa.Column('store_id', sa.Integer(), nullable=True))

    # ==========================================================================
    # Backfill ProductIdentifier scope columns
    # ==========================================================================
    print("Backfilling ProductIdentifier org_id and store_id from Product -> Store...")

    # Backfill org_id and store_id from Product.store_id -> Store.org_id
    if dialect == 'sqlite':
        # SQLite subquery syntax
        op.execute("""
            UPDATE product_identifiers
            SET store_id = (
                SELECT p.store_id
                FROM products p
                WHERE p.id = product_identifiers.product_id
            ),
            org_id = (
                SELECT s.org_id
                FROM stores s
                JOIN products p ON p.store_id = s.id
                WHERE p.id = product_identifiers.product_id
            )
            WHERE org_id IS NULL
        """)
    else:
        # PostgreSQL/MySQL UPDATE FROM syntax
        op.execute("""
            UPDATE product_identifiers pi
            SET store_id = p.store_id,
                org_id = s.org_id
            FROM products p
            JOIN stores s ON p.store_id = s.id
            WHERE pi.product_id = p.id
            AND pi.org_id IS NULL
        """)

    # ==========================================================================
    # Handle identifier duplicates before adding constraint
    # ==========================================================================
    print("Resolving identifier duplicates (deactivating older records)...")

    # Deactivate duplicate identifiers, keeping only the most recent active one
    # Strategy: For each (org_id, type, value) group with multiple active records,
    # deactivate all but the one with the highest ID (most recent)
    if dialect == 'sqlite':
        # SQLite-compatible deduplication
        op.execute("""
            UPDATE product_identifiers
            SET is_active = 0,
                deactivated_at = CURRENT_TIMESTAMP
            WHERE id IN (
                SELECT pi1.id
                FROM product_identifiers pi1
                WHERE pi1.is_active = 1
                AND EXISTS (
                    SELECT 1 FROM product_identifiers pi2
                    WHERE pi2.org_id = pi1.org_id
                    AND pi2.type = pi1.type
                    AND pi2.value = pi1.value
                    AND pi2.is_active = 1
                    AND pi2.id > pi1.id
                )
            )
        """)
    else:
        # PostgreSQL deduplication using window functions
        op.execute("""
            WITH duplicates AS (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY org_id, type, value
                           ORDER BY id DESC
                       ) as rn
                FROM product_identifiers
                WHERE is_active = true
            )
            UPDATE product_identifiers
            SET is_active = false,
                deactivated_at = NOW()
            WHERE id IN (
                SELECT id FROM duplicates WHERE rn > 1
            )
        """)

    # ==========================================================================
    # Make org_id non-nullable and add constraints
    # ==========================================================================
    print("Making org_id non-nullable and adding constraints...")

    # Check for any remaining NULL org_id (shouldn't happen if products exist)
    # If there are orphaned identifiers, fail with clear error
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT COUNT(*) FROM product_identifiers WHERE org_id IS NULL"
    ))
    null_count = result.scalar()

    if null_count > 0:
        # Try to handle orphaned identifiers by deleting them
        print(f"WARNING: Found {null_count} identifiers with NULL org_id (orphaned). Deleting...")
        op.execute("DELETE FROM product_identifiers WHERE org_id IS NULL")

    # Make org_id non-nullable
    op.alter_column('product_identifiers', 'org_id', nullable=False)

    # Add foreign keys
    op.create_foreign_key(
        'fk_product_identifiers_org_id',
        'product_identifiers', 'organizations',
        ['org_id'], ['id']
    )
    op.create_foreign_key(
        'fk_product_identifiers_store_id',
        'product_identifiers', 'stores',
        ['store_id'], ['id']
    )

    # Drop old global uniqueness constraint
    if dialect == 'sqlite':
        with op.batch_alter_table('product_identifiers', schema=None) as batch_op:
            try:
                batch_op.drop_constraint('uq_identifier_type_value', type_='unique')
            except Exception:
                pass
    else:
        try:
            op.drop_constraint('uq_identifier_type_value', 'product_identifiers', type_='unique')
        except Exception:
            pass

    # Add new org-scoped uniqueness constraint
    op.create_unique_constraint(
        'uq_identifier_org_type_value',
        'product_identifiers',
        ['org_id', 'type', 'value']
    )

    # Add lookup indexes
    op.create_index(
        'ix_identifier_org_value',
        'product_identifiers',
        ['org_id', 'value']
    )
    op.create_index(
        'ix_identifier_org_type_active',
        'product_identifiers',
        ['org_id', 'type', 'is_active']
    )
    op.create_index(
        'ix_identifier_org_vendor_value',
        'product_identifiers',
        ['org_id', 'vendor_id', 'value']
    )

    # ==========================================================================
    # Add org_id to roles table
    # ==========================================================================
    print("Adding org_id to roles table...")

    # Add column as nullable first
    op.add_column('roles',
        sa.Column('org_id', sa.Integer(), nullable=True))

    # Backfill existing roles to default org (id=1)
    op.execute("UPDATE roles SET org_id = 1 WHERE org_id IS NULL")

    # Make column non-nullable
    op.alter_column('roles', 'org_id', nullable=False)

    # Add foreign key
    op.create_foreign_key(
        'fk_roles_org_id',
        'roles', 'organizations',
        ['org_id'], ['id']
    )

    # Drop old global uniqueness constraint on name
    if dialect == 'sqlite':
        with op.batch_alter_table('roles', schema=None) as batch_op:
            try:
                batch_op.drop_constraint('uq_roles_name', type_='unique')
            except Exception:
                pass
            try:
                batch_op.drop_index('ix_roles_name')
            except Exception:
                pass
    else:
        try:
            op.drop_constraint('uq_roles_name', 'roles', type_='unique')
        except Exception:
            pass
        try:
            op.drop_index('ix_roles_name', 'roles')
        except Exception:
            pass

    # Add org-scoped uniqueness constraint
    op.create_unique_constraint(
        'uq_roles_org_name',
        'roles',
        ['org_id', 'name']
    )

    # Add index for org_id lookups
    op.create_index('ix_roles_org_id', 'roles', ['org_id'])

    # ==========================================================================
    # Add missing indexes on high-volume tables
    # ==========================================================================
    print("Adding composite indexes for query optimization...")

    # Sales indexes
    try:
        op.create_index(
            'ix_sales_document_number',
            'sales',
            ['document_number']
        )
    except Exception:
        pass  # Index may already exist

    try:
        op.create_index(
            'ix_sales_store_status_created',
            'sales',
            ['store_id', 'status', 'created_at']
        )
    except Exception:
        pass

    # Returns indexes
    try:
        op.create_index(
            'ix_returns_document_number',
            'returns',
            ['document_number']
        )
    except Exception:
        pass

    try:
        op.create_index(
            'ix_returns_store_status_created',
            'returns',
            ['store_id', 'status', 'created_at']
        )
    except Exception:
        pass

    # Products index for active status lookups
    try:
        op.create_index(
            'ix_products_store_active',
            'products',
            ['store_id', 'is_active']
        )
    except Exception:
        pass

    print("Migration complete!")


def downgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name

    # ==========================================================================
    # REVERSE Drop added indexes
    # ==========================================================================
    print("Downgrade Removing added indexes...")

    for idx_name, table_name in [
        ('ix_products_store_active', 'products'),
        ('ix_returns_store_status_created', 'returns'),
        ('ix_returns_document_number', 'returns'),
        ('ix_sales_store_status_created', 'sales'),
        ('ix_sales_document_number', 'sales'),
    ]:
        try:
            op.drop_index(idx_name, table_name)
        except Exception:
            pass

    # ==========================================================================
    # REVERSE Remove org_id from roles
    # ==========================================================================
    print("Downgrade Removing org_id from roles...")

    op.drop_index('ix_roles_org_id', 'roles')
    op.drop_constraint('uq_roles_org_name', 'roles', type_='unique')
    op.drop_constraint('fk_roles_org_id', 'roles', type_='foreignkey')
    op.drop_column('roles', 'org_id')

    # Restore global uniqueness on name
    op.create_unique_constraint('uq_roles_name', 'roles', ['name'])

    # ==========================================================================
    # REVERSE Remove identifier constraints and columns
    # ==========================================================================
    print("Downgrade Removing identifier scoping...")

    # Drop new indexes and constraints
    for idx_name in [
        'ix_identifier_org_vendor_value',
        'ix_identifier_org_type_active',
        'ix_identifier_org_value',
    ]:
        try:
            op.drop_index(idx_name, 'product_identifiers')
        except Exception:
            pass

    op.drop_constraint('uq_identifier_org_type_value', 'product_identifiers', type_='unique')
    op.drop_constraint('fk_product_identifiers_store_id', 'product_identifiers', type_='foreignkey')
    op.drop_constraint('fk_product_identifiers_org_id', 'product_identifiers', type_='foreignkey')

    # Drop columns
    op.drop_column('product_identifiers', 'store_id')
    op.drop_column('product_identifiers', 'org_id')

    # Restore old global uniqueness (WARNING: may fail if duplicates were created)
    op.create_unique_constraint(
        'uq_identifier_type_value',
        'product_identifiers',
        ['type', 'value']
    )

    # ==========================================================================
    # REVERSE Restore Count global uniqueness
    # ==========================================================================
    print("Downgrade Restoring Count global uniqueness...")

    op.drop_index('ix_counts_document_number', 'counts')
    op.drop_constraint('uq_counts_store_docnum', 'counts', type_='unique')

    # Restore global uniqueness (WARNING: may fail if duplicates exist)
    if dialect == 'sqlite':
        with op.batch_alter_table('counts', schema=None) as batch_op:
            batch_op.create_unique_constraint('uq_counts_document_number', ['document_number'])
    else:
        op.create_unique_constraint('uq_counts_document_number', 'counts', ['document_number'])

    # ==========================================================================
    # REVERSE Restore Transfer global uniqueness
    # ==========================================================================
    print("Downgrade Restoring Transfer global uniqueness...")

    op.drop_index('ix_transfers_document_number', 'transfers')
    op.drop_constraint('uq_transfers_store_docnum', 'transfers', type_='unique')

    # Restore global uniqueness (WARNING: may fail if duplicates exist)
    if dialect == 'sqlite':
        with op.batch_alter_table('transfers', schema=None) as batch_op:
            batch_op.create_unique_constraint('uq_transfers_document_number', ['document_number'])
    else:
        op.create_unique_constraint('uq_transfers_document_number', 'transfers', ['document_number'])

    print("Downgrade complete!")
