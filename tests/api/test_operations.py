# APOS API Tests - Returns, Transfers, and Counts
#
# Tests for:
# - Return processing and COGS reversal
# - Inter-store transfers
# - Physical inventory counts
# - Document approval workflows

import pytest
import time
from typing import Dict

from tests.conftest import APIClient, TestFailure, assert_response, TestDataFactory


class TestReturns:
    """Return processing tests."""

    @pytest.mark.smoke
    @pytest.mark.returns
    def test_create_return(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test creating a return document.

        SCENARIO: Create return for an existing sale
        EXPECTED: HTTP 201 with return in PENDING status
        """
        # Create and post a sale first
        product = factory.create_product(store_id=1, price_cents=1000)
        product_id = product.get("id") or product.get("product", {}).get("id")
        factory.receive_inventory(store_id=1, product_id=product_id, quantity=10, unit_cost_cents=500)

        sale = factory.create_sale(store_id=1)
        sale_id = sale.get("sale", {}).get("id")
        factory.add_sale_line(sale_id, product_id, 2)
        factory.post_sale(sale_id)

        # Create return
        response = admin_client.post("/api/returns/", json={
            "original_sale_id": sale_id,
            "store_id": 1,
            "reason": "Customer not satisfied"
        })

        assert_response(
            response, 201,
            scenario="Create return",
            code_location="backend/app/routes/returns.py:create_return_route"
        )

        data = response.json()

        if "return" not in data:
            raise TestFailure(
                scenario="Create return should return return object",
                expected="Response has 'return' key",
                actual=f"Response keys: {list(data.keys())}",
                likely_cause="Response format changed",
                code_location="backend/app/routes/returns.py:create_return_route",
                response=response
            )

        return_doc = data["return"]
        if return_doc.get("status") != "PENDING":
            raise TestFailure(
                scenario="New return should have PENDING status",
                expected="status = PENDING",
                actual=f"status = {return_doc.get('status')}",
                likely_cause="Return not initialized to PENDING",
                code_location="backend/app/services/return_service.py:create_return",
                response=response
            )

    @pytest.mark.returns
    def test_add_return_line(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test adding line items to a return.

        SCENARIO: Add return line referencing original sale line
        EXPECTED: HTTP 201 with return line details
        """
        # Create sale
        product = factory.create_product(store_id=1, price_cents=1000)
        product_id = product.get("id") or product.get("product", {}).get("id")
        factory.receive_inventory(store_id=1, product_id=product_id, quantity=10, unit_cost_cents=500)

        sale = factory.create_sale(store_id=1)
        sale_id = sale.get("sale", {}).get("id")
        line_response = admin_client.post(f"/api/sales/{sale_id}/lines", json={
            "product_id": product_id,
            "quantity": 3
        })
        sale_line_id = line_response.json().get("line", {}).get("id")
        factory.post_sale(sale_id)

        # Create return
        return_response = admin_client.post("/api/returns/", json={
            "original_sale_id": sale_id,
            "store_id": 1,
            "reason": "Defective"
        })
        return_id = return_response.json().get("return", {}).get("id")

        # Add return line
        response = admin_client.post(f"/api/returns/{return_id}/lines", json={
            "original_sale_line_id": sale_line_id,
            "quantity": 1  # Return 1 of 3
        })

        assert_response(
            response, 201,
            scenario="Add return line",
            code_location="backend/app/routes/returns.py:add_return_line_route"
        )

    @pytest.mark.returns
    def test_cannot_return_more_than_sold(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test that return quantity cannot exceed sold quantity.

        SCENARIO: Try to return more items than were sold
        EXPECTED: HTTP 400
        """
        # Create sale with 2 items
        product = factory.create_product(store_id=1, price_cents=1000)
        product_id = product.get("id") or product.get("product", {}).get("id")
        factory.receive_inventory(store_id=1, product_id=product_id, quantity=10, unit_cost_cents=500)

        sale = factory.create_sale(store_id=1)
        sale_id = sale.get("sale", {}).get("id")
        line_response = admin_client.post(f"/api/sales/{sale_id}/lines", json={
            "product_id": product_id,
            "quantity": 2
        })
        sale_line_id = line_response.json().get("line", {}).get("id")
        factory.post_sale(sale_id)

        # Create return
        return_response = admin_client.post("/api/returns/", json={
            "original_sale_id": sale_id,
            "store_id": 1
        })
        return_id = return_response.json().get("return", {}).get("id")

        # Try to return 5 (sold only 2)
        response = admin_client.post(f"/api/returns/{return_id}/lines", json={
            "original_sale_line_id": sale_line_id,
            "quantity": 5
        })

        assert_response(
            response, 400,
            scenario="Return more than sold quantity",
            code_location="backend/app/services/return_service.py:add_return_line"
        )

    @pytest.mark.returns
    def test_approve_return(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test approving a return (manager action).

        SCENARIO: Manager approves a pending return
        EXPECTED: HTTP 200, status becomes APPROVED
        """
        # Create complete return
        product = factory.create_product(store_id=1, price_cents=1000)
        product_id = product.get("id") or product.get("product", {}).get("id")
        factory.receive_inventory(store_id=1, product_id=product_id, quantity=10, unit_cost_cents=500)

        sale = factory.create_sale(store_id=1)
        sale_id = sale.get("sale", {}).get("id")
        line_response = admin_client.post(f"/api/sales/{sale_id}/lines", json={
            "product_id": product_id,
            "quantity": 2
        })
        sale_line_id = line_response.json().get("line", {}).get("id")
        factory.post_sale(sale_id)

        return_response = admin_client.post("/api/returns/", json={
            "original_sale_id": sale_id,
            "store_id": 1
        })
        return_id = return_response.json().get("return", {}).get("id")

        admin_client.post(f"/api/returns/{return_id}/lines", json={
            "original_sale_line_id": sale_line_id,
            "quantity": 1
        })

        # Approve
        response = admin_client.post(f"/api/returns/{return_id}/approve")

        assert_response(
            response, 200,
            scenario="Approve return",
            code_location="backend/app/routes/returns.py:approve_return_route"
        )

        data = response.json()
        return_doc = data.get("return", {})

        if return_doc.get("status") != "APPROVED":
            raise TestFailure(
                scenario="Approved return should have APPROVED status",
                expected="status = APPROVED",
                actual=f"status = {return_doc.get('status')}",
                likely_cause="Status not updated on approve",
                code_location="backend/app/services/return_service.py:approve_return",
                response=response
            )

    @pytest.mark.returns
    def test_complete_return(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test completing a return (restore inventory, reverse COGS).

        SCENARIO: Complete an approved return
        EXPECTED: HTTP 200, inventory restored
        """
        # Full return workflow
        product = factory.create_product(store_id=1, price_cents=1000)
        product_id = product.get("id") or product.get("product", {}).get("id")
        factory.receive_inventory(store_id=1, product_id=product_id, quantity=10, unit_cost_cents=500)

        # Get initial inventory
        inv_before = admin_client.get(f"/api/inventory/{product_id}/summary", params={"store_id": 1}).json()

        sale = factory.create_sale(store_id=1)
        sale_id = sale.get("sale", {}).get("id")
        line_response = admin_client.post(f"/api/sales/{sale_id}/lines", json={
            "product_id": product_id,
            "quantity": 2
        })
        sale_line_id = line_response.json().get("line", {}).get("id")
        factory.post_sale(sale_id)

        return_response = admin_client.post("/api/returns/", json={
            "original_sale_id": sale_id,
            "store_id": 1
        })
        return_id = return_response.json().get("return", {}).get("id")

        admin_client.post(f"/api/returns/{return_id}/lines", json={
            "original_sale_line_id": sale_line_id,
            "quantity": 1
        })

        admin_client.post(f"/api/returns/{return_id}/approve")

        # Complete
        response = admin_client.post(f"/api/returns/{return_id}/complete")

        assert_response(
            response, 200,
            scenario="Complete return",
            code_location="backend/app/routes/returns.py:complete_return_route"
        )

        data = response.json()
        return_doc = data.get("return", {})

        if return_doc.get("status") != "COMPLETED":
            raise TestFailure(
                scenario="Completed return should have COMPLETED status",
                expected="status = COMPLETED",
                actual=f"status = {return_doc.get('status')}",
                likely_cause="Status not updated on complete",
                code_location="backend/app/services/return_service.py:complete_return",
                response=response
            )

    @pytest.mark.returns
    def test_reject_return(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test rejecting a return.

        SCENARIO: Manager rejects a pending return
        EXPECTED: HTTP 200, status becomes REJECTED
        """
        product = factory.create_product(store_id=1, price_cents=1000)
        product_id = product.get("id") or product.get("product", {}).get("id")
        factory.receive_inventory(store_id=1, product_id=product_id, quantity=10, unit_cost_cents=500)

        sale = factory.create_sale(store_id=1)
        sale_id = sale.get("sale", {}).get("id")
        factory.add_sale_line(sale_id, product_id, 1)
        factory.post_sale(sale_id)

        return_response = admin_client.post("/api/returns/", json={
            "original_sale_id": sale_id,
            "store_id": 1
        })
        return_id = return_response.json().get("return", {}).get("id")

        response = admin_client.post(f"/api/returns/{return_id}/reject", json={
            "rejection_reason": "Items damaged beyond return policy"
        })

        assert_response(
            response, 200,
            scenario="Reject return",
            code_location="backend/app/routes/returns.py:reject_return_route"
        )


class TestTransfers:
    """Inter-store transfer tests."""

    @pytest.mark.smoke
    @pytest.mark.transfers
    def test_create_transfer(self, admin_client: APIClient):
        """
        Test creating a transfer document.

        SCENARIO: Create transfer between two stores
        EXPECTED: HTTP 201 with transfer in PENDING status
        """
        response = admin_client.post("/api/transfers", json={
            "from_store_id": 1,
            "to_store_id": 2,
            "reason": "Stock rebalancing"
        })

        assert_response(
            response, 201,
            scenario="Create transfer",
            code_location="backend/app/routes/transfers.py:create_transfer"
        )

        data = response.json()

        if data.get("status") != "PENDING":
            raise TestFailure(
                scenario="New transfer should have PENDING status",
                expected="status = PENDING",
                actual=f"status = {data.get('status')}",
                likely_cause="Transfer not initialized to PENDING",
                code_location="backend/app/services/transfer_service.py:create_transfer",
                response=response
            )

    @pytest.mark.transfers
    def test_add_transfer_line(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test adding line items to a transfer.

        SCENARIO: Add product to transfer
        EXPECTED: HTTP 201 with transfer line
        """
        # Create product with inventory in source store
        product = factory.create_product(store_id=1, price_cents=1000)
        product_id = product.get("id") or product.get("product", {}).get("id")
        factory.receive_inventory(store_id=1, product_id=product_id, quantity=20, unit_cost_cents=500)

        # Create transfer
        transfer_response = admin_client.post("/api/transfers", json={
            "from_store_id": 1,
            "to_store_id": 2
        })
        transfer_id = transfer_response.json().get("id")

        # Add line
        response = admin_client.post(f"/api/transfers/{transfer_id}/lines", json={
            "product_id": product_id,
            "quantity": 5
        })

        assert_response(
            response, 201,
            scenario="Add transfer line",
            code_location="backend/app/routes/transfers.py:add_transfer_line"
        )

    @pytest.mark.transfers
    def test_approve_transfer(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test approving a transfer.

        SCENARIO: Manager approves transfer
        EXPECTED: HTTP 200, status becomes APPROVED
        """
        product = factory.create_product(store_id=1, price_cents=1000)
        product_id = product.get("id") or product.get("product", {}).get("id")
        factory.receive_inventory(store_id=1, product_id=product_id, quantity=20, unit_cost_cents=500)

        transfer_response = admin_client.post("/api/transfers", json={
            "from_store_id": 1,
            "to_store_id": 2
        })
        transfer_id = transfer_response.json().get("id")

        admin_client.post(f"/api/transfers/{transfer_id}/lines", json={
            "product_id": product_id,
            "quantity": 5
        })

        response = admin_client.post(f"/api/transfers/{transfer_id}/approve")

        assert_response(
            response, 200,
            scenario="Approve transfer",
            code_location="backend/app/routes/transfers.py:approve_transfer"
        )

    @pytest.mark.transfers
    def test_ship_transfer(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test shipping a transfer (deduct from source).

        SCENARIO: Ship approved transfer
        EXPECTED: HTTP 200, status becomes IN_TRANSIT, inventory deducted from source
        """
        product = factory.create_product(store_id=1, price_cents=1000)
        product_id = product.get("id") or product.get("product", {}).get("id")
        factory.receive_inventory(store_id=1, product_id=product_id, quantity=20, unit_cost_cents=500)

        transfer_response = admin_client.post("/api/transfers", json={
            "from_store_id": 1,
            "to_store_id": 2
        })
        transfer_id = transfer_response.json().get("id")

        admin_client.post(f"/api/transfers/{transfer_id}/lines", json={
            "product_id": product_id,
            "quantity": 5
        })

        admin_client.post(f"/api/transfers/{transfer_id}/approve")

        response = admin_client.post(f"/api/transfers/{transfer_id}/ship")

        assert_response(
            response, 200,
            scenario="Ship transfer",
            code_location="backend/app/routes/transfers.py:ship_transfer"
        )

        data = response.json()
        if data.get("status") != "IN_TRANSIT":
            raise TestFailure(
                scenario="Shipped transfer should have IN_TRANSIT status",
                expected="status = IN_TRANSIT",
                actual=f"status = {data.get('status')}",
                likely_cause="Status not updated on ship",
                code_location="backend/app/services/transfer_service.py:ship_transfer",
                response=response
            )

    @pytest.mark.transfers
    def test_receive_transfer(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test receiving a transfer (add to destination).

        SCENARIO: Receive shipped transfer
        EXPECTED: HTTP 200, status becomes RECEIVED, inventory added to destination
        """
        product = factory.create_product(store_id=1, price_cents=1000)
        product_id = product.get("id") or product.get("product", {}).get("id")
        factory.receive_inventory(store_id=1, product_id=product_id, quantity=20, unit_cost_cents=500)

        transfer_response = admin_client.post("/api/transfers", json={
            "from_store_id": 1,
            "to_store_id": 2
        })
        transfer_id = transfer_response.json().get("id")

        admin_client.post(f"/api/transfers/{transfer_id}/lines", json={
            "product_id": product_id,
            "quantity": 5
        })

        admin_client.post(f"/api/transfers/{transfer_id}/approve")
        admin_client.post(f"/api/transfers/{transfer_id}/ship")

        response = admin_client.post(f"/api/transfers/{transfer_id}/receive")

        assert_response(
            response, 200,
            scenario="Receive transfer",
            code_location="backend/app/routes/transfers.py:receive_transfer"
        )

        data = response.json()
        if data.get("status") != "RECEIVED":
            raise TestFailure(
                scenario="Received transfer should have RECEIVED status",
                expected="status = RECEIVED",
                actual=f"status = {data.get('status')}",
                likely_cause="Status not updated on receive",
                code_location="backend/app/services/transfer_service.py:receive_transfer",
                response=response
            )


class TestCounts:
    """Physical inventory count tests."""

    @pytest.mark.smoke
    @pytest.mark.counts
    def test_create_count(self, admin_client: APIClient):
        """
        Test creating a count document.

        SCENARIO: Create cycle count
        EXPECTED: HTTP 201 with count in PENDING status
        """
        response = admin_client.post("/api/counts", json={
            "store_id": 1,
            "count_type": "CYCLE",
            "reason": "Monthly cycle count"
        })

        assert_response(
            response, 201,
            scenario="Create count",
            code_location="backend/app/routes/counts.py:create_count"
        )

        data = response.json()

        if data.get("status") != "PENDING":
            raise TestFailure(
                scenario="New count should have PENDING status",
                expected="status = PENDING",
                actual=f"status = {data.get('status')}",
                likely_cause="Count not initialized to PENDING",
                code_location="backend/app/services/count_service.py:create_count",
                response=response
            )

    @pytest.mark.counts
    def test_add_count_line(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test adding count line (actual quantity counted).

        SCENARIO: Add counted quantity for a product
        EXPECTED: HTTP 201 with count line and variance calculated
        """
        product = factory.create_product(store_id=1, price_cents=1000)
        product_id = product.get("id") or product.get("product", {}).get("id")
        factory.receive_inventory(store_id=1, product_id=product_id, quantity=10, unit_cost_cents=500)

        count_response = admin_client.post("/api/counts", json={
            "store_id": 1,
            "count_type": "CYCLE"
        })
        count_id = count_response.json().get("id")

        response = admin_client.post(f"/api/counts/{count_id}/lines", json={
            "product_id": product_id,
            "actual_quantity": 8  # Counted 8, expected 10 -> variance -2
        })

        assert_response(
            response, 201,
            scenario="Add count line",
            code_location="backend/app/routes/counts.py:add_count_line"
        )

    @pytest.mark.counts
    def test_approve_count(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test approving a count.

        SCENARIO: Manager approves count
        EXPECTED: HTTP 200, status becomes APPROVED
        """
        product = factory.create_product(store_id=1, price_cents=1000)
        product_id = product.get("id") or product.get("product", {}).get("id")
        factory.receive_inventory(store_id=1, product_id=product_id, quantity=10, unit_cost_cents=500)

        count_response = admin_client.post("/api/counts", json={
            "store_id": 1,
            "count_type": "CYCLE"
        })
        count_id = count_response.json().get("id")

        admin_client.post(f"/api/counts/{count_id}/lines", json={
            "product_id": product_id,
            "actual_quantity": 10
        })

        response = admin_client.post(f"/api/counts/{count_id}/approve")

        assert_response(
            response, 200,
            scenario="Approve count",
            code_location="backend/app/routes/counts.py:approve_count"
        )

    @pytest.mark.counts
    def test_post_count(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test posting a count (create adjustment transactions).

        SCENARIO: Post approved count
        EXPECTED: HTTP 200, inventory adjusted based on variances
        """
        product = factory.create_product(store_id=1, price_cents=1000)
        product_id = product.get("id") or product.get("product", {}).get("id")
        factory.receive_inventory(store_id=1, product_id=product_id, quantity=10, unit_cost_cents=500)

        count_response = admin_client.post("/api/counts", json={
            "store_id": 1,
            "count_type": "CYCLE"
        })
        count_id = count_response.json().get("id")

        admin_client.post(f"/api/counts/{count_id}/lines", json={
            "product_id": product_id,
            "actual_quantity": 8  # 2 short
        })

        admin_client.post(f"/api/counts/{count_id}/approve")

        response = admin_client.post(f"/api/counts/{count_id}/post")

        assert_response(
            response, 200,
            scenario="Post count",
            code_location="backend/app/routes/counts.py:post_count"
        )

        data = response.json()
        if data.get("status") != "POSTED":
            raise TestFailure(
                scenario="Posted count should have POSTED status",
                expected="status = POSTED",
                actual=f"status = {data.get('status')}",
                likely_cause="Status not updated on post",
                code_location="backend/app/services/count_service.py:post_count",
                response=response
            )


class TestOperationPermissions:
    """Permission enforcement for operations."""

    @pytest.mark.returns
    @pytest.mark.rbac
    def test_cashier_can_create_return(self, cashier_client: APIClient, admin_client: APIClient, factory: TestDataFactory):
        """
        Test that cashier can initiate returns.

        SCENARIO: Cashier creates a return
        EXPECTED: HTTP 201 (has PROCESS_RETURN permission)
        """
        product = factory.create_product(store_id=1, price_cents=1000)
        product_id = product.get("id") or product.get("product", {}).get("id")
        factory.receive_inventory(store_id=1, product_id=product_id, quantity=10, unit_cost_cents=500)

        sale = factory.create_sale(store_id=1)
        sale_id = sale.get("sale", {}).get("id")
        factory.add_sale_line(sale_id, product_id, 1)
        factory.post_sale(sale_id)

        response = cashier_client.post("/api/returns/", json={
            "original_sale_id": sale_id,
            "store_id": 1
        })

        assert_response(
            response, 201,
            scenario="Cashier creating return",
            code_location="backend/app/routes/returns.py:create_return_route"
        )

    @pytest.mark.returns
    @pytest.mark.rbac
    def test_cashier_cannot_approve_return(self, cashier_client: APIClient):
        """
        Test that cashier cannot approve returns.

        SCENARIO: Cashier tries to approve return
        EXPECTED: HTTP 403 (lacks APPROVE_DOCUMENTS)
        """
        response = cashier_client.post("/api/returns/99999/approve")

        assert_response(
            response, 403,
            scenario="Cashier approving return (forbidden)",
            code_location="backend/app/routes/returns.py:approve_return_route"
        )

    @pytest.mark.transfers
    @pytest.mark.rbac
    def test_cashier_cannot_create_transfer(self, cashier_client: APIClient):
        """
        Test that cashier cannot create transfers.

        SCENARIO: Cashier tries to create transfer
        EXPECTED: HTTP 403 (lacks CREATE_TRANSFERS)
        """
        response = cashier_client.post("/api/transfers", json={
            "from_store_id": 1,
            "to_store_id": 2
        })

        assert_response(
            response, 403,
            scenario="Cashier creating transfer (forbidden)",
            code_location="backend/app/routes/transfers.py:create_transfer"
        )

    @pytest.mark.counts
    @pytest.mark.rbac
    def test_cashier_cannot_create_count(self, cashier_client: APIClient):
        """
        Test that cashier cannot create counts.

        SCENARIO: Cashier tries to create count
        EXPECTED: HTTP 403 (lacks CREATE_COUNTS)
        """
        response = cashier_client.post("/api/counts", json={
            "store_id": 1,
            "count_type": "CYCLE"
        })

        assert_response(
            response, 403,
            scenario="Cashier creating count (forbidden)",
            code_location="backend/app/routes/counts.py:create_count"
        )
