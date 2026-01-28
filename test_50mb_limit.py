#!/usr/bin/env python3
"""
Test the Recipes Rewards Funnel query with 50MB limit using Python BigQuery Client.
"""

import sys
import os
from datetime import datetime

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from google.cloud import bigquery
from google.api_core.exceptions import BadRequest

def test_50mb_limit():
    """Test the query with 50MB limit."""
    print("Testing Python BigQuery Client with 50MB limit")
    print("=" * 50)

    client = bigquery.Client(project="yotam-395120")

    # The full query
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

    # Set 50MB limit
    limit_bytes = 50000000  # 50MB

    job_config = bigquery.QueryJobConfig(
        maximum_bytes_billed=limit_bytes
    )

    print(f"Query limit set to: {limit_bytes:,} bytes ({limit_bytes/1000000:.1f} MB)")
    print("Executing query...")

    try:
        start_time = datetime.now()
        query_job = client.query(query, job_config=job_config)
        results = query_job.result()
        end_time = datetime.now()

        # Count results
        row_count = 0
        for row in results:
            row_count += 1

        print("❌ UNEXPECTED: Query succeeded despite 50MB limit!")
        print(f"Rows returned: {row_count}")
        print(f"Execution time: {(end_time - start_time).total_seconds():.2f} seconds")
        print(f"Bytes billed: {query_job.total_bytes_billed:,}")
        return False

    except BadRequest as e:
        error_str = str(e)
        if "Query exceeded limit for bytes billed" in error_str:
            print("✅ SUCCESS: Query correctly blocked by 50MB limit")
            print(f"Error: {error_str}")
            return True
        else:
            print(f"❌ OTHER ERROR: {e}")
            return False
    except Exception as e:
        error_str = str(e)
        if "Query exceeded limit for bytes billed" in error_str:
            print("✅ SUCCESS: Query correctly blocked by 50MB limit")
            print(f"Error: {error_str}")
            return True
        else:
            print(f"❌ UNEXPECTED ERROR: {e}")
            return False

if __name__ == "__main__":
    success = test_50mb_limit()

    print("\n" + "=" * 50)
    if success:
        print("RESULT: ✅ 50MB limit test PASSED")
    else:
        print("RESULT: ❌ 50MB limit test FAILED")
    print("=" * 50)


