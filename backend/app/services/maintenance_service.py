# Overview: Service-layer operations for maintenance; encapsulates business logic and database work.

from __future__ import annotations

from datetime import timedelta

from ..extensions import db
from ..models import SecurityEvent
from app.time_utils import utcnow


def cleanup_security_events(*, retention_days: int = 90) -> int:
    """
    Delete security events older than retention_days.

    Master ledger events are preserved for compliance.
    """
    cutoff = utcnow() - timedelta(days=retention_days)
    deleted = db.session.query(SecurityEvent).filter(
        SecurityEvent.occurred_at < cutoff
    ).delete()
    db.session.commit()
    return deleted
