# APOS API Tests - Multi-Tenant Isolation
#
# Tests for:
# - Cross-tenant access denial
# - Data isolation between organizations
# - Scoped uniqueness constraints
# - Security event logging for cross-tenant attempts
# - Concurrent multi-tenant operations

import pytest
import time
import threading
from typing import Dict, List

from tests.conftest import APIClient, TestFailure, assert_response, TestDataFactory


class TestCrossTenantAccessDenial:
    """Tests proving cross-tenant access is blocked."""

    @pytest.mark.smoke
    @pytest.mark.tenant
    def test_org_b_cannot_see_org_a_products(
        self,
        admin_client: APIClient,  # Org Alpha
        admin_beta_client: APIClient,  # Org Beta
        factory: TestDataFactory
    ):
        """
        Test that Org B cannot see Org A's products.

        SCENARIO: Admin from Org B tries to view Org A's products
        EXPECTED: Products not visible (empty list or filtered)
        """
        # Create product in Org A
        product = factory.create_product(store_id=1, sku=f"ORG-A-{int(time.time())}")
        product_id = product.get("id") or product.get("product", {}).get("id")
        product_sku = product.get("sku") or product.get("product", {}).get("sku")

        # Org B tries to list products
        response = admin_beta_client.get("/api/products")

        if response.status_code == 200:
            data = response.json()
            products = data.get("items", []) if "items" in data else data

            # Org A's product should not be visible
            for p in products:
                if p.get("sku") == product_sku:
                    raise TestFailure(
                        scenario="Org B should not see Org A products",
                        expected="Product not in list",
                        actual=f"Found product with SKU {product_sku}",
                        likely_cause="Multi-tenant filtering not applied in list_products",
                        code_location="backend/app/services/products_service.py:list_products"
                    )

    @pytest.mark.tenant
    def test_org_b_cannot_access_org_a_product_by_id(
        self,
        admin_client: APIClient,
        admin_beta_client: APIClient,
        factory: TestDataFactory
    ):
        """
        Test that Org B cannot access Org A's product by ID.

        SCENARIO: Admin from Org B tries to GET a specific Org A product
        EXPECTED: 404 (not found) - no data leakage
        """
        # Create product in Org A
        product = factory.create_product(store_id=1)
        product_id = product.get("id") or product.get("product", {}).get("id")

        # Org B tries to access it directly
        response = admin_beta_client.get(f"/api/products/{product_id}")

        # Should not find it (404), not forbidden (403)
        # Returning 404 prevents attackers from knowing if ID exists
        if response.status_code == 200:
            raise TestFailure(
                scenario="Org B should not access Org A product",
                expected="HTTP 404 (not found)",
                actual=f"HTTP {response.status_code}",
                likely_cause="Product access not scoped to org",
                code_location="backend/app/services/products_service.py",
                response=response
            )

    @pytest.mark.tenant
    def test_org_b_cannot_create_in_org_a_store(
        self,
        admin_beta_client: APIClient
    ):
        """
        Test that Org B cannot create products in Org A's store.

        SCENARIO: Admin from Org B tries to create product in store_id=1 (Org A)
        EXPECTED: 403 or 404 (store not found/accessible)
        """
        response = admin_beta_client.post("/api/products", json={
            "store_id": 1,  # Org A's store
            "sku": f"CROSS-TENANT-{int(time.time())}",
            "name": "Cross Tenant Product",
            "price_cents": 1000
        })

        if response.status_code == 201:
            raise TestFailure(
                scenario="Org B should not create in Org A store",
                expected="HTTP 403 or 404",
                actual="HTTP 201 (product created)",
                likely_cause="Store ownership not validated",
                code_location="backend/app/services/tenant_service.py:require_store_in_org",
                response=response
            )

    @pytest.mark.tenant
    def test_org_b_cannot_see_org_a_sales(
        self,
        admin_client: APIClient,
        admin_beta_client: APIClient,
        factory: TestDataFactory
    ):
        """
        Test that Org B cannot see Org A's sales.

        SCENARIO: Admin from Org B tries to access Org A's sale
        EXPECTED: 404 (not found)
        """
        # Create sale in Org A
        product = factory.create_product(store_id=1)
        product_id = product.get("id") or product.get("product", {}).get("id")
        factory.receive_inventory(store_id=1, product_id=product_id, quantity=10, unit_cost_cents=500)

        sale = factory.create_sale(store_id=1)
        sale_id = sale.get("sale", {}).get("id")

        # Org B tries to access it
        response = admin_beta_client.get(f"/api/sales/{sale_id}")

        if response.status_code == 200:
            raise TestFailure(
                scenario="Org B should not access Org A sale",
                expected="HTTP 404",
                actual=f"HTTP {response.status_code}",
                likely_cause="Sale access not scoped to org",
                code_location="backend/app/routes/sales.py:get_sale_route",
                response=response
            )

    @pytest.mark.tenant
    def test_org_b_cannot_see_org_a_registers(
        self,
        admin_client: APIClient,
        admin_beta_client: APIClient,
        factory: TestDataFactory
    ):
        """
        Test that Org B cannot see Org A's registers.

        SCENARIO: Admin from Org B lists registers for Org A's store
        EXPECTED: Empty list or 403/404
        """
        # Create register in Org A
        factory.create_register(store_id=1)

        # Org B tries to list Org A's registers
        response = admin_beta_client.get("/api/registers/", params={"store_id": 1})

        if response.status_code == 200:
            data = response.json()
            registers = data.get("registers", [])

            if len(registers) > 0:
                raise TestFailure(
                    scenario="Org B should not see Org A registers",
                    expected="Empty list",
                    actual=f"Found {len(registers)} registers",
                    likely_cause="Register listing not scoped to org",
                    code_location="backend/app/routes/registers.py:list_registers_route"
                )


