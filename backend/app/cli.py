# Overview: Flask CLI command groups for bootstrap, inspection, and maintenance.

# backend/app/cli.py
# Commands Legend (run from the backend directory):
# Prereqs:
# - Activate your virtualenv.
# - Set FLASK_APP to wsgi.py (PowerShell: $env:FLASK_APP="wsgi.py").
# - Use: python -m flask <group> <command> [options]
#
# System bootstrap/repair:
# - python -m flask system init [--org "Org Name"]
#   Full idempotent bootstrap: creates default org, store, roles, permissions, and users.
# - python -m flask system init-roles
#   Create default roles only (admin, manager, cashier).
# - python -m flask system init-permissions
#   Initialize permissions and assign defaults to roles.
# - python -m flask system reset-db --yes
#   DEV/TEST only: drop and recreate all tables (deletes all data).
# - python -m flask system wipe --yes
#   Clear all transactional data but keep default users, org, store, roles, and permissions.
#
# Organization management (MULTI-TENANT):
# - python -m flask orgs list
#   List all organizations.
# - python -m flask orgs create --name "Acme Corp" --code "ACME"
#   Create a new organization (tenant).
#
# User inspection/bootstrap:
# - python -m flask users list [--org-id 1]
#   List all users with roles and active status.
# - python -m flask users create --org-id 1 --username admin --email admin@apos.local --password "Password123!" --role admin
#   Create a user (prompts if options are omitted).
# - python -m flask users create-developer --username dev --email dev@apos.local --password "Password123!"
#   Create a cross-org developer superuser (no org, is_developer=True).
#
# Permission inspection/repair:
# - python -m flask perms list --category SALES
#   List permissions (optionally filtered by role or category).
# - python -m flask perms check admin SYSTEM_ADMIN
#   Check whether a user has a permission.
# - python -m flask perms enforce-developer-access --dry-run
#   Audit DEVELOPER_ACCESS assignments and overrides.
# - python -m flask perms enforce-developer-access --fix
#   Remove DEVELOPER_ACCESS from non-developer roles and disable overrides.
# - python -m flask perms grant cashier VOID_SALE
#   Grant a permission to a role.
# - python -m flask perms revoke cashier VOID_SALE
#   Revoke a permission from a role.
#
# Register inspection/bootstrap:
# - python -m flask registers list --store-id 1
#   List registers (use --all to include inactive).
# - python -m flask registers create --store-id 1 --number "REG-01" --name "Front Counter 1" --location "Main Floor"
#   Create a new POS register.
# - python -m flask registers sessions --status OPEN --limit 20
#   List recent register sessions with optional filters.
#
# Maintenance:
# - python -m flask maintenance cleanup-security-events --retention-days 90
#   Delete security events older than the retention window.

import click
from datetime import timedelta
from flask.cli import with_appcontext

from .extensions import db
from .models import Store, User, Role, UserRole, Permission, RolePermission, Organization, UserPermissionOverride
from .services.auth_service import create_user, create_default_roles, assign_role, hash_password, PasswordValidationError
from .services import permission_service
from .services import maintenance_service
from .services.ledger_service import ensure_org_master_ledger
from .time_utils import utcnow


@click.group('system')
def system_group():
    """System bootstrap and repair commands."""


@system_group.command('init')
@click.option('--org', 'org_name', default='Default Organization', help='Organization name')
@click.option('--org-code', default='DEFAULT', help='Organization code')
@with_appcontext
def init_system(org_name, org_code):
    """
    Initialize complete APOS system: organization, roles, default users, and default store.

    MULTI-TENANT: Creates a default organization as the tenant root.
    All stores and users are scoped to this organization.

    Creates:
    - Default organization (if none exists)
    - Default store within the organization
    - Roles: admin, manager, cashier
    - Users: admin/admin@apos.local, manager/manager@apos.local, cashier/cashier@apos.local
    - All passwords default to: "Password123!"

    SECURITY: Change passwords immediately in production!
    """
    click.echo("START Initializing APOS system...")

    # 1. Ensure default organization exists
    org = db.session.query(Organization).first()
    if not org:
        org = Organization(name=org_name, code=org_code, is_active=True)
        db.session.add(org)
        db.session.commit()
        click.echo(f"PASS Created default organization: {org.name} (ID: {org.id}, Code: {org.code})")
    else:
        click.echo(f"PASS Using existing organization: {org.name} (ID: {org.id})")

    ensure_org_master_ledger(org.id)
    db.session.commit()

    # 2. Ensure default store exists within the organization
    store = db.session.query(Store).filter_by(org_id=org.id).first()
    if not store:
        store = Store(org_id=org.id, name="Main Store")
        db.session.add(store)
        db.session.commit()
        click.echo(f"PASS Created default store: {store.name} (ID: {store.id}, Org: {org.name})")
    else:
        click.echo(f"PASS Using existing store: {store.name} (ID: {store.id})")

    # 3. Create roles
    click.echo("\nLIST Creating roles...")
    create_default_roles(org.id)
    roles = db.session.query(Role).all()
    click.echo(f"PASS Roles created: {', '.join(r.name for r in roles)}")

    # 4. Initialize permissions
    click.echo("\nSECURITY Initializing permissions...")
    perm_count = permission_service.initialize_permissions()
    assignment_count = permission_service.assign_default_role_permissions()
    click.echo(f"PASS Created {perm_count} permissions, {assignment_count} role assignments")

    # 5. Create default users (within the organization)
    click.echo("\nUSERS Creating default users...")

    # Default password meets requirements:
    # - Minimum 8 characters
    # - Uppercase, lowercase, digit, special char
    default_password = "Password123!"

    default_users = [
        ("admin", "admin@apos.local", "admin", default_password),
        ("developer", "developer@apos.local", "developer", default_password),
        ("manager", "manager@apos.local", "manager", default_password),
        ("cashier", "cashier@apos.local", "cashier", default_password),
    ]

    for username, email, role_name, password in default_users:
        try:
            # Check if user exists in this org
            existing = db.session.query(User).filter_by(
                org_id=org.id,
                username=username
            ).first()
            if existing:
                click.echo(f"WARN  User '{username}' already exists in org, skipping...")
                continue

            # Create user with org_id (password will be hashed with bcrypt and validated)
            user = create_user(
                username=username,
                email=email,
                password=password,
                org_id=org.id,
                store_id=store.id
            )

            # Assign role
            assign_role(user.id, role_name)

            click.echo(f"PASS Created user: {username} ({email}) with role '{role_name}'")

        except PasswordValidationError as e:
            click.echo(f"FAIL Password validation failed for '{username}': {str(e)}")
        except Exception as e:
            click.echo(f"FAIL Failed to create user '{username}': {str(e)}")

    click.echo("\n" + "="*60)
    click.echo("DONE APOS System Initialized Successfully!")
    click.echo("="*60)
    click.echo(f"\nOrganization: {org.name} (ID: {org.id})")
    click.echo(f"Store: {store.name} (ID: {store.id})")
    click.echo("\nDefault Credentials (CHANGE IN PRODUCTION!):")
    click.echo("   admin     -> admin@apos.local     / Password123!")
    click.echo("   developer -> developer@apos.local / Password123!")
    click.echo("   manager   -> manager@apos.local   / Password123!")
    click.echo("   cashier   -> cashier@apos.local   / Password123!")
    click.echo("\nSECURITY SECURITY WARNING:")
    click.echo("   - Passwords are now hashed with bcrypt (secure)")
    click.echo("   - Change all passwords immediately in production!")
    click.echo("   - Password requirements: 8+ chars, uppercase, lowercase, digit, special char")
    click.echo("")


