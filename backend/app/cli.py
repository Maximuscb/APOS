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
from flask.cli import with_appcontext

from .extensions import db
from .models import Store, User, Role, UserRole, Permission, RolePermission, Organization
from .services.auth_service import create_user, create_default_roles, assign_role, hash_password, PasswordValidationError
from .services import permission_service
from .services import maintenance_service


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


# =============================================================================
# REGISTER MANAGEMENT COMMANDS
# =============================================================================

@click.group('registers')
def registers_group():
    """Register inspection and bootstrap commands."""


@registers_group.command('create')
@click.option('--store-id', type=int, required=True, help='Store ID')
@click.option('--number', required=True, help='Register number (e.g., REG-01)')
@click.option('--name', required=True, help='Register name')
@click.option('--location', help='Location in store')
@click.option('--device-id', help='Device/hardware ID')
@with_appcontext
def create_register_cli(store_id, number, name, location, device_id):
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
            device_id=device_id
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
