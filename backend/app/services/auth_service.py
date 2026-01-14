"""
Phase 4: Authentication Service

WHY: Every action must be attributable. Stub implementation for now -
production would use bcrypt, sessions, JWT, etc.
"""

from ..extensions import db
from ..models import User, Role, UserRole
from app.time_utils import utcnow


def create_user(username: str, email: str, password: str, store_id: int | None = None) -> User:
    """
    Create new user. Password hashing stubbed for now.

    SECURITY NOTE: Production must use bcrypt.hashpw()
    """
    existing = db.session.query(User).filter(
        db.or_(User.username == username, User.email == email)
    ).first()

    if existing:
        raise ValueError("Username or email already exists")

    # STUB: In production, use bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    password_hash = f"STUB_HASH_{password}"

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
    Authenticate user. Stub implementation.

    SECURITY NOTE: Production must use bcrypt.checkpw()
    """
    user = db.session.query(User).filter_by(username=username, is_active=True).first()

    if not user:
        return None

    # STUB: In production, use bcrypt.checkpw(password.encode(), user.password_hash.encode())
    if user.password_hash == f"STUB_HASH_{password}":
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
        ("manager", "Store management and approvals"),
        ("cashier", "POS sales only"),
    ]

    for name, desc in roles:
        existing = db.session.query(Role).filter_by(name=name).first()
        if not existing:
            role = Role(name=name, description=desc)
            db.session.add(role)

    db.session.commit()
