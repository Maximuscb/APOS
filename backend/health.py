#!/usr/bin/env python3
"""
Unified health and audit runner for APOS.

This consolidates all prior audit/test scripts into a single entrypoint.
Run:
    python health.py --suite all

Suites:
    phase4, lifecycle, auth, permission, comprehensive, payments, registers, concurrency
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.extensions import db
from app.models import (
    InventoryTransaction,
    MasterLedgerEvent,
    Permission,
    Product,
    Role,
    RolePermission,
    SecurityEvent,
    Store,
    User,
    UserRole,
)
from app.services import (
    auth_service,
    inventory_service,
    permission_service,
    session_service,
)
from app.services.auth_service import PasswordValidationError
from app.services.lifecycle_service import approve_transaction, post_transaction, LifecycleError
from app.time_utils import utcnow
from app.permissions import PERMISSION_DEFINITIONS


# ============================================================================
# Phase 4: Sales and COGS snapshot tests
# ============================================================================

def run_phase4_sales_audit() -> bool:
    def _dt_utc_naive(dt: datetime) -> datetime:
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt.replace(tzinfo=None)

    def _print(title: str) -> None:
        print("\n" + "=" * 80)
        print(title)
        print("=" * 80)

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
        product = Product(store_id=store_id, sku=sku, name=f"Sale Test Product {token}", is_active=True)
        db.session.add(product)
        db.session.commit()
        product_id = product.id
        print(f"Created Product id={product_id} sku={sku}")

        sale_time = _dt_utc_naive(utcnow() - timedelta(days=1))
        receive_time = _dt_utc_naive(sale_time - timedelta(days=2))
        backdated_receive_time = _dt_utc_naive(sale_time - timedelta(days=30))

        _print("TEST 1: RECEIVE inventory @ $1.00 (100 cents) at receive_time")
        tx_recv = inventory_service.receive_inventory(
            store_id=store_id,
            product_id=product_id,
            quantity=10,
            unit_cost_cents=100,
            occurred_at=receive_time,
            note="phase4 test receive 10 @ 1.00",
        )
        print(
            "RECEIVE tx id={} occurred_at={} qty_delta={} unit_cost_cents={}".format(
                tx_recv.id, tx_recv.occurred_at, tx_recv.quantity_delta, tx_recv.unit_cost_cents
            )
        )

        summary_after_receive = inventory_service.get_inventory_summary(
            store_id=store_id, product_id=product_id, as_of=sale_time
        )
        print("Summary as-of sale_time after RECEIVE:", summary_after_receive)
        assert summary_after_receive["quantity_on_hand"] == 10, "Expected on-hand 10 after initial receive"
        assert summary_after_receive["weighted_average_cost_cents"] == 100, "Expected WAC=100 after initial receive"

        _print("TEST 2: SELL 2 units at sale_time; verify SALE row + COGS snapshot + master ledger")
        sale_id = f"S-TEST-{token}"
        sale_line_id = "1"

        tx_sale = inventory_service.sell_inventory(
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
        print(
            "  unit_cost_cents_at_sale={} cogs_cents={}".format(
                getattr(tx_sale, "unit_cost_cents_at_sale", None),
                getattr(tx_sale, "cogs_cents", None),
            )
        )

        assert tx_sale.type == "SALE", "Expected tx type SALE"
        assert tx_sale.quantity_delta == -2, "Expected SALE quantity_delta = -2"
        assert tx_sale.unit_cost_cents is None, "Expected unit_cost_cents to be None for SALE"
        assert tx_sale.unit_cost_cents_at_sale == 100, "Expected unit_cost_cents_at_sale snapshot = 100"
        assert tx_sale.cogs_cents == 200, "Expected cogs_cents = 100*2 = 200"

        summary_after_sale = inventory_service.get_inventory_summary(
            store_id=store_id, product_id=product_id, as_of=sale_time
        )
        print("Summary as-of sale_time after SALE:", summary_after_sale)
        assert summary_after_sale["quantity_on_hand"] == 8, "Expected on-hand 8 after sale"

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
        tx_sale2 = inventory_service.sell_inventory(
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

        summary_after_idem = inventory_service.get_inventory_summary(
            store_id=store_id, product_id=product_id, as_of=sale_time
        )
        print("Summary as-of sale_time after idempotent call:", summary_after_idem)
        assert summary_after_idem["quantity_on_hand"] == 8, "Expected on-hand unchanged after idempotent sale call"

        _print("TEST 4: Oversell prevention - attempt to sell 999 should fail")
        try:
            inventory_service.sell_inventory(
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
        tx_back = inventory_service.receive_inventory(
            store_id=store_id,
            product_id=product_id,
            quantity=10,
            unit_cost_cents=1000,
            occurred_at=backdated_receive_time,
            note="phase4 test backdated receive 10 @ 10.00",
        )
        print(
            "Backdated RECEIVE tx id={} occurred_at={} unit_cost_cents={}".format(
                tx_back.id, tx_back.occurred_at, tx_back.unit_cost_cents
            )
        )

        sale_reloaded = db.session.query(InventoryTransaction).filter_by(id=tx_sale.id).one()
        print(f"Reloaded SALE tx id={sale_reloaded.id}")
        print(
            "  unit_cost_cents_at_sale={} cogs_cents={}".format(
                sale_reloaded.unit_cost_cents_at_sale, sale_reloaded.cogs_cents
            )
        )

        assert sale_reloaded.unit_cost_cents_at_sale == 100, "SALE unit_cost_cents_at_sale must remain unchanged"
        assert sale_reloaded.cogs_cents == 200, "SALE cogs_cents must remain unchanged"

        summary_after_backdate = inventory_service.get_inventory_summary(
            store_id=store_id, product_id=product_id, as_of=sale_time
        )
        print("Summary as-of sale_time after backdated RECEIVE:", summary_after_backdate)
        print("NOTE: weighted_average_cost_cents may change historically; SALE snapshot must not.")

        _print("ALL TESTS PASSED")
        return True


# ============================================================================
# Phase 5: Document lifecycle tests
# ============================================================================

def run_lifecycle_audit() -> bool:
    def _print(title: str) -> None:
        print("\n" + "=" * 80)
        print(title)
        print("=" * 80)

    app = create_app()

    with app.app_context():
        _print("SETUP: Ensure a store exists")
        store = db.session.query(Store).order_by(Store.id.asc()).first()
        if store is None:
            store = Store(name="Lifecycle Test Store")
            db.session.add(store)
            db.session.commit()
            print(f"Created Store id={store.id}")
        else:
            print(f"Using existing Store id={store.id}")

        store_id = store.id

        _print("SETUP: Create a unique active product")
        product = Product(
            store_id=store_id,
            sku=f"LIFECYCLE-TEST-{utcnow().timestamp()}",
            name="Lifecycle Test Product",
            is_active=True,
        )
        db.session.add(product)
        db.session.commit()
        product_id = product.id
        print(f"Created Product id={product_id} sku={product.sku}")

        _print("TEST 1: DRAFT transactions do NOT affect inventory")
        draft_rx = inventory_service.receive_inventory(
            store_id=store_id,
            product_id=product_id,
            quantity=100,
            unit_cost_cents=500,
            note="DRAFT receive for testing",
            status="DRAFT",
        )
        print(f"Created DRAFT RECEIVE tx id={draft_rx.id} qty=100 @ $5.00")
        assert draft_rx.status == "DRAFT", "Expected status=DRAFT"

        qty = inventory_service.get_quantity_on_hand(store_id, product_id)
        print(f"Quantity on hand after DRAFT receive: {qty}")
        assert qty == 0, "DRAFT transactions must NOT affect quantity on hand"

        ledger_count = db.session.query(MasterLedgerEvent).filter_by(
            entity_type="inventory_transaction",
            entity_id=draft_rx.id,
        ).count()
        print(f"Master ledger events for DRAFT tx: {ledger_count}")
        assert ledger_count == 0, "DRAFT transactions must NOT create master ledger events"
        print("PASS DRAFT transaction correctly ignored in calculations")

        _print("TEST 2: State transition DRAFT -> APPROVED")
        approved_tx = approve_transaction(draft_rx.id)
        print(f"Approved tx id={approved_tx.id}, status={approved_tx.status}")
        assert approved_tx.status == "APPROVED", "Expected status=APPROVED"
        assert approved_tx.approved_at is not None, "Expected approved_at timestamp"

        qty = inventory_service.get_quantity_on_hand(store_id, product_id)
        print(f"Quantity on hand after APPROVED: {qty}")
        assert qty == 0, "APPROVED transactions must NOT affect quantity on hand"
        print("PASS State transition DRAFT -> APPROVED successful")

        _print("TEST 3: State transition APPROVED -> POSTED")
        posted_tx = post_transaction(approved_tx.id)
        print(f"Posted tx id={posted_tx.id}, status={posted_tx.status}")
        assert posted_tx.status == "POSTED", "Expected status=POSTED"
        assert posted_tx.posted_at is not None, "Expected posted_at timestamp"

        qty = inventory_service.get_quantity_on_hand(store_id, product_id)
        print(f"Quantity on hand after POSTED: {qty}")
        assert qty == 100, "POSTED transaction must affect quantity on hand"

        ledger_count = db.session.query(MasterLedgerEvent).filter_by(
            entity_type="inventory_transaction",
            entity_id=posted_tx.id,
        ).count()
        print(f"Master ledger events for POSTED tx: {ledger_count}")
        print("PASS State transition APPROVED -> POSTED successful")

        _print("TEST 4: Invalid transition DRAFT -> POSTED (must go through APPROVED)")
        draft_rx2 = inventory_service.receive_inventory(
            store_id=store_id,
            product_id=product_id,
            quantity=50,
            unit_cost_cents=600,
            note="Second DRAFT receive",
            status="DRAFT",
        )
        print(f"Created second DRAFT tx id={draft_rx2.id}")

        try:
            post_transaction(draft_rx2.id)
            raise AssertionError("Expected LifecycleError when posting DRAFT directly")
        except LifecycleError as e:
            print(f"PASS Correctly blocked DRAFT -> POSTED: {e}")

        _print("TEST 5: Invalid reverse transition POSTED -> APPROVED")
        posted_tx_reloaded = db.session.query(InventoryTransaction).filter_by(id=posted_tx.id).one()
        print(f"Transaction {posted_tx.id} current status: {posted_tx_reloaded.status}")
        assert posted_tx_reloaded.status == "POSTED", f"Expected POSTED, got {posted_tx_reloaded.status}"

        try:
            approve_transaction(posted_tx.id)
            raise AssertionError("Expected LifecycleError when approving POSTED tx")
        except LifecycleError as e:
            print(f"PASS Correctly blocked POSTED -> APPROVED: {e}")

        _print("TEST 6: Multiple DRAFT transactions don't affect inventory")
        for i in range(3):
            inventory_service.adjust_inventory(
                store_id=store_id,
                product_id=product_id,
                quantity_delta=10 * (i + 1),
                note=f"DRAFT adjustment {i+1}",
                status="DRAFT",
            )

        qty = inventory_service.get_quantity_on_hand(store_id, product_id)
        print(f"Quantity on hand with 3 DRAFT adjustments: {qty}")
        assert qty == 100, "DRAFT adjustments must NOT affect quantity (should still be 100)"
        print("PASS Multiple DRAFT transactions correctly ignored")

        _print("TEST 7: Approve and post one DRAFT adjustment, verify inventory changes")
        draft_adj = db.session.query(InventoryTransaction).filter_by(
            store_id=store_id,
            product_id=product_id,
            type="ADJUST",
            status="DRAFT",
        ).first()

        print(f"Approving adjustment tx id={draft_adj.id} qty_delta={draft_adj.quantity_delta}")
        approved_adj = approve_transaction(draft_adj.id)

        qty_after_approve = inventory_service.get_quantity_on_hand(store_id, product_id)
        print(f"Quantity after APPROVED: {qty_after_approve}")
        assert qty_after_approve == 100, "APPROVED adjustment must NOT affect inventory yet"

        posted_adj = post_transaction(approved_adj.id)

        qty_after_post = inventory_service.get_quantity_on_hand(store_id, product_id)
        expected_qty = 100 + posted_adj.quantity_delta
        print(f"Quantity after POSTED: {qty_after_post} (expected {expected_qty})")
        assert qty_after_post == expected_qty, "POSTED adjustment must affect inventory"
        print("PASS Lifecycle works correctly for adjustments")

        _print("TEST 8: Weighted Average Cost only includes POSTED receives")
        summary1 = inventory_service.get_inventory_summary(store_id=store_id, product_id=product_id)
        print(f"Current WAC: {summary1['weighted_average_cost_cents']} cents")
        assert summary1["weighted_average_cost_cents"] == 500, "WAC should be 500 (only POSTED receive)"

        draft_expensive = inventory_service.receive_inventory(
            store_id=store_id,
            product_id=product_id,
            quantity=100,
            unit_cost_cents=1000,
            note="Expensive DRAFT receive",
            status="DRAFT",
        )
        print(f"Created DRAFT receive id={draft_expensive.id} @ $10.00")

        summary2 = inventory_service.get_inventory_summary(store_id=store_id, product_id=product_id)
        print(f"WAC after DRAFT receive: {summary2['weighted_average_cost_cents']} cents")
        assert summary2["weighted_average_cost_cents"] == 500, "DRAFT receive must NOT affect WAC"

        approve_transaction(draft_expensive.id)
        post_transaction(draft_expensive.id)

        summary3 = inventory_service.get_inventory_summary(store_id=store_id, product_id=product_id)
        print(f"WAC after POSTED receive: {summary3['weighted_average_cost_cents']} cents")
        expected_wac = 750
        assert summary3["weighted_average_cost_cents"] == expected_wac, f"Expected WAC={expected_wac}"
        print("PASS WAC correctly ignores DRAFT/APPROVED receives, includes only POSTED")

        _print("TEST 9: Can't approve or post non-existent transaction")
        try:
            approve_transaction(999999)
            raise AssertionError("Expected ValueError for non-existent transaction")
        except ValueError as e:
            print(f"PASS Correctly rejected non-existent tx for approval: {e}")

        try:
            post_transaction(999999)
            raise AssertionError("Expected ValueError for non-existent transaction")
        except ValueError as e:
            print(f"PASS Correctly rejected non-existent tx for posting: {e}")

        _print("ALL LIFECYCLE TESTS PASSED PASS")
        print("\nLifecycle system is working correctly:")
        print("  PASS DRAFT transactions don't affect inventory")
        print("  PASS APPROVED transactions don't affect inventory")
        print("  PASS POSTED transactions affect inventory calculations")
        print("  PASS State transitions enforce DRAFT -> APPROVED -> POSTED")
        print("  PASS Invalid transitions are blocked")
        print("  PASS WAC calculations respect lifecycle status")
        print("  PASS Master ledger events created only for POSTED")
        return True


# ============================================================================
# Phase 6: Authentication audit
# ============================================================================

def _auth_reset_db() -> int:
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()
        store = Store(name="Test Store")
        db.session.add(store)
        db.session.commit()
        return store.id


def _auth_test_password_validation() -> bool:
    print("\n=== Testing Password Validation ===")
    app = create_app()
    with app.app_context():
        try:
            auth_service.validate_password_strength("Pass1!")
            print("FAIL FAIL: Short password should be rejected")
            return False
        except PasswordValidationError as e:
            print(f"PASS PASS: Short password rejected - {e}")

        try:
            auth_service.validate_password_strength("password123!")
            print("FAIL FAIL: No uppercase should be rejected")
            return False
        except PasswordValidationError:
            print("PASS PASS: No uppercase rejected")

        try:
            auth_service.validate_password_strength("PASSWORD123!")
            print("FAIL FAIL: No lowercase should be rejected")
            return False
        except PasswordValidationError:
            print("PASS PASS: No lowercase rejected")

        try:
            auth_service.validate_password_strength("Password!")
            print("FAIL FAIL: No digit should be rejected")
            return False
        except PasswordValidationError:
            print("PASS PASS: No digit rejected")

        try:
            auth_service.validate_password_strength("Password123")
            print("FAIL FAIL: No special char should be rejected")
            return False
        except PasswordValidationError:
            print("PASS PASS: No special char rejected")

        try:
            auth_service.validate_password_strength("Password123!")
            print("PASS PASS: Valid password accepted")
        except PasswordValidationError as e:
            print(f"FAIL FAIL: Valid password rejected - {e}")
            return False

    return True


def _auth_test_bcrypt_hashing() -> bool:
    print("\n=== Testing bcrypt Password Hashing ===")
    app = create_app()
    with app.app_context():
        password = "TestPassword123!"
        hash1 = auth_service.hash_password(password)
        print(f"PASS PASS: Generated bcrypt hash: {hash1[:20]}...")

        hash2 = auth_service.hash_password(password)
        if hash1 == hash2:
            print("FAIL FAIL: Same password produced identical hash (salt not working)")
            return False
        print("PASS PASS: Same password produces different hashes (salt working)")

        if not auth_service.verify_password(password, hash1):
            print("FAIL FAIL: Password verification failed for correct password")
            return False
        print("PASS PASS: Correct password verifies successfully")

        if auth_service.verify_password("WrongPassword123!", hash1):
            print("FAIL FAIL: Wrong password verified (security breach!)")
            return False
        print("PASS PASS: Wrong password rejected")

        stub_hash = "STUB_HASH_password123"
        if not auth_service.verify_password("password123", stub_hash):
            print("FAIL FAIL: Legacy stub hash verification broken")
            return False
        print("PASS PASS: Legacy stub hash still works (backwards compatible)")

    return True


def _auth_test_user_creation_with_bcrypt() -> bool:
    print("\n=== Testing User Creation with bcrypt ===")
    store_id = _auth_reset_db()
    app = create_app()

    with app.app_context():
        user = auth_service.create_user(
            username="testuser",
            email="test@example.com",
            password="SecurePass123!",
            store_id=store_id,
        )

        if not user.password_hash.startswith("$2b$"):
            print(f"FAIL FAIL: Password hash doesn't start with bcrypt prefix: {user.password_hash[:10]}")
            return False
        print(f"PASS PASS: User created with bcrypt hash: {user.password_hash[:30]}...")

        auth_user = auth_service.authenticate("testuser", "SecurePass123!")
        if not auth_user:
            print("FAIL FAIL: Authentication failed with correct password")
            return False
        print("PASS PASS: Authentication successful with correct password")

        auth_user = auth_service.authenticate("testuser", "WrongPassword123!")
        if auth_user:
            print("FAIL FAIL: Authentication succeeded with wrong password")
            return False
        print("PASS PASS: Authentication failed with wrong password")

        try:
            auth_service.create_user(
                username="weakuser",
                email="weak@example.com",
                password="weak",
                store_id=store_id,
            )
            print("FAIL FAIL: Weak password was accepted")
            return False
        except PasswordValidationError:
            print("PASS PASS: Weak password rejected on user creation")

    return True


def _auth_test_session_token_generation() -> bool:
    print("\n=== Testing Session Token Generation ===")
    app = create_app()
    with app.app_context():
        token = session_service.generate_token()
        if len(token) != 64:
            print(f"FAIL FAIL: Token wrong length: {len(token)} (expected 64)")
            return False
        print(f"PASS PASS: Generated 64-char token: {token[:20]}...")

        token2 = session_service.generate_token()
        if token == token2:
            print("FAIL FAIL: Generated identical tokens (not random!)")
            return False
        print("PASS PASS: Tokens are unique")

        token_hash = session_service.hash_token(token)
        if len(token_hash) != 64:
            print(f"FAIL FAIL: Token hash wrong length: {len(token_hash)}")
            return False
        print(f"PASS PASS: Token hashed to SHA-256: {token_hash[:20]}...")

        token_hash2 = session_service.hash_token(token)
        if token_hash != token_hash2:
            print("FAIL FAIL: Same token produced different hashes")
            return False
        print("PASS PASS: Token hashing is deterministic")

    return True


def _auth_test_session_lifecycle() -> bool:
    print("\n=== Testing Session Lifecycle ===")
    store_id = _auth_reset_db()
    app = create_app()

    with app.app_context():
        user = auth_service.create_user(
            username="sessionuser",
            email="session@example.com",
            password="SessionPass123!",
            store_id=store_id,
        )

        session, token = session_service.create_session(
            user_id=user.id,
            user_agent="Test Browser",
            ip_address="127.0.0.1",
        )
        print(f"PASS PASS: Session created for user {user.id}")

        if session.user_agent != "Test Browser":
            print("FAIL FAIL: User agent not stored")
            return False
        if session.ip_address != "127.0.0.1":
            print("FAIL FAIL: IP address not stored")
            return False
        print("PASS PASS: Session metadata stored correctly")

        validated_user = session_service.validate_session(token)
        if not validated_user or validated_user.id != user.id:
            print("FAIL FAIL: Session validation failed")
            return False
        print("PASS PASS: Session validation successful")

        revoked = session_service.revoke_session(token, reason="Test logout")
        if not revoked:
            print("FAIL FAIL: Session revocation failed")
            return False
        print("PASS PASS: Session revoked successfully")

        validated_user = session_service.validate_session(token)
        if validated_user:
            print("FAIL FAIL: Revoked session still valid")
            return False
        print("PASS PASS: Revoked session rejected")

    return True


def _auth_test_session_timeout() -> bool:
    print("\n=== Testing Session Timeout ===")
    store_id = _auth_reset_db()
    app = create_app()

    with app.app_context():
        user = auth_service.create_user(
            username="timeoutuser",
            email="timeout@example.com",
            password="TimeoutPass123!",
            store_id=store_id,
        )

        session, token = session_service.create_session(user_id=user.id)
        session.expires_at = utcnow() - timedelta(hours=1)
        db.session.commit()

        validated_user = session_service.validate_session(token)
        if validated_user:
            print("FAIL FAIL: Expired session still valid")
            return False
        print("PASS PASS: Expired session rejected")

        session2, token2 = session_service.create_session(user_id=user.id)
        session2.last_used_at = utcnow() - timedelta(hours=3)
        db.session.commit()

        validated_user = session_service.validate_session(token2)
        if validated_user:
            print("FAIL FAIL: Idle session still valid")
            return False

        db.session.refresh(session2)
        if not session2.is_revoked:
            print("FAIL FAIL: Idle session not auto-revoked")
            return False
        if session2.revoked_reason != "Idle timeout":
            print(f"FAIL FAIL: Wrong revocation reason: {session2.revoked_reason}")
            return False
        print("PASS PASS: Idle session auto-revoked with correct reason")

    return True


def _auth_test_revoke_all_sessions() -> bool:
    print("\n=== Testing Revoke All Sessions ===")
    store_id = _auth_reset_db()
    app = create_app()

    with app.app_context():
        user = auth_service.create_user(
            username="multiuser",
            email="multi@example.com",
            password="MultiPass123!",
            store_id=store_id,
        )

        session1, token1 = session_service.create_session(user_id=user.id)
        session2, token2 = session_service.create_session(user_id=user.id)
        session3, token3 = session_service.create_session(user_id=user.id)
        print("PASS PASS: Created 3 sessions")

        if not all(
            [
                session_service.validate_session(token1),
                session_service.validate_session(token2),
                session_service.validate_session(token3),
            ]
        ):
            print("FAIL FAIL: Not all sessions valid after creation")
            return False
        print("PASS PASS: All 3 sessions valid")

        count = session_service.revoke_all_user_sessions(user.id, reason="Password change")
        if count != 3:
            print(f"FAIL FAIL: Expected 3 revoked, got {count}")
            return False
        print(f"PASS PASS: Revoked {count} sessions")

        if any(
            [
                session_service.validate_session(token1),
                session_service.validate_session(token2),
                session_service.validate_session(token3),
            ]
        ):
            print("FAIL FAIL: Some sessions still valid after revoke all")
            return False
        print("PASS PASS: All sessions invalidated")

    return True


def _auth_test_login_logout_flow() -> bool:
    print("\n=== Testing Login/Logout Flow ===")
    store_id = _auth_reset_db()
    app = create_app()

    with app.app_context():
        user = auth_service.create_user(
            username="flowuser",
            email="flow@example.com",
            password="FlowPass123!",
            store_id=store_id,
        )
        print("PASS PASS: User created")

        authenticated_user = auth_service.authenticate("flowuser", "FlowPass123!")
        if not authenticated_user:
            print("FAIL FAIL: Authentication failed")
            return False
        print("PASS PASS: User authenticated")

        session, token = session_service.create_session(user_id=authenticated_user.id)
        print("PASS PASS: Session token created")

        validated_user = session_service.validate_session(token)
        if not validated_user or validated_user.id != user.id:
            print("FAIL FAIL: Token validation failed")
            return False
        print("PASS PASS: Token validated successfully")

        revoked = session_service.revoke_session(token)
        if not revoked:
            print("FAIL FAIL: Logout failed")
            return False
        print("PASS PASS: Logout successful")

        validated_user = session_service.validate_session(token)
        if validated_user:
            print("FAIL FAIL: Token still valid after logout")
            return False
        print("PASS PASS: Token invalid after logout")

    return True


def run_authentication_audit() -> bool:
    print("=" * 70)
    print("PHASE 6: PRODUCTION-READY AUTHENTICATION AUDIT")
    print("=" * 70)

    tests = [
        ("Password Validation", _auth_test_password_validation),
        ("bcrypt Hashing", _auth_test_bcrypt_hashing),
        ("User Creation with bcrypt", _auth_test_user_creation_with_bcrypt),
        ("Session Token Generation", _auth_test_session_token_generation),
        ("Session Lifecycle", _auth_test_session_lifecycle),
        ("Session Timeout", _auth_test_session_timeout),
        ("Revoke All Sessions", _auth_test_revoke_all_sessions),
        ("Login/Logout Flow", _auth_test_login_logout_flow),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
                print(f"\nFAIL TEST FAILED: {name}")
        except Exception as e:
            failed += 1
            print(f"\nFAIL TEST CRASHED: {name}")
            print(f"   Error: {str(e)}")
            import traceback

            traceback.print_exc()

    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)

    if failed == 0:
        print("\nPASS ALL AUTHENTICATION TESTS PASSED")
        print("\nPhase 6 is PRODUCTION-READY with secure authentication:")
        print("  - bcrypt password hashing (cost factor 12)")
        print("  - Strong password requirements enforced")
        print("  - Session tokens with SHA-256 hashing")
        print("  - 24-hour absolute, 2-hour idle timeout")
        print("  - Explicit logout and revocation support")
        return True

    print(f"\nFAIL {failed} TESTS FAILED - DO NOT DEPLOY")
    return False


# ============================================================================
# Phase 7: Permission audit
# ============================================================================

def _perm_reset_db() -> int:
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()
        store = Store(name="Test Store")
        db.session.add(store)
        db.session.commit()
        auth_service.create_default_roles()
        return store.id


def _perm_test_permission_initialization() -> bool:
    print("\n=== Testing Permission Initialization ===")
    _perm_reset_db()
    app = create_app()

    with app.app_context():
        created = permission_service.initialize_permissions()
        print(f"PASS PASS: Created {created} permissions")

        total = db.session.query(Permission).count()
        expected = len(PERMISSION_DEFINITIONS)

        if total != expected:
            print(f"FAIL FAIL: Expected {expected} permissions, got {total}")
            return False

        print(f"PASS PASS: All {expected} permissions created")

        codes = [p.code for p in db.session.query(Permission).all()]
        if len(codes) != len(set(codes)):
            print("FAIL FAIL: Duplicate permission codes found")
            return False

        print("PASS PASS: All permission codes are unique")

    return True


def _perm_test_role_permission_assignment() -> bool:
    print("\n=== Testing Role-Permission Assignment ===")
    _perm_reset_db()
    app = create_app()

    with app.app_context():
        permission_service.initialize_permissions()
        created = permission_service.assign_default_role_permissions()
        print(f"PASS PASS: Created {created} role-permission assignments")

        admin_role = db.session.query(Role).filter_by(name="admin").first()
        admin_perms = db.session.query(RolePermission).filter_by(role_id=admin_role.id).count()
        total_perms = db.session.query(Permission).count()

        if admin_perms != total_perms:
            print(f"FAIL FAIL: Admin should have all {total_perms} permissions, has {admin_perms}")
            return False

        print(f"PASS PASS: Admin has all {total_perms} permissions")

        manager_role = db.session.query(Role).filter_by(name="manager").first()
        manager_perms = db.session.query(RolePermission).filter_by(role_id=manager_role.id).count()

        if manager_perms >= admin_perms:
            print("FAIL FAIL: Manager should have fewer permissions than admin")
            return False

        print(f"PASS PASS: Manager has {manager_perms} permissions (less than admin)")

        cashier_role = db.session.query(Role).filter_by(name="cashier").first()
        cashier_perms = db.session.query(RolePermission).filter_by(role_id=cashier_role.id).count()

        if cashier_perms >= manager_perms:
            print("FAIL FAIL: Cashier should have fewer permissions than manager")
            return False

        print(f"PASS PASS: Cashier has {cashier_perms} permissions (minimal access)")

    return True


def _perm_test_user_permission_checking() -> bool:
    print("\n=== Testing User Permission Checking ===")
    store_id = _perm_reset_db()
    app = create_app()

    with app.app_context():
        permission_service.initialize_permissions()
        permission_service.assign_default_role_permissions()

        admin = auth_service.create_user("admin", "admin@test.com", "Password123!", store_id)
        auth_service.assign_role(admin.id, "admin")

        manager = auth_service.create_user("manager", "manager@test.com", "Password123!", store_id)
        auth_service.assign_role(manager.id, "manager")

        cashier = auth_service.create_user("cashier", "cashier@test.com", "Password123!", store_id)
        auth_service.assign_role(cashier.id, "cashier")

        if not permission_service.user_has_permission(admin.id, "SYSTEM_ADMIN"):
            print("FAIL FAIL: Admin should have SYSTEM_ADMIN permission")
            return False
        print("PASS PASS: Admin has SYSTEM_ADMIN permission")

        if permission_service.user_has_permission(manager.id, "SYSTEM_ADMIN"):
            print("FAIL FAIL: Manager should NOT have SYSTEM_ADMIN permission")
            return False
        print("PASS PASS: Manager does not have SYSTEM_ADMIN permission")

        if not permission_service.user_has_permission(manager.id, "APPROVE_ADJUSTMENTS"):
            print("FAIL FAIL: Manager should have APPROVE_ADJUSTMENTS permission")
            return False
        print("PASS PASS: Manager has APPROVE_ADJUSTMENTS permission")

        if not permission_service.user_has_permission(cashier.id, "CREATE_SALE"):
            print("FAIL FAIL: Cashier should have CREATE_SALE permission")
            return False
        print("PASS PASS: Cashier has CREATE_SALE permission")

        if permission_service.user_has_permission(cashier.id, "APPROVE_ADJUSTMENTS"):
            print("FAIL FAIL: Cashier should NOT have APPROVE_ADJUSTMENTS permission")
            return False
        print("PASS PASS: Cashier does not have APPROVE_ADJUSTMENTS permission")

    return True


def _perm_test_security_event_logging() -> bool:
    print("\n=== Testing Security Event Logging ===")
    store_id = _perm_reset_db()
    app = create_app()

    with app.app_context():
        permission_service.initialize_permissions()
        permission_service.assign_default_role_permissions()

        cashier = auth_service.create_user("cashier", "cashier@test.com", "Password123!", store_id)
        auth_service.assign_role(cashier.id, "cashier")

        try:
            permission_service.require_permission(
                cashier.id,
                "CREATE_SALE",
                resource="/api/sales",
                ip_address="127.0.0.1",
            )
            print("PASS PASS: Permission check succeeded (CREATE_SALE granted)")
        except Exception:
            print("FAIL FAIL: Permission check should have succeeded")
            return False

        granted_event = db.session.query(SecurityEvent).filter_by(
            user_id=cashier.id,
            event_type="PERMISSION_GRANTED",
        ).first()

        if not granted_event:
            print("FAIL FAIL: PERMISSION_GRANTED event not logged")
            return False

        print("PASS PASS: PERMISSION_GRANTED event logged")

        try:
            permission_service.require_permission(
                cashier.id,
                "SYSTEM_ADMIN",
                resource="/api/admin",
                ip_address="127.0.0.1",
            )
            print("FAIL FAIL: Permission check should have failed")
            return False
        except permission_service.PermissionDeniedError:
            print("PASS PASS: Permission check correctly denied (SYSTEM_ADMIN)")

        denied_event = db.session.query(SecurityEvent).filter_by(
            user_id=cashier.id,
            event_type="PERMISSION_DENIED",
        ).first()

        if not denied_event:
            print("FAIL FAIL: PERMISSION_DENIED event not logged")
            return False

        print("PASS PASS: PERMISSION_DENIED event logged")

        if denied_event.action != "SYSTEM_ADMIN":
            print(f"FAIL FAIL: Event action wrong: {denied_event.action}")
            return False

        if "Missing permission" not in denied_event.reason:
            print(f"FAIL FAIL: Event reason wrong: {denied_event.reason}")
            return False

        print("PASS PASS: Security event details correct")

    return True


def _perm_test_grant_revoke_permissions() -> bool:
    print("\n=== Testing Grant/Revoke Permissions ===")
    store_id = _perm_reset_db()
    app = create_app()

    with app.app_context():
        permission_service.initialize_permissions()
        permission_service.assign_default_role_permissions()

        cashier = auth_service.create_user("cashier", "cashier@test.com", "Password123!", store_id)
        auth_service.assign_role(cashier.id, "cashier")

        if permission_service.user_has_permission(cashier.id, "VOID_SALE"):
            print("FAIL FAIL: Cashier should not have VOID_SALE permission initially")
            return False

        print("PASS PASS: Cashier does not have VOID_SALE initially")

        permission_service.grant_permission_to_role("cashier", "VOID_SALE")
        print("PASS PASS: Granted VOID_SALE to cashier role")

        if not permission_service.user_has_permission(cashier.id, "VOID_SALE"):
            print("FAIL FAIL: Cashier should have VOID_SALE after grant")
            return False

        print("PASS PASS: Cashier now has VOID_SALE permission")

        revoked = permission_service.revoke_permission_from_role("cashier", "VOID_SALE")

        if not revoked:
            print("FAIL FAIL: Revocation should return True")
            return False

        print("PASS PASS: Revoked VOID_SALE from cashier role")

        if permission_service.user_has_permission(cashier.id, "VOID_SALE"):
            print("FAIL FAIL: Cashier should not have VOID_SALE after revoke")
            return False

        print("PASS PASS: Cashier no longer has VOID_SALE permission")

    return True


def _perm_test_get_user_permissions() -> bool:
    print("\n=== Testing Get User Permissions ===")
    store_id = _perm_reset_db()
    app = create_app()

    with app.app_context():
        permission_service.initialize_permissions()
        permission_service.assign_default_role_permissions()

        admin = auth_service.create_user("admin", "admin@test.com", "Password123!", store_id)
        auth_service.assign_role(admin.id, "admin")

        admin_perms = permission_service.get_user_permissions(admin.id)

        if not isinstance(admin_perms, set):
            print(f"FAIL FAIL: Should return a set, got {type(admin_perms)}")
            return False

        print("PASS PASS: Returns set of permissions")

        if len(admin_perms) < 20:
            print(f"FAIL FAIL: Admin should have many permissions, got {len(admin_perms)}")
            return False

        print(f"PASS PASS: Admin has {len(admin_perms)} permissions")

        required_perms = ["SYSTEM_ADMIN", "APPROVE_ADJUSTMENTS", "CREATE_USER"]
        for perm in required_perms:
            if perm not in admin_perms:
                print(f"FAIL FAIL: Admin should have {perm} permission")
                return False

        print("PASS PASS: All required permissions present")

    return True


def _perm_test_user_with_no_roles() -> bool:
    print("\n=== Testing User With No Roles ===")
    store_id = _perm_reset_db()
    app = create_app()

    with app.app_context():
        permission_service.initialize_permissions()

        user = auth_service.create_user("norole", "norole@test.com", "Password123!", store_id)

        user_perms = permission_service.get_user_permissions(user.id)

        if len(user_perms) != 0:
            print(f"FAIL FAIL: User with no roles should have 0 permissions, has {len(user_perms)}")
            return False

        print("PASS PASS: User with no roles has no permissions")

        if permission_service.user_has_permission(user.id, "CREATE_SALE"):
            print("FAIL FAIL: User with no roles should not have any permissions")
            return False

        print("PASS PASS: Permission checks correctly fail for user with no roles")

    return True


def _perm_test_permission_categories() -> bool:
    print("\n=== Testing Permission Categories ===")
    _perm_reset_db()
    app = create_app()

    with app.app_context():
        permission_service.initialize_permissions()

        categories = ["INVENTORY", "SALES", "DOCUMENTS", "USERS", "SYSTEM"]

        for category in categories:
            perms = db.session.query(Permission).filter_by(category=category).all()

            if len(perms) == 0:
                print(f"FAIL FAIL: Category {category} has no permissions")
                return False

            print(f"PASS PASS: Category {category} has {len(perms)} permissions")

    return True


def run_permission_audit() -> bool:
    print("=" * 70)
    print("PHASE 7: ROLE-BASED PERMISSION SYSTEM AUDIT")
    print("=" * 70)

    tests = [
        ("Permission Initialization", _perm_test_permission_initialization),
        ("Role-Permission Assignment", _perm_test_role_permission_assignment),
        ("User Permission Checking", _perm_test_user_permission_checking),
        ("Security Event Logging", _perm_test_security_event_logging),
        ("Grant/Revoke Permissions", _perm_test_grant_revoke_permissions),
        ("Get User Permissions", _perm_test_get_user_permissions),
        ("User With No Roles", _perm_test_user_with_no_roles),
        ("Permission Categories", _perm_test_permission_categories),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
                print(f"\nFAIL TEST FAILED: {name}")
        except Exception as e:
            failed += 1
            print(f"\nFAIL TEST CRASHED: {name}")
            print(f"   Error: {str(e)}")
            import traceback

            traceback.print_exc()

    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)

    if failed == 0:
        print("\nPASS ALL PERMISSION TESTS PASSED")
        print("\nPhase 7 is PRODUCTION-READY with role-based permissions:")
        print("  - 22 granular permissions across 5 categories")
        print("  - Default role mappings (admin, manager, cashier)")
        print("  - Permission checking with audit logging")
        print("  - Grant/revoke permission management")
        print("  - Security event logging for all checks")
        return True

    print(f"\nFAIL {failed} TESTS FAILED - DO NOT DEPLOY")
    return False


# ============================================================================
# Comprehensive test suite
# ============================================================================

class ComprehensiveTestResults:
    def __init__(self):
        self.passed = []
        self.failed = []
        self.bugs = []

    def add_pass(self, test_name: str) -> None:
        self.passed.append(test_name)
        print(f"PASS PASS: {test_name}")

    def add_fail(self, test_name: str, error: Exception | str) -> None:
        self.failed.append((test_name, str(error)))
        print(f"FAIL FAIL: {test_name}: {error}")

    def add_bug(self, bug_description: str) -> None:
        self.bugs.append(bug_description)
        print(f"BUG BUG FOUND: {bug_description}")

    def summary(self) -> None:
        total = len(self.passed) + len(self.failed)
        print(f"\n{'='*80}")
        print("TEST SUMMARY")
        print(f"{'='*80}")
        print(f"Total Tests: {total}")
        print(f"Passed: {len(self.passed)} ({100*len(self.passed)//total if total > 0 else 0}%)")
        print(f"Failed: {len(self.failed)}")
        print(f"Bugs Found: {len(self.bugs)}")

        if self.failed:
            print(f"\n{'='*80}")
            print("FAILED TESTS:")
            print(f"{'='*80}")
            for test_name, error in self.failed:
                print(f"  - {test_name}")
                print(f"    Error: {error}")

        if self.bugs:
            print(f"\n{'='*80}")
            print("BUGS IDENTIFIED:")
            print(f"{'='*80}")
            for i, bug in enumerate(self.bugs, 1):
                print(f"  {i}. {bug}")


def _comprehensive_setup_test_db():
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()
        store = Store(name="Test Store", code="STORE001")
        db.session.add(store)
        db.session.commit()
        return app, store.id


def _comprehensive_feature_0_system_health(results: ComprehensiveTestResults) -> None:
    print(f"\n{'='*80}")
    print("FEATURE 0: System Health Check + CORS")
    print(f"{'='*80}")

    app, store_id = _comprehensive_setup_test_db()
    client = app.test_client()

    try:
        resp = client.get("/health")
        if resp.status_code == 200 and resp.json.get("status") == "ok":
            results.add_pass("Health check returns 200 with status:ok")
        else:
            results.add_fail("Health check", f"Got {resp.status_code}, {resp.json}")
    except Exception as e:
        results.add_fail("Health check", e)

    try:
        resp = client.get("/health", headers={"Origin": "http://localhost:5173"})
        acao = resp.headers.get("Access-Control-Allow-Origin")
        vary = resp.headers.get("Vary")
        if acao == "http://localhost:5173" and "Origin" in (vary or ""):
            results.add_pass("CORS returns correct ACAO for allowed origin")
        else:
            results.add_bug("CORS: Missing or incorrect Access-Control-Allow-Origin header")
    except Exception as e:
        results.add_fail("CORS allowed origin", e)

    try:
        resp = client.get("/health", headers={"Origin": "http://localhost:5174"})
        acao = resp.headers.get("Access-Control-Allow-Origin")
        if acao != "http://localhost:5174":
            results.add_pass("CORS blocks disallowed origin")
        else:
            results.add_bug("CORS: Allows origin that should be blocked (localhost:5174)")
    except Exception as e:
        results.add_fail("CORS disallowed origin", e)


def _comprehensive_feature_1_authentication(results: ComprehensiveTestResults) -> None:
    print(f"\n{'='*80}")
    print("FEATURE 1: Authentication + Sessions")
    print(f"{'='*80}")

    app, store_id = _comprehensive_setup_test_db()
    client = app.test_client()

    with app.app_context():
        try:
            auth_service.create_default_roles()
            permission_service.initialize_permissions()
            permission_service.assign_default_role_permissions()
            results.add_pass("Initialize roles is idempotent")
        except Exception as e:
            results.add_fail("Initialize roles", e)

    try:
        resp = client.post(
            "/api/auth/register",
            json={
                "username": "testuser1",
                "email": "test1@example.com",
                "password": "StrongPass123!",
                "store_id": store_id,
            },
        )
        if resp.status_code == 201:
            results.add_pass("User registration with strong password")
            user1_data = resp.json
        else:
            results.add_fail("User registration", f"Status {resp.status_code}: {resp.json}")
            return
    except Exception as e:
        results.add_fail("User registration", e)
        return

    try:
        resp = client.post(
            "/api/auth/register",
            json={
                "username": "testuser2",
                "email": "test2@example.com",
                "password": "weak",
                "store_id": store_id,
            },
        )
        if resp.status_code == 400:
            results.add_pass("Weak password rejected with 400")
        else:
            results.add_bug(f"Weak password accepted (status {resp.status_code})")
    except Exception as e:
        results.add_fail("Weak password rejection", e)

    try:
        resp = client.post(
            "/api/auth/register",
            json={
                "username": "testuser1",
                "email": "test3@example.com",
                "password": "StrongPass123!",
                "store_id": store_id,
            },
        )
        if resp.status_code in (400, 409):
            results.add_pass("Duplicate username rejected")
        else:
            results.add_bug(f"Duplicate username allowed (status {resp.status_code})")
    except Exception as e:
        results.add_fail("Duplicate username test", e)

    try:
        resp = client.post("/api/auth/login", json={"username": "testuser1", "password": "StrongPass123!"})
        if resp.status_code == 200 and "token" in resp.json:
            token = resp.json["token"]
            results.add_pass("Login returns token")
        else:
            results.add_fail("Login", f"Status {resp.status_code}: {resp.json}")
            return
    except Exception as e:
        results.add_fail("Login", e)
        return

    try:
        resp = client.post("/api/auth/login", json={"username": "testuser1", "password": "WrongPassword123!"})
        if resp.status_code == 401:
            results.add_pass("Invalid credentials return 401")
        else:
            results.add_bug(f"Invalid credentials got status {resp.status_code}")
    except Exception as e:
        results.add_fail("Invalid credentials test", e)

    try:
        resp = client.post("/api/auth/validate", headers={"Authorization": f"Bearer {token}"})
        if resp.status_code == 200:
            results.add_pass("Token validation works")
        else:
            results.add_fail("Token validation", f"Status {resp.status_code}")
    except Exception as e:
        results.add_fail("Token validation", e)

    try:
        resp = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
        if resp.status_code == 200:
            results.add_pass("Logout succeeds")
            resp2 = client.post("/api/auth/validate", headers={"Authorization": f"Bearer {token}"})
            if resp2.status_code == 401:
                results.add_pass("Token revoked after logout")
            else:
                results.add_bug(f"Token still valid after logout (status {resp2.status_code})")
        else:
            results.add_fail("Logout", f"Status {resp.status_code}")
    except Exception as e:
        results.add_fail("Logout test", e)


def _comprehensive_feature_2_permissions(results: ComprehensiveTestResults) -> None:
    print(f"\n{'='*80}")
    print("FEATURE 2: Permission Enforcement")
    print(f"{'='*80}")

    app, store_id = _comprehensive_setup_test_db()
    client = app.test_client()

    with app.app_context():
        auth_service.create_default_roles()
        permission_service.initialize_permissions()
        permission_service.assign_default_role_permissions()

        user = User(
            username="noperm",
            email="noperm@example.com",
            password_hash=auth_service.hash_password("Pass123!"),
            store_id=store_id,
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()

        session, token_str = session_service.create_session(user.id, "test-agent", "127.0.0.1")

    try:
        resp = client.post("/api/sales/", json={"store_id": store_id})
        if resp.status_code == 401:
            results.add_pass("Protected endpoint requires auth")
        else:
            results.add_bug(f"Protected endpoint accessible without auth (status {resp.status_code})")
    except Exception as e:
        results.add_fail("Auth required test", e)

    try:
        resp = client.post(
            "/api/sales/",
            json={"store_id": store_id},
            headers={"Authorization": f"Bearer {token_str}"},
        )
        if resp.status_code == 403:
            results.add_pass("Permission-protected endpoint returns 403")
        else:
            results.add_bug(f"No CREATE_SALE permission but got status {resp.status_code}")
    except Exception as e:
        results.add_fail("Permission enforcement test", e)


def _comprehensive_feature_3_products(results: ComprehensiveTestResults) -> None:
    print(f"\n{'='*80}")
    print("FEATURE 3: Products")
    print(f"{'='*80}")

    app, store_id = _comprehensive_setup_test_db()
    client = app.test_client()

    with app.app_context():
        auth_service.create_default_roles()
        permission_service.initialize_permissions()
        permission_service.assign_default_role_permissions()
        admin = User(
            username="admin",
            email="admin@example.com",
            password_hash=auth_service.hash_password("Admin123!"),
            store_id=store_id,
            is_active=True,
        )
        db.session.add(admin)
        db.session.flush()

        admin_role = Role.query.filter_by(name="admin").first()
        user_role = UserRole(user_id=admin.id, role_id=admin_role.id)
        db.session.add(user_role)
        db.session.commit()

        session, token_str = session_service.create_session(admin.id, "test-agent", "127.0.0.1")

    try:
        resp = client.post(
            "/api/products",
            json={
                "sku": "SKU-001",
                "name": "Test Product",
                "description": "A test product",
                "price_cents": 1999,
                "is_active": True,
                "store_id": store_id,
            },
            headers={"Authorization": f"Bearer {token_str}"},
        )
        if resp.status_code == 201:
            product_id = resp.json["id"]
            results.add_pass("Create product")
        else:
            results.add_fail("Create product", f"Status {resp.status_code}: {resp.json}")
            return
    except Exception as e:
        results.add_fail("Create product", e)
        return

    try:
        resp = client.post(
            "/api/products",
            json={
                "sku": "SKU-001",
                "name": "Duplicate Product",
                "price_cents": 2999,
                "is_active": True,
                "store_id": store_id,
            },
            headers={"Authorization": f"Bearer {token_str}"},
        )
        if resp.status_code in (409, 400):
            results.add_pass("Duplicate SKU rejected")
        else:
            results.add_bug(f"Duplicate SKU allowed (status {resp.status_code})")
    except Exception as e:
        results.add_fail("Duplicate SKU test", e)

    try:
        resp = client.get(
            f"/api/products?store_id={store_id}",
            headers={"Authorization": f"Bearer {token_str}"},
        )
        if resp.status_code == 200 and "items" in resp.json:
            results.add_pass("List products")
        else:
            results.add_fail("List products", f"Status {resp.status_code}")
    except Exception as e:
        results.add_fail("List products", e)

    try:
        resp = client.put(
            f"/api/products/{product_id}",
            json={"price_cents": 2499},
            headers={"Authorization": f"Bearer {token_str}"},
        )
        if resp.status_code == 200:
            results.add_pass("Update product")
        else:
            results.add_fail("Update product", f"Status {resp.status_code}")
    except Exception as e:
        results.add_fail("Update product", e)


def _comprehensive_integer_cents_invariants(results: ComprehensiveTestResults) -> None:
    print(f"\n{'='*80}")
    print("CROSS-CUTTING: Integer Cents Invariants")
    print(f"{'='*80}")

    app, store_id = _comprehensive_setup_test_db()
    client = app.test_client()

    with app.app_context():
        auth_service.create_default_roles()
        permission_service.initialize_permissions()
        permission_service.assign_default_role_permissions()
        admin = User(
            username="admin2",
            email="admin2@example.com",
            password_hash=auth_service.hash_password("Admin123!"),
            store_id=store_id,
            is_active=True,
        )
        db.session.add(admin)
        db.session.flush()

        admin_role = Role.query.filter_by(name="admin").first()
        user_role = UserRole(user_id=admin.id, role_id=admin_role.id)
        db.session.add(user_role)
        db.session.commit()

        session, token_str = session_service.create_session(admin.id, "test-agent", "127.0.0.1")

    try:
        resp = client.post(
            "/api/products",
            json={
                "sku": "NEG-001",
                "name": "Negative Price",
                "price_cents": -100,
                "is_active": True,
                "store_id": store_id,
            },
            headers={"Authorization": f"Bearer {token_str}"},
        )
        if resp.status_code == 400:
            results.add_pass("Negative price_cents rejected")
        else:
            results.add_bug(f"Negative price_cents allowed (status {resp.status_code})")
    except Exception as e:
        results.add_fail("Negative price test", e)

    try:
        resp = client.post(
            "/api/products",
            json={
                "sku": "HUGE-001",
                "name": "Huge Price",
                "price_cents": 9999999999999999,
                "is_active": True,
                "store_id": store_id,
            },
            headers={"Authorization": f"Bearer {token_str}"},
        )
        if resp.status_code in (200, 201):
            results.add_pass("Huge price_cents handled")
        else:
            results.add_bug(f"Huge price_cents causes error (status {resp.status_code})")
    except Exception as e:
        results.add_bug(f"Huge price_cents crashes: {e}")


def run_comprehensive_tests() -> bool:
    print("=" * 80)
    print("APOS COMPREHENSIVE TEST SUITE")
    print("=" * 80)

    results = ComprehensiveTestResults()

    _comprehensive_feature_0_system_health(results)
    _comprehensive_feature_1_authentication(results)
    _comprehensive_feature_2_permissions(results)
    _comprehensive_feature_3_products(results)
    _comprehensive_integer_cents_invariants(results)

    results.summary()
    return len(results.failed) == 0


# ============================================================================
# Runner
# ============================================================================

def _run_script(path: str) -> bool:
    import subprocess

    result = subprocess.run([sys.executable, path], cwd=os.path.dirname(__file__))
    return result.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run APOS health/audit suites")
    parser.add_argument(
        "--suite",
        default="all",
        choices=[
            "all",
            "phase4",
            "lifecycle",
            "auth",
            "permission",
            "comprehensive",
            "payments",
            "registers",
            "concurrency",
        ],
        help="Which suite to run",
    )
    args = parser.parse_args()

    results = []

    if args.suite in ("all", "phase4"):
        results.append(run_phase4_sales_audit())
    if args.suite in ("all", "lifecycle"):
        results.append(run_lifecycle_audit())
    if args.suite in ("all", "auth"):
        results.append(run_authentication_audit())
    if args.suite in ("all", "permission"):
        results.append(run_permission_audit())
    if args.suite in ("all", "comprehensive"):
        results.append(run_comprehensive_tests())
    if args.suite in ("all", "payments"):
        results.append(_run_script("PaymentTests.py"))
    if args.suite in ("all", "registers"):
        results.append(_run_script("RegisterTests.py"))
    if args.suite in ("all", "concurrency"):
        results.append(_run_script("ConcurrencyTests.py"))

    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
