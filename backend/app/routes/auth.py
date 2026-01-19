# backend/app/routes/auth.py
"""
Phase 6: Production-Ready Authentication API routes

SECURITY FEATURES:
- Password strength validation on registration
- Login throttling to prevent brute-force attacks
- Account lockout after repeated failed attempts
- Session management with token-based auth
"""

from flask import Blueprint, request, jsonify, current_app

from ..services import auth_service
from ..services import session_service
from ..services import login_throttle_service
from ..services import permission_service
from ..services.auth_service import PasswordValidationError


auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.post("/register")
def register_route():
    """
    Self-registration is disabled for security.

    Users can only be created by administrators via:
    - POST /api/admin/users (requires CREATE_USER permission)
    - CLI: flask create-user
    """
    return jsonify({
        "error": "Self-registration is disabled. Contact an administrator to create an account."
    }), 403


@auth_bp.post("/login")
def login_route():
    """
    Authenticate user and create session token.

    Returns user info and session token on success.
    Token must be included in Authorization header for protected routes.

    SECURITY:
    - Checks for account lockout before attempting authentication
    - Records failed attempts for throttling
    - Records successful logins for audit trail
    """
    try:
        data = request.get_json()
        username = data.get("username") or data.get("email") or data.get("identifier")
        password = data.get("password")

        if not all([username, password]):
            return jsonify({"error": "username/email and password required"}), 400

        user_agent = request.headers.get("User-Agent")
        ip_address = request.remote_addr

        # Check if account is locked due to too many failed attempts
        is_locked, seconds_remaining = login_throttle_service.is_account_locked(username)
        if is_locked:
            minutes_remaining = (seconds_remaining // 60) + 1 if seconds_remaining else 15
            return jsonify({
                "error": "Account temporarily locked due to too many failed login attempts",
                "locked": True,
                "retry_after_seconds": seconds_remaining,
                "retry_after_minutes": minutes_remaining,
            }), 429  # Too Many Requests

        # Authenticate user
        user = auth_service.authenticate(username, password)

        if not user:
            # Record failed attempt
            failed_count = login_throttle_service.record_failed_attempt(
                identifier=username,
                ip_address=ip_address,
                user_agent=user_agent,
                reason="Invalid credentials"
            )

            # Check if this failure triggered a lockout
            max_attempts = login_throttle_service.MAX_FAILED_ATTEMPTS
            remaining = max_attempts - failed_count

            if remaining <= 0:
                return jsonify({
                    "error": "Account locked due to too many failed login attempts",
                    "locked": True,
                    "retry_after_minutes": 15,
                }), 429
            elif remaining <= 3:
                # Warn user they're close to lockout
                return jsonify({
                    "error": "Invalid credentials",
                    "warning": f"{remaining} attempts remaining before account lockout"
                }), 401
            else:
                return jsonify({"error": "Invalid credentials"}), 401

        # Record successful login
        login_throttle_service.record_successful_login(
            user_id=user.id,
            identifier=username,
            ip_address=ip_address,
            user_agent=user_agent
        )

        # Create session token
        session, token = session_service.create_session(
            user_id=user.id,
            user_agent=user_agent,
            ip_address=ip_address
        )

        return jsonify({
            "user": user.to_dict(),
            "token": token,
            "session": session.to_dict(),
            "message": "Login successful"
        }), 200

    except Exception:
        current_app.logger.exception("Failed to login user")
        return jsonify({"error": "Internal server error"}), 500


@auth_bp.get("/lockout-status/<identifier>")
def lockout_status_route(identifier: str):
    """
    Check lockout status for an account.

    This is a public endpoint to allow users to check if their account is locked
    and when they can retry.
    """
    status = login_throttle_service.get_lockout_status(identifier)
    return jsonify(status)


@auth_bp.post("/logout")
def logout_route():
    """
    Revoke session token (logout).

    Expects Authorization header: Bearer <token>

    WHY: Explicit logout prevents token reuse.
    """
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Authorization header required"}), 401

        token = auth_header.split(" ", 1)[1]

        # Revoke the session
        revoked = session_service.revoke_session(token, reason="User logout")

        if not revoked:
            return jsonify({"error": "Invalid or expired token"}), 401

        return jsonify({"message": "Logout successful"}), 200

    except Exception:
        current_app.logger.exception("Failed to logout user")
        return jsonify({"error": "Internal server error"}), 500


@auth_bp.post("/validate")
def validate_route():
    """
    Validate session token and return user info WITH permissions and tenant context.

    Expects Authorization header: Bearer <token>

    Returns:
        - user: User object with id, username, email, store_id, org_id
        - permissions: List of permission codes the user has (for RBAC filtering)
        - org_id: Organization ID (tenant context)
        - store_id: User's store ID (may be null for org-level users)
        - message: Status message

    WHY: Frontend can check if token is still valid and get permissions
    for UI filtering (hiding nav items, buttons, etc.)
    """
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Authorization header required"}), 401

        token = auth_header.split(" ", 1)[1]

        # Validate token and get session context (includes tenant info)
        context = session_service.validate_session(token)

        if not context:
            return jsonify({"error": "Invalid or expired token"}), 401

        # Get user's permissions for frontend RBAC
        permissions = list(permission_service.get_user_permissions(context.user.id))

        return jsonify({
            "user": context.user.to_dict(),
            "permissions": permissions,
            "org_id": context.org_id,
            "store_id": context.store_id,
            "message": "Token valid"
        }), 200

    except Exception:
        current_app.logger.exception("Failed to validate session")
        return jsonify({"error": "Internal server error"}), 500


# NOTE: /roles/init endpoint REMOVED for security
# Use CLI command: flask init-roles
# See backend/app/cli.py for role initialization

# NOTE: /users/<id>/roles endpoint REMOVED for security
# Use admin endpoint: POST /api/admin/users/<id>/roles (requires ASSIGN_ROLES permission)
# See backend/app/routes/admin.py
