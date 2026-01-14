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
    click.echo("   admin    → admin@apos.local    / Password123!")
    click.echo("   manager  → manager@apos.local  / Password123!")
    click.echo("   cashier  → cashier@apos.local  / Password123!")
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
