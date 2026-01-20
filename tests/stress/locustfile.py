"""
APOS Load Testing with Locust

Run with:
    locust -f tests/stress/locustfile.py --host http://127.0.0.1:5001

Or headless:
    locust -f tests/stress/locustfile.py --host http://127.0.0.1:5001 \
           --users 10 --spawn-rate 2 --run-time 60s --headless

Pass thresholds:
- p95 response time < 500ms for reads
- p95 response time < 1000ms for writes
- Error rate < 1%
"""

import os
import time
import random
from typing import Optional, Dict, List

from locust import HttpUser, task, between, events
from locust.runners import MasterRunner


# =============================================================================
# CONFIGURATION
# =============================================================================

# Test credentials (from test fixtures)
TEST_USERS = [
    {"username": "admin_alpha", "password": "TestPass123!", "role": "admin"},
    {"username": "manager_alpha", "password": "TestPass123!", "role": "manager"},
    {"username": "cashier_alpha", "password": "TestPass123!", "role": "cashier"},
]


# =============================================================================
# METRICS TRACKING
# =============================================================================

class MetricsCollector:
    """Collect and report metrics."""

    def __init__(self):
        self.request_counts: Dict[str, int] = {}
        self.error_counts: Dict[str, int] = {}
        self.response_times: Dict[str, List[float]] = {}

    def record(self, name: str, response_time: float, success: bool):
        if name not in self.request_counts:
            self.request_counts[name] = 0
            self.error_counts[name] = 0
            self.response_times[name] = []

        self.request_counts[name] += 1
        if not success:
            self.error_counts[name] += 1
        self.response_times[name].append(response_time)

    def get_summary(self) -> Dict:
        summary = {}
        for name in self.request_counts:
            times = sorted(self.response_times[name])
            count = len(times)
            if count == 0:
                continue

            p50_idx = int(count * 0.50)
            p95_idx = int(count * 0.95)
            p99_idx = int(count * 0.99)

            summary[name] = {
                "count": self.request_counts[name],
                "errors": self.error_counts[name],
                "error_rate": self.error_counts[name] / self.request_counts[name] * 100,
                "avg_ms": sum(times) / count,
                "p50_ms": times[p50_idx] if p50_idx < count else times[-1],
                "p95_ms": times[p95_idx] if p95_idx < count else times[-1],
                "p99_ms": times[p99_idx] if p99_idx < count else times[-1],
            }
        return summary


metrics = MetricsCollector()


# =============================================================================
# USER BEHAVIORS
# =============================================================================

class APOSUser(HttpUser):
    """
    Base APOS user that authenticates on start.
    """
    wait_time = between(0.5, 2)
    abstract = True

    token: Optional[str] = None
    user_info: Optional[Dict] = None
    store_id: int = 1
    created_products: List[int] = []
    created_sales: List[int] = []

    def on_start(self):
        """Login when user starts."""
        self.login()

    def login(self):
        """Authenticate and get token."""
        creds = random.choice(TEST_USERS)
        response = self.client.post(
            "/api/auth/login",
            json={"username": creds["username"], "password": creds["password"]},
            name="auth/login"
        )

        if response.status_code == 200:
            data = response.json()
            self.token = data.get("token")
            self.user_info = data.get("user")
            session = data.get("session", {})
            self.store_id = session.get("store_id", 1)

    def get_headers(self) -> Dict:
        """Get headers with auth token."""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers


