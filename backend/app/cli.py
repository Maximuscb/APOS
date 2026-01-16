# backend/app/cli.py
"""
CLI commands for APOS initialization and maintenance.

Phase 6: Updated for bcrypt password hashing and validation.

Usage:
    flask init-system     - Initialize everything (roles + users + store)
    flask init-roles      - Create default roles only
    flask create-user     - Interactive user creation
"""

import click
from flask.cli import with_appcontext

from .extensions import db
from .models import Store, User, Role, UserRole, Permission, RolePermission
from .services.auth_service import create_user, create_default_roles, assign_role, PasswordValidationError
from .services import permission_service
from .permissions import PERMISSION_DEFINITIONS, DEFAULT_ROLE_PERMISSIONS


@click.command('init-system')
@with_appcontext
def init_system():
    """
    Initialize complete APOS system: roles, default users, and default store.

    Creates:
    - Default store (if none exists)
    - Roles: admin, manager, cashier
    - Users: admin/admin@apos.local, manager/manager@apos.local, cashier/cashier@apos.local
    - All passwords default to: "password123"

    SECURITY: Change passwords immediately in production!
    """
    click.echo("🚀 Initializing APOS system...")

    # 1. Ensure default store exists
    store = db.session.query(Store).first()
    if not store:
        store = Store(name="Main Store")
        db.session.add(store)
        db.session.commit()
        click.echo(f"✅ Created default store: {store.name} (ID: {store.id})")
    else:
        click.echo(f"✅ Using existing store: {store.name} (ID: {store.id})")

    # 2. Create roles
    click.echo("\n📋 Creating roles...")
    create_default_roles()
    roles = db.session.query(Role).all()
    click.echo(f"✅ Roles created: {', '.join(r.name for r in roles)}")

    # 2.5. Initialize permissions (Phase 7)
    click.echo("\n🔐 Initializing permissions...")
    perm_count = permission_service.initialize_permissions()
    assignment_count = permission_service.assign_default_role_permissions()
    click.echo(f"✅ Created {perm_count} permissions, {assignment_count} role assignments")

    # 3. Create default users
    click.echo("\n👥 Creating default users...")

    # Default password meets Phase 6 requirements:
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
            # Check if user exists
            existing = db.session.query(User).filter_by(username=username).first()
            if existing:
                click.echo(f"⚠️  User '{username}' already exists, skipping...")
                continue

            # Create user (password will be hashed with bcrypt and validated)
            user = create_user(username, email, password, store_id=store.id)

            # Assign role
            assign_role(user.id, role_name)

            click.echo(f"✅ Created user: {username} ({email}) with role '{role_name}'")

        except PasswordValidationError as e:
            click.echo(f"❌ Password validation failed for '{username}': {str(e)}")
        except Exception as e:
            click.echo(f"❌ Failed to create user '{username}': {str(e)}")

    click.echo("\n" + "="*60)
    click.echo("✨ APOS System Initialized Successfully!")
    click.echo("="*60)
    click.echo("\n📝 Default Credentials (CHANGE IN PRODUCTION!):")
    click.echo("   admin     → admin@apos.local     / Password123!")
    click.echo("   developer → developer@apos.local / Password123!")
    click.echo("   manager   → manager@apos.local   / Password123!")
    click.echo("   cashier   → cashier@apos.local   / Password123!")
    click.echo("\n🔒 SECURITY WARNING:")
    click.echo("   - Passwords are now hashed with bcrypt (secure)")
    click.echo("   - Change all passwords immediately in production!")
    click.echo("   - Password requirements: 8+ chars, uppercase, lowercase, digit, special char")
    click.echo("")


@click.command('init-roles')
@with_appcontext
def init_roles():
    """Create default roles (admin, manager, cashier)."""
    click.echo("📋 Creating default roles...")
    create_default_roles()
    roles = db.session.query(Role).all()
    click.echo(f"✅ Created roles: {', '.join(r.name for r in roles)}")


