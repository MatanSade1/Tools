# Notion Documentation Extraction Summary

## Overview
Successfully extracted and structured organizational data from the Notion "Main Documentation" page into the 4 BigQuery metadata tables for the query generation tool.

## What Was Extracted

### 1. Guardrails (14 records)
Query generation policies and best practices extracted from the documentation:

**Performance & Cost Management:**
- Date partition requirements (ALWAYS use date column)
- Maximum bytes billed policy (2TB limit)
- Table selection priority hierarchy
- Active versions filtering

**Data Quality:**
- Exclude test countries (UA, IL, AM)
- Exclude fraudsters (two different tables for revenue vs general)
- Exclude state loss temporary users
- Purchase filtering (exclude $0.01 test purchases)

**SQL Best Practices:**
- Event ordering post-v0.368 (use counter_per_session_game_side)
- No FLOAT64 partitioning (conversion required)
- Purchase deduplication by purchase_id
- Avoid reserved keywords as aliases
- Lead/Lag usage guidelines for funnels
- Retention analysis using pre-calculated flags

### 2. Tables (24 records)
All major tables in the schema with descriptions, partitions, clusters, and usage guidelines:

**Primary Analysis Tables:**
- `agg_player_daily` - Daily user metrics (10-100x faster than raw events)
- `dim_player` - Lifetime user attributes and LTV
- `agg_player_chapter_daily` - Chapter-specific daily metrics
- `vmp_master_event_normalized` - Raw events (use sparingly)

**Exclusion Tables:**
- `fraudsters` - Revenue-related fraudsters
- `potential_fraudsters` - All fraudsters
- `state_loss_temp_users` - Temporary users during state loss

**Metadata & Reference Tables:**
- `active_versions` - Version filtering
- `dim_country` - Country metadata
- `item_mapping_to_value` - Game economy values
- `sources_names_alignment` - Media source mapping
- `board_tasks_values` - Task difficulty values

**Debugging & Monitoring:**
- `sentry_errors` - Error logs
- `sentry_mapping` - Pre-joined user-error mapping
- `firebase_crashlytics_realtime_flattened` - Crash data (30-day rolling)
- `launch_funnel_analysis_dashboard` - Launch performance
- `users_lost_state` - State loss tracking

**Reconciliation & External Data:**
- `googleplay_sales` - Google Play transactions
- `singular.singular_events` - Attribution events
- `singular.marketing_data` - Marketing costs
- `max_revenue_data` - Max ad revenue
- `levelplay_revenue_data` - LevelPlay ad revenue
- `verification_service_events` - Purchase verification
- `prod_daily_currency_rates` - Exchange rates

### 3. Columns (62 records)
Key columns from the main analysis tables:

**agg_player_daily (19 columns):**
- Partition: `date`
- Cluster: `distinct_id`
- Revenue: `total_revenue`, `total_purchase_revenue`, `total_ad_revenue`
- Counts: `count_purchases`, `count_video_watched`, `generations_count`, `merges_count`
- Economy: `total_credits_spent`, `generation_credits_spent`, `bubble_credits_spent`
- Attributes: `first_chapter`, `last_chapter`, `first_platform`, `last_platform`, `first_country`, `last_country`, `first_mediasource`, `last_mediasource`

**dim_player (21 columns):**
- Primary Key: `distinct_id`
- Install: `install_date`
- LTV Metrics: `ltv_revenue`, `ltv_ad_revenue`, `ltv_iap_revenue`, `ltv_purchases`, `ltv_ads_impressions`, `ltv_generations_count`, `ltv_merges_count`, `ltv_total_credits_spent`
- Attribution: `first_mediasource`, `first_country`, `first_platform`, `first_app_version`
- Current State: `last_chapter`, `last_credit_balance`, `last_platform`
- Retention: `d1_retention`, `d7_retention`, `d30_retention`
- Conversion: `first_purchase_time`, `first_purchase_value`