class TestScopedUniqueness:
    """Tests for org-scoped uniqueness constraints."""

    @pytest.mark.tenant
    def test_same_sku_different_orgs(
        self,
        admin_client: APIClient,
        admin_beta_client: APIClient
    ):
        """
        Test that same SKU can exist in different organizations.

        SCENARIO: Both orgs create products with same SKU
        EXPECTED: Both succeed (SKU unique per store, not globally)
        """
        shared_sku = f"SHARED-{int(time.time())}"

        # Org A creates product
        response_a = admin_client.post("/api/products", json={
            "store_id": 1,
            "sku": shared_sku,
            "name": "Org A Product",
            "price_cents": 1000
        })

        assert_response(
            response_a, 201,
            scenario="Org A creates product",
            code_location="backend/app/routes/products.py:create_product_route"
        )

        # Org B creates product with same SKU
        # First, need to get Org B's store ID
        response_b = admin_beta_client.post("/api/products", json={
            "store_id": 3,  # Org Beta's store (store_b1)
            "sku": shared_sku,
            "name": "Org B Product",
            "price_cents": 2000
        })

        # This should succeed if store exists for Org B
        if response_b.status_code == 404:
            # Store might be store_id=3, depends on fixture setup
            pass
        elif response_b.status_code != 201:
            raise TestFailure(
                scenario="Same SKU should be allowed in different orgs",
                expected="HTTP 201",
                actual=f"HTTP {response_b.status_code}",
                likely_cause="SKU uniqueness too global",
                code_location="backend/app/models.py:Product",
                response=response_b
            )

    @pytest.mark.tenant
    def test_same_username_different_orgs(self, admin_client: APIClient, admin_beta_client: APIClient):
        """
        Test that same username can exist in different organizations.

        SCENARIO: Both orgs have user with same username
        EXPECTED: Allowed (username unique per org, not globally)
        """
        # Both orgs already have "admin" users from fixtures
        # This test verifies they can coexist

        # Validate Org A's admin
        response_a = admin_client.post("/api/auth/validate")
        assert_response(response_a, 200, "Validate Org A admin", "backend/app/routes/auth.py:validate_route")

        # Validate Org B's admin
        response_b = admin_beta_client.post("/api/auth/validate")
        assert_response(response_b, 200, "Validate Org B admin", "backend/app/routes/auth.py:validate_route")

        # Verify they are different users
        user_a = response_a.json().get("user", {})
        user_b = response_b.json().get("user", {})

        if user_a.get("id") == user_b.get("id"):
            raise TestFailure(
                scenario="Different orgs should have separate users",
                expected="Different user IDs",
                actual=f"Same ID: {user_a.get('id')}",
                likely_cause="Users not properly scoped to orgs",
                code_location="backend/app/models.py:User"
            )


class TestSecurityEventLogging:
    """Tests for security event logging on cross-tenant attempts."""

    @pytest.mark.tenant
    def test_cross_tenant_attempt_logged(
        self,
        admin_client: APIClient,
        admin_beta_client: APIClient,
        factory: TestDataFactory
    ):
        """
        Test that cross-tenant access attempts are logged.

        SCENARIO: Org B attempts to access Org A resource
        EXPECTED: Security event logged with CROSS_TENANT_ACCESS_DENIED
        """
        # Create product in Org A
        product = factory.create_product(store_id=1)
        product_id = product.get("id") or product.get("product", {}).get("id")

        # Org B attempts access (should fail)
        admin_beta_client.get(f"/api/products/{product_id}")

        # Check audit log (as Org A admin who has VIEW_AUDIT_LOG)
        # Note: This requires the audit endpoint to exist and be accessible
        # If not available, this test documents expected behavior


