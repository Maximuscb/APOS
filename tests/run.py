#!/usr/bin/env python3
"""
APOS Test Runner

Unified entrypoint for running all test types.

Usage:
    python -m tests.run smoke              # Quick critical path tests
    python -m tests.run full               # All functional tests
    python -m tests.run stress             # Load/stress tests
    python -m tests.run ui                 # UI E2E tests only
    python -m tests.run api                # API tests only

Options:
    --base-url URL        Backend base URL (default: http://127.0.0.1:5001)
    --frontend-url URL    Frontend base URL (default: http://127.0.0.1:5173)
    --concurrency N       Number of concurrent users for stress tests (default: 10)
    --duration N          Duration in seconds for stress tests (default: 60)
    --headless           Run UI tests in headless mode (default: true)
    --seed N             Random seed for determinism
    --verbose            Verbose output
    --external-server    Use external server (don't start/stop test server)
"""

import argparse
import os
import sys
import subprocess
import time
import signal
from pathlib import Path
from typing import List, Optional
from datetime import datetime


# Directories
TESTS_DIR = Path(__file__).parent
REPO_ROOT = TESTS_DIR.parent
BACKEND_DIR = REPO_ROOT / "backend"
ARTIFACTS_DIR = TESTS_DIR / "artifacts"

# Ensure artifacts directory exists
ARTIFACTS_DIR.mkdir(exist_ok=True)


def print_banner(text: str):
    """Print a banner for section headers."""
    width = 80
    print()
    print("=" * width)
    print(f" {text} ".center(width))
    print("=" * width)


def print_result(label: str, passed: bool):
    """Print test result."""
    status = "[PASS]" if passed else "[FAIL]"
    color = "\033[92m" if passed else "\033[91m"
    reset = "\033[0m"
    print(f"{color}{status}{reset} {label}")


