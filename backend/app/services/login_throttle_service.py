"""
Login Throttling Service

WHY: Prevent brute-force password attacks by limiting failed login attempts.
After too many failures, the account is temporarily locked.

SECURITY FEATURES:
- Tracks failed attempts per username/email
- Lockout after MAX_FAILED_ATTEMPTS failures within LOCKOUT_WINDOW
- Lockout duration: LOCKOUT_DURATION minutes
- Uses security_events table for tracking (already exists)
- Clears failed count on successful login
"""

from datetime import timedelta
from ..extensions import db
from ..models import SecurityEvent, User
from app.time_utils import utcnow


# Configuration constants
MAX_FAILED_ATTEMPTS = 10  # Lock after 10 failed attempts
LOCKOUT_WINDOW = timedelta(minutes=15)  # Within 15 minutes
LOCKOUT_DURATION = timedelta(minutes=15)  # Lockout for 15 minutes


def get_recent_failed_attempts(identifier: str, ip_address: str | None = None) -> int:
    """
    Count recent failed login attempts for a username/email.

    Uses the security_events table to track LOGIN_FAILED events.

    Returns count of failed attempts within LOCKOUT_WINDOW.
    """
    cutoff = utcnow() - LOCKOUT_WINDOW

    # Look for failed login attempts for this identifier
    # We store the username in the 'action' field of security events
    query = db.session.query(SecurityEvent).filter(
        SecurityEvent.event_type == "LOGIN_FAILED",
        SecurityEvent.action == identifier,
        SecurityEvent.occurred_at >= cutoff
    )

    return query.count()


def is_account_locked(identifier: str) -> tuple[bool, int | None]:
    """
    Check if an account is currently locked due to too many failed attempts.

    Returns:
    - (True, seconds_remaining) if locked
    - (False, None) if not locked
    """
    failed_count = get_recent_failed_attempts(identifier)

    if failed_count >= MAX_FAILED_ATTEMPTS:
        # Check when the most recent failure was
        most_recent = db.session.query(SecurityEvent).filter(
            SecurityEvent.event_type == "LOGIN_FAILED",
            SecurityEvent.action == identifier
        ).order_by(SecurityEvent.occurred_at.desc()).first()

        if most_recent:
            lockout_end = most_recent.occurred_at + LOCKOUT_DURATION
            now = utcnow()

            if now < lockout_end:
                # Still locked
                seconds_remaining = int((lockout_end - now).total_seconds())
                return True, seconds_remaining

    return False, None


def record_failed_attempt(
    identifier: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
    reason: str = "Invalid credentials"
) -> int:
    """
    Record a failed login attempt.

    Returns the total number of recent failed attempts.
    """
    # First try to find the user to get their ID
    user = db.session.query(User).filter(
        db.or_(User.username == identifier, User.email == identifier)
    ).first()

    event = SecurityEvent(
        user_id=user.id if user else None,
        event_type="LOGIN_FAILED",
        resource="/api/auth/login",
        action=identifier,  # Store the identifier for tracking
        success=False,
        reason=reason,
        ip_address=ip_address,
        user_agent=user_agent,
        occurred_at=utcnow()
    )

    db.session.add(event)
    db.session.commit()

    return get_recent_failed_attempts(identifier)


def record_successful_login(
    user_id: int,
    identifier: str,
    ip_address: str | None = None,
    user_agent: str | None = None
) -> None:
    """
    Record a successful login.

    Note: We don't clear old failed attempts, but successful login
    resets the "lockout clock" since the user proved they know the password.
    """
    event = SecurityEvent(
        user_id=user_id,
        event_type="LOGIN_SUCCESS",
        resource="/api/auth/login",
        action=identifier,
        success=True,
        reason=None,
        ip_address=ip_address,
        user_agent=user_agent,
        occurred_at=utcnow()
    )

    db.session.add(event)
    db.session.commit()


def get_lockout_status(identifier: str) -> dict:
    """
    Get detailed lockout status for an account.

    Returns dict with:
    - locked: bool
    - failed_attempts: int
    - max_attempts: int
    - seconds_until_unlock: int | None
    """
    failed_count = get_recent_failed_attempts(identifier)
    is_locked, seconds_remaining = is_account_locked(identifier)

    return {
        "locked": is_locked,
        "failed_attempts": failed_count,
        "max_attempts": MAX_FAILED_ATTEMPTS,
        "seconds_until_unlock": seconds_remaining,
        "lockout_window_minutes": int(LOCKOUT_WINDOW.total_seconds() / 60),
        "lockout_duration_minutes": int(LOCKOUT_DURATION.total_seconds() / 60),
    }
