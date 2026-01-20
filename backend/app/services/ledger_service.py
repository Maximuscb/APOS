# Overview: Service-layer operations for ledger; encapsulates business logic and database work.

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
    event_category: str,
    entity_type: str,
    entity_id: int,
    actor_user_id: int | None = None,
    register_id: int | None = None,
    register_session_id: int | None = None,
    sale_id: int | None = None,
    payment_id: int | None = None,
    return_id: int | None = None,
    transfer_id: int | None = None,
    count_id: int | None = None,
    cash_drawer_event_id: int | None = None,
    occurred_at: Optional[datetime] = None,
    note: Optional[str] = None,
    payload: Optional[str] = None,
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
        event_category=event_category,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_user_id=actor_user_id,
        register_id=register_id,
        register_session_id=register_session_id,
        sale_id=sale_id,
        payment_id=payment_id,
        return_id=return_id,
        transfer_id=transfer_id,
        count_id=count_id,
        cash_drawer_event_id=cash_drawer_event_id,
        occurred_at=occurred_at,  # if None, db default applies
        note=note,
        payload=payload,
    )
    db.session.add(ev)
    db.session.flush()  # ensures ev.id is assigned without committing
    return ev
