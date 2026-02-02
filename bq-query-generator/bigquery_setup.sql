-- =============================================================================
-- BigQuery Metadata Tables for Query Generator
-- Project: yotam-395120.peerplay
-- =============================================================================

-- =============================================================================
-- 1. GUARDRAILS TABLE
-- Stores policies, instructions, and hints for query generation
-- =============================================================================
CREATE TABLE IF NOT EXISTS `yotam-395120.peerplay.query_gen_guardrails` (
  guardrails_name STRING NOT NULL OPTIONS(description="Short name/identifier for the guardrail"),
  guardrails_description STRING NOT NULL OPTIONS(description="Detailed explanation of the rule or instruction"),
  guardrails_tags ARRAY<STRING> OPTIONS(description="Tags for categorization and semantic search"),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
OPTIONS(
  description="Query generation guardrails - policies and instructions the system must follow"
);

-- =============================================================================
-- 2. TABLES METADATA
-- Describes all tables the system should be aware of
-- =============================================================================
CREATE TABLE IF NOT EXISTS `yotam-395120.peerplay.query_gen_tables` (
  table_name STRING NOT NULL OPTIONS(description="Full table name (project.dataset.table)"),
  table_description STRING NOT NULL OPTIONS(description="What this table contains and when to use it"),
  table_partition STRING OPTIONS(description="Partition column name (e.g., 'date', 'event_date')"),
  table_clusters_list ARRAY<STRING> OPTIONS(description="List of clustering columns in order"),
  usage_description STRING OPTIONS(description="Guidance on when and how to use this table"),
  table_tags ARRAY<STRING> OPTIONS(description="Tags for categorization (e.g., 'server', 'client', 'events')"),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
OPTIONS(
  description="Metadata about all tables available for querying"
);

-- =============================================================================
-- 3. COLUMNS METADATA
-- Describes all columns across all tables
-- =============================================================================
CREATE TABLE IF NOT EXISTS `yotam-395120.peerplay.query_gen_columns` (
  column_name STRING NOT NULL OPTIONS(description="Name of the column"),
  related_table STRING NOT NULL OPTIONS(description="Full table name this column belongs to"),
  column_type STRING NOT NULL OPTIONS(description="Data type (STRING, INTEGER, TIMESTAMP, etc.)"),
  is_partition BOOL DEFAULT FALSE OPTIONS(description="Whether this is the partition column"),
  is_cluster BOOL DEFAULT FALSE OPTIONS(description="Whether this is a clustering column"),
  is_primary_key BOOL DEFAULT FALSE OPTIONS(description="Whether this is a primary key"),
  column_description STRING OPTIONS(description="What this column contains and represents"),
  column_tags ARRAY<STRING> OPTIONS(description="Tags for semantic search and categorization"),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
OPTIONS(
  description="Metadata about columns in all tables"
);

-- =============================================================================
-- 4. KNOWN METRICS
-- Organizational metrics with calculation examples
-- =============================================================================
CREATE TABLE IF NOT EXISTS `yotam-395120.peerplay.query_gen_known_metrics` (
  metric_name STRING NOT NULL OPTIONS(description="Name of the metric"),
  metric_description STRING NOT NULL OPTIONS(description="What this metric measures"),
  metric_query_example STRING NOT NULL OPTIONS(description="Example SQL query showing how to calculate this metric"),
  metric_tags ARRAY<STRING> OPTIONS(description="Tags for categorization (e.g., 'revenue', 'engagement', 'retention')"),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
OPTIONS(
  description="Known organizational metrics with calculation examples"
);

-- =============================================================================
-- SAMPLE DATA - Insert examples
-- =============================================================================

-- Sample guardrail
INSERT INTO `yotam-395120.peerplay.query_gen_guardrails` 
  (guardrails_name, guardrails_description, guardrails_tags)
VALUES (
  'partition_filtering_mandatory',
  'Any query on partitioned tables MUST contain a filter on the partition column in the WHERE clause. This is critical for performance and cost optimization. Partitioned tables should always have date range filters.',
  ['partition', 'performance', 'mandatory', 'cost-optimization']
);

-- Sample table metadata
INSERT INTO `yotam-395120.peerplay.query_gen_tables`
  (table_name, table_description, table_partition, table_clusters_list, usage_description, table_tags)
VALUES (
  'yotam-395120.peerplay.verification_service_events',
  'Raw events at the user level from our game backend service. Contains data about events from specific services in our backend. The endpoint_name column identifies the specific service. The distinct_id matches the distinct_id from the main client events table.',
  'date',
  ['endpoint_name', 'distinct_id'],
  'Use this table when analyzing backend service events or correlating server-side events with client events using distinct_id. Good for backend performance analysis and service-specific metrics.',
  ['server', 'backend', 'service-events', 'verification', 'raw']
);

-- Sample metric
INSERT INTO `yotam-395120.peerplay.query_gen_known_metrics`
  (metric_name, metric_description, metric_query_example, metric_tags)
VALUES 
  ('total_revenue', 
   'The total revenue (purchase + ads) for a specific date. This is our primary monetization KPI.',
   'SELECT date, SUM(total_revenue) AS total_revenue FROM `yotam-395120.peerplay.agg_player_daily` WHERE date = CURRENT_DATE() - 1 GROUP BY date ORDER BY date DESC',
   ['revenue', 'kpi', 'daily', 'monetization', 'primary-metric']
  ),
  ('purchase_revenue',
   'Revenue from in-app purchases only. Does not include ad revenue.',
   'SELECT date, SUM(total_purchase_revenue) AS purchase_revenue FROM `yotam-395120.peerplay.agg_player_daily` WHERE date >= CURRENT_DATE() - 30 GROUP BY date ORDER BY date DESC',
   ['revenue', 'iap', 'purchases', 'monetization']
  );
