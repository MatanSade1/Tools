"""
Mission Configuration Validator

Validates user mission configurations by comparing:
1. Segment assignments between BigQuery segmentation logic and actual user data
2. Mission configurations between actual user values and expected segment values

Usage:
    python mission_config_validator.py --live-ops-id 4253 --start-date 2026-01-26 --end-date 2026-01-26
    python mission_config_validator.py --live-ops-id 4253 --days-back 7
"""

import os
import sys
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
from google.cloud import bigquery
from googleapiclient.discovery import build
from google.oauth2 import service_account
import google.auth

# Add shared modules to path
sys.path.append(os.path.dirname(__file__))
from shared.bigquery_client import get_bigquery_client
from shared.sheets_client import read_config_from_sheets, get_sheets_service


# Spreadsheet IDs from URLs
CONFIG_SPREADSHEET_ID = "1L94yMz3iahaJdTCAE5v5NAPFfnLJ9DHVjlTWf11CIKM"
CONFIG_SHEET_GID = "1653708078"
OUTPUT_SPREADSHEET_ID = "1hph4x2MPemtTD8B8TSO8yjV2jH6XuM19CySTsujpFDw"

# BigQuery configuration
BQ_PROJECT = "yotam-395120"
BQ_DATASET = "peerplay"

# Configuration parameters
NUM_POSITIONS = 8
FIELDS_PER_POSITION = ["item_id", "item_quantity", "mission_type", "target_amount"]


