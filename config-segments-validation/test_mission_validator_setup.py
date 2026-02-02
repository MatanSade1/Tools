"""
Test script to verify mission validator setup.

This script checks that all dependencies and authentication are properly configured
without running the full validation.
"""

import sys
import os

# Test results
tests_passed = 0
tests_failed = 0

def test(name, func):
    """Run a test and track results."""
    global tests_passed, tests_failed
    try:
        print(f"Testing {name}...", end=" ")
        func()
        print("✅")
        tests_passed += 1
        return True
    except Exception as e:
        print(f"❌ {e}")
        tests_failed += 1
        return False


def test_imports():
    """Test that all required modules can be imported."""
    import pandas
    import google.cloud.bigquery
    import googleapiclient.discovery
    import google.auth
    assert pandas.__version__
    assert google.cloud.bigquery.__version__


def test_shared_modules():
    """Test that shared modules are accessible."""
    sys.path.append(os.path.dirname(__file__))
    from shared.bigquery_client import get_bigquery_client
    from shared.sheets_client import read_config_from_sheets, get_sheets_service


def test_gcp_auth():
    """Test GCP authentication."""
    import google.auth
    credentials, project = google.auth.default()
    assert credentials is not None
    assert project is not None or os.getenv("GCP_PROJECT_ID")


def test_bigquery_access():
    """Test BigQuery client creation."""
    sys.path.append(os.path.dirname(__file__))
    from shared.bigquery_client import get_bigquery_client
    client = get_bigquery_client()
    assert client is not None
    # Try a simple query to verify access
    query = "SELECT 1 as test"
    result = list(client.query(query).result())
    assert len(result) == 1


def test_sheets_service():
    """Test Google Sheets service creation."""
    sys.path.append(os.path.dirname(__file__))
    from shared.sheets_client import get_sheets_service
    service = get_sheets_service()
    assert service is not None


def test_spreadsheet_access():
    """Test that we can read from the user spreadsheet."""
    sys.path.append(os.path.dirname(__file__))
    from shared.sheets_client import read_config_from_sheets
    
    # Try to read just the header row
    USER_SPREADSHEET_ID = "1YZ-7pqKmYb43UnSXYneZT20elkcc1UTb9hDI4tjUhio"
    rows = read_config_from_sheets(USER_SPREADSHEET_ID, "A1:Z1")
    assert rows is not None
    assert len(rows) > 0


def test_bigquery_table_access():
    """Test that we can query the mission_segmentation_test table."""
    sys.path.append(os.path.dirname(__file__))
    from shared.bigquery_client import get_bigquery_client
    
    client = get_bigquery_client()
    query = """
    SELECT COUNT(*) as count
    FROM `yotam-395120.peerplay.mission_segmentation_test`
    LIMIT 1
    """
    result = list(client.query(query).result())
    assert len(result) == 1


def main():
    """Run all tests."""
    print("=" * 80)
    print("Mission Validator Setup Test")
    print("=" * 80)
    print()
    
    print("Running setup tests...")
    print()
    
    # Basic tests
    test("Python imports", test_imports)
    test("Shared modules", test_shared_modules)
    test("GCP authentication", test_gcp_auth)
    
    # Service tests
    test("BigQuery client", test_bigquery_access)
    test("Google Sheets service", test_sheets_service)
    
    # Access tests
    test("User spreadsheet access", test_spreadsheet_access)
    test("BigQuery table access", test_bigquery_table_access)
    
    # Summary
    print()
    print("=" * 80)
    print(f"Tests passed: {tests_passed}")
    print(f"Tests failed: {tests_failed}")
    
    if tests_failed == 0:
        print()
        print("✅ All tests passed! You're ready to run the validator.")
        print()
        print("Run: python3 mission_config_validator.py")
        print("Or:  ./run_mission_validator.sh")
    else:
        print()
        print("❌ Some tests failed. Please fix the issues above before running the validator.")
        print()
        print("Common fixes:")
        print("  - Install dependencies: pip3 install -r requirements.txt")
        print("  - Configure GCP auth: gcloud auth application-default login")
        print("  - Check spreadsheet access permissions")
    
    print("=" * 80)
    
    sys.exit(0 if tests_failed == 0 else 1)


if __name__ == "__main__":
    main()