@system_group.command('init-roles')
@with_appcontext
def init_roles():
    """Create default roles (admin, manager, cashier)."""
    org = db.session.query(Organization).first()
    if not org:
        click.echo("FAIL No organization exists. Run: python -m flask system init")
        return
    click.echo("LIST Creating default roles...")
    create_default_roles(org.id)
    roles = db.session.query(Role).all()
    click.echo(f"PASS Created roles: {', '.join(r.name for r in roles)}")


# =============================================================================
# ORGANIZATION MANAGEMENT COMMANDS (MULTI-TENANT)
# =============================================================================

@click.group('orgs')
def orgs_group():
    """Organization (tenant) management commands."""


@orgs_group.command('list')
@with_appcontext
def list_orgs():
    """List all organizations."""
    orgs = db.session.query(Organization).all()

    if not orgs:
        click.echo("No organizations found.")
        return

    click.echo("\n" + "="*80)
    click.echo(f"{'ID':<5} {'Name':<30} {'Code':<15} {'Active':<8} {'Stores':<8} {'Users'}")
    click.echo("="*80)

    for org in orgs:
        store_count = db.session.query(Store).filter_by(org_id=org.id).count()
        user_count = db.session.query(User).filter_by(org_id=org.id).count()
        active_str = "Yes" if org.is_active else "No"

        click.echo(f"{org.id:<5} {org.name:<30} {org.code or '-':<15} {active_str:<8} {store_count:<8} {user_count}")

    click.echo("="*80 + "\n")


@orgs_group.command('create')
@click.option('--name', required=True, help='Organization name')
@click.option('--code', required=True, help='Short code (unique)')
@with_appcontext
def create_org_cli(name, code):
    """Create a new organization (tenant)."""
    existing = db.session.query(Organization).filter_by(code=code).first()
    if existing:
        click.echo(f"FAIL Organization with code '{code}' already exists")
        return

    org = Organization(name=name, code=code, is_active=True)
    db.session.add(org)
    db.session.flush()
    ensure_org_master_ledger(org.id)
    db.session.commit()

    click.echo(f"PASS Created organization: {org.name} (ID: {org.id}, Code: {org.code})")


@orgs_group.command('add-store')
@click.option('--org-id', type=int, required=True, help='Organization ID')
@click.option('--name', required=True, help='Store name')
@click.option('--code', help='Store code (unique within org)')
@with_appcontext
def add_store_to_org_cli(org_id, name, code):
    """Add a store to an organization."""
    org = db.session.query(Organization).filter_by(id=org_id).first()
    if not org:
        click.echo(f"FAIL Organization ID {org_id} not found")
        return

    # Check name uniqueness within org
    existing = db.session.query(Store).filter_by(org_id=org_id, name=name).first()
    if existing:
        click.echo(f"FAIL Store '{name}' already exists in this organization")
        return

    store = Store(org_id=org_id, name=name, code=code)
    db.session.add(store)
    db.session.commit()

    click.echo(f"PASS Created store: {store.name} (ID: {store.id}) in org '{org.name}'")


# =============================================================================
# USER MANAGEMENT COMMANDS
# =============================================================================

@click.group('users')
def users_group():
    """User inspection and bootstrap commands."""


@users_group.command('create')
@click.option('--org-id', type=int, help='Organization ID (uses default if not specified)')
@click.option('--username', prompt=True, help='Username')
@click.option('--email', prompt=True, help='Email address')
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='Password')
@click.option('--role', type=click.Choice(['admin', 'manager', 'cashier']), prompt=True, help='Role')
@with_appcontext
def create_user_cli(org_id, username, email, password, role):
    """
    Create a new user interactively.

    MULTI-TENANT: User is created within the specified organization.
    If --org-id is not provided, uses the first (default) organization.

    Password must meet strength requirements:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character
    """
    try:
        # Get organization
        if org_id:
            org = db.session.query(Organization).filter_by(id=org_id).first()
            if not org:
                click.echo(f"FAIL Organization ID {org_id} not found")
                return
        else:
            org = db.session.query(Organization).first()
            if not org:
                click.echo("FAIL No organization found. Run 'python -m flask system init' first.")
                return

        # Get default store for this org
        store = db.session.query(Store).filter_by(org_id=org.id).first()
        if not store:
            click.echo(f"FAIL No store found in organization '{org.name}'. Create a store first.")
            return

        # Create user with org_id (password will be hashed with bcrypt and validated)
        user = create_user(
            username=username,
            email=email,
            password=password,
            org_id=org.id,
            store_id=store.id
        )

        # Assign role
        assign_role(user.id, role)

        click.echo(f"PASS Created user: {username} ({email}) with role '{role}'")
        click.echo(f"     Organization: {org.name} (ID: {org.id})")
        click.echo("SECURITY Password securely hashed with bcrypt")

    except PasswordValidationError as e:
        click.echo(f"FAIL Password validation failed: {str(e)}")
        click.echo("Requirements: 8+ chars, uppercase, lowercase, digit, special char")
    except Exception as e:
        click.echo(f"FAIL Failed to create user: {str(e)}")


@users_group.command('create-developer')
@click.option('--username', prompt=True, help='Username')
@click.option('--email', prompt=True, help='Email address')
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='Password')
@with_appcontext
def create_developer_cli(username, email, password):
    """
    Create a developer (cross-org superuser) account.

    Developer users have is_developer=True and no org_id,
    allowing them to switch between organizations via the UI.
    They receive the 'developer' role with all permissions
    including DEVELOPER_ACCESS.
    """
    try:
        existing = db.session.query(User).filter_by(username=username).first()
        if existing:
            click.echo(f"FAIL User '{username}' already exists")
            return

        password_hash = hash_password(password)
        user = User(
            org_id=None,
            username=username,
            email=email,
            password_hash=password_hash,
            store_id=None,
            is_developer=True,
        )
        db.session.add(user)
        db.session.commit()

        # Try to assign developer role (needs an org-scoped role — create if needed)
        role = db.session.query(Role).filter_by(name='developer').first()
        if role:
            assign_role(user.id, 'developer')
            click.echo(f"PASS Assigned 'developer' role")
        else:
            click.echo("WARN  No 'developer' role found — run 'flask system init-permissions' to create roles")

        click.echo(f"PASS Created developer user: {username} ({email})")
        click.echo(f"     is_developer = True, org_id = None")
        click.echo(f"     User ID: {user.id}")
        click.echo("")
        click.echo("To use: log in, then use the org switcher in the top banner to pick an organization.")

    except PasswordValidationError as e:
        click.echo(f"FAIL Password validation failed: {str(e)}")
        click.echo("Requirements: 8+ chars, uppercase, lowercase, digit, special char")
    except Exception as e:
        click.echo(f"FAIL Failed to create developer: {str(e)}")


@users_group.command('list')
@click.option('--org-id', type=int, help='Filter by organization ID')
@with_appcontext
def list_users(org_id):
    """List all users with their roles."""
    query = db.session.query(User)

    if org_id:
        query = query.filter_by(org_id=org_id)

    users = query.all()

    if not users:
        click.echo("No users found.")
        return

    click.echo("\n" + "="*100)
    click.echo(f"{'ID':<5} {'Org':<5} {'Username':<20} {'Email':<30} {'Active':<8} {'Roles'}")
    click.echo("="*100)

    for user in users:
        # Get user roles
        user_roles = db.session.query(UserRole).filter_by(user_id=user.id).all()
        role_names = []
        for ur in user_roles:
            role = db.session.query(Role).get(ur.role_id)
            if role:
                role_names.append(role.name)

        roles_str = ", ".join(role_names) if role_names else "none"
        active_str = "Yes" if user.is_active else "No"

        click.echo(f"{user.id:<5} {user.org_id:<5} {user.username:<20} {user.email:<30} {active_str:<8} {roles_str}")

    click.echo("="*100 + "\n")