def fetch_user_data(live_ops_id: int, start_date: str, end_date: str, feature: str, version_filter: str = '>=0.378') -> pd.DataFrame:
    """
    Fetch ACTUAL user data from BigQuery.
    Queries feature-specific impression events and parses the snapshot JSON.
    
    Args:
        live_ops_id: Live ops ID to filter by (e.g., 4253 for missions, 4230 for race)
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        feature: Feature to validate ('missions' or 'race')
    
    Returns:
        DataFrame with user data including distinct_id, config_segment, and parsed configuration
    """
    print(f"📖 Querying user data from BigQuery...")
    print(f"   Feature: {feature}")
    print(f"   Live Ops ID: {live_ops_id}")
    print(f"   Date Range: {start_date} to {end_date}")
    
    client = get_bigquery_client()
    
    # Feature-specific event names and snapshot fields
    if feature == 'missions':
        event_name = 'impression_missions_popup'
        snapshot_field = 'missions_snapshot'
        live_ops_field = 'live_ops_id'
    elif feature == 'race':
        event_name = 'impression_race_popup'
        snapshot_field = 'race_snapshot'
        live_ops_field = 'race_live_ops_id'
    elif feature == 'time-board-tasks':
        event_name = 'timed_board_task_started'
        snapshot_field = 'tbt_snapshot'
        live_ops_field = 'liveops_id'
    else:
        raise ValueError(f"Unsupported feature: {feature}")
    
    # For time-board-tasks, liveops_id is inside the JSON snapshot
    if feature == 'time-board-tasks':
        # For versions < 0.378, tbt_snapshot doesn't exist - use top-level liveops_id
        # For versions >= 0.378, use tbt_snapshot
        if '<' in version_filter:
            # Old version query - filter by liveops_id in active_segments, not in tbt_snapshot
            query = f"""
            WITH tbt_events AS (
              -- Get timed_board_task_started events with cycle=1 (old versions)
              SELECT
                distinct_id,
                {snapshot_field},
                goal_item_id_1,
                CAST(res_timestamp AS INT64) AS tbt_timestamp
              FROM `{BQ_PROJECT}.{BQ_DATASET}.vmp_master_event_normalized`
              WHERE date >= '{start_date}'
                AND date <= '{end_date}'
                AND mp_event_name = '{event_name}'
                AND cycle = 1
                AND version_float {version_filter}
                AND mp_country_code NOT IN ('UA', 'IL', 'AM')
                AND distinct_id NOT IN (SELECT distinct_id FROM `{BQ_PROJECT}.{BQ_DATASET}.potential_fraudsters`)
                AND distinct_id NOT IN (SELECT distinct_id FROM `{BQ_PROJECT}.{BQ_DATASET}.state_loss_temp_users`)
              QUALIFY ROW_NUMBER() OVER (
                PARTITION BY distinct_id 
                ORDER BY res_timestamp DESC, counter_per_session_game_side DESC
              ) = 1
            ),
            config_events AS (
              -- Get the most recent dynamic_configuration_loaded event before each tbt event
              SELECT
                tbt.distinct_id,
                tbt.{snapshot_field},
                tbt.goal_item_id_1,
                tbt.tbt_timestamp,
                cfg.active_segments,
                ROW_NUMBER() OVER (
                  PARTITION BY tbt.distinct_id 
                  ORDER BY cfg.res_timestamp DESC
                ) AS rn
              FROM tbt_events tbt
              LEFT JOIN `{BQ_PROJECT}.{BQ_DATASET}.vmp_master_event_normalized` cfg
                ON tbt.distinct_id = cfg.distinct_id
                AND cfg.mp_event_name = 'dynamic_configuration_loaded'
                AND CAST(cfg.res_timestamp AS INT64) < tbt.tbt_timestamp
                AND cfg.date >= DATE_SUB('{start_date}', INTERVAL 1 DAY)
                AND cfg.date <= '{end_date}'
            )
            SELECT
              distinct_id,
              {snapshot_field},
              goal_item_id_1,
              active_segments,
              '{live_ops_id}' as liveops_id,
              TIMESTAMP_MILLIS(tbt_timestamp) AS event_time
            FROM config_events
            WHERE rn = 1
              AND REGEXP_CONTAINS(active_segments, r'"config_type"\\s*:\\s*"TimedBoardTaskFeatureConfigData"[^}}]*"liveops_id"\\s*:\\s*{live_ops_id}')
            """
        else:
            # New version query (with tbt_snapshot)
            query = f"""
            WITH tbt_events AS (
              -- Get timed_board_task_started events with cycle=1
              SELECT
                distinct_id,
                {snapshot_field},
                goal_item_id_1,
                CAST(res_timestamp AS INT64) AS tbt_timestamp,
                JSON_EXTRACT_SCALAR({snapshot_field}, '$.liveops_id') AS liveops_id
              FROM `{BQ_PROJECT}.{BQ_DATASET}.vmp_master_event_normalized`
              WHERE date >= '{start_date}'
                AND date <= '{end_date}'
                AND mp_event_name = '{event_name}'
                AND JSON_EXTRACT_SCALAR({snapshot_field}, '$.liveops_id') = '{live_ops_id}'
                AND cycle = 1
                AND version_float {version_filter}
                AND mp_country_code NOT IN ('UA', 'IL', 'AM')
                AND distinct_id NOT IN (SELECT distinct_id FROM `{BQ_PROJECT}.{BQ_DATASET}.potential_fraudsters`)
                AND distinct_id NOT IN (SELECT distinct_id FROM `{BQ_PROJECT}.{BQ_DATASET}.state_loss_temp_users`)
              QUALIFY ROW_NUMBER() OVER (
                PARTITION BY distinct_id 
                ORDER BY res_timestamp DESC, counter_per_session_game_side DESC
              ) = 1
            ),
            config_events AS (
              -- Get the most recent dynamic_configuration_loaded event before each tbt event
              SELECT
                tbt.distinct_id,
                tbt.{snapshot_field},
                tbt.goal_item_id_1,
                tbt.tbt_timestamp,
                tbt.liveops_id,
                cfg.active_segments,
                ROW_NUMBER() OVER (
                  PARTITION BY tbt.distinct_id 
                  ORDER BY cfg.res_timestamp DESC
                ) AS rn
              FROM tbt_events tbt
              LEFT JOIN `{BQ_PROJECT}.{BQ_DATASET}.vmp_master_event_normalized` cfg
                ON tbt.distinct_id = cfg.distinct_id
                AND cfg.mp_event_name = 'dynamic_configuration_loaded'
                AND CAST(cfg.res_timestamp AS INT64) < tbt.tbt_timestamp
                AND cfg.date >= DATE_SUB('{start_date}', INTERVAL 7 DAY)
                AND cfg.date <= '{end_date}'
            )
            SELECT
              distinct_id,
              {snapshot_field},
              goal_item_id_1,
              active_segments,
              liveops_id,
              TIMESTAMP_MILLIS(tbt_timestamp) AS event_time
            FROM config_events
            WHERE rn = 1
            """
    elif feature == 'race':
        # For race, filter only events with race_board_level=1
        query = f"""
        SELECT
          distinct_id,
          {snapshot_field},
          TIMESTAMP_MILLIS(CAST(res_timestamp AS INT64)) AS event_time
        FROM `{BQ_PROJECT}.{BQ_DATASET}.vmp_master_event_normalized`
        WHERE date >= '{start_date}'
          AND date <= '{end_date}'
          AND mp_event_name = '{event_name}'
          AND {live_ops_field} = {live_ops_id}
          AND race_board_level = 1
          AND version_float {version_filter}
          AND mp_country_code NOT IN ('UA', 'IL', 'AM')
          AND distinct_id NOT IN (SELECT distinct_id FROM `{BQ_PROJECT}.{BQ_DATASET}.potential_fraudsters`)
          AND distinct_id NOT IN (SELECT distinct_id FROM `{BQ_PROJECT}.{BQ_DATASET}.state_loss_temp_users`)
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY distinct_id 
          ORDER BY res_timestamp DESC, counter_per_session_game_side DESC
        ) = 1
        """
    else:
        # For missions and other features
        query = f"""
        SELECT
          distinct_id,
          {snapshot_field},
          TIMESTAMP_MILLIS(CAST(res_timestamp AS INT64)) AS event_time
        FROM `{BQ_PROJECT}.{BQ_DATASET}.vmp_master_event_normalized`
        WHERE date >= '{start_date}'
          AND date <= '{end_date}'
          AND mp_event_name = '{event_name}'
          AND {live_ops_field} = {live_ops_id}
          AND version_float {version_filter}
          AND mp_country_code NOT IN ('UA', 'IL', 'AM')
          AND distinct_id NOT IN (SELECT distinct_id FROM `{BQ_PROJECT}.{BQ_DATASET}.potential_fraudsters`)
          AND distinct_id NOT IN (SELECT distinct_id FROM `{BQ_PROJECT}.{BQ_DATASET}.state_loss_temp_users`)
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY distinct_id 
          ORDER BY res_timestamp DESC, counter_per_session_game_side DESC
        ) = 1
        """
    
    try:
        print(f"   Running query...")
        df = client.query(query).result().to_dataframe()
        print(f"✅ Fetched {len(df)} users from BigQuery")
        
        if len(df) == 0:
            raise ValueError(f"No users found for live_ops_id={live_ops_id} in date range {start_date} to {end_date}")
        
        # Parse the snapshot JSON column (feature-specific)
        import json
        
        parsed_data = []
        snapshot_column = snapshot_field
        
        for idx, row in df.iterrows():
            distinct_id = row.get('distinct_id')
            snapshot_json = row.get(snapshot_column)
            
            # For old versions (< 0.378) with time-board-tasks, snapshot_json may be NULL
            # We still need to process for segment comparison using active_segments
            if not snapshot_json or pd.isna(snapshot_json):
                if feature == 'time-board-tasks':
                    # For segment-only comparison in old versions
                    data = {}
                    config_segment = ''  # Will be extracted from active_segments
                else:
                    continue
            else:
                try:
                    data = json.loads(snapshot_json)
                except (json.JSONDecodeError, TypeError) as e:
                    print(f"⚠️  Warning: Could not parse {snapshot_column} for user {distinct_id}: {e}")
                    continue
                config_segment = data.get('config_segment', '')  # Default from snapshot (overridden for time-board-tasks)
            
            try:
                # Create a flat structure
                user_data = {
                    'distinct_id': distinct_id,
                    'config_segment': config_segment,  # Will be overridden for time-board-tasks from active_segments
                }
                
                if feature == 'missions':
                    # Parse mission tasks
                    mission_tasks = data.get('mission_tasks', [])
                    for task in mission_tasks:
                        position = task.get('position')
                        if position:
                            user_data[f'item_id_{position}'] = task.get('item_id_1')
                            user_data[f'item_quantity_{position}'] = task.get('item_quantity_1')
                            user_data[f'mission_type_{position}'] = task.get('mission_type')
                            user_data[f'target_amount_{position}'] = task.get('target_amount')
                
                elif feature == 'race':
                    # Parse race configuration
                    user_data['current_level'] = data.get('current_level', 1)  # Default to level 1
                    user_data['target_points'] = data.get('target_points')
                    
                    # Parse place rewards
                    place_rewards = data.get('place_rewards', [])
                    for reward in place_rewards:
                        place = reward.get('place')
                        if place:
                            user_data[f'place_{place}_item_id_1'] = reward.get('item_id_1')
                            user_data[f'place_{place}_item_id_2'] = reward.get('item_id_2')
                            user_data[f'place_{place}_item_quantity_1'] = reward.get('item_quantity_1')
                            user_data[f'place_{place}_item_quantity_2'] = reward.get('item_quantity_2')
                
                elif feature == 'time-board-tasks':
                    # Parse time-board-tasks configuration (if available in new versions)
                    user_data['task_id'] = data.get('task_id')
                    # goal_item_id_1 is a top-level column, not in JSON
                    user_data['goal_item_id_1'] = row.get('goal_item_id_1')  # Used to match configuration
                    user_data['item_id_1'] = data.get('item_id_1')
                    user_data['item_id_2'] = data.get('item_id_2')
                    user_data['item_id_3'] = data.get('item_id_3')
                    user_data['item_quantity_1'] = data.get('item_quantity_1')
                    user_data['item_quantity_2'] = data.get('item_quantity_2')
                    user_data['item_quantity_3'] = data.get('item_quantity_3')
                    user_data['is_progressive'] = data.get('is_progressive', False)
                    
                    # Get actual segment from active_segments (from dynamic_configuration_loaded event)
                    active_segments_json = row.get('active_segments')
                    actual_segment = None
                    
                    if active_segments_json and not pd.isna(active_segments_json):
                        try:
                            active_segments = json.loads(active_segments_json)
                            # For old versions, get liveops_id from top-level column
                            liveops_id_from_row = str(row.get('liveops_id', ''))
                            liveops_id_from_tbt = str(data.get('liveops_id', '')) if data else ''
                            # Use whichever is available
                            liveops_id_to_match = liveops_id_from_tbt or liveops_id_from_row
                            
                            # Find the matching segment for this liveops_id and TimedBoardTaskFeatureConfigData
                            for segment_config in active_segments:
                                if (str(segment_config.get('liveops_id', '')) == liveops_id_to_match and 
                                    segment_config.get('config_type') == 'TimedBoardTaskFeatureConfigData'):
                                    actual_segment = segment_config.get('liveops_segment', '')
                                    break
                        except (json.JSONDecodeError, TypeError) as e:
                            print(f"⚠️  Warning: Could not parse active_segments for user {distinct_id}: {e}")
                    
                    # Override config_segment with the one from active_segments (use liveops_segment)
                    if actual_segment:
                        user_data['config_segment'] = actual_segment  # Update user_data, not just local variable
                
                parsed_data.append(user_data)
            except json.JSONDecodeError as e:
                print(f"⚠️  Warning: Could not parse JSON for user {distinct_id}: {e}")
                continue
        
        result_df = pd.DataFrame(parsed_data)
        print(f"✅ Parsed {len(result_df)} users with {feature} data")
        
        return result_df
    
    except Exception as e:
        print(f"❌ Error querying BigQuery: {e}")
        raise


