# Overview: Flask API routes for admin operations; parses input and returns JSON responses.

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
from ..models import User, Role, UserRole, Permission, RolePermission, UserPermissionOverride, Store
from ..services import auth_service, session_service, permission_service, user_store_access_service
from ..services.auth_service import PasswordValidationError
from ..decorators import require_auth, require_permission, require_any_permission
from ..permissions import PERMISSION_DEFINITIONS, DEFAULT_ROLE_PERMISSIONS

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def _get_user_in_current_org(user_id: int) -> User | None:
    return db.session.query(User).filter_by(id=user_id, org_id=g.org_id).first()


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
    if g.org_id is not None:
        query = query.filter(User.org_id == g.org_id)

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
        explicit_manager_access = user_store_access_service.list_manager_access(user.id)
        user_dict["explicit_manager_store_ids"] = [item.store_id for item in explicit_manager_access]
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
    if g.org_id is not None and user.org_id != g.org_id:
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

    # Add permissions and overrides
    user_dict["permissions"] = list(permission_service.get_user_permissions(user.id))
    overrides = db.session.query(UserPermissionOverride).filter_by(user_id=user.id).all()
    user_dict["permission_overrides"] = [o.to_dict() for o in overrides]

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


@admin_bp.get("/users/<int:user_id>/manager-stores")
@require_auth
@require_any_permission("EDIT_USER", "MANAGE_STORES")
def list_user_manager_stores(user_id: int):
    """List explicit and effective manager-store access for a user."""
    user = _get_user_in_current_org(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    explicit_items = user_store_access_service.list_manager_access(user_id)
    effective_store_ids = sorted(user_store_access_service.get_manager_store_ids(user_id, include_primary=True))

    return jsonify({
        "items": [i.to_dict() for i in explicit_items],
        "effective_store_ids": effective_store_ids,
        "primary_store_id": user.store_id,
    })


@admin_bp.post("/users/<int:user_id>/manager-stores")
@require_auth
@require_any_permission("EDIT_USER", "MANAGE_STORES")
def grant_user_manager_store(user_id: int):
    """Grant manager-store access for a user to an additional store."""
    user = _get_user_in_current_org(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json(silent=True) or {}
    store_id = data.get("store_id")
    if not store_id:
        return jsonify({"error": "store_id is required"}), 400

    store = db.session.query(Store).filter_by(id=store_id).first()
    if not store or store.org_id != g.org_id:
        return jsonify({"error": "Store not found"}), 404

    try:
        access = user_store_access_service.grant_manager_access(
            user_id=user_id,
            store_id=store_id,
            granted_by_user_id=g.current_user.id,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"item": access.to_dict()}), 201


@admin_bp.delete("/users/<int:user_id>/manager-stores/<int:store_id>")
@require_auth
@require_any_permission("EDIT_USER", "MANAGE_STORES")
def revoke_user_manager_store(user_id: int, store_id: int):
    """Revoke manager-store access for a user."""
    user = _get_user_in_current_org(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    if user.store_id == store_id:
        return jsonify({"error": "Cannot revoke user's primary store access"}), 400

    store = db.session.query(Store).filter_by(id=store_id).first()
    if not store or store.org_id != g.org_id:
        return jsonify({"error": "Store not found"}), 404

    revoked = user_store_access_service.revoke_manager_access(user_id=user_id, store_id=store_id)
    if not revoked:
        return jsonify({"error": "Access mapping not found"}), 404

    return jsonify({"message": "Manager store access revoked"})


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
    query = db.session.query(Role)
    if g.org_id is not None:
        query = query.filter(Role.org_id == g.org_id)
    roles = query.order_by(Role.name).all()

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
    query = db.session.query(Role).filter_by(name=role_name)
    if g.org_id is not None:
        query = query.filter(Role.org_id == g.org_id)
    role = query.first()

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


# =============================================================================
# PER-USER PERMISSION OVERRIDES
# =============================================================================

@admin_bp.get("/users/<int:user_id>/permission-overrides")
@require_auth
@require_permission("MANAGE_PERMISSIONS")
def list_permission_overrides(user_id: int):
    """List permission overrides for a user."""
    user = db.session.query(User).get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    overrides = db.session.query(UserPermissionOverride).filter_by(user_id=user_id).all()
    return jsonify({"overrides": [o.to_dict() for o in overrides]})


@admin_bp.post("/users/<int:user_id>/permission-overrides")
@require_auth
@require_permission("MANAGE_PERMISSIONS")
def upsert_permission_override(user_id: int):
    """
    Create or update a permission override for a user.

    Request body:
    - permission_code: str (required)
    - override_type: "GRANT" or "DENY" (required)
    - reason: str (optional)
    """
    user = db.session.query(User).get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json(silent=True) or {}
    permission_code = data.get("permission_code")
    override_type = data.get("override_type")
    reason = data.get("reason")

    if not permission_code or not override_type:
        return jsonify({"error": "permission_code and override_type are required"}), 400

    try:
        override = permission_service.grant_permission_override(
            user_id=user_id,
            permission_code=permission_code,
            granted_by_user_id=g.current_user.id,
            override_type=override_type,
            reason=reason,
        )
        return jsonify({"override": override.to_dict()}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@admin_bp.delete("/users/<int:user_id>/permission-overrides/<permission_code>")
@require_auth
@require_permission("MANAGE_PERMISSIONS")
def revoke_permission_override_route(user_id: int, permission_code: str):
    """Revoke a permission override for a user."""
    user = db.session.query(User).get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    override = permission_service.revoke_permission_override(
        user_id=user_id,
        permission_code=permission_code,
        revoked_by_user_id=g.current_user.id,
        reason="Revoked via admin API",
    )
    if not override:
        return jsonify({"error": "Override not found"}), 404

    return jsonify({"override": override.to_dict()})
