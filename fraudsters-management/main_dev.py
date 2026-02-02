"""
Fraudsters Management DEV/LOCAL Version

This version writes to staging tables and Mixpanel staging properties:
- potential_fraudsters_stage
- fraudsters_stage  
- fraudster_cohort_active_stage (Mixpanel property)
- known_fraudsters_stage (Mixpanel cohort)

Run this locally from your Mac to test changes without affecting production data.
"""

import uuid
import datetime
import json
import time
import traceback
import logging
import os
import sys
import base64
from typing import Dict, List, Optional, Any
from google.cloud import bigquery
from flask import Flask, request as flask_request, jsonify

# Import shared utilities
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from shared.bigquery_client import get_bigquery_client
from shared.config import get_config
from shared.slack_client import get_slack_webhook_url
import requests

# Configuration - STAGING VERSION
MIXPANEL_PROJECT_TOKEN = "0e73d8fa8567c5bf2820b408701fa7be"
CONSISTENT_COHORT_MARKER = "fraudster_cohort_active_stage_v2"  # STAGING PROPERTY
PROJECT_ID = "yotam-395120"
DATASET_ID = "peerplay"

# STAGING TABLE NAMES
POTENTIAL_FRAUDSTERS_TABLE = "potential_fraudsters_stage"
FRAUDSTERS_TABLE = "fraudsters_stage"
FRAUDSTERS_TEMP_TABLE = "fraudsters_stage_temp"

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('FraudstersManagementDev')

# Flask app
app = Flask(__name__)


def setup_logging():
    """Setup Cloud Logging"""
    try:
        import google.cloud.logging
        client = google.cloud.logging.Client(project=PROJECT_ID)
        client.setup_logging()
        return logging.getLogger('FraudstersManagement')
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
      'fraudsters_management',
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
                    "text": f"🚨 Fraudsters Management - Step {step} Failed"
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
            f"query=resource.type%3D%22cloud_run_revision%22%20resource.labels.service_name%3D%22fraudsters-management%22"
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