@click.command('create-user')
@click.option('--username', prompt=True, help='Username')
@click.option('--email', prompt=True, help='Email address')
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='Password')
@click.option('--role', type=click.Choice(['admin', 'manager', 'cashier']), prompt=True, help='Role')
@with_appcontext
def create_user_cli(username, email, password, role):
    """
    Create a new user interactively.

    Phase 6: Password must meet strength requirements:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character
    """
    try:
        # Get default store
        store = db.session.query(Store).first()
        if not store:
            click.echo("❌ No store found. Run 'flask init-system' first.")
            return

        # Create user (password will be hashed with bcrypt and validated)
        user = create_user(username, email, password, store_id=store.id)

        # Assign role
        assign_role(user.id, role)

        click.echo(f"✅ Created user: {username} ({email}) with role '{role}'")
        click.echo("🔒 Password securely hashed with bcrypt")

    except PasswordValidationError as e:
        click.echo(f"❌ Password validation failed: {str(e)}")
        click.echo("Requirements: 8+ chars, uppercase, lowercase, digit, special char")
    except Exception as e:
        click.echo(f"❌ Failed to create user: {str(e)}")


@click.command('list-users')
@with_appcontext
def list_users():
    """List all users with their roles."""
    users = db.session.query(User).all()

    if not users:
        click.echo("No users found.")
        return

    click.echo("\n" + "="*80)
    click.echo(f"{'ID':<5} {'Username':<20} {'Email':<30} {'Active':<8} {'Roles'}")
    click.echo("="*80)

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

        click.echo(f"{user.id:<5} {user.username:<20} {user.email:<30} {active_str:<8} {roles_str}")

    click.echo("="*80 + "\n")


@click.command('reset-db')
@click.option('--yes', is_flag=True, help='Skip confirmation')
@with_appcontext
def reset_db(yes):
    """
    DANGER: Drop all tables and recreate schema.

    This will DELETE ALL DATA!
    """
    if not yes:
        click.confirm('⚠️  This will DELETE ALL DATA. Are you sure?', abort=True)

    click.echo("🗑️  Dropping all tables...")
    db.drop_all()

    click.echo("🏗️  Creating all tables...")
    db.create_all()

    click.echo("✅ Database reset complete. Run 'flask init-system' to initialize.")


# =============================================================================
# PHASE 7: PERMISSION MANAGEMENT COMMANDS
# =============================================================================

@click.command('init-permissions')
@with_appcontext
def init_permissions():
    """
    Phase 7: Initialize permission system.

    Creates all permissions and assigns default permissions to roles.
    Safe to run multiple times (idempotent).
    """
    click.echo("🔐 Phase 7: Initializing Permission System...")
    click.echo("")

    # 1. Create all permission definitions
    click.echo("📋 Creating permissions...")
    perm_count = permission_service.initialize_permissions()
    click.echo(f"✅ Created {perm_count} new permissions")

    total_perms = db.session.query(Permission).count()
    click.echo(f"   Total permissions in system: {total_perms}")

    # 2. Assign default permissions to roles
    click.echo("\n🔗 Assigning default permissions to roles...")
    assignment_count = permission_service.assign_default_role_permissions()
    click.echo(f"✅ Created {assignment_count} new role-permission assignments")

    # 3. Show summary
    click.echo("\n📊 Permission Summary by Role:")
    click.echo("="*60)

    for role_name in ["admin", "manager", "cashier"]:
        role = db.session.query(Role).filter_by(name=role_name).first()
        if role:
            role_perms = db.session.query(RolePermission).filter_by(role_id=role.id).all()
            click.echo(f"  {role_name.upper():<10} → {len(role_perms)} permissions")

    click.echo("="*60)
    click.echo("\n✅ Permission system initialized successfully!")
    click.echo("   Users with these roles now have enforced permissions.")
    click.echo("")


@click.command('list-permissions')
@click.option('--role', help='Filter by role name')
@click.option('--category', help='Filter by category')
@with_appcontext
def list_permissions_cli(role, category):
    """List all permissions, optionally filtered by role or category."""
    if role:
        # Show permissions for a specific role
        role_obj = db.session.query(Role).filter_by(name=role).first()
        if not role_obj:
            click.echo(f"❌ Role '{role}' not found")
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
                click.echo(f"📁 {perm.category}")
                click.echo("-"*80)
                current_category = perm.category

            click.echo(f"  {perm.code:<28} {perm.name}")

        click.echo(f"\n Total: {len(perms)} permissions\n")