@system_group.command('reset-db')
@click.option('--yes', is_flag=True, help='Skip confirmation')
@with_appcontext
def reset_db(yes):
    """
    DANGER: Drop all tables and recreate schema.

    This will DELETE ALL DATA!
    """
    if not yes:
        click.confirm("WARN This will DELETE ALL DATA. Are you sure?", abort=True)

    click.echo("DELETE  Dropping all tables...")
    db.drop_all()

    click.echo("BUILD  Creating all tables...")
    db.create_all()

    click.echo("PASS Database reset complete. Run 'python -m flask system init' to initialize.")


@system_group.command('wipe')
@click.option('--yes', is_flag=True, help='Skip confirmation')
@with_appcontext
def wipe_data(yes):
    """
    Clear all transactional data while preserving system structure.

    Keeps: default users (admin, developer, manager, cashier),
    the default organization, default store, roles, permissions,
    and role-permission assignments.

    Removes: all sales, inventory, documents, registers, timekeeping,
    communications, promotions, imports, audit logs, sessions,
    extra users, extra orgs/stores, and user permission overrides.
    """
    if not yes:
        click.confirm("WARN This will DELETE all transactional data. Are you sure?", abort=True)

    # Lazy imports to avoid bloating module-level imports
    from .models.auth import SessionToken
    from .models.security import SecurityEvent
    from .models.inventory import (
        Product, InventoryTransaction, ProductIdentifier, Vendor,
        ReceiveDocument, ReceiveDocumentLine,
    )
    from .models.sales import Sale, SaleLine, Payment, PaymentTransaction
    from .models.documents import (
        Return, ReturnLine, Transfer, TransferLine,
        Count, CountLine, MasterLedgerEvent, DocumentSequence,
    )
    from .models.registers import Register, RegisterSession, CashDrawerEvent, CashDrawer, Printer
    from .models.timekeeping import TimeClockEntry, TimeClockBreak, TimeClockCorrection
    from .models.imports import ImportBatch, ImportStagingRow, ImportEntityMapping
    from .models.communications import Announcement, Reminder, Task
    from .models.promotions import Promotion
    from .models.settings import OrganizationSetting, DeviceSetting
    from .models.tenancy import StoreConfig

    click.echo("WIPE  Clearing transactional data...")

    default_usernames = ['admin', 'developer', 'manager', 'cashier']
    default_users = db.session.query(User).filter(User.username.in_(default_usernames)).all()
    default_user_ids = [u.id for u in default_users]

    if not default_user_ids:
        click.echo("WARN  No default users found — nothing to preserve. Run 'flask system init' first.")
        return

    # Determine the default org (from admin user)
    admin_user = next((u for u in default_users if u.username == 'admin'), default_users[0])
    default_org_id = admin_user.org_id

    # Delete in FK-safe order (children before parents)
    tables = [
        # Timekeeping
        ("TimeClockBreak", TimeClockBreak),
        ("TimeClockCorrection", TimeClockCorrection),
        ("TimeClockEntry", TimeClockEntry),
        # Registers
        ("CashDrawerEvent", CashDrawerEvent),
        ("RegisterSession", RegisterSession),
        ("Printer", Printer),
        ("CashDrawer", CashDrawer),
        ("DeviceSetting", DeviceSetting),
        ("Register", Register),
        # Sales
        ("PaymentTransaction", PaymentTransaction),
        ("Payment", Payment),
        ("ReturnLine", ReturnLine),
        ("Return", Return),
        ("SaleLine", SaleLine),
        ("Sale", Sale),
        # Documents
        ("ReceiveDocumentLine", ReceiveDocumentLine),
        ("ReceiveDocument", ReceiveDocument),
        ("TransferLine", TransferLine),
        ("Transfer", Transfer),
        ("CountLine", CountLine),
        ("Count", Count),
        # Inventory
        ("InventoryTransaction", InventoryTransaction),
        ("ProductIdentifier", ProductIdentifier),
        ("Product", Product),
        ("Vendor", Vendor),
        # Imports
        ("ImportEntityMapping", ImportEntityMapping),
        ("ImportStagingRow", ImportStagingRow),
        ("ImportBatch", ImportBatch),
        # Communications & Promotions
        ("Announcement", Announcement),
        ("Reminder", Reminder),
        ("Task", Task),
        ("Promotion", Promotion),
        # Audit & Events
        ("MasterLedgerEvent", MasterLedgerEvent),
        ("SecurityEvent", SecurityEvent),
        ("DocumentSequence", DocumentSequence),
        # Settings
        ("OrganizationSetting", OrganizationSetting),
        ("StoreConfig", StoreConfig),
        # Sessions & Overrides
        ("SessionToken", SessionToken),
        ("UserPermissionOverride", UserPermissionOverride),
    ]

    total_deleted = 0
    for name, model in tables:
        count = db.session.query(model).delete()
        if count:
            click.echo(f"  DELETE {name}: {count} rows")
            total_deleted += count

    # Remove non-default users and their role assignments
    extra_roles = db.session.query(UserRole).filter(~UserRole.user_id.in_(default_user_ids)).delete()
    extra_users = db.session.query(User).filter(~User.id.in_(default_user_ids)).delete()
    if extra_users:
        click.echo(f"  DELETE Users (non-default): {extra_users}")
        total_deleted += extra_users
    if extra_roles:
        click.echo(f"  DELETE UserRoles (non-default): {extra_roles}")
        total_deleted += extra_roles

    # Remove extra orgs and stores
    if default_org_id:
        extra_stores = db.session.query(Store).filter(Store.org_id != default_org_id).delete()
        extra_orgs = db.session.query(Organization).filter(Organization.id != default_org_id).delete()
        if extra_stores:
            click.echo(f"  DELETE Stores (non-default org): {extra_stores}")
            total_deleted += extra_stores
        if extra_orgs:
            click.echo(f"  DELETE Organizations (non-default): {extra_orgs}")
            total_deleted += extra_orgs

    db.session.commit()

    if total_deleted == 0:
        click.echo("PASS Nothing to delete — database was already clean.")
    else:
        click.echo(f"\nPASS Wiped {total_deleted} total rows.")

    click.echo(f"   Preserved users: {[u.username for u in default_users]}")
    click.echo(f"   Preserved org: {default_org_id}")