class BrowsingUser(APOSUser):
    """
    User that primarily browses/reads data.
    Simulates cashier checking inventory, viewing products, etc.
    """
    weight = 3  # 3x more browsing than heavy operations

    @task(5)
    def list_products(self):
        """List products (frequent operation)."""
        start = time.time()
        response = self.client.get(
            "/api/products",
            headers=self.get_headers(),
            name="products/list"
        )
        metrics.record("products/list", (time.time() - start) * 1000, response.status_code == 200)

    @task(3)
    def get_inventory_summary(self):
        """Get inventory summary for a product."""
        start = time.time()
        response = self.client.get(
            f"/api/inventory/1/summary",
            params={"store_id": self.store_id},
            headers=self.get_headers(),
            name="inventory/summary"
        )
        metrics.record("inventory/summary", (time.time() - start) * 1000, response.status_code in (200, 404))

    @task(2)
    def list_registers(self):
        """List registers."""
        start = time.time()
        response = self.client.get(
            "/api/registers/",
            params={"store_id": self.store_id},
            headers=self.get_headers(),
            name="registers/list"
        )
        metrics.record("registers/list", (time.time() - start) * 1000, response.status_code == 200)

    @task(1)
    def validate_session(self):
        """Validate current session."""
        start = time.time()
        response = self.client.post(
            "/api/auth/validate",
            headers=self.get_headers(),
            name="auth/validate"
        )
        metrics.record("auth/validate", (time.time() - start) * 1000, response.status_code == 200)

    @task(1)
    def health_check(self):
        """System health check."""
        start = time.time()
        response = self.client.get("/health", name="system/health")
        metrics.record("system/health", (time.time() - start) * 1000, response.status_code == 200)


class SalesUser(APOSUser):
    """
    User that creates sales.
    Simulates cashier creating and posting sales.
    """
    weight = 2

    @task(4)
    def create_and_post_sale(self):
        """Full sale workflow: create, add line, post."""
        # Create sale
        start = time.time()
        response = self.client.post(
            "/api/sales/",
            json={"store_id": self.store_id},
            headers=self.get_headers(),
            name="sales/create"
        )

        if response.status_code != 201:
            metrics.record("sales/create", (time.time() - start) * 1000, False)
            return

        sale_id = response.json().get("sale", {}).get("id")
        metrics.record("sales/create", (time.time() - start) * 1000, True)

        if not sale_id:
            return

        # Add line (use product_id 1 which should exist)
        start = time.time()
        response = self.client.post(
            f"/api/sales/{sale_id}/lines",
            json={"product_id": 1, "quantity": random.randint(1, 3)},
            headers=self.get_headers(),
            name="sales/add_line"
        )
        metrics.record("sales/add_line", (time.time() - start) * 1000, response.status_code == 201)

        if response.status_code != 201:
            return

        # Post sale
        start = time.time()
        response = self.client.post(
            f"/api/sales/{sale_id}/post",
            headers=self.get_headers(),
            name="sales/post"
        )
        metrics.record("sales/post", (time.time() - start) * 1000, response.status_code == 200)

        if response.status_code == 200:
            self.created_sales.append(sale_id)

    @task(2)
    def add_payment(self):
        """Add payment to a recent sale."""
        if not self.created_sales:
            return

        sale_id = random.choice(self.created_sales[-10:])  # Recent sales

        start = time.time()
        response = self.client.post(
            "/api/payments/",
            json={
                "sale_id": sale_id,
                "tender_type": random.choice(["CASH", "CARD"]),
                "amount_cents": random.randint(1000, 10000)
            },
            headers=self.get_headers(),
            name="payments/add"
        )
        metrics.record("payments/add", (time.time() - start) * 1000, response.status_code in (201, 400))

    @task(1)
    def get_payment_summary(self):
        """Get payment summary for a sale."""
        if not self.created_sales:
            return

        sale_id = random.choice(self.created_sales[-10:])

        start = time.time()
        response = self.client.get(
            f"/api/payments/sales/{sale_id}/summary",
            headers=self.get_headers(),
            name="payments/summary"
        )
        metrics.record("payments/summary", (time.time() - start) * 1000, response.status_code in (200, 404))