class TestRunner:
    """Test runner with server management."""

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.server_process: Optional[subprocess.Popen] = None

    def setup_environment(self):
        """Set up environment variables for tests."""
        os.environ["TEST_BACKEND_URL"] = self.args.base_url
        os.environ["TEST_FRONTEND_URL"] = self.args.frontend_url
        os.environ["TEST_HEADLESS"] = "true" if self.args.headless else "false"
        os.environ["TEST_SLOW_MO"] = "0"
        os.environ["TEST_STRESS_USERS"] = str(self.args.concurrency)
        os.environ["TEST_STRESS_DURATION"] = str(self.args.duration)
        os.environ["TEST_SEED"] = str(self.args.seed)

        if self.args.external_server:
            os.environ["TEST_EXTERNAL_SERVER"] = "true"

    def run_pytest(self, markers: List[str], extra_args: List[str] = None) -> int:
        """Run pytest with specified markers."""
        cmd = [sys.executable, "-m", "pytest"]

        # Add markers
        if markers:
            marker_expr = " or ".join(markers)
            cmd.extend(["-m", marker_expr])

        # Add common options
        cmd.extend([
            "-v" if self.args.verbose else "-q",
            "--tb=short",
            f"--junitxml={ARTIFACTS_DIR}/junit-{'-'.join(markers)}.xml",
            str(TESTS_DIR / "api"),  # API tests directory
        ])

        if extra_args:
            cmd.extend(extra_args)

        print(f"Running: {' '.join(cmd)}")
        return subprocess.call(cmd)

    def run_smoke_tests(self) -> int:
        """Run smoke tests (quick critical paths)."""
        print_banner("SMOKE TESTS")
        return self.run_pytest(["smoke"])

    def run_full_tests(self) -> int:
        """Run all functional tests."""
        print_banner("FULL REGRESSION TESTS")
        return self.run_pytest([
            "auth", "rbac", "products", "inventory",
            "sales", "payments", "registers",
            "returns", "transfers", "counts", "tenant"
        ])

    def run_api_tests(self) -> int:
        """Run API tests only."""
        print_banner("API TESTS")
        cmd = [
            sys.executable, "-m", "pytest",
            "-v" if self.args.verbose else "-q",
            "--tb=short",
            f"--junitxml={ARTIFACTS_DIR}/junit-api.xml",
            str(TESTS_DIR / "api"),
        ]
        print(f"Running: {' '.join(cmd)}")
        return subprocess.call(cmd)

    def run_ui_tests(self) -> int:
        """Run UI E2E tests."""
        print_banner("UI E2E TESTS")

        # Check if playwright is installed
        try:
            import playwright
        except ImportError:
            print("Playwright not installed. Install with:")
            print("  pip install playwright")
            print("  playwright install")
            return 1

        cmd = [
            sys.executable, "-m", "pytest",
            "-v" if self.args.verbose else "-q",
            "--tb=short",
            f"--junitxml={ARTIFACTS_DIR}/junit-ui.xml",
            str(TESTS_DIR / "ui"),
        ]
        print(f"Running: {' '.join(cmd)}")
        return subprocess.call(cmd)

    def run_stress_tests(self) -> int:
        """Run stress/load tests."""
        print_banner("STRESS/LOAD TESTS")

        # Check if locust is installed
        try:
            import locust
        except ImportError:
            print("Locust not installed. Install with:")
            print("  pip install locust")
            return 1

        locustfile = TESTS_DIR / "stress" / "locustfile.py"

        cmd = [
            sys.executable, "-m", "locust",
            "-f", str(locustfile),
            "--host", self.args.base_url,
            "--users", str(self.args.concurrency),
            "--spawn-rate", "2",
            "--run-time", f"{self.args.duration}s",
            "--headless",
        ]

        print(f"Running: {' '.join(cmd)}")
        print(f"  Users: {self.args.concurrency}")
        print(f"  Duration: {self.args.duration}s")
        print()

        return subprocess.call(cmd)

    def run(self, mode: str) -> int:
        """Run tests in specified mode."""
        self.setup_environment()

        start_time = time.time()

        if mode == "smoke":
            result = self.run_smoke_tests()
        elif mode == "full":
            result = self.run_full_tests()
        elif mode == "api":
            result = self.run_api_tests()
        elif mode == "ui":
            result = self.run_ui_tests()
        elif mode == "stress":
            result = self.run_stress_tests()
        elif mode == "all":
            results = []
            results.append(("Smoke Tests", self.run_smoke_tests()))
            results.append(("API Tests", self.run_api_tests()))
            results.append(("UI Tests", self.run_ui_tests()))

            print_banner("RESULTS SUMMARY")
            all_passed = True
            for name, code in results:
                passed = code == 0
                print_result(name, passed)
                if not passed:
                    all_passed = False

            result = 0 if all_passed else 1
        else:
            print(f"Unknown mode: {mode}")
            return 1

        elapsed = time.time() - start_time
        print()
        print(f"Total time: {elapsed:.1f}s")

        return result


def main():
    parser = argparse.ArgumentParser(
        description="APOS Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  smoke     Quick critical path tests (~1-2 minutes)
  full      All functional tests (~5-10 minutes)
  api       API tests only
  ui        UI E2E tests only
  stress    Load/stress tests
  all       Smoke + API + UI tests

Examples:
  python -m tests.run smoke
  python -m tests.run full --verbose
  python -m tests.run stress --concurrency 20 --duration 120
  python -m tests.run ui --headless
        """
    )

    parser.add_argument(
        "mode",
        choices=["smoke", "full", "api", "ui", "stress", "all"],
        help="Test mode to run"
    )

    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:5001",
        help="Backend base URL"
    )

    parser.add_argument(
        "--frontend-url",
        default="http://127.0.0.1:5173",
        help="Frontend base URL"
    )

    parser.add_argument(
        "--concurrency",
        type=int,
        default=10,
        help="Number of concurrent users for stress tests"
    )

    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Duration in seconds for stress tests"
    )

    parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="Run UI tests in headless mode"
    )

    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Run UI tests with visible browser"
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=int(time.time()),
        help="Random seed for determinism"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )

    parser.add_argument(
        "--external-server",
        action="store_true",
        help="Use external server (don't manage test server)"
    )

    args = parser.parse_args()

    # Handle headless toggle
    if args.no_headless:
        args.headless = False

    # Print header
    print_banner(f"APOS TEST SUITE - {args.mode.upper()}")
    print(f"Started: {datetime.now().isoformat()}")
    print(f"Backend URL: {args.base_url}")
    print(f"Frontend URL: {args.frontend_url}")
    print(f"Seed: {args.seed}")

    # Run tests
    runner = TestRunner(args)
    exit_code = runner.run(args.mode)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
