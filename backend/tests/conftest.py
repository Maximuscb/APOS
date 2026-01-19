"""
Pytest fixtures for APOS backend tests.

Provides test database setup, tenant isolation fixtures, and test client.
"""

import pytest
from flask import Flask
from app import create_app
from app.extensions import db
from app.models import Organization, Store, User, Role, UserRole, Product
from app.services.auth_service import hash_password, create_default_roles, assign_role
from app.services import permission_service


@pytest.fixture(scope='session')
def app():
    """Create application for testing."""
    app = create_app()
    app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
    })

    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture(scope='function')
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture(scope='function')
def db_session(app):
    """Create fresh database for each test."""
    with app.app_context():
        # Clear all data but keep schema
        meta = db.metadata
        for table in reversed(meta.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()

        yield db.session

        # Cleanup after test
        db.session.rollback()


@pytest.fixture(scope='function')
def setup_roles(db_session):
    """Setup default roles and permissions."""
    create_default_roles()
    permission_service.initialize_permissions()
    permission_service.assign_default_role_permissions()
    db_session.commit()


@pytest.fixture(scope='function')
def org_a(db_session):
    """Create Organization A (first tenant)."""
    org = Organization(name="Org A - Acme Corp", code="ACME", is_active=True)
    db_session.add(org)
    db_session.commit()
    return org


@pytest.fixture(scope='function')
def org_b(db_session):
    """Create Organization B (second tenant)."""
    org = Organization(name="Org B - Beta Inc", code="BETA", is_active=True)
    db_session.add(org)
    db_session.commit()
    return org


@pytest.fixture(scope='function')
def store_a(db_session, org_a):
    """Create Store A in Organization A."""
    store = Store(org_id=org_a.id, name="Store A1", code="A1")
    db_session.add(store)
    db_session.commit()
    return store


@pytest.fixture(scope='function')
def store_b(db_session, org_b):
    """Create Store B in Organization B."""
    store = Store(org_id=org_b.id, name="Store B1", code="B1")
    db_session.add(store)
    db_session.commit()
    return store


@pytest.fixture(scope='function')
def user_a(db_session, org_a, store_a, setup_roles):
    """Create User A in Organization A with admin role."""
    user = User(
        org_id=org_a.id,
        store_id=store_a.id,
        username="user_a",
        email="user_a@acme.com",
        password_hash=hash_password("Password123!")
    )
    db_session.add(user)
    db_session.commit()

    # Assign admin role
    role = db_session.query(Role).filter_by(name="admin").first()
    user_role = UserRole(user_id=user.id, role_id=role.id)
    db_session.add(user_role)
    db_session.commit()

    return user


@pytest.fixture(scope='function')
def user_b(db_session, org_b, store_b, setup_roles):
    """Create User B in Organization B with admin role."""
    user = User(
        org_id=org_b.id,
        store_id=store_b.id,
        username="user_b",
        email="user_b@beta.com",
        password_hash=hash_password("Password123!")
    )
    db_session.add(user)
    db_session.commit()

    # Assign admin role
    role = db_session.query(Role).filter_by(name="admin").first()
    user_role = UserRole(user_id=user.id, role_id=role.id)
    db_session.add(user_role)
    db_session.commit()

    return user


@pytest.fixture(scope='function')
def product_a(db_session, store_a):
    """Create Product in Store A."""
    product = Product(
        store_id=store_a.id,
        sku="PROD-A-001",
        name="Product A",
        price_cents=1000
    )
    db_session.add(product)
    db_session.commit()
    return product


@pytest.fixture(scope='function')
def product_b(db_session, store_b):
    """Create Product in Store B."""
    product = Product(
        store_id=store_b.id,
        sku="PROD-B-001",
        name="Product B",
        price_cents=2000
    )
    db_session.add(product)
    db_session.commit()
    return product


def get_auth_token(client, username: str, password: str) -> str:
    """Helper to get auth token for a user."""
    response = client.post('/api/auth/login', json={
        'username': username,
        'password': password
    })
    if response.status_code == 200:
        return response.json.get('token')
    return None


def auth_headers(token: str) -> dict:
    """Helper to create Authorization headers."""
    return {'Authorization': f'Bearer {token}'}
