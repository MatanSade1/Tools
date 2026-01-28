# BigQuery Tables Schema Documentation

This document describes all analytical tables in our BigQuery dataset, their schemas, granularity, and usage guidelines.

---

## Table: events_raw

### Description
Raw event stream from our mobile and web applications. Contains all user interactions and system events with full property payloads.

### Schema

| Column Name | Data Type | Description | Example |
|------------|-----------|-------------|---------|
| event_timestamp | TIMESTAMP | When the event occurred (UTC) | 2024-01-15 14:30:00 UTC |
| event_date | DATE | Partition column - event date | 2024-01-15 |
| event_id | STRING | Unique event identifier | evt_abc123xyz |
| event_name | STRING | Name of the event | user_signup |
| user_id | STRING | Unique user identifier | usr_12345 |
| distinct_id | STRING | Anonymous or identified user ID | anon_xyz789 |
| platform | STRING | Platform where event occurred | ios, android, web |
| app_version | STRING | Application version | 2.5.1 |
| properties | JSON | Event properties payload | {"screen": "home", "button": "cta"} |
| inserted_at | TIMESTAMP | When record was inserted to BQ | 2024-01-15 14:31:00 UTC |

### Granularity
- **One row per event** - This is the most granular level of data
- Event-level data with no aggregation
- Includes duplicate events if user triggers same action multiple times

### Partitioning & Clustering
- **Partitioned by:** `event_date` (daily partitions)
- **Clustered by:** `event_name`, `user_id`, `platform`
- **Retention:** 400 days

### When to Use This Table
- When you need raw event-level data
- For detailed user journey analysis
- When analyzing specific event properties
- For event-level funnel analysis
- When you need exact timestamps

### When NOT to Use This Table
- For aggregated metrics (use events_daily_summary instead)
- For user-level attributes (use users_dim instead)
- For high-level trends (use events_hourly_summary)

### Performance Tips
- **Always filter by event_date** (partition column) to reduce scan costs
- Filter by event_name early for better clustering performance
- Avoid SELECT * - specify only needed columns
- JSON property extraction can be expensive - consider materialized columns for frequent properties

### Example Queries

#### Get all signup events for last 7 days
```sql
SELECT 
  event_timestamp,
  user_id,
  platform,
  JSON_EXTRACT_SCALAR(properties, '$.signup_method') AS signup_method
FROM `project.dataset.events_raw`
WHERE event_date >= CURRENT_DATE() - 7
  AND event_name = 'user_signup'
ORDER BY event_timestamp DESC
```

#### Count events by platform for a specific day
```sql
SELECT 
  platform,
  COUNT(*) AS event_count
FROM `project.dataset.events_raw`
WHERE event_date = '2024-01-15'
  AND event_name = 'app_opened'
GROUP BY platform
```

---

## Table: events_daily_summary

### Description
Pre-aggregated daily event counts by user and event type. Use this for faster queries when you don't need event-level granularity.

### Schema

| Column Name | Data Type | Description | Example |
|------------|-----------|-------------|---------|
| event_date | DATE | Day of events (partition column) | 2024-01-15 |
| user_id | STRING | Unique user identifier | usr_12345 |
| event_name | STRING | Name of the event | app_opened |
| platform | STRING | Primary platform for the day | ios |
| event_count | INTEGER | Number of events that day | 15 |
| first_event_timestamp | TIMESTAMP | First event of the day | 2024-01-15 08:00:00 UTC |
| last_event_timestamp | TIMESTAMP | Last event of the day | 2024-01-15 22:30:00 UTC |
| unique_sessions | INTEGER | Number of unique sessions | 3 |

### Granularity
- **One row per user, per event name, per day**
- Aggregated at daily level
- Multiple platforms consolidated to primary platform

### Partitioning & Clustering
- **Partitioned by:** `event_date`
- **Clustered by:** `event_name`, `user_id`
- **Retention:** 730 days (2 years)

### When to Use This Table
- For daily aggregated metrics (DAU, event counts)
- When analyzing trends over time
- For user activity summaries
- When exact timestamps aren't needed
- For cohort analysis at daily granularity

### When NOT to Use This Table
- When you need event-level details
- For intraday analysis (hourly patterns)
- When event properties are needed
- For real-time monitoring (has 4-hour delay)

### Update Frequency
- Updated every 4 hours
- Based on events_raw table
- Last 3 days are recalculated to handle late-arriving events

### Example Queries

