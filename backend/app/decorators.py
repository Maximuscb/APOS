# Overview: Request and permission decorators for API routes.

from functools import wraps
from flask import request, jsonify, g

from .services import session_service, permission_service
from .services.permission_service import PermissionDeniedError


def _is_authenticated() -> bool:
    return hasattr(g, 'current_user') and hasattr(g, 'org_id')


def _is_developer() -> bool:
    return _is_authenticated() and bool(g.current_user.is_developer)


def require_auth(f):
    """
    Require authentication and establish tenant context.

    MULTI-TENANT: Sets the following Flask g attributes:
    - g.current_user: The authenticated User object
    - g.org_id: The organization ID (tenant context) - REQUIRED
    - g.store_id: The user's store ID (may be None for org-level users)
    - g.session_context: The full SessionContext object

    SECURITY: Returns 401 if:
    - No Authorization header
    - Invalid or expired token
    - User account deactivated
    - Organization deactivated
    - Session missing org_id (should not happen with new sessions)
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Authentication required"}), 401

        token = auth_header.split(" ", 1)[1]

        # Validate token and get session context (includes tenant info)
        context = session_service.validate_session(token)

        if not context:
            return jsonify({"error": "Invalid or expired token"}), 401

        # MULTI-TENANT: Enforce org_id is present (unless developer)
        # Developer users may have null org_id until they switch into an org
        if not context.org_id and not (context.user and context.user.is_developer):
            permission_service.log_security_event(
                user_id=context.user.id if context.user else None,
                event_type="TENANT_CONTEXT_MISSING",
                success=False,
                resource=request.path,
                action=request.method,
                reason="Session missing org_id - critical security invariant violated",
                ip_address=request.remote_addr,
                user_agent=request.headers.get("User-Agent"),
                org_id=None,
                store_id=None
            )
            return jsonify({"error": "Invalid session: missing tenant context"}), 401

        # Store user and tenant context in Flask g for access in routes
        g.current_user = context.user
        g.org_id = context.org_id
        g.store_id = context.store_id
        g.session_context = context

        return f(*args, **kwargs)

    return decorated_function


def require_permission(permission_code: str):
    """
    Require a specific permission.

    MULTI-TENANT: Security events include org_id and store_id for tenant-scoped auditing.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Ensure @require_auth was called first
            if not _is_authenticated():
                return jsonify({"error": "Authentication required"}), 401

            if _is_developer():
                return f(*args, **kwargs)

            # Get client context for logging
            user = g.current_user
            ip_address = request.remote_addr
            user_agent = request.headers.get("User-Agent")
            resource = request.path

            # Check permission (logs to security_events with tenant context)
            try:
                permission_service.require_permission(
                    user_id=user.id,
                    permission_code=permission_code,
                    resource=resource,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    org_id=g.org_id,
                    store_id=g.store_id
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
    Require any of the specified permissions.

    MULTI-TENANT: Security events include org_id and store_id for tenant-scoped auditing.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not _is_authenticated():
                return jsonify({"error": "Authentication required"}), 401

            if _is_developer():
                return f(*args, **kwargs)

            user = g.current_user
            ip_address = request.remote_addr
            user_agent = request.headers.get("User-Agent")
            resource = request.path

            # Check if user has ANY of the permissions
            user_permissions = permission_service.get_user_permissions(user.id)
            has_any = any(code in user_permissions for code in permission_codes)

            if not has_any:
                permission_service.log_security_event(
                    user_id=user.id,
                    event_type="PERMISSION_DENIED",
                    success=False,
                    resource=resource,
                    action=f"ANY_OF:{','.join(permission_codes)}",
                    reason=f"Missing any of: {', '.join(permission_codes)}",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    org_id=g.org_id,
                    store_id=g.store_id
                )
                return jsonify({
                    "error": "Permission denied",
                    "required_permissions": list(permission_codes),
                    "message": f"Requires any of: {', '.join(permission_codes)}"
                }), 403

            return f(*args, **kwargs)

        return decorated_function
    return decorator


def require_developer(f):
    """Require the authenticated user to be a developer."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(g, 'current_user'):
            return jsonify({"error": "Authentication required"}), 401
        if not g.current_user.is_developer:
            return jsonify({"error": "Developer access required"}), 403
        return f(*args, **kwargs)
    return decorated_function


def require_all_permissions(*permission_codes):
    """
    Require all of the specified permissions.

    MULTI-TENANT: Security events include org_id and store_id for tenant-scoped auditing.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not _is_authenticated():
                return jsonify({"error": "Authentication required"}), 401

            if _is_developer():
                return f(*args, **kwargs)

            user = g.current_user
            ip_address = request.remote_addr
            user_agent = request.headers.get("User-Agent")
            resource = request.path

            # Check if user has ALL of the permissions
            user_permissions = permission_service.get_user_permissions(user.id)
            has_all = all(code in user_permissions for code in permission_codes)
            missing = [code for code in permission_codes if code not in user_permissions]

            if not has_all:
                permission_service.log_security_event(
                    user_id=user.id,
                    event_type="PERMISSION_DENIED",
                    success=False,
                    resource=resource,
                    action=f"ALL_OF:{','.join(permission_codes)}",
                    reason=f"Missing: {', '.join(missing)}",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    org_id=g.org_id,
                    store_id=g.store_id
                )
                return jsonify({
                    "error": "Permission denied",
                    "required_permissions": list(permission_codes),
                    "missing_permissions": missing,
                    "message": f"Requires all of: {', '.join(permission_codes)}"
                }), 403

            return f(*args, **kwargs)

        return decorated_function
    return decorator
