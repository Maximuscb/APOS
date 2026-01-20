#!/usr/bin/env python3
# Overview: Standalone test runner for register and session behavior.

"""
Register and Shift Management Tests

Tests register creation, shift operations, cash drawer tracking, and variance calculation.

Run with:
    python RegisterTests.py
"""

import os
import sys
import unittest
from datetime import datetime

# Ensure backend module can be imported
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.extensions import db
from app.models import Store, User, Role, Register, RegisterSession, CashDrawerEvent, Sale, Product
from app.services import register_service, payment_service, sales_service, inventory_service
from app.services.register_service import ShiftError, RegisterError


class RegisterSystemTest(unittest.TestCase):
    """Test register and shift management functionality."""

    def setUp(self):
        """Set up test app and database before each test."""
        os.environ["DATABASE_URL"] = "sqlite:///:memory:"
        self.app = create_app()
        self.app.config['TESTING'] = True

        with self.app.app_context():
            db.create_all()

            # Create test store
            store = Store(name="Test Store")
            db.session.add(store)
            db.session.commit()
            self.store_id = store.id

            # Create test users
            cashier = User(
                username="test_cashier",
                email="cashier@test.com",
                password_hash="dummy",
                store_id=self.store_id,
                is_active=True
            )
            manager = User(
                username="test_manager",
                email="manager@test.com",
                password_hash="dummy",
                store_id=self.store_id,
                is_active=True
            )
            db.session.add(cashier)
            db.session.add(manager)
            db.session.commit()

            self.cashier_id = cashier.id
            self.manager_id = manager.id

    def tearDown(self):
        """Clean up database after each test."""
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    # =========================================================================
    # REGISTER MANAGEMENT TESTS
    # =========================================================================

    def test_register_creation(self):
        """Test creating a new register."""
        with self.app.app_context():
            register = register_service.create_register(
                store_id=self.store_id,
                register_number="REG-01",
                name="Front Counter 1",
                location="Main Floor",
                device_id="DEVICE-001"
            )

            self.assertEqual(register.register_number, "REG-01")
            self.assertEqual(register.name, "Front Counter 1")
            self.assertEqual(register.location, "Main Floor")
            self.assertEqual(register.device_id, "DEVICE-001")
            self.assertTrue(register.is_active)
            self.assertEqual(register.store_id, self.store_id)

            print("PASS test_register_creation: Register created successfully")

    def test_unique_register_number_per_store(self):
        """Test that register numbers must be unique per store."""
        with self.app.app_context():
            # Create first register
            register_service.create_register(
                store_id=self.store_id,
                register_number="REG-01",
                name="Register 1"
            )

            # Try to create duplicate
            with self.assertRaises(RegisterError) as context:
                register_service.create_register(
                    store_id=self.store_id,
                    register_number="REG-01",
                    name="Register 2"
                )

            self.assertIn("already exists", str(context.exception).lower())

            print("PASS test_unique_register_number_per_store: Duplicate prevention works")

    # =========================================================================
    # SHIFT LIFECYCLE TESTS
    # =========================================================================

    def test_open_shift(self):
        """Test opening a new shift."""
        with self.app.app_context():
            register = register_service.create_register(
                store_id=self.store_id,
                register_number="REG-01",
                name="Test Register"
            )

            session = register_service.open_shift(
                register_id=register.id,
                user_id=self.cashier_id,
                opening_cash_cents=10000  # $100.00
            )

            self.assertEqual(session.register_id, register.id)
            self.assertEqual(session.user_id, self.cashier_id)
            self.assertEqual(session.opened_by_user_id, self.cashier_id)
            self.assertEqual(session.status, "OPEN")
            self.assertEqual(session.opening_cash_cents, 10000)
            self.assertEqual(session.expected_cash_cents, 10000)  # Initially same as opening
            self.assertIsNone(session.closed_at)
            self.assertIsNone(session.variance_cents)

            # Check SHIFT_OPEN event was logged
            event = db.session.query(CashDrawerEvent).filter_by(
                register_session_id=session.id,
                event_type="SHIFT_OPEN"
            ).first()

            self.assertIsNotNone(event)
            self.assertEqual(event.amount_cents, 10000)

            print("PASS test_open_shift: Shift opened and logged correctly")

    def test_prevent_multiple_open_shifts(self):
        """Test that only one shift can be open per register at a time."""
        with self.app.app_context():
            register = register_service.create_register(
                store_id=self.store_id,
                register_number="REG-01",
                name="Test Register"
            )

            # Open first shift
            register_service.open_shift(
                register_id=register.id,
                user_id=self.cashier_id,
                opening_cash_cents=10000
            )

            # Try to open second shift
            with self.assertRaises(ShiftError) as context:
                register_service.open_shift(
                    register_id=register.id,
                    user_id=self.manager_id,
                    opening_cash_cents=5000
                )

            self.assertIn("already has open shift", str(context.exception).lower())

            print("PASS test_prevent_multiple_open_shifts: Multiple shifts prevented")

    def test_close_shift_with_variance(self):
        """Test closing a shift and calculating variance."""
        with self.app.app_context():
            register = register_service.create_register(
                store_id=self.store_id,
                register_number="REG-01",
                name="Test Register"
            )

            session = register_service.open_shift(
                register_id=register.id,
                user_id=self.cashier_id,
                opening_cash_cents=10000  # $100.00
            )

            # Simulate some sales by updating expected_cash
            session.expected_cash_cents = 12500  # $125.00 expected
            db.session.commit()

            # Close shift with actual cash
            closed_session = register_service.close_shift(
                session_id=session.id,
                closing_cash_cents=12300,  # $123.00 actual
                notes="Short $2.00",
                current_user_id=self.cashier_id,
            )

            self.assertEqual(closed_session.status, "CLOSED")
            self.assertEqual(closed_session.closing_cash_cents, 12300)
            self.assertEqual(closed_session.expected_cash_cents, 12500)
            self.assertEqual(closed_session.variance_cents, -200)  # Short $2.00
            self.assertIsNotNone(closed_session.closed_at)
            self.assertEqual(closed_session.notes, "Short $2.00")

            # Check SHIFT_CLOSE event was logged
            event = db.session.query(CashDrawerEvent).filter_by(
                register_session_id=session.id,
                event_type="SHIFT_CLOSE"
            ).first()

            self.assertIsNotNone(event)
            self.assertEqual(event.amount_cents, 12300)

            print("PASS test_close_shift_with_variance: Shift closed, variance calculated")

    def test_close_shift_balanced(self):
        """Test closing a shift with no variance."""
        with self.app.app_context():
            register = register_service.create_register(
                store_id=self.store_id,
                register_number="REG-01",
                name="Test Register"
            )

            session = register_service.open_shift(
                register_id=register.id,
                user_id=self.cashier_id,
                opening_cash_cents=10000
            )

            # Expected and actual match
            session.expected_cash_cents = 15000
            db.session.commit()

            closed_session = register_service.close_shift(
                session_id=session.id,
                closing_cash_cents=15000,
                notes="Perfect balance",
                current_user_id=self.cashier_id,
            )

            self.assertEqual(closed_session.variance_cents, 0)

            print("PASS test_close_shift_balanced: Balanced shift works correctly")

    def test_close_shift_requires_owner_or_manager(self):
        """Test that only the session owner can close unless manager override."""
        with self.app.app_context():
            register = register_service.create_register(
                store_id=self.store_id,
                register_number="REG-01",
                name="Test Register"
            )

            session = register_service.open_shift(
                register_id=register.id,
                user_id=self.cashier_id,
                opening_cash_cents=10000
            )

            with self.assertRaises(ShiftError):
                register_service.close_shift(
                    session_id=session.id,
                    closing_cash_cents=10000,
                    current_user_id=self.manager_id,
                    manager_override=False,
                )

            closed = register_service.close_shift(
                session_id=session.id,
                closing_cash_cents=10000,
                current_user_id=self.manager_id,
                manager_override=True,
            )

            self.assertEqual(closed.status, "CLOSED")

            print("Owner enforcement ok")

    def test_cannot_reopen_closed_shift(self):
        """Test that closed shifts cannot be reopened."""
        with self.app.app_context():
            register = register_service.create_register(
                store_id=self.store_id,
                register_number="REG-01",
                name="Test Register"
            )

            session = register_service.open_shift(
                register_id=register.id,
                user_id=self.cashier_id,
                opening_cash_cents=10000
            )

            # Close the shift
            register_service.close_shift(
                session_id=session.id,
                closing_cash_cents=10000,
                current_user_id=self.cashier_id,
            )

            # Try to close again
            with self.assertRaises(ShiftError) as context:
                register_service.close_shift(
                    session_id=session.id,
                    closing_cash_cents=11000,
                    current_user_id=self.cashier_id,
                )

            self.assertIn("already closed", str(context.exception).lower())

            print("PASS test_cannot_reopen_closed_shift: Session immutability enforced")

    # =========================================================================
    # CASH DRAWER EVENT TESTS
    # =========================================================================

    def test_no_sale_drawer_open(self):
        """Test logging no-sale drawer opens."""
        with self.app.app_context():
            register = register_service.create_register(
                store_id=self.store_id,
                register_number="REG-01",
                name="Test Register"
            )

            session = register_service.open_shift(
                register_id=register.id,
                user_id=self.cashier_id,
                opening_cash_cents=10000
            )

            # Open drawer without sale
            event = register_service.open_drawer_no_sale(
                register_session_id=session.id,
                register_id=register.id,
                user_id=self.cashier_id,
                approved_by_user_id=self.manager_id,
                reason="Customer needed change"
            )

            self.assertEqual(event.event_type, "NO_SALE")
            self.assertEqual(event.user_id, self.cashier_id)
            self.assertEqual(event.approved_by_user_id, self.manager_id)
            self.assertEqual(event.reason, "Customer needed change")
            self.assertIsNone(event.amount_cents)

            print("PASS test_no_sale_drawer_open: No-sale event logged correctly")

    def test_cash_drop(self):
        """Test logging cash drops."""
        with self.app.app_context():
            register = register_service.create_register(
                store_id=self.store_id,
                register_number="REG-01",
                name="Test Register"
            )

            session = register_service.open_shift(
                register_id=register.id,
                user_id=self.cashier_id,
                opening_cash_cents=10000
            )

            # Simulate sales
            session.expected_cash_cents = 20000  # $200.00
            db.session.commit()

            # Drop excess cash
            event = register_service.cash_drop(
                register_session_id=session.id,
                register_id=register.id,
                user_id=self.cashier_id,
                amount_cents=5000,  # Drop $50.00
                approved_by_user_id=self.manager_id,
                reason="Safe drop - drawer over $200"
            )

            self.assertEqual(event.event_type, "CASH_DROP")
            self.assertEqual(event.amount_cents, 5000)
            self.assertEqual(event.approved_by_user_id, self.manager_id)
            self.assertEqual(event.reason, "Safe drop - drawer over $200")

            # Expected cash should be reduced
            db.session.refresh(session)
            self.assertEqual(session.expected_cash_cents, 15000)  # $200 - $50 = $150

            print("PASS test_cash_drop: Cash drop logged and expected cash adjusted")

    def test_drawer_event_audit_trail(self):
        """Test that all drawer events create immutable audit trail."""
        with self.app.app_context():
            register = register_service.create_register(
                store_id=self.store_id,
                register_number="REG-01",
                name="Test Register"
            )

            session = register_service.open_shift(
                register_id=register.id,
                user_id=self.cashier_id,
                opening_cash_cents=10000
            )

            # Log multiple events
            register_service.open_drawer_no_sale(
                register_session_id=session.id,
                register_id=register.id,
                user_id=self.cashier_id,
                approved_by_user_id=self.manager_id,
                reason="Event 1"
            )

            register_service.cash_drop(
                register_session_id=session.id,
                register_id=register.id,
                user_id=self.cashier_id,
                amount_cents=5000,
                approved_by_user_id=self.manager_id,
                reason="Event 2"
            )

            register_service.close_shift(
                session_id=session.id,
                closing_cash_cents=5000,
                current_user_id=self.cashier_id,
            )

            # Check all events
            events = db.session.query(CashDrawerEvent).filter_by(
                register_session_id=session.id
            ).order_by(CashDrawerEvent.occurred_at).all()

            # Should have: SHIFT_OPEN, NO_SALE, CASH_DROP, SHIFT_CLOSE
            self.assertEqual(len(events), 4)
            self.assertEqual(events[0].event_type, "SHIFT_OPEN")
            self.assertEqual(events[1].event_type, "NO_SALE")
            self.assertEqual(events[2].event_type, "CASH_DROP")
            self.assertEqual(events[3].event_type, "SHIFT_CLOSE")

            print("PASS test_drawer_event_audit_trail: Complete audit trail maintained")

    # =========================================================================
    # INTEGRATION TESTS
    # =========================================================================

    def test_expected_cash_from_payments_and_drops(self):
        """Test expected cash updates from payments and cash drops."""
        with self.app.app_context():
            register = register_service.create_register(
                store_id=self.store_id,
                register_number="REG-01",
                name="Test Register"
            )

            session = register_service.open_shift(
                register_id=register.id,
                user_id=self.cashier_id,
                opening_cash_cents=10000
            )

            product = Product(
                store_id=self.store_id,
                sku="TEST-002",
                name="Test Product 2",
                price_cents=2000,
                is_active=True
            )
            db.session.add(product)
            db.session.commit()

            inventory_service.receive_inventory(
                store_id=self.store_id,
                product_id=product.id,
                quantity=10,
                unit_cost_cents=500,
                note="Seed inventory",
                status="POSTED",
            )

            sale = sales_service.create_sale(self.store_id, self.cashier_id)
            sales_service.add_line(sale.id, product.id, 2)
            payment_service.add_payment(
                sale_id=sale.id,
                user_id=self.cashier_id,
                tender_type=payment_service.TENDER_CASH,
                amount_cents=4000,
                register_id=register.id,
                register_session_id=session.id
            )

            db.session.refresh(session)
            self.assertEqual(session.expected_cash_cents, 14000)

            register_service.cash_drop(
                register_session_id=session.id,
                register_id=register.id,
                user_id=self.cashier_id,
                amount_cents=2000,
                approved_by_user_id=self.manager_id,
                reason="Safe drop"
            )

            db.session.refresh(session)
            self.assertEqual(session.expected_cash_cents, 12000)

            closed = register_service.close_shift(
                session_id=session.id,
                closing_cash_cents=12000,
                current_user_id=self.cashier_id,
            )

            self.assertEqual(closed.variance_cents, 0)

            events = db.session.query(CashDrawerEvent).filter_by(
                register_session_id=session.id,
                event_type="SHIFT_CLOSE"
            ).all()
            self.assertTrue(events)

            print("Expected cash and variance ok")

    def test_multiple_shifts_on_register(self):
        """Test that multiple shifts can be opened sequentially."""
        with self.app.app_context():
            register = register_service.create_register(
                store_id=self.store_id,
                register_number="REG-01",
                name="Test Register"
            )

            # First shift
            session1 = register_service.open_shift(
                register_id=register.id,
                user_id=self.cashier_id,
                opening_cash_cents=10000
            )

            register_service.close_shift(
                session_id=session1.id,
                closing_cash_cents=12000,
                current_user_id=self.cashier_id,
            )

            # Second shift (should work now)
            session2 = register_service.open_shift(
                register_id=register.id,
                user_id=self.manager_id,
                opening_cash_cents=5000
            )

            self.assertEqual(session2.status, "OPEN")
            self.assertEqual(session1.status, "CLOSED")

            print("PASS test_multiple_shifts_on_register: Sequential shifts work correctly")

    def test_expected_cash_calculation(self):
        """Test that expected cash starts at opening cash and can be updated."""
        with self.app.app_context():
            register = register_service.create_register(
                store_id=self.store_id,
                register_number="REG-01",
                name="Test Register"
            )

            session = register_service.open_shift(
                register_id=register.id,
                user_id=self.cashier_id,
                opening_cash_cents=10000
            )

            # Initially, expected = opening
            self.assertEqual(session.expected_cash_cents, session.opening_cash_cents)

            # Simulate sales by updating expected cash
            session.expected_cash_cents += 5000  # Add $50 sale
            db.session.commit()

            self.assertEqual(session.expected_cash_cents, 15000)

            # Close with matching amount
            closed = register_service.close_shift(
                session_id=session.id,
                closing_cash_cents=15000,
                current_user_id=self.cashier_id,
            )

            self.assertEqual(closed.variance_cents, 0)

            print("PASS test_expected_cash_calculation: Expected cash calculation correct")


def run_tests():
    """Run all tests and display results."""
    print("\n" + "="*80)
    print("REGISTER & SHIFT MANAGEMENT TESTS")
    print("="*80 + "\n")

    # Create test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(RegisterSystemTest)

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Display summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")

    if result.wasSuccessful():
        print("\nPASS ALL TESTS PASSED!")
    else:
        print("\nFAIL SOME TESTS FAILED")

    print("="*80 + "\n")

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