@system_group.command('seed-defaults')
@click.option('--org-id', type=int, help='Organization ID (defaults to first org)')
@click.option('--store-id', type=int, help='Store ID (defaults to first store in org)')
@click.option('--days-history', type=int, default=30, show_default=True, help='How far back historical demo data should go')
@click.option('--password', default='Password123!', show_default=True, help='Password for any seeded users')
@with_appcontext
def seed_defaults(org_id, store_id, days_history, password):
    """
    Seed a realistic POS demo dataset so a fresh environment is immediately usable.

    Safe to rerun: records use deterministic codes/document numbers and are skipped
    when they already exist.
    """
    from .models import (
        Product,
        ProductIdentifier,
        Vendor,
        ReceiveDocument,
        ReceiveDocumentLine,
        InventoryTransaction,
        Register,
        RegisterSession,
        CashDrawer,
        CashDrawerEvent,
        Printer,
        Sale,
        SaleLine,
        Payment,
        PaymentTransaction,
        Return,
        ReturnLine,
        Count,
        CountLine,
        Announcement,
        Reminder,
        Task,
        UserStoreManagerAccess,
    )
    from .services.ledger_service import append_ledger_event
    from .services import register_service
    from .permissions import DEFAULT_ROLE_PERMISSIONS

    created_counts = {
        "stores": 0,
        "users": 0,
        "manager_store_access": 0,
        "vendors": 0,
        "products": 0,
        "identifiers": 0,
        "registers": 0,
        "drawers": 0,
        "printers": 0,
        "sessions": 0,
        "drawer_events": 0,
        "receives": 0,
        "receive_lines": 0,
        "inventory_txns": 0,
        "sales": 0,
        "sale_lines": 0,
        "payments": 0,
        "payment_txns": 0,
        "returns": 0,
        "return_lines": 0,
        "counts": 0,
        "count_lines": 0,
        "announcements": 0,
        "reminders": 0,
        "tasks": 0,
    }

    def ensure_user(username: str, email: str, role_name: str, primary_store_id: int) -> User:
        user = db.session.query(User).filter_by(org_id=org.id, username=username).first()
        if not user:
            user = create_user(
                username=username,
                email=email,
                password=password,
                org_id=org.id,
                store_id=primary_store_id,
            )
            created_counts["users"] += 1

        role = db.session.query(Role).filter_by(org_id=org.id, name=role_name).first()
        if role:
            user_role = db.session.query(UserRole).filter_by(user_id=user.id, role_id=role.id).first()
            if not user_role:
                db.session.add(UserRole(user_id=user.id, role_id=role.id))
                db.session.commit()
        return user

    def ensure_manager_store_access(user_id: int, managed_store_id: int, granted_by_user_id: int | None) -> None:
        existing = db.session.query(UserStoreManagerAccess).filter_by(
            user_id=user_id,
            store_id=managed_store_id,
        ).first()
        if existing:
            return
        db.session.add(
            UserStoreManagerAccess(
                user_id=user_id,
                store_id=managed_store_id,
                granted_by_user_id=granted_by_user_id,
            )
        )
        db.session.commit()
        created_counts["manager_store_access"] += 1

    def ensure_default_permissions_for_org(org_scope_id: int) -> None:
        for role_name, permission_codes in DEFAULT_ROLE_PERMISSIONS.items():
            role = db.session.query(Role).filter_by(org_id=org_scope_id, name=role_name).first()
            if not role:
                continue
            for permission_code in permission_codes:
                permission = db.session.query(Permission).filter_by(code=permission_code).first()
                if not permission:
                    continue
                existing = db.session.query(RolePermission).filter_by(
                    role_id=role.id,
                    permission_id=permission.id,
                ).first()
                if not existing:
                    db.session.add(RolePermission(role_id=role.id, permission_id=permission.id))
        db.session.commit()

    if days_history < 1:
        click.echo("FAIL --days-history must be >= 1")
        return

    if org_id:
        org = db.session.query(Organization).filter_by(id=org_id).first()
        if not org:
            click.echo(f"FAIL Organization {org_id} not found")
            return
    else:
        org = db.session.query(Organization).first()
        if not org:
            org = Organization(name="Demo Organization", code="DEMO", is_active=True)
            db.session.add(org)
            db.session.commit()
            click.echo(f"Created organization: {org.name} (ID: {org.id})")

    # Ensure baseline RBAC exists before creating users.
    ensure_org_master_ledger(org.id)
    db.session.commit()
    create_default_roles(org.id)
    permission_service.initialize_permissions()
    ensure_default_permissions_for_org(org.id)

    if store_id:
        main_store = db.session.query(Store).filter_by(id=store_id, org_id=org.id).first()
        if not main_store:
            click.echo(f"FAIL Store {store_id} not found in organization {org.id}")
            return
    else:
        main_store = db.session.query(Store).filter_by(org_id=org.id).order_by(Store.id.asc()).first()
        if not main_store:
            main_store = Store(org_id=org.id, name="Main Store", code="MAIN")
            db.session.add(main_store)
            db.session.commit()
            created_counts["stores"] += 1

    branch_store = db.session.query(Store).filter_by(org_id=org.id, code="BRANCH").first()
    if not branch_store:
        branch_store = db.session.query(Store).filter_by(org_id=org.id, name="Branch Store").first()
        if branch_store and not branch_store.code:
            conflicting_branch_code = db.session.query(Store).filter_by(org_id=org.id, code="BRANCH").first()
            if not conflicting_branch_code:
                branch_store.code = "BRANCH"
                db.session.commit()
    if not branch_store:
        branch_store = Store(org_id=org.id, name="Branch Store", code="BRANCH")
        db.session.add(branch_store)
        db.session.commit()
        created_counts["stores"] += 1

    admin_user = ensure_user("admin", "admin@apos.local", "admin", main_store.id)
    manager_user = ensure_user("manager", "manager@apos.local", "manager", main_store.id)
    cashier_user = ensure_user("cashier", "cashier@apos.local", "cashier", main_store.id)

    ensure_manager_store_access(manager_user.id, main_store.id, admin_user.id)
    if branch_store.id != main_store.id:
        ensure_manager_store_access(manager_user.id, branch_store.id, admin_user.id)

    vendors_seed = [
        ("DEMO-ALPHA", "Alpha Wholesale", "orders@alpha-wholesale.demo"),
        ("DEMO-FRESH", "Fresh Farms Supply", "procurement@freshfarms.demo"),
        ("DEMO-BEVERAGE", "Beverage Partners", "sales@beverage-partners.demo"),
    ]
    vendors = []
    for code, name, email in vendors_seed:
        vendor = db.session.query(Vendor).filter_by(org_id=org.id, code=code).first()
        if not vendor:
            vendor = Vendor(
                org_id=org.id,
                code=code,
                name=name,
                contact_email=email,
                is_active=True,
                notes="Seeded by system seed-defaults",
            )
            db.session.add(vendor)
            db.session.commit()
            created_counts["vendors"] += 1
        vendors.append(vendor)

    products_seed = [
        ("DEMO-COFFEE-12OZ", "Coffee Beans 12oz", 1299, 899, "012345670001"),
        ("DEMO-CREAMER-16OZ", "Vanilla Creamer 16oz", 499, 299, "012345670002"),
        ("DEMO-SUGAR-2LB", "Cane Sugar 2lb", 699, 449, "012345670003"),
        ("DEMO-TEA-BOX", "Black Tea Box", 899, 559, "012345670004"),
        ("DEMO-WATER-24PK", "Spring Water 24pk", 749, 520, "012345670005"),
        ("DEMO-CUP-16OZ-50", "Paper Cups 16oz (50)", 1099, 650, "012345670006"),
    ]
    products = []
    for sku, name, price_cents, cost_cents, upc in products_seed:
        product = db.session.query(Product).filter_by(store_id=main_store.id, sku=sku).first()
        if not product:
            product = Product(
                store_id=main_store.id,
                sku=sku,
                name=name,
                price_cents=price_cents,
                is_active=True,
                description="Seeded demo product",
            )
            db.session.add(product)
            db.session.commit()
            created_counts["products"] += 1
        products.append((product, cost_cents))

        identifier = db.session.query(ProductIdentifier).filter_by(
            org_id=org.id,
            type="UPC",
            value=upc,
        ).first()
        if not identifier:
            db.session.add(
                ProductIdentifier(
                    product_id=product.id,
                    org_id=org.id,
                    store_id=main_store.id,
                    type="UPC",
                    value=upc,
                    is_primary=True,
                    is_active=True,
                )
            )
            db.session.commit()
            created_counts["identifiers"] += 1

    register_configs = [
        ("1", "Front Register", "Front Counter"),
        ("2", "Express Register", "Express Lane"),
    ]
    registers = []
    for reg_number, reg_name, location in register_configs:
        register = db.session.query(Register).filter_by(store_id=main_store.id, register_number=reg_number).first()
        if not register:
            register = register_service.create_register(
                store_id=main_store.id,
                register_number=reg_number,
                name=reg_name,
                location=location,
                org_id=org.id,
                actor_user_id=admin_user.id,
            )
            created_counts["registers"] += 1
        registers.append(register)

        drawer = db.session.query(CashDrawer).filter_by(register_id=register.id).first()
        if not drawer:
            db.session.add(
                CashDrawer(
                    register_id=register.id,
                    model="APOS Standard Drawer",
                    serial_number=f"DEMO-CD-{register.id}",
                    connection_type="USB",
                    connection_address=f"USB-{register.id}",
                    is_active=True,
                )
            )
            db.session.commit()
            created_counts["drawers"] += 1

    receipt_printer = db.session.query(Printer).filter_by(
        register_id=registers[0].id,
        name="Front Receipt Printer",
    ).first()
    if not receipt_printer:
        db.session.add(
            Printer(
                register_id=registers[0].id,
                name="Front Receipt Printer",
                printer_type="RECEIPT",
                model="Epson TM-T88VI",
                connection_type="NETWORK",
                connection_address="192.168.1.50:9100",
                paper_width_mm=80,
                supports_cut=True,
                supports_cash_drawer=True,
                is_active=True,
            )
        )
        db.session.commit()
        created_counts["printers"] += 1

    now = utcnow()
    start_time = now - timedelta(days=days_history)

    closed_session = db.session.query(RegisterSession).filter_by(
        register_id=registers[0].id,
        status="CLOSED",
    ).order_by(RegisterSession.id.desc()).first()
    if not closed_session:
        closed_session = RegisterSession(
            register_id=registers[0].id,
            user_id=cashier_user.id,
            opened_by_user_id=manager_user.id,
            status="CLOSED",
            opening_cash_cents=20000,
            closing_cash_cents=24850,
            expected_cash_cents=24850,
            variance_cents=0,
            opened_at=start_time,
            closed_at=start_time + timedelta(hours=8),
            notes="Seeded historical session",
        )
        db.session.add(closed_session)
        db.session.commit()
        created_counts["sessions"] += 1

    open_session = db.session.query(RegisterSession).filter_by(
        register_id=registers[1].id,
        status="OPEN",
    ).first()
    if not open_session:
        open_session = RegisterSession(
            register_id=registers[1].id,
            user_id=cashier_user.id,
            opened_by_user_id=cashier_user.id,
            status="OPEN",
            opening_cash_cents=15000,
            expected_cash_cents=15000,
            opened_at=now - timedelta(hours=2),
            notes="Seeded active session",
        )
        db.session.add(open_session)
        db.session.commit()
        created_counts["sessions"] += 1

    existing_session_event = db.session.query(CashDrawerEvent).filter_by(
        register_session_id=closed_session.id,
        event_type="SHIFT_OPEN",
    ).first()
    if not existing_session_event:
        db.session.add(
            CashDrawerEvent(
                register_session_id=closed_session.id,
                register_id=registers[0].id,
                user_id=cashier_user.id,
                event_type="SHIFT_OPEN",
                amount_cents=closed_session.opening_cash_cents,
                reason="Seeded opening event",
                occurred_at=closed_session.opened_at,
            )
        )
        db.session.add(
            CashDrawerEvent(
                register_session_id=closed_session.id,
                register_id=registers[0].id,
                user_id=cashier_user.id,
                event_type="SHIFT_CLOSE",
                amount_cents=closed_session.closing_cash_cents,
                reason="Seeded closing event",
                occurred_at=closed_session.closed_at,
            )
        )
        db.session.commit()
        created_counts["drawer_events"] += 2

    receive_doc = db.session.query(ReceiveDocument).filter_by(
        store_id=main_store.id,
        document_number="DEMO-RCV-0001",
    ).first()
    if not receive_doc:
        receive_doc = ReceiveDocument(
            store_id=main_store.id,
            vendor_id=vendors[0].id,
            document_number="DEMO-RCV-0001",
            receive_type="PURCHASE",
            status="POSTED",
            occurred_at=start_time + timedelta(days=1),
            notes="Seeded opening inventory receipt",
            reference_number="PO-DEMO-1001",
            created_by_user_id=manager_user.id,
            approved_by_user_id=manager_user.id,
            posted_by_user_id=manager_user.id,
            approved_at=start_time + timedelta(days=1, hours=1),
            posted_at=start_time + timedelta(days=1, hours=2),
        )
        db.session.add(receive_doc)
        db.session.flush()
        created_counts["receives"] += 1

        for idx, (product, unit_cost) in enumerate(products):
            qty = 30 + (idx * 3)
            inv_txn = InventoryTransaction(
                store_id=main_store.id,
                product_id=product.id,
                type="RECEIVE",
                quantity_delta=qty,
                unit_cost_cents=unit_cost,
                note="Seeded receive document posting",
                occurred_at=receive_doc.posted_at,
                status="POSTED",
                approved_by_user_id=manager_user.id,
                approved_at=receive_doc.approved_at,
                posted_by_user_id=manager_user.id,
                posted_at=receive_doc.posted_at,
                inventory_state="SELLABLE",
            )
            db.session.add(inv_txn)
            db.session.flush()
            created_counts["inventory_txns"] += 1

            line = ReceiveDocumentLine(
                receive_document_id=receive_doc.id,
                product_id=product.id,
                quantity=qty,
                unit_cost_cents=unit_cost,
                line_cost_cents=qty * unit_cost,
                note="Seeded line",
                inventory_transaction_id=inv_txn.id,
            )
            db.session.add(line)
            created_counts["receive_lines"] += 1

        append_ledger_event(
            store_id=main_store.id,
            event_type="inventory.receive_posted",
            event_category="inventory",
            entity_type="receive_document",
            entity_id=receive_doc.id,
            actor_user_id=manager_user.id,
            occurred_at=receive_doc.posted_at,
            note="Seeded posted receive document",
        )
        db.session.commit()

    for i in range(1, 6):
        doc_num = f"DEMO-S-{i:04d}"
        sale = db.session.query(Sale).filter_by(store_id=main_store.id, document_number=doc_num).first()
        if sale:
            continue

        sale_time = now - timedelta(days=max(days_history - i, 1))
        first = products[(i - 1) % len(products)][0]
        second = products[i % len(products)][0]
        first_qty = 1 + (i % 3)
        second_qty = 1
        total_due = (first.price_cents * first_qty) + (second.price_cents * second_qty)

        sale = Sale(
            store_id=main_store.id,
            document_number=doc_num,
            status="COMPLETED",
            created_at=sale_time,
            completed_at=sale_time + timedelta(minutes=3),
            created_by_user_id=cashier_user.id,
            register_id=registers[0].id,
            register_session_id=closed_session.id,
            payment_status="PAID",
            total_due_cents=total_due,
            total_paid_cents=total_due,
            change_due_cents=0,
        )
        db.session.add(sale)
        db.session.flush()
        created_counts["sales"] += 1

        sale_lines = [
            SaleLine(
                sale_id=sale.id,
                product_id=first.id,
                quantity=first_qty,
                unit_price_cents=first.price_cents,
                line_total_cents=first.price_cents * first_qty,
            ),
            SaleLine(
                sale_id=sale.id,
                product_id=second.id,
                quantity=second_qty,
                unit_price_cents=second.price_cents,
                line_total_cents=second.price_cents * second_qty,
            ),
        ]
        for line in sale_lines:
            db.session.add(line)
            created_counts["sale_lines"] += 1

        payment = Payment(
            sale_id=sale.id,
            tender_type="CARD" if i % 2 == 0 else "CASH",
            amount_cents=total_due,
            status="COMPLETED",
            reference_number=f"SEED-PAY-{sale.id}",
            change_cents=0,
            created_by_user_id=cashier_user.id,
            register_id=registers[0].id,
            register_session_id=closed_session.id,
            created_at=sale.completed_at,
        )
        db.session.add(payment)
        db.session.flush()
        created_counts["payments"] += 1

        db.session.add(
            PaymentTransaction(
                payment_id=payment.id,
                sale_id=sale.id,
                transaction_type="PAYMENT",
                amount_cents=total_due,
                tender_type=payment.tender_type,
                user_id=cashier_user.id,
                occurred_at=sale.completed_at,
                register_id=registers[0].id,
                register_session_id=closed_session.id,
            )
        )
        created_counts["payment_txns"] += 1

        for product, qty in [(first, first_qty), (second, second_qty)]:
            db.session.add(
                InventoryTransaction(
                    store_id=main_store.id,
                    product_id=product.id,
                    type="SALE",
                    quantity_delta=-qty,
                    note=f"Seeded sale {doc_num}",
                    occurred_at=sale.completed_at,
                    sale_id=str(sale.id),
                    status="POSTED",
                    posted_by_user_id=cashier_user.id,
                    posted_at=sale.completed_at,
                    inventory_state="SELLABLE",
                )
            )
            created_counts["inventory_txns"] += 1

        append_ledger_event(
            store_id=main_store.id,
            event_type="sale.completed",
            event_category="sales",
            entity_type="sale",
            entity_id=sale.id,
            actor_user_id=cashier_user.id,
            register_id=registers[0].id,
            register_session_id=closed_session.id,
            sale_id=sale.id,
            occurred_at=sale.completed_at,
            note=f"Seeded sale {doc_num}",
        )
        append_ledger_event(
            store_id=main_store.id,
            event_type="payment.completed",
            event_category="payment",
            entity_type="payment",
            entity_id=payment.id,
            actor_user_id=cashier_user.id,
            register_id=registers[0].id,
            register_session_id=closed_session.id,
            sale_id=sale.id,
            payment_id=payment.id,
            occurred_at=sale.completed_at,
            note=f"Seeded payment for {doc_num}",
        )
        db.session.commit()

    seed_sale = db.session.query(Sale).filter_by(store_id=main_store.id, document_number="DEMO-S-0001").first()
    seed_sale_line = seed_sale.lines[0] if seed_sale and seed_sale.lines else None
    return_doc = db.session.query(Return).filter_by(
        store_id=main_store.id,
        document_number="DEMO-RET-0001",
    ).first()
    if seed_sale and seed_sale_line and not return_doc:
        return_doc = Return(
            store_id=main_store.id,
            document_number="DEMO-RET-0001",
            original_sale_id=seed_sale.id,
            status="COMPLETED",
            reason="Seeded sample customer return",
            restocking_fee_cents=0,
            refund_amount_cents=seed_sale_line.unit_price_cents,
            created_at=now - timedelta(days=2),
            approved_at=now - timedelta(days=2, minutes=-10),
            completed_at=now - timedelta(days=2, minutes=-20),
            created_by_user_id=cashier_user.id,
            approved_by_user_id=manager_user.id,
            completed_by_user_id=cashier_user.id,
            register_id=registers[0].id,
            register_session_id=closed_session.id,
        )
        db.session.add(return_doc)
        db.session.flush()
        created_counts["returns"] += 1

        inv_txn = InventoryTransaction(
            store_id=main_store.id,
            product_id=seed_sale_line.product_id,
            type="RETURN",
            quantity_delta=1,
            note="Seeded return restock",
            occurred_at=return_doc.completed_at,
            status="POSTED",
            approved_by_user_id=manager_user.id,
            approved_at=return_doc.approved_at,
            posted_by_user_id=cashier_user.id,
            posted_at=return_doc.completed_at,
            inventory_state="SELLABLE",
        )
        db.session.add(inv_txn)
        db.session.flush()
        created_counts["inventory_txns"] += 1

        db.session.add(
            ReturnLine(
                return_id=return_doc.id,
                original_sale_line_id=seed_sale_line.id,
                product_id=seed_sale_line.product_id,
                quantity=1,
                unit_price_cents=seed_sale_line.unit_price_cents,
                line_refund_cents=seed_sale_line.unit_price_cents,
                original_unit_cost_cents=None,
                original_cogs_cents=None,
                inventory_transaction_id=inv_txn.id,
            )
        )
        created_counts["return_lines"] += 1

        append_ledger_event(
            store_id=main_store.id,
            event_type="return.completed",
            event_category="returns",
            entity_type="return",
            entity_id=return_doc.id,
            actor_user_id=cashier_user.id,
            register_id=registers[0].id,
            register_session_id=closed_session.id,
            return_id=return_doc.id,
            occurred_at=return_doc.completed_at,
            note="Seeded sample return",
        )
        db.session.commit()

    count_doc = db.session.query(Count).filter_by(
        store_id=main_store.id,
        document_number="DEMO-C-0001",
    ).first()
    if not count_doc:
        count_doc = Count(
            store_id=main_store.id,
            document_number="DEMO-C-0001",
            count_type="CYCLE",
            status="POSTED",
            reason="Seeded cycle count",
            created_by_user_id=manager_user.id,
            approved_by_user_id=manager_user.id,
            posted_by_user_id=manager_user.id,
            created_at=now - timedelta(days=1, hours=5),
            approved_at=now - timedelta(days=1, hours=4, minutes=45),
            posted_at=now - timedelta(days=1, hours=4, minutes=30),
            total_variance_units=0,
            total_variance_cost_cents=0,
        )
        db.session.add(count_doc)
        db.session.flush()
        created_counts["counts"] += 1

        for idx, (product, unit_cost) in enumerate(products[:3]):
            expected = 20 + idx
            actual = expected + (1 if idx == 1 else 0)
            variance = actual - expected
            var_cost = variance * unit_cost

            inv_txn = None
            if variance != 0:
                inv_txn = InventoryTransaction(
                    store_id=main_store.id,
                    product_id=product.id,
                    type="ADJUST",
                    quantity_delta=variance,
                    unit_cost_cents=unit_cost,
                    note="Seeded count variance posting",
                    occurred_at=count_doc.posted_at,
                    status="POSTED",
                    approved_by_user_id=manager_user.id,
                    approved_at=count_doc.approved_at,
                    posted_by_user_id=manager_user.id,
                    posted_at=count_doc.posted_at,
                    inventory_state="SELLABLE",
                )
                db.session.add(inv_txn)
                db.session.flush()
                created_counts["inventory_txns"] += 1

            db.session.add(
                CountLine(
                    count_id=count_doc.id,
                    product_id=product.id,
                    expected_quantity=expected,
                    actual_quantity=actual,
                    variance_quantity=variance,
                    unit_cost_cents=unit_cost,
                    variance_cost_cents=var_cost,
                    inventory_transaction_id=inv_txn.id if inv_txn else None,
                )
            )
            created_counts["count_lines"] += 1

        append_ledger_event(
            store_id=main_store.id,
            event_type="count.posted",
            event_category="counts",
            entity_type="count",
            entity_id=count_doc.id,
            actor_user_id=manager_user.id,
            count_id=count_doc.id,
            occurred_at=count_doc.posted_at,
            note="Seeded posted cycle count",
        )
        db.session.commit()

    announcement = db.session.query(Announcement).filter_by(
        org_id=org.id,
        title="Seeded: Store Opening Brief",
    ).first()
    if not announcement:
        db.session.add(
            Announcement(
                org_id=org.id,
                store_id=main_store.id,
                title="Seeded: Store Opening Brief",
                body="Review promotions, verify drawer counts, and confirm receipt printer status.",
                priority="HIGH",
                created_by_user_id=manager_user.id,
                target_type="STORE",
                target_id=main_store.id,
                display_type="LOGIN_POPUP",
                is_active=True,
            )
        )
        db.session.commit()
        created_counts["announcements"] += 1

    reminder = db.session.query(Reminder).filter_by(
        org_id=org.id,
        title="Seeded: End of Day Count",
    ).first()
    if not reminder:
        db.session.add(
            Reminder(
                org_id=org.id,
                store_id=main_store.id,
                title="Seeded: End of Day Count",
                body="Run cycle count on high-velocity SKUs before close.",
                created_by_user_id=manager_user.id,
                target_type="STORE",
                target_id=main_store.id,
                repeat_type="DAILY",
                display_type="LOGIN_POPUP",
                is_active=True,
            )
        )
        db.session.commit()
        created_counts["reminders"] += 1

    task = db.session.query(Task).filter_by(
        org_id=org.id,
        title="Seeded: Verify register supplies",
    ).first()
    if not task:
        db.session.add(
            Task(
                org_id=org.id,
                store_id=main_store.id,
                title="Seeded: Verify register supplies",
                description="Confirm receipt paper, drawer till, and scanner readiness.",
                created_by_user_id=manager_user.id,
                assigned_to_user_id=cashier_user.id,
                assigned_to_register_id=registers[0].id,
                task_type="REGISTER",
                status="PENDING",
                due_at=now + timedelta(hours=4),
            )
        )
        db.session.commit()
        created_counts["tasks"] += 1

    click.echo("")
    click.echo("Seed completed.")
    click.echo(f"Organization: {org.name} (ID: {org.id})")
    click.echo(f"Main store: {main_store.name} (ID: {main_store.id})")
    click.echo(f"Branch store: {branch_store.name} (ID: {branch_store.id})")
    click.echo("")
    click.echo("Created this run:")
    for key in sorted(created_counts.keys()):
        click.echo(f"  {key:<20} {created_counts[key]}")
    click.echo("")
    click.echo("Suggested login users:")
    click.echo("  admin   / Password123!")
    click.echo("  manager / Password123!")
    click.echo("  cashier / Password123!")