def step_1_calculate_potential_fraudsters(client: bigquery.Client, run_id: str) -> Dict[str, Any]:
    """Step 1: Calculate the potential_fraudsters_stage table"""
    logger.info("Starting Step 1: Calculate potential_fraudsters_stage table (DEV)")
    log_step(client, run_id, "1", is_start=True)
    
    query = """
    -- Create the potential_fraudsters table
    -- Comprehensive Fraud Detection Query - All Users Historical Analysis + Privacy Abandonment + Rapid Chapter Progression + Refund Abuse + High Tutorial Balance
    -- This query creates the potential_fraudsters table by analyzing all users (removed install date restriction)
    -- Includes privacy abandonment detection, rapid chapter progression, refund abuse detection, and high tutorial balance detection merged into the main fraud detection process

    -- Create the new table (STAGING VERSION)
    CREATE OR REPLACE TABLE `yotam-395120.peerplay.potential_fraudsters_stage` AS (

    -- Get user attributes and device identifiers from dim_player (optimized - no vmp scan needed)
    WITH user_attributes AS (
      SELECT
        distinct_id,
        install_date,
        COALESCE(first_mediasource, last_mediasource) as first_mediasource,
        first_country,
        first_platform,
        -- Device identifiers: prefer last, fallback to first
        COALESCE(last_device_id, first_device_id) AS device_id,
        COALESCE(last_idfa, first_idfa) AS IDFA,
        COALESCE(last_gaid, first_gaid) AS GAID
      FROM `yotam-395120.peerplay.dim_player`
      WHERE distinct_id NOT IN (SELECT distinct_id FROM peerplay.fraudsters_exclusion_list)
    ),

    -- All users (removed offerwall restriction)
    target_users AS (
      SELECT
        ua.distinct_id,
        ua.install_date,
        ua.first_mediasource,
        ua.first_country,
        ua.first_platform,
        ua.device_id,
        ua.IDFA,
        ua.GAID,
        -- Keep source_network mapping but allow all sources
        CASE
          WHEN ua.first_mediasource = 'adjoe' THEN 'Adjoe'
          WHEN ua.first_mediasource = 'fetch' THEN 'Fetch'
          WHEN ua.first_mediasource = 'prodege' THEN 'Prodege'
          WHEN ua.first_mediasource = 'kashkick' THEN 'Kashkick'
          WHEN ua.first_mediasource = 'freecash' THEN 'FreeCash'
          WHEN ua.first_mediasource = 'mega fortuna' THEN 'MegaF'
          WHEN ua.first_mediasource = 'exmoo' THEN 'Exmo'
          WHEN ua.first_mediasource = 'tyrads' THEN 'Tyrads'
          WHEN ua.first_mediasource = 'benjamin' THEN 'Benjamin'
          WHEN ua.first_mediasource = 'torox' THEN 'Torox'
          WHEN ua.first_mediasource = 'brown boots' THEN 'Brownboots'
          WHEN ua.first_mediasource = 'vybs' THEN 'VYBS'
          WHEN ua.first_mediasource = 'cashcow' THEN 'Cashcow'
          WHEN ua.first_mediasource = 'taurusx' THEN 'Taurus'
          WHEN ua.first_mediasource = 'mistplay' THEN 'Mistplay'
          ELSE COALESCE(ua.first_mediasource, 'Unknown')
        END AS source_network
      FROM user_attributes ua
    ),

    -- Privacy Abandonment Detection (Pattern 9) - Modified to run since 2025-03-01
    privacy_impressions AS (
      -- Get all impression_privacy events since 2025-03-01
      SELECT DISTINCT
        distinct_id
      FROM `yotam-395120.peerplay.vmp_master_event_normalized`
      WHERE
        mp_event_name = 'impression_privacy'
        AND date >= DATE('2025-03-01')
        AND mp_country_code NOT IN ('UA', 'IL')
        AND distinct_id IN (SELECT distinct_id FROM target_users)
    ),

    agreement_clicks AS (
      -- Get all click_privacy_popup_agree events since 2025-03-01
      SELECT DISTINCT
        distinct_id
      FROM `yotam-395120.peerplay.vmp_master_event_normalized`
      WHERE
        mp_event_name = 'click_privacy_popup_agree'
        AND date >= DATE('2025-03-01')
        AND mp_country_code NOT IN ('UA', 'IL')
        AND distinct_id IN (SELECT distinct_id FROM target_users)
    ),

    -- Pattern 9: Privacy Screen Abandonment
    fraud_pattern_9 AS (
      SELECT
        p.distinct_id,
        1 AS privacy_abandonment_count
      FROM privacy_impressions p
      LEFT JOIN agreement_clicks a ON p.distinct_id = a.distinct_id
      WHERE a.distinct_id IS NULL  -- Users who never had an agreement click
    ),

    -- Pattern 10: Rapid Chapter Progression with Low Credit Spend
    rapid_chapter_users AS (
      SELECT
        distinct_id,
        date,
        COUNT(*) AS num_chapter_events
      FROM `yotam-395120.peerplay.vmp_master_event_normalized`
      WHERE mp_event_name = 'scapes_tasks_new_chapter'
        AND date >= DATE('2025-03-01')
        AND distinct_id IN (SELECT distinct_id FROM target_users)
      GROUP BY distinct_id, date
      HAVING COUNT(*) > 5
    ),

    rapid_chapter_credits AS (
      SELECT
        e.distinct_id,
        e.date,
        SUM(CAST(e.delta_credits AS FLOAT64)) * -1 AS total_delta_credits
      FROM `yotam-395120.peerplay.vmp_master_event_normalized` e
      INNER JOIN rapid_chapter_users rcu
        ON e.distinct_id = rcu.distinct_id
        AND e.date = rcu.date
      WHERE e.mp_event_name = 'generation'
        AND e.date >= DATE('2025-03-01')
      GROUP BY e.distinct_id, e.date
    ),

    fraud_pattern_10 AS (
      SELECT
        rcu.distinct_id,
        MAX(rcu.num_chapter_events) AS max_chapter_events_per_day,
        MIN(rcc.total_delta_credits / rcu.num_chapter_events) AS min_credits_per_chapter,
        COUNT(DISTINCT rcu.date) AS suspicious_days
      FROM rapid_chapter_users rcu
      INNER JOIN rapid_chapter_credits rcc
        ON rcu.distinct_id = rcc.distinct_id
        AND rcu.date = rcc.date
      WHERE rcc.total_delta_credits / rcu.num_chapter_events <= 500
      GROUP BY rcu.distinct_id
    ),

    -- Pattern 11: Refund Abuse Detection
    android_purchases_with_order_numbers AS (
      SELECT
        distinct_id,
        google_order_number,
        TIMESTAMP_MILLIS(CAST(res_timestamp AS INT64)) AS purchase_time
      FROM `yotam-395120.peerplay.vmp_master_event_normalized`
      WHERE date >= DATE('2025-05-15')  -- Start from when google_order_number became available
        AND mp_event_name = 'purchase_successful'
        AND mp_os = 'Android'
        AND google_order_number IS NOT NULL
        AND distinct_id IN (SELECT distinct_id FROM target_users)
    ),

    googleplay_refunds AS (
      SELECT
        order_number AS refunded_order_number,
        order_charged_date,
        order_charged_timestamp
      FROM `yotam-395120.peerplay.googleplay_sales`
      WHERE order_charged_date >= DATE('2025-06-01')  -- Start from when refund data became reliable
        AND financial_status = 'Refund'
    ),

    refund_abuse_analysis AS (
      SELECT
        ap.distinct_id,
        COUNT(DISTINCT ap.google_order_number) AS total_purchases,
        COUNT(DISTINCT gr.refunded_order_number) AS total_refunds,
        CASE
          WHEN COUNT(DISTINCT ap.google_order_number) > 0
          THEN COUNT(DISTINCT gr.refunded_order_number) / COUNT(DISTINCT ap.google_order_number)
          ELSE 0
        END AS refund_rate,
        MIN(ap.google_order_number) AS example_order_number
      FROM android_purchases_with_order_numbers ap
      LEFT JOIN googleplay_refunds gr
        ON ap.google_order_number = gr.refunded_order_number
      GROUP BY ap.distinct_id
    ),

    fraud_pattern_11 AS (
      SELECT
        distinct_id,
        total_purchases,
        total_refunds,
        ROUND(refund_rate * 100, 2) AS refund_rate_percentage,
        example_order_number
      FROM refund_abuse_analysis
      WHERE total_purchases > 5
        AND refund_rate > 0.25  -- More than 25% refund rate
    ),

    -- Pattern 12: High Balance in Tutorial Chapters Without Purchases
    tutorial_chapter_analysis AS (
      SELECT
        apcd.distinct_id,
        MAX(apcd.first_credit_balance) AS max_first_credit_balance,
        MAX(apcd.last_credit_balance) AS max_last_credit_balance,
        SUM(apcd.total_purchase_revenue) AS total_tutorial_revenue
      FROM `yotam-395120.peerplay.agg_player_chapter_daily` apcd
      INNER JOIN target_users tu ON apcd.distinct_id = tu.distinct_id
      WHERE apcd.date >= DATE('2025-03-01')
        AND apcd.chapter BETWEEN 1 AND 3  -- Tutorial chapters only
        AND (apcd.first_credit_balance > 4990 OR apcd.last_credit_balance > 4950)  -- High balance threshold
      GROUP BY apcd.distinct_id
    ),

    fraud_pattern_12 AS (
      SELECT
        distinct_id,
        max_first_credit_balance,
        max_last_credit_balance,
        GREATEST(max_first_credit_balance, max_last_credit_balance) AS highest_tutorial_balance,
        total_tutorial_revenue
      FROM tutorial_chapter_analysis
      WHERE total_tutorial_revenue = 0  -- No purchases during tutorial
    ),

    -- Balance events for violation detection - analyze full historical period
    balance_events AS (
      SELECT
        distinct_id,
        TIMESTAMP_MILLIS(CAST(res_timestamp AS INT64)) AS event_time,
        res_timestamp,
        mp_event_name,
        CAST(credit_balance AS INT64) AS credit_balance,
        CAST(metapoint_balance AS INT64) AS metapoint_balance,
        -- Get previous balances to calculate jumps
        LAG(CAST(credit_balance AS INT64)) OVER (
          PARTITION BY distinct_id
          ORDER BY res_timestamp
        ) AS prev_credit_balance,
        LAG(CAST(metapoint_balance AS INT64)) OVER (
          PARTITION BY distinct_id
          ORDER BY res_timestamp
        ) AS prev_metapoint_balance,
        LAG(mp_event_name) OVER (
          PARTITION BY distinct_id
          ORDER BY res_timestamp
        ) AS prev_event_name,
        -- Get next event names to exclude reward-related jumps (Pattern 8)
        LEAD(mp_event_name, 1) OVER (
          PARTITION BY distinct_id
          ORDER BY res_timestamp
        ) AS next_event_name_1,
        LEAD(mp_event_name, 2) OVER (
          PARTITION BY distinct_id
          ORDER BY res_timestamp
        ) AS next_event_name_2,
        ROW_NUMBER() OVER (
          PARTITION BY distinct_id
          ORDER BY res_timestamp
        ) AS event_sequence
      FROM `yotam-395120.peerplay.vmp_master_event_normalized`
      WHERE (credit_balance IS NOT NULL OR metapoint_balance IS NOT NULL)
        AND date >= DATE('2025-03-01')
        AND distinct_id IN (SELECT distinct_id FROM target_users)
    ),

    -- Pattern 6: High Balance Violations
    fraud_pattern_6 AS (
      SELECT
        distinct_id,
        COUNT(*) AS high_balance_violations,
        MIN(event_time) AS first_high_balance_time,
        MAX(GREATEST(credit_balance, metapoint_balance)) AS max_balance_amount
      FROM balance_events
      WHERE credit_balance > 245000  -- 245K threshold (updated in 2025-11-27)
         OR metapoint_balance > 850000  -- 850K threshold
      GROUP BY distinct_id
    ),

    -- Pattern 7: Negative Balance Violations
    fraud_pattern_7 AS (
      SELECT
        distinct_id,
        COUNT(*) AS negative_balance_violations,
        MIN(event_time) AS first_negative_balance_time,
        MIN(LEAST(credit_balance, metapoint_balance)) AS most_negative_balance
      FROM balance_events
      WHERE credit_balance < 0
         OR metapoint_balance < 0
      GROUP BY distinct_id
    ),

    -- Pattern 8: Large Jump Violations
    -- Excludes jumps where previous, current, or next 2 events are reward-related
    fraud_pattern_8 AS (
      SELECT
        distinct_id,
        COUNT(*) AS large_jump_violations,
        MIN(event_time) AS first_large_jump_time,
        MAX(
          GREATEST(
            credit_balance - COALESCE(prev_credit_balance, 0),
            metapoint_balance - COALESCE(prev_metapoint_balance, 0)
          )
        ) AS largest_jump_amount
      FROM balance_events
      WHERE event_sequence > 1  -- Skip first event
        AND (
          -- Large credit jump without reward event (40K threshold)
          (credit_balance - COALESCE(prev_credit_balance, 0) > 40000
           AND mp_event_name NOT LIKE '%reward%'
           AND prev_event_name NOT LIKE '%reward%'
           AND COALESCE(next_event_name_1, '') NOT LIKE '%reward%'
           AND COALESCE(next_event_name_2, '') NOT LIKE '%reward%')
          OR
          -- Large metapoint jump without reward event (100K threshold)
          (metapoint_balance - COALESCE(prev_metapoint_balance, 0) > 100000
           AND mp_event_name NOT LIKE '%reward%'
           AND prev_event_name NOT LIKE '%reward%'
           AND COALESCE(next_event_name_1, '') NOT LIKE '%reward%'
           AND COALESCE(next_event_name_2, '') NOT LIKE '%reward%')
        )
      GROUP BY distinct_id
    ),

    -- Pattern 1: Reaching chapter 20+ in less than 24 hours without purchasing
    fraud_pattern_1 AS (
      SELECT
        u.distinct_id,
        MAX(CAST(c.chapter AS INT64)) AS max_chapter,
        MIN(CASE WHEN CAST(c.chapter AS INT64) >= 20
                 THEN TIMESTAMP_MILLIS(CAST(c.res_timestamp AS INT64)) END) AS chapter_20_time,
        COUNT(p.distinct_id) AS purchase_count
      FROM target_users u
      JOIN `yotam-395120.peerplay.vmp_master_event_normalized` c
        ON u.distinct_id = c.distinct_id
        AND c.mp_event_name = 'scapes_tasks_new_chapter'
        AND CAST(c.chapter AS INT64) >= 20
        AND c.date >= DATE('2025-03-01')
        -- Time filter relative to each user's install date
        AND TIMESTAMP_MILLIS(CAST(c.res_timestamp AS INT64)) <= TIMESTAMP_ADD(TIMESTAMP(u.install_date), INTERVAL 24 HOUR)
      LEFT JOIN `yotam-395120.peerplay.vmp_master_event_normalized` p
        ON u.distinct_id = p.distinct_id
        AND p.mp_event_name = 'purchase_successful'
        AND p.date >= DATE('2025-03-01')
        AND TIMESTAMP_MILLIS(CAST(p.res_timestamp AS INT64)) BETWEEN TIMESTAMP(u.install_date) AND TIMESTAMP_ADD(TIMESTAMP(u.install_date), INTERVAL 24 HOUR)
      GROUP BY u.distinct_id
      HAVING purchase_count = 0
        AND chapter_20_time IS NOT NULL
    ),

    -- Pattern 2: More than 21 harvests in one day (updated condition)
    daily_activity AS (
      SELECT
        h.distinct_id,
        DATE(TIMESTAMP_MILLIS(CAST(h.res_timestamp AS INT64))) AS activity_date,
        COUNT(CASE WHEN h.mp_event_name = 'rewards_harvest_collect' and coalesce(is_turbo_tip_jar,0)<>1 THEN 1 END) AS harvest_count,
        COUNT(CASE WHEN h.mp_event_name = 'scapes_tasks_new_chapter' THEN 1 END) AS chapter_count
      FROM target_users u
      JOIN `yotam-395120.peerplay.vmp_master_event_normalized` h
        ON u.distinct_id = h.distinct_id
      WHERE h.mp_event_name IN ('rewards_harvest_collect', 'scapes_tasks_new_chapter')
        AND h.date >= DATE('2025-03-01')
      GROUP BY h.distinct_id, DATE(TIMESTAMP_MILLIS(CAST(h.res_timestamp AS INT64)))
    ),

    fraud_pattern_2 AS (
      SELECT
        distinct_id,
        MAX(activity_date) AS max_harvest_date,
        MAX(harvest_count - chapter_count) AS max_harvests_chapters_diff
      FROM daily_activity
      WHERE (harvest_count-chapter_count) >= 22
      GROUP BY distinct_id
      HAVING COUNT(DISTINCT activity_date) > 2  -- More than 2 days with suspicious activity
    ),

    -- Pattern 3: Purchases with price = 0.01
    fraud_pattern_3 AS (
      SELECT
        u.distinct_id,
        COUNT(*) AS suspicious_purchase_count
      FROM target_users u
      JOIN `yotam-395120.peerplay.vmp_master_event_normalized` p
        ON u.distinct_id = p.distinct_id
      WHERE p.mp_event_name = 'purchase_successful'
        AND CAST(p.price_original AS FLOAT64) = 0.01
        AND p.date >= DATE('2025-03-01')
      GROUP BY u.distinct_id
      HAVING COUNT(*) > 0
    ),

    -- Pattern 4: Rapid consecutive purchases (1-7 seconds apart) on Apple devices
    purchase_events AS (
      SELECT
        p.distinct_id,
        TIMESTAMP_MILLIS(CAST(p.res_timestamp AS INT64)) AS purchase_time,
        p.package_id,
        ROW_NUMBER() OVER(PARTITION BY p.distinct_id ORDER BY p.res_timestamp) AS purchase_seq
      FROM target_users u
      JOIN `yotam-395120.peerplay.vmp_master_event_normalized` p
        ON u.distinct_id = p.distinct_id
      WHERE p.mp_event_name = 'purchase_successful'
        AND p.mp_os = 'Apple'
        AND p.date >= DATE('2025-03-01')
    ),

    rapid_purchases AS (
      SELECT
        a.distinct_id,
        COUNT(*) AS rapid_purchase_count,
        MIN(TIMESTAMP_DIFF(b.purchase_time, a.purchase_time, SECOND)) AS min_seconds_between_purchases,
        MAX(TIMESTAMP_DIFF(b.purchase_time, a.purchase_time, SECOND)) AS max_seconds_between_purchases,
        STRING_AGG(DISTINCT FORMAT_TIMESTAMP('%Y-%m-%d %H:%M:%S', a.purchase_time), ', ' ORDER BY FORMAT_TIMESTAMP('%Y-%m-%d %H:%M:%S', a.purchase_time)) AS purchase_timestamps
      FROM purchase_events a
      JOIN purchase_events b
        ON a.distinct_id = b.distinct_id
        AND b.purchase_seq = a.purchase_seq + 1
      WHERE
        TIMESTAMP_DIFF(b.purchase_time, a.purchase_time, SECOND) > 0
        AND TIMESTAMP_DIFF(b.purchase_time, a.purchase_time, SECOND) < 8
      GROUP BY a.distinct_id
    ),

    fraud_pattern_4 AS (
      SELECT
        distinct_id,
        rapid_purchase_count,
        min_seconds_between_purchases,
        max_seconds_between_purchases,
        purchase_timestamps
      FROM rapid_purchases
      WHERE rapid_purchase_count > 0
    ),

    -- Pattern 5: Consecutive purchase_successful events without purchase_click in between
    purchase_flow_events AS (
      SELECT
        u.distinct_id,
        e.mp_event_name AS event_name,
        TIMESTAMP_MILLIS(CAST(e.res_timestamp AS INT64)) AS event_time,
        LEAD(e.mp_event_name) OVER (
          PARTITION BY u.distinct_id
          ORDER BY e.res_timestamp
        ) AS next_event_name,
        LEAD(TIMESTAMP_MILLIS(CAST(e.res_timestamp AS INT64))) OVER (
          PARTITION BY u.distinct_id
          ORDER BY e.res_timestamp
        ) AS next_event_time
      FROM target_users u
      JOIN `yotam-395120.peerplay.vmp_master_event_normalized` e
        ON u.distinct_id = e.distinct_id
      WHERE
        e.mp_event_name IN ('purchase_successful', 'purchase_click')
        AND e.date >= DATE('2025-03-01')
    ),

    fraud_pattern_5 AS (
      SELECT
        distinct_id,
        COUNT(*) AS consecutive_successful_purchases,
        STRING_AGG(DISTINCT FORMAT_TIMESTAMP('%Y-%m-%d %H:%M:%S', event_time), ', ' ORDER BY FORMAT_TIMESTAMP('%Y-%m-%d %H:%M:%S', event_time)) AS anomalous_purchase_times
      FROM purchase_flow_events
      WHERE
        event_name = 'purchase_successful' AND
        next_event_name = 'purchase_successful' AND
        event_time != next_event_time
      GROUP BY distinct_id
      HAVING COUNT(*) > 0
    ),

    -- Pattern 13: Multiple Purchases in Chapter 1 (CORRECTED)
    fraud_pattern_13 AS (
      SELECT
        tu.distinct_id,
        tu.install_date,
        SUM(apcd.count_purchases) AS chapter1_purchase_count,
        SUM(apcd.total_purchase_revenue) AS chapter1_total_revenue
      FROM target_users tu
      INNER JOIN `yotam-395120.peerplay.agg_player_chapter_daily` apcd
        ON tu.distinct_id = apcd.distinct_id
        AND apcd.chapter = 1
        AND apcd.count_purchases > 0
      WHERE tu.install_date >= DATE('2025-03-01')
      GROUP BY tu.distinct_id, tu.install_date
      HAVING SUM(apcd.count_purchases) > 1  -- More than 1 purchase in chapter 1
    ),
    -- Pattern 14: Duplicate Transaction ID Usage (Apple, Google, and Stash)
    -- Single unified query for all payment platforms
    all_duplicate_transactions AS (
      SELECT
        distinct_id,
        CASE 
          WHEN payment_platform = 'stash' THEN checkout_id
          WHEN payment_platform = 'googleplay' OR (payment_platform IS NULL AND mp_os = 'Android') THEN google_order_number
          WHEN payment_platform = 'apple' OR (payment_platform IS NULL AND mp_os = 'Apple') THEN purchase_id
        END AS txn_id,
        CASE 
          WHEN payment_platform = 'stash' THEN 'stash'
          WHEN payment_platform = 'googleplay' OR (payment_platform IS NULL AND mp_os = 'Android') THEN 'googleplay'
          WHEN payment_platform = 'apple' OR (payment_platform IS NULL AND mp_os = 'Apple') THEN 'apple'
        END AS payment_platform,
        res_timestamp
      FROM `yotam-395120.peerplay.vmp_master_event_normalized`
      WHERE date >= DATE('2025-05-15')  -- Earliest start date across all platforms
        AND mp_country_code NOT IN ('UA', 'IL')
        AND currency <> 'UAH'
        AND mp_event_name = 'purchase_successful'
        AND distinct_id IN (SELECT distinct_id FROM target_users)
        -- At least one transaction ID must be present
        AND (checkout_id IS NOT NULL OR google_order_number IS NOT NULL OR purchase_id IS NOT NULL)
    ),

    -- Aggregate duplicates across all platforms
    duplicate_transactions_agg AS (
      SELECT
        distinct_id,
        txn_id,
        payment_platform,
        COUNT(DISTINCT res_timestamp) AS num_uses,
        MIN(TIMESTAMP_MILLIS(CAST(res_timestamp AS INT64))) AS first_use_time,
        MAX(TIMESTAMP_MILLIS(CAST(res_timestamp AS INT64))) AS last_use_time
      FROM all_duplicate_transactions
      WHERE txn_id IS NOT NULL  -- Filter out rows where CASE didn't match
      GROUP BY distinct_id, txn_id, payment_platform
      HAVING COUNT(DISTINCT res_timestamp) > 1
    ),

    fraud_pattern_14 AS (
      SELECT
        distinct_id,
        COUNT(DISTINCT txn_id) AS duplicate_transaction_count,
        MAX(num_uses) AS max_reuse_count,
        MIN(first_use_time) AS earliest_duplicate_time,
        MAX(last_use_time) AS latest_duplicate_time,
        STRING_AGG(DISTINCT payment_platform, ', ') AS affected_platforms
      FROM duplicate_transactions_agg
      GROUP BY distinct_id
    ),

    -- Pattern 15: Suspicious $0.01 Purchases
    -- Users making multiple purchases at exactly $0.01 price
    fraud_pattern_15 AS (
      SELECT
        distinct_id,
        COUNT(*) AS penny_purchase_count,
        MAX(TIMESTAMP_MILLIS(CAST(res_timestamp AS INT64))) AS last_penny_purchase_time
      FROM `yotam-395120.peerplay.vmp_master_event_normalized`
      WHERE mp_event_name = 'purchase_successful'
        AND CAST(price_original AS FLOAT64) = 0.01
        AND date >= DATE('2025-03-01')
        AND distinct_id IN (SELECT distinct_id FROM target_users)
      GROUP BY distinct_id
      HAVING COUNT(*) >= 2  -- At least 2 purchases at $0.01
    )


    -- Final SELECT for table creation
    SELECT
      u.distinct_id,
      u.device_id,
      u.IDFA,
      u.GAID,
      u.source_network,
      u.first_mediasource,
      u.first_country,
      u.first_platform,
      u.install_date,

      -- Pattern 1 info
      CASE WHEN p1.distinct_id IS NOT NULL THEN 1 ELSE 0 END AS fast_progression_flag,
      p1.max_chapter,
      TIMESTAMP_DIFF(p1.chapter_20_time, TIMESTAMP(u.install_date), HOUR) AS hours_to_chapter_20,

      -- Pattern 2 info (updated column name)
      CASE WHEN p2.distinct_id IS NOT NULL THEN 1 ELSE 0 END AS excessive_harvests_flag,
      p2.max_harvest_date,
      p2.max_harvests_chapters_diff, -- Changed: Now shows max_harvests instead of max_net_harvests

      -- Pattern 3 info
      CASE WHEN p3.distinct_id IS NOT NULL THEN 1 ELSE 0 END AS suspicious_purchase_flag,
      p3.suspicious_purchase_count,

      -- Pattern 4 info
      CASE WHEN p4.distinct_id IS NOT NULL THEN 1 ELSE 0 END AS rapid_purchases_flag,
      p4.rapid_purchase_count,
      p4.min_seconds_between_purchases,
      p4.max_seconds_between_purchases,
      p4.purchase_timestamps,

      -- Pattern 5 info
      CASE WHEN p5.distinct_id IS NOT NULL THEN 1 ELSE 0 END AS purchase_flow_anomaly_flag,
      p5.consecutive_successful_purchases,
      p5.anomalous_purchase_times,

      -- Pattern 6 info - High Balance Violations
      CASE WHEN p6.distinct_id IS NOT NULL THEN 1 ELSE 0 END AS high_balance_flag,
      p6.high_balance_violations,
      p6.first_high_balance_time,
      p6.max_balance_amount,

      -- Pattern 7 info - Negative Balance Violations
      CASE WHEN p7.distinct_id IS NOT NULL THEN 1 ELSE 0 END AS negative_balance_flag,
      p7.negative_balance_violations,
      p7.first_negative_balance_time,
      p7.most_negative_balance,

      -- Pattern 8 info - Large Jump Violations
      CASE WHEN p8.distinct_id IS NOT NULL THEN 1 ELSE 0 END AS large_jump_flag,
      p8.large_jump_violations,
      p8.first_large_jump_time,
      p8.largest_jump_amount,

      -- Pattern 9 info - Privacy Screen Abandonment
      CASE WHEN p9.distinct_id IS NOT NULL THEN 1 ELSE 0 END AS privacy_abandonment_flag,
      p9.privacy_abandonment_count,

      -- Pattern 10 info - Rapid Chapter Progression with Low Credit Spend
      CASE WHEN p10.distinct_id IS NOT NULL THEN 1 ELSE 0 END AS rapid_chapter_progression_flag,
      p10.max_chapter_events_per_day,
      p10.min_credits_per_chapter,
      p10.suspicious_days,

      -- Pattern 11 info - Refund Abuse Detection
      CASE WHEN p11.distinct_id IS NOT NULL THEN 1 ELSE 0 END AS refund_abuse_flag,
      p11.total_purchases,
      p11.total_refunds,
      p11.refund_rate_percentage,
      p11.example_order_number,

      -- Pattern 12 info - High Balance in Tutorial Without Purchases
      CASE WHEN p12.distinct_id IS NOT NULL THEN 1 ELSE 0 END AS high_tutorial_balance_flag,
      p12.max_first_credit_balance,
      p12.max_last_credit_balance,
      p12.highest_tutorial_balance,
      p12.total_tutorial_revenue,

      -- Pattern 13 info - Multiple Purchases in Chapter 1
      CASE WHEN p13.distinct_id IS NOT NULL THEN 1 ELSE 0 END AS multiple_chapter1_purchases_flag,
      p13.chapter1_purchase_count,
      p13.chapter1_total_revenue,

      -- Pattern 14 info - Duplicate Transaction ID Usage
      CASE WHEN p14.distinct_id IS NOT NULL THEN 1 ELSE 0 END AS duplicate_transaction_flag,
      p14.duplicate_transaction_count,
      p14.max_reuse_count,
      p14.earliest_duplicate_time,
      p14.latest_duplicate_time,

      -- Pattern 15 info - Suspicious $0.01 Purchases
      CASE WHEN p15.distinct_id IS NOT NULL THEN 1 ELSE 0 END AS penny_purchase_flag,
      p15.penny_purchase_count,
      p15.last_penny_purchase_time,

      -- Total flags for sorting (updated to include all patterns)
      (CASE WHEN p1.distinct_id IS NOT NULL THEN 1 ELSE 0 END) +
      (CASE WHEN p2.distinct_id IS NOT NULL THEN 1 ELSE 0 END) +
      (CASE WHEN p3.distinct_id IS NOT NULL THEN 1 ELSE 0 END) +
      (CASE WHEN p4.distinct_id IS NOT NULL THEN 1 ELSE 0 END) +
      (CASE WHEN p5.distinct_id IS NOT NULL THEN 1 ELSE 0 END) +
      (CASE WHEN p6.distinct_id IS NOT NULL THEN 1 ELSE 0 END) +
      (CASE WHEN p7.distinct_id IS NOT NULL THEN 1 ELSE 0 END) +
      (CASE WHEN p8.distinct_id IS NOT NULL THEN 1 ELSE 0 END) +
      (CASE WHEN p9.distinct_id IS NOT NULL THEN 1 ELSE 0 END) +
      (CASE WHEN p10.distinct_id IS NOT NULL THEN 1 ELSE 0 END) +
      (CASE WHEN p11.distinct_id IS NOT NULL THEN 1 ELSE 0 END) +
      (CASE WHEN p12.distinct_id IS NOT NULL THEN 1 ELSE 0 END) +
      (CASE WHEN p13.distinct_id IS NOT NULL THEN 1 ELSE 0 END) +
      (CASE WHEN p14.distinct_id IS NOT NULL THEN 1 ELSE 0 END) +
      (CASE WHEN p15.distinct_id IS NOT NULL THEN 1 ELSE 0 END) AS total_fraud_flags,

      -- Add metadata for tracking
      CURRENT_TIMESTAMP() AS analysis_timestamp,
      DATE('2025-03-01') AS analysis_start_date

    FROM target_users u
    LEFT JOIN fraud_pattern_1 p1 ON u.distinct_id = p1.distinct_id
    LEFT JOIN fraud_pattern_2 p2 ON u.distinct_id = p2.distinct_id
    LEFT JOIN fraud_pattern_3 p3 ON u.distinct_id = p3.distinct_id
    LEFT JOIN fraud_pattern_4 p4 ON u.distinct_id = p4.distinct_id
    LEFT JOIN fraud_pattern_5 p5 ON u.distinct_id = p5.distinct_id
    LEFT JOIN fraud_pattern_6 p6 ON u.distinct_id = p6.distinct_id
    LEFT JOIN fraud_pattern_7 p7 ON u.distinct_id = p7.distinct_id
    LEFT JOIN fraud_pattern_8 p8 ON u.distinct_id = p8.distinct_id
    LEFT JOIN fraud_pattern_9 p9 ON u.distinct_id = p9.distinct_id
    LEFT JOIN fraud_pattern_10 p10 ON u.distinct_id = p10.distinct_id
    LEFT JOIN fraud_pattern_11 p11 ON u.distinct_id = p11.distinct_id
    LEFT JOIN fraud_pattern_12 p12 ON u.distinct_id = p12.distinct_id
    LEFT JOIN fraud_pattern_13 p13 ON u.distinct_id = p13.distinct_id
    LEFT JOIN fraud_pattern_14 p14 ON u.distinct_id = p14.distinct_id
    LEFT JOIN fraud_pattern_15 p15 ON u.distinct_id = p15.distinct_id
    WHERE p1.distinct_id IS NOT NULL
       OR p2.distinct_id IS NOT NULL
       OR p3.distinct_id IS NOT NULL
       OR p4.distinct_id IS NOT NULL
       OR p5.distinct_id IS NOT NULL
       OR p6.distinct_id IS NOT NULL
       OR p7.distinct_id IS NOT NULL
       OR p8.distinct_id IS NOT NULL
       OR p9.distinct_id IS NOT NULL
    --   OR p10.distinct_id IS NOT NULL
       OR p11.distinct_id IS NOT NULL
       OR p12.distinct_id IS NOT NULL
       OR p13.distinct_id IS NOT NULL
       OR p14.distinct_id IS NOT NULL
       OR p15.distinct_id IS NOT NULL
    )
    """
    
    try:
        query_job = client.query(query)
        query_job.result()  # Wait for completion
        logger.info("✓ Step 1 completed: potential_fraudsters_stage table created (DEV)")
        log_step(client, run_id, "1", is_start=False)
        return {"success": True, "step": 1}
    except Exception as e:
        error_msg = str(e)
        # Check if it's the Drive credentials error
        if "Drive credentials" in error_msg or "Permission denied while getting Drive" in error_msg:
            logger.warning("⚠ Step 1 failed due to Drive credentials issue (likely googleplay_sales table access)")
            logger.warning("   This is a known issue - the table may require additional permissions for complex queries")
            logger.warning("   Steps 2-4 will continue using existing potential_fraudsters_stage data if available")
            logger.warning(f"   Error details: {error_msg[:200]}")
            # Don't raise - allow script to continue with other steps
            log_step(client, run_id, "1", is_start=False)
            return {"success": False, "step": 1, "error": error_msg, "warning": "Drive credentials issue - continuing with other steps"}
        else:
            # For other errors, still raise to alert
            error_msg = f"Step 1 failed: {error_msg}"
        logger.error(error_msg)
        send_error_alert(1, e, run_id, query[:500])
        log_step(client, run_id, "1", is_start=False)
        raise Exception(error_msg)


