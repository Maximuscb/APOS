# Overview: Service-layer operations for session; encapsulates business logic and database work.

"""
Session Token Management Service with Multi-Tenant Support

WHY: Secure session management with automatic timeout and revocation.
Tokens are cryptographically secure, hashed in database, and time-limited.

MULTI-TENANT: Sessions capture org_id and store_id at creation time.
This establishes the tenant context for every authenticated request
without repeated database lookups.

SECURITY FEATURES:
- Cryptographically secure random tokens (32 bytes)
- Tokens hashed with SHA-256 before storage (fast, one-way)
- 24-hour absolute timeout (SESSION_ABSOLUTE_TIMEOUT)
- 2-hour idle timeout (SESSION_IDLE_TIMEOUT)
- Revocable on logout or security events
- Tracks client IP and user agent for security monitoring
- Tenant context (org_id) is immutable for the session lifetime
"""

import secrets
import hashlib
from dataclasses import dataclass
from datetime import timedelta
from ..extensions import db
from ..models import SessionToken, User, Organization
from app.time_utils import utcnow


# Configuration constants
SESSION_ABSOLUTE_TIMEOUT = timedelta(hours=24)  # Maximum session length
SESSION_IDLE_TIMEOUT = timedelta(hours=2)        # Activity timeout


@dataclass
class SessionContext:
    """
    Complete session context returned by validate_session.

    MULTI-TENANT: Contains both user identity and tenant context.
    All fields are set from the immutable session record.
    """
    user: User
    session: SessionToken
    org_id: int
    store_id: int | None  # May be None for org-level users


def generate_token() -> str:
    """
    Generate cryptographically secure random token.

    Returns 64-character hex string (32 bytes of entropy).
    This is the plaintext token sent to client (never stored).

    WHY secrets.token_hex: Cryptographically secure PRNG.
    DO NOT use random.random() or uuid4() for auth tokens!
    """
    return secrets.token_hex(32)  # 32 bytes = 64 hex characters


def hash_token(token: str) -> str:
    """
    Hash token for database storage using SHA-256.

    WHY SHA-256 not bcrypt: Tokens are already high-entropy (unlike passwords).
    SHA-256 is faster and sufficient for high-entropy inputs.

    Returns hex-encoded hash string.
    """
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def create_session(
    user_id: int,
    user_agent: str | None = None,
    ip_address: str | None = None
) -> tuple[SessionToken, str]:
    """
    Create new session token for user with tenant context.

    MULTI-TENANT: Captures org_id and store_id from the user at session
    creation time. This context is immutable for the session lifetime.

    Returns (session_record, plaintext_token).
    Client receives plaintext_token, database stores only the hash.

    Raises ValueError if user has no org_id (tenant context required).
    """
    # Get user to capture tenant context
    user = db.session.query(User).filter_by(id=user_id).first()
    if not user:
        raise ValueError("User not found")

    # MULTI-TENANT: Require org_id for all sessions
    if not user.org_id:
        raise ValueError("User must belong to an organization")

    # Verify organization is active
    org = db.session.query(Organization).filter_by(id=user.org_id).first()
    if not org or not org.is_active:
        raise ValueError("Organization is not active")

    plaintext_token = generate_token()
    token_hash = hash_token(plaintext_token)

    now = utcnow()
    expires_at = now + SESSION_ABSOLUTE_TIMEOUT

    session = SessionToken(
        user_id=user_id,
        org_id=user.org_id,  # MULTI-TENANT: Capture tenant context
        store_id=user.store_id,  # May be None for org-level users
        token_hash=token_hash,
        created_at=now,
        last_used_at=now,
        expires_at=expires_at,
        user_agent=user_agent,
        ip_address=ip_address,
        is_revoked=False
    )

    db.session.add(session)
    db.session.commit()

    return session, plaintext_token


def validate_session(token: str) -> SessionContext | None:
    """
    Validate session token and return SessionContext if valid.

    MULTI-TENANT: Returns SessionContext with user, org_id, and store_id.
    The tenant context is taken from the session record, not the user,
    ensuring immutability even if user's org changes after login.

    Returns None if:
    - Token is invalid, expired, or revoked
    - User account is deactivated (is_active=False)
    - Organization is deactivated (is_active=False)

    Updates last_used_at on successful validation (activity tracking).

    WHY: Central validation point. All protected routes call this.
    """
    token_hash = hash_token(token)
    now = utcnow()

    # Find session by token hash
    session = db.session.query(SessionToken).filter_by(
        token_hash=token_hash,
        is_revoked=False
    ).first()

    if not session:
        return None

    # Check absolute timeout
    if session.expires_at < now:
        return None

    # Check idle timeout
    idle_time = now - session.last_used_at
    if idle_time > SESSION_IDLE_TIMEOUT:
        # Auto-revoke idle sessions
        session.is_revoked = True
        session.revoked_at = now
        session.revoked_reason = "Idle timeout"
        db.session.commit()
        return None

    # Get the associated user
    user = session.user

    # SECURITY: Check if user account is active
    if not user or not user.is_active:
        session.is_revoked = True
        session.revoked_at = now
        session.revoked_reason = "User account deactivated"
        db.session.commit()
        return None

    # MULTI-TENANT: Check if organization is still active
    org = session.organization
    if not org or not org.is_active:
        session.is_revoked = True
        session.revoked_at = now
        session.revoked_reason = "Organization deactivated"
        db.session.commit()
        return None

    # Valid session - update activity timestamp
    session.last_used_at = now
    db.session.commit()

    # Return full context with tenant information
    return SessionContext(
        user=user,
        session=session,
        org_id=session.org_id,
        store_id=session.store_id
    )


def revoke_session(token: str, reason: str = "User logout") -> bool:
    """
    Revoke session token.

    Returns True if session was revoked, False if not found.

    WHY explicit revocation: Allows immediate logout and security response.
    Revoked sessions cannot be used even if not expired.
    """
    token_hash = hash_token(token)

    session = db.session.query(SessionToken).filter_by(
        token_hash=token_hash,
        is_revoked=False
    ).first()

    if not session:
        return False

    session.is_revoked = True
    session.revoked_at = utcnow()
    session.revoked_reason = reason

    db.session.commit()
    return True


def revoke_all_user_sessions(user_id: int, reason: str = "Revoke all sessions") -> int:
    """
    Revoke all active sessions for a user.

    Returns count of sessions revoked.

    WHY: Security response (password change, account compromise, etc.)
    Forces re-authentication on all devices.
    """
    now = utcnow()

    sessions = db.session.query(SessionToken).filter_by(
        user_id=user_id,
        is_revoked=False
    ).all()

    count = 0
    for session in sessions:
        session.is_revoked = True
        session.revoked_at = now
        session.revoked_reason = reason
        count += 1

    db.session.commit()
    return count


def cleanup_expired_sessions() -> int:
    """
    Delete expired and revoked sessions older than 30 days.

    Returns count of sessions deleted.

    WHY: Database cleanup. Expired sessions accumulate over time.
    Run this periodically (daily cron job recommended).
    """
    cutoff = utcnow() - timedelta(days=30)

    # Delete sessions that are both old AND (expired OR revoked)
    deleted = db.session.query(SessionToken).filter(
        db.or_(
            SessionToken.expires_at < utcnow(),
            SessionToken.is_revoked == True
        ),
        SessionToken.created_at < cutoff
    ).delete()

    db.session.commit()
    return deleted
