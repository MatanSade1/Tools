# BigQuery Integration Guide

## 🎉 What's Been Set Up

Your Query Generator now pulls organizational knowledge from **BigQuery metadata tables** instead of markdown files!

### ✅ Completed:

1. **4 BigQuery tables created** in `yotam-395120.peerplay`:
   - `query_gen_guardrails` - Query rules and policies
   - `query_gen_tables` - Table metadata  
   - `query_gen_columns` - Column definitions
   - `query_gen_known_metrics` - Metric calculations

2. **Sample data inserted**:
   - 1 guardrail (partition filtering)
   - 1 table (verification_service_events)
   - 2 metrics (total_revenue, purchase_revenue)

3. **Vector database updated**:
   - 4 documents embedded in Pinecone
   - Ready for semantic search

---

## 📊 BigQuery Tables Schema

### 1. query_gen_guardrails
**Purpose:** Store mandatory rules and policies

| Column | Type | Description |
|--------|------|-------------|
| guardrails_name | STRING | Short identifier |
| guardrails_description | STRING | Detailed rule explanation |
| guardrails_tags | ARRAY<STRING> | Tags for search |
| created_at | TIMESTAMP | When added |
| updated_at | TIMESTAMP | Last modified |

**Example:**
```sql
INSERT INTO `yotam-395120.peerplay.query_gen_guardrails` 
  (guardrails_name, guardrails_description, guardrails_tags)
VALUES (
  'partition_filtering_mandatory',
  'Always filter by partition column in WHERE clause for performance',
  ['partition', 'performance', 'mandatory']
);
```

### 2. query_gen_tables
**Purpose:** Describe available tables

| Column | Type | Description |
|--------|------|-------------|
| table_name | STRING | Full table path |
| table_description | STRING | What table contains |
| table_partition | STRING | Partition column name |
| table_clusters_list | ARRAY<STRING> | Clustering columns |
| usage_description | STRING | When to use |
| table_tags | ARRAY<STRING> | Tags for search |

**Example:**
```sql
INSERT INTO `yotam-395120.peerplay.query_gen_tables`
  (table_name, table_description, table_partition, table_clusters_list, usage_description, table_tags)
VALUES (
  'yotam-395120.peerplay.events',
  'Raw user events from mobile and web apps. One row per event.',
  'event_date',
  ['event_name', 'user_id'],
  'Use for event-level analysis. Always filter by event_date partition.',
  ['events', 'raw', 'client']
);
```

### 3. query_gen_columns
**Purpose:** Column metadata for all tables

| Column | Type | Description |
|--------|------|-------------|
| column_name | STRING | Column name |
| related_table | STRING | Which table |
| column_type | STRING | Data type |
| is_partition | BOOL | Is partition column |
| is_cluster | BOOL | Is clustering column |
| is_primary_key | BOOL | Is primary key |
| column_description | STRING | What it contains |
| column_tags | ARRAY<STRING> | Tags for search |

**Example:**
```sql
INSERT INTO `yotam-395120.peerplay.query_gen_columns`
  (column_name, related_table, column_type, is_partition, is_cluster, column_description, column_tags)
VALUES 
  ('event_date', 'yotam-395120.peerplay.events', 'DATE', TRUE, FALSE, 'Event date - MUST be in WHERE clause', ['partition', 'date', 'mandatory']),
  ('event_name', 'yotam-395120.peerplay.events', 'STRING', FALSE, TRUE, 'Type of event (e.g., app_opened, purchase_completed)', ['event', 'clustering']);
```

### 4. query_gen_known_metrics
**Purpose:** How to calculate organizational metrics

| Column | Type | Description |
|--------|------|-------------|
| metric_name | STRING | Metric name |
| metric_description | STRING | What it measures |
| metric_query_example | STRING | SQL showing how to calculate |
| metric_tags | ARRAY<STRING> | Tags for search |

**Example:**
```sql
INSERT INTO `yotam-395120.peerplay.query_gen_known_metrics`
  (metric_name, metric_description, metric_query_example, metric_tags)
VALUES (
  'daily_active_users',
  'Unique users who opened the app each day',
  'SELECT event_date, COUNT(DISTINCT user_id) AS dau FROM `yotam-395120.peerplay.events` WHERE event_date >= CURRENT_DATE() - 7 AND event_name = ''app_opened'' GROUP BY event_date ORDER BY event_date',
  ['engagement', 'dau', 'users', 'kpi']
);
```

---