# =============================================================================
# PERMISSION MANAGEMENT COMMANDS
# =============================================================================

@system_group.command('init-permissions')
@with_appcontext
def init_permissions():
    """
    Initialize permission system.

    Creates all permissions and assigns default permissions to roles.
    Safe to run multiple times (idempotent).
    """
    click.echo("SECURITY Initializing Permission System...")
    click.echo("")

    # 1. Create all permission definitions
    click.echo("LIST Creating permissions...")
    perm_count = permission_service.initialize_permissions()
    click.echo(f"PASS Created {perm_count} new permissions")

    total_perms = db.session.query(Permission).count()
    click.echo(f"   Total permissions in system: {total_perms}")

    # 2. Assign default permissions to roles
    click.echo("\nLINK Assigning default permissions to roles...")
    assignment_count = permission_service.assign_default_role_permissions()
    click.echo(f"PASS Created {assignment_count} new role-permission assignments")

    # 3. Show summary
    click.echo("\nSTATS Permission Summary by Role:")
    click.echo("="*60)

    for role_name in ["admin", "manager", "cashier"]:
        role = db.session.query(Role).filter_by(name=role_name).first()
        if role:
            role_perms = db.session.query(RolePermission).filter_by(role_id=role.id).all()
            click.echo(f"  {role_name.upper():<10} -> {len(role_perms)} permissions")

    click.echo("="*60)
    click.echo("\nPASS Permission system initialized successfully!")
    click.echo("   Users with these roles now have enforced permissions.")
    click.echo("")


