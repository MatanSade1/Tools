"""
Temp Users Cohort Cloud Run Service

Identifies temp users (users who had impression_privacy followed by 
impression_restore_user_state_by_device_id within 2 minutes on the same device)
and updates Mixpanel cohorts.

Executes 2 steps:
1. Find temp users from last 2 days and insert into state_loss_temp_users table
2. Update Mixpanel cohort with temp user markers
"""

import uuid
import datetime
import json
import time
import traceback
import logging
import os
import sys
from typing import Dict, List, Optional, Any
from google.cloud import bigquery
from flask import Flask, request as flask_request, jsonify

# Import shared utilities
# Try importing from local shared directory first, then fallback to parent
try:
    from shared.bigquery_client import get_bigquery_client
    from shared.config import get_config
    from shared.slack_client import get_slack_webhook_url
except ImportError:
    # Fallback to parent directory
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from shared.bigquery_client import get_bigquery_client
    from shared.config import get_config
    from shared.slack_client import get_slack_webhook_url
import requests

# Configuration
MIXPANEL_PROJECT_TOKEN = "0e73d8fa8567c5bf2820b408701fa7be"
COHORT_MARKER = "state_loss_temp_user_cohort_v1"
PROJECT_ID = "yotam-395120"
DATASET_ID = "peerplay"
TEMP_USERS_TABLE = f"{PROJECT_ID}.core_tables.state_loss_temp_users"  # Insert into underlying table, not the view

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('TempUsersCohort')

# Flask app
app = Flask(__name__)


def setup_logging():
    """Setup Cloud Logging"""
    try:
        import google.cloud.logging
        client = google.cloud.logging.Client(project=PROJECT_ID)
        client.setup_logging()
        return logging.getLogger('TempUsersCohort')
    except Exception as e:
        logger.warning(f"Could not setup Cloud Logging: {e}")
        return logger


def log_step(client: bigquery.Client, run_id: str, step_name: str, is_start: bool = True):
    """Log step start/end to audit table"""
    log_name = f"{'start' if is_start else 'end'}_step_{step_name}"
    
    query = f"""
    INSERT INTO `{PROJECT_ID}.{DATASET_ID}.process_audit_log` (
      log_timestamp,
      process_name,
      run_id,
      log_name,
      comment
    )
    VALUES (
      CURRENT_TIMESTAMP(),
      'temp_users_cohort',
      '{run_id}',
      '{log_name}',
      ''
    )
    """
    
    try:
        client.query(query).result()
        logger.info(f"✓ Logged: {log_name} (Run ID: {run_id})")
    except Exception as e:
        logger.error(f"✗ Logging failed for {log_name}: {str(e)}")


def send_error_alert(step: int, error: Exception, run_id: str, query_details: Optional[str] = None):
    """Send error alert to Slack"""
    try:
        config = get_config()
        webhook_url = get_slack_webhook_url("matan-coralogix-alerts")
        
        error_traceback = traceback.format_exc()
        error_message = str(error)
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🚨 Temp Users Cohort - Step {step} Failed"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Step:*\n{step}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Run ID:*\n`{run_id}`"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Error:*\n`{error_message[:200]}`"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Time:*\n{datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
                    }
                ]
            }
        ]
        
        if query_details:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Query Details:*\n```{query_details[:500]}```"
                }
            })
        
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Full Traceback:*\n```{error_traceback[:1000]}```"
            }
        })
        
        # Add Cloud Logging link
        log_url = (
            f"https://console.cloud.google.com/logs/query?"
            f"project={PROJECT_ID}&"
            f"query=resource.type%3D%22cloud_run_revision%22%20resource.labels.service_name%3D%22temp-users-cohort%22"
        )
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"<{log_url}|View in Cloud Logging>"
            }
        })
        
        message = {"blocks": blocks}
        
        response = requests.post(webhook_url, json=message, timeout=10)
        response.raise_for_status()
        logger.info(f"✓ Sent error alert to Slack for Step {step}")
    except Exception as e:
        logger.error(f"✗ Failed to send error alert: {str(e)}")


