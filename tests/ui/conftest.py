# APOS UI Tests - Playwright Configuration
#
# Provides fixtures for Playwright browser automation.

import os
import pytest
from pathlib import Path
from typing import Generator

# Only import playwright if available
try:
    from playwright.sync_api import sync_playwright, Browser, Page, BrowserContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


# Test configuration
UI_BASE_URL = os.environ.get("TEST_FRONTEND_URL", "http://127.0.0.1:5173")
BACKEND_BASE_URL = os.environ.get("TEST_BACKEND_URL", "http://127.0.0.1:5001")
HEADLESS = os.environ.get("TEST_HEADLESS", "true").lower() == "true"
SLOW_MO = int(os.environ.get("TEST_SLOW_MO", "0"))

# Screenshots and traces directory
ARTIFACTS_DIR = Path(__file__).parent.parent / "artifacts"
ARTIFACTS_DIR.mkdir(exist_ok=True)


@pytest.fixture(scope="session")
def playwright_instance():
    """Create playwright instance for the test session."""
    if not PLAYWRIGHT_AVAILABLE:
        pytest.skip("Playwright not installed. Run: pip install playwright && playwright install")

    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def browser(playwright_instance) -> Generator[Browser, None, None]:
    """Create browser for the test session."""
    browser = playwright_instance.chromium.launch(
        headless=HEADLESS,
        slow_mo=SLOW_MO
    )
    yield browser
    browser.close()


@pytest.fixture
def context(browser: Browser) -> Generator[BrowserContext, None, None]:
    """Create browser context for each test."""
    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        record_video_dir=str(ARTIFACTS_DIR / "videos") if not HEADLESS else None
    )
    yield context
    context.close()


@pytest.fixture
def page(context: BrowserContext) -> Generator[Page, None, None]:
    """Create page for each test."""
    page = context.new_page()
    yield page
    page.close()


@pytest.fixture
def logged_in_page(page: Page) -> Generator[Page, None, None]:
    """Create page with logged-in admin user."""
    # Navigate to app
    page.goto(UI_BASE_URL)

    # Wait for login form
    page.wait_for_selector('input[name="username"], input[placeholder*="username"], #username', timeout=10000)

    # Fill login form
    username_input = page.locator('input[name="username"], input[placeholder*="username"], #username').first
    password_input = page.locator('input[name="password"], input[type="password"], #password').first

    username_input.fill("admin_alpha")
    password_input.fill("TestPass123!")

    # Submit
    submit_button = page.locator('button[type="submit"], button:has-text("Login"), button:has-text("Sign In")').first
    submit_button.click()

    # Wait for dashboard or some logged-in indicator
    page.wait_for_timeout(2000)  # Give time for redirect

    yield page


def take_screenshot_on_failure(page: Page, request):
    """Take screenshot when test fails."""
    if request.node.rep_call.failed:
        screenshot_path = ARTIFACTS_DIR / f"{request.node.name}.png"
        page.screenshot(path=str(screenshot_path))
        print(f"Screenshot saved: {screenshot_path}")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Hook to capture test results for screenshot on failure."""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)
