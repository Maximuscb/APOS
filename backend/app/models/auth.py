from __future__ import annotations

from ..extensions import db
from app.time_utils import to_utc_z

class User(db.Model):
    """
    User accounts for authentication and attribution.

    MULTI-TENANT: Users belong to exactly one organization (org_id).
    Username and email are unique within an organization, not globally.
    This allows different tenants to have users with the same username.

    WHY: Every action must be attributable. No shared logins.
    """
    __tablename__ = "users"
    __table_args__ = (
        db.UniqueConstraint("org_id", "username", name="uq_users_org_username"),
        db.UniqueConstraint("org_id", "email", name="uq_users_org_email"),
        db.Index("ix_users_org_id", "org_id"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)

    # MULTI-TENANT: User belongs to exactly one organization (nullable for developer users)
    org_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True, index=True)

    username = db.Column(db.String(64), nullable=False, index=True)
    email = db.Column(db.String(255), nullable=False)

    # Bcrypt hashed password
    password_hash = db.Column(db.String(255), nullable=False)

    # Optional 6-digit PIN for Register Mode login (bcrypt hashed)
    # PINs are org-wide per user; PIN login grants full Register Mode access
    pin_hash = db.Column(db.String(255), nullable=True)

    # Store association (nullable for org-level users)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=True)

    is_active = db.Column(db.Boolean, nullable=False, default=True)

    # Developer flag: cross-org superuser that can switch between organizations
    is_developer = db.Column(db.Boolean, nullable=False, default=False)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True)

    organization = db.relationship("Organization", backref=db.backref("users", lazy=True))
    store = db.relationship("Store", backref=db.backref("users", lazy=True))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "org_id": self.org_id,
            "username": self.username,
            "email": self.email,
            "store_id": self.store_id,
            "is_active": self.is_active,
            "is_developer": self.is_developer,
            "created_at": to_utc_z(self.created_at),
            "last_login_at": to_utc_z(self.last_login_at) if self.last_login_at else None,
        }


class UserStoreManagerAccess(db.Model):
    """
    Per-user managerial access to additional stores in the same organization.

    WHY: A user remains affiliated to a primary store (User.store_id), but can
    be granted manager-level oversight on multiple stores.
    """
    __tablename__ = "user_store_manager_access"
    __table_args__ = (
        db.UniqueConstraint("user_id", "store_id", name="uq_user_store_manager_access"),
        db.Index("ix_user_store_manager_access_user", "user_id"),
        db.Index("ix_user_store_manager_access_store", "store_id"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False, index=True)
    granted_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    granted_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())

    user = db.relationship("User", foreign_keys=[user_id], backref=db.backref("manager_store_access", lazy=True))
    store = db.relationship("Store", backref=db.backref("manager_user_access", lazy=True))
    granted_by = db.relationship("User", foreign_keys=[granted_by_user_id])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "store_id": self.store_id,
            "granted_by_user_id": self.granted_by_user_id,
            "granted_at": to_utc_z(self.granted_at),
        }


class Role(db.Model):
    """
    Role-based permissions.

    MULTI-TENANT RBAC:
    - Roles are org-scoped: each organization can define its own roles
    - Role names are unique within an organization: UniqueConstraint("org_id", "name")
    - Permissions (Permission table) remain global system definitions
    - RolePermission links org-specific roles to global permissions

    WHY ORG-SCOPED ROLES:
    1. Different orgs have different business structures (retail vs warehouse)
    2. Allows customizing role names and permission sets per tenant
    3. Tenant A's "Manager" may have different permissions than Tenant B's
    4. New orgs can start with template roles without affecting others

    MIGRATION NOTE:
    Existing roles are backfilled to org_id=1 (Default Organization).
    To support system-wide template roles in the future, consider adding
    an is_template flag or a separate RoleTemplate table.
    """
    __tablename__ = "roles"
    __table_args__ = (
        # Role names unique within an organization
        db.UniqueConstraint("org_id", "name", name="uq_roles_org_name"),
        db.Index("ix_roles_org_id", "org_id"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)

    # MULTI-TENANT: Roles belong to organizations
    org_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True)

    name = db.Column(db.String(64), nullable=False)
    description = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())

    organization = db.relationship("Organization", backref=db.backref("roles", lazy=True))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "org_id": self.org_id,
            "name": self.name,
            "description": self.description,
            "created_at": to_utc_z(self.created_at),
        }

class UserRole(db.Model):
    """User-Role association."""
    __tablename__ = "user_roles"
    __table_args__ = (
        db.UniqueConstraint("user_id", "role_id", name="uq_user_roles"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False, index=True)

    assigned_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())

    user = db.relationship("User", backref=db.backref("user_roles", lazy=True))
    role = db.relationship("Role", backref=db.backref("user_roles", lazy=True))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "role_id": self.role_id,
            "assigned_at": to_utc_z(self.assigned_at),
        }

class Permission(db.Model):
    """
    Permissions for role-based access control.

    WHY: Roles need enforceable permissions. This table defines what actions exist.
    RolePermission links these to roles.

    DESIGN: Permissions are identified by unique codes (e.g., "APPROVE_ADJUSTMENTS").
    Categories group related permissions for UI display.
    """
    __tablename__ = "permissions"
    __table_args__ = {"sqlite_autoincrement": True}

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64), nullable=False, unique=True, index=True)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(64), nullable=False, index=True)  # INVENTORY, SALES, USERS, SYSTEM

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "created_at": to_utc_z(self.created_at),
        }