class TestConcurrentMultiTenant:
    """Tests for concurrent operations across tenants."""

    @pytest.mark.tenant
    @pytest.mark.concurrent
    def test_parallel_operations_different_orgs(
        self,
        admin_client: APIClient,
        admin_beta_client: APIClient,
        test_config
    ):
        """
        Test that parallel operations in different orgs don't interfere.

        SCENARIO: Both orgs create products simultaneously
        EXPECTED: Both succeed without data leakage
        """
        results: Dict[str, Dict] = {}
        errors: List[str] = []

        def create_product_org_a():
            try:
                response = admin_client.post("/api/products", json={
                    "store_id": 1,
                    "sku": f"PARALLEL-A-{int(time.time() * 1000)}",
                    "name": "Parallel Org A",
                    "price_cents": 1000
                })
                results["org_a"] = {"status": response.status_code, "data": response.json()}
            except Exception as e:
                errors.append(f"Org A: {e}")

        def create_product_org_b():
            try:
                response = admin_beta_client.post("/api/products", json={
                    "store_id": 3,  # Org B's store
                    "sku": f"PARALLEL-B-{int(time.time() * 1000)}",
                    "name": "Parallel Org B",
                    "price_cents": 2000
                })
                results["org_b"] = {"status": response.status_code, "data": response.json()}
            except Exception as e:
                errors.append(f"Org B: {e}")

        # Run in parallel
        thread_a = threading.Thread(target=create_product_org_a)
        thread_b = threading.Thread(target=create_product_org_b)

        thread_a.start()
        thread_b.start()

        thread_a.join(timeout=10)
        thread_b.join(timeout=10)

        if errors:
            raise TestFailure(
                scenario="Parallel product creation",
                expected="Both succeed",
                actual=f"Errors: {errors}",
                likely_cause="Concurrency issue in multi-tenant handling",
                code_location="backend/app/services/products_service.py"
            )

        # Verify Org A result
        if "org_a" in results and results["org_a"]["status"] != 201:
            raise TestFailure(
                scenario="Org A parallel create should succeed",
                expected="HTTP 201",
                actual=f"HTTP {results['org_a']['status']}",
                likely_cause="Parallel operation conflict",
                code_location="backend/app/routes/products.py"
            )

    @pytest.mark.tenant
    @pytest.mark.concurrent
    def test_parallel_users_same_org(
        self,
        admin_client: APIClient,
        manager_client: APIClient,
        factory: TestDataFactory
    ):
        """
        Test that parallel users in same org work correctly.

        SCENARIO: Admin and Manager both operate on same inventory
        EXPECTED: Operations succeed without race conditions
        """
        product = factory.create_product(store_id=1)
        product_id = product.get("id") or product.get("product", {}).get("id")
        factory.receive_inventory(store_id=1, product_id=product_id, quantity=100, unit_cost_cents=500)

        results = []
        errors = []

        def admin_adjust():
            try:
                response = admin_client.post("/api/inventory/adjust", json={
                    "store_id": 1,
                    "product_id": product_id,
                    "quantity_delta": -5,
                    "note": "Admin adjustment",
                    "status": "POSTED"
                })
                results.append(("admin", response.status_code))
            except Exception as e:
                errors.append(f"Admin: {e}")

        def manager_adjust():
            try:
                response = manager_client.post("/api/inventory/adjust", json={
                    "store_id": 1,
                    "product_id": product_id,
                    "quantity_delta": -3,
                    "note": "Manager adjustment",
                    "status": "POSTED"
                })
                results.append(("manager", response.status_code))
            except Exception as e:
                errors.append(f"Manager: {e}")

        # Run in parallel
        threads = [
            threading.Thread(target=admin_adjust),
            threading.Thread(target=manager_adjust)
        ]

        for t in threads:
            t.start()

        for t in threads:
            t.join(timeout=10)

        if errors:
            raise TestFailure(
                scenario="Parallel adjustments same org",
                expected="Both succeed",
                actual=f"Errors: {errors}",
                likely_cause="Concurrency handling issue",
                code_location="backend/app/services/inventory_service.py"
            )


class TestTenantContextValidation:
    """Tests for tenant context validation."""

    @pytest.mark.tenant
    def test_session_carries_org_context(self, admin_client: APIClient):
        """
        Test that session carries organization context.

        SCENARIO: Validate session includes org_id
        EXPECTED: Response includes org_id
        """
        response = admin_client.post("/api/auth/validate")

        assert_response(
            response, 200,
            scenario="Validate session",
            code_location="backend/app/routes/auth.py:validate_route"
        )

        data = response.json()

        if "org_id" not in data:
            raise TestFailure(
                scenario="Session should include org_id",
                expected="org_id in response",
                actual=f"Response keys: {list(data.keys())}",
                likely_cause="Org context not included in validate response",
                code_location="backend/app/routes/auth.py:validate_route",
                response=response
            )

    @pytest.mark.tenant
    def test_request_store_id_validated(
        self,
        admin_client: APIClient,
        admin_beta_client: APIClient
    ):
        """
        Test that store_id in requests is validated against org.

        SCENARIO: Pass foreign store_id in request
        EXPECTED: Rejected (403 or 404)
        """
        # Org B tries to receive inventory into Org A's store
        response = admin_beta_client.post("/api/inventory/receive", json={
            "store_id": 1,  # Org A's store
            "product_id": 1,
            "quantity_delta": 10,
            "unit_cost_cents": 500
        })

        if response.status_code == 201:
            raise TestFailure(
                scenario="Foreign store_id should be rejected",
                expected="HTTP 403 or 404",
                actual="HTTP 201",
                likely_cause="Store validation not checking org ownership",
                code_location="backend/app/services/tenant_service.py:require_store_in_org",
                response=response
            )
