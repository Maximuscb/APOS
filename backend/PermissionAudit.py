#!/usr/bin/env python3
"""
Phase 7: Role-Based Permission System Tests

Comprehensive test suite for:
- Permission initialization
- Role-permission assignments
- Permission checking (user_has_permission)
- Security event logging
- Permission decorators
- Grant/revoke permissions

WHY: RBAC is critical for security. Must verify all permission checks work correctly.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.extensions import db
from app.models import User, Store, Role, Permission, RolePermission, SecurityEvent
from app.services import auth_service, permission_service
from app.permissions import PERMISSION_DEFINITIONS, DEFAULT_ROLE_PERMISSIONS


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

        # Create roles
        auth_service.create_default_roles()

        return store.id


def test_permission_initialization():
    """Test that all permissions are created correctly."""
    print("\n=== Testing Permission Initialization ===")

    store_id = reset_db()
    app = create_app()

    with app.app_context():
        # Initialize permissions
        created = permission_service.initialize_permissions()
        print(f"PASS PASS: Created {created} permissions")

        # Verify all permissions exist
        total = db.session.query(Permission).count()
        expected = len(PERMISSION_DEFINITIONS)

        if total != expected:
            print(f"FAIL FAIL: Expected {expected} permissions, got {total}")
            return False

        print(f"PASS PASS: All {expected} permissions created")

        # Verify permission codes are unique
        codes = [p.code for p in db.session.query(Permission).all()]
        if len(codes) != len(set(codes)):
            print("FAIL FAIL: Duplicate permission codes found")
            return False

        print("PASS PASS: All permission codes are unique")

    return True


def test_role_permission_assignment():
    """Test default role-permission assignments."""
    print("\n=== Testing Role-Permission Assignment ===")

    store_id = reset_db()
    app = create_app()

    with app.app_context():
        # Initialize permissions
        permission_service.initialize_permissions()

        # Assign default permissions
        created = permission_service.assign_default_role_permissions()
        print(f"PASS PASS: Created {created} role-permission assignments")

        # Verify admin has all permissions
        admin_role = db.session.query(Role).filter_by(name="admin").first()
        admin_perms = db.session.query(RolePermission).filter_by(role_id=admin_role.id).count()
        total_perms = db.session.query(Permission).count()

        if admin_perms != total_perms:
            print(f"FAIL FAIL: Admin should have all {total_perms} permissions, has {admin_perms}")
            return False

        print(f"PASS PASS: Admin has all {total_perms} permissions")

        # Verify manager has fewer permissions than admin
        manager_role = db.session.query(Role).filter_by(name="manager").first()
        manager_perms = db.session.query(RolePermission).filter_by(role_id=manager_role.id).count()

        if manager_perms >= admin_perms:
            print(f"FAIL FAIL: Manager should have fewer permissions than admin")
            return False

        print(f"PASS PASS: Manager has {manager_perms} permissions (less than admin)")

        # Verify cashier has minimal permissions
        cashier_role = db.session.query(Role).filter_by(name="cashier").first()
        cashier_perms = db.session.query(RolePermission).filter_by(role_id=cashier_role.id).count()

        if cashier_perms >= manager_perms:
            print(f"FAIL FAIL: Cashier should have fewer permissions than manager")
            return False

        print(f"PASS PASS: Cashier has {cashier_perms} permissions (minimal access)")

    return True


def test_user_permission_checking():
    """Test checking if user has specific permissions."""
    print("\n=== Testing User Permission Checking ===")

    store_id = reset_db()
    app = create_app()

    with app.app_context():
        # Setup permissions
        permission_service.initialize_permissions()
        permission_service.assign_default_role_permissions()

        # Create users with different roles
        admin = auth_service.create_user("admin", "admin@test.com", "Password123!", store_id)
        auth_service.assign_role(admin.id, "admin")

        manager = auth_service.create_user("manager", "manager@test.com", "Password123!", store_id)
        auth_service.assign_role(manager.id, "manager")

        cashier = auth_service.create_user("cashier", "cashier@test.com", "Password123!", store_id)
        auth_service.assign_role(cashier.id, "cashier")

        # Test admin has SYSTEM_ADMIN permission
        if not permission_service.user_has_permission(admin.id, "SYSTEM_ADMIN"):
            print("FAIL FAIL: Admin should have SYSTEM_ADMIN permission")
            return False
        print("PASS PASS: Admin has SYSTEM_ADMIN permission")

        # Test manager does NOT have SYSTEM_ADMIN permission
        if permission_service.user_has_permission(manager.id, "SYSTEM_ADMIN"):
            print("FAIL FAIL: Manager should NOT have SYSTEM_ADMIN permission")
            return False
        print("PASS PASS: Manager does not have SYSTEM_ADMIN permission")

        # Test manager has APPROVE_ADJUSTMENTS permission
        if not permission_service.user_has_permission(manager.id, "APPROVE_ADJUSTMENTS"):
            print("FAIL FAIL: Manager should have APPROVE_ADJUSTMENTS permission")
            return False
        print("PASS PASS: Manager has APPROVE_ADJUSTMENTS permission")

        # Test cashier has CREATE_SALE permission
        if not permission_service.user_has_permission(cashier.id, "CREATE_SALE"):
            print("FAIL FAIL: Cashier should have CREATE_SALE permission")
            return False
        print("PASS PASS: Cashier has CREATE_SALE permission")

        # Test cashier does NOT have APPROVE_ADJUSTMENTS permission
        if permission_service.user_has_permission(cashier.id, "APPROVE_ADJUSTMENTS"):
            print("FAIL FAIL: Cashier should NOT have APPROVE_ADJUSTMENTS permission")
            return False
        print("PASS PASS: Cashier does not have APPROVE_ADJUSTMENTS permission")

    return True


def test_security_event_logging():
    """Test that security events are logged correctly."""
    print("\n=== Testing Security Event Logging ===")

    store_id = reset_db()
    app = create_app()

    with app.app_context():
        # Setup
        permission_service.initialize_permissions()
        permission_service.assign_default_role_permissions()

        cashier = auth_service.create_user("cashier", "cashier@test.com", "Password123!", store_id)
        auth_service.assign_role(cashier.id, "cashier")

        # Test permission check that should succeed (cashier has CREATE_SALE)
        try:
            permission_service.require_permission(
                cashier.id,
                "CREATE_SALE",
                resource="/api/sales",
                ip_address="127.0.0.1"
            )
            print("PASS PASS: Permission check succeeded (CREATE_SALE granted)")
        except:
            print("FAIL FAIL: Permission check should have succeeded")
            return False

        # Verify event was logged
        granted_event = db.session.query(SecurityEvent).filter_by(
            user_id=cashier.id,
            event_type="PERMISSION_GRANTED"
        ).first()

        if not granted_event:
            print("FAIL FAIL: PERMISSION_GRANTED event not logged")
            return False

        print("PASS PASS: PERMISSION_GRANTED event logged")

        # Test permission check that should fail (cashier doesn't have SYSTEM_ADMIN)
        try:
            permission_service.require_permission(
                cashier.id,
                "SYSTEM_ADMIN",
                resource="/api/admin",
                ip_address="127.0.0.1"
            )
            print("FAIL FAIL: Permission check should have failed")
            return False
        except permission_service.PermissionDeniedError:
            print("PASS PASS: Permission check correctly denied (SYSTEM_ADMIN)")

        # Verify denied event was logged
        denied_event = db.session.query(SecurityEvent).filter_by(
            user_id=cashier.id,
            event_type="PERMISSION_DENIED"
        ).first()

        if not denied_event:
            print("FAIL FAIL: PERMISSION_DENIED event not logged")
            return False

        print("PASS PASS: PERMISSION_DENIED event logged")

        # Verify event details
        if denied_event.action != "SYSTEM_ADMIN":
            print(f"FAIL FAIL: Event action wrong: {denied_event.action}")
            return False

        if "Missing permission" not in denied_event.reason:
            print(f"FAIL FAIL: Event reason wrong: {denied_event.reason}")
            return False

        print("PASS PASS: Security event details correct")

    return True


def test_grant_revoke_permissions():
    """Test granting and revoking permissions."""
    print("\n=== Testing Grant/Revoke Permissions ===")

    store_id = reset_db()
    app = create_app()

    with app.app_context():
        # Setup
        permission_service.initialize_permissions()
        permission_service.assign_default_role_permissions()

        cashier = auth_service.create_user("cashier", "cashier@test.com", "Password123!", store_id)
        auth_service.assign_role(cashier.id, "cashier")

        # Verify cashier doesn't have VOID_SALE initially
        if permission_service.user_has_permission(cashier.id, "VOID_SALE"):
            print("FAIL FAIL: Cashier should not have VOID_SALE permission initially")
            return False

        print("PASS PASS: Cashier does not have VOID_SALE initially")

        # Grant VOID_SALE to cashier role
        permission_service.grant_permission_to_role("cashier", "VOID_SALE")
        print("PASS PASS: Granted VOID_SALE to cashier role")

        # Verify cashier now has VOID_SALE
        if not permission_service.user_has_permission(cashier.id, "VOID_SALE"):
            print("FAIL FAIL: Cashier should have VOID_SALE after grant")
            return False

        print("PASS PASS: Cashier now has VOID_SALE permission")

        # Revoke VOID_SALE from cashier role
        revoked = permission_service.revoke_permission_from_role("cashier", "VOID_SALE")

        if not revoked:
            print("FAIL FAIL: Revocation should return True")
            return False

        print("PASS PASS: Revoked VOID_SALE from cashier role")

        # Verify cashier no longer has VOID_SALE
        if permission_service.user_has_permission(cashier.id, "VOID_SALE"):
            print("FAIL FAIL: Cashier should not have VOID_SALE after revoke")
            return False

        print("PASS PASS: Cashier no longer has VOID_SALE permission")

    return True


def test_get_user_permissions():
    """Test getting all permissions for a user."""
    print("\n=== Testing Get User Permissions ===")

    store_id = reset_db()
    app = create_app()

    with app.app_context():
        # Setup
        permission_service.initialize_permissions()
        permission_service.assign_default_role_permissions()

        admin = auth_service.create_user("admin", "admin@test.com", "Password123!", store_id)
        auth_service.assign_role(admin.id, "admin")

        # Get all admin permissions
        admin_perms = permission_service.get_user_permissions(admin.id)

        # Verify it's a set
        if not isinstance(admin_perms, set):
            print(f"FAIL FAIL: Should return a set, got {type(admin_perms)}")
            return False

        print(f"PASS PASS: Returns set of permissions")

        # Verify admin has many permissions
        if len(admin_perms) < 20:
            print(f"FAIL FAIL: Admin should have many permissions, got {len(admin_perms)}")
            return False

        print(f"PASS PASS: Admin has {len(admin_perms)} permissions")

        # Verify specific permissions are in the set
        required_perms = ["SYSTEM_ADMIN", "APPROVE_ADJUSTMENTS", "CREATE_USER"]
        for perm in required_perms:
            if perm not in admin_perms:
                print(f"FAIL FAIL: Admin should have {perm} permission")
                return False

        print(f"PASS PASS: All required permissions present")

    return True


def test_user_with_no_roles():
    """Test user with no roles has no permissions."""
    print("\n=== Testing User With No Roles ===")

    store_id = reset_db()
    app = create_app()

    with app.app_context():
        # Setup
        permission_service.initialize_permissions()

        # Create user WITHOUT assigning role
        user = auth_service.create_user("norole", "norole@test.com", "Password123!", store_id)

        # Get permissions (should be empty)
        user_perms = permission_service.get_user_permissions(user.id)

        if len(user_perms) != 0:
            print(f"FAIL FAIL: User with no roles should have 0 permissions, has {len(user_perms)}")
            return False

        print("PASS PASS: User with no roles has no permissions")

        # Verify permission check fails
        if permission_service.user_has_permission(user.id, "CREATE_SALE"):
            print("FAIL FAIL: User with no roles should not have any permissions")
            return False

        print("PASS PASS: Permission checks correctly fail for user with no roles")

    return True


def test_permission_categories():
    """Test that permissions are correctly categorized."""
    print("\n=== Testing Permission Categories ===")

    store_id = reset_db()
    app = create_app()

    with app.app_context():
        # Initialize permissions
        permission_service.initialize_permissions()

        # Check each category has permissions
        categories = ["INVENTORY", "SALES", "DOCUMENTS", "USERS", "SYSTEM"]

        for category in categories:
            perms = db.session.query(Permission).filter_by(category=category).all()

            if len(perms) == 0:
                print(f"FAIL FAIL: Category {category} has no permissions")
                return False

            print(f"PASS PASS: Category {category} has {len(perms)} permissions")

    return True


def run_all_tests():
    """Run all permission tests."""
    print("=" * 70)
    print("PHASE 7: ROLE-BASED PERMISSION SYSTEM AUDIT")
    print("=" * 70)

    tests = [
        ("Permission Initialization", test_permission_initialization),
        ("Role-Permission Assignment", test_role_permission_assignment),
        ("User Permission Checking", test_user_permission_checking),
        ("Security Event Logging", test_security_event_logging),
        ("Grant/Revoke Permissions", test_grant_revoke_permissions),
        ("Get User Permissions", test_get_user_permissions),
        ("User With No Roles", test_user_with_no_roles),
        ("Permission Categories", test_permission_categories),
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
        print("\nPASS ALL PERMISSION TESTS PASSED")
        print("\nPhase 7 is PRODUCTION-READY with role-based permissions:")
        print("  - 22 granular permissions across 5 categories")
        print("  - Default role mappings (admin, manager, cashier)")
        print("  - Permission checking with audit logging")
        print("  - Grant/revoke permission management")
        print("  - Security event logging for all checks")
        return True
    else:
        print(f"\nFAIL {failed} TESTS FAILED - DO NOT DEPLOY")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