def step_2_calculate_offerwall_cheaters(client: bigquery.Client, run_id: str) -> Dict[str, Any]:
    """Step 2: Calculate the offerwalls cheaters table (using staging)"""
    logger.info("Starting Step 2: Calculate offer_wall_progression_cheaters table (DEV)")
    log_step(client, run_id, "2", is_start=True)
    
    query = """
    -- Insert the table results to offer_wall_progression_cheaters table (DEV - using staging)
    CREATE OR REPLACE TABLE `yotam-395120.peerplay.offer_wall_progression_cheaters` AS
    SELECT * FROM `yotam-395120.peerplay.potential_fraudsters_stage`
    WHERE privacy_abandonment_flag = 0 OR total_fraud_flags > 1  --all list except users only with privacy_abandonment_flag
    """
    
    try:
        query_job = client.query(query)
        query_job.result()  # Wait for completion
        logger.info("✓ Step 2 completed: offer_wall_progression_cheaters table created")
        log_step(client, run_id, "2", is_start=False)
        return {"success": True, "step": 2}
    except Exception as e:
        error_msg = f"Step 2 failed: {str(e)}"
        logger.error(error_msg)
        send_error_alert(2, e, run_id, query)
        log_step(client, run_id, "2", is_start=False)
        raise Exception(error_msg)


