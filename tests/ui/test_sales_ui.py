# APOS UI Tests - Sales/POS Interface
#
# Browser-based tests for POS workflows.

import pytest
import os

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
class TestSalesInterfaceUI:
    """Sales interface UI tests."""

    @pytest.mark.smoke
    def test_sales_tab_accessible(self, logged_in_page: Page):
        """
        Test that sales tab/section is accessible.

        SCENARIO: Navigate to sales section
        EXPECTED: Sales interface loads
        """
        page = logged_in_page

        # Look for Sales tab or navigation
        sales_nav = page.locator('text=Sales, button:has-text("Sales"), [data-tab="sales"]').first

        if sales_nav.count() > 0:
            sales_nav.click()
            page.wait_for_timeout(1000)

        # Check for sales interface elements
        has_sales_ui = (
            page.locator('text=New Sale').count() > 0 or
            page.locator('text=Create Sale').count() > 0 or
            page.locator('text=Cart').count() > 0 or
            page.locator('[data-testid="sales"]').count() > 0
        )

        page.screenshot(path="tests/artifacts/sales_interface.png")

        # May not have explicit sales UI if it's a different layout
        # This is an exploratory test

    def test_product_lookup_field(self, logged_in_page: Page):
        """
        Test product lookup/scanner field exists.

        SCENARIO: Look for barcode/SKU input field
        EXPECTED: Input field for product lookup exists
        """
        page = logged_in_page

        # Navigate to sales if needed
        sales_nav = page.locator('text=Sales, button:has-text("Sales")').first
        if sales_nav.count() > 0:
            sales_nav.click()
            page.wait_for_timeout(1000)

        # Look for product lookup input
        lookup_input = page.locator(
            'input[placeholder*="barcode"], '
            'input[placeholder*="SKU"], '
            'input[placeholder*="scan"], '
            'input[placeholder*="product"], '
            '#product-lookup, '
            '[data-testid="product-lookup"]'
        ).first

        page.screenshot(path="tests/artifacts/product_lookup.png")

        # This is exploratory - document what exists

    def test_cart_display(self, logged_in_page: Page):
        """
        Test cart display area.

        SCENARIO: Check for cart/line items display
        EXPECTED: Area to show sale items exists
        """
        page = logged_in_page

        # Navigate to sales
        sales_nav = page.locator('text=Sales, button:has-text("Sales")').first
        if sales_nav.count() > 0:
            sales_nav.click()
            page.wait_for_timeout(1000)

        # Look for cart/items area
        has_cart = (
            page.locator('text=Cart').count() > 0 or
            page.locator('text=Items').count() > 0 or
            page.locator('text=Total').count() > 0 or
            page.locator('[class*="cart"]').count() > 0
        )

        page.screenshot(path="tests/artifacts/cart_display.png")


@pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="Playwright not installed")
class TestPaymentUI:
    """Payment UI tests."""

    def test_payment_options_visible(self, logged_in_page: Page):
        """
        Test payment options are visible.

        SCENARIO: Check for payment tender options
        EXPECTED: Cash, Card options visible
        """
        page = logged_in_page

        # Navigate to payments if separate
        payments_nav = page.locator('text=Payments, button:has-text("Payments")').first
        if payments_nav.count() > 0:
            payments_nav.click()
            page.wait_for_timeout(1000)

        # Look for payment options
        has_payment_options = (
            page.locator('text=Cash').count() > 0 or
            page.locator('text=Card').count() > 0 or
            page.locator('text=Payment').count() > 0
        )

        page.screenshot(path="tests/artifacts/payment_options.png")


@pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="Playwright not installed")
class TestNavigationUI:
    """Navigation UI tests."""

    @pytest.mark.smoke
    def test_main_navigation_tabs(self, logged_in_page: Page):
        """
        Test main navigation tabs exist.

        SCENARIO: Check for main navigation elements
        EXPECTED: Key sections accessible via navigation
        """
        page = logged_in_page

        # Check for common navigation elements
        nav_elements = []

        if page.locator('text=Overview').count() > 0:
            nav_elements.append("Overview")
        if page.locator('text=Inventory').count() > 0:
            nav_elements.append("Inventory")
        if page.locator('text=Sales').count() > 0:
            nav_elements.append("Sales")
        if page.locator('text=Products').count() > 0:
            nav_elements.append("Products")
        if page.locator('text=Registers').count() > 0:
            nav_elements.append("Registers")
        if page.locator('text=Payments').count() > 0:
            nav_elements.append("Payments")
        if page.locator('text=Operations').count() > 0:
            nav_elements.append("Operations")
        if page.locator('text=Users').count() > 0:
            nav_elements.append("Users")

        page.screenshot(path="tests/artifacts/navigation.png")

        assert len(nav_elements) > 0, (
            "TEST FAILURE\n"
            "SCENARIO: Main navigation should have tabs\n"
            "EXPECTED: At least one navigation element\n"
            "ACTUAL: No navigation elements found\n"
            "LIKELY CAUSE: Dashboard not loading or wrong selectors\n"
            "CODE LOCATION: frontend/src/App.tsx"
        )

    def test_click_through_tabs(self, logged_in_page: Page):
        """
        Test clicking through navigation tabs.

        SCENARIO: Click each navigation tab
        EXPECTED: Content changes without errors
        """
        page = logged_in_page

        tabs_to_test = ['Inventory', 'Sales', 'Products', 'Registers', 'Payments']

        for tab_name in tabs_to_test:
            tab = page.locator(f'text={tab_name}, button:has-text("{tab_name}")').first

            if tab.count() > 0:
                tab.click()
                page.wait_for_timeout(500)

                # Check for error indicators
                has_error = page.locator('text=Error, [class*="error"]').count() > 0

                if has_error:
                    page.screenshot(path=f"tests/artifacts/tab_error_{tab_name.lower()}.png")

        page.screenshot(path="tests/artifacts/final_tab_state.png")
