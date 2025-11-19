#!/usr/bin/env python3
"""Delete all records with ticket_id = 'number' from BigQuery."""
import sys
import os
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.bigquery_client import get_bigquery_client
from google.cloud import bigquery

def delete_number_records(max_retries=5, wait_seconds=30):
    """Delete records with ticket_id = 'number', retrying if in streaming buffer."""
    client = get_bigquery_client()
    project_id = "yotam-395120"
    dataset_id = "peerplay"
    table_id = "personal_data_deletion_tool"
    
    print("=" * 60)
    print("Deleting records with ticket_id = 'number'")
    print("=" * 60)
    print()
    
    # Check how many records to delete
    count_query = f"""
    SELECT COUNT(*) as count
    FROM `{project_id}.{dataset_id}.{table_id}`
    WHERE ticket_id = 'number'
    """
    
    count_results = client.query(count_query).result()
    for row in count_results:
        count = row.count
        if count == 0:
            print("✅ No records with ticket_id = 'number' found")
            return True
        print(f"Found {count} records with ticket_id = 'number'")
        print()
    
    # Try to delete with retries
    delete_query = f"""
    DELETE FROM `{project_id}.{dataset_id}.{table_id}`
    WHERE ticket_id = 'number'
    """
    
    for attempt in range(1, max_retries + 1):
        try:
            print(f"Attempt {attempt}/{max_retries}: Deleting records...")
            delete_job = client.query(delete_query)
            delete_job.result()  # Wait for completion
            
            print(f"✅ Successfully deleted {count} records")
            print()
            
            # Verify
            verify_results = client.query(count_query).result()
            for verify_row in verify_results:
                if verify_row.count == 0:
                    print("✅ Verification: All records deleted successfully")
                    return True
                else:
                    print(f"⚠️  {verify_row.count} records still remain")
            
            return True
            
        except Exception as e:
            error_msg = str(e)
            if "streaming buffer" in error_msg.lower():
                if attempt < max_retries:
                    print(f"⚠️  Records still in streaming buffer. Waiting {wait_seconds} seconds...")
                    print()
                    time.sleep(wait_seconds)
                else:
                    print("❌ Records are still in streaming buffer after all retries.")
                    print()
                    print("Please wait a few more minutes and run this script again, or")
                    print("delete manually from BigQuery console:")
                    print(f"  DELETE FROM `{project_id}.{dataset_id}.{table_id}`")
                    print("  WHERE ticket_id = 'number'")
                    return False
            else:
                print(f"❌ Error: {e}")
                return False
    
    return False

if __name__ == "__main__":
    delete_number_records()

