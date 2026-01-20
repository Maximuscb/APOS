#!/usr/bin/env python3
# Overview: Standalone concurrency test runner for backend safeguards.

"""
Scripted concurrency tests for APOS.

Run with:
    python ConcurrencyTests.py
"""
import os
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.extensions import db
from app.models import Store, User, Product, Sale
from app.services import sales_service, payment_service, inventory_service


class ConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        db_path = os.path.join(self.tmpdir.name, "concurrency.db")
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
        self.app = create_app()
        self.app.config["TESTING"] = True

        with self.app.app_context():
            db.drop_all()
            db.create_all()

            store = Store(name="Concurrency Store")
            db.session.add(store)
            db.session.commit()
            self.store_id = store.id

            user = User(
                username="concurrent_user",
                email="concurrent@example.com",
                password_hash="dummy",
                store_id=self.store_id,
                is_active=True,
            )
            db.session.add(user)
            db.session.commit()
            self.user_id = user.id

            product = Product(
                store_id=self.store_id,
                sku="CONCUR-1",
                name="Concurrent Product",
                price_cents=1000,
                is_active=True,
            )
            db.session.add(product)
            db.session.commit()
            self.product_id = product.id

            inventory_service.receive_inventory(
                store_id=self.store_id,
                product_id=self.product_id,
                quantity=10,
                unit_cost_cents=400,
                note="Seed inventory",
                status="POSTED",
            )

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.session.remove()
            db.engine.dispose()
        self.tmpdir.cleanup()

    def test_document_sequence_concurrency(self):
        created = []
        errors = []
        lock = threading.Lock()

        def worker():
            with self.app.app_context():
                try:
                    sale = sales_service.create_sale(self.store_id, self.user_id)
                    with lock:
                        created.append(sale.document_number)
                except Exception as exc:
                    with lock:
                        errors.append(exc)
                finally:
                    db.session.remove()

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertFalse(errors)
        self.assertEqual(len(created), len(set(created)))

    def test_concurrent_sale_post_oversell(self):
        with self.app.app_context():
            sale1 = sales_service.create_sale(self.store_id, self.user_id)
            sales_service.add_line(sale1.id, self.product_id, 6)
            sale2 = sales_service.create_sale(self.store_id, self.user_id)
            sales_service.add_line(sale2.id, self.product_id, 6)
            sale1_id = sale1.id
            sale2_id = sale2.id

        results = []
        lock = threading.Lock()

        def worker(sale_id):
            with self.app.app_context():
                try:
                    sales_service.post_sale(sale_id, self.user_id)
                    with lock:
                        results.append("posted")
                except Exception as exc:
                    with lock:
                        results.append(exc)
                finally:
                    db.session.remove()

        threads = [
            threading.Thread(target=worker, args=(sale1_id,)),
            threading.Thread(target=worker, args=(sale2_id,)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        with self.app.app_context():
            on_hand = inventory_service.get_quantity_on_hand(self.store_id, self.product_id)

        posted_count = sum(1 for r in results if r == "posted")
        self.assertLessEqual(posted_count, 1)
        self.assertGreaterEqual(on_hand, 0)

    def test_concurrent_void_and_refund(self):
        with self.app.app_context():
            sale = sales_service.create_sale(self.store_id, self.user_id)
            sales_service.add_line(sale.id, self.product_id, 2)

            payment = payment_service.add_payment(
                sale_id=sale.id,
                user_id=self.user_id,
                tender_type=payment_service.TENDER_CASH,
                amount_cents=2000,
            )
            sale_id = sale.id
            payment_id = payment.id

        results = []
        lock = threading.Lock()

        def void_worker():
            with self.app.app_context():
                try:
                    payment_service.void_payment(
                        payment_id=payment_id,
                        user_id=self.user_id,
                        reason="Test void",
                    )
                    with lock:
                        results.append("voided")
                except Exception as exc:
                    with lock:
                        results.append(exc)
                finally:
                    db.session.remove()

        def refund_worker():
            with self.app.app_context():
                try:
                    payment_service.refund_payment(
                        payment_id=payment_id,
                        user_id=self.user_id,
                        amount_cents=500,
                        tender_type=payment_service.TENDER_CASH,
                        reason="Test refund",
                    )
                    with lock:
                        results.append("refunded")
                except Exception as exc:
                    with lock:
                        results.append(exc)
                finally:
                    db.session.remove()

        threads = [threading.Thread(target=void_worker), threading.Thread(target=refund_worker)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        with self.app.app_context():
            sale = db.session.query(Sale).get(sale_id)
            self.assertIsNotNone(sale)
            self.assertGreaterEqual(sale.total_paid_cents or 0, 0)

        success_count = sum(1 for r in results if r in ("voided", "refunded"))
        self.assertEqual(success_count, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