## 🚀 How to Use

### 1. Add Your Organizational Knowledge

Connect to BigQuery and insert your data:

```sql
-- Add a guardrail
INSERT INTO `yotam-395120.peerplay.query_gen_guardrails` 
  (guardrails_name, guardrails_description, guardrails_tags)
VALUES (
  'use_aggregated_tables_first',
  'When possible, use pre-aggregated tables (like agg_player_daily) instead of raw events for better performance',
  ['performance', 'best-practice', 'aggregation']
);

-- Add a table
INSERT INTO `yotam-395120.peerplay.query_gen_tables`
  (table_name, table_description, table_partition, table_clusters_list, usage_description, table_tags)
VALUES (
  'yotam-395120.peerplay.agg_player_daily',
  'Daily aggregated player metrics including revenue, events count, and session data',
  'date',
  ['player_id'],
  'Use for daily player metrics and revenue analysis. Much faster than raw events table.',
  ['aggregated', 'daily', 'revenue', 'players']
);

-- Add columns for that table
INSERT INTO `yotam-395120.peerplay.query_gen_columns`
  (column_name, related_table, column_type, is_partition, column_description, column_tags)
VALUES 
  ('date', 'yotam-395120.peerplay.agg_player_daily', 'DATE', TRUE, 'Date of aggregated data - always filter by this', ['partition', 'date']),
  ('player_id', 'yotam-395120.peerplay.agg_player_daily', 'STRING', FALSE, 'Unique player identifier', ['player', 'user_id']),
  ('total_revenue', 'yotam-395120.peerplay.agg_player_daily', 'FLOAT', FALSE, 'Sum of purchase and ad revenue for the day', ['revenue', 'monetization']);
```

### 2. Refresh the Vector Database

After adding data to BigQuery:

```bash
cd /Users/matansade/Tools/bq-query-generator
source ../venv/bin/activate

# Reload from BigQuery and update Pinecone
echo "yes" | python setup_vectordb_from_bigquery.py --reset
```

This will:
- ✅ Query BigQuery for all metadata
- ✅ Generate embeddings
- ✅ Update Pinecone with new knowledge

### 3. Test Queries

```bash
# Test with your new data
python main.py query "Show me total revenue per day for last 7 days"

# Verbose mode to see what context was retrieved
python main.py query "Calculate DAU" --verbose

# Interactive mode
python main.py interactive
```

---

## 💡 Best Practices

### Adding Tables

When you add a new table, include:
1. **Full table name** (project.dataset.table)
2. **Clear description** of what it contains
3. **Partition column** (critical for performance)
4. **Clustering columns** in order
5. **Usage guidance** - when to use vs other tables
6. **Relevant tags** for semantic search

### Adding Metrics

Include:
1. **Metric name** (what analysts call it)
2. **Business definition** (what it means)
3. **Complete SQL example** showing calculation
4. **Tags** for discoverability

### Adding Guardrails

Document:
1. **Rule name** (short identifier)
2. **Detailed explanation** with WHY
3. **Tags** including severity (mandatory, recommended, etc.)

### Column Descriptions

Be specific:
- Not just "user ID" → "Unique identifier for authenticated users. NULL for anonymous sessions."
- Include join keys, relationships, special handling

---

## 🔄 Workflow

### Daily Operations:
```sql
-- Team member adds new table
INSERT INTO query_gen_tables VALUES (...);
INSERT INTO query_gen_columns VALUES (...);

-- Update vector DB (once per day or after bulk changes)
python setup_vectordb_from_bigquery.py --reset
```

### Updating Existing:
```sql
-- Update table description
UPDATE `yotam-395120.peerplay.query_gen_tables`
SET table_description = 'Updated description...',
    updated_at = CURRENT_TIMESTAMP()
WHERE table_name = 'yotam-395120.peerplay.events';

-- Then refresh vectors
python setup_vectordb_from_bigquery.py --reset
```

---

## 📈 Scaling Tips

### For Large Organizations:

1. **Batch Updates**: Add multiple items, then refresh once
2. **Team Ownership**: Different teams manage their table/metric metadata
3. **Review Process**: Use separate staging tables before production
4. **Version Control**: Track changes via created_at/updated_at timestamps
5. **Documentation**: Keep tags consistent for better semantic search

### Auto-Population Script:

For columns, you can auto-populate from INFORMATION_SCHEMA:

