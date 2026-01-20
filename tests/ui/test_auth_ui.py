# APOS UI Tests - Authentication
#
# Browser-based tests for login/logout flows.

import pytest
import os

# Skip all tests if Playwright not available
pytestmark = pytest.mark.ui

try:
    from playwright.sync_api import Page, expect
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    Page = None
    expect = None


UI_BASE_URL = os.environ.get("TEST_FRONTEND_URL", "http://127.0.0.1:5173")


@pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="Playwright not installed")
class TestLoginUI:
    """Login UI tests."""

    @pytest.mark.smoke
    def test_login_page_loads(self, page: Page):
        """
        Test that login page loads correctly.

        SCENARIO: Navigate to app root
        EXPECTED: Login form is visible
        """
        page.goto(UI_BASE_URL)

        # Should see some login form elements
        page.wait_for_timeout(2000)

        # Look for common login form indicators
        has_username = page.locator('input[name="username"], input[placeholder*="username"], #username').count() > 0
        has_password = page.locator('input[name="password"], input[type="password"]').count() > 0

        assert has_username or has_password, (
            "TEST FAILURE\n"
            "SCENARIO: Login page should have username/password inputs\n"
            "EXPECTED: At least one login input visible\n"
            "ACTUAL: No login inputs found\n"
            "LIKELY CAUSE: Frontend not running or login component not rendering\n"
            "CODE LOCATION: frontend/src/components/AuthInterface.tsx"
        )

    @pytest.mark.smoke
    def test_successful_login(self, page: Page):
        """
        Test successful login flow.

        SCENARIO: Enter valid credentials and submit
        EXPECTED: User is logged in, dashboard visible
        """
        page.goto(UI_BASE_URL)

        # Wait for login form
        page.wait_for_selector('input[type="password"]', timeout=10000)

        # Fill credentials
        username_input = page.locator('input[name="username"], input[placeholder*="username"], #username').first
        password_input = page.locator('input[name="password"], input[type="password"]').first

        username_input.fill("admin_alpha")
        password_input.fill("TestPass123!")

        # Submit
        submit_button = page.locator('button[type="submit"], button:has-text("Login"), button:has-text("Sign")').first
        submit_button.click()

        # Wait for response
        page.wait_for_timeout(3000)

        # Check for logged-in state indicators
        # Could be: username displayed, logout button, dashboard elements
        is_logged_in = (
            page.locator('text=admin_alpha').count() > 0 or
            page.locator('button:has-text("Logout")').count() > 0 or
            page.locator('[data-testid="dashboard"]').count() > 0 or
            page.locator('text=Dashboard').count() > 0 or
            page.locator('text=Overview').count() > 0
        )

        # Take screenshot for debugging
        page.screenshot(path="tests/artifacts/login_result.png")

        assert is_logged_in, (
            "TEST FAILURE\n"
            "SCENARIO: Login with valid credentials should succeed\n"
            "EXPECTED: Dashboard or logged-in indicators visible\n"
            "ACTUAL: No logged-in state detected\n"
            "LIKELY CAUSE: Login failed or redirect not working\n"
            "CODE LOCATION: frontend/src/components/AuthInterface.tsx"
        )

    def test_invalid_login_shows_error(self, page: Page):
        """
        Test that invalid login shows error message.

        SCENARIO: Enter invalid credentials
        EXPECTED: Error message displayed
        """
        page.goto(UI_BASE_URL)

        # Wait for login form
        page.wait_for_selector('input[type="password"]', timeout=10000)

        # Fill invalid credentials
        username_input = page.locator('input[name="username"], input[placeholder*="username"], #username').first
        password_input = page.locator('input[name="password"], input[type="password"]').first

        username_input.fill("invalid_user")
        password_input.fill("WrongPassword123!")

        # Submit
        submit_button = page.locator('button[type="submit"], button:has-text("Login"), button:has-text("Sign")').first
        submit_button.click()

        # Wait for error response
        page.wait_for_timeout(2000)

        # Check for error message
        has_error = (
            page.locator('text=Invalid').count() > 0 or
            page.locator('text=error').count() > 0 or
            page.locator('text=Error').count() > 0 or
            page.locator('[class*="error"]').count() > 0 or
            page.locator('[role="alert"]').count() > 0
        )

        assert has_error, (
            "TEST FAILURE\n"
            "SCENARIO: Invalid login should show error\n"
            "EXPECTED: Error message visible\n"
            "ACTUAL: No error message found\n"
            "LIKELY CAUSE: Error handling not displaying message\n"
            "CODE LOCATION: frontend/src/components/AuthInterface.tsx"
        )


@pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="Playwright not installed")
class TestLogoutUI:
    """Logout UI tests."""

    def test_logout_flow(self, logged_in_page: Page):
        """
        Test logout flow.

        SCENARIO: Click logout button
        EXPECTED: Returns to login screen
        """
        page = logged_in_page

        # Find and click logout
        logout_button = page.locator('button:has-text("Logout"), button:has-text("Sign Out"), [data-testid="logout"]').first

        if logout_button.count() > 0:
            logout_button.click()
            page.wait_for_timeout(2000)

            # Should see login form again
            has_login = page.locator('input[type="password"]').count() > 0

            assert has_login, (
                "TEST FAILURE\n"
                "SCENARIO: Logout should return to login screen\n"
                "EXPECTED: Login form visible\n"
                "ACTUAL: Login form not found\n"
                "LIKELY CAUSE: Logout redirect not working\n"
                "CODE LOCATION: frontend/src/components/AuthInterface.tsx"
            )
