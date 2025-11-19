#!/usr/bin/env python3
"""Fix ticket_id values in BigQuery records."""
import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.bigquery_client import get_bigquery_client
from google.cloud import bigquery

def fix_ticket_ids():
    """Update ticket_id values in BigQuery."""
    client = get_bigquery_client()
    
    # Map of distinct_id to correct ticket_id
    fixes = {
        '68c949d2371ba335b59a2911': '3880',
        '68e03c6d7a33acd0e32a1116': '3895'
    }
    
    print("=" * 60)
    print("Fixing ticket_id values in BigQuery")
    print("=" * 60)
    print()
    
    project_id = "yotam-395120"
    dataset_id = "peerplay"
    table_id = "personal_data_deletion_tool"
    
    for distinct_id, correct_ticket_id in fixes.items():
        query = f"""
        UPDATE `{project_id}.{dataset_id}.{table_id}`
        SET ticket_id = @ticket_id
        WHERE distinct_id = @distinct_id
          AND ticket_id = 'number'
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("ticket_id", "STRING", correct_ticket_id),
                bigquery.ScalarQueryParameter("distinct_id", "STRING", distinct_id),
            ]
        )
        
        try:
            query_job = client.query(query, job_config=job_config)
            query_job.result()  # Wait for the job to complete
            print(f"✅ Updated ticket_id for {distinct_id}: {correct_ticket_id}")
        except Exception as e:
            print(f"❌ Error updating {distinct_id}: {e}")
    
    print()
    print("=" * 60)
    print("✅ Fix complete!")
    print("=" * 60)
    print()
    
    # Verify the fix
    print("Verifying updates...")
    query = f"""
    SELECT distinct_id, ticket_id, request_date
    FROM `{project_id}.{dataset_id}.{table_id}`
    WHERE distinct_id IN ('68c949d2371ba335b59a2911', '68e03c6d7a33acd0e32a1116')
    ORDER BY request_date
    """
    
    try:
        results = client.query(query).result()
        print()
        print("Updated records:")
        for row in results:
            print(f"  distinct_id: {row.distinct_id}")
            print(f"  ticket_id: {row.ticket_id}")
            print(f"  request_date: {row.request_date}")
            print()
    except Exception as e:
        print(f"Error verifying: {e}")

if __name__ == "__main__":
    fix_ticket_ids()

