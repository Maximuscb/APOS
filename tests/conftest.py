# APOS Test Suite - Shared Configuration and Fixtures
#
# This module provides:
# - Test database provisioning (ephemeral SQLite per test run)
# - Multi-tenant fixtures (organizations, stores, users)
# - Authentication helpers
# - Failure message formatting
# - Log capture for debugging

import os
import sys
import time
import tempfile
import subprocess
import signal
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Generator, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field

import pytest
import httpx

# Add backend to path for imports
REPO_ROOT = Path(__file__).parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class TestConfig:
    """Test configuration with environment variable overrides."""
    # Base URLs
    backend_base_url: str = os.environ.get("TEST_BACKEND_URL", "http://127.0.0.1:5001")
    frontend_base_url: str = os.environ.get("TEST_FRONTEND_URL", "http://127.0.0.1:5173")

    # Database (ephemeral per run)
    db_path: str = ""  # Will be set dynamically

    # Timeouts
    request_timeout: float = float(os.environ.get("TEST_REQUEST_TIMEOUT", "30"))
    server_startup_timeout: float = float(os.environ.get("TEST_SERVER_STARTUP_TIMEOUT", "30"))

    # Concurrency (for stress tests)
    stress_users: int = int(os.environ.get("TEST_STRESS_USERS", "10"))
    stress_duration: int = int(os.environ.get("TEST_STRESS_DURATION", "60"))

    # UI tests
    headless: bool = os.environ.get("TEST_HEADLESS", "true").lower() == "true"
    slow_mo: int = int(os.environ.get("TEST_SLOW_MO", "0"))

    # Random seed for determinism
    seed: int = int(os.environ.get("TEST_SEED", str(int(time.time()))))


# =============================================================================
# FAILURE MESSAGE HELPER
# =============================================================================

class TestFailure(Exception):
    """
    Custom exception with detailed, human-readable failure messages.

    Structure:
    1. Scenario: What was being tested
    2. Expected: What should have happened
    3. Actual: What actually happened
    4. Likely Cause: Most probable reason for failure
    5. Code Location: Where to look in the codebase
    """

    def __init__(
        self,
        scenario: str,
        expected: str,
        actual: str,
        likely_cause: str,
        code_location: str,
        response: Optional[httpx.Response] = None,
        extra_context: Optional[Dict[str, Any]] = None
    ):
        self.scenario = scenario
        self.expected = expected
        self.actual = actual
        self.likely_cause = likely_cause
        self.code_location = code_location
        self.response = response
        self.extra_context = extra_context or {}

        message = self._format_message()
        super().__init__(message)

    def _format_message(self) -> str:
        lines = [
            "",
            "=" * 80,
            "TEST FAILURE DETAILS",
            "=" * 80,
            f"SCENARIO: {self.scenario}",
            "-" * 80,
            f"EXPECTED: {self.expected}",
            f"ACTUAL: {self.actual}",
            "-" * 80,
            f"LIKELY CAUSE: {self.likely_cause}",
            f"CODE LOCATION: {self.code_location}",
        ]

        if self.response is not None:
            lines.extend([
                "-" * 80,
                f"HTTP STATUS: {self.response.status_code}",
                f"RESPONSE BODY: {self.response.text[:1000]}",
            ])

        if self.extra_context:
            lines.append("-" * 80)
            lines.append("EXTRA CONTEXT:")
            for key, value in self.extra_context.items():
                lines.append(f"  {key}: {value}")

        lines.append("=" * 80)
        return "\n".join(lines)


def assert_response(
    response: httpx.Response,
    expected_status: int,
    scenario: str,
    code_location: str,
    expected_body_contains: Optional[str] = None
):
    """
    Assert HTTP response status and optionally body content.
    Raises TestFailure with detailed message on failure.
    """
    if response.status_code != expected_status:
        raise TestFailure(
            scenario=scenario,
            expected=f"HTTP {expected_status}",
            actual=f"HTTP {response.status_code}",
            likely_cause=_infer_cause(response),
            code_location=code_location,
            response=response
        )

    if expected_body_contains and expected_body_contains not in response.text:
        raise TestFailure(
            scenario=scenario,
            expected=f"Response body contains: {expected_body_contains}",
            actual=f"Response body: {response.text[:500]}",
            likely_cause="Response format changed or wrong endpoint hit",
            code_location=code_location,
            response=response
        )


