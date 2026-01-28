#!/usr/bin/env python3
"""Fix Mixpanel status for specific distinct_ids."""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.bigquery_client import get_bigquery_client
from shared.config import get_config
from api_clients import check_mixpanel_gdpr_status
from shared.bigquery_client import update_gdpr_request_status
import requests

def fix_mixpanel_status():
    """Check and fix Mixpanel status for specific distinct_ids."""
    distinct_ids = ['68311de16f5faeae6d015a66', '68ddde58d4192948d46621e6']
    
    client = get_bigquery_client()
    
    print("=" * 60)
    print("Checking Mixpanel status for specific users")
    print("=" * 60)
    print()
    
    for distinct_id in distinct_ids:
        # Query BigQuery to find the record
        query = f"""
        SELECT 
            distinct_id,
            ticket_id,
            mixpanel_request_id,
            mixpanel_deletion_status
        FROM `yotam-395120.peerplay.personal_data_deletion_tool`
        WHERE distinct_id = '{distinct_id}'
        ORDER BY inserted_at DESC
        LIMIT 1
        """
        
        try:
            results = client.query(query).result()
            row = next(results, None)
            
            if not row:
                print(f"⚠️  No record found for distinct_id: {distinct_id}")
                continue
            
            ticket_id = row.ticket_id
            mixpanel_request_id = row.mixpanel_request_id
            current_status = row.mixpanel_deletion_status
            
            print(f"Found record for {distinct_id}:")
            print(f"  Ticket ID: {ticket_id}")
            print(f"  Mixpanel Request ID: {mixpanel_request_id}")
            print(f"  Current Status: {current_status}")
            
            if not mixpanel_request_id:
                print(f"  ⚠️  No Mixpanel request ID found, skipping")
                continue
            
            # Check actual Mixpanel status
            print(f"  Checking Mixpanel API...")
            
            # Get config for API call
            config = get_config()
            oauth_token = config.get("mixpanel_gdpr_token")
            project_token = os.getenv("MIXPANEL_PROJECT_TOKEN") or config.get("mixpanel_project_id")
            
            if not project_token:
                project_token = "0e73d8fa8567c5bf2820b408701fa7be"
            
            url = f"https://mixpanel.com/api/app/data-deletions/v3.0/{mixpanel_request_id}?token={project_token}"
            headers = {"Authorization": f"Bearer {oauth_token}"}
            
            try:
                response = requests.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                result = response.json()
                
                print(f"  Mixpanel API Response: {result}")
                
                # Check various possible status fields
                status = result.get("status")
                results_data = result.get("results", {})
                task_status = results_data.get("status")
                task_state = results_data.get("state")
                
                print(f"  Response fields:")
                print(f"    - status: {status}")
                print(f"    - results.status: {task_status}")
                print(f"    - results.state: {task_state}")
                
                # Determine if completed - Mixpanel returns "SUCCESS" (uppercase) when completed
                is_completed = False
                if task_status == "SUCCESS" or task_status == "success" or task_status == "completed":
                    is_completed = True
                elif task_state in ["completed", "success", "done"]:
                    is_completed = True
                
                new_status = "completed" if is_completed else "pending"
                
                if new_status != current_status:
                    print(f"  ✅ Status needs update: {current_status} → {new_status}")
                    success = update_gdpr_request_status(ticket_id, mixpanel_status=new_status)
                    if success:
                        print(f"  ✅ Updated BigQuery record")
                    else:
                        print(f"  ❌ Failed to update BigQuery record")
                else:
                    print(f"  ✓ Status is already correct: {current_status}")
                    
            except Exception as e:
                print(f"  ❌ Error checking Mixpanel API: {e}")
            
            print()
            
        except Exception as e:
            print(f"❌ Error processing {distinct_id}: {e}")
            print()
    
    print("=" * 60)
    print("✅ Fix complete!")
    print("=" * 60)

if __name__ == "__main__":
    fix_mixpanel_status()