#### Calculate Daily Active Users (DAU) for last 30 days
```sql
SELECT 
  event_date,
  COUNT(DISTINCT user_id) AS dau
FROM `project.dataset.events_daily_summary`
WHERE event_date >= CURRENT_DATE() - 30
  AND event_name IN ('app_opened', 'session_start')
GROUP BY event_date
ORDER BY event_date
```

#### Find power users (users with >100 events/day)
```sql
SELECT 
  user_id,
  event_date,
  SUM(event_count) AS total_events
FROM `project.dataset.events_daily_summary`
WHERE event_date = CURRENT_DATE() - 1
GROUP BY user_id, event_date
HAVING total_events > 100
ORDER BY total_events DESC
```

---

## Table: users_dim

### Description
Dimensional table containing user attributes and profile information. Updated daily with latest user state.

### Schema

| Column Name | Data Type | Description | Example |
|------------|-----------|-------------|---------|
| user_id | STRING | Unique user identifier (primary key) | usr_12345 |
| created_at | TIMESTAMP | User signup timestamp | 2023-06-15 10:30:00 UTC |
| signup_date | DATE | Signup date (for easy filtering) | 2023-06-15 |
| email | STRING | User email (hashed for privacy) | hash_abc123 |
| country | STRING | User country (ISO code) | US |
| subscription_tier | STRING | Current subscription level | premium, free, trial |
| is_active | BOOLEAN | User is currently active | true |
| last_active_date | DATE | Most recent activity date | 2024-01-15 |
| lifetime_events | INTEGER | Total events all-time | 1543 |
| lifetime_revenue_usd | FLOAT | Total revenue from user | 99.99 |

### Granularity
- **One row per user** - SCD Type 1 (current state only)
- Slowly changing dimension - updated daily
- No historical state tracking (current values only)

### Clustering
- **Clustered by:** `signup_date`, `country`, `subscription_tier`
- **No partitioning** (dimension table, not time-series)

### When to Use This Table
- For user attribute filtering
- To join with events for user context
- For cohort definition (e.g., users by signup month)
- For subscription or tier-based analysis
- For geographic segmentation

### When NOT to Use This Table
- For historical user states (use users_history instead)
- For real-time user attributes (4-hour delay)
- For event-specific user data

### Example Queries

#### Get user details for cohort analysis
```sql
SELECT 
  DATE_TRUNC(signup_date, MONTH) AS signup_month,
  subscription_tier,
  COUNT(*) AS user_count,
  AVG(lifetime_revenue_usd) AS avg_ltv
FROM `project.dataset.users_dim`
WHERE signup_date >= '2024-01-01'
  AND is_active = true
GROUP BY signup_month, subscription_tier
ORDER BY signup_month, subscription_tier
```

#### Join events with user attributes
```sql
SELECT 
  e.event_date,
  u.subscription_tier,
  u.country,
  COUNT(DISTINCT e.user_id) AS dau
FROM `project.dataset.events_daily_summary` e
JOIN `project.dataset.users_dim` u
  ON e.user_id = u.user_id
WHERE e.event_date >= CURRENT_DATE() - 7
  AND e.event_name = 'app_opened'
GROUP BY e.event_date, u.subscription_tier, u.country
```

---

## Table Relationships

```
events_raw (1:N)
    └─> Aggregated into events_daily_summary
    
events_raw.user_id (N:1)
    └─> users_dim.user_id

events_daily_summary.user_id (N:1)
    └─> users_dim.user_id
```

## General Query Best Practices

1. **Always filter partitioned tables by date** - Use `event_date` or `signup_date` filters
2. **Use clustering columns in WHERE clauses** - Improves query performance
3. **Prefer summary tables for aggregations** - Use `events_daily_summary` over `events_raw` when possible
4. **Limit lookback windows** - Don't query unlimited date ranges
5. **Be specific with columns** - Avoid `SELECT *`
6. **Use APPROX functions for large datasets** - `APPROX_COUNT_DISTINCT` instead of `COUNT(DISTINCT)`

## Cost Optimization

- **events_raw**: ~50 GB/day, query with date filters to avoid full scans
- **events_daily_summary**: ~5 GB total, much cheaper for trend analysis
- **users_dim**: ~2 GB total, small enough for full scans

Expected query costs:
- Raw events (7 days filtered): ~350 GB scanned = $1.75
- Daily summary (30 days): ~5 GB scanned = $0.025
- User dimension (full table): ~2 GB scanned = $0.01
