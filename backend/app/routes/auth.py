# backend/app/routes/auth.py
"""Phase 4: Authentication API routes (stub implementation)"""

from flask import Blueprint, request, jsonify

from ..services import auth_service


auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.post("/register")
def register_route():
    """Create new user account."""
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

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@auth_bp.post("/login")
def login_route():
    """
    Authenticate user (stub implementation).

    SECURITY NOTE: Production needs proper session/JWT handling.
    """
    try:
        data = request.get_json()
        username = data.get("username")
        password = data.get("password")

        if not all([username, password]):
            return jsonify({"error": "username and password required"}), 400

        user = auth_service.authenticate(username, password)

        if not user:
            return jsonify({"error": "Invalid credentials"}), 401

        return jsonify({
            "user": user.to_dict(),
            "message": "Login successful"
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