def fetch_expected_configs(config_spreadsheet_id: str, feature: str = 'missions') -> Dict[str, Dict]:
    """
    Fetch expected configurations from the config spreadsheet.
    
    Args:
        config_spreadsheet_id: Google Spreadsheet ID containing expected configurations
        feature: Feature being validated ('missions' or 'race')
    
    Returns:
        Dictionary mapping segment_id to expected configuration
    """
    print(f"📖 Reading expected configurations from spreadsheet...")
    print(f"   Spreadsheet ID: {config_spreadsheet_id}")
    
    # Read all data from the sheet
    # Feature-specific sheet tabs
    if feature == 'race':
        sheet_range = "'Full config to upload'!A:ZZ"
    elif feature == 'time-board-tasks':
        sheet_range = "'BoardTasks'!A:ZZ"
    else:
        sheet_range = "A:ZZ"
    
    rows = read_config_from_sheets(config_spreadsheet_id, sheet_range)
    
    if not rows or len(rows) < 2:
        raise ValueError("Config spreadsheet is empty or has no data rows")
    
    # Pad rows to match header length (some rows may have fewer columns)
    header = rows[0]
    header_len = len(header)
    padded_rows = []
    for row in rows[1:]:
        if len(row) < header_len:
            # Pad with empty strings
            padded_row = row + [''] * (header_len - len(row))
            padded_rows.append(padded_row)
        else:
            padded_rows.append(row[:header_len])  # Trim if too long
    
    # Convert to DataFrame
    df = pd.DataFrame(padded_rows, columns=header)
    
    # Index by appropriate key depending on feature
    configs = {}
    if feature == 'time-board-tasks':
        # For time-board-tasks, index by Item1Id (column C)
        for _, row in df.iterrows():
            item1_id = row.get('Item1Id') or row.get('item1_id') or row.get('Item 1 ID')
            if item1_id:
                configs[str(item1_id)] = row.to_dict()
        print(f"✅ Read {len(configs)} configurations indexed by Item1Id")
        print(f"   Item1Ids: {', '.join(list(configs.keys())[:5])}{'...' if len(configs) > 5 else ''}")
    else:
        # For missions and race, index by SegmentId
        for _, row in df.iterrows():
            segment_id = row.get('SegmentId') or row.get('segment_id') or row.get('Segment ID')
            if segment_id:
                configs[str(segment_id)] = row.to_dict()
        print(f"✅ Read {len(configs)} segment configurations")
        print(f"   Segments: {', '.join(list(configs.keys())[:5])}{'...' if len(configs) > 5 else ''}")
    
    return configs


def query_bq_time_board_tasks_segments(distinct_ids: List[str], config_spreadsheet_id: str, tab_name: str = 'distinct_id_segmentation_list') -> Dict[str, str]:
    """
    For time-board-tasks, expected segments are defined in a spreadsheet tab.
    
    This tab contains:
    - Column A (SegmentId): Expected segment for the user
    - Column C (UserId): distinct_id of the user
    
    Args:
        distinct_ids: List of distinct_id values to query
        config_spreadsheet_id: Spreadsheet ID containing the segment assignments
        tab_name: Name of the tab containing segment assignments (default: 'distinct_id_segmentation_list')
    
    Returns:
        Dictionary mapping distinct_id to expected segment_name
    """
    if not distinct_ids:
        return {}
    
    print(f"🔍 Reading time-board-tasks segment assignments from '{tab_name}' tab...")
    
    try:
        from shared.sheets_client import read_config_from_sheets
        
        # Read the specified tab
        rows = read_config_from_sheets(config_spreadsheet_id, f"'{tab_name}'!A:C")
        
        if not rows or len(rows) < 2:
            print(f"⚠️  No data found in '{tab_name}' tab")
            return {}
        
        # Parse the data (skip header row)
        segments = {}
        header = rows[0]
        
        # Find column indices (case-insensitive)
        segment_col_idx = None
        user_id_col_idx = None
        
        for i, col_name in enumerate(header):
            if col_name and normalize_column_name(col_name) == normalize_column_name('SegmentId'):
                segment_col_idx = i
            elif col_name and normalize_column_name(col_name) == normalize_column_name('UserId'):
                user_id_col_idx = i
        
        if segment_col_idx is None or user_id_col_idx is None:
            print(f"⚠️  Could not find SegmentId or UserId columns in 'distinct_id_segmentation_list' tab")
            return {}
        
        # Build the mapping
        for row in rows[1:]:
            if len(row) > max(segment_col_idx, user_id_col_idx):
                user_id = str(row[user_id_col_idx]).strip() if row[user_id_col_idx] else None
                segment = str(row[segment_col_idx]).strip() if row[segment_col_idx] else None
                
                if user_id and segment and user_id in distinct_ids:
                    segments[user_id] = segment
        
        print(f"✅ Found expected segments for {len(segments)} users")
        
        not_found = set(distinct_ids) - set(segments.keys())
        if not_found:
            print(f"⚠️  {len(not_found)} users not found in 'distinct_id_segmentation_list' tab")
        
        return segments
    
    except Exception as e:
        print(f"❌ Error reading time-board-tasks segments from spreadsheet: {e}")
        return {}


