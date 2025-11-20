#!/usr/bin/env python3
"""Update existing records with install_date and last_activity_date from dim_player."""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.bigquery_client import get_bigquery_client, get_player_dates
from google.cloud import bigquery

def update_existing_records():
    """Update existing records with player data from dim_player."""
    client = get_bigquery_client()
    
    project_id = "yotam-395120"
    dataset_id = "peerplay"
    table_id = "personal_data_deletion_tool"
    
    print("=" * 60)
    print("Updating existing records with player data")
    print("=" * 60)
    print()
    
    # Get all distinct_ids that need updating (where install_date is NULL)
    query = f"""
    SELECT DISTINCT distinct_id
    FROM `{project_id}.{dataset_id}.{table_id}`
    WHERE distinct_id IS NOT NULL
      AND (install_date IS NULL OR last_activity_date IS NULL)
    """
    
    try:
        results = client.query(query).result()
        distinct_ids = [row.distinct_id for row in results]
        
        if not distinct_ids:
            print("✅ All records already have install_date and last_activity_date")
            return
        
        print(f"Found {len(distinct_ids)} distinct_ids that need updating")
        print()
        
        # Fetch player data
        print("Fetching player data from dim_player...")
        player_data = get_player_dates(distinct_ids)
        print(f"✅ Fetched data for {len(player_data)} users")
        print()
        
        # Update each record
        updated_count = 0
        for distinct_id, player_info in player_data.items():
            install_date = player_info.get("install_date")
            last_activity_date = player_info.get("last_activity_date")
            
            if not install_date and not last_activity_date:
                continue
            
            update_query = f"""
            UPDATE `{project_id}.{dataset_id}.{table_id}`
            SET 
                install_date = @install_date,
                last_activity_date = @last_activity_date
            WHERE distinct_id = @distinct_id
              AND (install_date IS NULL OR last_activity_date IS NULL)
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("install_date", "DATE", install_date),
                    bigquery.ScalarQueryParameter("last_activity_date", "DATE", last_activity_date),
                    bigquery.ScalarQueryParameter("distinct_id", "STRING", distinct_id),
                ]
            )
            
            try:
                update_job = client.query(update_query, job_config=job_config)
                update_job.result()
                updated_count += 1
                print(f"✅ Updated {distinct_id}: install_date={install_date}, last_activity_date={last_activity_date}")
            except Exception as e:
                error_msg = str(e)
                if "streaming buffer" in error_msg.lower():
                    print(f"⚠️  {distinct_id}: Records in streaming buffer, will update later")
                else:
                    print(f"❌ Error updating {distinct_id}: {e}")
        
        print()
        print("=" * 60)
        print(f"✅ Updated {updated_count} distinct_ids")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    update_existing_records()

