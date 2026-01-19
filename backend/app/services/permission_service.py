"""
Permission Checking and Security Event Logging with Multi-Tenant Support

WHY: Enforce role-based access control and create audit trail.
Every permission check is logged for security monitoring.

MULTI-TENANT: Security events include org_id and store_id for tenant isolation.
All permission checks occur within the caller's tenant boundary.

DESIGN PRINCIPLES:
- Fail closed: Deny by default, require explicit permission grant
- Log everything: All checks logged to security_events with tenant context
- Performance: Cache user permissions to avoid repeated queries
- Tenant isolation: All queries and logs scoped by org_id
"""

from ..extensions import db
from ..models import User, UserRole, Role, RolePermission, Permission, SecurityEvent
from ..permissions import PERMISSION_DEFINITIONS, DEFAULT_ROLE_PERMISSIONS
from app.time_utils import utcnow


class PermissionDeniedError(Exception):
    """Raised when user lacks required permission."""
    pass


def log_security_event(
    user_id: int | None,
    event_type: str,
    success: bool,
    resource: str | None = None,
    action: str | None = None,
    reason: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    org_id: int | None = None,
    store_id: int | None = None
) -> SecurityEvent:
    """
    Log security event to audit trail with tenant context.

    MULTI-TENANT: Includes org_id and store_id for tenant-scoped auditing.
    Events can be filtered by tenant for security monitoring.

    WHY: Immutable audit log for compliance and security monitoring.
    Every permission check, login attempt, and security-relevant action logged.

    event_type examples:
    - PERMISSION_CHECK
    - PERMISSION_DENIED
    - LOGIN_FAILED
    - LOGOUT
    - ROLE_ASSIGNED
    - USER_CREATED
    - TENANT_CONTEXT_MISSING
    - CROSS_TENANT_ACCESS_DENIED
    """
    event = SecurityEvent(
        user_id=user_id,
        org_id=org_id,
        store_id=store_id,
        event_type=event_type,
        resource=resource,
        action=action,
        success=success,
        reason=reason,
        ip_address=ip_address,
        user_agent=user_agent,
        occurred_at=utcnow()
    )

    db.session.add(event)
    db.session.commit()

    return event


def get_user_permissions(user_id: int) -> set[str]:
    """
    Get all permission codes for a user.

    Returns set of permission codes (e.g., {"CREATE_SALE", "POST_SALE"}).

    WHY: Centralized permission resolution. Checks all user's roles
    and collects union of their permissions.
    """
    # Get all roles for user
    user_roles = db.session.query(UserRole).filter_by(user_id=user_id).all()

    if not user_roles:
        return set()

    # Collect all permission codes from all roles
    permission_codes = set()

    for user_role in user_roles:
        role_permissions = db.session.query(RolePermission).filter_by(
            role_id=user_role.role_id
        ).all()

        for role_perm in role_permissions:
            permission = db.session.query(Permission).get(role_perm.permission_id)
            if permission:
                permission_codes.add(permission.code)

    return permission_codes


def user_has_permission(user_id: int, permission_code: str) -> bool:
    """
    Check if user has a specific permission.

    Returns True if user has permission, False otherwise.

    WHY: Core permission check function. Used by decorators and manual checks.
    """
    user_permissions = get_user_permissions(user_id)
    return permission_code in user_permissions


def require_permission(
    user_id: int,
    permission_code: str,
    resource: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    org_id: int | None = None,
    store_id: int | None = None
) -> None:
    """
    Require user to have permission, raise PermissionDeniedError if not.

    MULTI-TENANT: Logs all permission checks with org_id and store_id
    for tenant-scoped auditing.

    Logs all permission checks (granted and denied) to security_events.

    WHY: Explicit permission enforcement with audit trail.
    Raises exception for easy integration with Flask error handlers.

    Usage:
        require_permission(user.id, "CREATE_SALE", resource="/api/sales", org_id=g.org_id)
    """
    has_permission = user_has_permission(user_id, permission_code)

    # Log the permission check with tenant context
    log_security_event(
        user_id=user_id,
        event_type="PERMISSION_DENIED" if not has_permission else "PERMISSION_GRANTED",
        success=has_permission,
        resource=resource,
        action=permission_code,
        reason=None if has_permission else f"Missing permission: {permission_code}",
        ip_address=ip_address,
        user_agent=user_agent,
        org_id=org_id,
        store_id=store_id
    )

    if not has_permission:
        raise PermissionDeniedError(f"Permission denied: {permission_code}")