def _infer_cause(response: httpx.Response) -> str:
    """Infer likely cause from response status/body."""
    if response.status_code == 401:
        return "Authentication failed - token invalid/missing or session expired"
    elif response.status_code == 403:
        return "Permission denied - user lacks required permission for this action"
    elif response.status_code == 404:
        return "Resource not found - wrong ID, deleted, or wrong tenant context"
    elif response.status_code == 400:
        return "Invalid request - missing required field or validation failed"
    elif response.status_code == 409:
        return "Conflict - duplicate resource or business rule violation"
    elif response.status_code == 500:
        return "Server error - check backend logs for stack trace"
    elif response.status_code == 429:
        return "Rate limited - too many requests or account locked"
    else:
        return f"Unexpected status code {response.status_code}"


# =============================================================================
# HTTP CLIENT WITH AUTH HELPERS
# =============================================================================

class APIClient:
    """
    HTTP client wrapper with authentication and convenience methods.
    """

    def __init__(self, base_url: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=timeout)
        self.token: Optional[str] = None
        self.current_user: Optional[Dict] = None
        self.org_id: Optional[int] = None
        self.store_id: Optional[int] = None

    def _headers(self, extra: Optional[Dict] = None) -> Dict:
        """Build request headers with optional auth."""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if extra:
            headers.update(extra)
        return headers

    def get(self, path: str, params: Optional[Dict] = None, **kwargs) -> httpx.Response:
        return self.client.get(
            f"{self.base_url}{path}",
            headers=self._headers(),
            params=params,
            **kwargs
        )

    def post(self, path: str, json: Optional[Dict] = None, **kwargs) -> httpx.Response:
        return self.client.post(
            f"{self.base_url}{path}",
            headers=self._headers(),
            json=json,
            **kwargs
        )

    def put(self, path: str, json: Optional[Dict] = None, **kwargs) -> httpx.Response:
        return self.client.put(
            f"{self.base_url}{path}",
            headers=self._headers(),
            json=json,
            **kwargs
        )

    def patch(self, path: str, json: Optional[Dict] = None, **kwargs) -> httpx.Response:
        return self.client.patch(
            f"{self.base_url}{path}",
            headers=self._headers(),
            json=json,
            **kwargs
        )

    def delete(self, path: str, **kwargs) -> httpx.Response:
        return self.client.delete(
            f"{self.base_url}{path}",
            headers=self._headers(),
            **kwargs
        )

    def login(self, username: str, password: str) -> bool:
        """Authenticate and store token."""
        response = self.post("/api/auth/login", json={
            "username": username,
            "password": password
        })
        if response.status_code == 200:
            data = response.json()
            self.token = data.get("token")
            self.current_user = data.get("user")
            session = data.get("session", {})
            self.org_id = session.get("org_id")
            self.store_id = session.get("store_id")
            return True
        return False

    def logout(self) -> bool:
        """Logout and clear token."""
        if not self.token:
            return True
        response = self.post("/api/auth/logout")
        if response.status_code == 200:
            self.token = None
            self.current_user = None
            self.org_id = None
            self.store_id = None
            return True
        return False

    def validate_session(self) -> bool:
        """Validate current session token."""
        if not self.token:
            return False
        response = self.post("/api/auth/validate")
        return response.status_code == 200

    def close(self):
        """Close the HTTP client."""
        self.client.close()


# =============================================================================
# SERVER MANAGEMENT
# =============================================================================

