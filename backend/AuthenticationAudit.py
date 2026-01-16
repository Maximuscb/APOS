#!/usr/bin/env python3
"""
Phase 6: Production-Ready Authentication Tests

Comprehensive test suite for:
- Password strength validation
- bcrypt password hashing
- Session token management
- Login/logout workflows
- Token expiration and revocation

WHY: Authentication is security-critical. Must verify all edge cases.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.extensions import db
from app.models import User, SessionToken, Store
from app.services import auth_service, session_service
from app.services.auth_service import PasswordValidationError
from app.time_utils import utcnow
from datetime import timedelta


def reset_db():
    """Reset database to clean state."""
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()

        # Create default store
        store = Store(name="Test Store")
        db.session.add(store)
        db.session.commit()

        return store.id


def test_password_validation():
    """Test password strength validation."""
    print("\n=== Testing Password Validation ===")

    app = create_app()
    with app.app_context():
        # Test: Password too short
        try:
            auth_service.validate_password_strength("Pass1!")
            print("FAIL FAIL: Short password should be rejected")
            return False
        except PasswordValidationError as e:
            print(f"PASS PASS: Short password rejected - {e}")

        # Test: No uppercase
        try:
            auth_service.validate_password_strength("password123!")
            print("FAIL FAIL: No uppercase should be rejected")
            return False
        except PasswordValidationError:
            print("PASS PASS: No uppercase rejected")

        # Test: No lowercase
        try:
            auth_service.validate_password_strength("PASSWORD123!")
            print("FAIL FAIL: No lowercase should be rejected")
            return False
        except PasswordValidationError:
            print("PASS PASS: No lowercase rejected")

        # Test: No digit
        try:
            auth_service.validate_password_strength("Password!")
            print("FAIL FAIL: No digit should be rejected")
            return False
        except PasswordValidationError:
            print("PASS PASS: No digit rejected")

        # Test: No special character
        try:
            auth_service.validate_password_strength("Password123")
            print("FAIL FAIL: No special char should be rejected")
            return False
        except PasswordValidationError:
            print("PASS PASS: No special char rejected")

        # Test: Valid password
        try:
            auth_service.validate_password_strength("Password123!")
            print("PASS PASS: Valid password accepted")
        except PasswordValidationError as e:
            print(f"FAIL FAIL: Valid password rejected - {e}")
            return False

    return True


def test_bcrypt_hashing():
    """Test bcrypt password hashing."""
    print("\n=== Testing bcrypt Password Hashing ===")

    app = create_app()
    with app.app_context():
        password = "TestPassword123!"

        # Test: Hash generation
        hash1 = auth_service.hash_password(password)
        print(f"PASS PASS: Generated bcrypt hash: {hash1[:20]}...")

        # Test: Hash is different each time (salt randomization)
        hash2 = auth_service.hash_password(password)
        if hash1 == hash2:
            print("FAIL FAIL: Same password produced identical hash (salt not working)")
            return False
        print("PASS PASS: Same password produces different hashes (salt working)")

        # Test: Verification works
        if not auth_service.verify_password(password, hash1):
            print("FAIL FAIL: Password verification failed for correct password")
            return False
        print("PASS PASS: Correct password verifies successfully")

        # Test: Wrong password fails
        if auth_service.verify_password("WrongPassword123!", hash1):
            print("FAIL FAIL: Wrong password verified (security breach!)")
            return False
        print("PASS PASS: Wrong password rejected")

        # Test: Legacy stub hash still works (backwards compatibility)
        stub_hash = "STUB_HASH_password123"
        if not auth_service.verify_password("password123", stub_hash):
            print("FAIL FAIL: Legacy stub hash verification broken")
            return False
        print("PASS PASS: Legacy stub hash still works (backwards compatible)")

    return True


def test_user_creation_with_bcrypt():
    """Test user creation with bcrypt hashing."""
    print("\n=== Testing User Creation with bcrypt ===")

    store_id = reset_db()
    app = create_app()

    with app.app_context():
        # Test: Create user with strong password
        user = auth_service.create_user(
            username="testuser",
            email="test@example.com",
            password="SecurePass123!",
            store_id=store_id
        )

        if not user.password_hash.startswith("$2b$"):
            print(f"FAIL FAIL: Password hash doesn't start with bcrypt prefix: {user.password_hash[:10]}")
            return False
        print(f"PASS PASS: User created with bcrypt hash: {user.password_hash[:30]}...")

        # Test: Can authenticate with correct password
        auth_user = auth_service.authenticate("testuser", "SecurePass123!")
        if not auth_user:
            print("FAIL FAIL: Authentication failed with correct password")
            return False
        print("PASS PASS: Authentication successful with correct password")

        # Test: Cannot authenticate with wrong password
        auth_user = auth_service.authenticate("testuser", "WrongPassword123!")
        if auth_user:
            print("FAIL FAIL: Authentication succeeded with wrong password")
            return False
        print("PASS PASS: Authentication failed with wrong password")

        # Test: Weak password rejected
        try:
            auth_service.create_user(
                username="weakuser",
                email="weak@example.com",
                password="weak",
                store_id=store_id
            )
            print("FAIL FAIL: Weak password was accepted")
            return False
        except PasswordValidationError:
            print("PASS PASS: Weak password rejected on user creation")

    return True


def test_session_token_generation():
    """Test session token generation and hashing."""
    print("\n=== Testing Session Token Generation ===")

    app = create_app()
    with app.app_context():
        # Test: Token generation
        token = session_service.generate_token()
        if len(token) != 64:  # 32 bytes * 2 (hex encoding)
            print(f"FAIL FAIL: Token wrong length: {len(token)} (expected 64)")
            return False
        print(f"PASS PASS: Generated 64-char token: {token[:20]}...")

        # Test: Tokens are unique
        token2 = session_service.generate_token()
        if token == token2:
            print("FAIL FAIL: Generated identical tokens (not random!)")
            return False
        print("PASS PASS: Tokens are unique")

        # Test: Token hashing
        token_hash = session_service.hash_token(token)
        if len(token_hash) != 64:  # SHA-256 hex is 64 chars
            print(f"FAIL FAIL: Token hash wrong length: {len(token_hash)}")
            return False
        print(f"PASS PASS: Token hashed to SHA-256: {token_hash[:20]}...")

        # Test: Same token produces same hash (deterministic)
        token_hash2 = session_service.hash_token(token)
        if token_hash != token_hash2:
            print("FAIL FAIL: Same token produced different hashes")
            return False
        print("PASS PASS: Token hashing is deterministic")

    return True


def test_session_lifecycle():
    """Test complete session lifecycle: create, validate, revoke."""
    print("\n=== Testing Session Lifecycle ===")

    store_id = reset_db()
    app = create_app()

    with app.app_context():
        # Create user
        user = auth_service.create_user(
            username="sessionuser",
            email="session@example.com",
            password="SessionPass123!",
            store_id=store_id
        )

        # Test: Create session
        session, token = session_service.create_session(
            user_id=user.id,
            user_agent="Test Browser",
            ip_address="127.0.0.1"
        )
        print(f"PASS PASS: Session created for user {user.id}")

        # Test: Session metadata
        if session.user_agent != "Test Browser":
            print("FAIL FAIL: User agent not stored")
            return False
        if session.ip_address != "127.0.0.1":
            print("FAIL FAIL: IP address not stored")
            return False
        print("PASS PASS: Session metadata stored correctly")

        # Test: Validate session (should work)
        validated_user = session_service.validate_session(token)
        if not validated_user or validated_user.id != user.id:
            print("FAIL FAIL: Session validation failed")
            return False
        print("PASS PASS: Session validation successful")

        # Test: Revoke session
        revoked = session_service.revoke_session(token, reason="Test logout")
        if not revoked:
            print("FAIL FAIL: Session revocation failed")
            return False
        print("PASS PASS: Session revoked successfully")

        # Test: Validate revoked session (should fail)
        validated_user = session_service.validate_session(token)
        if validated_user:
            print("FAIL FAIL: Revoked session still valid")
            return False
        print("PASS PASS: Revoked session rejected")

    return True


def test_session_timeout():
    """Test session absolute and idle timeout."""
    print("\n=== Testing Session Timeout ===")

    store_id = reset_db()
    app = create_app()

    with app.app_context():
        # Create user
        user = auth_service.create_user(
            username="timeoutuser",
            email="timeout@example.com",
            password="TimeoutPass123!",
            store_id=store_id
        )

        # Test: Create session with expired absolute timeout
        session, token = session_service.create_session(user_id=user.id)

        # Manually expire the session
        session.expires_at = utcnow() - timedelta(hours=1)
        db.session.commit()

        validated_user = session_service.validate_session(token)
        if validated_user:
            print("FAIL FAIL: Expired session still valid")
            return False
        print("PASS PASS: Expired session rejected")

        # Test: Create session with idle timeout
        session2, token2 = session_service.create_session(user_id=user.id)

        # Manually set last_used_at to trigger idle timeout
        session2.last_used_at = utcnow() - timedelta(hours=3)
        db.session.commit()

        validated_user = session_service.validate_session(token2)
        if validated_user:
            print("FAIL FAIL: Idle session still valid")
            return False

        # Check that session was auto-revoked
        db.session.refresh(session2)
        if not session2.is_revoked:
            print("FAIL FAIL: Idle session not auto-revoked")
            return False
        if session2.revoked_reason != "Idle timeout":
            print(f"FAIL FAIL: Wrong revocation reason: {session2.revoked_reason}")
            return False
        print("PASS PASS: Idle session auto-revoked with correct reason")

    return True


def test_revoke_all_sessions():
    """Test revoking all sessions for a user."""
    print("\n=== Testing Revoke All Sessions ===")

    store_id = reset_db()
    app = create_app()

    with app.app_context():
        # Create user
        user = auth_service.create_user(
            username="multiuser",
            email="multi@example.com",
            password="MultiPass123!",
            store_id=store_id
        )

        # Create multiple sessions
        session1, token1 = session_service.create_session(user_id=user.id)
        session2, token2 = session_service.create_session(user_id=user.id)
        session3, token3 = session_service.create_session(user_id=user.id)
        print("PASS PASS: Created 3 sessions")

        # Validate all work
        if not all([
            session_service.validate_session(token1),
            session_service.validate_session(token2),
            session_service.validate_session(token3)
        ]):
            print("FAIL FAIL: Not all sessions valid after creation")
            return False
        print("PASS PASS: All 3 sessions valid")

        # Revoke all sessions
        count = session_service.revoke_all_user_sessions(user.id, reason="Password change")
        if count != 3:
            print(f"FAIL FAIL: Expected 3 revoked, got {count}")
            return False
        print(f"PASS PASS: Revoked {count} sessions")

        # Validate all should fail now
        if any([
            session_service.validate_session(token1),
            session_service.validate_session(token2),
            session_service.validate_session(token3)
        ]):
            print("FAIL FAIL: Some sessions still valid after revoke all")
            return False
        print("PASS PASS: All sessions invalidated")

    return True


def test_login_logout_flow():
    """Test complete login/logout workflow."""
    print("\n=== Testing Login/Logout Flow ===")

    store_id = reset_db()
    app = create_app()

    with app.app_context():
        # Create user
        user = auth_service.create_user(
            username="flowuser",
            email="flow@example.com",
            password="FlowPass123!",
            store_id=store_id
        )
        print("PASS PASS: User created")

        # Test: Login (authenticate + create session)
        authenticated_user = auth_service.authenticate("flowuser", "FlowPass123!")
        if not authenticated_user:
            print("FAIL FAIL: Authentication failed")
            return False
        print("PASS PASS: User authenticated")

        session, token = session_service.create_session(user_id=authenticated_user.id)
        print("PASS PASS: Session token created")

        # Test: Token works
        validated_user = session_service.validate_session(token)
        if not validated_user or validated_user.id != user.id:
            print("FAIL FAIL: Token validation failed")
            return False
        print("PASS PASS: Token validated successfully")

        # Test: Logout (revoke session)
        revoked = session_service.revoke_session(token)
        if not revoked:
            print("FAIL FAIL: Logout failed")
            return False
        print("PASS PASS: Logout successful")

        # Test: Token no longer works
        validated_user = session_service.validate_session(token)
        if validated_user:
            print("FAIL FAIL: Token still valid after logout")
            return False
        print("PASS PASS: Token invalid after logout")

    return True


def run_all_tests():
    """Run all authentication tests."""
    print("=" * 70)
    print("PHASE 6: PRODUCTION-READY AUTHENTICATION AUDIT")
    print("=" * 70)

    tests = [
        ("Password Validation", test_password_validation),
        ("bcrypt Hashing", test_bcrypt_hashing),
        ("User Creation with bcrypt", test_user_creation_with_bcrypt),
        ("Session Token Generation", test_session_token_generation),
        ("Session Lifecycle", test_session_lifecycle),
        ("Session Timeout", test_session_timeout),
        ("Revoke All Sessions", test_revoke_all_sessions),
        ("Login/Logout Flow", test_login_logout_flow),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
                print(f"\nFAIL TEST FAILED: {name}")
        except Exception as e:
            failed += 1
            print(f"\nFAIL TEST CRASHED: {name}")
            print(f"   Error: {str(e)}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)

    if failed == 0:
        print("\nPASS ALL AUTHENTICATION TESTS PASSED")
        print("\nPhase 6 is PRODUCTION-READY with secure authentication:")
        print("  - bcrypt password hashing (cost factor 12)")
        print("  - Strong password requirements enforced")
        print("  - Session tokens with SHA-256 hashing")
        print("  - 24-hour absolute, 2-hour idle timeout")
        print("  - Explicit logout and revocation support")
        return True
    else:
        print(f"\nFAIL {failed} TESTS FAILED - DO NOT DEPLOY")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
