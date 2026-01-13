"""
APOS Phase 4 - Sales & COGS Snapshot Tests
Run: python phase4_sales_tests.py

This script uses your app factory + real DB configured in your backend (SQLite in /instance).
It will:
- create a unique product
- RECEIVE inventory at a known historical time
- SELL inventory at a known historical time
- verify: inventory decrement, WAC snapshot stored on SALE, master ledger event appended
- verify: idempotency (same sale_id + sale_line_id returns same row)
- verify: oversell prevention
- verify: COGS immutability after a backdated RECEIVE that would change WAC as-of sale
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sys
import uuid

# Import app + db + models/services
from app import create_app
from app.extensions import db
from app.models import Product, Store, InventoryTransaction, MasterLedgerEvent
from app.time_utils import utcnow
from app.services.inventory_service import (
    receive_inventory,
    sell_inventory,
    get_inventory_summary,
)


def _dt_utc_naive(dt: datetime) -> datetime:
    """Ensure dt is UTC-naive (tzinfo=None) in your canonical internal format."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.replace(tzinfo=None)


def _print(title: str):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def main() -> int:
    app = create_app()

    with app.app_context():
        _print("SETUP: Ensure a store exists")
        store = db.session.query(Store).order_by(Store.id.asc()).first()
        if store is None:
            store = Store(name="Default Store")
            db.session.add(store)
            db.session.commit()
            print(f"Created Store id={store.id}")
        else:
            print(f"Using existing Store id={store.id}")

        store_id = store.id

        _print("SETUP: Create a unique active product")
        token = uuid.uuid4().hex[:8].upper()
        sku = f"SALE-TEST-{token}"
        p = Product(store_id=store_id, sku=sku, name=f"Sale Test Product {token}", is_active=True)
        db.session.add(p)
        db.session.commit()
        product_id = p.id
        print(f"Created Product id={product_id} sku={sku}")

        # Choose deterministic historical times (avoid future-dating issues)
        # sale_time is yesterday; initial receive is 2 days before sale; backdated receive is 30 days before sale
        sale_time = _dt_utc_naive(utcnow() - timedelta(days=1))
        receive_time = _dt_utc_naive(sale_time - timedelta(days=2))
        backdated_receive_time = _dt_utc_naive(sale_time - timedelta(days=30))

        _print("TEST 1: RECEIVE inventory @ $1.00 (100 cents) at receive_time")
        tx_recv = receive_inventory(
            store_id=store_id,
            product_id=product_id,
            quantity=10,
            unit_cost_cents=100,
            occurred_at=receive_time,
            note="phase4 test receive 10 @ 1.00",
        )
        print(f"RECEIVE tx id={tx_recv.id} occurred_at={tx_recv.occurred_at} qty_delta={tx_recv.quantity_delta} unit_cost_cents={tx_recv.unit_cost_cents}")

        summary_after_receive = get_inventory_summary(store_id=store_id, product_id=product_id, as_of=sale_time)
        print("Summary as-of sale_time after RECEIVE:", summary_after_receive)
        assert summary_after_receive["quantity_on_hand"] == 10, "Expected on-hand 10 after initial receive"
        assert summary_after_receive["weighted_average_cost_cents"] == 100, "Expected WAC=100 after initial receive"

        _print("TEST 2: SELL 2 units at sale_time; verify SALE row + COGS snapshot + master ledger")
        sale_id = f"S-TEST-{token}"
        sale_line_id = "1"

        tx_sale = sell_inventory(
            store_id=store_id,
            product_id=product_id,
            quantity=2,
            sale_id=sale_id,
            sale_line_id=sale_line_id,
            occurred_at=sale_time,
            note="phase4 test sale 2 units",
        )
        print(f"SALE tx id={tx_sale.id} occurred_at={tx_sale.occurred_at} qty_delta={tx_sale.quantity_delta}")
        print(f"  sale_id={tx_sale.sale_id} sale_line_id={tx_sale.sale_line_id}")
        print(f"  unit_cost_cents_at_sale={getattr(tx_sale, 'unit_cost_cents_at_sale', None)} cogs_cents={getattr(tx_sale, 'cogs_cents', None)}")

        assert tx_sale.type == "SALE", "Expected tx type SALE"
        assert tx_sale.quantity_delta == -2, "Expected SALE quantity_delta = -2"
        assert tx_sale.unit_cost_cents is None, "Expected unit_cost_cents to be None for SALE"
        assert tx_sale.unit_cost_cents_at_sale == 100, "Expected unit_cost_cents_at_sale snapshot = 100"
        assert tx_sale.cogs_cents == 200, "Expected cogs_cents = 100*2 = 200"

        # Inventory after sale as-of sale_time should now be 8
        summary_after_sale = get_inventory_summary(store_id=store_id, product_id=product_id, as_of=sale_time)
        print("Summary as-of sale_time after SALE:", summary_after_sale)
        assert summary_after_sale["quantity_on_hand"] == 8, "Expected on-hand 8 after sale"

        # Master ledger must contain SALE_RECORDED referencing this tx id
        ev = (
            db.session.query(MasterLedgerEvent)
            .filter(
                MasterLedgerEvent.store_id == store_id,
                MasterLedgerEvent.event_type == "SALE_RECORDED",
                MasterLedgerEvent.entity_type == "inventory_transaction",
                MasterLedgerEvent.entity_id == tx_sale.id,
            )
            .order_by(MasterLedgerEvent.id.desc())
            .first()
        )
        print("Master ledger SALE_RECORDED event found:", bool(ev))
        assert ev is not None, "Expected MasterLedgerEvent SALE_RECORDED for the sale tx"

        _print("TEST 3: Idempotency - re-post same sale_id + sale_line_id returns same tx")
        tx_sale2 = sell_inventory(
            store_id=store_id,
            product_id=product_id,
            quantity=2,
            sale_id=sale_id,
            sale_line_id=sale_line_id,
            occurred_at=sale_time,
            note="phase4 test sale 2 units (duplicate call)",
        )
        print(f"Second call returned tx id={tx_sale2.id}")
        assert tx_sale2.id == tx_sale.id, "Expected idempotent call to return the same tx id"

        # Ensure on-hand didn't decrement twice
        summary_after_idem = get_inventory_summary(store_id=store_id, product_id=product_id, as_of=sale_time)
        print("Summary as-of sale_time after idempotent call:", summary_after_idem)
        assert summary_after_idem["quantity_on_hand"] == 8, "Expected on-hand unchanged after idempotent sale call"

        _print("TEST 4: Oversell prevention - attempt to sell 999 should fail")
        try:
            sell_inventory(
                store_id=store_id,
                product_id=product_id,
                quantity=999,
                sale_id=f"{sale_id}-OVR",
                sale_line_id="1",
                occurred_at=sale_time,
                note="phase4 oversell attempt",
            )
            raise AssertionError("Expected oversell to raise ValueError, but it succeeded")
        except ValueError as e:
            print("Oversell raised ValueError as expected:", str(e))

        _print("TEST 5: COGS immutability - backdated RECEIVE @ $10.00 before sale should NOT mutate prior SALE snapshot")
        # This backdated receive would change WAC as-of sale if WAC were recomputed historically,
        # but because we snapshot at sale time, the existing sale row must not change.
        tx_back = receive_inventory(
            store_id=store_id,
            product_id=product_id,
            quantity=10,
            unit_cost_cents=1000,
            occurred_at=backdated_receive_time,
            note="phase4 test backdated receive 10 @ 10.00",
        )
        print(f"Backdated RECEIVE tx id={tx_back.id} occurred_at={tx_back.occurred_at} unit_cost_cents={tx_back.unit_cost_cents}")

        # Reload sale from DB to verify immutable fields
        sale_reloaded = db.session.query(InventoryTransaction).filter_by(id=tx_sale.id).one()
        print(f"Reloaded SALE tx id={sale_reloaded.id}")
        print(f"  unit_cost_cents_at_sale={sale_reloaded.unit_cost_cents_at_sale} cogs_cents={sale_reloaded.cogs_cents}")

        assert sale_reloaded.unit_cost_cents_at_sale == 100, "SALE unit_cost_cents_at_sale must remain unchanged"
        assert sale_reloaded.cogs_cents == 200, "SALE cogs_cents must remain unchanged"

        # Show what WAC as-of sale_time is now (it may differ; that is allowed)
        summary_after_backdate = get_inventory_summary(store_id=store_id, product_id=product_id, as_of=sale_time)
        print("Summary as-of sale_time after backdated RECEIVE:", summary_after_backdate)
        print("NOTE: weighted_average_cost_cents may change historically; SALE snapshot must not.")

        _print("ALL TESTS PASSED")
        return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print("\nTEST RUN FAILED:", repr(e))
        sys.exit(1)