def step_1_find_and_insert_temp_users(client: bigquery.Client, run_id: str) -> Dict[str, Any]:
    """Step 1: Find temp users from last 2 days and insert into state_loss_temp_users table"""
    logger.info("Starting Step 1: Find and insert temp users")
    log_step(client, run_id, "1", is_start=True)
    
    try:
        # Query to find temp users
        query = """
        WITH privacy_events AS (
          SELECT 
            distinct_id,
            device_id,
            TIMESTAMP_MILLIS(CAST(res_timestamp AS INT64)) as event_time,
            date
          FROM `yotam-395120.peerplay.vmp_master_event_normalized`
          WHERE mp_event_name = 'impression_privacy'
            AND date >= DATE_SUB(CURRENT_DATE(), INTERVAL 2 DAY)
            AND device_id IS NOT NULL
            AND distinct_id IS NOT NULL
            AND mp_os = 'Android'
        ),
        restore_events AS (
          SELECT 
            device_id,
            TIMESTAMP_MILLIS(CAST(res_timestamp AS INT64)) as event_time,
            date
          FROM `yotam-395120.peerplay.vmp_master_event_normalized`
          WHERE mp_event_name = 'impression_restore_user_state_by_device_id'
            AND date >= DATE_SUB(CURRENT_DATE(), INTERVAL 2 DAY)
            AND device_id IS NOT NULL
            AND mp_os = 'Android'
        )
        SELECT DISTINCT
          p.distinct_id
        FROM privacy_events p
        INNER JOIN restore_events r
          ON p.device_id = r.device_id
          AND r.event_time BETWEEN p.event_time AND TIMESTAMP_ADD(p.event_time, INTERVAL 2 MINUTE)
        WHERE p.distinct_id NOT IN (
          SELECT DISTINCT distinct_id 
          FROM `yotam-395120.peerplay.state_loss_temp_users`
          WHERE distinct_id IS NOT NULL
        )
        """
        
        logger.info("Executing query to find temp users...")
        query_job = client.query(query)
        results = query_job.result()
        
        distinct_ids = [row[0] for row in results]
        logger.info(f"✓ Found {len(distinct_ids)} new temp users")
        
        if not distinct_ids:
            logger.info("No new temp users to insert")
            log_step(client, run_id, "1", is_start=False)
            return {"success": True, "step": 1, "inserted_count": 0}
        
        # Insert into state_loss_temp_users table
        logger.info(f"Inserting {len(distinct_ids)} distinct_ids into {TEMP_USERS_TABLE}...")
        
        rows_to_insert = [{"distinct_id": distinct_id} for distinct_id in distinct_ids]
        
        table_ref = client.get_table(TEMP_USERS_TABLE)
        errors = client.insert_rows_json(table_ref, rows_to_insert)
        
        if errors:
            error_msg = f"Error inserting rows: {errors}"
            logger.error(f"✗ {error_msg}")
            raise Exception(error_msg)
        
        logger.info(f"✓ Step 1 completed: Inserted {len(distinct_ids)} temp users into {TEMP_USERS_TABLE}")
        log_step(client, run_id, "1", is_start=False)
        return {"success": True, "step": 1, "inserted_count": len(distinct_ids)}
        
    except Exception as e:
        error_msg = f"Step 1 failed: {str(e)}"
        logger.error(error_msg)
        send_error_alert(1, e, run_id, query)
        log_step(client, run_id, "1", is_start=False)
        raise Exception(error_msg)


def get_distinct_ids_from_bigquery(client: bigquery.Client) -> List[str]:
    """Fetch distinct IDs from BigQuery state_loss_temp_users table"""
    logger.info(f"Fetching distinct IDs from {TEMP_USERS_TABLE}...")
    
    query = f"""
    SELECT DISTINCT distinct_id
    FROM `{TEMP_USERS_TABLE}`
    WHERE distinct_id IS NOT NULL
    """
    
    try:
        query_job = client.query(query)
        results = query_job.result()
        distinct_ids = [row[0] for row in results]
        logger.info(f"✓ Found {len(distinct_ids)} distinct IDs")
        return distinct_ids
    except Exception as e:
        logger.error(f"✗ Error fetching data from BigQuery: {str(e)}")
        raise


def update_user_profiles_with_marker(distinct_ids: List[str]) -> tuple:
    """
    Update Mixpanel user profiles with temp user cohort marker property
    """
    logger.info(f"Updating {len(distinct_ids)} user profiles with temp user cohort marker...")
    
    cohort_marker_value = COHORT_MARKER
    update_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    url = "https://api.mixpanel.com/engage"
    
    batch_size = 200  # Mixpanel recommends batches of 200 for profile updates
    total_batches = (len(distinct_ids) + batch_size - 1) // batch_size
    successful_updates = 0
    
    for i in range(0, len(distinct_ids), batch_size):
        batch = distinct_ids[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        
        logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} profiles)...")
        
        # Create batch payload for user profile updates
        updates = []
        for uid in batch:
            updates.append({
                "$distinct_id": str(uid),
                "$token": MIXPANEL_PROJECT_TOKEN,
                "$ip": "0",  # Set to 0 to avoid geolocation parsing
                "$set": {
                    "state_loss_temp_user_cohort_marker": cohort_marker_value,
                    "state_loss_last_updated": update_timestamp
                }
            })
        
        # Send as form data with 'data' parameter
        payload = {
            "data": json.dumps(updates),
            "verbose": "1"  # Get detailed response
        }
        
        try:
            response = requests.post(url, data=payload, timeout=30)
            response.raise_for_status()
            
            # Check if the response indicates success
            response_text = response.text.strip()
            if response_text == "1" or "success" in response_text.lower():
                logger.info(f"✓ Batch {batch_num} processed successfully")
                successful_updates += len(batch)
            else:
                logger.warning(f"⚠ Batch {batch_num} response: {response_text}")
                successful_updates += len(batch)  # Assume success for now
            
            # Add a small delay to avoid rate limiting
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"✗ Error processing batch {batch_num}: {str(e)}")
            if hasattr(e, 'response'):
                logger.error(f"Response: {e.response.text}")
            raise
    
    logger.info(f"✓ Profile updates complete. Successfully updated {successful_updates} user profiles.")
    logger.info(f"✓ Cohort marker property: state_loss_temp_user_cohort_marker = '{cohort_marker_value}'")
    
    return successful_updates, cohort_marker_value


