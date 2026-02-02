-- ================================================
-- POPULATE BIGQUERY METADATA TABLES FROM NOTION
-- ================================================
-- This script populates the 4 metadata tables from the Notion documentation
-- Run this after creating the tables with bigquery_setup.sql

-- Clear existing data (optional - remove if you want to keep existing records)
DELETE FROM `yotam-395120.peerplay.query_gen_guardrails` WHERE TRUE;
DELETE FROM `yotam-395120.peerplay.query_gen_tables` WHERE TRUE;
DELETE FROM `yotam-395120.peerplay.query_gen_columns` WHERE TRUE;
DELETE FROM `yotam-395120.peerplay.query_gen_known_metrics` WHERE TRUE;

-- ================================================
-- 1. GUARDRAILS TABLE
-- ================================================

-- Partition usage policy
INSERT INTO `yotam-395120.peerplay.query_gen_guardrails` 
(guardrails_name, guardrails_description, guardrails_tags)
VALUES
('date_partition_requirement', 'ALWAYS use the date partition column when querying vmp_master_event_normalized. Use WHERE date >= CURRENT_DATE() - X instead of filtering only on timestamp calculations', ARRAY['partition', 'performance', 'cost', 'events']),

-- BigQuery cost control
('maximum_bytes_billed', 'When executing BigQuery queries programmatically always include maximumBytesBilled parameter set to 2000000000000 (2TB) to control costs and prevent unexpected charges', ARRAY['cost', 'safety', 'cli']),

-- Table selection priority
('table_selection_priority', 'Follow this hierarchy: 1) agg_player_daily for daily metrics like revenue DAU purchases - fastest and most cost-effective 2) dim_player for lifetime user metrics LTV total revenue install date 3) agg_player_chapter_daily for chapter-specific daily analysis 4) vmp_master_event_normalized ONLY when aggregated tables lack needed data or for current date data', ARRAY['tables', 'performance', 'optimization']),

-- Country filtering
('exclude_test_countries', 'Always exclude test countries UA IL AM in analytics queries. Use mp_country_code NOT IN or coalesce first_country last_country NOT IN for aggregated tables. Also exclude currency UAH', ARRAY['filtering', 'data-quality', 'countries']),

-- Fraudster exclusion
('exclude_fraudsters', 'For revenue KPIs exclude fraudsters table. For other KPIs exclude potential_fraudsters table. Use NOT IN subquery pattern', ARRAY['fraud', 'filtering', 'data-quality']),

-- State loss users exclusion  
('exclude_state_loss_users', 'Always exclude temporary state loss users from state_loss_temp_users table', ARRAY['filtering', 'data-quality']),

-- Purchase filtering
('purchase_exclusion', 'Exclude 0.01 test purchases when analyzing purchase data. Filter where price_original != 0.01', ARRAY['purchases', 'revenue', 'filtering']),

-- Event ordering
('event_ordering_post_v0368', 'Since version 0.368 from 2025-10-09 multiple events can have same res_timestamp. Order by res_timestamp AND counter_per_session_game_side when ordering events after this date', ARRAY['events', 'ordering', 'timestamp']),

-- Float partitioning limitation
('no_float_partitioning', 'BigQuery does not allow partitioning by FLOAT64 columns. Convert timestamps using TIMESTAMP_MILLIS with CAST to INT64. Convert version_float to STRING if needed for partitioning', ARRAY['bigquery', 'partitioning', 'data-types']),

-- Purchase deduplication
('purchase_deduplication', 'Always deduplicate purchases by purchase_id grouped with date. Use MAX of price_usd for each purchase_id and date combination to avoid revenue inflation from duplicate logging', ARRAY['purchases', 'deduplication', 'revenue']),

-- Reserved keywords
('avoid_reserved_keywords', 'Never use BigQuery reserved keywords as table aliases like current user table order group limit timestamp date time interval. Use descriptive alternatives like evt curr prev', ARRAY['sql', 'syntax', 'best-practices']),

-- Lead/Lag usage
('lead_lag_usage', 'Do NOT use LEAD or LAG for event funnels unless explicitly analyzing strictly adjacent events. For time-based funnels use time windows and join on timestamp conditions instead of window functions', ARRAY['funnels', 'analysis', 'events']),

-- Aggregated tables for retention
('retention_use_dim_player', 'For retention analysis use pre-calculated retention flags in dim_player table like d1_retention d7_retention d30_retention for supported periods 0 1 3 7 14 21 30 45 60 75 90 120 150 180 days and more', ARRAY['retention', 'dim_player', 'performance']),

