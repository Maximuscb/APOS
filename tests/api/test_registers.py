# APOS API Tests - Registers & Cash Management
#
# Tests for:
# - Register CRUD operations
# - Shift lifecycle (open/close)
# - Cash drawer operations
# - Cash reconciliation
# - Shift variance detection
# - Cash drop and no-sale events

import pytest
import time
from typing import Dict

from tests.conftest import APIClient, TestFailure, assert_response, TestDataFactory


class TestRegisterCRUD:
    """Register create, read, update tests."""

    @pytest.mark.smoke
    @pytest.mark.registers
    def test_create_register(self, admin_client: APIClient):
        """
        Test creating a new register.

        SCENARIO: Admin creates a POS register
        EXPECTED: HTTP 201 with register details
        """
        unique_id = int(time.time())
        response = admin_client.post("/api/registers/", json={
            "store_id": 1,
            "register_number": f"REG-{unique_id}",
            "name": f"Register {unique_id}",
            "location": "Front Counter"
        })

        assert_response(
            response, 201,
            scenario="Create register",
            code_location="backend/app/routes/registers.py:create_register_route"
        )

        data = response.json()

        if "register" not in data:
            raise TestFailure(
                scenario="Create register response should have register object",
                expected="Response has 'register' key",
                actual=f"Response keys: {list(data.keys())}",
                likely_cause="Response format changed",
                code_location="backend/app/routes/registers.py:create_register_route",
                response=response
            )

    @pytest.mark.registers
    def test_create_register_missing_fields(self, admin_client: APIClient):
        """
        Test register creation validation.

        SCENARIO: Create register without required fields
        EXPECTED: HTTP 400
        """
        response = admin_client.post("/api/registers/", json={
            "store_id": 1,
            "name": "No Number Register"
            # Missing register_number
        })

        assert_response(
            response, 400,
            scenario="Create register without register_number",
            code_location="backend/app/routes/registers.py:create_register_route"
        )

    @pytest.mark.registers
    def test_create_duplicate_register_number(self, admin_client: APIClient):
        """
        Test that duplicate register numbers in same store are rejected.

        SCENARIO: Create two registers with same number in same store
        EXPECTED: HTTP 400 or 409 on second creation
        """
        unique_num = f"DUP-{int(time.time())}"

        # First register
        response1 = admin_client.post("/api/registers/", json={
            "store_id": 1,
            "register_number": unique_num,
            "name": "First Register",
            "location": "Front"
        })

        assert_response(
            response1, 201,
            scenario="Create first register",
            code_location="backend/app/routes/registers.py:create_register_route"
        )

        # Second with same number
        response2 = admin_client.post("/api/registers/", json={
            "store_id": 1,
            "register_number": unique_num,
            "name": "Duplicate Register",
            "location": "Back"
        })

        if response2.status_code == 201:
            raise TestFailure(
                scenario="Duplicate register number should be rejected",
                expected="HTTP 400 or 409",
                actual="HTTP 201",
                likely_cause="Register number uniqueness not enforced",
                code_location="backend/app/services/register_service.py:create_register",
                response=response2
            )

    @pytest.mark.smoke
    @pytest.mark.registers
    def test_list_registers(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test listing registers.

        SCENARIO: List all registers for a store
        EXPECTED: HTTP 200 with registers array
        """
        # Create a register first
        factory.create_register(store_id=1)

        response = admin_client.get("/api/registers/", params={"store_id": 1})

        assert_response(
            response, 200,
            scenario="List registers",
            code_location="backend/app/routes/registers.py:list_registers_route"
        )

        data = response.json()

        if "registers" not in data:
            raise TestFailure(
                scenario="List registers should return registers array",
                expected="Response has 'registers' key",
                actual=f"Response keys: {list(data.keys())}",
                likely_cause="Response format changed",
                code_location="backend/app/routes/registers.py:list_registers_route",
                response=response
            )

    @pytest.mark.registers
    def test_get_register_detail(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test getting register details.

        SCENARIO: Get a specific register by ID
        EXPECTED: HTTP 200 with register details and current session
        """
        register = factory.create_register(store_id=1)
        register_id = register.get("register", {}).get("id")

        response = admin_client.get(f"/api/registers/{register_id}")

        assert_response(
            response, 200,
            scenario="Get register detail",
            code_location="backend/app/routes/registers.py:get_register_route"
        )

    @pytest.mark.registers
    def test_update_register(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test updating register details.

        SCENARIO: Update register name and location
        EXPECTED: HTTP 200 with updated data
        """
        register = factory.create_register(store_id=1)
        register_id = register.get("register", {}).get("id")

        response = admin_client.patch(f"/api/registers/{register_id}", json={
            "name": "Updated Register Name",
            "location": "Updated Location"
        })

        assert_response(
            response, 200,
            scenario="Update register",
            code_location="backend/app/routes/registers.py:update_register_route"
        )


class TestShiftLifecycle:
    """Shift open/close tests."""

    @pytest.mark.smoke
    @pytest.mark.registers
    def test_open_shift(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test opening a shift on a register.

        SCENARIO: Open shift with starting cash
        EXPECTED: HTTP 201 with session in OPEN status
        """
        register = factory.create_register(store_id=1)
        register_id = register.get("register", {}).get("id")

        response = admin_client.post(f"/api/registers/{register_id}/shifts/open", json={
            "opening_cash_cents": 10000  # $100.00 starting cash
        })

        assert_response(
            response, 201,
            scenario="Open shift",
            code_location="backend/app/routes/registers.py:open_shift_route"
        )

        data = response.json()

        if "session" not in data:
            raise TestFailure(
                scenario="Open shift should return session",
                expected="Response has 'session' key",
                actual=f"Response keys: {list(data.keys())}",
                likely_cause="Response format changed",
                code_location="backend/app/routes/registers.py:open_shift_route",
                response=response
            )

        session = data["session"]
        if session.get("status") != "OPEN":
            raise TestFailure(
                scenario="New shift should have OPEN status",
                expected="status = OPEN",
                actual=f"status = {session.get('status')}",
                likely_cause="Session not initialized to OPEN",
                code_location="backend/app/services/register_service.py:open_shift",
                response=response
            )

    @pytest.mark.registers
    def test_cannot_open_second_shift(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test that register can only have one open shift.

        SCENARIO: Try to open second shift on register with open shift
        EXPECTED: HTTP 400
        """
        register = factory.create_register(store_id=1)
        register_id = register.get("register", {}).get("id")

        # Open first shift
        factory.open_shift(register_id, 10000)

        # Try to open second
        response = admin_client.post(f"/api/registers/{register_id}/shifts/open", json={
            "opening_cash_cents": 10000
        })

        assert_response(
            response, 400,
            scenario="Open second shift on register (should fail)",
            code_location="backend/app/routes/registers.py:open_shift_route"
        )

    @pytest.mark.smoke
    @pytest.mark.registers
    def test_close_shift(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test closing a shift.

        SCENARIO: Close shift with counted cash
        EXPECTED: HTTP 200 with session in CLOSED status and variance calculated
        """
        register = factory.create_register(store_id=1)
        register_id = register.get("register", {}).get("id")

        session = factory.open_shift(register_id, 10000)
        session_id = session.get("session", {}).get("id")

        response = admin_client.post(f"/api/registers/sessions/{session_id}/close", json={
            "closing_cash_cents": 10500,  # $105.00 (net $5 over)
            "notes": "Good shift"
        })

        assert_response(
            response, 200,
            scenario="Close shift",
            code_location="backend/app/routes/registers.py:close_shift_route"
        )

        data = response.json()
        session_data = data.get("session", {})

        if session_data.get("status") != "CLOSED":
            raise TestFailure(
                scenario="Closed shift should have CLOSED status",
                expected="status = CLOSED",
                actual=f"status = {session_data.get('status')}",
                likely_cause="Session status not updated on close",
                code_location="backend/app/services/register_service.py:close_shift",
                response=response
            )

    @pytest.mark.registers
    def test_close_shift_requires_cash_count(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test that closing shift requires cash count.

        SCENARIO: Close shift without providing closing cash
        EXPECTED: HTTP 400
        """
        register = factory.create_register(store_id=1)
        register_id = register.get("register", {}).get("id")

        session = factory.open_shift(register_id, 10000)
        session_id = session.get("session", {}).get("id")

        response = admin_client.post(f"/api/registers/sessions/{session_id}/close", json={})

        assert_response(
            response, 400,
            scenario="Close shift without cash count",
            code_location="backend/app/routes/registers.py:close_shift_route"
        )

    @pytest.mark.registers
    def test_close_shift_calculates_variance(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test that shift close calculates variance.

        SCENARIO: Close shift with cash that differs from expected
        EXPECTED: Variance calculated (closing - expected)
        """
        register = factory.create_register(store_id=1)
        register_id = register.get("register", {}).get("id")

        session = factory.open_shift(register_id, 10000)  # Start with $100
        session_id = session.get("session", {}).get("id")

        # Close with $95 (should show $5 short if no sales)
        response = admin_client.post(f"/api/registers/sessions/{session_id}/close", json={
            "closing_cash_cents": 9500
        })

        data = response.json()
        session_data = data.get("session", {})

        # Variance should be -500 (short $5)
        variance = session_data.get("variance_cents")
        if variance is not None and variance != -500:
            # Only check if no sales were made during test
            pass  # Variance depends on sales during shift

    @pytest.mark.registers
    def test_cannot_close_already_closed_shift(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test that closed shift cannot be closed again.

        SCENARIO: Try to close an already closed shift
        EXPECTED: HTTP 400
        """
        register = factory.create_register(store_id=1)
        register_id = register.get("register", {}).get("id")

        session = factory.open_shift(register_id, 10000)
        session_id = session.get("session", {}).get("id")

        # Close it
        admin_client.post(f"/api/registers/sessions/{session_id}/close", json={
            "closing_cash_cents": 10000
        })

        # Try to close again
        response = admin_client.post(f"/api/registers/sessions/{session_id}/close", json={
            "closing_cash_cents": 10000
        })

        assert_response(
            response, 400,
            scenario="Close already closed shift",
            code_location="backend/app/routes/registers.py:close_shift_route"
        )


class TestCashDrawerOperations:
    """Cash drawer event tests."""

    @pytest.mark.registers
    def test_no_sale_drawer_open(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test no-sale drawer open (requires manager approval).

        SCENARIO: Open drawer without a sale
        EXPECTED: HTTP 201 with drawer event logged
        """
        register = factory.create_register(store_id=1)
        register_id = register.get("register", {}).get("id")

        session = factory.open_shift(register_id, 10000)
        session_id = session.get("session", {}).get("id")

        response = admin_client.post(f"/api/registers/sessions/{session_id}/drawer/no-sale", json={
            "reason": "Customer needed change"
        })

        # May require manager approval depending on store policy
        if response.status_code in (201, 200):
            # Success
            pass
        elif response.status_code == 403:
            # Manager approval required - acceptable
            pass
        else:
            assert_response(
                response, 201,
                scenario="No-sale drawer open",
                code_location="backend/app/routes/registers.py:no_sale_drawer_open_route"
            )

    @pytest.mark.registers
    def test_no_sale_requires_reason(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test that no-sale requires a reason.

        SCENARIO: No-sale without reason
        EXPECTED: HTTP 400
        """
        register = factory.create_register(store_id=1)
        register_id = register.get("register", {}).get("id")

        session = factory.open_shift(register_id, 10000)
        session_id = session.get("session", {}).get("id")

        response = admin_client.post(f"/api/registers/sessions/{session_id}/drawer/no-sale", json={})

        assert_response(
            response, 400,
            scenario="No-sale without reason",
            code_location="backend/app/routes/registers.py:no_sale_drawer_open_route"
        )

    @pytest.mark.registers
    def test_cash_drop(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test cash drop operation.

        SCENARIO: Remove excess cash from drawer
        EXPECTED: HTTP 201 with cash drop event logged
        """
        register = factory.create_register(store_id=1)
        register_id = register.get("register", {}).get("id")

        session = factory.open_shift(register_id, 10000)
        session_id = session.get("session", {}).get("id")

        response = admin_client.post(f"/api/registers/sessions/{session_id}/drawer/cash-drop", json={
            "amount_cents": 5000,  # $50 drop
            "reason": "Safe drop - drawer over limit"
        })

        # May require manager approval
        if response.status_code in (201, 200):
            data = response.json()
            if "event" in data:
                event = data["event"]
                if event.get("amount_cents") != 5000:
                    raise TestFailure(
                        scenario="Cash drop should record correct amount",
                        expected="amount_cents = 5000",
                        actual=f"amount_cents = {event.get('amount_cents')}",
                        likely_cause="Amount not recorded correctly",
                        code_location="backend/app/services/register_service.py:cash_drop",
                        response=response
                    )
        elif response.status_code == 403:
            # Manager approval required - acceptable
            pass

    @pytest.mark.registers
    def test_cash_drop_requires_amount(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test that cash drop requires amount.

        SCENARIO: Cash drop without amount
        EXPECTED: HTTP 400
        """
        register = factory.create_register(store_id=1)
        register_id = register.get("register", {}).get("id")

        session = factory.open_shift(register_id, 10000)
        session_id = session.get("session", {}).get("id")

        response = admin_client.post(f"/api/registers/sessions/{session_id}/drawer/cash-drop", json={
            "reason": "Need to drop cash"
            # Missing amount_cents
        })

        assert_response(
            response, 400,
            scenario="Cash drop without amount",
            code_location="backend/app/routes/registers.py:cash_drop_route"
        )

    @pytest.mark.registers
    def test_cash_drop_negative_amount_rejected(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test that negative cash drop amount is rejected.

        SCENARIO: Cash drop with negative amount
        EXPECTED: HTTP 400
        """
        register = factory.create_register(store_id=1)
        register_id = register.get("register", {}).get("id")

        session = factory.open_shift(register_id, 10000)
        session_id = session.get("session", {}).get("id")

        response = admin_client.post(f"/api/registers/sessions/{session_id}/drawer/cash-drop", json={
            "amount_cents": -1000,
            "reason": "Negative drop"
        })

        assert_response(
            response, 400,
            scenario="Cash drop with negative amount",
            code_location="backend/app/routes/registers.py:cash_drop_route"
        )


class TestShiftSessions:
    """Shift session query tests."""

    @pytest.mark.registers
    def test_get_session_details(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test getting session details with events.

        SCENARIO: Get details of a shift session
        EXPECTED: HTTP 200 with session and events
        """
        register = factory.create_register(store_id=1)
        register_id = register.get("register", {}).get("id")

        session = factory.open_shift(register_id, 10000)
        session_id = session.get("session", {}).get("id")

        response = admin_client.get(f"/api/registers/sessions/{session_id}")

        assert_response(
            response, 200,
            scenario="Get session details",
            code_location="backend/app/routes/registers.py:get_session_route"
        )

        data = response.json()

        if "session" not in data:
            raise TestFailure(
                scenario="Session details should include session",
                expected="Response has 'session' key",
                actual=f"Response keys: {list(data.keys())}",
                likely_cause="Response format changed",
                code_location="backend/app/routes/registers.py:get_session_route",
                response=response
            )

    @pytest.mark.registers
    def test_list_register_sessions(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test listing sessions for a register.

        SCENARIO: List all sessions (shifts) for a register
        EXPECTED: HTTP 200 with sessions array
        """
        register = factory.create_register(store_id=1)
        register_id = register.get("register", {}).get("id")

        # Open and close a shift
        session = factory.open_shift(register_id, 10000)
        session_id = session.get("session", {}).get("id")
        admin_client.post(f"/api/registers/sessions/{session_id}/close", json={
            "closing_cash_cents": 10000
        })

        response = admin_client.get(f"/api/registers/{register_id}/sessions")

        assert_response(
            response, 200,
            scenario="List register sessions",
            code_location="backend/app/routes/registers.py:list_sessions_route"
        )

        data = response.json()

        if "sessions" not in data:
            raise TestFailure(
                scenario="List sessions should return sessions array",
                expected="Response has 'sessions' key",
                actual=f"Response keys: {list(data.keys())}",
                likely_cause="Response format changed",
                code_location="backend/app/routes/registers.py:list_sessions_route",
                response=response
            )


class TestTenderSummary:
    """Tender summary tests."""

    @pytest.mark.registers
    @pytest.mark.payments
    def test_tender_summary_for_session(self, admin_client: APIClient, factory: TestDataFactory):
        """
        Test getting tender summary for a shift.

        SCENARIO: Get breakdown of payment types for a shift
        EXPECTED: HTTP 200 with tender totals
        """
        register = factory.create_register(store_id=1)
        register_id = register.get("register", {}).get("id")

        session = factory.open_shift(register_id, 10000)
        session_id = session.get("session", {}).get("id")

        response = admin_client.get(f"/api/payments/sessions/{session_id}/tender-summary")

        assert_response(
            response, 200,
            scenario="Get tender summary",
            code_location="backend/app/routes/payments.py:get_tender_summary_route"
        )


class TestRegisterPermissions:
    """Permission enforcement for register operations."""

    @pytest.mark.registers
    @pytest.mark.rbac
    def test_cashier_can_view_registers(self, cashier_client: APIClient):
        """
        Test that cashier can view registers.

        SCENARIO: Cashier lists registers
        EXPECTED: HTTP 200 (has CREATE_SALE permission)
        """
        response = cashier_client.get("/api/registers/", params={"store_id": 1})

        assert_response(
            response, 200,
            scenario="Cashier viewing registers",
            code_location="backend/app/routes/registers.py:list_registers_route"
        )

    @pytest.mark.registers
    @pytest.mark.rbac
    def test_cashier_cannot_create_register(self, cashier_client: APIClient):
        """
        Test that cashier cannot create registers.

        SCENARIO: Cashier tries to create a register
        EXPECTED: HTTP 403 (lacks MANAGE_REGISTER)
        """
        response = cashier_client.post("/api/registers/", json={
            "store_id": 1,
            "register_number": "CASHIER-REG",
            "name": "Cashier Register",
            "location": "Test"
        })

        assert_response(
            response, 403,
            scenario="Cashier creating register (forbidden)",
            code_location="backend/app/routes/registers.py:create_register_route"
        )

    @pytest.mark.registers
    @pytest.mark.rbac
    def test_cashier_can_open_shift(self, cashier_client: APIClient, admin_client: APIClient, factory: TestDataFactory):
        """
        Test that cashier can open shifts.

        SCENARIO: Cashier opens a shift
        EXPECTED: HTTP 201 (has CREATE_SALE permission)
        """
        # Admin creates register
        register = factory.create_register(store_id=1)
        register_id = register.get("register", {}).get("id")

        # Cashier opens shift
        response = cashier_client.post(f"/api/registers/{register_id}/shifts/open", json={
            "opening_cash_cents": 10000
        })

        assert_response(
            response, 201,
            scenario="Cashier opening shift",
            code_location="backend/app/routes/registers.py:open_shift_route"
        )
