#!/usr/bin/env python3
"""
Comprehensive test runner for the 20-20-20 eye health SaaS application.
Provides options for running different test suites with various configurations.
"""
import os
import sys
import argparse
import subprocess
import time
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')

def run_command(command, description, capture_output=False):
    """Run a command and handle errors"""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {command}")
    print(f"{'='*60}")

    start_time = time.time()

    try:
        if capture_output:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout
        else:
            result = subprocess.run(
                command,
                shell=True,
                check=True
            )
            return None
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {e}")
        if capture_output and hasattr(e, 'stderr'):
            print(f"Error output: {e.stderr}")
        return None
    finally:
        end_time = time.time()
        print(f"Duration: {end_time - start_time:.2f} seconds")

def run_django_tests(test_pattern="", verbosity=2, parallel=1, keepdb=False, debug_mode=False):
    """Run Django tests with specified options"""
    command_parts = ["python3", "manage.py", "test"]

    if test_pattern:
        command_parts.append(test_pattern)

    command_parts.extend([
        f"--verbosity={verbosity}",
        f"--parallel={parallel}",
    ])

    if keepdb:
        command_parts.append("--keepdb")

    if debug_mode:
        command_parts.append("--debug-mode")

    command = " ".join(command_parts)
    return run_command(command, f"Django tests: {test_pattern or 'All tests'}")

def run_pytest_tests(test_pattern="", markers="", verbosity="-v", maxfail=None):
    """Run pytest tests with specified options"""
    command_parts = ["python3", "-m", "pytest"]

    if test_pattern:
        command_parts.append(test_pattern)

    if markers:
        command_parts.extend(["-m", markers])

    command_parts.append(verbosity)

    if maxfail:
        command_parts.extend(["--maxfail", str(maxfail)])

    # Add coverage if available
    command_parts.extend([
        "--cov=.",
        "--cov-report=term-missing",
        "--cov-report=html:htmlcov",
        "--cov-fail-under=80"
    ])

    command = " ".join(command_parts)
    return run_command(command, f"Pytest tests: {test_pattern or 'All tests'}")

def run_unit_tests():
    """Run all unit tests"""
    print("\n" + "="*80)
    print("RUNNING UNIT TESTS")
    print("="*80)

    unit_test_suites = [
        ("timer.tests", "Timer model and utility tests"),
        ("accounts.tests", "User account and gamification tests"),
        ("analytics.tests", "Analytics and statistics tests"),
    ]

    for test_suite, description in unit_test_suites:
        success = run_django_tests(test_suite, verbosity=2)
        if success is None:
            print(f"Failed to run {description}")
            return False

    return True

def run_integration_tests():
    """Run integration tests"""
    print("\n" + "="*80)
    print("RUNNING INTEGRATION TESTS")
    print("="*80)

    # Run integration test files
    integration_files = [
        "test_integration_workflows.py",
        "test_api_endpoints.py",
    ]

    for test_file in integration_files:
        if os.path.exists(test_file):
            success = run_pytest_tests(test_file, markers="integration")
            if success is None:
                print(f"Failed to run {test_file}")
                return False
        else:
            print(f"Integration test file {test_file} not found")

    return True

def run_performance_tests():
    """Run performance tests"""
    print("\n" + "="*80)
    print("RUNNING PERFORMANCE TESTS")
    print("="*80)
    print("Warning: Performance tests may take several minutes to complete")

    if os.path.exists("test_performance_load.py"):
        success = run_pytest_tests("test_performance_load.py", markers="performance")
        if success is None:
            print("Failed to run performance tests")
            return False
    else:
        print("Performance test file not found")
        return False

    return True

def run_security_tests():
    """Run security tests"""
    print("\n" + "="*80)
    print("RUNNING SECURITY TESTS")
    print("="*80)

    # Run security-focused tests
    success = run_pytest_tests("", markers="security")
    if success is None:
        print("Failed to run security tests")
        return False

    return True

def run_api_tests():
    """Run API endpoint tests"""
    print("\n" + "="*80)
    print("RUNNING API TESTS")
    print("="*80)

    if os.path.exists("test_api_endpoints.py"):
        success = run_pytest_tests("test_api_endpoints.py", markers="api")
        if success is None:
            print("Failed to run API tests")
            return False
    else:
        print("API test file not found")
        return False

    return True