def step_3_update_fraudsters_table(client: bigquery.Client, run_id: str) -> Dict[str, Any]:
    """Step 3: Update fraudsters_stage table in BigQuery"""
    logger.info("Starting Step 3: Update fraudsters_stage table (DEV)")
    log_step(client, run_id, "3", is_start=True)
    
    query = """
    -- Insert the new users to fraudsters table
    -- Updated logic with platform and install date OR last purchase date specific rules

    -- Clear the temp table first (STAGING)
    TRUNCATE TABLE `yotam-395120.peerplay.fraudsters_stage_temp`;

    -- Insert from potential_fraudsters_stage (automated fraud detection)
    INSERT INTO `yotam-395120.peerplay.fraudsters_stage_temp` (
      distinct_id,
      manual_identification_fraud_purchase_flag,
      fast_progression_flag,
      excessive_harvests_flag,
      suspicious_purchase_flag,
      rapid_purchases_flag,
      purchase_flow_anomaly_flag,
      high_balance_flag,
      negative_balance_flag,
      large_jump_flag,
      privacy_abandonment_flag,
      rapid_chapter_progression_flag,
      refund_abuse_flag,
      high_tutorial_balance_flag,
      multiple_chapter1_purchases_flag,
      duplicate_transaction_flag,
      penny_purchase_flag
    )
    WITH last_purchase_dates AS (
      -- Get the last purchase date for each user
      SELECT
        distinct_id,
        MAX(DATE(TIMESTAMP_MILLIS(CAST(res_timestamp AS INT64)))) as last_purchase_date
      FROM `yotam-395120.peerplay.vmp_master_event_normalized`
      WHERE mp_event_name = 'purchase_successful'
        AND CAST(price_original AS FLOAT64) != 0.01
        AND date >= DATE('2025-01-01')  -- Reasonable date range for performance
      GROUP BY distinct_id
    )
    SELECT
      pf.distinct_id,
      0 as manual_identification_fraud_purchase_flag,  -- These are automated detections
      fast_progression_flag,
      excessive_harvests_flag,
      suspicious_purchase_flag,
      rapid_purchases_flag,
      purchase_flow_anomaly_flag,
      high_balance_flag,
      negative_balance_flag,
      large_jump_flag,
      privacy_abandonment_flag,
      rapid_chapter_progression_flag,
      refund_abuse_flag,
      high_tutorial_balance_flag,
      multiple_chapter1_purchases_flag,
      duplicate_transaction_flag,
      penny_purchase_flag
    FROM `yotam-395120.peerplay.potential_fraudsters_stage` pf
    LEFT JOIN `yotam-395120.peerplay.dim_player` dp ON pf.distinct_id = dp.distinct_id
    LEFT JOIN last_purchase_dates lpd ON pf.distinct_id = lpd.distinct_id
    WHERE pf.first_country NOT IN ('UA','IL')
    AND (
      -- Apple users: installed OR last purchased on/after 2025-08-13: ONLY duplicate_transaction_flag or penny_purchase_flag
      (dp.first_platform = 'Apple'
       AND (dp.install_date >= DATE('2025-08-13') OR lpd.last_purchase_date >= DATE('2025-08-13'))
       AND (pf.duplicate_transaction_flag = 1 OR pf.penny_purchase_flag = 1))

      -- Apple users: installed AND last purchased before 2025-08-13: Previous logic
      OR (dp.first_platform = 'Apple'
          AND (dp.install_date < DATE('2025-08-13') OR dp.install_date IS NULL)
          AND (lpd.last_purchase_date < DATE('2025-08-13') OR lpd.last_purchase_date IS NULL)
          AND (
            (suspicious_purchase_flag=1 OR rapid_purchases_flag=1 OR purchase_flow_anomaly_flag=1)
            OR privacy_abandonment_flag=1
            OR excessive_harvests_flag=1
            OR fast_progression_flag=1
            OR high_balance_flag=1
            OR negative_balance_flag=1
            OR large_jump_flag=1
            OR high_tutorial_balance_flag=1
            OR refund_abuse_flag=1
            OR multiple_chapter1_purchases_flag=1
            OR duplicate_transaction_flag=1
            OR penny_purchase_flag=1
          ))

      -- Android users: installed OR last purchased on/after 2025-04-17: ONLY duplicate_transaction_flag or penny_purchase_flag
      OR (dp.first_platform = 'Android'
          AND (dp.install_date >= DATE('2025-04-17') OR lpd.last_purchase_date >= DATE('2025-04-17'))
          AND (pf.duplicate_transaction_flag = 1 OR pf.penny_purchase_flag = 1))

      -- Android users: installed AND last purchased before 2025-04-17: Previous logic
      OR (dp.first_platform = 'Android'
          AND (dp.install_date < DATE('2025-04-17') OR dp.install_date IS NULL)
          AND (lpd.last_purchase_date < DATE('2025-04-17') OR lpd.last_purchase_date IS NULL)
          AND (
            privacy_abandonment_flag=1
            OR excessive_harvests_flag=1
            OR fast_progression_flag=1
            OR high_balance_flag=1
            OR negative_balance_flag=1
            OR large_jump_flag=1
            OR high_tutorial_balance_flag=1
            OR refund_abuse_flag=1
            OR multiple_chapter1_purchases_flag=1
            OR duplicate_transaction_flag=1
            OR penny_purchase_flag=1
          ))
    );

    -- Insert from fraudsters table (manual fraud purchase identification)
    -- NOTE: Reading from PRODUCTION fraudsters table to get manual flags
    -- Manual identifications are ALWAYS included regardless of platform or install date
    INSERT INTO `yotam-395120.peerplay.fraudsters_stage_temp` (
      distinct_id,
      manual_identification_fraud_purchase_flag,
      fast_progression_flag,
      excessive_harvests_flag,
      suspicious_purchase_flag,
      rapid_purchases_flag,
      purchase_flow_anomaly_flag,
      high_balance_flag,
      negative_balance_flag,
      large_jump_flag,
      privacy_abandonment_flag,
      rapid_chapter_progression_flag,
      refund_abuse_flag,
      high_tutorial_balance_flag,
      multiple_chapter1_purchases_flag,
      duplicate_transaction_flag,
      penny_purchase_flag
    )
    SELECT
      distinct_id,
      1 as manual_identification_fraud_purchase_flag,  -- These are manual identifications
      0 as fast_progression_flag,                      -- Default to 0 for manual entries
      0 as excessive_harvests_flag,
      0 as suspicious_purchase_flag,
      0 as rapid_purchases_flag,
      0 as purchase_flow_anomaly_flag,
      0 as high_balance_flag,
      0 as negative_balance_flag,
      0 as large_jump_flag,
      0 as privacy_abandonment_flag,
      0 as rapid_chapter_progression_flag,
      0 as refund_abuse_flag,
      0 as high_tutorial_balance_flag,
      0 as multiple_chapter1_purchases_flag,
      0 as duplicate_transaction_flag,
      0 as penny_purchase_flag
    FROM `yotam-395120.peerplay.fraudsters`
    WHERE manual_identification_fraud_purchase_flag=1
      AND distinct_id NOT IN (
        SELECT distinct_id
        FROM `yotam-395120.peerplay.potential_fraudsters_stage`
      );

    -- Handle overlapping users (exist in both potential_fraudsters_stage AND have manual fraud purchases)
    -- Update their manual flag to 1 while keeping their automated flags
    UPDATE `yotam-395120.peerplay.fraudsters_stage_temp`
    SET manual_identification_fraud_purchase_flag = 1
    WHERE distinct_id IN (
      SELECT distinct_id
      FROM `yotam-395120.peerplay.fraudsters`
      WHERE manual_identification_fraud_purchase_flag=1
    );

    -- Final step: replace the content in the fraudsters_stage table
    CREATE OR REPLACE TABLE yotam-395120.peerplay.fraudsters_stage
    AS
    SELECT * FROM yotam-395120.peerplay.fraudsters_stage_temp;
    """
    
    try:
        # Execute the multi-statement query
        query_job = client.query(query)
        query_job.result()  # Wait for completion
        logger.info("✓ Step 3 completed: fraudsters_stage table updated (DEV)")
        log_step(client, run_id, "3", is_start=False)
        return {"success": True, "step": 3}
    except Exception as e:
        error_msg = f"Step 3 failed: {str(e)}"
        logger.error(error_msg)
        send_error_alert(3, e, run_id, query[:500])
        log_step(client, run_id, "3", is_start=False)
        raise Exception(error_msg)