@click.command('grant-permission')
@click.argument('role_name')
@click.argument('permission_code')
@with_appcontext
def grant_permission_cli(role_name, permission_code):
    """Grant a permission to a role."""
    try:
        permission_service.grant_permission_to_role(role_name, permission_code)
        click.echo(f"✅ Granted '{permission_code}' to role '{role_name}'")
    except ValueError as e:
        click.echo(f"❌ Error: {str(e)}")


@click.command('revoke-permission')
@click.argument('role_name')
@click.argument('permission_code')
@with_appcontext
def revoke_permission_cli(role_name, permission_code):
    """Revoke a permission from a role."""
    try:
        revoked = permission_service.revoke_permission_from_role(role_name, permission_code)
        if revoked:
            click.echo(f"✅ Revoked '{permission_code}' from role '{role_name}'")
        else:
            click.echo(f"⚠️  Permission '{permission_code}' was not granted to '{role_name}'")
    except ValueError as e:
        click.echo(f"❌ Error: {str(e)}")


@click.command('check-permission')
@click.argument('username')
@click.argument('permission_code')
@with_appcontext
def check_permission_cli(username, permission_code):
    """Check if a user has a specific permission."""
    user = db.session.query(User).filter_by(username=username).first()

    if not user:
        click.echo(f"❌ User '{username}' not found")
        return

    has_permission = permission_service.user_has_permission(user.id, permission_code)

    if has_permission:
        click.echo(f"✅ User '{username}' HAS permission '{permission_code}'")
    else:
        click.echo(f"❌ User '{username}' DOES NOT HAVE permission '{permission_code}'")

    # Show user's roles and all permissions
    roles = permission_service.get_user_role_names(user.id)
    all_perms = permission_service.get_user_permissions(user.id)

    click.echo(f"\nUser roles: {', '.join(roles)}")
    click.echo(f"Total permissions: {len(all_perms)}")


# =============================================================================
# PHASE 8: REGISTER MANAGEMENT COMMANDS
# =============================================================================

@click.command('create-register')
@click.option('--store-id', type=int, required=True, help='Store ID')
@click.option('--number', required=True, help='Register number (e.g., REG-01)')
@click.option('--name', required=True, help='Register name')
@click.option('--location', help='Location in store')
@click.option('--device-id', help='Device/hardware ID')
@with_appcontext
def create_register_cli(store_id, number, name, location, device_id):
    """
    Phase 8: Create a new POS register.

    Example:
        flask create-register --store-id 1 --number REG-01 --name "Front Counter 1" --location "Main Floor"
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

        click.echo(f"✅ Created register: {register.register_number} - {register.name}")
        click.echo(f"   Store ID: {register.store_id}")
        click.echo(f"   Location: {register.location or 'Not specified'}")
        click.echo(f"   Register ID: {register.id}")

    except ValueError as e:
        click.echo(f"❌ Error: {str(e)}")
    except Exception as e:
        click.echo(f"❌ Failed to create register: {str(e)}")


@click.command('list-registers')
@click.option('--store-id', type=int, help='Filter by store ID')
@click.option('--all', 'show_all', is_flag=True, help='Show inactive registers too')
@with_appcontext
def list_registers_cli(store_id, show_all):
    """
    Phase 8: List all registers.

    Example:
        flask list-registers
        flask list-registers --store-id 1
        flask list-registers --all
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


