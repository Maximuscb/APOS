"""
Phase 7: Route Decorators for Authentication and Authorization

WHY: Declarative permission enforcement on Flask routes.
Decorators provide clean, readable way to protect endpoints.

USAGE:
    @auth_bp.post("/users")
    @require_auth
    @require_permission("CREATE_USER")
    def create_user_route():
        # user is now available in g.current_user
        ...

DESIGN:
- @require_auth: Validates session token, sets g.current_user
- @require_permission: Checks user has specific permission
- Logs all permission checks to security_events
- Returns standard JSON error responses
"""

from functools import wraps
from flask import request, jsonify, g

from .services import session_service, permission_service
from .services.permission_service import PermissionDeniedError


def require_auth(f):
    """
    Decorator: Require valid authentication token.

    Expects Authorization header: Bearer <token>
    Sets g.current_user to authenticated User object.

    Returns 401 if token missing, invalid, or expired.

    WHY: Central authentication enforcement. All protected routes start here.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Authentication required"}), 401

        token = auth_header.split(" ", 1)[1]

        # Validate token and get user
        user = session_service.validate_session(token)

        if not user:
            return jsonify({"error": "Invalid or expired token"}), 401

        # Store user in Flask g for access in route
        g.current_user = user

        return f(*args, **kwargs)

    return decorated_function


def require_permission(permission_code: str):
    """
    Decorator factory: Require specific permission.

    Must be used AFTER @require_auth decorator.
    Checks g.current_user has the specified permission.

    Returns 403 if permission denied.
    Logs all checks (granted and denied) to security_events.

    WHY: Declarative RBAC enforcement. Permission requirements
    are clear and visible at route definition.

    Usage:
        @require_auth
        @require_permission("CREATE_SALE")
        def create_sale():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Ensure @require_auth was called first
            if not hasattr(g, 'current_user'):
                return jsonify({"error": "Authentication required"}), 401

            user = g.current_user

            # Get client context for logging
            ip_address = request.remote_addr
            user_agent = request.headers.get("User-Agent")
            resource = request.path

            # Check permission (logs to security_events)
            try:
                permission_service.require_permission(
                    user_id=user.id,
                    permission_code=permission_code,
                    resource=resource,
                    ip_address=ip_address,
                    user_agent=user_agent
                )
            except PermissionDeniedError as e:
                return jsonify({
                    "error": "Permission denied",
                    "required_permission": permission_code,
                    "message": str(e)
                }), 403

            return f(*args, **kwargs)

        return decorated_function
    return decorator


def require_any_permission(*permission_codes):
    """
    Decorator factory: Require ANY of the specified permissions.

    User needs at least one of the permissions to proceed.
    Useful for routes that can be accessed by multiple roles.

    Returns 403 if none of the permissions are granted.

    Usage:
        @require_auth
        @require_any_permission("APPROVE_DOCUMENTS", "SYSTEM_ADMIN")
        def approve_document():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(g, 'current_user'):
                return jsonify({"error": "Authentication required"}), 401

            user = g.current_user
            ip_address = request.remote_addr
            user_agent = request.headers.get("User-Agent")
            resource = request.path

            # Check if user has ANY of the permissions
            user_permissions = permission_service.get_user_permissions(user.id)
            has_any = any(code in user_permissions for code in permission_codes)

            # Log the check
            permission_service.log_security_event(
                user_id=user.id,
                event_type="PERMISSION_DENIED" if not has_any else "PERMISSION_GRANTED",
                success=has_any,
                resource=resource,
                action=f"ANY_OF:{','.join(permission_codes)}",
                reason=None if has_any else f"Missing any of: {', '.join(permission_codes)}",
                ip_address=ip_address,
                user_agent=user_agent
            )

            if not has_any:
                return jsonify({
                    "error": "Permission denied",
                    "required_permissions": list(permission_codes),
                    "message": f"Requires any of: {', '.join(permission_codes)}"
                }), 403

            return f(*args, **kwargs)

        return decorated_function
    return decorator


def require_all_permissions(*permission_codes):
    """
    Decorator factory: Require ALL of the specified permissions.

    User must have every specified permission to proceed.
    Useful for highly privileged operations.

    Returns 403 if any permission is missing.

    Usage:
        @require_auth
        @require_all_permissions("VOID_SALE", "VIEW_AUDIT_LOG")
        def void_sale_with_audit():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(g, 'current_user'):
                return jsonify({"error": "Authentication required"}), 401

            user = g.current_user
            ip_address = request.remote_addr
            user_agent = request.headers.get("User-Agent")
            resource = request.path

            # Check if user has ALL of the permissions
            user_permissions = permission_service.get_user_permissions(user.id)
            has_all = all(code in user_permissions for code in permission_codes)
            missing = [code for code in permission_codes if code not in user_permissions]

            # Log the check
            permission_service.log_security_event(
                user_id=user.id,
                event_type="PERMISSION_DENIED" if not has_all else "PERMISSION_GRANTED",
                success=has_all,
                resource=resource,
                action=f"ALL_OF:{','.join(permission_codes)}",
                reason=None if has_all else f"Missing: {', '.join(missing)}",
                ip_address=ip_address,
                user_agent=user_agent
            )

            if not has_all:
                return jsonify({
                    "error": "Permission denied",
                    "required_permissions": list(permission_codes),
                    "missing_permissions": missing,
                    "message": f"Requires all of: {', '.join(permission_codes)}"
                }), 403

            return f(*args, **kwargs)

        return decorated_function
    return decorator
