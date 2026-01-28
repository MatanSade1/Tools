#!/usr/bin/env python3
import sys
sys.path.append('/Users/matansade/Tools')
from shared.bigquery_client import get_bigquery_client

query = """
-- Check what data exists for liveops_id 4271
SELECT 
  COUNT(*) as total_events,
  COUNT(DISTINCT distinct_id) as unique_users,
  MIN(version_float) as min_version,
  MAX(version_float) as max_version,
  COUNTIF(version_float < 0.378) as events_below_378,
  COUNTIF(version_float >= 0.378) as events_at_or_above_378,
  COUNTIF(cycle = 1) as events_with_cycle_1,
  COUNTIF(liveops_id = 4271) as events_with_top_level_liveops_id,
  COUNTIF(tbt_snapshot IS NOT NULL) as events_with_tbt_snapshot
FROM `yotam-395120.peerplay.vmp_master_event_normalized`
WHERE date >= '2026-01-27'
  AND date <= '2026-01-28'
  AND mp_event_name = 'timed_board_task_started'
  AND (liveops_id = 4271 OR JSON_EXTRACT_SCALAR(tbt_snapshot, '$.liveops_id') = '4271')
  AND mp_country_code NOT IN ('UA', 'IL', 'AM')
  AND distinct_id NOT IN (SELECT distinct_id FROM `yotam-395120.peerplay.potential_fraudsters`)
  AND distinct_id NOT IN (SELECT distinct_id FROM `yotam-395120.peerplay.state_loss_temp_users`)
"""

client = get_bigquery_client()
result = client.query(query).result()

for row in result:
    print(f"Total events: {row['total_events']}")
    print(f"Unique users: {row['unique_users']}")
    print(f"Min version: {row['min_version']}")
    print(f"Max version: {row['max_version']}")
    print(f"Events with version < 0.378: {row['events_below_378']}")
    print(f"Events with version >= 0.378: {row['events_at_or_above_378']}")
    print(f"Events with cycle=1: {row['events_with_cycle_1']}")
    print(f"Events with top-level liveops_id=4271: {row['events_with_top_level_liveops_id']}")
    print(f"Events with tbt_snapshot: {row['events_with_tbt_snapshot']}")