@click.group('perms')
def perms_group():
    """Permission inspection and repair commands."""


@perms_group.command('list')
@click.option('--role', help='Filter by role name')
@click.option('--category', help='Filter by category')
@with_appcontext
def list_permissions_cli(role, category):
    """List all permissions, optionally filtered by role or category."""
    if role:
        # Show permissions for a specific role
        role_obj = db.session.query(Role).filter_by(name=role).first()
        if not role_obj:
            click.echo(f"FAIL Role '{role}' not found")
            return

        role_perms = db.session.query(RolePermission).filter_by(role_id=role_obj.id).all()

        click.echo(f"\n{'='*80}")
        click.echo(f"Permissions for role: {role.upper()}")
        click.echo(f"{'='*80}\n")

        click.echo(f"{'Code':<30} {'Name':<35} {'Category'}")
        click.echo("-"*80)

        for rp in role_perms:
            perm = db.session.query(Permission).get(rp.permission_id)
            if perm:
                click.echo(f"{perm.code:<30} {perm.name:<35} {perm.category}")

        click.echo(f"\n Total: {len(role_perms)} permissions\n")

    elif category:
        # Show permissions in a category
        perms = db.session.query(Permission).filter_by(category=category).all()

        click.echo(f"\n{'='*80}")
        click.echo(f"Permissions in category: {category}")
        click.echo(f"{'='*80}\n")

        click.echo(f"{'Code':<30} {'Name'}")
        click.echo("-"*80)

        for perm in perms:
            click.echo(f"{perm.code:<30} {perm.name}")

        click.echo(f"\n Total: {len(perms)} permissions\n")

    else:
        # Show all permissions grouped by category
        perms = db.session.query(Permission).order_by(Permission.category, Permission.code).all()

        click.echo(f"\n{'='*80}")
        click.echo(f"All Permissions")
        click.echo(f"{'='*80}\n")

        current_category = None
        for perm in perms:
            if perm.category != current_category:
                if current_category:
                    click.echo("")
                click.echo(f"CATEGORY {perm.category}")
                click.echo("-"*80)
                current_category = perm.category

            click.echo(f"  {perm.code:<28} {perm.name}")

        click.echo(f"\n Total: {len(perms)} permissions\n")


