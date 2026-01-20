# Overview: Service-layer operations for auth; encapsulates business logic and database work.

"""
Production-Ready Authentication Service with Multi-Tenant Support

WHY: Every action must be attributable. Uses bcrypt for secure password
hashing and validates password strength.

MULTI-TENANT: Users belong to exactly one organization (org_id).
User creation requires org_id. Username/email uniqueness is tenant-scoped.

SECURITY NOTES:
- Passwords hashed with bcrypt (cost factor 12)
- Minimum 8 characters required
- Must contain uppercase, lowercase, digit, and special char
- Session tokens managed separately (see session_service.py)
- User authentication validates org is active
"""

import bcrypt
import re
from ..extensions import db
from ..models import User, Role, UserRole, Organization
from app.time_utils import utcnow


class PasswordValidationError(Exception):
    """Raised when password doesn't meet strength requirements."""
    pass


def validate_password_strength(password: str) -> None:
    """
    Validate password meets strength requirements.

    Requirements:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character (!@#$%^&*(),.'":{}|<>)

    Raises PasswordValidationError if requirements not met.
    """
    if len(password) < 8:
        raise PasswordValidationError("Password must be at least 8 characters long")

    if not re.search(r'[A-Z]', password):
        raise PasswordValidationError("Password must contain at least one uppercase letter")

    if not re.search(r'[a-z]', password):
        raise PasswordValidationError("Password must contain at least one lowercase letter")

    if not re.search(r'\d', password):
        raise PasswordValidationError("Password must contain at least one digit")

    if not re.search(r"[!@#$%^&*(),.'\":{}|<>]", password):
        raise PasswordValidationError("Password must contain at least one special character")


def hash_password(password: str) -> str:
    """
    Hash password using bcrypt with cost factor 12.

    WHY: Cost factor 12 provides good security/performance balance.
    Higher costs slow down brute force attacks but also slow down login.

    Password is validated for strength before hashing.
    """
    validate_password_strength(password)
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')  # Store as string in database


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verify password against bcrypt hash.

    Returns True if password matches hash, False otherwise.

    WHY timing-safe: bcrypt.checkpw() prevents timing attacks automatically.

    SECURITY: Legacy STUB_HASH_ format has been removed. All passwords must
    use proper bcrypt hashing. If legacy accounts exist, they must reset
    their passwords or be migrated via admin tooling.
    """
    # SECURITY: Reject legacy stub hashes - they are insecure
    if password_hash.startswith("STUB_HASH_"):
        # Log this attempt for security monitoring
        # Legacy stub hashes are no longer supported
        return False

    # Production bcrypt verification
    try:
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    except Exception:
        return False


def create_user(
    username: str,
    email: str,
    password: str,
    org_id: int,
    store_id: int | None = None
) -> User:
    """
    Create new user with bcrypt password hashing.

    MULTI-TENANT: Users must belong to an organization (org_id required).
    Username and email uniqueness is scoped to the organization.

    Password must meet strength requirements or PasswordValidationError will be raised.
    Username and email must be unique within the org or ValueError will be raised.

    WHY: User creation is the entry point for authentication.
    Must enforce password strength at creation time.

    Args:
        username: Unique username within the organization
        email: Unique email within the organization
        password: Password meeting strength requirements
        org_id: Organization ID (required)
        store_id: Store ID for store-level users (optional)

    Returns:
        Created User object

    Raises:
        ValueError: If org doesn't exist, user exists, or store doesn't belong to org
        PasswordValidationError: If password doesn't meet requirements
    """
    # Validate organization exists and is active
    org = db.session.query(Organization).filter_by(id=org_id).first()
    if not org:
        raise ValueError("Organization not found")
    if not org.is_active:
        raise ValueError("Organization is not active")

    # MULTI-TENANT: Check uniqueness within organization
    existing = db.session.query(User).filter(
        User.org_id == org_id,
        db.or_(User.username == username, User.email == email)
    ).first()

    if existing:
        raise ValueError("Username or email already exists in this organization")

    # If store_id provided, verify it belongs to the same org
    if store_id is not None:
        from ..models import Store
        store = db.session.query(Store).filter_by(id=store_id).first()
        if not store:
            raise ValueError("Store not found")
        if store.org_id != org_id:
            raise ValueError("Store does not belong to this organization")

    # Hash password with bcrypt (validates strength automatically)
    password_hash = hash_password(password)

    user = User(
        org_id=org_id,
        username=username,
        email=email,
        password_hash=password_hash,
        store_id=store_id
    )

    db.session.add(user)
    db.session.commit()
    return user


def authenticate(username: str, password: str, org_id: int | None = None) -> User | None:
    """
    Authenticate user with username and password.

    MULTI-TENANT: If org_id is provided, authentication is scoped to that org.
    If org_id is None, searches across all orgs (for backwards compatibility
    during migration, but should be avoided in production).

    Returns User if credentials valid, None otherwise.
    Updates last_login_at timestamp on successful authentication.

    WHY: Central authentication function. All login flows go through here.
    Uses timing-safe comparison via bcrypt.

    Args:
        username: Username or email
        password: Password to verify
        org_id: Organization ID to scope authentication (recommended)

    Returns:
        User object if credentials valid and org is active, None otherwise
    """
    query = db.session.query(User).filter(
        db.or_(User.username == username, User.email == username),
        User.is_active.is_(True),
    )

    # MULTI-TENANT: Scope to organization if provided
    if org_id is not None:
        query = query.filter(User.org_id == org_id)

    user = query.first()

    if not user:
        return None

    # MULTI-TENANT: Verify organization is active
    org = db.session.query(Organization).filter_by(id=user.org_id).first()
    if not org or not org.is_active:
        return None

    # Verify password
    if verify_password(password, user.password_hash):
        user.last_login_at = utcnow()
        db.session.commit()
        return user

    return None


def assign_role(user_id: int, role_name: str) -> UserRole:
    """Assign role to user."""
    role = db.session.query(Role).filter_by(name=role_name).first()
    if not role:
        raise ValueError(f"Role {role_name} not found")

    existing = db.session.query(UserRole).filter_by(
        user_id=user_id,
        role_id=role.id
    ).first()

    if existing:
        return existing

    user_role = UserRole(user_id=user_id, role_id=role.id)

    db.session.add(user_role)
    db.session.commit()
    return user_role


def create_default_roles(org_id: int):
    """Create standard roles for a specific organization if they don't exist."""
    roles = [
        ("admin", "Full system access"),
        ("developer", "Full system access with role assignment for development/testing"),
        ("manager", "Store management and approvals"),
        ("cashier", "POS sales only"),
    ]

    for name, desc in roles:
        existing = db.session.query(Role).filter_by(org_id=org_id, name=name).first()
        if not existing:
            role = Role(org_id=org_id, name=name, description=desc)
            db.session.add(role)

    db.session.commit()

