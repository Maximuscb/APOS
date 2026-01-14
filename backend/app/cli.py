# backend/app/cli.py
"""
CLI commands for APOS initialization and maintenance.

Usage:
    flask init-system     - Initialize everything (roles + users + store)
    flask init-roles      - Create default roles only
    flask create-user     - Interactive user creation
"""

import click
from flask.cli import with_appcontext

from .extensions import db
from .models import Store, User, Role, UserRole
from .services.auth_service import create_user, create_default_roles, assign_role


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

    # 3. Create default users
    click.echo("\n👥 Creating default users...")

    default_users = [
        ("admin", "admin@apos.local", "admin", "password123"),
        ("manager", "manager@apos.local", "manager", "password123"),
        ("cashier", "cashier@apos.local", "cashier", "password123"),
    ]

    for username, email, role_name, password in default_users:
        try:
            # Check if user exists
            existing = db.session.query(User).filter_by(username=username).first()
            if existing:
                click.echo(f"⚠️  User '{username}' already exists, skipping...")
                continue

            # Create user
            user = create_user(username, email, password, store_id=store.id)

            # Assign role
            assign_role(user.id, role_name)

            click.echo(f"✅ Created user: {username} ({email}) with role '{role_name}'")

        except Exception as e:
            click.echo(f"❌ Failed to create user '{username}': {str(e)}")

    click.echo("\n" + "="*60)
    click.echo("✨ APOS System Initialized Successfully!")
    click.echo("="*60)
    click.echo("\n📝 Default Credentials (CHANGE IN PRODUCTION!):")
    click.echo("   admin    → admin@apos.local    / password123")
    click.echo("   manager  → manager@apos.local  / password123")
    click.echo("   cashier  → cashier@apos.local  / password123")
    click.echo("\n🔒 SECURITY WARNING: Change all passwords immediately!")
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
    """Create a new user interactively."""
    try:
        # Get default store
        store = db.session.query(Store).first()
        if not store:
            click.echo("❌ No store found. Run 'flask init-system' first.")
            return

        # Create user
        user = create_user(username, email, password, store_id=store.id)

        # Assign role
        assign_role(user.id, role)

        click.echo(f"✅ Created user: {username} ({email}) with role '{role}'")

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


def register_commands(app):
    """Register all CLI commands with Flask app."""
    app.cli.add_command(init_system)
    app.cli.add_command(init_roles)
    app.cli.add_command(create_user_cli)
    app.cli.add_command(list_users)
    app.cli.add_command(reset_db)
