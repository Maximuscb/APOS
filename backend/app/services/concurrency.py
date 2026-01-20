# Overview: Service-layer operations for concurrency; encapsulates business logic and database work.

from __future__ import annotations

import time

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm.exc import StaleDataError

from ..extensions import db


def lock_for_update(query):
    """
    Apply row-level locking for critical operations.

    NOTE: SQLite ignores SELECT ... FOR UPDATE, but other DBs will honor it.
    """
    return query.with_for_update()


def run_with_retry(func, *, attempts: int = 3, backoff_base: float = 0.1):
    """
    Execute a DB operation with retry on concurrency-related failures.

    Retries on OperationalError (deadlocks, locks) and StaleDataError
    (optimistic locking conflicts).
    """
    last_exc = None
    for attempt in range(attempts):
        try:
            return func()
        except (OperationalError, StaleDataError) as exc:
            db.session.rollback()
            last_exc = exc
            if attempt >= attempts - 1:
                raise
            time.sleep(backoff_base * (2 ** attempt))
    if last_exc:
        raise last_exc


def commit_with_retry(*, attempts: int = 3, backoff_base: float = 0.1):
    """Commit current session with retry handling."""
    def _op():
        db.session.commit()
    return run_with_retry(_op, attempts=attempts, backoff_base=backoff_base)