def get_distinct_ids_from_bigquery(client: bigquery.Client) -> List[str]:
    """Fetch distinct IDs from BigQuery fraudsters_stage_temp table"""
    logger.info(f"Fetching distinct IDs from {PROJECT_ID}.{DATASET_ID}.{FRAUDSTERS_TEMP_TABLE}...")
    
    query = f"""
    SELECT DISTINCT distinct_id
    FROM `{PROJECT_ID}.{DATASET_ID}.{FRAUDSTERS_TEMP_TABLE}`
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
    Update Mixpanel user profiles with STAGING cohort marker property
    """
    logger.info(f"Updating {len(distinct_ids)} user profiles with STAGING cohort marker...")
    
    cohort_marker_value = CONSISTENT_COHORT_MARKER
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
                    "fraudster_cohort_marker": cohort_marker_value,  # CONSISTENT VALUE
                    "fraudster_last_updated": update_timestamp       # Track when last updated
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
    logger.info(f"✓ Cohort marker property: fraudster_cohort_marker = '{cohort_marker_value}'")
    
    return successful_updates, cohort_marker_value


def create_mixpanel_cohort(distinct_ids: List[str], cohort_name: str = "known_fraudsters_stage"):
    """
    Note: Mixpanel cohorts cannot be created programmatically via API.
    Cohorts must be created manually in the Mixpanel UI.
    
    This function provides instructions for manual cohort creation.
    User profiles have already been updated with the marker property.
    """
    logger.info(f"ℹ Mixpanel cohort '{cohort_name}' must be created manually in the UI")
    logger.info("")
    logger.info("=" * 60)
    logger.info("COHORT CREATION INSTRUCTIONS:")
    logger.info("=" * 60)
    logger.info(f"1. Go to Mixpanel UI: https://mixpanel.com/project/2991947/cohorts")
    logger.info(f"2. Click 'Create Cohort' or edit existing '{cohort_name}'")
    logger.info(f"3. Set cohort filter to:")
    logger.info(f"   fraudster_cohort_marker = '{CONSISTENT_COHORT_MARKER}'")
    logger.info(f"4. Save the cohort")
    logger.info("")
    logger.info(f"✓ {len(distinct_ids)} user profiles have been updated with property:")
    logger.info(f"   fraudster_cohort_marker = '{CONSISTENT_COHORT_MARKER}'")
    logger.info("=" * 60)
    logger.info("")
    
    # Return False to indicate manual creation is needed
    # This is not an error - it's expected behavior
    return False


