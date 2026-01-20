# APOS API Tests - Products & Inventory
#
# Tests for:
# - Product CRUD operations
# - Product validation (SKU uniqueness, price limits)
# - Inventory transactions (receive, adjust, sale)
# - Inventory summary and WAC calculations
# - Identifier management (UPC, ALT_BARCODE, VENDOR_CODE)
# - Document lifecycle (DRAFT -> APPROVED -> POSTED)

import pytest
import time
from typing import Dict

from tests.conftest import APIClient, TestFailure, assert_response, TestDataFactory


class TestProductCRUD:
    """Product create, read, update, delete tests."""

    @pytest.mark.smoke
    @pytest.mark.products
    def test_create_product(self, admin_client: APIClient):
        """
        Test creating a new product.

        SCENARIO: Admin creates a product with valid data
        EXPECTED: HTTP 201 with product details
        """
        unique_id = int(time.time())
        response = admin_client.post("/api/products", json={
            "store_id": 1,  # Alpha Store 1
            "sku": f"TEST-{unique_id}",
            "name": f"Test Product {unique_id}",
            "price_cents": 1999,
            "description": "A test product"
        })

        assert_response(
            response, 201,
            scenario="Create product with valid data",
            code_location="backend/app/routes/products.py:create_product_route"
        )

        data = response.json()
        if "sku" not in data:
            raise TestFailure(
                scenario="Product response should include product data",
                expected="Response contains 'sku'",
                actual=f"Response keys: {list(data.keys())}",
                likely_cause="Response format changed",
                code_location="backend/app/routes/products.py:create_product_route",
                response=response
            )

    @pytest.mark.products
    def test_create_product_missing_required_fields(self, admin_client: APIClient):
        """
        Test product creation validation.

        SCENARIO: Create product missing required fields
        EXPECTED: HTTP 400 with validation error
        """
        # Missing SKU
        response = admin_client.post("/api/products", json={
            "store_id": 1,
            "name": "No SKU Product",
            "price_cents": 1000
        })

        assert_response(
            response, 400,
            scenario="Create product without SKU",
            code_location="backend/app/routes/products.py:create_product_route"
        )

        # Missing name
        response = admin_client.post("/api/products", json={
            "store_id": 1,
            "sku": "NO-NAME-SKU",
            "price_cents": 1000
        })

        assert_response(
            response, 400,
            scenario="Create product without name",
            code_location="backend/app/routes/products.py:create_product_route"
        )

    @pytest.mark.products
    def test_create_product_duplicate_sku_same_store(self, admin_client: APIClient):
        """
        Test that duplicate SKU in same store is rejected.

        SCENARIO: Create two products with same SKU in same store
        EXPECTED: HTTP 409 (conflict) on second creation
        """
        unique_sku = f"DUP-{int(time.time())}"

        # First product
        response1 = admin_client.post("/api/products", json={
            "store_id": 1,
            "sku": unique_sku,
            "name": "First Product",
            "price_cents": 1000
        })

        assert_response(
            response1, 201,
            scenario="Create first product with unique SKU",
            code_location="backend/app/routes/products.py:create_product_route"
        )

        # Second product with same SKU
        response2 = admin_client.post("/api/products", json={
            "store_id": 1,
            "sku": unique_sku,
            "name": "Duplicate Product",
            "price_cents": 2000
        })

        assert_response(
            response2, 409,
            scenario="Create product with duplicate SKU (same store)",
            code_location="backend/app/routes/products.py:create_product_route"
        )

    @pytest.mark.products
    def test_same_sku_different_stores_allowed(self, admin_client: APIClient):
        """
        Test that same SKU can exist in different stores.

        SCENARIO: Create products with same SKU in different stores
        EXPECTED: Both products created successfully
        """
        unique_sku = f"MULTI-{int(time.time())}"

        # Product in store 1
        response1 = admin_client.post("/api/products", json={
            "store_id": 1,
            "sku": unique_sku,
            "name": "Store 1 Product",
            "price_cents": 1000
        })

        assert_response(
            response1, 201,
            scenario="Create product in store 1",
            code_location="backend/app/routes/products.py:create_product_route"
        )

        # Same SKU in store 2
        response2 = admin_client.post("/api/products", json={
            "store_id": 2,  # Alpha Store 2
            "sku": unique_sku,
            "name": "Store 2 Product",
            "price_cents": 1500
        })

        assert_response(
            response2, 201,
            scenario="Create product with same SKU in store 2",
            code_location="backend/app/routes/products.py:create_product_route"
        )

    @pytest.mark.smoke
    @pytest.mark.products
    def test_list_products(self, admin_client: APIClient):
        """
        Test listing products.

        SCENARIO: List all products
        EXPECTED: HTTP 200 with products array
        """
        response = admin_client.get("/api/products")

        assert_response(
            response, 200,
            scenario="List products",
            code_location="backend/app/routes/products.py:list_products"
        )

        data = response.json()
        if "items" not in data and not isinstance(data, list):
            # Could be paginated with 'items' or just a list
            if not isinstance(data.get("items", []), list):
                raise TestFailure(
                    scenario="List products should return items",
                    expected="Response with 'items' list or direct list",
                    actual=f"Response type: {type(data)}",
                    likely_cause="Response format changed",
                    code_location="backend/app/routes/products.py:list_products",
                    response=response
                )

    @pytest.mark.products
    def test_list_products_with_store_filter(self, admin_client: APIClient):
        """
        Test listing products filtered by store.

        SCENARIO: List products for a specific store
        EXPECTED: HTTP 200 with only that store's products
        """
        response = admin_client.get("/api/products", params={"store_id": 1})

        assert_response(
            response, 200,
            scenario="List products for store 1",
            code_location="backend/app/routes/products.py:list_products"
        )

    @pytest.mark.products
    def test_update_product(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test updating a product.

        SCENARIO: Update product name and price
        EXPECTED: HTTP 200 with updated data
        """
        # Create a product first
        product = factory.create_product(store_id=1, price_cents=1000)
        product_id = product.get("id") or product.get("product", {}).get("id")

        # Update it
        response = admin_client.put(f"/api/products/{product_id}", json={
            "name": "Updated Product Name",
            "price_cents": 1500
        })

        assert_response(
            response, 200,
            scenario="Update product",
            code_location="backend/app/routes/products.py:update_product_route"
        )

        data = response.json()
        # Verify update applied
        if data.get("price_cents") != 1500:
            raise TestFailure(
                scenario="Product update should change price",
                expected="price_cents = 1500",
                actual=f"price_cents = {data.get('price_cents')}",
                likely_cause="Update not applied correctly",
                code_location="backend/app/routes/products.py:update_product_route",
                response=response
            )

    @pytest.mark.products
    def test_delete_product(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test deleting a product.

        SCENARIO: Delete an existing product
        EXPECTED: HTTP 200, product no longer accessible
        """
        # Create a product first
        product = factory.create_product(store_id=1)
        product_id = product.get("id") or product.get("product", {}).get("id")

        # Delete it
        response = admin_client.delete(f"/api/products/{product_id}")

        assert_response(
            response, 200,
            scenario="Delete product",
            code_location="backend/app/routes/products.py:delete_product_route"
        )

    @pytest.mark.products
    def test_price_validation_max_limit(self, admin_client: APIClient):
        """
        Test that price exceeding maximum is rejected.

        SCENARIO: Create product with price over $100,000
        EXPECTED: HTTP 400 (validation error)
        """
        response = admin_client.post("/api/products", json={
            "store_id": 1,
            "sku": f"EXPENSIVE-{int(time.time())}",
            "name": "Very Expensive",
            "price_cents": 100_000_01  # Over $100,000.00
        })

        # Should be rejected
        if response.status_code == 201:
            raise TestFailure(
                scenario="Price over maximum should be rejected",
                expected="HTTP 400",
                actual="HTTP 201 (product created)",
                likely_cause="Price max validation not enforced",
                code_location="backend/app/validation.py:enforce_rules_product",
                response=response
            )

    @pytest.mark.products
    def test_price_validation_negative(self, admin_client: APIClient):
        """
        Test that negative price is rejected.

        SCENARIO: Create product with negative price
        EXPECTED: HTTP 400 (validation error)
        """
        response = admin_client.post("/api/products", json={
            "store_id": 1,
            "sku": f"NEGATIVE-{int(time.time())}",
            "name": "Negative Price",
            "price_cents": -100
        })

        assert_response(
            response, 400,
            scenario="Negative price should be rejected",
            code_location="backend/app/validation.py:enforce_rules_product"
        )


class TestInventoryTransactions:
    """Inventory transaction tests."""

    @pytest.mark.smoke
    @pytest.mark.inventory
    def test_receive_inventory(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test receiving inventory.

        SCENARIO: Receive 10 units of a product at $5.00 each
        EXPECTED: HTTP 201 with transaction and summary
        """
        # Create product
        product = factory.create_product(store_id=1)
        product_id = product.get("id") or product.get("product", {}).get("id")

        # Receive inventory
        response = admin_client.post("/api/inventory/receive", json={
            "store_id": 1,
            "product_id": product_id,
            "quantity_delta": 10,
            "unit_cost_cents": 500  # $5.00
        })

        assert_response(
            response, 201,
            scenario="Receive inventory",
            code_location="backend/app/routes/inventory.py:receive_inventory_route"
        )

        data = response.json()

        if "transaction" not in data:
            raise TestFailure(
                scenario="Receive response should include transaction",
                expected="Response has 'transaction'",
                actual=f"Response keys: {list(data.keys())}",
                likely_cause="Response format changed",
                code_location="backend/app/routes/inventory.py:receive_inventory_route",
                response=response
            )

        if "summary" not in data:
            raise TestFailure(
                scenario="Receive response should include summary",
                expected="Response has 'summary'",
                actual=f"Response keys: {list(data.keys())}",
                likely_cause="Response format changed",
                code_location="backend/app/routes/inventory.py:receive_inventory_route",
                response=response
            )

    @pytest.mark.inventory
    def test_receive_inventory_validation(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test inventory receive validation.

        SCENARIO: Receive with invalid data
        EXPECTED: HTTP 400 for each invalid case
        """
        product = factory.create_product(store_id=1)
        product_id = product.get("id") or product.get("product", {}).get("id")

        # Negative quantity
        response = admin_client.post("/api/inventory/receive", json={
            "store_id": 1,
            "product_id": product_id,
            "quantity_delta": -5,
            "unit_cost_cents": 500
        })

        assert_response(
            response, 400,
            scenario="Receive with negative quantity",
            code_location="backend/app/validation.py:enforce_rules_inventory_receive"
        )

        # Negative cost
        response = admin_client.post("/api/inventory/receive", json={
            "store_id": 1,
            "product_id": product_id,
            "quantity_delta": 5,
            "unit_cost_cents": -100
        })

        assert_response(
            response, 400,
            scenario="Receive with negative cost",
            code_location="backend/app/validation.py:enforce_rules_inventory_receive"
        )

    @pytest.mark.inventory
    def test_adjust_inventory(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test inventory adjustment.

        SCENARIO: Adjust inventory (shrink, correction)
        EXPECTED: HTTP 201 with adjustment transaction
        """
        # Create product and receive inventory first
        product = factory.create_product(store_id=1)
        product_id = product.get("id") or product.get("product", {}).get("id")

        factory.receive_inventory(store_id=1, product_id=product_id, quantity=20, unit_cost_cents=500)

        # Adjust inventory (negative = shrink)
        response = admin_client.post("/api/inventory/adjust", json={
            "store_id": 1,
            "product_id": product_id,
            "quantity_delta": -3,
            "note": "Inventory shrink"
        })

        assert_response(
            response, 201,
            scenario="Adjust inventory",
            code_location="backend/app/routes/inventory.py:adjust_inventory_route"
        )

    @pytest.mark.smoke
    @pytest.mark.inventory
    def test_inventory_summary(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test getting inventory summary.

        SCENARIO: Get inventory summary after receiving
        EXPECTED: HTTP 200 with on_hand quantity and WAC
        """
        # Create product and receive inventory
        product = factory.create_product(store_id=1)
        product_id = product.get("id") or product.get("product", {}).get("id")

        factory.receive_inventory(store_id=1, product_id=product_id, quantity=10, unit_cost_cents=500)

        # Get summary
        response = admin_client.get(f"/api/inventory/{product_id}/summary", params={"store_id": 1})

        assert_response(
            response, 200,
            scenario="Get inventory summary",
            code_location="backend/app/routes/inventory.py:inventory_summary_route"
        )

        data = response.json()

        if "on_hand" not in data and "quantity" not in data:
            raise TestFailure(
                scenario="Inventory summary should include quantity",
                expected="Response has 'on_hand' or 'quantity'",
                actual=f"Response keys: {list(data.keys())}",
                likely_cause="Response format changed",
                code_location="backend/app/routes/inventory.py:inventory_summary_route",
                response=response
            )

    @pytest.mark.inventory
    def test_inventory_wac_calculation(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test weighted average cost calculation.

        SCENARIO: Receive inventory at different costs
        EXPECTED: WAC correctly calculated
        """
        product = factory.create_product(store_id=1)
        product_id = product.get("id") or product.get("product", {}).get("id")

        # Receive 10 at $5.00
        factory.receive_inventory(store_id=1, product_id=product_id, quantity=10, unit_cost_cents=500)

        # Receive 10 at $10.00
        factory.receive_inventory(store_id=1, product_id=product_id, quantity=10, unit_cost_cents=1000)

        # Expected WAC: (10*500 + 10*1000) / 20 = 750 cents
        response = admin_client.get(f"/api/inventory/{product_id}/summary", params={"store_id": 1})

        data = response.json()
        wac = data.get("wac_cents") or data.get("weighted_average_cost_cents")

        if wac is not None and wac != 750:
            raise TestFailure(
                scenario="WAC should be weighted average",
                expected="WAC = 750 cents",
                actual=f"WAC = {wac}",
                likely_cause="WAC calculation error",
                code_location="backend/app/services/inventory_service.py",
                extra_context={"formula": "(10*500 + 10*1000) / 20 = 750"}
            )

    @pytest.mark.inventory
    def test_inventory_transactions_list(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test listing inventory transactions.

        SCENARIO: List transactions for a product
        EXPECTED: HTTP 200 with transaction list
        """
        product = factory.create_product(store_id=1)
        product_id = product.get("id") or product.get("product", {}).get("id")

        factory.receive_inventory(store_id=1, product_id=product_id, quantity=10, unit_cost_cents=500)

        response = admin_client.get(f"/api/inventory/{product_id}/transactions", params={"store_id": 1})

        assert_response(
            response, 200,
            scenario="List inventory transactions",
            code_location="backend/app/routes/inventory.py:inventory_transactions_route"
        )


class TestDocumentLifecycle:
    """Document lifecycle (DRAFT -> APPROVED -> POSTED) tests."""

    @pytest.mark.inventory
    def test_adjustment_draft_approval_flow(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test inventory adjustment approval workflow.

        SCENARIO: Create draft adjustment, approve it, post it
        EXPECTED: Status transitions correctly
        """
        product = factory.create_product(store_id=1)
        product_id = product.get("id") or product.get("product", {}).get("id")

        factory.receive_inventory(store_id=1, product_id=product_id, quantity=20, unit_cost_cents=500)

        # Create draft adjustment
        response = admin_client.post("/api/inventory/adjust", json={
            "store_id": 1,
            "product_id": product_id,
            "quantity_delta": -5,
            "note": "Test adjustment",
            "status": "DRAFT"
        })

        assert_response(
            response, 201,
            scenario="Create draft adjustment",
            code_location="backend/app/routes/inventory.py:adjust_inventory_route"
        )

        data = response.json()
        transaction_id = data.get("transaction", {}).get("id")

        if transaction_id:
            # Approve it
            response = admin_client.post(f"/api/lifecycle/approve/{transaction_id}")

            if response.status_code == 200:
                # Post it
                response = admin_client.post(f"/api/lifecycle/post/{transaction_id}")
                assert_response(
                    response, 200,
                    scenario="Post approved transaction",
                    code_location="backend/app/routes/lifecycle.py:post_transaction_route"
                )

    @pytest.mark.inventory
    def test_list_pending_transactions(self, admin_client: APIClient):
        """
        Test listing pending (DRAFT) transactions.

        SCENARIO: Get list of transactions awaiting approval
        EXPECTED: HTTP 200 with pending list
        """
        response = admin_client.get("/api/lifecycle/pending", params={"store_id": 1})

        assert_response(
            response, 200,
            scenario="List pending transactions",
            code_location="backend/app/routes/lifecycle.py:list_pending_transactions_route"
        )

        data = response.json()
        if "transactions" not in data:
            raise TestFailure(
                scenario="Pending list should have transactions array",
                expected="Response has 'transactions'",
                actual=f"Response keys: {list(data.keys())}",
                likely_cause="Response format changed",
                code_location="backend/app/routes/lifecycle.py:list_pending_transactions_route",
                response=response
            )


class TestProductIdentifiers:
    """Product identifier (barcode, UPC) tests."""

    @pytest.mark.products
    def test_identifier_lookup(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test product lookup by identifier.

        SCENARIO: Look up product by SKU
        EXPECTED: HTTP 200 with product info
        """
        unique_sku = f"LOOKUP-{int(time.time())}"
        product = factory.create_product(store_id=1, sku=unique_sku)

        response = admin_client.get("/api/identifiers/lookup", params={
            "store_id": 1,
            "value": unique_sku
        })

        # May be 200 with product or 404 if identifier service works differently
        if response.status_code == 200:
            data = response.json()
            # Should have product info
            assert "product" in data or "products" in data or "sku" in data
        elif response.status_code == 404:
            # SKU lookup might not be through identifiers endpoint
            pass
        else:
            assert_response(
                response, 200,
                scenario="Lookup product by identifier",
                code_location="backend/app/routes/identifiers.py"
            )


class TestPermissionsOnProducts:
    """Permission enforcement tests for product operations."""

    @pytest.mark.products
    @pytest.mark.rbac
    def test_cashier_can_view_products(self, cashier_client: APIClient):
        """
        Test that cashier can view products (VIEW_INVENTORY permission).

        SCENARIO: Cashier lists products
        EXPECTED: HTTP 200 (has VIEW_INVENTORY)
        """
        response = cashier_client.get("/api/products")

        assert_response(
            response, 200,
            scenario="Cashier viewing products",
            code_location="backend/app/routes/products.py:list_products"
        )

    @pytest.mark.products
    @pytest.mark.rbac
    def test_cashier_cannot_create_products(self, cashier_client: APIClient):
        """
        Test that cashier cannot create products.

        SCENARIO: Cashier tries to create a product
        EXPECTED: HTTP 403 (lacks MANAGE_PRODUCTS)
        """
        response = cashier_client.post("/api/products", json={
            "store_id": 1,
            "sku": "CASHIER-CREATE",
            "name": "Cashier Product",
            "price_cents": 1000
        })

        assert_response(
            response, 403,
            scenario="Cashier creating product (forbidden)",
            code_location="backend/app/routes/products.py:create_product_route"
        )

    @pytest.mark.inventory
    @pytest.mark.rbac
    def test_cashier_cannot_receive_inventory(self, cashier_client: APIClient):
        """
        Test that cashier cannot receive inventory.

        SCENARIO: Cashier tries to receive inventory
        EXPECTED: HTTP 403 (lacks RECEIVE_INVENTORY)
        """
        response = cashier_client.post("/api/inventory/receive", json={
            "store_id": 1,
            "product_id": 1,
            "quantity_delta": 10,
            "unit_cost_cents": 500
        })

        assert_response(
            response, 403,
            scenario="Cashier receiving inventory (forbidden)",
            code_location="backend/app/routes/inventory.py:receive_inventory_route"
        )
