#!/usr/bin/env python3
"""Delete incorrect records from BigQuery (will wait for streaming buffer to clear)."""
import sys
import os
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.bigquery_client import get_bigquery_client
from google.cloud import bigquery

def delete_incorrect_records():
    """Delete records with incorrect ticket_id."""
    client = get_bigquery_client()
    
    project_id = "yotam-395120"
    dataset_id = "peerplay"
    table_id = "personal_data_deletion_tool"
    
    print("=" * 60)
    print("Deleting incorrect records from BigQuery")
    print("=" * 60)
    print()
    print("Note: BigQuery has a streaming buffer. If records were just inserted,")
    print("you may need to wait a few minutes before they can be deleted.")
    print()
    
    # Try to delete records with ticket_id = 'number'
    query = f"""
    DELETE FROM `{project_id}.{dataset_id}.{table_id}`
    WHERE ticket_id = 'number'
      AND distinct_id IN ('68c949d2371ba335b59a2911', '68e03c6d7a33acd0e32a1116')
    """
    
    try:
        query_job = client.query(query)
        query_job.result()  # Wait for the job to complete
        print("✅ Deleted incorrect records")
        print()
        print("You can now re-run the handler with fixed parsing:")
        print("  ./gdpr-handler/run.sh 2025-11-16 2025-11-17")
    except Exception as e:
        error_msg = str(e)
        if "streaming buffer" in error_msg.lower():
            print("⚠️  Records are in streaming buffer. Please wait 2-3 minutes and try again.")
            print()
            print("Or you can manually delete them from BigQuery console:")
            print(f"  DELETE FROM `{project_id}.{dataset_id}.{table_id}`")
            print("  WHERE ticket_id = 'number'")
        else:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    delete_incorrect_records()