@perms_group.command('grant')
@click.argument('role_name')
@click.argument('permission_code')
@with_appcontext
def grant_permission_cli(role_name, permission_code):
    """Grant a permission to a role."""
    try:
        permission_service.grant_permission_to_role(role_name, permission_code)
        click.echo(f"PASS Granted '{permission_code}' to role '{role_name}'")
    except ValueError as e:
        click.echo(f"FAIL Error: {str(e)}")


@perms_group.command('revoke')
@click.argument('role_name')
@click.argument('permission_code')
@with_appcontext
def revoke_permission_cli(role_name, permission_code):
    """Revoke a permission from a role."""
    try:
        revoked = permission_service.revoke_permission_from_role(role_name, permission_code)
        if revoked:
            click.echo(f"PASS Revoked '{permission_code}' from role '{role_name}'")
        else:
            click.echo(f"WARN  Permission '{permission_code}' was not granted to '{role_name}'")
    except ValueError as e:
        click.echo(f"FAIL Error: {str(e)}")


@perms_group.command('check')
@click.argument('username')
@click.argument('permission_code')
@with_appcontext
def check_permission_cli(username, permission_code):
    """Check if a user has a specific permission."""
    user = db.session.query(User).filter_by(username=username).first()

    if not user:
        click.echo(f"FAIL User '{username}' not found")
        return

    has_permission = permission_service.user_has_permission(user.id, permission_code)

    if has_permission:
        click.echo(f"PASS User '{username}' HAS permission '{permission_code}'")
    else:
        click.echo(f"FAIL User '{username}' DOES NOT HAVE permission '{permission_code}'")

    # Show user's roles and all permissions
    roles = permission_service.get_user_role_names(user.id)
    all_perms = permission_service.get_user_permissions(user.id)

    click.echo(f"\nUser roles: {', '.join(roles)}")
    click.echo(f"Total permissions: {len(all_perms)}")


