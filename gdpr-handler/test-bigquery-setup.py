#!/usr/bin/env python3
"""Test BigQuery setup for GDPR handler."""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("=" * 50)
print("Testing BigQuery Setup")
print("=" * 50)
print()

try:
    from shared.bigquery_client import ensure_gdpr_table_exists, get_bigquery_client
    from shared.config import get_config
except ImportError as e:
    print(f"❌ Import error: {e}")
    print()
    print("Make sure you're running from the project root and dependencies are installed:")
    print("  pip install google-cloud-bigquery")
    sys.exit(1)

# Test config
print("1. Checking configuration...")
try:
    config = get_config()
    project_id = config.get("gcp_project_id")
    if not project_id:
        print("   ❌ ERROR: GCP_PROJECT_ID not configured")
        print("   Set it with: export GCP_PROJECT_ID='your-project-id'")
        sys.exit(1)
    print(f"   ✅ GCP Project: {project_id}")
except Exception as e:
    print(f"   ❌ ERROR: {e}")
    sys.exit(1)

print()

# Test BigQuery client
print("2. Testing BigQuery client...")
try:
    client = get_bigquery_client()
    print(f"   ✅ BigQuery client created")
except Exception as e:
    print(f"   ❌ ERROR: {e}")
    print()
    print("   Make sure:")
    print("   - GCP authentication is configured (gcloud auth application-default login)")
    print("   - Service account has BigQuery permissions")
    sys.exit(1)

print()

# Test table creation
print("3. Testing GDPR table creation...")
try:
    ensure_gdpr_table_exists()
    print("   ✅ Table exists or was created successfully")
except Exception as e:
    print(f"   ❌ ERROR: {e}")
    print()
    print("   Possible issues:")
    print("   - No permission to create tables in yotam-395120.peerplay")
    print("   - Dataset doesn't exist")
    print("   - Authentication issues")
    sys.exit(1)

print()

# Verify table schema
print("4. Verifying table schema...")
try:
    client = get_bigquery_client()
    table_ref = client.dataset("peerplay", project="yotam-395120").table("personal_data_deletion_tool")
    table = client.get_table(table_ref)
    
    required_fields = {
        "distinct_id", "request_date", "ticket_id",
        "mixpanel_request_id", "mixpanel_deletion_status",
        "singular_request_id", "singular_deletion_status",
        "bigquery_deletion_status", "game_state_status",
        "is_request_completed", "slack_message_ts", "inserted_at"
    }
    
    existing_fields = {field.name for field in table.schema}
    missing_fields = required_fields - existing_fields
    
    if missing_fields:
        print(f"   ⚠️  WARNING: Missing fields: {missing_fields}")
    else:
        print(f"   ✅ All required fields present ({len(required_fields)} fields)")
        print(f"   ✅ Total fields in table: {len(existing_fields)}")
except Exception as e:
    print(f"   ⚠️  WARNING: Could not verify schema: {e}")
    print("   (Table might not exist yet, will be created on first use)")

print()

print("=" * 50)
print("✅ BigQuery setup looks good!")
print("=" * 50)
print()
print("Table location: yotam-395120.peerplay.personal_data_deletion_tool")
print()
print("You can query it with:")
print("  SELECT * FROM \`yotam-395120.peerplay.personal_data_deletion_tool\` LIMIT 10")
print()