def query_bq_race_segments(distinct_ids: List[str], config_spreadsheet_id: str) -> Dict[str, str]:
    """
    For race, expected segments are defined in the 'list for liveops ' tab (note: trailing space in tab name).
    
    This tab contains:
    - Column A (SegmentId): Expected segment for the user
    - Column C (UserId): distinct_id of the user
    
    Args:
        distinct_ids: List of distinct_id values to query
        config_spreadsheet_id: Spreadsheet ID containing the segment assignments
    
    Returns:
        Dictionary mapping distinct_id to expected segment_name
    """
    if not distinct_ids:
        return {}
    
    print(f"🔍 Reading race segment assignments from 'list for liveops ' tab...")
    
    try:
        from shared.sheets_client import read_config_from_sheets
        
        # Read the 'list for liveops ' tab (note: tab name has trailing space)
        rows = read_config_from_sheets(config_spreadsheet_id, "'list for liveops '!A:C")
        
        if not rows or len(rows) < 2:
            print(f"⚠️  No data found in 'list for liveops ' tab")
            return {}
        
        # Parse the data (skip header row)
        segments = {}
        header = rows[0]
        
        # Find column indices (case-insensitive)
        segment_col_idx = None
        user_id_col_idx = None
        
        for i, col_name in enumerate(header):
            if col_name and normalize_column_name(col_name) == normalize_column_name('SegmentId'):
                segment_col_idx = i
            elif col_name and normalize_column_name(col_name) == normalize_column_name('UserId'):
                user_id_col_idx = i
        
        if segment_col_idx is None or user_id_col_idx is None:
            print(f"⚠️  Could not find SegmentId or UserId columns in 'list for liveops ' tab")
            return {}
        
        # Build the mapping
        for row in rows[1:]:
            if len(row) > max(segment_col_idx, user_id_col_idx):
                user_id = str(row[user_id_col_idx]).strip() if row[user_id_col_idx] else None
                segment = str(row[segment_col_idx]).strip() if row[segment_col_idx] else None
                
                if user_id and segment and user_id in distinct_ids:
                    segments[user_id] = segment
        
        print(f"✅ Found expected segments for {len(segments)} users")
        
        not_found = set(distinct_ids) - set(segments.keys())
        if not_found:
            print(f"⚠️  {len(not_found)} users not found in 'list for liveops ' tab")
        
        return segments
    
    except Exception as e:
        print(f"❌ Error reading race segments from spreadsheet: {e}")
        return {}
    


def query_bq_segments(distinct_ids: List[str], feature: str, config_spreadsheet_id: str = None, segment_tab: str = None) -> Dict[str, str]:
    """
    Calculate EXPECTED segment names for the given distinct_ids using feature-specific segmentation logic.
    
    Args:
        distinct_ids: List of distinct_id values to query
        feature: Feature to calculate segments for ('missions' or 'race')
        config_spreadsheet_id: Spreadsheet ID for race segment lookup
        segment_tab: Custom tab name for segment assignments (optional)
    
    Returns:
        Dictionary mapping distinct_id to expected segment_name
    """
    if not distinct_ids:
        return {}
    
    # Route to feature-specific segmentation
    if feature == 'race':
        return query_bq_race_segments(distinct_ids, config_spreadsheet_id)
    elif feature == 'time-board-tasks':
        tab_name = segment_tab if segment_tab else 'distinct_id_segmentation_list'
        return query_bq_time_board_tasks_segments(distinct_ids, config_spreadsheet_id, tab_name)
    
    # Default: missions segmentation
    print(f"🔍 Calculating expected segments for {len(distinct_ids)} users...")
    
    client = get_bigquery_client()
    
    # Build parameterized query with segmentation logic
    query = f"""
    WITH segmented_users AS (
      SELECT
        distinct_id,
        CASE
          -- mission_1: median between 3500-5500, >4 active days, chapter < 12
          WHEN median_daily_spend BETWEEN 3500 AND 5500 
            AND total_active_days > 4 
            AND max_chapter < 12 
          THEN 'mission_1'
          
          -- mission_2: median > 5500, >4 active days, chapter < 12
          WHEN median_daily_spend > 5500 
            AND total_active_days > 4 
            AND max_chapter < 12 
          THEN 'mission_2'
          
          -- above_chapter_12: median < 3500, chapter >= 12
          WHEN median_daily_spend < 3500 
            AND max_chapter >= 12 
          THEN 'above_chapter_12'
          
          -- mission_1_chapter_12: median between 3500-5500, >4 active days, chapter >= 12
          WHEN median_daily_spend BETWEEN 3500 AND 5500 
            AND total_active_days > 4 
            AND max_chapter >= 12 
          THEN 'mission_1_chapter_12'
          
          -- mission_2_chapter_12: median > 5500, >4 active days, chapter >= 12
          WHEN median_daily_spend > 5500 
            AND total_active_days > 4 
            AND max_chapter >= 12 
          THEN 'mission_2_chapter_12'
          
          ELSE 'default'
        END as segment_name,
        'MissionsConfigData' as config_types
      FROM (
        SELECT
          distinct_id,
          ROUND(median_14_active_days_total_credits_spend, 2) as median_daily_spend,
          credit_spend_active_days as total_active_days,
          last_chapter as max_chapter
        FROM `{BQ_PROJECT}.{BQ_DATASET}.segmentation_parameters`
        WHERE 
          credit_spend_active_days >= 1
          AND days_since_last_activity <= 45
          AND distinct_id IN UNNEST(@distinct_ids)
      )
    )
    SELECT 
      distinct_id,
      segment_name,
      config_types
    FROM segmented_users
    ORDER BY segment_name, distinct_id
    """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ArrayQueryParameter("distinct_ids", "STRING", distinct_ids)
        ]
    )
    
    try:
        results = client.query(query, job_config=job_config).result()
        
        segments = {}
        for row in results:
            segments[row.distinct_id] = row.segment_name
        
        print(f"✅ Calculated segments for {len(segments)} users")
        
        # Report users not found (those not in segmentation_parameters or don't meet criteria)
        not_found = set(distinct_ids) - set(segments.keys())
        if not_found:
            print(f"⚠️  {len(not_found)} users not in segmentation_parameters or don't meet criteria")
        
        return segments
    
    except Exception as e:
        print(f"❌ Error calculating segments: {e}")
        raise