-- Version filtering for analysis
('active_versions_only', 'When calculating KPIs by version join with active_versions table to filter only active versions with more than 1000 users per day for main countries or more than 100 for low payers countries', ARRAY['versions', 'filtering', 'analysis']);

-- ================================================
-- 2. TABLES METADATA
-- ================================================

-- Main aggregated table
INSERT INTO `yotam-395120.peerplay.query_gen_tables`
(table_name, table_description, table_partition, table_clusters_list, usage_description, table_tags)
VALUES
('yotam-395120.peerplay.agg_player_daily', 
 'Pre-calculated daily metrics per user. Contains revenue IAP and ad, game actions generations merges credits spent, user attributes chapter platform country. 10-100x faster than raw events. Use for daily revenue DAU ARPDAU daily user activity', 
 'date',
 ARRAY['distinct_id'],
 'Use this table for any daily metrics queries. Available metrics: total_revenue total_purchase_revenue total_ad_revenue count_purchases count_video_watched generations_count merges_count total_credits_spent generation_credits_spent bubble_credits_spent first_chapter last_chapter first_platform last_platform first_country last_country first_mediasource last_mediasource',
 ARRAY['aggregated', 'daily', 'revenue', 'activity', 'primary']),

-- User dimension table  
('yotam-395120.peerplay.dim_player',
 'User lifetime attributes and metrics. One row per distinct_id. Contains LTV revenue lifetime game actions install attributes retention metrics first purchase info current state. Use for user-level analysis LTV retention install cohorts first-time depositors',
 NULL,
 ARRAY['distinct_id'],
 'Use for lifetime user metrics. Available: ltv_revenue ltv_ad_revenue ltv_iap_revenue ltv_purchases ltv_ads_impressions ltv_generations_count ltv_merges_count install_date first_mediasource first_country first_platform d1_retention d7_retention d30_retention first_purchase_time last_chapter last_credit_balance',
 ARRAY['dimension', 'lifetime', 'retention', 'ltv', 'users']),

-- Chapter daily aggregated table
('yotam-395120.peerplay.agg_player_chapter_daily',
 'Same metrics as agg_player_daily but with chapter dimension. One row per distinct_id per date per chapter. Use for chapter-specific analysis chapter progression analysis chapter-based revenue and activity',
 'date',
 ARRAY['distinct_id', 'chapter'],
 'Use when you need to analyze metrics broken down by chapter. Contains same metrics as agg_player_daily plus chapter dimension',
 ARRAY['aggregated', 'daily', 'chapter', 'activity']),

-- Raw events table (use sparingly)
('yotam-395120.peerplay.vmp_master_event_normalized',
 'Raw event-level data. Every user action logged as event. Use ONLY when aggregated tables lack specific data or need current date data or need event sequences funnels or need detailed event debugging. WARNING Large table expensive to query. ALWAYS filter by date partition',
 'date',
 ARRAY['distinct_id', 'mp_event_name'],
 'Key columns: distinct_id user ID, mp_event_name event type, res_timestamp event time convert with TIMESTAMP_MILLIS, date partition ALWAYS use, chapter, credit_balance, version_float, mp_os, mp_country_code, end_of_content, mode_status, game_board. Common events: purchase_successful generation merge rewarded_video_revenue_from_impression_data scapes_tasks_new_chapter',
 ARRAY['raw', 'events', 'detailed', 'expensive']),

-- Fraudsters tables
('yotam-395120.peerplay.fraudsters',
 'Contains distinct_ids of revenue-related fraudsters. Use for excluding fraudulent revenue in purchase and revenue queries',
 NULL,
 NULL,
 'Use in WHERE clause with NOT IN subquery for revenue-related queries',
 ARRAY['fraud', 'exclusion', 'revenue']),

('yotam-395120.peerplay.potential_fraudsters',
 'Contains distinct_ids of all types of fraudsters gameplay and revenue. Use for excluding fraudsters from non-revenue queries',
 NULL,
 NULL,
 'Use in WHERE clause with NOT IN subquery for non-revenue queries',
 ARRAY['fraud', 'exclusion', 'general']),

-- State loss users
('yotam-395120.peerplay.state_loss_temp_users',
 'Contains distinct_ids of temporary users created during state loss events. These users had very short lifespans and should be excluded from analysis',
 NULL,
 NULL,
 'Always exclude with NOT IN subquery',
 ARRAY['state-loss', 'exclusion', 'data-quality']),

-- Active versions table
('yotam-395120.peerplay.active_versions',
 'Contains daily active user counts per version per platform. Used to filter for active versions in analysis',
 'date',
 NULL,
 'Columns: date version_float android_active_users apple_active_users android_active_users_low_payers_countries apple_active_users_low_payers_countries. Filter for active versions with total users over 1000',
 ARRAY['versions', 'filtering', 'metadata']),