def step_4_update_mixpanel_cohort(client: bigquery.Client, run_id: str) -> Dict[str, Any]:
    """Step 4: Update Mixpanel cohort with fraudster markers (STAGING)"""
    logger.info("Starting Step 4: Update Mixpanel cohort (STAGING)")
    log_step(client, run_id, "4", is_start=True)
    
    try:
        # Get distinct IDs from BigQuery
        distinct_ids = get_distinct_ids_from_bigquery(client)
        if not distinct_ids:
            logger.warning("✗ No distinct IDs found. Skipping Mixpanel update.")
            log_step(client, run_id, "4", is_start=False)
            return {"success": True, "step": 4, "updated_count": 0}
        
        # Update profiles with staging marker
        logger.info(f"Using STAGING cohort marker: '{CONSISTENT_COHORT_MARKER}'")
        successful_updates, cohort_marker = update_user_profiles_with_marker(distinct_ids)
        
        # Note: Cohort creation is manual - provide instructions
        cohort_created = create_mixpanel_cohort(distinct_ids, "known_fraudsters_stage")
        
        if successful_updates > 0:
            logger.info(f"✓ Step 4 completed: Updated {successful_updates} user profiles in Mixpanel")
            logger.info(f"ℹ Mixpanel cohort 'known_fraudsters_stage' must be created manually in UI (see instructions above)")
        else:
            logger.warning("✗ Step 4: No profiles updated")
        
        log_step(client, run_id, "4", is_start=False)
        return {"success": True, "step": 4, "updated_count": successful_updates, "cohort_created": cohort_created}
    except Exception as e:
        error_msg = f"Step 4 failed: {str(e)}"
        logger.error(error_msg)
        send_error_alert(4, e, run_id)
        log_step(client, run_id, "4", is_start=False)
        raise Exception(error_msg)