def normalize_column_name(name: str) -> str:
    """Normalize column name by removing spaces and converting to lowercase."""
    return str(name).strip().lower().replace(' ', '_').replace('-', '_')


def find_column(df: pd.DataFrame, possible_names: List[str]) -> Optional[str]:
    """
    Find a column in the DataFrame by checking multiple possible names.
    
    Args:
        df: DataFrame to search
        possible_names: List of possible column names (case-insensitive)
    
    Returns:
        Actual column name if found, None otherwise
    """
    normalized_cols = {normalize_column_name(col): col for col in df.columns}
    
    for name in possible_names:
        normalized = normalize_column_name(name)
        if normalized in normalized_cols:
            return normalized_cols[normalized]
    
    return None


def get_user_config_value(user_row: pd.Series, position: int, field: str) -> Optional[str]:
    """
    Get configuration value from user row for a specific position and field.
    
    Args:
        user_row: User data row
        position: Position number (1-8)
        field: Field name (item_id, item_quantity, mission_type, target_amount)
    
    Returns:
        Configuration value as string, or None if not found
    """
    # Try different column naming patterns
    possible_patterns = [
        f"{field}_{position}",
        f"position_{position}_{field}",
        f"pos_{position}_{field}",
        f"p{position}_{field}",
        f"{field}{position}",
    ]
    
    for pattern in possible_patterns:
        col = find_column(pd.DataFrame([user_row.to_dict()]), [pattern])
        if col and col in user_row.index:
            value = user_row[col]
            if pd.notna(value) and str(value).strip() != '':
                return str(value).strip()
    
    return None


def get_expected_race_config_value(config_row: Dict, level: int, field: str) -> Optional[str]:
    """
    Get expected race configuration value for a specific level and field.
    
    Args:
        config_row: Expected configuration row
        level: Level number (1, 2, 3, etc.) corresponding to SubConfig1, SubConfig2, etc.
        field: Field name (TargetPoints, Place1Reward1Id, Place1Reward1Count, etc.)
    
    Returns:
        Expected configuration value as string, or None if not found
    """
    # Race configuration format: SubConfig<level><field>
    # Example: SubConfig1TargetPoints, SubConfig2Place1Reward1Id
    expected_col = f'SubConfig{level}{field}'
    
    # Try to find the column with case-insensitive matching
    for key, value in config_row.items():
        if normalize_column_name(key) == normalize_column_name(expected_col):
            if pd.notna(value) and str(value).strip() != '':
                return str(value).strip()
    
    return None


def get_expected_config_value(config_row: Dict, position: int, field: str) -> Optional[str]:
    """
    Get expected configuration value for a specific position and field.
    
    Args:
        config_row: Expected configuration row
        position: Position number (1-8 for missions, 1 for race SubConfig)
        field: Field name (missions: item_id, item_quantity, mission_type, target_amount)
                         (race: TargetPoints, Place1Reward1Id, Place1Reward1Count, etc.)
    
    Returns:
        Expected configuration value as string, or None if not found
    """
    # Map field names to expected column patterns
    if field in ['TargetPoints', 'Place1Reward1Id', 'Place2Reward1Id', 'Place3Reward1Id',
                  'Place1Reward2Id', 'Place2Reward2Id', 'Place3Reward2Id',
                  'Place1Reward1Count', 'Place2Reward1Count', 'Place3Reward1Count',
                  'Place1Reward2Count', 'Place2Reward2Count', 'Place3Reward2Count']:
        # Race-specific fields (always SubConfig1 for race)
        expected_col = f'SubConfig1{field}'
    else:
        # Mission-specific fields
        field_mapping = {
            'item_id': f'SubConfig{position}Reward1Id',
            'item_quantity': f'SubConfig{position}Reward1Count',
            'mission_type': f'SubConfig{position}Type',
            'target_amount': f'SubConfig{position}Amount',
        }
        expected_col = field_mapping.get(field)
        if not expected_col:
            return None
    
    # Try to find the column with case-insensitive matching
    for key, value in config_row.items():
        if normalize_column_name(key) == normalize_column_name(expected_col):
            if pd.notna(value) and str(value).strip() != '':
                return str(value).strip()
    
    return None


def validate_segment(distinct_id: str, actual_segment: str, expected_segment: Optional[str]) -> Tuple[bool, str, str]:
    """
    Validate segment assignment for a user.
    
    Args:
        distinct_id: User's distinct_id
        actual_segment: Actual segment from user spreadsheet (what they got)
        expected_segment: Expected segment from BigQuery (what they should have)
    
    Returns:
        Tuple of (is_match, difference_type, detailed_difference)
    """
    if expected_segment is None:
        return False, "segment", f"Actual (Spreadsheet): {actual_segment} | Expected (BigQuery): NOT FOUND"
    
    # Normalize for comparison
    actual_segment_norm = str(actual_segment).strip().lower()
    expected_segment_norm = str(expected_segment).strip().lower()
    
    if actual_segment_norm != expected_segment_norm:
        return False, "segment", f"Actual (Spreadsheet): {actual_segment} | Expected (BigQuery): {expected_segment}"
    
    return True, "", f"Actual (Spreadsheet): {actual_segment} | Expected (BigQuery): {expected_segment}"


