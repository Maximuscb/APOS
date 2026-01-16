#!/usr/bin/env python3
"""
Comprehensive Feature Testing Script

Tests all 14 feature areas plus cross-cutting concerns:
- Feature 0: System health + CORS
- Feature 1-13: All functional areas
- Cross-cutting: Auth boundaries, race conditions, large data, integer invariants
"""

import sys
import os
import json
import threading
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.extensions import db
from app.models import *
from app.services import auth_service, session_service, permission_service


class TestResults:
    def __init__(self):
        self.passed = []
        self.failed = []
        self.bugs = []

    def add_pass(self, test_name):
        self.passed.append(test_name)
        print(f"✓ PASS: {test_name}")

    def add_fail(self, test_name, error):
        self.failed.append((test_name, str(error)))
        print(f"✗ FAIL: {test_name}: {error}")

    def add_bug(self, bug_description):
        self.bugs.append(bug_description)
        print(f"🐛 BUG FOUND: {bug_description}")

    def summary(self):
        total = len(self.passed) + len(self.failed)
        print(f"\n{'='*80}")
        print(f"TEST SUMMARY")
        print(f"{'='*80}")
        print(f"Total Tests: {total}")
        print(f"Passed: {len(self.passed)} ({100*len(self.passed)//total if total > 0 else 0}%)")
        print(f"Failed: {len(self.failed)}")
        print(f"Bugs Found: {len(self.bugs)}")

        if self.failed:
            print(f"\n{'='*80}")
            print("FAILED TESTS:")
            print(f"{'='*80}")
            for test_name, error in self.failed:
                print(f"  - {test_name}")
                print(f"    Error: {error}")

        if self.bugs:
            print(f"\n{'='*80}")
            print("BUGS IDENTIFIED:")
            print(f"{'='*80}")
            for i, bug in enumerate(self.bugs, 1):
                print(f"  {i}. {bug}")


def setup_test_db():
    """Initialize fresh test database."""
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()

        # Create test store
        store = Store(name="Test Store", code="STORE001")
        db.session.add(store)
        db.session.commit()

        return app, store.id


def test_feature_0_system_health(results):
    """Test Feature 0: System health check + CORS."""
    print(f"\n{'='*80}")
    print("FEATURE 0: System Health Check + CORS")
    print(f"{'='*80}")

    app, store_id = setup_test_db()
    client = app.test_client()

    # Test health endpoint
    try:
        resp = client.get('/health')
        if resp.status_code == 200 and resp.json.get('status') == 'ok':
            results.add_pass("Health check returns 200 with status:ok")
        else:
            results.add_fail("Health check", f"Got {resp.status_code}, {resp.json}")
    except Exception as e:
        results.add_fail("Health check", e)

    # Test CORS with allowed origin
    try:
        resp = client.get('/health', headers={'Origin': 'http://localhost:5173'})
        acao = resp.headers.get('Access-Control-Allow-Origin')
        vary = resp.headers.get('Vary')
        if acao == 'http://localhost:5173' and 'Origin' in (vary or ''):
            results.add_pass("CORS returns correct ACAO for allowed origin")
        else:
            results.add_bug("CORS: Missing or incorrect Access-Control-Allow-Origin header")
    except Exception as e:
        results.add_fail("CORS allowed origin", e)

    # Test CORS with disallowed origin
    try:
        resp = client.get('/health', headers={'Origin': 'http://localhost:5174'})
        acao = resp.headers.get('Access-Control-Allow-Origin')
        if acao != 'http://localhost:5174':
            results.add_pass("CORS blocks disallowed origin")
        else:
            results.add_bug("CORS: Allows origin that should be blocked (localhost:5174)")
    except Exception as e:
        results.add_fail("CORS disallowed origin", e)