class RolePermission(db.Model):
    """
    Role-Permission association.

    WHY: Defines which roles have which permissions.
    Many-to-many relationship between roles and permissions.
    """
    __tablename__ = "role_permissions"
    __table_args__ = (
        db.UniqueConstraint("role_id", "permission_id", name="uq_role_permissions"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False, index=True)
    permission_id = db.Column(db.Integer, db.ForeignKey("permissions.id"), nullable=False, index=True)

    granted_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())

    role = db.relationship("Role", backref=db.backref("role_permissions", lazy=True))
    permission = db.relationship("Permission", backref=db.backref("role_permissions", lazy=True))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "role_id": self.role_id,
            "permission_id": self.permission_id,
            "granted_at": to_utc_z(self.granted_at),
        }

class SessionToken(db.Model):
    """
    Secure session token management with tenant context.

    MULTI-TENANT: Session tokens carry org_id and store_id to establish
    tenant context for every authenticated request. This enables tenant
    isolation without repeated database lookups.

    WHY: Stateless auth tokens with timeout and revocation support.
    Tokens are cryptographically secure random strings (32 bytes = 64 hex chars).

    SECURITY NOTES:
    - Tokens stored hashed in database (SHA-256)
    - 24-hour absolute timeout
    - 2-hour idle timeout
    - Revocable on logout or suspicious activity
    - Tenant context (org_id) is immutable for the session lifetime
    """
    __tablename__ = "session_tokens"
    __table_args__ = (
        db.Index("ix_session_tokens_user_active", "user_id", "is_revoked"),
        db.Index("ix_session_tokens_org_id", "org_id"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    # MULTI-TENANT: Tenant context captured at session creation
    # org_id is nullable for developer sessions (developer must switch org before accessing data)
    org_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True, index=True)
    # store_id is the user's primary/current store (nullable for org-level users)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=True, index=True)

    # Token hash (never store plaintext tokens!)
    token_hash = db.Column(db.String(255), nullable=False, unique=True, index=True)

    # Session metadata
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    last_used_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)

    # Revocation support
    is_revoked = db.Column(db.Boolean, nullable=False, default=False, index=True)
    revoked_at = db.Column(db.DateTime(timezone=True), nullable=True)
    revoked_reason = db.Column(db.String(255), nullable=True)

    # Client information (for security monitoring)
    user_agent = db.Column(db.String(512), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)  # IPv6 max length

    user = db.relationship("User", backref=db.backref("session_tokens", lazy=True))
    organization = db.relationship("Organization", backref=db.backref("session_tokens", lazy=True))
    store = db.relationship("Store", backref=db.backref("session_tokens", lazy=True))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "org_id": self.org_id,
            "store_id": self.store_id,
            "created_at": to_utc_z(self.created_at),
            "last_used_at": to_utc_z(self.last_used_at),
            "expires_at": to_utc_z(self.expires_at),
            "is_revoked": self.is_revoked,
            "revoked_at": to_utc_z(self.revoked_at) if self.revoked_at else None,
        }

class UserPermissionOverride(db.Model):
    """
    Per-user permission overrides (grant or deny).

    WHY: Role-based permissions don't cover all cases. Sometimes a specific
    user needs elevated access or restricted access beyond their role.

    DESIGN:
    - Overrides are org-wide per user (not store-scoped)
    - override_type: GRANT (add permission) or DENY (remove permission)
    - Overrides take precedence over role-based permissions
    - DENY overrides take precedence over GRANT overrides
    - Admin permissions cannot be altered via overrides (protected)

    AUDIT:
    - Tracks who granted the override and when
    - Reason field for compliance documentation
    """
    __tablename__ = "user_permission_overrides"
    __table_args__ = (
        db.UniqueConstraint("user_id", "permission_code", name="uq_user_perm_override"),
        db.Index("ix_user_perm_overrides_user", "user_id"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    # Permission code (must match valid Permission.code)
    permission_code = db.Column(db.String(64), nullable=False, index=True)

    # GRANT or DENY
    override_type = db.Column(db.String(8), nullable=False)

    # Who granted this override
    granted_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    # When it was granted
    granted_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())

    # Reason for the override (compliance)
    reason = db.Column(db.Text, nullable=True)

    # Active status (allows soft-delete of overrides)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)

    # Revocation tracking
    revoked_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    revoked_at = db.Column(db.DateTime(timezone=True), nullable=True)
    revocation_reason = db.Column(db.Text, nullable=True)

    # Relationships
    user = db.relationship("User", foreign_keys=[user_id], backref=db.backref("permission_overrides", lazy=True))
    granted_by = db.relationship("User", foreign_keys=[granted_by_user_id])
    revoked_by = db.relationship("User", foreign_keys=[revoked_by_user_id])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "permission_code": self.permission_code,
            "override_type": self.override_type,
            "granted_by_user_id": self.granted_by_user_id,
            "granted_at": to_utc_z(self.granted_at),
            "reason": self.reason,
            "is_active": self.is_active,
            "revoked_by_user_id": self.revoked_by_user_id,
            "revoked_at": to_utc_z(self.revoked_at) if self.revoked_at else None,
            "revocation_reason": self.revocation_reason,
        }


# =============================================================================
# TIMEKEEPING (Shift-Based Clock In/Out)
# =============================================================================