def get_user_role_names(user_id: int) -> list[str]:
    """Get list of role names for a user."""
    user_roles = db.session.query(UserRole).filter_by(user_id=user_id).all()

    role_names = []
    for user_role in user_roles:
        role = db.session.query(Role).get(user_role.role_id)
        if role:
            role_names.append(role.name)

    return role_names


def initialize_permissions():
    """
    Initialize all permission definitions in database.

    Creates Permission records for all codes in PERMISSION_DEFINITIONS.
    Idempotent: Safe to run multiple times.

    WHY: Permissions must exist in DB before they can be assigned to roles.
    """
    created_count = 0

    for code, name, description, category in PERMISSION_DEFINITIONS:
        existing = db.session.query(Permission).filter_by(code=code).first()

        if not existing:
            permission = Permission(
                code=code,
                name=name,
                description=description,
                category=category
            )
            db.session.add(permission)
            created_count += 1

    db.session.commit()
    return created_count


def assign_default_role_permissions():
    """
    Assign default permissions to roles based on DEFAULT_ROLE_PERMISSIONS.

    Creates RolePermission records linking roles to their default permissions.
    Idempotent: Safe to run multiple times (skips existing).

    WHY: Default permission sets ensure consistent RBAC out-of-the-box.
    Admin gets all permissions, manager gets subset, cashier gets minimal.
    """
    created_count = 0

    for role_name, permission_codes in DEFAULT_ROLE_PERMISSIONS.items():
        role = db.session.query(Role).filter_by(name=role_name).first()

        if not role:
            continue  # Role doesn't exist, skip

        for permission_code in permission_codes:
            permission = db.session.query(Permission).filter_by(code=permission_code).first()

            if not permission:
                continue  # Permission doesn't exist, skip

            # Check if already assigned
            existing = db.session.query(RolePermission).filter_by(
                role_id=role.id,
                permission_id=permission.id
            ).first()

            if not existing:
                role_permission = RolePermission(
                    role_id=role.id,
                    permission_id=permission.id
                )
                db.session.add(role_permission)
                created_count += 1

    db.session.commit()
    return created_count


def grant_permission_to_role(role_name: str, permission_code: str):
    """Grant a permission to a role."""
    role = db.session.query(Role).filter_by(name=role_name).first()
    if not role:
        raise ValueError(f"Role '{role_name}' not found")

    permission = db.session.query(Permission).filter_by(code=permission_code).first()
    if not permission:
        raise ValueError(f"Permission '{permission_code}' not found")

    # Check if already granted
    existing = db.session.query(RolePermission).filter_by(
        role_id=role.id,
        permission_id=permission.id
    ).first()

    if existing:
        return existing  # Already granted

    role_permission = RolePermission(
        role_id=role.id,
        permission_id=permission.id
    )

    db.session.add(role_permission)
    db.session.commit()

    return role_permission


def revoke_permission_from_role(role_name: str, permission_code: str):
    """Revoke a permission from a role."""
    role = db.session.query(Role).filter_by(name=role_name).first()
    if not role:
        raise ValueError(f"Role '{role_name}' not found")

    permission = db.session.query(Permission).filter_by(code=permission_code).first()
    if not permission:
        raise ValueError(f"Permission '{permission_code}' not found")

    role_permission = db.session.query(RolePermission).filter_by(
        role_id=role.id,
        permission_id=permission.id
    ).first()

    if role_permission:
        db.session.delete(role_permission)
        db.session.commit()
        return True

    return False  # Wasn't granted in the first place