-- Country dimension
('yotam-395120.peerplay.dim_country',
 'Country metadata including low payers country flag',
 NULL,
 NULL,
 'Use to exclude low payers countries by joining on country_code with is_low_payers_country flag',
 ARRAY['country', 'dimension', 'filtering']),

-- Sentry errors
('yotam-395120.peerplay.sentry_errors',
 'Sentry error logs. Contains error_id group_id issue_short_id user_id maps to distinct_id, timestamp title message platform environment',
 NULL,
 NULL,
 'Join with events using user_id equals distinct_id and timestamp proximity. Filter by issue_short_id for specific issues or level for severity',
 ARRAY['errors', 'debugging', 'sentry']),

-- Firebase Crashlytics
('yotam-395120.peerplay.firebase_crashlytics_realtime_flattened',
 'Firebase crash and error data. Rolling 30-day window. Contains event_id event_timestamp user_id maps to distinct_id, platform is_fatal issue_id device info memory data blame_frame location',
 NULL,
 NULL,
 'Data retention 30 days rolling. Join with game events using user_id equals distinct_id. Filter by is_fatal for crash severity',
 ARRAY['crashlytics', 'debugging', 'firebase', 'crashes']),

-- Launch funnel analysis
('yotam-395120.peerplay.launch_funnel_analysis_dashboard',
 'Tracks app launch sequences and timing. Failed launches identified when splash_to_scapes_time IS NULL',
 'splash_date',
 NULL,
 'Key fields: distinct_id splash_time full_launch_time launch_type First Launch or Repeat Launch, version_float. Failed launch equals splash_to_scapes_time IS NULL',
 ARRAY['launch', 'performance', 'funnel']),

-- State loss tracking
('yotam-395120.peerplay.users_lost_state',
 'Tracks user state loss events progress regression. Contains device_id distinct_id before and after, prev_chapter chapter_after_drop is_restore_user_state',
 'date',
 NULL,
 'Analyze state losses and restoration success. Users with permanent loss WHERE prev_chapter greater than latest_chapter',
 ARRAY['state-loss', 'debugging', 'user-issues']),

-- Google Play sales
('yotam-395120.peerplay.googleplay_sales',
 'Google Play transaction records. Daily import at 2AM UTC. Contains order_number maps to google_order_number, order_charged_date charged_amount currency_of_sale sku_id device_model country_of_buyer',
 NULL,
 NULL,
 'For revenue reconciliation. Join with events on google_order_number equals order_number. No current day data. Excludes sandbox purchases',
 ARRAY['googleplay', 'revenue', 'reconciliation', 'android']),

-- Singular events
('yotam-395120.singular.singular_events',
 'Events sent to Singular for attribution. Updated every few hours. Contains custom_user_id maps to distinct_id, adjusted_timestamp name event name, partner campaign info attribution data',
 'etl_record_processing_hour_utc',
 NULL,
 'For attribution analysis and event trace. Use etl_record_processing_hour_utc as default time filter. Revenue events: __iap__ and __ADMON_USER_LEVEL_REVENUE__',
 ARRAY['singular', 'attribution', 'events']),

-- Max revenue data
('yotam-395120.peerplay.max_revenue_data',
 'Max AppLovin impression-level ad revenue data. Daily import at 10AM UTC. Contains timestamp user_id maps to distinct_id, placement country revenue',
 'date',
 NULL,
 'For ad revenue reconciliation. Imported daily with yesterday plus 1-day-ago update',
 ARRAY['max', 'ad-revenue', 'reconciliation', 'impressions']),

-- LevelPlay revenue data
('yotam-395120.peerplay.levelplay_revenue_data',
 'IronSource LevelPlay impression-level ad revenue. Daily import at 12PM UTC. Contains event_timestamp user_id maps to distinct_id, ad_network placement country revenue',
 'date',
 NULL,
 'For ad revenue reconciliation. Imported daily with yesterday plus 2-days-ago update',
 ARRAY['levelplay', 'ironsource', 'ad-revenue', 'reconciliation']),

-- Marketing costs
('yotam-395120.singular.marketing_data',
 'Marketing spend data from Singular. Campaign Data Schema. Updates at 04:00 10:00 16:00 22:00 UTC',
 'date',
 NULL,
 'Key fields: date source os country_field adn_cost adn_impressions adn_clicks adn_installs campaign_id campaign_name. For cost analysis and ROAS',
 ARRAY['singular', 'marketing', 'costs', 'roas']),

-- Verification service events
('yotam-395120.peerplay.verification_service_events',
 'Backend service events for purchase verification Apple. Contains distinct_id endpoint_name transaction_id request_id event_name',
 'date',
 NULL,
 'For validating Apple purchases. Events: purchase_verification_request purchase_verification_approval',
 ARRAY['verification', 'purchases', 'backend', 'apple']),