def validate_time_board_tasks_config(
    distinct_id: str,
    user_row: pd.Series,
    expected_config: Dict
) -> Tuple[bool, str, str]:
    """
    Validate time-board-tasks configuration for a user.
    
    Args:
        distinct_id: User's distinct_id
        user_row: User data row with actual time-board-tasks configuration
        expected_config: Expected configuration for user's segment
    
    Returns:
        Tuple of (is_match, difference_type, detailed_difference)
    """
    differences = []
    
    # 1. Validate task_id equals Item1Id
    actual_task_id = user_row.get('task_id')
    expected_item1_id = expected_config.get('Item1Id')
    
    if str(actual_task_id) != str(expected_item1_id):
        differences.append(f"task_id: expected={expected_item1_id}, actual={actual_task_id}")
    
    # 2. Validate item_id_1, item_id_2, item_id_3 exist in Reward1Id-Reward5Id
    for item_num in range(1, 4):  # items 1, 2, 3
        actual_item_id_key = f'item_id_{item_num}'
        actual_item_id = user_row.get(actual_item_id_key)
        
        if pd.isna(actual_item_id):
            continue  # Skip if no item
        
        actual_item_id_str = str(int(actual_item_id)) if isinstance(actual_item_id, float) else str(actual_item_id)
        
        # Check if this item_id exists in any of the Reward1Id-Reward5Id columns
        found = False
        for reward_num in range(1, 6):  # Reward 1-5
            expected_reward_id_key = f'Reward{reward_num}Id'
            expected_reward_id = expected_config.get(expected_reward_id_key)
            
            if expected_reward_id and str(expected_reward_id).strip():
                expected_reward_id_str = str(int(float(expected_reward_id))) if expected_reward_id else None
                if expected_reward_id_str == actual_item_id_str:
                    found = True
                    break
        
        if not found:
            expected_rewards = [expected_config.get(f'Reward{i}Id', '') for i in range(1, 6)]
            differences.append(f"item_id_{item_num}: actual={actual_item_id_str} not found in expected rewards {expected_rewards}")
    
    # 3. Validate item_quantity_1 exists in Reward1Count-Reward5Count
    actual_quantity_1 = user_row.get('item_quantity_1')
    
    if pd.notna(actual_quantity_1):
        actual_quantity_1_str = str(int(actual_quantity_1)) if isinstance(actual_quantity_1, float) else str(actual_quantity_1)
        
        # Check if this quantity exists in any of the Reward1Count-Reward5Count columns
        found = False
        for reward_num in range(1, 6):  # Reward 1-5
            expected_reward_count_key = f'Reward{reward_num}Count'
            expected_reward_count = expected_config.get(expected_reward_count_key)
            
            if expected_reward_count and str(expected_reward_count).strip():
                expected_reward_count_str = str(int(float(expected_reward_count))) if expected_reward_count else None
                if expected_reward_count_str == actual_quantity_1_str:
                    found = True
                    break
        
        if not found:
            expected_counts = [expected_config.get(f'Reward{i}Count', '') for i in range(1, 6)]
            differences.append(f"item_quantity_1: actual={actual_quantity_1_str} not found in expected counts {expected_counts}")
    
    if differences:
        return False, "config", " | ".join(differences)
    
    return True, "", ""


def validate_race_config(
    distinct_id: str,
    user_row: pd.Series,
    expected_config: Dict
) -> Tuple[bool, str, str]:
    """
    Validate race configuration for a user.
    
    IMPORTANT: Race configuration always uses SubConfig1* columns from the spreadsheet,
    regardless of the user's current_level in the event.
    
    Args:
        distinct_id: User's distinct_id
        user_row: User data row with actual race configuration
        expected_config: Expected configuration for user's segment
    
    Returns:
        Tuple of (is_match, difference_type, detailed_difference)
    """
    differences = []
    
    # Race configuration always uses SubConfig1 (level 1) for comparison
    # The current_level in the event indicates user progression, but does not affect
    # which configuration columns we compare against
    config_level = 1
    
    # 1. Compare target_points
    actual_target = user_row.get('target_points')
    expected_target = get_expected_race_config_value(expected_config, config_level, 'TargetPoints')
    
    if str(actual_target) != str(expected_target):
        differences.append(f"target_points: expected={expected_target}, actual={actual_target}")
    
    # 2-14. Compare place rewards (3 places, 2 items each, with id and count)
    for place in range(1, 4):  # Places 1, 2, 3
        for item_num in range(1, 3):  # Items 1, 2
            # Compare item IDs
            actual_id_key = f'place_{place}_item_id_{item_num}'
            actual_id = user_row.get(actual_id_key)
            
            expected_id_key = f'Place{place}Reward{item_num}Id'
            expected_id = get_expected_race_config_value(expected_config, config_level, expected_id_key)
            
            if pd.notna(actual_id) or pd.notna(expected_id):
                # Skip comparison if expected is 0 or empty and actual is NaN (both mean no reward)
                if expected_id in ['0', '0.0', '', None] and pd.isna(actual_id):
                    continue
                if str(actual_id) != str(expected_id):
                    differences.append(f"Place{place} item_{item_num}_id: expected={expected_id}, actual={actual_id}")
            
            # Compare item quantities/counts
            actual_count_key = f'place_{place}_item_quantity_{item_num}'
            actual_count = user_row.get(actual_count_key)
            
            expected_count_key = f'Place{place}Reward{item_num}Count'
            expected_count = get_expected_race_config_value(expected_config, config_level, expected_count_key)
            
            if pd.notna(actual_count) or pd.notna(expected_count):
                # Skip comparison if expected is 0 or empty and actual is NaN (both mean no reward)
                if expected_count in ['0', '0.0', '', None] and pd.isna(actual_count):
                    continue
                if str(actual_count) != str(expected_count):
                    differences.append(f"Place{place} item_{item_num}_count: expected={expected_count}, actual={actual_count}")
    
    if differences:
        return False, "config", " | ".join(differences)
    
    return True, "", ""


def validate_config(
    distinct_id: str,
    user_row: pd.Series,
    expected_config: Dict,
    feature: str = 'missions'
) -> Tuple[bool, str, str]:
    """
    Validate configuration for a user (feature-specific).
    
    Args:
        distinct_id: User's distinct_id
        user_row: User data row with actual configuration
        expected_config: Expected configuration for user's segment
        feature: Feature being validated ('missions' or 'race')
    
    Returns:
        Tuple of (is_match, difference_type, detailed_difference)
    """
    # Route to feature-specific validation
    if feature == 'race':
        return validate_race_config(distinct_id, user_row, expected_config)
    elif feature == 'time-board-tasks':
        return validate_time_board_tasks_config(distinct_id, user_row, expected_config)
    
    # Default: missions validation
    differences = []
    
    for position in range(1, NUM_POSITIONS + 1):
        position_diffs = []
        
        for field in FIELDS_PER_POSITION:
            actual_value = get_user_config_value(user_row, position, field)
            expected_value = get_expected_config_value(expected_config, position, field)
            
            # Normalize for comparison
            actual_norm = str(actual_value).strip().lower() if actual_value else ""
            expected_norm = str(expected_value).strip().lower() if expected_value else ""
            
            # Skip if both are empty
            if not actual_norm and not expected_norm:
                continue
            
            if actual_norm != expected_norm:
                position_diffs.append(
                    f"{field}: expected={expected_value or 'NULL'}, actual={actual_value or 'NULL'}"
                )
        
        if position_diffs:
            differences.append(f"Position {position}: {'; '.join(position_diffs)}")
    
    if differences:
        return False, "config", " | ".join(differences)
    
    return True, "", ""


