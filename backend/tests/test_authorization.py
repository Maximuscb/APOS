"""
Authorization tests for APOS 1.3.

Verifies:
- Unauthenticated requests return 401
- Cashier role denied high-risk operations (403)
- Admin role can perform privileged operations
- Developer access is properly protected
"""

import pytest


# =============================================================================
# UNAUTHENTICATED ACCESS — 401
# =============================================================================


class TestUnauthenticatedAccess:
    """All protected endpoints return 401 without a token."""

    @pytest.mark.parametrize(
        "method,path",
        [
            ("GET", "/api/admin/users"),
            ("POST", "/api/admin/users"),
            ("GET", "/api/admin/roles"),
            ("POST", "/api/admin/roles"),
            ("GET", "/api/admin/permissions"),
            ("POST", "/api/inventory/adjust"),
            ("GET", "/api/analytics/sales-trends"),
            ("GET", "/api/stores"),
            ("GET", "/api/products"),
            ("GET", "/api/vendors"),
            ("GET", "/api/documents"),
            ("GET", "/api/ledger"),
            ("GET", "/api/timekeeping/entries"),
            ("GET", "/api/communications/notifications"),
            ("GET", "/api/promotions"),
            ("GET", "/api/developer/organizations"),
            ("GET", "/api/developer/status"),
        ],
    )
    def test_requires_auth(self, client, seed, method, path):
        resp = getattr(client, method.lower())(path)
        assert resp.status_code == 401, f"{method} {path} returned {resp.status_code}"


# =============================================================================
# CASHIER DENIED HIGH-RISK OPERATIONS — 403
# =============================================================================


class TestCashierDeniedHighRisk:
    """Cashier role cannot perform privileged operations."""

    def test_cannot_list_users(self, client, cashier_headers):
        resp = client.get("/api/admin/users", headers=cashier_headers)
        assert resp.status_code == 403

    def test_cannot_create_user(self, client, cashier_headers):
        resp = client.post(
            "/api/admin/users",
            json={"username": "x", "email": "x@x.com", "password": "P@ssw0rd123!"},
            headers=cashier_headers,
        )
        assert resp.status_code == 403

    def test_cannot_create_role(self, client, cashier_headers):
        resp = client.post(
            "/api/admin/roles",
            json={"name": "evil-role"},
            headers=cashier_headers,
        )
        assert resp.status_code == 403

    def test_cannot_adjust_inventory(self, client, cashier_headers):
        resp = client.post(
            "/api/inventory/adjust",
            json={"store_id": 1, "product_id": 1, "quantity_delta": 10},
            headers=cashier_headers,
        )
        assert resp.status_code == 403

    def test_cannot_view_analytics(self, client, cashier_headers):
        resp = client.get("/api/analytics/sales-trends?store_id=1", headers=cashier_headers)
        assert resp.status_code == 403

    def test_cannot_manage_timekeeping(self, client, cashier_headers):
        resp = client.patch(
            "/api/timekeeping/entries/1",
            json={"reason": "test"},
            headers=cashier_headers,
        )
        assert resp.status_code == 403

    def test_cannot_view_audit_log(self, client, cashier_headers):
        resp = client.get("/api/ledger", headers=cashier_headers)
        assert resp.status_code == 403

    def test_cannot_manage_stores(self, client, cashier_headers):
        resp = client.post(
            "/api/stores",
            json={"name": "Evil Store"},
            headers=cashier_headers,
        )
        assert resp.status_code == 403

    def test_cannot_manage_vendors(self, client, cashier_headers):
        resp = client.post(
            "/api/vendors",
            json={"name": "Evil Vendor"},
            headers=cashier_headers,
        )
        assert resp.status_code == 403

    def test_cannot_access_developer_tools(self, client, cashier_headers):
        resp = client.get("/api/developer/organizations", headers=cashier_headers)
        assert resp.status_code == 403

    def test_cannot_grant_permissions(self, client, cashier_headers):
        resp = client.post(
            "/api/admin/roles/cashier/permissions",
            json={"permission_code": "SYSTEM_ADMIN"},
            headers=cashier_headers,
        )
        assert resp.status_code == 403


# =============================================================================
# ADMIN CAN PERFORM PRIVILEGED OPERATIONS — 200
# =============================================================================


class TestAdminAccess:
    """Admin role can perform privileged operations."""

    def test_can_list_users(self, client, admin_headers):
        resp = client.get("/api/admin/users", headers=admin_headers)
        assert resp.status_code == 200

    def test_can_list_roles(self, client, admin_headers):
        resp = client.get("/api/admin/roles", headers=admin_headers)
        assert resp.status_code == 200

    def test_can_list_permissions(self, client, admin_headers):
        resp = client.get("/api/admin/permissions", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data.get("permissions", [])) > 0

    def test_can_list_stores(self, client, admin_headers):
        resp = client.get("/api/stores", headers=admin_headers)
        assert resp.status_code == 200

    def test_can_view_ledger(self, client, admin_headers):
        resp = client.get("/api/ledger", headers=admin_headers)
        assert resp.status_code == 200

    def test_can_view_timekeeping(self, client, admin_headers):
        resp = client.get("/api/timekeeping/entries", headers=admin_headers)
        assert resp.status_code == 200


# =============================================================================
# DEVELOPER ACCESS PROTECTION
# =============================================================================


class TestDeveloperAccessProtection:
    """Developer-only endpoints blocked for non-developer users."""

    def test_admin_cannot_access_developer_endpoints(self, client, admin_headers):
        resp = client.get("/api/developer/organizations", headers=admin_headers)
        assert resp.status_code == 403

    def test_admin_cannot_switch_org(self, client, admin_headers):
        resp = client.post(
            "/api/developer/switch-org",
            json={"org_id": 1},
            headers=admin_headers,
        )
        assert resp.status_code == 403

    def test_manager_cannot_access_developer_endpoints(self, client, manager_headers):
        resp = client.get("/api/developer/status", headers=manager_headers)
        assert resp.status_code == 403


# =============================================================================
# PUBLIC ENDPOINTS — NO AUTH REQUIRED
# =============================================================================


class TestPublicEndpoints:
    """System health and version endpoints are public."""

    def test_health(self, client, seed):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_version(self, client, seed):
        resp = client.get("/version")
        assert resp.status_code == 200
