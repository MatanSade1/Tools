#!/usr/bin/env python3
"""
Test pandas-gbq with maximum_bytes_billed limits.
"""

import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

try:
    import pandas as pd
    from google.api_core.exceptions import BadRequest
    print("Testing pandas-gbq with maximum_bytes_billed...")
except ImportError as e:
    print(f"pandas or pandas-gbq not available: {e}")
    sys.exit(1)

def test_pandas_gbq():
    """Test pandas-gbq with maximumBytesBilled configuration."""

    # Test with a simple query first
    simple_query = """
    SELECT COUNT(*) as total_count
    FROM `yotam-395120.peerplay.vmp_master_event_normalized`
    WHERE date >= CURRENT_DATE
    """

    try:
        print("Testing pandas-gbq with simple query...")
        df = pd.read_gbq(
            simple_query,
            project_id='yotam-395120',
            configuration={'query': {'maximumBytesBilled': '500000000'}}
        )
        print(f"✅ Simple query succeeded. Result: {df.iloc[0, 0]} rows")
    except BadRequest as e:
        print(f"❌ Simple query failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

    # Test with the full query that exceeds limit
    full_query = """
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

    try:
        print("Testing pandas-gbq with full query (should fail due to 500MB limit)...")
        df = pd.read_gbq(
            full_query,
            project_id='yotam-395120',
            configuration={'query': {'maximumBytesBilled': '500000000'}}
        )
        print(f"❌ Full query unexpectedly succeeded. Shape: {df.shape}")
        return False
    except BadRequest as e:
        if "bytes billed exceeds maximum_bytes_billed" in str(e) or "bytesBilledLimitExceeded" in str(e) or "Query exceeded limit for bytes billed" in str(e):
            print("✅ Full query correctly failed due to bytes billed limit")
            return True
        else:
            print(f"❌ Full query failed with unexpected error: {e}")
            return False
    except Exception as e:
        # Check if the error message contains the limit exceeded text
        error_str = str(e)
        if "Query exceeded limit for bytes billed" in error_str:
            print("✅ Full query correctly failed due to bytes billed limit")
            return True
        else:
            print(f"❌ Unexpected error: {e}")
            return False

if __name__ == "__main__":
    print("Testing pandas-gbq maximum_bytes_billed functionality")
    print("="*55)

    success = test_pandas_gbq()

    print("\n" + "="*55)
    if success:
        print("OVERALL RESULT: ✅ pandas-gbq limit test PASSED")
    else:
        print("OVERALL RESULT: ❌ pandas-gbq limit test FAILED")
    print("="*55)
