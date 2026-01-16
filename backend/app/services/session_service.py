"""
Phase 6: Session Token Management Service

WHY: Secure session management with automatic timeout and revocation.
Tokens are cryptographically secure, hashed in database, and time-limited.

SECURITY FEATURES:
- Cryptographically secure random tokens (32 bytes)
- Tokens hashed with SHA-256 before storage (fast, one-way)
- 24-hour absolute timeout (SESSION_ABSOLUTE_TIMEOUT)
- 2-hour idle timeout (SESSION_IDLE_TIMEOUT)
- Revocable on logout or security events
- Tracks client IP and user agent for security monitoring
"""

import secrets
import hashlib
from datetime import timedelta
from ..extensions import db
from ..models import SessionToken, User
from app.time_utils import utcnow


# Configuration constants
SESSION_ABSOLUTE_TIMEOUT = timedelta(hours=24)  # Maximum session length
SESSION_IDLE_TIMEOUT = timedelta(hours=2)        # Activity timeout


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
    Create new session token for user.

    Returns (session_record, plaintext_token).
    Client receives plaintext_token, database stores only the hash.

    WHY return tuple: Plaintext token needed for client, but never stored.
    Once this function returns, plaintext cannot be recovered.
    """
    plaintext_token = generate_token()
    token_hash = hash_token(plaintext_token)

    now = utcnow()
    expires_at = now + SESSION_ABSOLUTE_TIMEOUT

    session = SessionToken(
        user_id=user_id,
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


def validate_session(token: str) -> User | None:
    """
    Validate session token and return User if valid.

    Returns None if:
    - Token is invalid, expired, or revoked
    - User account is deactivated (is_active=False)

    Updates last_used_at on successful validation (activity tracking).

    WHY: Central validation point. All protected routes call this.

    SECURITY: Also checks user.is_active to ensure deactivated users
    cannot continue using existing sessions.
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
    # Deactivated users should not be able to use existing sessions
    if not user or not user.is_active:
        # Auto-revoke session for deactivated user
        session.is_revoked = True
        session.revoked_at = now
        session.revoked_reason = "User account deactivated"
        db.session.commit()
        return None

    # Valid session - update activity timestamp
    session.last_used_at = now
    db.session.commit()

    return user


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