-- Daily currency rates
('yotam-395120.peerplay.prod_daily_currency_rates',
 'Daily exchange rates for currency conversion',
 'date',
 NULL,
 'Use to convert Google Play revenue to USD by joining on currency_id and date',
 ARRAY['currency', 'exchange-rates', 'conversion']),

-- Item mapping to value
('yotam-395120.peerplay.item_mapping_to_value',
 'Maps item IDs to their credit value in the game economy',
 NULL,
 NULL,
 'Join on CAST distinct_id AS INT64 equals item_id. Use real value column. For mode 2 multiply by 0.75',
 ARRAY['items', 'economy', 'mapping', 'values']),

-- Sources names alignment
('yotam-395120.peerplay.sources_names_alignment',
 'Maps media source names to standardized names and media types social offerwall networks organic',
 NULL,
 NULL,
 'Join with dim_player.first_mediasource on final_name. Returns media_type for grouping',
 ARRAY['attribution', 'media-source', 'mapping']),

-- Sentry mapping
('yotam-395120.peerplay.sentry_mapping',
 'Daily mapping between Sentry errors and game users based on IP device location timestamp proximity',
 'error_date',
 NULL,
 'Pre-joined Sentry errors with user distinct_ids. Use instead of manual joining. Filter by match_status equals Match Found',
 ARRAY['sentry', 'mapping', 'debugging']),

-- Board task values
('yotam-395120.peerplay.board_tasks_values',
 'Pre-calculated credit values required to complete board tasks',
 'date',
 NULL,
 'Contains chapter version task_value board_task_trigger. For calculating avg task difficulty use avg of task_value WHERE task_value not equal 0',
 ARRAY['board-tasks', 'economy', 'difficulty']);

-- ================================================
-- 3. COLUMNS METADATA (Key columns for main tables)
-- ================================================

-- agg_player_daily columns
INSERT INTO `yotam-395120.peerplay.query_gen_columns`
(column_name, related_table, column_type, is_partition, is_cluster, is_primary_key, column_description, column_tags)
VALUES
('date', 'yotam-395120.peerplay.agg_player_daily', 'DATE', TRUE, FALSE, FALSE, 'Date of activity. Partition column - always use in WHERE clause', ARRAY['partition', 'time', 'required']),
('distinct_id', 'yotam-395120.peerplay.agg_player_daily', 'STRING', FALSE, TRUE, FALSE, 'Unique user identifier', ARRAY['user-id', 'cluster', 'join-key']),
('total_revenue', 'yotam-395120.peerplay.agg_player_daily', 'FLOAT64', FALSE, FALSE, FALSE, 'Total revenue IAP plus ads for this user on this day', ARRAY['revenue', 'kpi', 'aggregate']),
('total_purchase_revenue', 'yotam-395120.peerplay.agg_player_daily', 'FLOAT64', FALSE, FALSE, FALSE, 'IAP revenue for this user on this day', ARRAY['revenue', 'iap', 'kpi']),
('total_ad_revenue', 'yotam-395120.peerplay.agg_player_daily', 'FLOAT64', FALSE, FALSE, FALSE, 'Ad revenue for this user on this day', ARRAY['revenue', 'ads', 'kpi']),
('count_purchases', 'yotam-395120.peerplay.agg_player_daily', 'INTEGER', FALSE, FALSE, FALSE, 'Number of purchases made by user on this day', ARRAY['purchases', 'count', 'kpi']),
('count_video_watched', 'yotam-395120.peerplay.agg_player_daily', 'INTEGER', FALSE, FALSE, FALSE, 'Number of rewarded videos watched on this day', ARRAY['ads', 'count', 'kpi']),
('generations_count', 'yotam-395120.peerplay.agg_player_daily', 'INTEGER', FALSE, FALSE, FALSE, 'Number of generation actions on this day', ARRAY['gameplay', 'count', 'kpi']),
('merges_count', 'yotam-395120.peerplay.agg_player_daily', 'INTEGER', FALSE, FALSE, FALSE, 'Number of merge actions on this day', ARRAY['gameplay', 'count', 'kpi']),
('total_credits_spent', 'yotam-395120.peerplay.agg_player_daily', 'INTEGER', FALSE, FALSE, FALSE, 'Total credits spent generations plus bubbles on this day', ARRAY['gameplay', 'economy', 'kpi']),
('generation_credits_spent', 'yotam-395120.peerplay.agg_player_daily', 'INTEGER', FALSE, FALSE, FALSE, 'Credits spent on generations on this day', ARRAY['gameplay', 'economy', 'kpi']),
('bubble_credits_spent', 'yotam-395120.peerplay.agg_player_daily', 'INTEGER', FALSE, FALSE, FALSE, 'Credits spent on bubbles on this day', ARRAY['gameplay', 'economy', 'kpi']),
('first_chapter', 'yotam-395120.peerplay.agg_player_daily', 'INTEGER', FALSE, FALSE, FALSE, 'First chapter seen for this user on this day', ARRAY['chapter', 'progression']),
('last_chapter', 'yotam-395120.peerplay.agg_player_daily', 'INTEGER', FALSE, FALSE, FALSE, 'Last chapter seen for this user on this day', ARRAY['chapter', 'progression']),
('first_platform', 'yotam-395120.peerplay.agg_player_daily', 'STRING', FALSE, FALSE, FALSE, 'First platform Apple or Android seen for user on this day', ARRAY['platform', 'device']),
('last_platform', 'yotam-395120.peerplay.agg_player_daily', 'STRING', FALSE, FALSE, FALSE, 'Last platform Apple or Android seen for user on this day', ARRAY['platform', 'device']),
('first_country', 'yotam-395120.peerplay.agg_player_daily', 'STRING', FALSE, FALSE, FALSE, 'First country code seen for user on this day', ARRAY['geo', 'country']),
('last_country', 'yotam-395120.peerplay.agg_player_daily', 'STRING', FALSE, FALSE, FALSE, 'Last country code seen for user on this day', ARRAY['geo', 'country']),
('first_mediasource', 'yotam-395120.peerplay.agg_player_daily', 'STRING', FALSE, FALSE, FALSE, 'First media source seen for user on this day', ARRAY['attribution', 'media-source']),
('last_mediasource', 'yotam-395120.peerplay.agg_player_daily', 'STRING', FALSE, FALSE, FALSE, 'Last media source seen for user on this day', ARRAY['attribution', 'media-source']);

