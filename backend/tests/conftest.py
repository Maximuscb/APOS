"""
Pytest fixtures for APOS 1.3 authorization tests.

Provides:
- Flask app with in-memory SQLite
- Seeded permissions and default roles
- Admin, manager, and cashier users with tokens
"""

import os
import pytest

# Set DATABASE_URL before importing app so create_app() picks it up
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from app import create_app
from app.extensions import db as _db
from app.models import Organization, Store, Role
from app.services.auth_service import create_user, create_default_roles, assign_role
from app.services.session_service import create_session
from app.services.permission_service import initialize_permissions, assign_default_role_permissions


@pytest.fixture(scope="session")
def app():
    """Create Flask app with in-memory SQLite for testing."""
    app = create_app()
    app.config["TESTING"] = True

    with app.app_context():
        # Deduplicate indexes: some models define both index=True on a column
        # AND an explicit db.Index() with the same name in __table_args__.
        # SQLite rejects duplicate index names, so remove them before create_all.
        for table in _db.metadata.tables.values():
            seen = set()
            dupes = []
            for idx in table.indexes:
                if idx.name in seen:
                    dupes.append(idx)
                else:
                    seen.add(idx.name)
            for idx in dupes:
                table.indexes.discard(idx)

        _db.create_all()
        yield app
        _db.drop_all()


@pytest.fixture(autouse=True)
def _clean_db(app):
    """Roll back after each test to ensure isolation."""
    with app.app_context():
        yield
        _db.session.rollback()


@pytest.fixture(scope="session")
def seed(app):
    """Seed org, store, permissions, and roles once for all tests."""
    with app.app_context():
        org = Organization(name="Test Organization", code="TEST", is_active=True)
        _db.session.add(org)
        _db.session.flush()

        store = Store(org_id=org.id, name="Test Store", code="STORE1")
        _db.session.add(store)
        _db.session.flush()

        # Initialize global permission records
        initialize_permissions()

        # Create default roles for this org
        create_default_roles(org.id)
        _db.session.flush()

        # Assign default permissions to roles
        assign_default_role_permissions()
        _db.session.commit()

        return {"org_id": org.id, "store_id": store.id}


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture(scope="session")
def admin_headers(app, seed):
    """Create admin user and return auth headers."""
    with app.app_context():
        user = create_user(
            username="test_admin",
            email="admin@test.local",
            password="TestPassword123!",
            org_id=seed["org_id"],
            store_id=seed["store_id"],
        )
        assign_role(user.id, "admin")
        _, token = create_session(user.id)
        _db.session.commit()
        return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def cashier_headers(app, seed):
    """Create cashier user and return auth headers."""
    with app.app_context():
        user = create_user(
            username="test_cashier",
            email="cashier@test.local",
            password="TestPassword123!",
            org_id=seed["org_id"],
            store_id=seed["store_id"],
        )
        assign_role(user.id, "cashier")
        _, token = create_session(user.id)
        _db.session.commit()
        return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def manager_headers(app, seed):
    """Create manager user and return auth headers."""
    with app.app_context():
        user = create_user(
            username="test_manager",
            email="manager@test.local",
            password="TestPassword123!",
            org_id=seed["org_id"],
            store_id=seed["store_id"],
        )
        assign_role(user.id, "manager")
        _, token = create_session(user.id)
        _db.session.commit()
        return {"Authorization": f"Bearer {token}"}