def run_coverage_report():
    """Generate and display coverage report"""
    print("\n" + "="*80)
    print("GENERATING COVERAGE REPORT")
    print("="*80)

    # Run tests with coverage
    command = "python3 -m pytest --cov=. --cov-report=term-missing --cov-report=html:htmlcov"
    run_command(command, "Coverage analysis")

    print("\nCoverage report generated in htmlcov/index.html")

def check_test_setup():
    """Check if test environment is properly set up"""
    print("Checking test environment setup...")

    # Check if Django is available
    try:
        import django
        print(f"✓ Django {django.get_version()} is available")
    except ImportError:
        print("✗ Django not available. Please install Django.")
        return False

    # Check if pytest is available
    try:
        import pytest
        print(f"✓ Pytest is available")
    except ImportError:
        print("✗ Pytest not available. Please install pytest.")
        return False

    # Check if coverage is available
    try:
        import coverage
        print(f"✓ Coverage.py is available")
    except ImportError:
        print("! Coverage.py not available. Install with: pip install coverage pytest-cov")

    # Check if freezegun is available (used in tests)
    try:
        import freezegun
        print(f"✓ Freezegun is available")
    except ImportError:
        print("! Freezegun not available. Install with: pip install freezegun")

    # Check if test database can be created
    try:
        os.environ['DJANGO_SETTINGS_MODULE'] = 'mysite.settings'
        django.setup()
        from django.test.utils import setup_test_environment, teardown_test_environment
        from django.db import connection

        setup_test_environment()
        print("✓ Test environment setup successful")
        teardown_test_environment()

    except Exception as e:
        print(f"✗ Test environment setup failed: {e}")
        return False

    return True

def main():
    """Main test runner function"""
    parser = argparse.ArgumentParser(
        description="Comprehensive test runner for 20-20-20 SaaS application"
    )

    parser.add_argument(
        "suite",
        nargs="?",
        choices=["unit", "integration", "api", "security", "performance", "all", "coverage"],
        default="unit",
        help="Test suite to run"
    )

    parser.add_argument(
        "--pattern",
        help="Specific test pattern to run"
    )

    parser.add_argument(
        "--parallel",
        type=int,
        default=1,
        help="Number of parallel processes for Django tests"
    )

    parser.add_argument(
        "--keepdb",
        action="store_true",
        help="Keep test database between runs"
    )

    parser.add_argument(
        "--fast",
        action="store_true",
        help="Run tests in fast mode (skip slow tests)"
    )

    parser.add_argument(
        "--check-setup",
        action="store_true",
        help="Check test environment setup"
    )

    args = parser.parse_args()

    if args.check_setup:
        return check_test_setup()

    # Ensure we're in the project directory
    if not os.path.exists("manage.py"):
        print("Error: Must be run from Django project root directory")
        return False

    print("20-20-20 SaaS Application Test Runner")
    print("="*50)

    success = True

    if args.suite == "unit" or args.suite == "all":
        success &= run_unit_tests()

    if args.suite == "integration" or args.suite == "all":
        success &= run_integration_tests()

    if args.suite == "api" or args.suite == "all":
        success &= run_api_tests()

    if args.suite == "security" or args.suite == "all":
        success &= run_security_tests()

    if args.suite == "performance" or args.suite == "all":
        if not args.fast:
            success &= run_performance_tests()
        else:
            print("Skipping performance tests in fast mode")

    if args.suite == "coverage":
        run_coverage_report()

    if args.pattern:
        # Run specific test pattern
        if "pytest" in args.pattern or args.pattern.endswith(".py"):
            success &= run_pytest_tests(args.pattern)
        else:
            success &= run_django_tests(args.pattern, parallel=args.parallel, keepdb=args.keepdb)

    print("\n" + "="*80)
    if success:
        print("🎉 ALL TESTS COMPLETED SUCCESSFULLY!")
    else:
        print("❌ SOME TESTS FAILED!")
    print("="*80)

    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)