-- dim_player columns
INSERT INTO `yotam-395120.peerplay.query_gen_columns`
(column_name, related_table, column_type, is_partition, is_cluster, is_primary_key, column_description, column_tags)
VALUES
('distinct_id', 'yotam-395120.peerplay.dim_player', 'STRING', FALSE, TRUE, TRUE, 'Unique user identifier. Primary key', ARRAY['user-id', 'cluster', 'primary-key']),
('install_date', 'yotam-395120.peerplay.dim_player', 'DATE', FALSE, FALSE, FALSE, 'Date when user first installed the app', ARRAY['install', 'cohort', 'time']),
('ltv_revenue', 'yotam-395120.peerplay.dim_player', 'FLOAT64', FALSE, FALSE, FALSE, 'Lifetime total revenue IAP plus ads for this user', ARRAY['ltv', 'revenue', 'kpi']),
('ltv_ad_revenue', 'yotam-395120.peerplay.dim_player', 'FLOAT64', FALSE, FALSE, FALSE, 'Lifetime ad revenue for this user', ARRAY['ltv', 'revenue', 'ads']),
('ltv_iap_revenue', 'yotam-395120.peerplay.dim_player', 'FLOAT64', FALSE, FALSE, FALSE, 'Lifetime IAP revenue for this user', ARRAY['ltv', 'revenue', 'iap']),
('ltv_purchases', 'yotam-395120.peerplay.dim_player', 'INTEGER', FALSE, FALSE, FALSE, 'Lifetime number of purchases', ARRAY['ltv', 'purchases', 'count']),
('ltv_ads_impressions', 'yotam-395120.peerplay.dim_player', 'INTEGER', FALSE, FALSE, FALSE, 'Lifetime number of ads watched', ARRAY['ltv', 'ads', 'count']),
('ltv_generations_count', 'yotam-395120.peerplay.dim_player', 'INTEGER', FALSE, FALSE, FALSE, 'Lifetime number of generation actions', ARRAY['ltv', 'gameplay', 'count']),
('ltv_merges_count', 'yotam-395120.peerplay.dim_player', 'INTEGER', FALSE, FALSE, FALSE, 'Lifetime number of merge actions', ARRAY['ltv', 'gameplay', 'count']),
('ltv_total_credits_spent', 'yotam-395120.peerplay.dim_player', 'INTEGER', FALSE, FALSE, FALSE, 'Lifetime total credits spent', ARRAY['ltv', 'economy', 'gameplay']),
('first_mediasource', 'yotam-395120.peerplay.dim_player', 'STRING', FALSE, FALSE, FALSE, 'First-touch attribution acquisition media source', ARRAY['attribution', 'install', 'media-source']),
('first_country', 'yotam-395120.peerplay.dim_player', 'STRING', FALSE, FALSE, FALSE, 'Country at install time', ARRAY['geo', 'install', 'country']),
('first_platform', 'yotam-395120.peerplay.dim_player', 'STRING', FALSE, FALSE, FALSE, 'Platform Apple or Android at install. Users cannot switch platforms', ARRAY['platform', 'install', 'device']),
('first_app_version', 'yotam-395120.peerplay.dim_player', 'FLOAT64', FALSE, FALSE, FALSE, 'App version at install time', ARRAY['version', 'install']),
('last_chapter', 'yotam-395120.peerplay.dim_player', 'INTEGER', FALSE, FALSE, FALSE, 'Most recent chapter achieved by this user', ARRAY['chapter', 'progression', 'current']),
('last_credit_balance', 'yotam-395120.peerplay.dim_player', 'FLOAT64', FALSE, FALSE, FALSE, 'Most recent credit balance', ARRAY['economy', 'current', 'credits']),
('last_platform', 'yotam-395120.peerplay.dim_player', 'STRING', FALSE, FALSE, FALSE, 'Most recent platform. Should match first_platform', ARRAY['platform', 'current']),
('d1_retention', 'yotam-395120.peerplay.dim_player', 'INTEGER', FALSE, FALSE, FALSE, 'Day 1 retention flag 1 retained 0 not retained', ARRAY['retention', 'cohort', 'kpi']),
('d7_retention', 'yotam-395120.peerplay.dim_player', 'INTEGER', FALSE, FALSE, FALSE, 'Day 7 retention flag 1 retained 0 not retained', ARRAY['retention', 'cohort', 'kpi']),
('d30_retention', 'yotam-395120.peerplay.dim_player', 'INTEGER', FALSE, FALSE, FALSE, 'Day 30 retention flag 1 retained 0 not retained', ARRAY['retention', 'cohort', 'kpi']),
('first_purchase_time', 'yotam-395120.peerplay.dim_player', 'TIMESTAMP', FALSE, FALSE, FALSE, 'Timestamp of first purchase', ARRAY['purchases', 'ftd', 'conversion']),
('first_purchase_value', 'yotam-395120.peerplay.dim_player', 'FLOAT64', FALSE, FALSE, FALSE, 'Value of first purchase in USD', ARRAY['purchases', 'ftd', 'revenue']);