**vmp_master_event_normalized (20 key columns):**
- Partition: `date` (ALWAYS required)
- Clusters: `distinct_id`, `mp_event_name`
- Time: `res_timestamp`, `counter_per_session_game_side`
- User State: `chapter`, `credit_balance`, `version_float`, `mp_os`, `mp_country_code`
- Game State: `end_of_content`, `mode_status`
- Purchases: `price_usd`, `price_original`, `currency`, `purchase_id`, `google_order_number`
- Ads: `revenue`
- Economy: `delta_credits`, `bubble_cost`

### 4. Known Metrics (7 records)
Common KPIs with example SQL queries:

1. **daily_revenue** - Total revenue (IAP + ads) per day
2. **daily_active_users** - DAU excluding test countries and fraudsters
3. **arpdau** - Average revenue per daily active user
4. **installs** - Daily install count
5. **d1_retention_rate** - Day 1 retention by cohort
6. **d7_retention_rate** - Day 7 retention by cohort
7. **end_of_content_users_daily** - Users reaching EOC per day

## Key Insights from Documentation

### Table Selection Priority
1. **agg_player_daily** - For daily metrics (revenue, DAU, purchases) - FASTEST
2. **dim_player** - For lifetime metrics (LTV, retention, install cohorts)
3. **agg_player_chapter_daily** - For chapter-specific analysis
4. **vmp_master_event_normalized** - ONLY when:
   - Aggregated tables lack needed data
   - Need current date data
   - Need event sequences/funnels
   - Need detailed debugging

### Critical Filters (ALWAYS Apply)
```sql
WHERE date >= CURRENT_DATE() - X  -- Partition filter
AND mp_country_code NOT IN ('UA', 'IL', 'AM')  -- Exclude test countries
AND distinct_id NOT IN (SELECT distinct_id FROM potential_fraudsters)  -- or fraudsters for revenue
AND distinct_id NOT IN (SELECT distinct_id FROM state_loss_temp_users)
AND CAST(price_original AS FLOAT64) != 0.01  -- For purchases only
```

### Important Version-Specific Logic
- **v0.368+ (2025-10-09)**: Order by `res_timestamp, counter_per_session_game_side`
- **Purchase deduplication**: Group by `purchase_id` and date, use MAX(price_usd)
- **Retention periods supported**: 0, 1, 3, 7, 14, 21, 30, 45, 60, 75, 90, 120, 150, 180, 210, 240, 270, 300, 330, 360, 540, 720, 900, 1080 days

## What Was NOT Extracted (Too Detailed for Initial Load)

The following information exists in the documentation but was not included in this initial extraction:
- Specific event parameter details (e.g., `generated_items` JSON structure)
- Complex segment parsing logic (server_segments, firebase_segments)
- Specific game feature event schemas (Frenzy, Missions, etc.)
- Detailed reconciliation query examples
- Advanced funnel analysis patterns
- Custom JavaScript functions for game_board parsing

**Recommendation**: These can be added as additional guardrails or metrics based on actual query patterns observed.

## Next Steps

1. **✅ COMPLETED**: Populate BigQuery metadata tables
2. **⏭️ NEXT**: Refresh Pinecone vector database with new data
3. **⏭️ NEXT**: Test query generation with real user questions
4. **Future**: Add more detailed column descriptions and event-specific knowledge

## Files Created

1. `populate_from_notion.sql` - SQL script with all INSERT statements
2. `NOTION_EXTRACTION_SUMMARY.md` - This summary document

## Validation

Run this query to verify data loaded correctly:
```sql
SELECT 'guardrails' AS table_name, COUNT(*) AS record_count 
FROM `yotam-395120.peerplay.query_gen_guardrails`
UNION ALL
SELECT 'tables', COUNT(*) FROM `yotam-395120.peerplay.query_gen_tables`
UNION ALL
SELECT 'columns', COUNT(*) FROM `yotam-395120.peerplay.query_gen_columns`
UNION ALL
SELECT 'metrics', COUNT(*) FROM `yotam-395120.peerplay.query_gen_known_metrics`
ORDER BY table_name;
```

Expected results:
- guardrails: 14
- tables: 24
- columns: 62
- metrics: 7

**Total: 107 records** of organizational knowledge extracted and structured!
