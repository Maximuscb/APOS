# backend/app/routes/admin.py
"""
Admin routes for user and role management.

Provides endpoints for:
- User management (list, create, update, deactivate)
- Role management (list, create, assign, revoke)
- Permission management (list, grant, revoke)

All endpoints require authentication and appropriate permissions.
"""

from flask import Blueprint, request, jsonify, g, current_app

from ..extensions import db
from ..models import User, Role, UserRole, Permission, RolePermission
from ..services import auth_service, session_service, permission_service
from ..services.auth_service import PasswordValidationError
from ..decorators import require_auth, require_permission, require_any_permission
from ..permissions import PERMISSION_DEFINITIONS, DEFAULT_ROLE_PERMISSIONS

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


# =============================================================================
# USER MANAGEMENT
# =============================================================================

@admin_bp.get("/users")
@require_auth
@require_permission("VIEW_USERS")
def list_users():
    """
    List all users with their roles.

    Query params:
    - include_inactive: bool (default false) - include deactivated users
    - store_id: int - filter by store
    """
    include_inactive = request.args.get("include_inactive", "false").lower() == "true"
    store_id = request.args.get("store_id", type=int)

    query = db.session.query(User)

    if not include_inactive:
        query = query.filter_by(is_active=True)

    if store_id:
        query = query.filter_by(store_id=store_id)

    users = query.order_by(User.username).all()

    result = []
    for user in users:
        user_dict = user.to_dict()
        # Add roles
        user_roles = db.session.query(UserRole).filter_by(user_id=user.id).all()
        role_names = []
        for ur in user_roles:
            role = db.session.query(Role).get(ur.role_id)
            if role:
                role_names.append(role.name)
        user_dict["roles"] = role_names
        result.append(user_dict)

    return jsonify({"users": result, "count": len(result)})