-- vmp_master_event_normalized key columns
INSERT INTO `yotam-395120.peerplay.query_gen_columns`
(column_name, related_table, column_type, is_partition, is_cluster, is_primary_key, column_description, column_tags)
VALUES
('date', 'yotam-395120.peerplay.vmp_master_event_normalized', 'DATE', TRUE, FALSE, FALSE, 'Date partition column. ALWAYS use in WHERE clause for performance', ARRAY['partition', 'time', 'required']),
('distinct_id', 'yotam-395120.peerplay.vmp_master_event_normalized', 'STRING', FALSE, TRUE, FALSE, 'Unique user identifier', ARRAY['user-id', 'cluster', 'join-key']),
('mp_event_name', 'yotam-395120.peerplay.vmp_master_event_normalized', 'STRING', FALSE, TRUE, FALSE, 'Event type name like purchase_successful generation merge', ARRAY['event-type', 'cluster', 'required']),
('res_timestamp', 'yotam-395120.peerplay.vmp_master_event_normalized', 'FLOAT64', FALSE, FALSE, FALSE, 'Unix timestamp in milliseconds as FLOAT64. Convert to timestamp using TIMESTAMP_MILLIS with CAST to INT64', ARRAY['timestamp', 'time', 'ordering']),
('counter_per_session_game_side', 'yotam-395120.peerplay.vmp_master_event_normalized', 'INTEGER', FALSE, FALSE, FALSE, 'Event counter within session. Use with res_timestamp for ordering after version 0.368', ARRAY['ordering', 'sequence']),
('chapter', 'yotam-395120.peerplay.vmp_master_event_normalized', 'FLOAT64', FALSE, FALSE, FALSE, 'User chapter or level at time of event', ARRAY['chapter', 'progression']),
('credit_balance', 'yotam-395120.peerplay.vmp_master_event_normalized', 'FLOAT64', FALSE, FALSE, FALSE, 'User credit balance at time of event', ARRAY['economy', 'credits', 'state']),
('version_float', 'yotam-395120.peerplay.vmp_master_event_normalized', 'FLOAT64', FALSE, FALSE, FALSE, 'App version number', ARRAY['version', 'app']),
('mp_os', 'yotam-395120.peerplay.vmp_master_event_normalized', 'STRING', FALSE, FALSE, FALSE, 'Operating system Apple or Android', ARRAY['platform', 'os', 'device']),
('mp_country_code', 'yotam-395120.peerplay.vmp_master_event_normalized', 'STRING', FALSE, FALSE, FALSE, 'Two-letter country code like US CA AU', ARRAY['geo', 'country']),
('end_of_content', 'yotam-395120.peerplay.vmp_master_event_normalized', 'INTEGER', FALSE, FALSE, FALSE, 'Global parameter 1 if user reached end of available content 0 otherwise', ARRAY['state', 'eoc', 'progression']),
('mode_status', 'yotam-395120.peerplay.vmp_master_event_normalized', 'INTEGER', FALSE, FALSE, FALSE, 'Game mode 0 is Mode 1, 1 is Mode 2, 2 is Mode 3', ARRAY['mode', 'gameplay']),
('price_usd', 'yotam-395120.peerplay.vmp_master_event_normalized', 'FLOAT64', FALSE, FALSE, FALSE, 'Purchase price in USD for purchase_successful events', ARRAY['purchases', 'revenue', 'usd']),
('price_original', 'yotam-395120.peerplay.vmp_master_event_normalized', 'FLOAT64', FALSE, FALSE, FALSE, 'Purchase price in original currency. Exclude 0.01 test purchases', ARRAY['purchases', 'revenue']),
('currency', 'yotam-395120.peerplay.vmp_master_event_normalized', 'STRING', FALSE, FALSE, FALSE, 'Purchase currency code', ARRAY['purchases', 'currency']),
('purchase_id', 'yotam-395120.peerplay.vmp_master_event_normalized', 'STRING', FALSE, FALSE, FALSE, 'Unique purchase identifier. Use for deduplication', ARRAY['purchases', 'id', 'deduplication']),
('google_order_number', 'yotam-395120.peerplay.vmp_master_event_normalized', 'STRING', FALSE, FALSE, FALSE, 'Google Play order number for Android purchases. Maps to order_number in googleplay_sales', ARRAY['purchases', 'android', 'join-key']),
('revenue', 'yotam-395120.peerplay.vmp_master_event_normalized', 'FLOAT64', FALSE, FALSE, FALSE, 'Ad revenue value for rewarded_video_revenue_from_impression_data events', ARRAY['ads', 'revenue']),
('delta_credits', 'yotam-395120.peerplay.vmp_master_event_normalized', 'FLOAT64', FALSE, FALSE, FALSE, 'Credit change for generation events always non-positive. Use ABS for spend calculation', ARRAY['economy', 'credits', 'generation']),
('bubble_cost', 'yotam-395120.peerplay.vmp_master_event_normalized', 'INTEGER', FALSE, FALSE, FALSE, 'Credits spent on bubble purchase positive value', ARRAY['economy', 'credits', 'bubble']);