def write_results_to_sheet(results: List[Dict]):
    """
    Write validation results to a new tab in the output spreadsheet.
    
    Args:
        results: List of validation result dictionaries
    """
    print(f"📝 Writing {len(results)} results to output spreadsheet...")
    
    try:
        # Get sheets service with write permissions
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        import google.auth
        
        # Try to get credentials with spreadsheets (not readonly) scope
        try:
            credentials, project = google.auth.default(
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            from google.auth.transport.requests import Request
            credentials.refresh(Request())
            service = build('sheets', 'v4', credentials=credentials)
        except Exception:
            # Fallback to get_sheets_service
            service = get_sheets_service()
        
        # Create new tab with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        tab_name = f"validation_{timestamp}"
        
        # Add new sheet
        request_body = {
            'requests': [{
                'addSheet': {
                    'properties': {
                        'title': tab_name
                    }
                }
            }]
        }
        
        service.spreadsheets().batchUpdate(
            spreadsheetId=OUTPUT_SPREADSHEET_ID,
            body=request_body
        ).execute()
        
        print(f"✅ Created new tab: {tab_name}")
        
        # Prepare data for writing
        headers = ["distinct_id", "feature", "live_ops_id", "config_link", "is_difference", "difference_type", "detailed_difference"]
        rows = [headers]
        
        for result in results:
            rows.append([
                result.get("distinct_id", ""),
                result.get("feature", ""),
                result.get("live_ops_id", ""),
                result.get("config_link", ""),
                result.get("is_difference", ""),
                result.get("difference_type", ""),
                result.get("detailed_difference", "")
            ])
        
        # Write data
        range_name = f"{tab_name}!A1"
        body = {
            'values': rows
        }
        
        service.spreadsheets().values().update(
            spreadsheetId=OUTPUT_SPREADSHEET_ID,
            range=range_name,
            valueInputOption='RAW',
            body=body
        ).execute()
        
        print(f"✅ Wrote {len(results)} results to {tab_name}")
        print(f"   View at: https://docs.google.com/spreadsheets/d/{OUTPUT_SPREADSHEET_ID}")
        
    except Exception as e:
        print(f"❌ Error writing to spreadsheet: {e}")
        
        # Fallback: write to CSV
        csv_filename = f"validation_results_{timestamp}.csv"
        df = pd.DataFrame(results)
        df.to_csv(csv_filename, index=False)
        print(f"💾 Saved results to {csv_filename} as backup")
        raise


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Validate mission configurations by comparing actual vs expected data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate for specific date range (default config spreadsheet)
  python mission_config_validator.py --live-ops-id 4253 --start-date 2026-01-26 --end-date 2026-01-26 --feature missions
  
  # Validate for last 7 days
  python mission_config_validator.py --live-ops-id 4253 --days-back 7 --feature missions
  
  # Validate for today only
  python mission_config_validator.py --live-ops-id 4253 --feature missions
  
  # Use custom config spreadsheet
  python mission_config_validator.py --live-ops-id 4253 --feature missions --config-spreadsheet-id 1ABC...
        """
    )
    
    parser.add_argument(
        '--live-ops-id',
        type=int,
        required=True,
        help='Live ops ID to filter events (e.g., 4253)'
    )
    
    parser.add_argument(
        '--start-date',
        type=str,
        help='Start date in YYYY-MM-DD format (default: today)'
    )
    
    parser.add_argument(
        '--end-date',
        type=str,
        help='End date in YYYY-MM-DD format (default: today)'
    )
    
    parser.add_argument(
        '--days-back',
        type=int,
        help='Number of days back from today to include (alternative to start-date/end-date)'
    )
    
    parser.add_argument(
        '--feature',
        type=str,
        required=True,
        help='Feature(s) to validate: missions, race, time-board-tasks, or comma-separated list (e.g., missions,race)'
    )
    
    parser.add_argument(
        '--config-spreadsheet-id',
        type=str,
        help='Google Spreadsheet ID containing expected configurations (defaults based on feature)'
    )
    
    parser.add_argument(
        '--version-filter',
        type=str,
        default='>=0.378',
        help='Version filter (e.g., ">=0.378" or "<0.378"). Default: >=0.378'
    )
    
    parser.add_argument(
        '--segment-tab',
        type=str,
        help='Tab name in config spreadsheet containing segment assignments (overrides default)'
    )
    
    parser.add_argument(
        '--skip-config-validation',
        action='store_true',
        help='Skip configuration validation, only validate segments'
    )
    
    args = parser.parse_args()
    
    # Calculate dates
    today = datetime.now().date()
    
    if args.days_back:
        args.start_date = (today - timedelta(days=args.days_back)).strftime('%Y-%m-%d')
        args.end_date = today.strftime('%Y-%m-%d')
    else:
        if not args.start_date:
            args.start_date = today.strftime('%Y-%m-%d')
        if not args.end_date:
            args.end_date = today.strftime('%Y-%m-%d')
    
    return args


def validate_feature(args, feature: str) -> List[Dict]:
    """
    Validate a single feature.
    
    Args:
        args: Parsed command line arguments
        feature: Feature name to validate ('missions' or 'race')
    
    Returns:
        List of validation result dictionaries
    """
    print("=" * 80)
    print(f"Validating Feature: {feature.upper()}")
    print("=" * 80)
    print()
    
    # Set default config spreadsheet if not provided
    config_spreadsheet_id = args.config_spreadsheet_id
    if not config_spreadsheet_id:
        if feature == 'missions':
            config_spreadsheet_id = '1L94yMz3iahaJdTCAE5v5NAPFfnLJ9DHVjlTWf11CIKM'
        elif feature == 'race':
            config_spreadsheet_id = '1M5LUieqAxtwAcOhexxBgMkwV0lh85YQgGVhatUyQjIY'
        elif feature == 'time-board-tasks':
            config_spreadsheet_id = '1b68uDDLuGGawiWWIARA5AvB1TU5Yrv1drIVDezznmmg'
    
    # Step 1: Fetch ACTUAL user data from BigQuery (what they got)
    user_df = fetch_user_data(args.live_ops_id, args.start_date, args.end_date, feature, args.version_filter)
        
    # Columns are now: distinct_id, config_segment (ACTUAL), and mission/race fields (ACTUAL)
    distinct_id_col = 'distinct_id'
    config_segment_col = 'config_segment'  # What segment they ACTUALLY got
    
    print(f"   Using columns: distinct_id='{distinct_id_col}', config_segment='{config_segment_col}' (ACTUAL)")
    print()
    
    # Step 2: Fetch EXPECTED configurations per segment (skip if only validating segments)
    if not args.skip_config_validation:
        expected_configs = fetch_expected_configs(config_spreadsheet_id, feature)
        print()
    else:
        expected_configs = {}
        print("⏭️  Skipping configuration validation (segments only)")
        print()
    
    # Step 3: Query for EXPECTED segments
    distinct_ids = user_df[distinct_id_col].dropna().astype(str).tolist()
    bq_segments = query_bq_segments(distinct_ids, feature, config_spreadsheet_id, args.segment_tab)  # What segment they SHOULD have
    print()
    
    # Step 4: Validate each user
    print(f"🔍 Validating {len(user_df)} users...")
    results = []
    
    # Prepare config link and live ops ID for results
    config_link = f"https://docs.google.com/spreadsheets/d/{config_spreadsheet_id}"
    live_ops_id = args.live_ops_id
    
    for idx, row in user_df.iterrows():
        distinct_id = str(row[distinct_id_col]) if pd.notna(row[distinct_id_col]) else None
        
        if not distinct_id or distinct_id.strip() == '':
            continue
        
        actual_segment = str(row[config_segment_col]) if pd.notna(row[config_segment_col]) else None
        expected_segment = bq_segments.get(distinct_id)
        
        # Validate segment (actual from event vs expected from configuration/BigQuery)
        segment_match, diff_type, segment_details = validate_segment(distinct_id, actual_segment, expected_segment)
        
        if not segment_match:
            results.append({
                "distinct_id": distinct_id,
                "feature": feature,
                "live_ops_id": live_ops_id,
                "config_link": config_link,
                "is_difference": "yes",
                "difference_type": diff_type,
                "detailed_difference": segment_details
            })
            continue
        
        # If skipping config validation, segment match is enough
        if args.skip_config_validation:
            results.append({
                "distinct_id": distinct_id,
                "feature": feature,
                "live_ops_id": live_ops_id,
                "config_link": config_link,
                "is_difference": "no",
                "difference_type": "",
                "detailed_difference": segment_details
            })
            continue
        
        # Segment matches, now look up the expected configuration
        segment_details_str = segment_details
        
        # For time-board-tasks, match configuration by goal_item_id_1 (not by segment)
        if feature == 'time-board-tasks':
            goal_item_id_raw = row.get('goal_item_id_1')
            # Convert float to int to string (e.g., 514.0 → 514 → "514")
            if pd.notna(goal_item_id_raw):
                goal_item_id = str(int(float(goal_item_id_raw)))
            else:
                goal_item_id = None
            expected_config = expected_configs.get(goal_item_id)
            config_lookup_key = f"goal_item_id_1={goal_item_id}"
        else:
            # For missions and race, match by segment
            segment_for_config_lookup = expected_segment
            expected_config = expected_configs.get(str(segment_for_config_lookup))
            config_lookup_key = f"segment={segment_for_config_lookup}"
        
        if not expected_config:
            results.append({
                "distinct_id": distinct_id,
                "feature": feature,
                "live_ops_id": live_ops_id,
                "config_link": config_link,
                "is_difference": "yes",
                "difference_type": "config",
                "detailed_difference": f"{segment_details_str} | Config: No expected configuration found for {config_lookup_key}"
            })
            continue
        
        config_match, diff_type, diff_details = validate_config(distinct_id, row, expected_config, feature)
        
        if not config_match:
            results.append({
                "distinct_id": distinct_id,
                "feature": feature,
                "live_ops_id": live_ops_id,
                "config_link": config_link,
                "is_difference": "yes",
                "difference_type": diff_type,
                "detailed_difference": f"{segment_details_str} | Config: {diff_details}"
            })
        else:
            results.append({
                "distinct_id": distinct_id,
                "feature": feature,
                "live_ops_id": live_ops_id,
                "config_link": config_link,
                "is_difference": "no",
                "difference_type": "",
                "detailed_difference": segment_details_str
            })
    
    print(f"✅ Feature validation complete!")
    print(f"   Total users: {len(results)}")
    print(f"   Differences found: {sum(1 for r in results if r['is_difference'] == 'yes')}")
    print(f"   Perfect matches (actual = expected): {sum(1 for r in results if r['is_difference'] == 'no')}")
    print()
    
    return results


def main():
    """Main validation workflow."""
    # Parse command line arguments
    args = parse_arguments()
    
    # Parse features (support comma-separated list)
    feature_list = [f.strip() for f in args.feature.split(',')]
    
    # Validate feature names
    valid_features = ['missions', 'race', 'time-board-tasks']
    for feature in feature_list:
        if feature not in valid_features:
            print(f"❌ Error: Invalid feature '{feature}'. Valid features: {', '.join(valid_features)}")
            sys.exit(1)
    
    print("=" * 80)
    print(f"Mission Configuration Validator")
    print(f"Features to validate: {', '.join(feature_list)}")
    print("=" * 80)
    print()
    
    all_results = []
    failed_features = []
    
    # Validate each feature
    for feature in feature_list:
        try:
            results = validate_feature(args, feature)
            all_results.extend(results)
        except Exception as e:
            print()
            print(f"⚠️  Feature '{feature}' validation failed: {e}")
            print()
            failed_features.append(feature)
            # Continue with next feature
            continue
    
    # Write combined results
    if all_results:
        try:
            write_results_to_sheet(all_results)
            print()
        except Exception as e:
            print(f"❌ Error writing results: {e}")
    
    print("=" * 80)
    if failed_features:
        print(f"⚠️  Validation complete with warnings.")
        print(f"   Failed features: {', '.join(failed_features)}")
        print(f"   Successful features: {len(feature_list) - len(failed_features)}/{len(feature_list)}")
    else:
        print("✅ All validations complete! Check the output spreadsheet for results.")
    print("=" * 80)


if __name__ == "__main__":
    main()
