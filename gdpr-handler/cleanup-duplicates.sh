#!/bin/bash
# Cleanup duplicate records with incorrect ticket_id

export PATH="/Users/matansade/google-cloud-sdk/bin:$PATH"
export PYTHONPATH=/Users/matansade/Tools:$PYTHONPATH

echo "Cleaning up duplicate records with ticket_id='number'..."
echo ""
echo "This will delete records where ticket_id = 'number'"
echo "and keep the ones with correct ticket_id values (3880, 3895)."
echo ""

python3 << 'PYTHON_SCRIPT'
from shared.bigquery_client import get_bigquery_client
from google.cloud import bigquery
import time

client = get_bigquery_client()
project_id = "yotam-395120"
dataset_id = "peerplay"
table_id = "personal_data_deletion_tool"

# Delete records with ticket_id = 'number'
query = f"""
DELETE FROM `{project_id}.{dataset_id}.{table_id}`
WHERE ticket_id = 'number'
  AND distinct_id IN ('68c949d2371ba335b59a2911', '68e03c6d7a33acd0e32a1116')
"""

try:
    print("Attempting to delete incorrect records...")
    query_job = client.query(query)
    query_job.result()
    print("✅ Successfully deleted incorrect records")
except Exception as e:
    error_msg = str(e)
    if "streaming buffer" in error_msg.lower():
        print("⚠️  Records are still in streaming buffer.")
        print("")
        print("Please wait 2-3 minutes after the last insert, then run:")
        print("  ./gdpr-handler/cleanup-duplicates.sh")
        print("")
        print("Or delete manually from BigQuery console:")
        print(f"  DELETE FROM `{project_id}.{dataset_id}.{table_id}`")
        print("  WHERE ticket_id = 'number'")
    else:
        print(f"❌ Error: {e}")

PYTHON_SCRIPT