@perms_group.command('enforce-developer-access')
@click.option('--dry-run', is_flag=True, help='Audit only; do not write changes')
@click.option('--fix', is_flag=True, help='Apply remediation changes')
@with_appcontext
def enforce_developer_access_cli(dry_run, fix):
    """
    Enforce DEVELOPER_ACCESS policy.

    Policy:
    - DEVELOPER_ACCESS must only be assigned to the 'developer' role.
    - Per-user overrides for DEVELOPER_ACCESS are disabled (protected permission).
    """
    if dry_run and fix:
        click.echo("FAIL Use only one mode: --dry-run or --fix")
        return

    apply_changes = fix and not dry_run
    mode_label = "FIX" if apply_changes else "DRY-RUN"
    click.echo(f"\n{mode_label} Enforcing DEVELOPER_ACCESS policy...\n")

    developer_perm = db.session.query(Permission).filter_by(code='DEVELOPER_ACCESS').first()
    if not developer_perm:
        click.echo("FAIL Permission 'DEVELOPER_ACCESS' not found. Run: python -m flask system init-permissions")
        return

    # Find all role assignments for DEVELOPER_ACCESS
    dev_role_perms = db.session.query(RolePermission).filter_by(permission_id=developer_perm.id).all()
    non_developer_role_perms = []
    for rp in dev_role_perms:
        role = db.session.query(Role).get(rp.role_id)
        if role and role.name != 'developer':
            non_developer_role_perms.append((rp, role))

    # Find all active per-user overrides for DEVELOPER_ACCESS
    dev_overrides = db.session.query(UserPermissionOverride).filter_by(
        permission_code='DEVELOPER_ACCESS',
        is_active=True,
    ).all()

    click.echo(f"Found {len(dev_role_perms)} DEVELOPER_ACCESS role assignments")
    click.echo(f"Found {len(non_developer_role_perms)} non-developer role violations")
    click.echo(f"Found {len(dev_overrides)} active DEVELOPER_ACCESS overrides")

    if non_developer_role_perms:
        click.echo("\nNon-developer roles with DEVELOPER_ACCESS:")
        for _, role in non_developer_role_perms:
            click.echo(f"  - role='{role.name}' (role_id={role.id}, org_id={role.org_id})")

    if dev_overrides:
        click.echo("\nActive DEVELOPER_ACCESS overrides:")
        for o in dev_overrides:
            user = db.session.query(User).get(o.user_id)
            username = user.username if user else f"user#{o.user_id}"
            click.echo(
                f"  - override_id={o.id} user={username} "
                f"type={o.override_type} is_developer={bool(user and user.is_developer)}"
            )

    if not apply_changes:
        click.echo("\nNo changes applied (dry run).")
        return

    # Remediate role violations
    removed_role_links = 0
    for rp, _ in non_developer_role_perms:
        db.session.delete(rp)
        removed_role_links += 1

    # Remediate overrides (disable; permission is protected anyway)
    disabled_overrides = 0
    for o in dev_overrides:
        o.is_active = False
        o.revocation_reason = "Policy enforcement: DEVELOPER_ACCESS is developer-specific"
        disabled_overrides += 1

    db.session.commit()

    click.echo("\nPASS Policy enforcement complete")
    click.echo(f"  Removed role-permission links: {removed_role_links}")
    click.echo(f"  Disabled overrides: {disabled_overrides}")


# =============================================================================
# REGISTER MANAGEMENT COMMANDS
# =============================================================================

@click.group('registers')
def registers_group():
    """Register inspection and bootstrap commands."""


@registers_group.command('create')
@click.option('--store-id', type=int, required=True, help='Store ID')
@click.option('--number', help='Register number (optional, auto-assigned if omitted)')
@click.option('--name', required=True, help='Register name')
@click.option('--location', help='Location in store')
@with_appcontext
def create_register_cli(store_id, number, name, location):
    """
    Create a new POS register.

    Example:
        flask registers create --store-id 1 --number REG-01 --name "Front Counter 1" --location "Main Floor"
    """
    from .services import register_service
    from .models import Register

    try:
        register = register_service.create_register(
            store_id=store_id,
            register_number=number,
            name=name,
            location=location,
        )

        click.echo(f"PASS Created register: {register.register_number} - {register.name}")
        click.echo(f"   Store ID: {register.store_id}")
        click.echo(f"   Location: {register.location or 'Not specified'}")
        click.echo(f"   Register ID: {register.id}")

    except ValueError as e:
        click.echo(f"FAIL Error: {str(e)}")
    except Exception as e:
        click.echo(f"FAIL Failed to create register: {str(e)}")


@registers_group.command('list')
@click.option('--store-id', type=int, help='Filter by store ID')
@click.option('--all', 'show_all', is_flag=True, help='Show inactive registers too')
@with_appcontext
def list_registers_cli(store_id, show_all):
    """
    List all registers.

    Example:
        flask registers list
        flask registers list --store-id 1
        flask registers list --all
    """
    from .models import Register, RegisterSession

    query = db.session.query(Register)

    if store_id:
        query = query.filter_by(store_id=store_id)

    if not show_all:
        query = query.filter_by(is_active=True)

    registers = query.order_by(Register.register_number).all()

    if not registers:
        click.echo("No registers found.")
        return

    click.echo("\n" + "="*100)
    click.echo(f"{'ID':<5} {'Number':<12} {'Name':<25} {'Location':<20} {'Active':<8} {'Status'}")
    click.echo("="*100)

    for register in registers:
        # Check for open session
        open_session = db.session.query(RegisterSession).filter_by(
            register_id=register.id,
            status="OPEN"
        ).first()

        status = "OPEN" if open_session else "CLOSED"
        active_str = "Yes" if register.is_active else "No"
        location = register.location or "-"

        click.echo(f"{register.id:<5} {register.register_number:<12} {register.name:<25} {location:<20} {active_str:<8} {status}")

    click.echo("="*100 + "\n")


@registers_group.command('sessions')
@click.option('--register-id', type=int, help='Filter by register ID')
@click.option('--status', type=click.Choice(['OPEN', 'CLOSED']), help='Filter by status')
@click.option('--limit', type=int, default=20, help='Max sessions to show')
@with_appcontext
def list_sessions_cli(register_id, status, limit):
    """
    List register sessions.

    Example:
        flask registers sessions
        flask registers sessions --register-id 1
        flask registers sessions --status OPEN
    """
    from .models import RegisterSession, Register, User

    query = db.session.query(RegisterSession)

    if register_id:
        query = query.filter_by(register_id=register_id)

    if status:
        query = query.filter_by(status=status)

    sessions = query.order_by(RegisterSession.opened_at.desc()).limit(limit).all()

    if not sessions:
        click.echo("No sessions found.")
        return

    click.echo("\n" + "="*120)
    click.echo(f"{'ID':<5} {'Register':<12} {'User':<15} {'Status':<8} {'Opened':<20} {'Variance':<12} {'Notes'}")
    click.echo("="*120)

    for session in sessions:
        register = db.session.query(Register).get(session.register_id)
        user = db.session.query(User).get(session.user_id)

        register_num = register.register_number if register else "Unknown"
        username = user.username if user else "Unknown"

        variance_str = "-"
        if session.variance_cents is not None:
            variance = session.variance_cents / 100
            variance_str = f"${variance:+.2f}"

        notes = session.notes[:30] if session.notes else "-"

        click.echo(f"{session.id:<5} {register_num:<12} {username:<15} {session.status:<8} "
                  f"{str(session.opened_at)[:19]:<20} {variance_str:<12} {notes}")

    click.echo("="*120 + "\n")


@click.group('maintenance')
def maintenance_group():
    """Maintenance commands."""


@maintenance_group.command('cleanup-security-events')
@click.option('--retention-days', type=int, default=90, show_default=True)
@with_appcontext
def cleanup_security_events_cli(retention_days):
    """
    Cleanup old security events.

    Default retention: 90 days.
    """
    deleted = maintenance_service.cleanup_security_events(retention_days=retention_days)
    click.echo(f"Deleted {deleted} security events older than {retention_days} days.")


def register_commands(app):
    """Register all CLI commands with Flask app."""
    app.cli.add_command(system_group)
    app.cli.add_command(orgs_group)  # Multi-tenant organization management
    app.cli.add_command(users_group)
    app.cli.add_command(perms_group)
    app.cli.add_command(registers_group)
    app.cli.add_command(maintenance_group)
