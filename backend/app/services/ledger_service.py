from __future__ import annotations

from typing import Optional
from datetime import datetime

from ..extensions import db
from ..models import MasterLedgerEvent
"""
APOS Master Ledger Invariants (authoritative)

- Append-only audit log for cross-cutting domain events.
- No domain/business logic in the master ledger itself.
- Events are written inside the same DB transaction as the domain event they record.
- occurred_at is business time; created_at is system time (DB default).
- As-of filtering in the read API is inclusive: occurred_at <= as_of.
"""


def append_ledger_event(
    *,
    store_id: int,
    event_type: str,
    entity_type: str,
    entity_id: int,
    occurred_at: Optional[datetime] = None,
    note: Optional[str] = None,
) -> MasterLedgerEvent:
    """
    Append-only master ledger event.

    - No domain logic here.
    - No deletes/updates of existing events.
    - occurred_at is business time; created_at is system time (db default).
    """
    ev = MasterLedgerEvent(
        store_id=store_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        occurred_at=occurred_at,  # if None, db default applies
        note=note,
    )
    db.session.add(ev)
    db.session.flush()  # ensures ev.id is assigned without committing
    return ev