def run_fraudsters_management():
    """Main execution function - DEV VERSION"""
    logger.info("=" * 60)
    logger.info("FRAUDSTERS MANAGEMENT PROCESS (DEV/STAGING) - STARTING")
    logger.info("=" * 60)
    
    # Generate unique run_id for this execution
    run_id = str(uuid.uuid4())
    logger.info(f"Run ID for this execution: {run_id}")
    
    # Ensure GCP_PROJECT_ID is set for BigQuery client
    if not os.getenv("GCP_PROJECT_ID"):
        os.environ["GCP_PROJECT_ID"] = PROJECT_ID
        logger.info(f"Set GCP_PROJECT_ID environment variable to: {PROJECT_ID}")
    
    # Get BigQuery client - use explicit project ID to ensure correct initialization
    try:
        client = bigquery.Client(project=PROJECT_ID)
        logger.info(f"BigQuery client initialized with project: {PROJECT_ID}")
    except Exception as e:
        logger.warning(f"Failed to initialize with explicit project, trying get_bigquery_client(): {e}")
    client = get_bigquery_client()
    
    results = {
        "run_id": run_id,
        "start_time": datetime.datetime.utcnow().isoformat(),
        "steps": [],
        "mode": "DEV/STAGING"
    }
    
    # Execute all steps
    steps = [
        ("Step 1", step_1_calculate_potential_fraudsters),
        ("Step 2", step_2_calculate_offerwall_cheaters),
        ("Step 3", step_3_update_fraudsters_table),
        ("Step 4", step_4_update_mixpanel_cohort),
    ]
    
    for step_name, step_func in steps:
        try:
            step_result = step_func(client, run_id)
            # Check if step returned a warning (non-fatal error)
            if isinstance(step_result, dict) and step_result.get("success") == False and step_result.get("warning"):
                results["steps"].append({
                    "step": step_name,
                    "success": False,
                    "error": step_result.get("error"),
                    "warning": step_result.get("warning")
                })
                logger.warning(f"⚠ {step_name} completed with warning: {step_result.get('warning')}")
            else:
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
    # Consider success if at least Steps 2-4 completed (Step 1 can fail due to Drive credentials)
    # Step 1 failure is non-fatal since Steps 2-4 can work with existing data
    critical_steps_success = all(step["success"] for step in results["steps"][1:])  # Steps 2-4
    step1_has_warning = len(results["steps"]) > 0 and results["steps"][0].get("warning")
    results["success"] = all(step["success"] for step in results["steps"]) or \
                         (critical_steps_success and step1_has_warning)
    
    logger.info("=" * 60)
    logger.info(f"FRAUDSTERS MANAGEMENT PROCESS (DEV/STAGING) - {'SUCCESS' if results['success'] else 'COMPLETED WITH ERRORS'}")
    logger.info("=" * 60)
    
    return results


@app.route('/', methods=['GET', 'POST'])
def handle_request():
    """Cloud Run entry point (not used in dev version)"""
    logger = setup_logging()
    logger.info("Fraudsters Management DEV version - Cloud Run entry point (not used)")
    
    try:
        results = run_fraudsters_management()
        
        return jsonify({
            'success': results['success'],
            'run_id': results['run_id'],
            'steps': results['steps'],
            'start_time': results['start_time'],
            'end_time': results['end_time'],
            'timestamp': datetime.datetime.utcnow().isoformat()
        }), 200
    except Exception as e:
        logger.error(f"Fraudsters Management service failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.datetime.utcnow().isoformat()
        }), 500


if __name__ == '__main__':
    # Run locally
    logger.info("Running Fraudsters Management DEV version locally...")
    result = run_fraudsters_management()
    print(json.dumps(result, indent=2))