@click.command('open-shift')
@click.option('--register-id', type=int, required=True, help='Register ID')
@click.option('--username', required=True, help='Username opening the shift')
@click.option('--opening-cash', type=float, default=0.0, help='Opening cash amount (e.g., 100.00)')
@with_appcontext
def open_shift_cli(register_id, username, opening_cash):
    """
    Phase 8: Open a new shift on a register.

    Example:
        flask open-shift --register-id 1 --username cashier --opening-cash 100.00
    """
    from .services import register_service
    from .services.register_service import ShiftError

    try:
        # Find user
        user = db.session.query(User).filter_by(username=username).first()
        if not user:
            click.echo(f"❌ User '{username}' not found")
            return

        # Convert dollars to cents
        opening_cash_cents = int(opening_cash * 100)

        session = register_service.open_shift(
            register_id=register_id,
            user_id=user.id,
            opening_cash_cents=opening_cash_cents
        )

        click.echo(f"✅ Shift opened successfully!")
        click.echo(f"   Session ID: {session.id}")
        click.echo(f"   Register ID: {session.register_id}")
        click.echo(f"   User: {username}")
        click.echo(f"   Opening Cash: ${opening_cash:.2f}")
        click.echo(f"   Opened At: {session.opened_at}")

    except ShiftError as e:
        click.echo(f"❌ Shift Error: {str(e)}")
    except ValueError as e:
        click.echo(f"❌ Error: {str(e)}")
    except Exception as e:
        click.echo(f"❌ Failed to open shift: {str(e)}")


@click.command('close-shift')
@click.option('--session-id', type=int, required=True, help='Session ID to close')
@click.option('--closing-cash', type=float, required=True, help='Closing cash amount (e.g., 125.50)')
@click.option('--notes', help='Optional notes about the shift')
@with_appcontext
def close_shift_cli(session_id, closing_cash, notes):
    """
    Phase 8: Close a shift and calculate variance.

    Example:
        flask close-shift --session-id 1 --closing-cash 125.50 --notes "Good shift"
    """
    from .services import register_service
    from .services.register_service import ShiftError

    try:
        # Convert dollars to cents
        closing_cash_cents = int(closing_cash * 100)

        session = register_service.close_shift(
            session_id=session_id,
            closing_cash_cents=closing_cash_cents,
            notes=notes
        )

        opening = session.opening_cash_cents / 100
        expected = session.expected_cash_cents / 100
        closing = session.closing_cash_cents / 100
        variance = session.variance_cents / 100

        click.echo(f"✅ Shift closed successfully!")
        click.echo(f"   Session ID: {session.id}")
        click.echo(f"   Opening Cash: ${opening:.2f}")
        click.echo(f"   Expected Cash: ${expected:.2f}")
        click.echo(f"   Closing Cash: ${closing:.2f}")
        click.echo(f"   Variance: ${variance:+.2f}")

        if abs(variance) > 0:
            if variance > 0:
                click.echo(f"   ⚠️  OVER by ${abs(variance):.2f}")
            else:
                click.echo(f"   ⚠️  SHORT by ${abs(variance):.2f}")
        else:
            click.echo(f"   ✅ Cash balanced perfectly!")

        if session.notes:
            click.echo(f"   Notes: {session.notes}")

    except ShiftError as e:
        click.echo(f"❌ Shift Error: {str(e)}")
    except ValueError as e:
        click.echo(f"❌ Error: {str(e)}")
    except Exception as e:
        click.echo(f"❌ Failed to close shift: {str(e)}")


@click.command('list-sessions')
@click.option('--register-id', type=int, help='Filter by register ID')
@click.option('--status', type=click.Choice(['OPEN', 'CLOSED']), help='Filter by status')
@click.option('--limit', type=int, default=20, help='Max sessions to show')
@with_appcontext
def list_sessions_cli(register_id, status, limit):
    """
    Phase 8: List register sessions.

    Example:
        flask list-sessions
        flask list-sessions --register-id 1
        flask list-sessions --status OPEN
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


def register_commands(app):
    """Register all CLI commands with Flask app."""
    app.cli.add_command(init_system)
    app.cli.add_command(init_roles)
    app.cli.add_command(create_user_cli)
    app.cli.add_command(list_users)
    app.cli.add_command(reset_db)

    # Phase 7: Permission management
    app.cli.add_command(init_permissions)
    app.cli.add_command(list_permissions_cli)
    app.cli.add_command(grant_permission_cli)
    app.cli.add_command(revoke_permission_cli)
    app.cli.add_command(check_permission_cli)

    # Phase 8: Register management
    app.cli.add_command(create_register_cli)
    app.cli.add_command(list_registers_cli)
    app.cli.add_command(open_shift_cli)
    app.cli.add_command(close_shift_cli)
    app.cli.add_command(list_sessions_cli)