class InventoryUser(APOSUser):
    """
    User that manages inventory.
    Simulates receiving inventory and checking stock.
    """
    weight = 1

    @task(3)
    def receive_inventory(self):
        """Receive inventory."""
        start = time.time()
        response = self.client.post(
            "/api/inventory/receive",
            json={
                "store_id": self.store_id,
                "product_id": 1,
                "quantity_delta": random.randint(1, 10),
                "unit_cost_cents": random.randint(100, 1000)
            },
            headers=self.get_headers(),
            name="inventory/receive"
        )
        metrics.record("inventory/receive", (time.time() - start) * 1000, response.status_code in (201, 403, 400))

    @task(2)
    def adjust_inventory(self):
        """Adjust inventory."""
        start = time.time()
        response = self.client.post(
            "/api/inventory/adjust",
            json={
                "store_id": self.store_id,
                "product_id": 1,
                "quantity_delta": random.randint(-3, 3),
                "note": "Load test adjustment"
            },
            headers=self.get_headers(),
            name="inventory/adjust"
        )
        metrics.record("inventory/adjust", (time.time() - start) * 1000, response.status_code in (201, 403, 400))

    @task(5)
    def list_transactions(self):
        """List inventory transactions."""
        start = time.time()
        response = self.client.get(
            f"/api/inventory/1/transactions",
            params={"store_id": self.store_id},
            headers=self.get_headers(),
            name="inventory/transactions"
        )
        metrics.record("inventory/transactions", (time.time() - start) * 1000, response.status_code in (200, 404))


class AdminUser(APOSUser):
    """
    Admin user performing management operations.
    """
    weight = 1

    @task(3)
    def list_users(self):
        """List users."""
        start = time.time()
        response = self.client.get(
            "/api/admin/users",
            headers=self.get_headers(),
            name="admin/users"
        )
        metrics.record("admin/users", (time.time() - start) * 1000, response.status_code in (200, 403))

    @task(2)
    def list_roles(self):
        """List roles."""
        start = time.time()
        response = self.client.get(
            "/api/admin/roles",
            headers=self.get_headers(),
            name="admin/roles"
        )
        metrics.record("admin/roles", (time.time() - start) * 1000, response.status_code in (200, 403))

    @task(1)
    def list_permissions(self):
        """List permissions."""
        start = time.time()
        response = self.client.get(
            "/api/admin/permissions",
            headers=self.get_headers(),
            name="admin/permissions"
        )
        metrics.record("admin/permissions", (time.time() - start) * 1000, response.status_code in (200, 403))


# =============================================================================
# EVENT HANDLERS
# =============================================================================

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Print summary when test stops."""
    print("\n" + "=" * 80)
    print("LOAD TEST SUMMARY")
    print("=" * 80)

    summary = metrics.get_summary()

    print(f"\n{'Endpoint':<30} {'Count':>8} {'Errors':>8} {'Err%':>8} {'Avg(ms)':>10} {'P95(ms)':>10}")
    print("-" * 80)

    total_requests = 0
    total_errors = 0
    all_pass = True

    for name, stats in sorted(summary.items()):
        total_requests += stats["count"]
        total_errors += stats["errors"]

        # Check thresholds
        p95_threshold = 1000 if "create" in name or "post" in name or "add" in name else 500
        passed = stats["p95_ms"] < p95_threshold and stats["error_rate"] < 1

        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False

        print(f"{name:<30} {stats['count']:>8} {stats['errors']:>8} {stats['error_rate']:>7.2f}% {stats['avg_ms']:>9.1f} {stats['p95_ms']:>9.1f} [{status}]")

    print("-" * 80)
    print(f"{'TOTAL':<30} {total_requests:>8} {total_errors:>8} {total_errors/max(total_requests,1)*100:>7.2f}%")
    print("=" * 80)

    if all_pass:
        print("\n[PASS] All endpoints within thresholds")
    else:
        print("\n[FAIL] Some endpoints exceeded thresholds")
        print("  - Reads (list/get): P95 < 500ms, Error rate < 1%")
        print("  - Writes (create/post): P95 < 1000ms, Error rate < 1%")

    print("=" * 80)


# =============================================================================
# SIMPLE STRESS TEST (for pytest integration)
# =============================================================================

def run_quick_stress_test(host: str, users: int = 5, duration: int = 30) -> Dict:
    """
    Run a quick stress test and return results.

    For integration with pytest:

    from tests.stress.locustfile import run_quick_stress_test
    results = run_quick_stress_test("http://localhost:5001", users=5, duration=30)
    assert results["error_rate"] < 1
    """
    import subprocess
    import json

    result = subprocess.run([
        "locust",
        "-f", __file__,
        "--host", host,
        "--users", str(users),
        "--spawn-rate", "2",
        "--run-time", f"{duration}s",
        "--headless",
        "--json"
    ], capture_output=True, text=True)

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"error": result.stderr, "stdout": result.stdout}