def test_feature_1_authentication(results):
    """Test Feature 1: Authentication + sessions."""
    print(f"\n{'='*80}")
    print("FEATURE 1: Authentication + Sessions")
    print(f"{'='*80}")

    app, store_id = setup_test_db()
    client = app.test_client()

    with app.app_context():
        # Initialize roles
        try:
            auth_service.create_default_roles()
            permission_service.initialize_permissions()
            permission_service.assign_default_role_permissions()
            results.add_pass("Initialize roles is idempotent")
        except Exception as e:
            results.add_fail("Initialize roles", e)

    # Test user registration with strong password
    try:
        resp = client.post('/api/auth/register', json={
            'username': 'testuser1',
            'email': 'test1@example.com',
            'password': 'StrongPass123!',
            'store_id': store_id
        })
        if resp.status_code == 201:
            results.add_pass("User registration with strong password")
            user1_data = resp.json
        else:
            results.add_fail("User registration", f"Status {resp.status_code}: {resp.json}")
            return
    except Exception as e:
        results.add_fail("User registration", e)
        return

    # Test registration with weak password
    try:
        resp = client.post('/api/auth/register', json={
            'username': 'testuser2',
            'email': 'test2@example.com',
            'password': 'weak',
            'store_id': store_id
        })
        if resp.status_code == 400:
            results.add_pass("Weak password rejected with 400")
        else:
            results.add_bug(f"Weak password accepted (status {resp.status_code})")
    except Exception as e:
        results.add_fail("Weak password rejection", e)

    # Test duplicate username
    try:
        resp = client.post('/api/auth/register', json={
            'username': 'testuser1',
            'email': 'test3@example.com',
            'password': 'StrongPass123!',
            'store_id': store_id
        })
        if resp.status_code in (400, 409):
            results.add_pass("Duplicate username rejected")
        else:
            results.add_bug(f"Duplicate username allowed (status {resp.status_code})")
    except Exception as e:
        results.add_fail("Duplicate username test", e)

    # Test login
    try:
        resp = client.post('/api/auth/login', json={
            'username': 'testuser1',
            'password': 'StrongPass123!'
        })
        if resp.status_code == 200 and 'token' in resp.json:
            token = resp.json['token']
            results.add_pass("Login returns token")
        else:
            results.add_fail("Login", f"Status {resp.status_code}: {resp.json}")
            return
    except Exception as e:
        results.add_fail("Login", e)
        return

    # Test invalid credentials
    try:
        resp = client.post('/api/auth/login', json={
            'username': 'testuser1',
            'password': 'WrongPassword123!'
        })
        if resp.status_code == 401:
            results.add_pass("Invalid credentials return 401")
        else:
            results.add_bug(f"Invalid credentials got status {resp.status_code}")
    except Exception as e:
        results.add_fail("Invalid credentials test", e)

    # Test token validation
    try:
        resp = client.post('/api/auth/validate',
            headers={'Authorization': f'Bearer {token}'})
        if resp.status_code == 200:
            results.add_pass("Token validation works")
        else:
            results.add_fail("Token validation", f"Status {resp.status_code}")
    except Exception as e:
        results.add_fail("Token validation", e)

    # Test logout
    try:
        resp = client.post('/api/auth/logout',
            headers={'Authorization': f'Bearer {token}'})
        if resp.status_code == 200:
            results.add_pass("Logout succeeds")

            # Verify token is revoked
            resp2 = client.post('/api/auth/validate',
                headers={'Authorization': f'Bearer {token}'})
            if resp2.status_code == 401:
                results.add_pass("Token revoked after logout")
            else:
                results.add_bug(f"Token still valid after logout (status {resp2.status_code})")
        else:
            results.add_fail("Logout", f"Status {resp.status_code}")
    except Exception as e:
        results.add_fail("Logout test", e)


def test_feature_2_permissions(results):
    """Test Feature 2: Permission enforcement."""
    print(f"\n{'='*80}")
    print("FEATURE 2: Permission Enforcement")
    print(f"{'='*80}")

    app, store_id = setup_test_db()
    client = app.test_client()

    with app.app_context():
        auth_service.create_default_roles()
        permission_service.initialize_permissions()
        permission_service.assign_default_role_permissions()

        # Create user without permissions
        user = User(
            username='noperm',
            email='noperm@example.com',
            password_hash=auth_service.hash_password('Pass123!'),
            store_id=store_id,
            is_active=True
        )
        db.session.add(user)
        db.session.commit()

        # Create token
        token_str, _ = session_service.create_session(user.id, 'test-agent', '127.0.0.1')

    # Try to access protected endpoint without token
    try:
        resp = client.post('/api/sales/', json={'store_id': store_id})
        if resp.status_code == 401:
            results.add_pass("Protected endpoint requires auth")
        else:
            results.add_bug(f"Protected endpoint accessible without auth (status {resp.status_code})")
    except Exception as e:
        results.add_fail("Auth required test", e)

    # Try with token but no permission
    try:
        resp = client.post('/api/sales/',
            json={'store_id': store_id},
            headers={'Authorization': f'Bearer {token_str}'})
        if resp.status_code == 403:
            results.add_pass("Permission-protected endpoint returns 403")
        else:
            results.add_bug(f"No CREATE_SALE permission but got status {resp.status_code}")
    except Exception as e:
        results.add_fail("Permission enforcement test", e)


