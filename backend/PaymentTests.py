#!/usr/bin/env python3
"""
Phase 9: Payment Processing Tests

Tests payment creation, split payments, change calculation, voids, and payment status tracking.

Run with:
    python PaymentTests.py
"""

import os
import sys
import unittest
import uuid

# Ensure backend module can be imported
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.extensions import db
from app.models import Store, User, Product, Sale, SaleLine, Payment, PaymentTransaction, RegisterSession, Register
from app.services import payment_service, sales_service, inventory_service
from app.services.payment_service import PaymentError


class PaymentSystemTest(unittest.TestCase):
    """Test payment processing functionality."""

    def setUp(self):
        """Set up test app and database before each test."""
        os.environ["DATABASE_URL"] = "sqlite:///:memory:"
        self.app = create_app()
        self.app.config['TESTING'] = True

        with self.app.app_context():
            db.create_all()

            # Create test store with unique name
            store = Store(name=f"Test Store {uuid.uuid4().hex[:8]}")
            db.session.add(store)
            db.session.commit()
            self.store_id = store.id

            # Create test users with unique usernames
            unique_id = uuid.uuid4().hex[:8]
            cashier = User(
                username=f"test_cashier_{unique_id}",
                email=f"cashier_{unique_id}@test.com",
                password_hash="dummy",
                store_id=self.store_id,
                is_active=True
            )
            manager = User(
                username=f"test_manager_{unique_id}",
                email=f"manager_{unique_id}@test.com",
                password_hash="dummy",
                store_id=self.store_id,
                is_active=True
            )
            db.session.add(cashier)
            db.session.add(manager)
            db.session.commit()

            self.cashier_id = cashier.id
            self.manager_id = manager.id

            # Create test product
            product = Product(
                store_id=self.store_id,
                sku="TEST-001",
                name="Test Product",
                price_cents=2000,  # $20.00
                is_active=True
            )
            db.session.add(product)
            db.session.commit()
            self.product_id = product.id

            inventory_service.receive_inventory(
                store_id=self.store_id,
                product_id=self.product_id,
                quantity=200,
                unit_cost_cents=500,
                note="Test seed inventory",
                status="POSTED",
            )

    def tearDown(self):
        """Clean up database after each test."""
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    # =========================================================================
    # PAYMENT CREATION TESTS
    # =========================================================================

    def test_create_cash_payment(self):
        """Test creating a cash payment."""
        with self.app.app_context():
            # Create sale with line
            sale = sales_service.create_sale(self.store_id, self.cashier_id)
            sales_service.add_line(sale.id, self.product_id, 2)  # 2 x $20 = $40

            # Add cash payment
            payment = payment_service.add_payment(
                sale_id=sale.id,
                user_id=self.cashier_id,
                tender_type=payment_service.TENDER_CASH,
                amount_cents=4000  # $40.00 exact
            )

            self.assertEqual(payment.tender_type, "CASH")
            self.assertEqual(payment.amount_cents, 4000)
            self.assertEqual(payment.status, "COMPLETED")
            self.assertEqual(payment.change_cents, 0)  # Exact payment

            # Check payment transaction was logged
            txns = payment_service.get_payment_transactions(payment.id)
            self.assertEqual(len(txns), 1)
            self.assertEqual(txns[0].transaction_type, "PAYMENT")
            self.assertEqual(txns[0].amount_cents, 4000)

            print("PASS test_create_cash_payment: Cash payment created correctly")

    def test_auto_post_on_payment(self):
        """Test that draft sales are auto-posted when payment is added."""
        with self.app.app_context():
            sale = sales_service.create_sale(self.store_id, self.cashier_id)
            sales_service.add_line(sale.id, self.product_id, 1)

            payment_service.add_payment(
                sale_id=sale.id,
                user_id=self.cashier_id,
                tender_type=payment_service.TENDER_CARD,
                amount_cents=2000
            )

            db.session.refresh(sale)
            self.assertEqual(sale.status, "POSTED")
            self.assertIsNotNone(sale.completed_at)

            lines = db.session.query(SaleLine).filter_by(sale_id=sale.id).all()
            self.assertTrue(all(line.inventory_transaction_id for line in lines))

            print("Auto-post on payment ok")

    def test_cash_payment_with_change(self):
        """Test cash payment with change calculation."""
        with self.app.app_context():
            # Create sale: $40.00 due
            sale = sales_service.create_sale(self.store_id, self.cashier_id)
            sales_service.add_line(sale.id, self.product_id, 2)

            # Pay with $50.00 cash
            payment = payment_service.add_payment(
                sale_id=sale.id,
                user_id=self.cashier_id,
                tender_type=payment_service.TENDER_CASH,
                amount_cents=5000  # $50.00
            )

            self.assertEqual(payment.amount_cents, 5000)
            self.assertEqual(payment.change_cents, 1000)  # $10.00 change

            # Check sale payment status
            db.session.refresh(sale)
            self.assertEqual(sale.payment_status, "PAID")
            self.assertEqual(sale.total_paid_cents, 4000)  # $40 applied to sale (after change)
            self.assertEqual(sale.change_due_cents, 1000)  # $10 change

            print("PASS test_cash_payment_with_change: Change calculated correctly")

    def test_non_cash_overpay_rejected(self):
        """Test that non-cash overpayment is rejected."""
        with self.app.app_context():
            sale = sales_service.create_sale(self.store_id, self.cashier_id)
            sales_service.add_line(sale.id, self.product_id, 1)

            with self.assertRaises(PaymentError) as context:
                payment_service.add_payment(
                    sale_id=sale.id,
                    user_id=self.cashier_id,
                    tender_type=payment_service.TENDER_CARD,
                    amount_cents=3000
                )

            self.assertIn("non-cash", str(context.exception).lower())

            print("Non-cash overpay rejected")

    def test_create_card_payment(self):
        """Test creating a card payment."""
        with self.app.app_context():
            sale = sales_service.create_sale(self.store_id, self.cashier_id)
            sales_service.add_line(sale.id, self.product_id, 1)  # $20.00

            payment = payment_service.add_payment(
                sale_id=sale.id,
                user_id=self.cashier_id,
                tender_type=payment_service.TENDER_CARD,
                amount_cents=2000,
                reference_number="AUTH-12345"
            )

            self.assertEqual(payment.tender_type, "CARD")
            self.assertEqual(payment.amount_cents, 2000)
            self.assertEqual(payment.reference_number, "AUTH-12345")
            self.assertEqual(payment.change_cents, 0)  # No change for cards

            print("PASS test_create_card_payment: Card payment created correctly")

    # =========================================================================
    # SPLIT PAYMENT TESTS
    # =========================================================================

    def test_split_payment_cash_and_card(self):
        """Test split payment with cash and card."""
        with self.app.app_context():
            sale = sales_service.create_sale(self.store_id, self.cashier_id)
            sales_service.add_line(sale.id, self.product_id, 3)  # $60.00 total

            # Pay $30 cash
            payment1 = payment_service.add_payment(
                sale_id=sale.id,
                user_id=self.cashier_id,
                tender_type=payment_service.TENDER_CASH,
                amount_cents=3000
            )

            # Check partial payment status
            db.session.refresh(sale)
            self.assertEqual(sale.payment_status, "PARTIAL")
            self.assertEqual(sale.total_paid_cents, 3000)

            # Pay remaining $30 by card
            payment2 = payment_service.add_payment(
                sale_id=sale.id,
                user_id=self.cashier_id,
                tender_type=payment_service.TENDER_CARD,
                amount_cents=3000,
                reference_number="AUTH-67890"
            )

            # Check fully paid
            db.session.refresh(sale)
            self.assertEqual(sale.payment_status, "PAID")
            self.assertEqual(sale.total_paid_cents, 6000)

            # Verify both payments exist
            payments = payment_service.get_sale_payments(sale.id)
            self.assertEqual(len(payments), 2)

            print("PASS test_split_payment_cash_and_card: Split payment works correctly")

    def test_void_one_of_multiple_payments(self):
        """Test voiding one of multiple payments updates totals correctly."""
        with self.app.app_context():
            sale = sales_service.create_sale(self.store_id, self.cashier_id)
            sales_service.add_line(sale.id, self.product_id, 3)

            payment1 = payment_service.add_payment(
                sale_id=sale.id,
                user_id=self.cashier_id,
                tender_type=payment_service.TENDER_CASH,
                amount_cents=3000
            )
            payment_service.add_payment(
                sale_id=sale.id,
                user_id=self.cashier_id,
                tender_type=payment_service.TENDER_CARD,
                amount_cents=3000
            )

            payment_service.void_payment(
                payment_id=payment1.id,
                user_id=self.manager_id,
                reason="Cash error"
            )

            db.session.refresh(sale)
            self.assertEqual(sale.total_paid_cents, 3000)
            self.assertEqual(sale.payment_status, "PARTIAL")

            print("Void one of multiple payments ok")

    def test_partial_payment(self):
        """Test partial payment (layaway scenario)."""
        with self.app.app_context():
            sale = sales_service.create_sale(self.store_id, self.cashier_id)
            sales_service.add_line(sale.id, self.product_id, 5)  # $100.00 total

            # Pay $40 as deposit
            payment = payment_service.add_payment(
                sale_id=sale.id,
                user_id=self.cashier_id,
                tender_type=payment_service.TENDER_CASH,
                amount_cents=4000
            )

            # Check partial status
            db.session.refresh(sale)
            self.assertEqual(sale.payment_status, "PARTIAL")
            self.assertEqual(sale.total_paid_cents, 4000)

            # Check remaining balance
            remaining = payment_service.get_sale_remaining_balance(sale.id)
            self.assertEqual(remaining, 6000)  # $60.00 remaining

            print("PASS test_partial_payment: Partial payment tracking works")

    # =========================================================================
    # PAYMENT STATUS TESTS
    # =========================================================================

    def test_payment_status_unpaid(self):
        """Test UNPAID status."""
        with self.app.app_context():
            sale = sales_service.create_sale(self.store_id, self.cashier_id)
            sales_service.add_line(sale.id, self.product_id, 1)

            db.session.refresh(sale)
            self.assertEqual(sale.payment_status, "UNPAID")
            self.assertEqual(sale.total_paid_cents, 0)

            print("PASS test_payment_status_unpaid: UNPAID status correct")

    def test_payment_status_paid(self):
        """Test PAID status."""
        with self.app.app_context():
            sale = sales_service.create_sale(self.store_id, self.cashier_id)
            sales_service.add_line(sale.id, self.product_id, 1)  # $20.00

            # Pay exact amount
            payment_service.add_payment(
                sale_id=sale.id,
                user_id=self.cashier_id,
                tender_type=payment_service.TENDER_CARD,
                amount_cents=2000
            )

            db.session.refresh(sale)
            self.assertEqual(sale.payment_status, "PAID")
            self.assertEqual(sale.total_paid_cents, 2000)

            print("PASS test_payment_status_paid: PAID status correct")

    def test_payment_status_overpaid(self):
        """Test OVERPAID status (cash over-tender)."""
        with self.app.app_context():
            sale = sales_service.create_sale(self.store_id, self.cashier_id)
            sales_service.add_line(sale.id, self.product_id, 1)  # $20.00

            # Pay $30.00 cash (over by $10)
            payment_service.add_payment(
                sale_id=sale.id,
                user_id=self.cashier_id,
                tender_type=payment_service.TENDER_CASH,
                amount_cents=3000
            )

            db.session.refresh(sale)
            self.assertEqual(sale.payment_status, "PAID")  # Still PAID, not OVERPAID
            self.assertEqual(sale.total_paid_cents, 2000)  # Only $20 applied
            self.assertEqual(sale.change_due_cents, 1000)  # $10 change

            print("PASS test_payment_status_overpaid: Overpayment handled correctly")

    # =========================================================================
    # PAYMENT VOID TESTS
    # =========================================================================

    def test_void_payment(self):
        """Test voiding a payment."""
        with self.app.app_context():
            sale = sales_service.create_sale(self.store_id, self.cashier_id)
            sales_service.add_line(sale.id, self.product_id, 1)  # $20.00

            # Add payment
            payment = payment_service.add_payment(
                sale_id=sale.id,
                user_id=self.cashier_id,
                tender_type=payment_service.TENDER_CASH,
                amount_cents=2000
            )

            # Verify payment completed
            db.session.refresh(sale)
            self.assertEqual(sale.payment_status, "PAID")

            # Void payment
            voided = payment_service.void_payment(
                payment_id=payment.id,
                user_id=self.manager_id,
                reason="Customer changed mind"
            )

            self.assertEqual(voided.status, "VOIDED")
            self.assertEqual(voided.voided_by_user_id, self.manager_id)
            self.assertEqual(voided.void_reason, "Customer changed mind")

            # Check sale reverted to unpaid
            db.session.refresh(sale)
            self.assertEqual(sale.payment_status, "UNPAID")
            self.assertEqual(sale.total_paid_cents, 0)

            # Check void transaction logged
            txns = payment_service.get_payment_transactions(payment.id)
            self.assertEqual(len(txns), 2)  # PAYMENT + VOID
            self.assertEqual(txns[1].transaction_type, "VOID")
            self.assertEqual(txns[1].amount_cents, -2000)  # Negative

            print("PASS test_void_payment: Payment void works correctly")

    def test_void_then_new_payment(self):
        """Test void then new payment keeps totals consistent."""
        with self.app.app_context():
            sale = sales_service.create_sale(self.store_id, self.cashier_id)
            sales_service.add_line(sale.id, self.product_id, 1)

            payment = payment_service.add_payment(
                sale_id=sale.id,
                user_id=self.cashier_id,
                tender_type=payment_service.TENDER_CASH,
                amount_cents=2000
            )

            payment_service.void_payment(
                payment_id=payment.id,
                user_id=self.manager_id,
                reason="Mistake"
            )

            payment_service.add_payment(
                sale_id=sale.id,
                user_id=self.cashier_id,
                tender_type=payment_service.TENDER_CARD,
                amount_cents=2000
            )

            db.session.refresh(sale)
            self.assertEqual(sale.payment_status, "PAID")
            self.assertEqual(sale.total_paid_cents, 2000)

            print("Void then new payment ok")

    def test_cannot_void_already_voided(self):
        """Test that voided payments cannot be voided again."""
        with self.app.app_context():
            sale = sales_service.create_sale(self.store_id, self.cashier_id)
            sales_service.add_line(sale.id, self.product_id, 1)

            payment = payment_service.add_payment(
                sale_id=sale.id,
                user_id=self.cashier_id,
                tender_type=payment_service.TENDER_CASH,
                amount_cents=2000
            )

            # Void payment
            payment_service.void_payment(
                payment_id=payment.id,
                user_id=self.manager_id,
                reason="Test"
            )

            # Try to void again
            with self.assertRaises(PaymentError) as context:
                payment_service.void_payment(
                    payment_id=payment.id,
                    user_id=self.manager_id,
                    reason="Test 2"
                )

            self.assertIn("already voided", str(context.exception).lower())

            print("PASS test_cannot_void_already_voided: Double void prevented")

    # =========================================================================
    # PAYMENT SUMMARY TESTS
    # =========================================================================

    def test_payment_summary(self):
        """Test payment summary calculation."""
        with self.app.app_context():
            sale = sales_service.create_sale(self.store_id, self.cashier_id)
            sales_service.add_line(sale.id, self.product_id, 5)  # $100.00 total

            # Add partial payment
            payment_service.add_payment(
                sale_id=sale.id,
                user_id=self.cashier_id,
                tender_type=payment_service.TENDER_CASH,
                amount_cents=6000  # $60.00
            )

            # Get summary
            summary = payment_service.get_payment_summary(sale.id)

            self.assertEqual(summary["total_due_cents"], 10000)  # $100.00
            self.assertEqual(summary["total_paid_cents"], 6000)  # $60.00
            self.assertEqual(summary["remaining_cents"], 4000)  # $40.00 remaining
            self.assertEqual(summary["payment_status"], "PARTIAL")
            self.assertEqual(len(summary["payments"]), 1)

            print("PASS test_payment_summary: Payment summary calculated correctly")

    # =========================================================================
    # TENDER SUMMARY TESTS
    # =========================================================================

    def test_refund_payment(self):
        """Test refunding a payment using negative transactions."""
        with self.app.app_context():
            sale = sales_service.create_sale(self.store_id, self.cashier_id)
            sales_service.add_line(sale.id, self.product_id, 2)

            payment = payment_service.add_payment(
                sale_id=sale.id,
                user_id=self.cashier_id,
                tender_type=payment_service.TENDER_CASH,
                amount_cents=4000
            )

            payment_service.refund_payment(
                payment_id=payment.id,
                user_id=self.manager_id,
                amount_cents=1000,
                tender_type=payment_service.TENDER_CASH,
                reason="Refund partial"
            )

            db.session.refresh(sale)
            self.assertEqual(sale.total_paid_cents, 3000)
            self.assertEqual(sale.payment_status, "PARTIAL")

            txns = payment_service.get_payment_transactions(payment.id)
            self.assertTrue(any(tx.transaction_type == "REFUND" for tx in txns))

            print("Refund payment ok")

    def test_void_sale_reverses_payments(self):
        """Test voiding a sale reverses payments and inventory."""
        with self.app.app_context():
            sale = sales_service.create_sale(self.store_id, self.cashier_id)
            sales_service.add_line(sale.id, self.product_id, 1)

            payment = payment_service.add_payment(
                sale_id=sale.id,
                user_id=self.cashier_id,
                tender_type=payment_service.TENDER_CASH,
                amount_cents=2000
            )

            sales_service.void_sale(
                sale_id=sale.id,
                user_id=self.manager_id,
                reason="Customer cancelled"
            )

            db.session.refresh(sale)
            self.assertEqual(sale.status, "VOIDED")
            self.assertEqual(sale.payment_status, "VOIDED")

            db.session.refresh(payment)
            self.assertEqual(payment.status, "VOIDED")

            print("Sale void reverses payments ok")

    def test_tender_summary(self):
        """Test tender type summary for register session."""
        with self.app.app_context():
            # Create register and session
            from app.services import register_service
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

            # Create multiple sales with different tender types
            # Sale 1: $40 cash
            sale1 = sales_service.create_sale(self.store_id, self.cashier_id)
            sales_service.add_line(sale1.id, self.product_id, 2)
            payment_service.add_payment(
                sale_id=sale1.id,
                user_id=self.cashier_id,
                tender_type=payment_service.TENDER_CASH,
                amount_cents=4000,
                register_session_id=session.id
            )

            # Sale 2: $60 card
            sale2 = sales_service.create_sale(self.store_id, self.cashier_id)
            sales_service.add_line(sale2.id, self.product_id, 3)
            payment_service.add_payment(
                sale_id=sale2.id,
                user_id=self.cashier_id,
                tender_type=payment_service.TENDER_CARD,
                amount_cents=6000,
                reference_number="AUTH-123",
                register_session_id=session.id
            )

            # Sale 3: $20 cash
            sale3 = sales_service.create_sale(self.store_id, self.cashier_id)
            sales_service.add_line(sale3.id, self.product_id, 1)
            payment_service.add_payment(
                sale_id=sale3.id,
                user_id=self.cashier_id,
                tender_type=payment_service.TENDER_CASH,
                amount_cents=2000,
                register_session_id=session.id
            )

            # Get tender summary
            tender_summary = payment_service.get_tender_summary(session.id)

            self.assertEqual(tender_summary["CASH"], 6000)  # $40 + $20
            self.assertEqual(tender_summary["CARD"], 6000)  # $60

            print("PASS test_tender_summary: Tender summary calculated correctly")

    # =========================================================================
    # VALIDATION TESTS
    # =========================================================================

    def test_invalid_tender_type(self):
        """Test that invalid tender types are rejected."""
        with self.app.app_context():
            sale = sales_service.create_sale(self.store_id, self.cashier_id)
            sales_service.add_line(sale.id, self.product_id, 1)

            with self.assertRaises(PaymentError) as context:
                payment_service.add_payment(
                    sale_id=sale.id,
                    user_id=self.cashier_id,
                    tender_type="BITCOIN",  # Invalid
                    amount_cents=2000
                )

            self.assertIn("invalid tender type", str(context.exception).lower())

            print("PASS test_invalid_tender_type: Invalid tender type rejected")

    def test_negative_payment_amount(self):
        """Test that negative payment amounts are rejected."""
        with self.app.app_context():
            sale = sales_service.create_sale(self.store_id, self.cashier_id)
            sales_service.add_line(sale.id, self.product_id, 1)

            with self.assertRaises(PaymentError) as context:
                payment_service.add_payment(
                    sale_id=sale.id,
                    user_id=self.cashier_id,
                    tender_type=payment_service.TENDER_CASH,
                    amount_cents=-1000  # Negative
                )

            self.assertIn("must be positive", str(context.exception).lower())

            print("PASS test_negative_payment_amount: Negative amount rejected")


def run_tests():
    """Run all tests and display results."""
    print("\n" + "="*80)
    print("PHASE 9: PAYMENT PROCESSING TESTS")
    print("="*80 + "\n")

    # Create test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(PaymentSystemTest)

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