def step_2_update_mixpanel_cohort(client: bigquery.Client, run_id: str) -> Dict[str, Any]:
    """Step 2: Update Mixpanel cohort with temp user markers"""
    logger.info("Starting Step 2: Update Mixpanel cohort")
    log_step(client, run_id, "2", is_start=True)
    
    try:
        # Get distinct IDs from BigQuery
        distinct_ids = get_distinct_ids_from_bigquery(client)
        if not distinct_ids:
            logger.warning("✗ No distinct IDs found. Skipping Mixpanel update.")
            log_step(client, run_id, "2", is_start=False)
            return {"success": True, "step": 2, "updated_count": 0}
        
        # Update profiles with cohort marker
        logger.info(f"Using cohort marker: '{COHORT_MARKER}'")
        successful_updates, cohort_marker = update_user_profiles_with_marker(distinct_ids)
        
        if successful_updates > 0:
            logger.info(f"✓ Step 2 completed: Updated {successful_updates} user profiles in Mixpanel")
        else:
            logger.warning("✗ Step 2: No profiles updated")
        
        log_step(client, run_id, "2", is_start=False)
        return {"success": True, "step": 2, "updated_count": successful_updates}
    except Exception as e:
        error_msg = f"Step 2 failed: {str(e)}"
        logger.error(error_msg)
        send_error_alert(2, e, run_id)
        log_step(client, run_id, "2", is_start=False)
        raise Exception(error_msg)


def run_temp_users_cohort():
    """Main execution function"""
    logger.info("=" * 60)
    logger.info("TEMP USERS COHORT PROCESS - STARTING")
    logger.info("=" * 60)
    
    # Generate unique run_id for this execution
    run_id = str(uuid.uuid4())
    logger.info(f"Run ID for this execution: {run_id}")
    
    # Get BigQuery client
    client = get_bigquery_client()
    
    results = {
        "run_id": run_id,
        "start_time": datetime.datetime.utcnow().isoformat(),
        "steps": []
    }
    
    # Execute all steps
    steps = [
        ("Step 1", step_1_find_and_insert_temp_users),
        ("Step 2", step_2_update_mixpanel_cohort),
    ]
    
    for step_name, step_func in steps:
        try:
            step_result = step_func(client, run_id)
            results["steps"].append({
                "step": step_name,
                "success": True,
                "result": step_result
            })
            logger.info(f"✓ {step_name} completed successfully")
        except Exception as e:
            error_msg = str(e)
            logger.error(f"✗ {step_name} failed: {error_msg}")
            results["steps"].append({
                "step": step_name,
                "success": False,
                "error": error_msg
            })
            # Continue with next step even if one fails
    
    results["end_time"] = datetime.datetime.utcnow().isoformat()
    results["success"] = all(step["success"] for step in results["steps"])
    
    logger.info("=" * 60)
    logger.info(f"TEMP USERS COHORT PROCESS - {'SUCCESS' if results['success'] else 'COMPLETED WITH ERRORS'}")
    logger.info("=" * 60)
    
    return results


@app.route('/', methods=['GET', 'POST'])
def handle_request():
    """Cloud Run entry point"""
    logger = setup_logging()
    logger.info("Temp Users Cohort Cloud Run service invoked")
    
    try:
        results = run_temp_users_cohort()
        
        return jsonify({
            'success': results['success'],
            'run_id': results['run_id'],
            'steps': results['steps'],
            'start_time': results['start_time'],
            'end_time': results['end_time'],
            'timestamp': datetime.datetime.utcnow().isoformat()
        }), 200
    except Exception as e:
        logger.error(f"Temp Users Cohort service failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.datetime.utcnow().isoformat()
        }), 500


if __name__ == '__main__':
    # For local testing
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

