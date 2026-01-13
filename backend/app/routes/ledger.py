from flask import Blueprint, request

from ..models import MasterLedgerEvent
from app.time_utils import parse_iso_datetime

"""
Time semantics:
- API accepts ISO-8601 datetimes with Z/offsets; backend normalizes to UTC-naive internally.
- as_of filtering is inclusive: occurred_at <= as_of.
"""

ledger_bp = Blueprint("ledger", __name__, url_prefix="/api/ledger")


@ledger_bp.get("")
def list_ledger_events_route():
    store_id = request.args.get("store_id", type=int)
    if store_id is None:
        return {"error": "store_id is required"}, 400

    limit = request.args.get("limit", default=100, type=int)
    limit = max(1, min(limit, 500))

    as_of_raw = request.args.get("as_of")
    try:
        as_of_dt = parse_iso_datetime(as_of_raw)
    except Exception:
        return {"error": "as_of must be an ISO-8601 datetime"}, 400

    q = MasterLedgerEvent.query.filter(MasterLedgerEvent.store_id == store_id)

    if as_of_dt is not None:
        q = q.filter(MasterLedgerEvent.occurred_at <= as_of_dt)

    rows = (
        q.order_by(MasterLedgerEvent.occurred_at.desc(), MasterLedgerEvent.id.desc())
        .limit(limit)
        .all()
    )

    return [r.to_dict() for r in rows], 200