-- ================================================
-- 4. KNOWN METRICS
-- ================================================

INSERT INTO `yotam-395120.peerplay.query_gen_known_metrics`
(metric_name, metric_description, metric_query_example, metric_tags)
VALUES
('daily_revenue', 
 'Total revenue IAP plus ads per day for non-test countries excluding fraudsters',
 'SELECT date, SUM(total_purchase_revenue) AS purchase_revenue, SUM(total_ad_revenue) AS ad_revenue, SUM(total_revenue) AS total_revenue FROM yotam-395120.peerplay.agg_player_daily WHERE date >= CURRENT_DATE() - 30 GROUP BY date ORDER BY date DESC',
 ARRAY['revenue', 'daily', 'kpi']),

('daily_active_users',
 'Count of distinct active users per day excluding test countries and fraudsters',
 'SELECT date, COUNT(DISTINCT apd.distinct_id) AS dau FROM yotam-395120.peerplay.agg_player_daily apd LEFT JOIN yotam-395120.peerplay.dim_player dp ON apd.distinct_id = dp.distinct_id WHERE date >= CURRENT_DATE() - 30 AND dp.first_country NOT IN (UA, IL, AM) AND apd.distinct_id NOT IN (SELECT distinct_id FROM yotam-395120.peerplay.potential_fraudsters) AND apd.distinct_id NOT IN (SELECT distinct_id FROM yotam-395120.peerplay.state_loss_temp_users) GROUP BY date ORDER BY date DESC',
 ARRAY['dau', 'daily', 'users', 'kpi']),