```sql
-- Auto-add columns when table is added
INSERT INTO `yotam-395120.peerplay.query_gen_columns`
  (column_name, related_table, column_type, is_partition, is_cluster)
SELECT 
  column_name,
  'yotam-395120.peerplay.YOUR_TABLE' AS related_table,
  data_type AS column_type,
  is_partitioning_column = 'YES' AS is_partition,
  clustering_ordinal_position IS NOT NULL AS is_cluster
FROM `yotam-395120.peerplay.INFORMATION_SCHEMA.COLUMNS`
WHERE table_name = 'YOUR_TABLE';

-- Then manually add descriptions and tags
UPDATE `yotam-395120.peerplay.query_gen_columns`
SET column_description = 'Your description',
    column_tags = ['tag1', 'tag2']
WHERE column_name = 'your_column' 
  AND related_table = 'yotam-395120.peerplay.YOUR_TABLE';
```

---

## 🎯 Example: Full Table Setup

Here's a complete example adding the `end_of_content` event you asked about:

```sql
-- 1. Add the events table if not already added
INSERT INTO `yotam-395120.peerplay.query_gen_tables`
  (table_name, table_description, table_partition, table_clusters_list, usage_description, table_tags)
VALUES (
  'yotam-395120.peerplay.client_events',
  'Raw events from mobile client. Includes all user interactions and system events.',
  'event_date',
  ['event_name', 'distinct_id'],
  'Use for detailed event analysis. Always filter by event_date. For aggregated metrics use agg_player_daily instead.',
  ['client', 'events', 'raw', 'mobile']
);

-- 2. Add key columns
INSERT INTO `yotam-395120.peerplay.query_gen_columns`
  (column_name, related_table, column_type, is_partition, is_cluster, column_description, column_tags)
VALUES 
  ('event_date', 'yotam-395120.peerplay.client_events', 'DATE', TRUE, FALSE, 'Date of event - MUST be in WHERE clause for performance', ['partition', 'date', 'mandatory']),
  ('event_name', 'yotam-395120.peerplay.client_events', 'STRING', FALSE, TRUE, 'Type of event. Examples: end_of_content, app_opened, purchase_completed', ['event', 'clustering']),
  ('distinct_id', 'yotam-395120.peerplay.client_events', 'STRING', FALSE, TRUE, 'User identifier. Can be anonymous or authenticated user_id', ['user', 'identifier', 'clustering']);

-- 3. Add metric for end_of_content
INSERT INTO `yotam-395120.peerplay.query_gen_known_metrics`
  (metric_name, metric_description, metric_query_example, metric_tags)
VALUES (
  'users_reaching_end_of_content',
  'Number of unique users who reached the end of content each day',
  'SELECT event_date, COUNT(DISTINCT distinct_id) AS users FROM `yotam-395120.peerplay.client_events` WHERE event_date >= CURRENT_DATE() - 7 AND event_name = ''end_of_content'' GROUP BY event_date ORDER BY event_date DESC',
  ['engagement', 'content', 'completion', 'users']
);

-- 4. Refresh vector DB
-- Run: echo "yes" | python setup_vectordb_from_bigquery.py --reset
```

Now when you ask: "Give me users who reached end of content", the RAG system will:
1. Find your metric definition
2. Find the table metadata
3. Find the column information
4. Generate the correct query using your actual table names!

---

## ✅ Current Status

**Tables Created:** ✓  
**Sample Data Inserted:** ✓  
**Vector DB Connected:** ✓  
**BigQuery Loader Working:** ✓  
**Setup Script Ready:** ✓  

**Current Content:**
- 1 guardrail
- 1 table (verification_service_events)
- 0 columns  
- 2 metrics (total_revenue, purchase_revenue)
- **4 documents embedded** in Pinecone

**Next Steps:**
1. Add YOUR actual tables, columns, and metrics to BigQuery
2. Run `setup_vectordb_from_bigquery.py --reset`
3. Start generating queries with your real schema!

---

## 🆘 Troubleshooting

**Q: Changes not reflected in queries?**  
A: Run `python setup_vectordb_from_bigquery.py --reset` to refresh embeddings

**Q: BigQuery authentication error?**  
A: Ensure `gcloud auth application-default login` is configured

**Q: No documents found?**  
A: Check that you've inserted data into the BigQuery tables

**Q: Want to see what's embedded?**  
A: Run `python src/bigquery_loader.py` to see current content

---

**Your Query Generator is now powered by BigQuery metadata tables! 🚀**

Add your schema, refresh vectors, and start generating queries tailored to your organization!