@admin_bp.get("/users/<int:user_id>")
@require_auth
@require_permission("VIEW_USERS")
def get_user(user_id: int):
    """Get a specific user by ID."""
    user = db.session.query(User).get(user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    user_dict = user.to_dict()

    # Add roles
    user_roles = db.session.query(UserRole).filter_by(user_id=user.id).all()
    role_names = []
    for ur in user_roles:
        role = db.session.query(Role).get(ur.role_id)
        if role:
            role_names.append(role.name)
    user_dict["roles"] = role_names

    # Add permissions
    user_dict["permissions"] = list(permission_service.get_user_permissions(user.id))

    return jsonify({"user": user_dict})


@admin_bp.post("/users")
@require_auth
@require_permission("CREATE_USER")
def create_user():
    """
    Create a new user.

    Request body:
    - username: str (required)
    - email: str (required)
    - password: str (required)
    - store_id: int (optional)
    - role: str (optional) - role to assign
    """
    try:
        data = request.get_json()
        username = data.get("username")
        email = data.get("email")
        password = data.get("password")
        store_id = data.get("store_id")
        role_name = data.get("role")

        if not all([username, email, password]):
            return jsonify({"error": "username, email, and password required"}), 400

        # Create user
        user = auth_service.create_user(username, email, password, store_id)

        # Assign role if provided
        if role_name:
            try:
                auth_service.assign_role(user.id, role_name)
            except ValueError as e:
                # User created but role assignment failed
                return jsonify({
                    "user": user.to_dict(),
                    "warning": f"User created but role assignment failed: {str(e)}"
                }), 201

        # Log security event
        permission_service.log_security_event(
            user_id=g.current_user.id,
            event_type="USER_CREATED",
            success=True,
            resource=f"/api/admin/users",
            action=f"Created user: {username}",
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent")
        )

        user_dict = user.to_dict()
        if role_name:
            user_dict["roles"] = [role_name]

        return jsonify({"user": user_dict, "message": "User created successfully"}), 201

    except PasswordValidationError as e:
        return jsonify({"error": str(e)}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        current_app.logger.exception("Failed to create user")
        return jsonify({"error": "Internal server error"}), 500


@admin_bp.patch("/users/<int:user_id>")
@require_auth
@require_permission("EDIT_USER")
def update_user(user_id: int):
    """
    Update user details.

    Request body (all optional):
    - email: str
    - store_id: int
    """
    user = db.session.query(User).get(user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json()

    if "email" in data:
        # Check email uniqueness
        existing = db.session.query(User).filter(
            User.email == data["email"],
            User.id != user_id
        ).first()
        if existing:
            return jsonify({"error": "Email already in use"}), 400
        user.email = data["email"]

    if "store_id" in data:
        user.store_id = data["store_id"]

    db.session.commit()

    return jsonify({"user": user.to_dict(), "message": "User updated successfully"})


@admin_bp.post("/users/<int:user_id>/deactivate")
@require_auth
@require_permission("DEACTIVATE_USER")
def deactivate_user(user_id: int):
    """
    Deactivate a user account.

    This will:
    1. Set is_active=False
    2. Revoke all active sessions for the user

    The user will be immediately logged out and unable to log back in.
    """
    user = db.session.query(User).get(user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    if not user.is_active:
        return jsonify({"error": "User is already deactivated"}), 400

    # Prevent self-deactivation
    if user.id == g.current_user.id:
        return jsonify({"error": "Cannot deactivate your own account"}), 400

    # Deactivate user
    user.is_active = False

    # Revoke all sessions
    revoked_count = session_service.revoke_all_user_sessions(
        user_id=user.id,
        reason="Account deactivated by admin"
    )

    db.session.commit()

    # Log security event
    permission_service.log_security_event(
        user_id=g.current_user.id,
        event_type="USER_DEACTIVATED",
        success=True,
        resource=f"/api/admin/users/{user_id}/deactivate",
        action=f"Deactivated user: {user.username}",
        reason=f"Revoked {revoked_count} sessions",
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent")
    )

    return jsonify({
        "message": f"User {user.username} deactivated",
        "sessions_revoked": revoked_count
    })


@admin_bp.post("/users/<int:user_id>/reactivate")
@require_auth
@require_permission("DEACTIVATE_USER")
def reactivate_user(user_id: int):
    """Reactivate a deactivated user account."""
    user = db.session.query(User).get(user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    if user.is_active:
        return jsonify({"error": "User is already active"}), 400

    user.is_active = True
    db.session.commit()

    # Log security event
    permission_service.log_security_event(
        user_id=g.current_user.id,
        event_type="USER_REACTIVATED",
        success=True,
        resource=f"/api/admin/users/{user_id}/reactivate",
        action=f"Reactivated user: {user.username}",
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent")
    )

    return jsonify({"message": f"User {user.username} reactivated", "user": user.to_dict()})


@admin_bp.post("/users/<int:user_id>/reset-password")
@require_auth
@require_permission("EDIT_USER")
def reset_user_password(user_id: int):
    """
    Reset a user's password.

    Request body:
    - new_password: str (required)

    This will also revoke all existing sessions for the user.
    """
    user = db.session.query(User).get(user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json()
    new_password = data.get("new_password")

    if not new_password:
        return jsonify({"error": "new_password required"}), 400

    try:
        # Hash the new password (validates strength)
        user.password_hash = auth_service.hash_password(new_password)

        # Revoke all sessions
        revoked_count = session_service.revoke_all_user_sessions(
            user_id=user.id,
            reason="Password reset by admin"
        )

        db.session.commit()

        # Log security event
        permission_service.log_security_event(
            user_id=g.current_user.id,
            event_type="PASSWORD_RESET",
            success=True,
            resource=f"/api/admin/users/{user_id}/reset-password",
            action=f"Reset password for user: {user.username}",
            reason=f"Revoked {revoked_count} sessions",
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent")
        )

        return jsonify({
            "message": f"Password reset for {user.username}",
            "sessions_revoked": revoked_count
        })

    except PasswordValidationError as e:
        return jsonify({"error": str(e)}), 400


# =============================================================================
# ROLE MANAGEMENT
# =============================================================================

@admin_bp.get("/roles")
@require_auth
@require_permission("VIEW_USERS")
def list_roles():
    """List all roles with their permission counts."""
    roles = db.session.query(Role).order_by(Role.name).all()

    result = []
    for role in roles:
        role_dict = role.to_dict()
        # Count permissions
        perm_count = db.session.query(RolePermission).filter_by(role_id=role.id).count()
        role_dict["permission_count"] = perm_count
        result.append(role_dict)

    return jsonify({"roles": result})


@admin_bp.get("/roles/<role_name>")
@require_auth
@require_permission("VIEW_USERS")
def get_role(role_name: str):
    """Get a role with its full permission list."""
    role = db.session.query(Role).filter_by(name=role_name).first()

    if not role:
        return jsonify({"error": "Role not found"}), 404

    role_dict = role.to_dict()

    # Get permissions
    role_perms = db.session.query(RolePermission).filter_by(role_id=role.id).all()
    permissions = []
    for rp in role_perms:
        perm = db.session.query(Permission).get(rp.permission_id)
        if perm:
            permissions.append(perm.to_dict())

    role_dict["permissions"] = permissions

    return jsonify({"role": role_dict})


@admin_bp.post("/roles")
@require_auth
@require_permission("MANAGE_PERMISSIONS")
def create_role():
    """
    Create a new role.

    Request body:
    - name: str (required)
    - description: str (optional)
    """
    data = request.get_json()
    name = data.get("name")
    description = data.get("description")

    if not name:
        return jsonify({"error": "name required"}), 400

    # Check if role exists
    existing = db.session.query(Role).filter_by(name=name).first()
    if existing:
        return jsonify({"error": "Role already exists"}), 400

    role = Role(name=name, description=description)
    db.session.add(role)
    db.session.commit()

    return jsonify({"role": role.to_dict(), "message": "Role created successfully"}), 201


@admin_bp.post("/users/<int:user_id>/roles")
@require_auth
@require_permission("ASSIGN_ROLES")
def assign_role_to_user(user_id: int):
    """
    Assign a role to a user.

    Request body:
    - role_name: str (required)
    """
    user = db.session.query(User).get(user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json()
    role_name = data.get("role_name")

    if not role_name:
        return jsonify({"error": "role_name required"}), 400

    try:
        user_role = auth_service.assign_role(user_id, role_name)

        # Log security event
        permission_service.log_security_event(
            user_id=g.current_user.id,
            event_type="ROLE_ASSIGNED",
            success=True,
            resource=f"/api/admin/users/{user_id}/roles",
            action=f"Assigned role {role_name} to user {user.username}",
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent")
        )

        return jsonify({
            "user_role": user_role.to_dict(),
            "message": f"Role {role_name} assigned to {user.username}"
        }), 201

    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@admin_bp.delete("/users/<int:user_id>/roles/<role_name>")
@require_auth
@require_permission("ASSIGN_ROLES")
def remove_role_from_user(user_id: int, role_name: str):
    """Remove a role from a user."""
    user = db.session.query(User).get(user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    role = db.session.query(Role).filter_by(name=role_name).first()

    if not role:
        return jsonify({"error": "Role not found"}), 404

    user_role = db.session.query(UserRole).filter_by(
        user_id=user_id,
        role_id=role.id
    ).first()

    if not user_role:
        return jsonify({"error": "User does not have this role"}), 400

    db.session.delete(user_role)
    db.session.commit()

    # Log security event
    permission_service.log_security_event(
        user_id=g.current_user.id,
        event_type="ROLE_REVOKED",
        success=True,
        resource=f"/api/admin/users/{user_id}/roles/{role_name}",
        action=f"Revoked role {role_name} from user {user.username}",
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent")
    )

    return jsonify({"message": f"Role {role_name} removed from {user.username}"})


# =============================================================================
# PERMISSION MANAGEMENT
# =============================================================================

@admin_bp.get("/permissions")
@require_auth
@require_permission("VIEW_USERS")
def list_permissions():
    """
    List all available permissions.

    Query params:
    - category: str - filter by category
    """
    category = request.args.get("category")

    query = db.session.query(Permission)

    if category:
        query = query.filter_by(category=category)

    permissions = query.order_by(Permission.category, Permission.code).all()

    return jsonify({"permissions": [p.to_dict() for p in permissions]})


@admin_bp.post("/roles/<role_name>/permissions")
@require_auth
@require_permission("MANAGE_PERMISSIONS")
def grant_permission_to_role(role_name: str):
    """
    Grant a permission to a role.

    Request body:
    - permission_code: str (required)
    """
    data = request.get_json()
    permission_code = data.get("permission_code")

    if not permission_code:
        return jsonify({"error": "permission_code required"}), 400

    try:
        role_permission = permission_service.grant_permission_to_role(role_name, permission_code)

        return jsonify({
            "message": f"Permission {permission_code} granted to role {role_name}",
            "role_permission": role_permission.to_dict() if role_permission else None
        }), 201

    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@admin_bp.delete("/roles/<role_name>/permissions/<permission_code>")
@require_auth
@require_permission("MANAGE_PERMISSIONS")
def revoke_permission_from_role(role_name: str, permission_code: str):
    """Revoke a permission from a role."""
    try:
        revoked = permission_service.revoke_permission_from_role(role_name, permission_code)

        if revoked:
            return jsonify({"message": f"Permission {permission_code} revoked from role {role_name}"})
        else:
            return jsonify({"error": "Permission was not granted to this role"}), 400

    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@admin_bp.get("/permissions/categories")
@require_auth
@require_permission("VIEW_USERS")
def list_permission_categories():
    """List all permission categories."""
    categories = db.session.query(Permission.category).distinct().all()
    return jsonify({"categories": [c[0] for c in categories]})
