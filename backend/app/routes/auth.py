# backend/app/routes/auth.py
"""Phase 6: Production-Ready Authentication API routes"""

from flask import Blueprint, request, jsonify

from ..services import auth_service
from ..services import session_service
from ..services.auth_service import PasswordValidationError


auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.post("/register")
def register_route():
    """
    Create new user account with secure password hashing.

    Password must meet strength requirements or 400 error returned.
    """
    try:
        data = request.get_json()
        username = data.get("username")
        email = data.get("email")
        password = data.get("password")
        store_id = data.get("store_id")

        if not all([username, email, password]):
            return jsonify({"error": "username, email, and password required"}), 400

        user = auth_service.create_user(username, email, password, store_id)

        return jsonify({
            "user": user.to_dict(),
            "message": "User created successfully"
        }), 201

    except PasswordValidationError as e:
        return jsonify({"error": str(e)}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@auth_bp.post("/login")
def login_route():
    """
    Authenticate user and create session token.

    Returns user info and session token on success.
    Token must be included in Authorization header for protected routes.

    WHY: Session tokens enable stateless authentication with timeout.
    """
    try:
        data = request.get_json()
        username = data.get("username") or data.get("email") or data.get("identifier")
        password = data.get("password")

        if not all([username, password]):
            return jsonify({"error": "username/email and password required"}), 400

        # Authenticate user
        user = auth_service.authenticate(username, password)

        if not user:
            return jsonify({"error": "Invalid credentials"}), 401

        # Create session token
        user_agent = request.headers.get("User-Agent")
        ip_address = request.remote_addr
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

    except Exception as e:
        return jsonify({"error": str(e)}), 500


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

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@auth_bp.post("/validate")
def validate_route():
    """
    Validate session token and return user info.

    Expects Authorization header: Bearer <token>

    WHY: Frontend can check if token is still valid without making other API calls.
    """
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Authorization header required"}), 401

        token = auth_header.split(" ", 1)[1]

        # Validate token and get user
        user = session_service.validate_session(token)

        if not user:
            return jsonify({"error": "Invalid or expired token"}), 401

        return jsonify({
            "user": user.to_dict(),
            "message": "Token valid"
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@auth_bp.post("/roles/init")
def init_roles_route():
    """Initialize default roles."""
    try:
        auth_service.create_default_roles()
        return jsonify({"message": "Default roles created"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@auth_bp.post("/users/<int:user_id>/roles")
def assign_role_route(user_id: int):
    """Assign role to user."""
    try:
        data = request.get_json()
        role_name = data.get("role_name")

        if not role_name:
            return jsonify({"error": "role_name required"}), 400

        user_role = auth_service.assign_role(user_id, role_name)

        return jsonify({"user_role": user_role.to_dict()}), 201

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