class ServerManager:
    """
    Manages Flask backend server lifecycle for tests.
    """

    def __init__(self, config: TestConfig):
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self.db_file: Optional[Path] = None

    def start(self) -> bool:
        """Start the Flask server with test database."""
        # Create temp database file
        temp_dir = tempfile.mkdtemp(prefix="apos_test_")
        self.db_file = Path(temp_dir) / "test_apos.sqlite3"

        # Set database URL environment variable
        db_url = f"sqlite:///{self.db_file}"

        env = os.environ.copy()
        env["DATABASE_URL"] = db_url
        env["FLASK_ENV"] = "testing"
        env["TESTING"] = "true"

        # Start Flask server
        self.process = subprocess.Popen(
            [sys.executable, "-m", "flask", "run", "--port", "5001"],
            cwd=str(BACKEND_DIR),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Wait for server to start
        return self._wait_for_server()

    def _wait_for_server(self) -> bool:
        """Wait for server to be responsive."""
        start_time = time.time()
        while time.time() - start_time < self.config.server_startup_timeout:
            try:
                response = httpx.get(f"{self.config.backend_base_url}/health", timeout=2.0)
                if response.status_code in (200, 503):  # 503 means degraded but running
                    return True
            except (httpx.ConnectError, httpx.TimeoutException):
                pass
            time.sleep(0.5)
        return False

    def stop(self):
        """Stop the Flask server and cleanup."""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None

        # Clean up temp database
        if self.db_file and self.db_file.parent.exists():
            shutil.rmtree(self.db_file.parent, ignore_errors=True)

    def initialize_db(self, client: APIClient):
        """
        Initialize database with schema and seed data.
        Uses Flask CLI commands via API or direct DB access.
        """
        from app import create_app
        from app.extensions import db
        from app.services.auth_service import create_default_roles, hash_password
        from app.services.permission_service import initialize_permissions, assign_default_role_permissions
        from app.models import Organization, Store, User, Role, UserRole

        app = create_app()
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{self.db_file}"

        with app.app_context():
            # Create all tables
            db.create_all()

            # Initialize roles and permissions
            create_default_roles()
            initialize_permissions()
            assign_default_role_permissions()

            # Create test organizations
            org_a = Organization(name="Test Org Alpha", code="ALPHA", is_active=True)
            org_b = Organization(name="Test Org Beta", code="BETA", is_active=True)
            db.session.add_all([org_a, org_b])
            db.session.commit()

            # Create test stores
            store_a1 = Store(org_id=org_a.id, name="Alpha Store 1", code="A1")
            store_a2 = Store(org_id=org_a.id, name="Alpha Store 2", code="A2")
            store_b1 = Store(org_id=org_b.id, name="Beta Store 1", code="B1")
            db.session.add_all([store_a1, store_a2, store_b1])
            db.session.commit()

            # Create test users
            # Org A users
            admin_a = User(
                org_id=org_a.id,
                store_id=store_a1.id,
                username="admin_alpha",
                email="admin@alpha.test",
                password_hash=hash_password("TestPass123!")
            )
            manager_a = User(
                org_id=org_a.id,
                store_id=store_a1.id,
                username="manager_alpha",
                email="manager@alpha.test",
                password_hash=hash_password("TestPass123!")
            )
            cashier_a = User(
                org_id=org_a.id,
                store_id=store_a1.id,
                username="cashier_alpha",
                email="cashier@alpha.test",
                password_hash=hash_password("TestPass123!")
            )

            # Org B users
            admin_b = User(
                org_id=org_b.id,
                store_id=store_b1.id,
                username="admin_beta",
                email="admin@beta.test",
                password_hash=hash_password("TestPass123!")
            )

            db.session.add_all([admin_a, manager_a, cashier_a, admin_b])
            db.session.commit()

            # Assign roles
            admin_role = db.session.query(Role).filter_by(name="admin").first()
            manager_role = db.session.query(Role).filter_by(name="manager").first()
            cashier_role = db.session.query(Role).filter_by(name="cashier").first()

            db.session.add(UserRole(user_id=admin_a.id, role_id=admin_role.id))
            db.session.add(UserRole(user_id=manager_a.id, role_id=manager_role.id))
            db.session.add(UserRole(user_id=cashier_a.id, role_id=cashier_role.id))
            db.session.add(UserRole(user_id=admin_b.id, role_id=admin_role.id))

            db.session.commit()


# =============================================================================
# TEST DATA FACTORIES
# =============================================================================

class TestDataFactory:
    """
    Factory for creating test data via API calls.
    """

    def __init__(self, client: APIClient):
        self.client = client
        self._counter = 0

    def _next_id(self) -> int:
        self._counter += 1
        return self._counter

    def create_product(
        self,
        store_id: int,
        sku: Optional[str] = None,
        name: Optional[str] = None,
        price_cents: int = 1000,
        description: str = "Test product"
    ) -> Dict:
        """Create a product via API."""
        n = self._next_id()
        response = self.client.post("/api/products", json={
            "store_id": store_id,
            "sku": sku or f"TEST-SKU-{n}",
            "name": name or f"Test Product {n}",
            "price_cents": price_cents,
            "description": description
        })
        if response.status_code == 201:
            return response.json()
        raise TestFailure(
            scenario="Create test product",
            expected="HTTP 201",
            actual=f"HTTP {response.status_code}",
            likely_cause="Product creation failed - check validation",
            code_location="backend/app/routes/products.py:create_product_route",
            response=response
        )

    def receive_inventory(
        self,
        store_id: int,
        product_id: int,
        quantity: int,
        unit_cost_cents: int
    ) -> Dict:
        """Receive inventory via API."""
        response = self.client.post("/api/inventory/receive", json={
            "store_id": store_id,
            "product_id": product_id,
            "quantity_delta": quantity,
            "unit_cost_cents": unit_cost_cents
        })
        if response.status_code == 201:
            return response.json()
        raise TestFailure(
            scenario="Receive inventory",
            expected="HTTP 201",
            actual=f"HTTP {response.status_code}",
            likely_cause="Inventory receive failed",
            code_location="backend/app/routes/inventory.py:receive_inventory_route",
            response=response
        )

    def create_sale(self, store_id: int) -> Dict:
        """Create a draft sale via API."""
        response = self.client.post("/api/sales/", json={
            "store_id": store_id
        })
        if response.status_code == 201:
            return response.json()
        raise TestFailure(
            scenario="Create sale",
            expected="HTTP 201",
            actual=f"HTTP {response.status_code}",
            likely_cause="Sale creation failed",
            code_location="backend/app/routes/sales.py:create_sale_route",
            response=response
        )

    def add_sale_line(self, sale_id: int, product_id: int, quantity: int) -> Dict:
        """Add line to sale via API."""
        response = self.client.post(f"/api/sales/{sale_id}/lines", json={
            "product_id": product_id,
            "quantity": quantity
        })
        if response.status_code == 201:
            return response.json()
        raise TestFailure(
            scenario="Add sale line",
            expected="HTTP 201",
            actual=f"HTTP {response.status_code}",
            likely_cause="Sale line addition failed",
            code_location="backend/app/routes/sales.py:add_line_route",
            response=response
        )

    def post_sale(self, sale_id: int) -> Dict:
        """Post a sale via API."""
        response = self.client.post(f"/api/sales/{sale_id}/post")
        if response.status_code == 200:
            return response.json()
        raise TestFailure(
            scenario="Post sale",
            expected="HTTP 200",
            actual=f"HTTP {response.status_code}",
            likely_cause="Sale posting failed - check inventory and approval status",
            code_location="backend/app/routes/sales.py:post_sale_route",
            response=response
        )

    def create_register(
        self,
        store_id: int,
        register_number: Optional[str] = None,
        name: Optional[str] = None
    ) -> Dict:
        """Create a register via API."""
        n = self._next_id()
        response = self.client.post("/api/registers/", json={
            "store_id": store_id,
            "register_number": register_number or f"REG-{n}",
            "name": name or f"Test Register {n}",
            "location": "Test Location"
        })
        if response.status_code == 201:
            return response.json()
        raise TestFailure(
            scenario="Create register",
            expected="HTTP 201",
            actual=f"HTTP {response.status_code}",
            likely_cause="Register creation failed",
            code_location="backend/app/routes/registers.py:create_register_route",
            response=response
        )

    def open_shift(self, register_id: int, opening_cash_cents: int = 10000) -> Dict:
        """Open a shift on a register via API."""
        response = self.client.post(f"/api/registers/{register_id}/shifts/open", json={
            "opening_cash_cents": opening_cash_cents
        })
        if response.status_code == 201:
            return response.json()
        raise TestFailure(
            scenario="Open shift",
            expected="HTTP 201",
            actual=f"HTTP {response.status_code}",
            likely_cause="Shift open failed - check if register already has open shift",
            code_location="backend/app/routes/registers.py:open_shift_route",
            response=response
        )

    def add_payment(
        self,
        sale_id: int,
        tender_type: str,
        amount_cents: int,
        register_id: Optional[int] = None,
        register_session_id: Optional[int] = None
    ) -> Dict:
        """Add payment to a sale via API."""
        payload = {
            "sale_id": sale_id,
            "tender_type": tender_type,
            "amount_cents": amount_cents
        }
        if register_id:
            payload["register_id"] = register_id
        if register_session_id:
            payload["register_session_id"] = register_session_id

        response = self.client.post("/api/payments/", json=payload)
        if response.status_code == 201:
            return response.json()
        raise TestFailure(
            scenario="Add payment",
            expected="HTTP 201",
            actual=f"HTTP {response.status_code}",
            likely_cause="Payment failed - check tender type and amount",
            code_location="backend/app/routes/payments.py:add_payment_route",
            response=response
        )


# =============================================================================
# PYTEST FIXTURES
# =============================================================================

@pytest.fixture(scope="session")
def test_config() -> TestConfig:
    """Provide test configuration."""
    return TestConfig()


@pytest.fixture(scope="session")
def server_manager(test_config: TestConfig) -> Generator[ServerManager, None, None]:
    """
    Manage test server lifecycle.
    Server is started once per test session.
    """
    manager = ServerManager(test_config)

    # For CI/external server mode, don't manage server
    if os.environ.get("TEST_EXTERNAL_SERVER"):
        yield manager
    else:
        if not manager.start():
            pytest.fail("Failed to start test server")
        yield manager
        manager.stop()


@pytest.fixture(scope="session")
def api_client(test_config: TestConfig, server_manager: ServerManager) -> Generator[APIClient, None, None]:
    """
    Provide API client for session-scoped tests.
    Database is initialized once.
    """
    client = APIClient(test_config.backend_base_url, timeout=test_config.request_timeout)

    # Initialize database if we're managing the server
    if not os.environ.get("TEST_EXTERNAL_SERVER"):
        server_manager.initialize_db(client)

    yield client
    client.close()


@pytest.fixture
def client(api_client: APIClient) -> APIClient:
    """
    Provide API client for each test.
    Clears any existing auth state.
    """
    api_client.token = None
    api_client.current_user = None
    api_client.org_id = None
    api_client.store_id = None
    return api_client


@pytest.fixture
def admin_client(client: APIClient) -> APIClient:
    """Provide authenticated admin client for Org Alpha."""
    if not client.login("admin_alpha", "TestPass123!"):
        pytest.fail("Failed to login as admin_alpha")
    return client


@pytest.fixture
def manager_client(client: APIClient) -> APIClient:
    """Provide authenticated manager client for Org Alpha."""
    if not client.login("manager_alpha", "TestPass123!"):
        pytest.fail("Failed to login as manager_alpha")
    return client


@pytest.fixture
def cashier_client(client: APIClient) -> APIClient:
    """Provide authenticated cashier client for Org Alpha."""
    if not client.login("cashier_alpha", "TestPass123!"):
        pytest.fail("Failed to login as cashier_alpha")
    return client


@pytest.fixture
def admin_beta_client(api_client: APIClient, test_config: TestConfig) -> Generator[APIClient, None, None]:
    """Provide authenticated admin client for Org Beta (different tenant)."""
    beta_client = APIClient(test_config.backend_base_url, timeout=test_config.request_timeout)
    if not beta_client.login("admin_beta", "TestPass123!"):
        pytest.fail("Failed to login as admin_beta")
    yield beta_client
    beta_client.close()


@pytest.fixture
def factory(admin_client: APIClient) -> TestDataFactory:
    """Provide test data factory with admin auth."""
    return TestDataFactory(admin_client)


# =============================================================================
# TEST MARKERS
# =============================================================================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "smoke: Quick smoke tests for critical paths")
    config.addinivalue_line("markers", "full: Full regression tests")
    config.addinivalue_line("markers", "stress: Load/stress tests")
    config.addinivalue_line("markers", "auth: Authentication tests")
    config.addinivalue_line("markers", "rbac: Role-based access control tests")
    config.addinivalue_line("markers", "products: Product management tests")
    config.addinivalue_line("markers", "inventory: Inventory management tests")
    config.addinivalue_line("markers", "sales: Sales workflow tests")
    config.addinivalue_line("markers", "payments: Payment processing tests")
    config.addinivalue_line("markers", "registers: Register/shift management tests")
    config.addinivalue_line("markers", "returns: Return processing tests")
    config.addinivalue_line("markers", "transfers: Inter-store transfer tests")
    config.addinivalue_line("markers", "counts: Physical inventory count tests")
    config.addinivalue_line("markers", "tenant: Multi-tenant isolation tests")
    config.addinivalue_line("markers", "concurrent: Concurrency tests")
    config.addinivalue_line("markers", "ui: UI end-to-end tests")
