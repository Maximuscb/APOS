# APOS API Tests - Sales & Payments
#
# Tests for:
# - Sale creation and line items
# - Sale posting (inventory deduction)
# - Sale voiding
# - Payment processing (multiple tenders)
# - Split payments and change calculation
# - Payment voids and refunds
# - Payment summary calculations

import pytest
import time
from typing import Dict

from tests.conftest import APIClient, TestFailure, assert_response, TestDataFactory


class TestSaleCreation:
    """Sale creation and line item tests."""

    @pytest.mark.smoke
    @pytest.mark.sales
    def test_create_sale(self, admin_client: APIClient):
        """
        Test creating a new draft sale.

        SCENARIO: Create a sale document
        EXPECTED: HTTP 201 with sale in DRAFT status
        """
        response = admin_client.post("/api/sales/", json={
            "store_id": 1
        })

        assert_response(
            response, 201,
            scenario="Create draft sale",
            code_location="backend/app/routes/sales.py:create_sale_route"
        )

        data = response.json()

        if "sale" not in data:
            raise TestFailure(
                scenario="Create sale response should have sale object",
                expected="Response has 'sale' key",
                actual=f"Response keys: {list(data.keys())}",
                likely_cause="Response format changed",
                code_location="backend/app/routes/sales.py:create_sale_route",
                response=response
            )

        sale = data["sale"]
        if sale.get("status") != "DRAFT":
            raise TestFailure(
                scenario="New sale should be in DRAFT status",
                expected="status = DRAFT",
                actual=f"status = {sale.get('status')}",
                likely_cause="Sale not initialized to DRAFT",
                code_location="backend/app/services/sales_service.py:create_sale",
                response=response
            )

    @pytest.mark.sales
    def test_create_sale_missing_store(self, admin_client: APIClient):
        """
        Test sale creation validation.

        SCENARIO: Create sale without store_id
        EXPECTED: HTTP 400
        """
        response = admin_client.post("/api/sales/", json={})

        assert_response(
            response, 400,
            scenario="Create sale without store_id",
            code_location="backend/app/routes/sales.py:create_sale_route"
        )

    @pytest.mark.smoke
    @pytest.mark.sales
    def test_add_sale_line(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test adding line items to a sale.

        SCENARIO: Add product line to draft sale
        EXPECTED: HTTP 201 with line item details
        """
        # Create product with inventory
        product = factory.create_product(store_id=1, price_cents=1999)
        product_id = product.get("id") or product.get("product", {}).get("id")
        factory.receive_inventory(store_id=1, product_id=product_id, quantity=10, unit_cost_cents=1000)

        # Create sale
        sale = factory.create_sale(store_id=1)
        sale_id = sale.get("sale", {}).get("id")

        # Add line
        response = admin_client.post(f"/api/sales/{sale_id}/lines", json={
            "product_id": product_id,
            "quantity": 2
        })

        assert_response(
            response, 201,
            scenario="Add line to sale",
            code_location="backend/app/routes/sales.py:add_line_route"
        )

        data = response.json()

        if "line" not in data:
            raise TestFailure(
                scenario="Add line response should have line object",
                expected="Response has 'line' key",
                actual=f"Response keys: {list(data.keys())}",
                likely_cause="Response format changed",
                code_location="backend/app/routes/sales.py:add_line_route",
                response=response
            )

        line = data["line"]
        # Verify line total is calculated (2 * 1999 = 3998)
        if line.get("line_total_cents") != 3998:
            raise TestFailure(
                scenario="Line total should be quantity * unit_price",
                expected="line_total_cents = 3998 (2 * 1999)",
                actual=f"line_total_cents = {line.get('line_total_cents')}",
                likely_cause="Line total calculation error",
                code_location="backend/app/services/sales_service.py:add_line",
                response=response
            )

    @pytest.mark.sales
    def test_add_multiple_lines(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test adding multiple line items to a sale.

        SCENARIO: Add multiple products to one sale
        EXPECTED: All lines added correctly
        """
        # Create products
        product1 = factory.create_product(store_id=1, price_cents=1000)
        product1_id = product1.get("id") or product1.get("product", {}).get("id")
        factory.receive_inventory(store_id=1, product_id=product1_id, quantity=10, unit_cost_cents=500)

        product2 = factory.create_product(store_id=1, price_cents=2000)
        product2_id = product2.get("id") or product2.get("product", {}).get("id")
        factory.receive_inventory(store_id=1, product_id=product2_id, quantity=10, unit_cost_cents=1000)

        # Create sale
        sale = factory.create_sale(store_id=1)
        sale_id = sale.get("sale", {}).get("id")

        # Add lines
        factory.add_sale_line(sale_id, product1_id, 3)  # 3000
        factory.add_sale_line(sale_id, product2_id, 2)  # 4000

        # Get sale to verify total
        response = admin_client.get(f"/api/sales/{sale_id}")

        assert_response(
            response, 200,
            scenario="Get sale with multiple lines",
            code_location="backend/app/routes/sales.py:get_sale_route"
        )

        data = response.json()
        lines = data.get("lines", [])

        if len(lines) != 2:
            raise TestFailure(
                scenario="Sale should have 2 lines",
                expected="2 lines",
                actual=f"{len(lines)} lines",
                likely_cause="Lines not all added or returned",
                code_location="backend/app/routes/sales.py:get_sale_route",
                response=response
            )


class TestSalePosting:
    """Sale posting (finalization) tests."""

    @pytest.mark.smoke
    @pytest.mark.sales
    def test_post_sale(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test posting a sale (deducting inventory).

        SCENARIO: Post a sale with items
        EXPECTED: HTTP 200, status becomes POSTED, inventory deducted
        """
        # Setup
        product = factory.create_product(store_id=1, price_cents=1000)
        product_id = product.get("id") or product.get("product", {}).get("id")
        factory.receive_inventory(store_id=1, product_id=product_id, quantity=10, unit_cost_cents=500)

        sale = factory.create_sale(store_id=1)
        sale_id = sale.get("sale", {}).get("id")
        factory.add_sale_line(sale_id, product_id, 3)

        # Get initial inventory
        inv_before = admin_client.get(f"/api/inventory/{product_id}/summary", params={"store_id": 1}).json()
        on_hand_before = inv_before.get("on_hand") or inv_before.get("quantity", 10)

        # Post sale
        response = admin_client.post(f"/api/sales/{sale_id}/post")

        assert_response(
            response, 200,
            scenario="Post sale",
            code_location="backend/app/routes/sales.py:post_sale_route"
        )

        data = response.json()
        sale = data.get("sale", {})

        if sale.get("status") != "POSTED":
            raise TestFailure(
                scenario="Posted sale should have POSTED status",
                expected="status = POSTED",
                actual=f"status = {sale.get('status')}",
                likely_cause="Sale status not updated on post",
                code_location="backend/app/services/sales_service.py:post_sale",
                response=response
            )

        # Verify inventory deducted
        inv_after = admin_client.get(f"/api/inventory/{product_id}/summary", params={"store_id": 1}).json()
        on_hand_after = inv_after.get("on_hand") or inv_after.get("quantity")

        if on_hand_after is not None and on_hand_before is not None:
            expected_after = on_hand_before - 3
            if on_hand_after != expected_after:
                raise TestFailure(
                    scenario="Posting sale should deduct inventory",
                    expected=f"on_hand = {expected_after} (was {on_hand_before}, sold 3)",
                    actual=f"on_hand = {on_hand_after}",
                    likely_cause="Inventory transaction not created on post",
                    code_location="backend/app/services/sales_service.py:post_sale"
                )

    @pytest.mark.sales
    def test_cannot_post_empty_sale(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test that empty sale cannot be posted.

        SCENARIO: Try to post sale with no lines
        EXPECTED: HTTP 400
        """
        sale = factory.create_sale(store_id=1)
        sale_id = sale.get("sale", {}).get("id")

        response = admin_client.post(f"/api/sales/{sale_id}/post")

        # Should fail - no lines
        if response.status_code == 200:
            raise TestFailure(
                scenario="Empty sale should not be postable",
                expected="HTTP 400",
                actual="HTTP 200",
                likely_cause="Empty sale validation missing",
                code_location="backend/app/services/sales_service.py:post_sale",
                response=response
            )

    @pytest.mark.sales
    def test_cannot_post_already_posted_sale(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test that already-posted sale cannot be posted again.

        SCENARIO: Try to post a POSTED sale
        EXPECTED: HTTP 400
        """
        # Create and post a sale
        product = factory.create_product(store_id=1)
        product_id = product.get("id") or product.get("product", {}).get("id")
        factory.receive_inventory(store_id=1, product_id=product_id, quantity=10, unit_cost_cents=500)

        sale = factory.create_sale(store_id=1)
        sale_id = sale.get("sale", {}).get("id")
        factory.add_sale_line(sale_id, product_id, 1)
        factory.post_sale(sale_id)

        # Try to post again
        response = admin_client.post(f"/api/sales/{sale_id}/post")

        assert_response(
            response, 400,
            scenario="Post already-posted sale",
            code_location="backend/app/services/sales_service.py:post_sale"
        )


class TestSaleVoiding:
    """Sale void tests."""

    @pytest.mark.sales
    def test_void_posted_sale(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test voiding a posted sale.

        SCENARIO: Void a posted sale
        EXPECTED: HTTP 200, status becomes VOIDED, inventory restored
        """
        # Setup and post sale
        product = factory.create_product(store_id=1)
        product_id = product.get("id") or product.get("product", {}).get("id")
        factory.receive_inventory(store_id=1, product_id=product_id, quantity=10, unit_cost_cents=500)

        sale = factory.create_sale(store_id=1)
        sale_id = sale.get("sale", {}).get("id")
        factory.add_sale_line(sale_id, product_id, 3)
        factory.post_sale(sale_id)

        # Get inventory after post
        inv_after_post = admin_client.get(f"/api/inventory/{product_id}/summary", params={"store_id": 1}).json()

        # Void sale
        response = admin_client.post(f"/api/sales/{sale_id}/void", json={
            "reason": "Customer changed mind"
        })

        assert_response(
            response, 200,
            scenario="Void posted sale",
            code_location="backend/app/routes/sales.py:void_sale_route"
        )

        data = response.json()
        sale = data.get("sale", {})

        if sale.get("status") != "VOIDED":
            raise TestFailure(
                scenario="Voided sale should have VOIDED status",
                expected="status = VOIDED",
                actual=f"status = {sale.get('status')}",
                likely_cause="Sale status not updated on void",
                code_location="backend/app/services/sales_service.py:void_sale",
                response=response
            )

    @pytest.mark.sales
    def test_void_requires_reason(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test that void requires a reason.

        SCENARIO: Void without providing reason
        EXPECTED: HTTP 400
        """
        # Create and post sale
        product = factory.create_product(store_id=1)
        product_id = product.get("id") or product.get("product", {}).get("id")
        factory.receive_inventory(store_id=1, product_id=product_id, quantity=10, unit_cost_cents=500)

        sale = factory.create_sale(store_id=1)
        sale_id = sale.get("sale", {}).get("id")
        factory.add_sale_line(sale_id, product_id, 1)
        factory.post_sale(sale_id)

        # Try to void without reason
        response = admin_client.post(f"/api/sales/{sale_id}/void", json={})

        assert_response(
            response, 400,
            scenario="Void sale without reason",
            code_location="backend/app/routes/sales.py:void_sale_route"
        )

    @pytest.mark.sales
    @pytest.mark.rbac
    def test_cashier_cannot_void_sale(self, cashier_client: APIClient):
        """
        Test that cashier cannot void sales.

        SCENARIO: Cashier tries to void a sale
        EXPECTED: HTTP 403 (requires VOID_SALE permission)
        """
        response = cashier_client.post("/api/sales/99999/void", json={
            "reason": "Test"
        })

        assert_response(
            response, 403,
            scenario="Cashier voiding sale (forbidden)",
            code_location="backend/app/routes/sales.py:void_sale_route"
        )


class TestPayments:
    """Payment processing tests."""

    @pytest.mark.smoke
    @pytest.mark.payments
    def test_add_cash_payment(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test adding a cash payment to a sale.

        SCENARIO: Pay for sale with cash
        EXPECTED: HTTP 201 with payment and summary
        """
        # Create and post sale
        product = factory.create_product(store_id=1, price_cents=1000)
        product_id = product.get("id") or product.get("product", {}).get("id")
        factory.receive_inventory(store_id=1, product_id=product_id, quantity=10, unit_cost_cents=500)

        sale = factory.create_sale(store_id=1)
        sale_id = sale.get("sale", {}).get("id")
        factory.add_sale_line(sale_id, product_id, 2)  # 2000 cents total
        factory.post_sale(sale_id)

        # Add payment
        response = admin_client.post("/api/payments/", json={
            "sale_id": sale_id,
            "tender_type": "CASH",
            "amount_cents": 2000
        })

        assert_response(
            response, 201,
            scenario="Add cash payment",
            code_location="backend/app/routes/payments.py:add_payment_route"
        )

        data = response.json()

        if "payment" not in data:
            raise TestFailure(
                scenario="Payment response should have payment object",
                expected="Response has 'payment' key",
                actual=f"Response keys: {list(data.keys())}",
                likely_cause="Response format changed",
                code_location="backend/app/routes/payments.py:add_payment_route",
                response=response
            )

        if "summary" not in data:
            raise TestFailure(
                scenario="Payment response should have summary",
                expected="Response has 'summary' key",
                actual=f"Response keys: {list(data.keys())}",
                likely_cause="Response format changed",
                code_location="backend/app/routes/payments.py:add_payment_route",
                response=response
            )

    @pytest.mark.payments
    def test_change_calculation(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test automatic change calculation for overpayment.

        SCENARIO: Pay with more cash than sale total
        EXPECTED: Change due calculated correctly
        """
        # Create $20.00 sale
        product = factory.create_product(store_id=1, price_cents=2000)
        product_id = product.get("id") or product.get("product", {}).get("id")
        factory.receive_inventory(store_id=1, product_id=product_id, quantity=10, unit_cost_cents=1000)

        sale = factory.create_sale(store_id=1)
        sale_id = sale.get("sale", {}).get("id")
        factory.add_sale_line(sale_id, product_id, 1)
        factory.post_sale(sale_id)

        # Pay $25.00 (expect $5 change)
        response = admin_client.post("/api/payments/", json={
            "sale_id": sale_id,
            "tender_type": "CASH",
            "amount_cents": 2500
        })

        data = response.json()
        summary = data.get("summary", {})

        change_due = summary.get("change_due_cents")
        if change_due != 500:
            raise TestFailure(
                scenario="Change should be calculated on overpayment",
                expected="change_due_cents = 500",
                actual=f"change_due_cents = {change_due}",
                likely_cause="Change calculation error",
                code_location="backend/app/services/payment_service.py:add_payment",
                response=response
            )

    @pytest.mark.payments
    def test_split_payment(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test split payment (multiple tenders).

        SCENARIO: Pay with cash and card
        EXPECTED: Both payments recorded, sale fully paid
        """
        # Create $30.00 sale
        product = factory.create_product(store_id=1, price_cents=3000)
        product_id = product.get("id") or product.get("product", {}).get("id")
        factory.receive_inventory(store_id=1, product_id=product_id, quantity=10, unit_cost_cents=1500)

        sale = factory.create_sale(store_id=1)
        sale_id = sale.get("sale", {}).get("id")
        factory.add_sale_line(sale_id, product_id, 1)
        factory.post_sale(sale_id)

        # Pay $10 cash
        admin_client.post("/api/payments/", json={
            "sale_id": sale_id,
            "tender_type": "CASH",
            "amount_cents": 1000
        })

        # Check partial payment status
        summary_response = admin_client.get(f"/api/payments/sales/{sale_id}/summary")
        summary = summary_response.json()

        if summary.get("payment_status") != "PARTIAL":
            raise TestFailure(
                scenario="Partial payment should show PARTIAL status",
                expected="payment_status = PARTIAL",
                actual=f"payment_status = {summary.get('payment_status')}",
                likely_cause="Payment status not updated correctly",
                code_location="backend/app/services/payment_service.py:get_payment_summary"
            )

        # Pay remaining $20 with card
        response = admin_client.post("/api/payments/", json={
            "sale_id": sale_id,
            "tender_type": "CARD",
            "amount_cents": 2000,
            "reference_number": "AUTH-12345"
        })

        data = response.json()
        summary = data.get("summary", {})

        if summary.get("payment_status") != "PAID":
            raise TestFailure(
                scenario="Fully paid sale should show PAID status",
                expected="payment_status = PAID",
                actual=f"payment_status = {summary.get('payment_status')}",
                likely_cause="Payment status not updated to PAID",
                code_location="backend/app/services/payment_service.py:add_payment",
                response=response
            )

    @pytest.mark.payments
    def test_payment_summary(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test payment summary endpoint.

        SCENARIO: Get payment summary for a sale
        EXPECTED: HTTP 200 with totals and status
        """
        # Create sale
        product = factory.create_product(store_id=1, price_cents=1500)
        product_id = product.get("id") or product.get("product", {}).get("id")
        factory.receive_inventory(store_id=1, product_id=product_id, quantity=10, unit_cost_cents=750)

        sale = factory.create_sale(store_id=1)
        sale_id = sale.get("sale", {}).get("id")
        factory.add_sale_line(sale_id, product_id, 2)  # 3000 cents
        factory.post_sale(sale_id)

        response = admin_client.get(f"/api/payments/sales/{sale_id}/summary")

        assert_response(
            response, 200,
            scenario="Get payment summary",
            code_location="backend/app/routes/payments.py:get_payment_summary_route"
        )

        data = response.json()

        required_fields = ["total_due_cents", "payment_status"]
        for field in required_fields:
            if field not in data:
                raise TestFailure(
                    scenario=f"Payment summary should have {field}",
                    expected=f"Field '{field}' in response",
                    actual=f"Response keys: {list(data.keys())}",
                    likely_cause="Summary response format changed",
                    code_location="backend/app/services/payment_service.py:get_payment_summary",
                    response=response
                )

    @pytest.mark.payments
    def test_list_tender_types(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test that various tender types are accepted.

        SCENARIO: Pay with different tender types
        EXPECTED: All valid types accepted
        """
        tender_types = ["CASH", "CARD", "CHECK", "GIFT_CARD", "STORE_CREDIT"]

        for tender_type in tender_types:
            product = factory.create_product(store_id=1, price_cents=100)
            product_id = product.get("id") or product.get("product", {}).get("id")
            factory.receive_inventory(store_id=1, product_id=product_id, quantity=1, unit_cost_cents=50)

            sale = factory.create_sale(store_id=1)
            sale_id = sale.get("sale", {}).get("id")
            factory.add_sale_line(sale_id, product_id, 1)
            factory.post_sale(sale_id)

            response = admin_client.post("/api/payments/", json={
                "sale_id": sale_id,
                "tender_type": tender_type,
                "amount_cents": 100
            })

            if response.status_code != 201:
                raise TestFailure(
                    scenario=f"Tender type {tender_type} should be valid",
                    expected="HTTP 201",
                    actual=f"HTTP {response.status_code}",
                    likely_cause="Tender type validation too strict",
                    code_location="backend/app/services/payment_service.py:add_payment",
                    response=response
                )


class TestPaymentVoidRefund:
    """Payment void and refund tests."""

    @pytest.mark.payments
    def test_void_payment(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test voiding a payment.

        SCENARIO: Void a payment (mistake correction)
        EXPECTED: HTTP 200, payment voided
        """
        # Create sale and payment
        product = factory.create_product(store_id=1, price_cents=1000)
        product_id = product.get("id") or product.get("product", {}).get("id")
        factory.receive_inventory(store_id=1, product_id=product_id, quantity=10, unit_cost_cents=500)

        sale = factory.create_sale(store_id=1)
        sale_id = sale.get("sale", {}).get("id")
        factory.add_sale_line(sale_id, product_id, 1)
        factory.post_sale(sale_id)

        payment = factory.add_payment(sale_id, "CASH", 1000)
        payment_id = payment.get("payment", {}).get("id")

        # Void the payment
        response = admin_client.post(f"/api/payments/{payment_id}/void", json={
            "reason": "Wrong amount entered"
        })

        assert_response(
            response, 200,
            scenario="Void payment",
            code_location="backend/app/routes/payments.py:void_payment_route"
        )

    @pytest.mark.payments
    def test_void_payment_requires_reason(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test that void requires a reason.

        SCENARIO: Void payment without reason
        EXPECTED: HTTP 400
        """
        product = factory.create_product(store_id=1, price_cents=1000)
        product_id = product.get("id") or product.get("product", {}).get("id")
        factory.receive_inventory(store_id=1, product_id=product_id, quantity=10, unit_cost_cents=500)

        sale = factory.create_sale(store_id=1)
        sale_id = sale.get("sale", {}).get("id")
        factory.add_sale_line(sale_id, product_id, 1)
        factory.post_sale(sale_id)

        payment = factory.add_payment(sale_id, "CASH", 1000)
        payment_id = payment.get("payment", {}).get("id")

        response = admin_client.post(f"/api/payments/{payment_id}/void", json={})

        assert_response(
            response, 400,
            scenario="Void payment without reason",
            code_location="backend/app/routes/payments.py:void_payment_route"
        )

    @pytest.mark.payments
    @pytest.mark.rbac
    def test_cashier_cannot_void_payment(self, cashier_client: APIClient):
        """
        Test that cashier cannot void payments.

        SCENARIO: Cashier tries to void a payment
        EXPECTED: HTTP 403 (requires VOID_SALE permission)
        """
        response = cashier_client.post("/api/payments/99999/void", json={
            "reason": "Test"
        })

        assert_response(
            response, 403,
            scenario="Cashier voiding payment (forbidden)",
            code_location="backend/app/routes/payments.py:void_payment_route"
        )


class TestSalePermissions:
    """Permission enforcement for sales operations."""

    @pytest.mark.sales
    @pytest.mark.rbac
    def test_cashier_can_create_sale(self, cashier_client: APIClient):
        """
        Test that cashier can create sales.

        SCENARIO: Cashier creates a sale
        EXPECTED: HTTP 201 (has CREATE_SALE permission)
        """
        response = cashier_client.post("/api/sales/", json={
            "store_id": 1
        })

        assert_response(
            response, 201,
            scenario="Cashier creating sale",
            code_location="backend/app/routes/sales.py:create_sale_route"
        )

    @pytest.mark.sales
    @pytest.mark.rbac
    def test_cashier_can_post_sale(self, cashier_client: APIClient, admin_client: APIClient, factory: TestDataFactory):
        """
        Test that cashier can post sales.

        SCENARIO: Cashier posts a sale
        EXPECTED: HTTP 200 (has POST_SALE permission)
        """
        # Admin creates product with inventory (cashier can't)
        product = factory.create_product(store_id=1, price_cents=1000)
        product_id = product.get("id") or product.get("product", {}).get("id")
        factory.receive_inventory(store_id=1, product_id=product_id, quantity=10, unit_cost_cents=500)

        # Cashier creates and posts sale
        sale_response = cashier_client.post("/api/sales/", json={"store_id": 1})
        sale_id = sale_response.json().get("sale", {}).get("id")

        cashier_client.post(f"/api/sales/{sale_id}/lines", json={
            "product_id": product_id,
            "quantity": 1
        })

        response = cashier_client.post(f"/api/sales/{sale_id}/post")

        assert_response(
            response, 200,
            scenario="Cashier posting sale",
            code_location="backend/app/routes/sales.py:post_sale_route"
        )
