"""
Phase 6: Production-Ready Authentication Service

WHY: Every action must be attributable. Uses bcrypt for secure password
hashing and validates password strength.

SECURITY NOTES:
- Passwords hashed with bcrypt (cost factor 12)
- Minimum 8 characters required
- Must contain uppercase, lowercase, digit, and special char
- Session tokens managed separately (see session_service.py)
"""

import bcrypt
import re
from ..extensions import db
from ..models import User, Role, UserRole
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


def create_user(username: str, email: str, password: str, store_id: int | None = None) -> User:
    """
    Create new user with bcrypt password hashing.

    Password must meet strength requirements or PasswordValidationError will be raised.
    Username and email must be unique or ValueError will be raised.

    WHY: User creation is the entry point for authentication.
    Must enforce password strength at creation time.
    """
    existing = db.session.query(User).filter(
        db.or_(User.username == username, User.email == email)
    ).first()

    if existing:
        raise ValueError("Username or email already exists")

    # Hash password with bcrypt (validates strength automatically)
    password_hash = hash_password(password)

    user = User(
        username=username,
        email=email,
        password_hash=password_hash,
        store_id=store_id
    )

    db.session.add(user)
    db.session.commit()
    return user


def authenticate(username: str, password: str) -> User | None:
    """
    Authenticate user with username and password.

    Returns User if credentials valid, None otherwise.
    Updates last_login_at timestamp on successful authentication.

    WHY: Central authentication function. All login flows go through here.
    Uses timing-safe comparison via bcrypt.
    """
    user = (
        db.session.query(User)
        .filter(
            db.or_(User.username == username, User.email == username),
            User.is_active.is_(True),
        )
        .first()
    )

    if not user:
        return None

    # Verify password (supports both bcrypt and legacy stub hashes)
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


def create_default_roles():
    """Create standard roles if they don't exist."""
    roles = [
        ("admin", "Full system access"),
        ("developer", "Full system access with role assignment for development/testing"),
        ("manager", "Store management and approvals"),
        ("cashier", "POS sales only"),
    ]

    for name, desc in roles:
        existing = db.session.query(Role).filter_by(name=name).first()
        if not existing:
            role = Role(name=name, description=desc)
            db.session.add(role)

    db.session.commit()