('arpdau',
 'Average revenue per daily active user',
 'SELECT date, COUNT(DISTINCT apd.distinct_id) AS dau, SUM(total_revenue) AS total_revenue, ROUND(SUM(total_revenue) / COUNT(DISTINCT apd.distinct_id), 4) AS arpdau FROM yotam-395120.peerplay.agg_player_daily apd LEFT JOIN yotam-395120.peerplay.dim_player dp ON apd.distinct_id = dp.distinct_id WHERE date >= CURRENT_DATE() - 30 AND dp.first_country NOT IN (UA, IL, AM) AND apd.distinct_id NOT IN (SELECT distinct_id FROM yotam-395120.peerplay.fraudsters) AND apd.distinct_id NOT IN (SELECT distinct_id FROM yotam-395120.peerplay.state_loss_temp_users) GROUP BY date ORDER BY date DESC',
 ARRAY['arpdau', 'revenue', 'daily', 'kpi']),

('installs',
 'Daily install count from dim_player',
 'SELECT install_date AS date, COUNT(DISTINCT distinct_id) AS installs FROM yotam-395120.peerplay.dim_player WHERE install_date >= CURRENT_DATE() - 30 AND first_country NOT IN (UA, IL, AM) AND distinct_id NOT IN (SELECT distinct_id FROM yotam-395120.peerplay.potential_fraudsters) AND distinct_id NOT IN (SELECT distinct_id FROM yotam-395120.peerplay.state_loss_temp_users) GROUP BY install_date ORDER BY install_date DESC',
 ARRAY['installs', 'acquisition', 'daily', 'kpi']),

('d1_retention_rate',
 'Day 1 retention rate per install cohort',
 'SELECT install_date, COUNT(DISTINCT distinct_id) AS cohort_size, COUNT(DISTINCT CASE WHEN d1_retention = 1 THEN distinct_id END) AS d1_retained, ROUND(100.0 * COUNT(DISTINCT CASE WHEN d1_retention = 1 THEN distinct_id END) / COUNT(DISTINCT distinct_id), 2) AS d1_retention_pct FROM yotam-395120.peerplay.dim_player WHERE first_country NOT IN (UA, IL, AM) AND distinct_id NOT IN (SELECT distinct_id FROM yotam-395120.peerplay.fraudsters) AND distinct_id NOT IN (SELECT distinct_id FROM yotam-395120.peerplay.state_loss_temp_users) AND install_date >= CURRENT_DATE() - 60 AND install_date < CURRENT_DATE() - 1 GROUP BY install_date ORDER BY install_date DESC',
 ARRAY['retention', 'd1', 'cohort', 'kpi']),

('d7_retention_rate',
 'Day 7 retention rate per install cohort',
 'SELECT install_date, COUNT(DISTINCT distinct_id) AS cohort_size, COUNT(DISTINCT CASE WHEN d7_retention = 1 THEN distinct_id END) AS d7_retained, ROUND(100.0 * COUNT(DISTINCT CASE WHEN d7_retention = 1 THEN distinct_id END) / COUNT(DISTINCT distinct_id), 2) AS d7_retention_pct FROM yotam-395120.peerplay.dim_player WHERE first_country NOT IN (UA, IL, AM) AND distinct_id NOT IN (SELECT distinct_id FROM yotam-395120.peerplay.fraudsters) AND distinct_id NOT IN (SELECT distinct_id FROM yotam-395120.peerplay.state_loss_temp_users) AND install_date >= CURRENT_DATE() - 60 AND install_date < CURRENT_DATE() - 7 GROUP BY install_date ORDER BY install_date DESC',
 ARRAY['retention', 'd7', 'cohort', 'kpi']),

('end_of_content_users_daily',
 'Daily count of users who reached end of content',
 'SELECT date, COUNT(DISTINCT distinct_id) AS eoc_users FROM yotam-395120.peerplay.vmp_master_event_normalized WHERE mp_event_name = scapes_tasks_new_chapter AND end_of_content = 1 AND date >= CURRENT_DATE() - 7 AND mp_country_code NOT IN (UA, IL, AM) AND distinct_id NOT IN (SELECT distinct_id FROM yotam-395120.peerplay.potential_fraudsters) AND distinct_id NOT IN (SELECT distinct_id FROM yotam-395120.peerplay.state_loss_temp_users) GROUP BY date ORDER BY date DESC',
 ARRAY['eoc', 'progression', 'content', 'daily']);

-- ================================================
-- VERIFICATION QUERIES
-- ================================================

SELECT 'guardrails' AS table_name, COUNT(*) AS record_count FROM `yotam-395120.peerplay.query_gen_guardrails`
UNION ALL
SELECT 'tables', COUNT(*) FROM `yotam-395120.peerplay.query_gen_tables`
UNION ALL
SELECT 'columns', COUNT(*) FROM `yotam-395120.peerplay.query_gen_columns`
UNION ALL
SELECT 'metrics', COUNT(*) FROM `yotam-395120.peerplay.query_gen_known_metrics`
ORDER BY table_name;