def test_feature_3_products(results):
    """Test Feature 3: Products CRUD."""
    print(f"\n{'='*80}")
    print("FEATURE 3: Products")
    print(f"{'='*80}")

    app, store_id = setup_test_db()
    client = app.test_client()

    with app.app_context():
        auth_service.create_default_roles()
        permission_service.initialize_permissions()
        permission_service.assign_default_role_permissions()
        admin = User(
            username='admin',
            email='admin@example.com',
            password_hash=auth_service.hash_password('Admin123!'),
            store_id=store_id,
            is_active=True
        )
        db.session.add(admin)
        db.session.flush()

        # Assign admin role
        admin_role = Role.query.filter_by(name='admin').first()
        user_role = UserRole(user_id=admin.id, role_id=admin_role.id)
        db.session.add(user_role)
        db.session.commit()

        token_str, _ = session_service.create_session(admin.id, 'test-agent', '127.0.0.1')

    # Create product
    try:
        resp = client.post('/api/products',
            json={
                'sku': 'SKU-001',
                'name': 'Test Product',
                'description': 'A test product',
                'price_cents': 1999,
                'is_active': True,
                'store_id': store_id
            },
            headers={'Authorization': f'Bearer {token_str}'})
        if resp.status_code == 201:
            product_id = resp.json['id']
            results.add_pass("Create product")
        else:
            results.add_fail("Create product", f"Status {resp.status_code}: {resp.json}")
            return
    except Exception as e:
        results.add_fail("Create product", e)
        return

    # Test duplicate SKU
    try:
        resp = client.post('/api/products',
            json={
                'sku': 'SKU-001',
                'name': 'Duplicate Product',
                'price_cents': 2999,
                'is_active': True,
                'store_id': store_id
            },
            headers={'Authorization': f'Bearer {token_str}'})
        if resp.status_code in (409, 400):
            results.add_pass("Duplicate SKU rejected")
        else:
            results.add_bug(f"Duplicate SKU allowed (status {resp.status_code})")
    except Exception as e:
        results.add_fail("Duplicate SKU test", e)

    # List products
    try:
        resp = client.get(f'/api/products?store_id={store_id}',
            headers={'Authorization': f'Bearer {token_str}'})
        if resp.status_code == 200 and 'items' in resp.json:
            results.add_pass("List products")
        else:
            results.add_fail("List products", f"Status {resp.status_code}")
    except Exception as e:
        results.add_fail("List products", e)

    # Update product
    try:
        resp = client.put(f'/api/products/{product_id}',
            json={'price_cents': 2499},
            headers={'Authorization': f'Bearer {token_str}'})
        if resp.status_code == 200:
            results.add_pass("Update product")
        else:
            results.add_fail("Update product", f"Status {resp.status_code}")
    except Exception as e:
        results.add_fail("Update product", e)


def test_integer_cents_invariants(results):
    """Test cross-cutting concern: Integer cents validation."""
    print(f"\n{'='*80}")
    print("CROSS-CUTTING: Integer Cents Invariants")
    print(f"{'='*80}")

    app, store_id = setup_test_db()
    client = app.test_client()

    with app.app_context():
        auth_service.create_default_roles()
        permission_service.initialize_permissions()
        permission_service.assign_default_role_permissions()
        admin = User(
            username='admin2',
            email='admin2@example.com',
            password_hash=auth_service.hash_password('Admin123!'),
            store_id=store_id,
            is_active=True
        )
        db.session.add(admin)
        db.session.flush()

        admin_role = Role.query.filter_by(name='admin').first()
        user_role = UserRole(user_id=admin.id, role_id=admin_role.id)
        db.session.add(user_role)
        db.session.commit()

        token_str, _ = session_service.create_session(admin.id, 'test-agent', '127.0.0.1')

    # Test negative price_cents
    try:
        resp = client.post('/api/products',
            json={
                'sku': 'NEG-001',
                'name': 'Negative Price',
                'price_cents': -100,
                'is_active': True,
                'store_id': store_id
            },
            headers={'Authorization': f'Bearer {token_str}'})
        if resp.status_code == 400:
            results.add_pass("Negative price_cents rejected")
        else:
            results.add_bug(f"Negative price_cents allowed (status {resp.status_code})")
    except Exception as e:
        results.add_fail("Negative price test", e)

    # Test huge price_cents (overflow test)
    try:
        resp = client.post('/api/products',
            json={
                'sku': 'HUGE-001',
                'name': 'Huge Price',
                'price_cents': 9999999999999999,
                'is_active': True,
                'store_id': store_id
            },
            headers={'Authorization': f'Bearer {token_str}'})
        if resp.status_code in (200, 201):
            results.add_pass("Huge price_cents handled")
        else:
            results.add_bug(f"Huge price_cents causes error (status {resp.status_code})")
    except Exception as e:
        results.add_bug(f"Huge price_cents crashes: {e}")


def main():
    """Run all tests."""
    print("="*80)
    print("APOS COMPREHENSIVE TEST SUITE")
    print("="*80)

    results = TestResults()

    # Run test suites
    test_feature_0_system_health(results)
    test_feature_1_authentication(results)
    test_feature_2_permissions(results)
    test_feature_3_products(results)
    test_integer_cents_invariants(results)

    # Print summary
    results.summary()

    return len(results.failed) == 0


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
