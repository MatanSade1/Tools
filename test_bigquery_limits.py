#!/usr/bin/env python3
"""
Test script for BigQuery maximum_bytes_billed limits across different access methods.
"""

import sys
import os
import json
from datetime import datetime

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from google.cloud import bigquery
from google.api_core.exceptions import BadRequest

def get_bigquery_client():
    """Get BigQuery client (simplified version for testing)."""
    return bigquery.Client(project="yotam-395120")

def test_python_client():
    """Test Python BigQuery client with QueryJobConfig maximum_bytes_billed."""
    print("="*60)
    print("Testing Python BigQuery Client with maximum_bytes_billed")
    print("="*60)

    client = get_bigquery_client()

    # Test query with 500MB limit
    query = """
    -- Recipes Rewards Funnel Analysis - Individual Event Records
    WITH
    -- First identify users who triggered the first step (click_recipes_go_board)
    first_step AS (
      SELECT
        distinct_id,
        recipes_milestone_id,
        version_float,
        mp_os,
        live_ops_id,
        TIMESTAMP_MILLIS(CAST(res_timestamp AS INT64)) AS event_time
      FROM `yotam-395120.peerplay.vmp_master_event_normalized`
      WHERE mp_event_name = 'click_recipes_go_board'
        AND date >= CURRENT_DATE
        AND recipes_milestone_id IS NOT NULL
        AND mp_country_code NOT IN ('UA', 'IL')
    ),

    -- Then identify users who triggered the second step (rewards_recipes)
    second_step AS (
      SELECT
        distinct_id,
        recipes_milestone_id,
        TIMESTAMP_MILLIS(CAST(res_timestamp AS INT64)) AS event_time
      FROM `yotam-395120.peerplay.vmp_master_event_normalized`
      WHERE mp_event_name = 'rewards_recipes'
        AND date >= CURRENT_DATE
        AND recipes_milestone_id IS NOT NULL
        AND mp_country_code NOT IN ('UA', 'IL')
    )

    -- Match users and get the first subsequent rewards event (if any)
    SELECT
      f.distinct_id,
      f.version_float,
      f.mp_os,
      f.live_ops_id,
      f.recipes_milestone_id,
      f.event_time AS go_board_event_time,
      MIN(s.event_time) AS rewards_event_time,
      TIMESTAMP_DIFF(MIN(s.event_time), f.event_time, SECOND) AS time_between_events_seconds
    FROM first_step f
    LEFT JOIN second_step s
      ON f.distinct_id = s.distinct_id
      AND f.recipes_milestone_id = s.recipes_milestone_id
    GROUP BY
      f.distinct_id,
      f.version_float,
      f.mp_os,
      f.live_ops_id,
      f.recipes_milestone_id,
      f.event_time
    HAVING rewards_event_time IS NULL
    ORDER BY f.event_time DESC
    """

    job_config = bigquery.QueryJobConfig(
        maximum_bytes_billed=500000000  # 500MB limit
    )

    try:
        print(f"Executing query with 500MB limit...")
        start_time = datetime.now()

        query_job = client.query(query, job_config=job_config)
        results = query_job.result()

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Count results
        row_count = 0
        for row in results:
            row_count += 1

        print(f"✅ SUCCESS: Query completed in {duration:.2f} seconds")
        print(f"   Rows returned: {row_count}")
        print(f"   Bytes billed: {query_job.total_bytes_billed}")
        print(f"   Bytes processed: {query_job.total_bytes_processed}")
        print(f"   Cache hit: {query_job.cache_hit}")

        return True

    except BadRequest as e:
        if "bytes billed exceeds maximum_bytes_billed" in str(e):
            print(f"❌ LIMIT EXCEEDED: Query would exceed 500MB limit")
            print(f"   Error: {e}")
            return False
        else:
            print(f"❌ OTHER ERROR: {e}")
            return False
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}")
        return False

def test_python_client_no_limit():
    """Test the same query without any limit to see the actual cost."""
    print("\n" + "="*60)
    print("Testing Python BigQuery Client WITHOUT limit (to see actual cost)")
    print("="*60)

    client = get_bigquery_client()

    # Simplified version for testing
    query = """
    SELECT COUNT(*) as total_rows,
           COUNT(DISTINCT distinct_id) as unique_users
    FROM `yotam-395120.peerplay.vmp_master_event_normalized`
    WHERE date >= CURRENT_DATE - 7
    """

    try:
        print("Executing query without limit...")
        start_time = datetime.now()

        query_job = client.query(query)
        results = query_job.result()

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        for row in results:
            print(f"   Total rows: {row.total_rows}")
            print(f"   Unique users: {row.unique_users}")

        print(f"✅ SUCCESS: Query completed in {duration:.2f} seconds")
        print(f"   Bytes billed: {query_job.total_bytes_billed}")
        print(f"   Bytes processed: {query_job.total_bytes_processed}")
        print(f"   Cache hit: {query_job.cache_hit}")

        return query_job.total_bytes_billed

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return None

if __name__ == "__main__":
    print("BigQuery Maximum Bytes Billed Testing")
    print("=====================================")

    # Test without limit first to see actual cost
    actual_bytes = test_python_client_no_limit()

    if actual_bytes:
        print(f"\nActual query cost: {actual_bytes} bytes ({actual_bytes/1000000000:.2f} GB)")
        limit_bytes = 500000000  # 500MB
        print(f"Testing with limit: {limit_bytes} bytes ({limit_bytes/1000000000:.2f} GB)")

        if actual_bytes > limit_bytes:
            print("⚠️  WARNING: Actual cost exceeds limit - expect query to fail")
        else:
            print("✅ INFO: Actual cost is below limit - expect query to succeed")

    # Test with limit
    success = test_python_client()

    print("\n" + "="*60)
    if success:
        print("OVERALL RESULT: ✅ Python client limit test PASSED")
    else:
        print("OVERALL RESULT: ❌ Python client limit test FAILED")
    print("="*60)


