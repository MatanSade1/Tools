# Query Usage Guardrails and Best Practices

This document outlines critical rules and best practices for writing BigQuery queries in our organization. Following these guardrails ensures optimal query performance, cost efficiency, and data accuracy.

---

## Critical Rules (ALWAYS Follow)

### 1. Partition Filtering (MANDATORY)

**RULE:** Always filter by partition columns in WHERE clauses.

**Why:** Partitioning reduces the amount of data scanned, dramatically lowering costs and improving performance.

**Tables and their partition columns:**
- `events_raw` → `event_date`
- `events_daily_summary` → `event_date`
- `users_dim` → Not partitioned (dimension table)

**Examples:**

✅ **CORRECT:**
```sql
SELECT * 
FROM `project.dataset.events_raw`
WHERE event_date >= '2024-01-01'
  AND event_date <= '2024-01-31'
  AND event_name = 'user_signup'
```

❌ **WRONG:**
```sql
-- Missing partition filter - will scan entire table!
SELECT * 
FROM `project.dataset.events_raw`
WHERE event_name = 'user_signup'
```

**Best practices:**
- Use explicit date ranges: `event_date >= X AND event_date <= Y`
- Or use relative dates: `event_date >= CURRENT_DATE() - 7`
- Avoid open-ended ranges without upper bounds
- Date ranges should typically be ≤ 90 days unless specifically needed

---

### 2. Clustering Column Order

**RULE:** Filter and sort by clustering columns in the order they're defined.

**Why:** BigQuery organizes data based on clustering columns. Using them in order maximizes data pruning.

**Clustering definitions:**
- `events_raw`: Clustered by `event_name`, `user_id`, `platform`
- `events_daily_summary`: Clustered by `event_name`, `user_id`
- `users_dim`: Clustered by `signup_date`, `country`, `subscription_tier`

**Examples:**

✅ **CORRECT (follows clustering order):**
```sql
SELECT *
FROM `project.dataset.events_raw`
WHERE event_date >= CURRENT_DATE() - 7
  AND event_name = 'app_opened'          -- 1st cluster column
  AND user_id = 'usr_12345'              -- 2nd cluster column
  AND platform = 'ios'                   -- 3rd cluster column
```

⚠️ **SUBOPTIMAL (out of order, but still works):**
```sql
SELECT *
FROM `project.dataset.events_raw`
WHERE event_date >= CURRENT_DATE() - 7
  AND platform = 'ios'                   -- 3rd cluster column first
  AND event_name = 'app_opened'          -- 1st cluster column last
```

---

### 3. Column Selection

**RULE:** Never use `SELECT *` in production queries. Always specify needed columns.

**Why:** 
- Reduces data scanned (lower costs)
- Faster query execution
- More maintainable code
- Avoids pulling unnecessary JSON fields

**Examples:**

✅ **CORRECT:**
```sql
SELECT 
  event_date,
  user_id,
  event_name,
  JSON_EXTRACT_SCALAR(properties, '$.screen_name') AS screen_name
FROM `project.dataset.events_raw`
WHERE event_date >= CURRENT_DATE() - 7
```

❌ **WRONG:**
```sql
SELECT * 
FROM `project.dataset.events_raw`
WHERE event_date >= CURRENT_DATE() - 7
```

---

### 4. JSON Property Extraction

**RULE:** Extract JSON properties with caution and limit their use.

**Why:** JSON parsing is computationally expensive.

**Best practices:**
- Use `JSON_EXTRACT_SCALAR()` for simple string values
- Use `JSON_EXTRACT()` for complex objects
- Filter after extraction when possible
- Consider creating materialized columns for frequently accessed properties

**Examples:**

✅ **CORRECT:**
```sql
SELECT 
  event_date,
  user_id,
  JSON_EXTRACT_SCALAR(properties, '$.screen_name') AS screen_name,
  JSON_EXTRACT_SCALAR(properties, '$.button_id') AS button_id
FROM `project.dataset.events_raw`
WHERE event_date >= CURRENT_DATE() - 7
  AND event_name = 'button_click'
```

⚠️ **EXPENSIVE (but sometimes necessary):**
```sql
-- JSON extraction in WHERE clause - scans more data
SELECT *
FROM `project.dataset.events_raw`
WHERE event_date >= CURRENT_DATE() - 7
  AND JSON_EXTRACT_SCALAR(properties, '$.error_code') = '500'
```

---

### 5. Aggregation Strategy

**RULE:** Use pre-aggregated tables when possible. Avoid aggregating raw events for routine queries.

**Why:** Pre-aggregated tables are faster and cheaper.

**Table selection guide:**
- **Need event-level details?** → Use `events_raw`
- **Need daily metrics?** → Use `events_daily_summary`
- **Need user attributes?** → Use `users_dim`

**Examples:**

✅ **CORRECT (uses pre-aggregated table):**
```sql
-- Fast and cheap
SELECT 
  event_date,
  COUNT(DISTINCT user_id) AS dau
FROM `project.dataset.events_daily_summary`
WHERE event_date >= CURRENT_DATE() - 30
  AND event_name = 'app_opened'
GROUP BY event_date
```

❌ **INEFFICIENT (aggregates raw events):**
```sql
-- Slower and more expensive
SELECT 
  event_date,
  COUNT(DISTINCT user_id) AS dau
FROM `project.dataset.events_raw`
WHERE event_date >= CURRENT_DATE() - 30
  AND event_name = 'app_opened'
GROUP BY event_date
```

---

## Performance Guidelines

### Expected Query Latency

| Query Type | Expected Latency | Example |
|-----------|------------------|---------|
| Simple filtered query on daily summary | 1-3 seconds | DAU for last 30 days |
| Raw events with partition filter | 5-10 seconds | Last 7 days of signups |
| Raw events with JSON extraction | 10-20 seconds | Button clicks with properties |
| Complex joins across 3+ tables | 20-60 seconds | User cohort funnel analysis |

If queries exceed these times, review:
1. Are partition filters applied?
2. Are clustering columns used?
3. Is column selection specific?
4. Can you use a pre-aggregated table?

---

### Query Cost Guidelines

**BigQuery pricing:** $5 per TB scanned (on-demand)

**Typical scan sizes:**
- `events_raw` (1 day): ~50 GB
- `events_raw` (7 days): ~350 GB → $1.75
- `events_raw` (30 days): ~1.5 TB → $7.50
- `events_daily_summary` (30 days): ~5 GB → $0.025
- `users_dim` (full scan): ~2 GB → $0.01

**Cost optimization tips:**
1. Use `events_daily_summary` instead of `events_raw` when possible (100x cheaper!)
2. Limit date ranges to what's needed
3. Use LIMIT for exploratory queries
4. Use `APPROX_COUNT_DISTINCT` for approximate counting (faster, cheaper)

---

### APPROX Functions for Large Datasets

**RULE:** Use approximation functions for distinct counts on large datasets when exact precision isn't critical.

✅ **GOOD for exploration and dashboards:**
```sql
SELECT 
  event_date,
  APPROX_COUNT_DISTINCT(user_id) AS approx_dau
FROM `project.dataset.events_raw`
WHERE event_date >= CURRENT_DATE() - 90
GROUP BY event_date
```

✅ **GOOD for exact counts when needed:**
```sql
SELECT 
  event_date,
  COUNT(DISTINCT user_id) AS exact_dau
FROM `project.dataset.events_daily_summary`
WHERE event_date >= CURRENT_DATE() - 30
GROUP BY event_date
```

---

## Special Instructions

### 1. Date Handling

**Always use consistent date logic:**

```sql
-- Relative dates (PREFERRED for recurring queries)
WHERE event_date >= CURRENT_DATE() - 7

-- Explicit dates (PREFERRED for ad-hoc analysis)
WHERE event_date >= '2024-01-01' AND event_date <= '2024-01-31'

-- Date truncation for grouping
DATE_TRUNC(event_date, WEEK) AS week
DATE_TRUNC(event_date, MONTH) AS month
```

### 2. User Deduplication

**When joining events with users:**

```sql
-- CORRECT: Join on user_id
SELECT 
  u.subscription_tier,
  COUNT(DISTINCT e.user_id) AS dau
FROM `project.dataset.events_daily_summary` e
JOIN `project.dataset.users_dim` u
  ON e.user_id = u.user_id
WHERE e.event_date >= CURRENT_DATE() - 7
GROUP BY u.subscription_tier
```

### 3. Handling NULL Values

**Be explicit about NULL handling:**

```sql
-- Use COALESCE for default values
SELECT 
  user_id,
  COALESCE(platform, 'unknown') AS platform,
  COUNT(*) AS event_count
FROM `project.dataset.events_raw`
WHERE event_date >= CURRENT_DATE() - 7
GROUP BY user_id, platform
```

---

## Query Template Patterns

### Pattern 1: DAU/MAU Calculation
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

### Pattern 2: Event Funnel
```sql
WITH step1 AS (
  SELECT DISTINCT user_id
  FROM `project.dataset.events_raw`
  WHERE event_date >= CURRENT_DATE() - 7
    AND event_name = 'signup_started'
),
step2 AS (
  SELECT DISTINCT user_id
  FROM `project.dataset.events_raw`
  WHERE event_date >= CURRENT_DATE() - 7
    AND event_name = 'signup_completed'
)
SELECT 
  COUNT(DISTINCT s1.user_id) AS step1_users,
  COUNT(DISTINCT s2.user_id) AS step2_users,
  SAFE_DIVIDE(COUNT(DISTINCT s2.user_id), COUNT(DISTINCT s1.user_id)) AS conversion_rate
FROM step1 s1
LEFT JOIN step2 s2 ON s1.user_id = s2.user_id
```

### Pattern 3: Cohort Retention
```sql
WITH cohorts AS (
  SELECT 
    user_id,
    DATE_TRUNC(signup_date, MONTH) AS cohort_month
  FROM `project.dataset.users_dim`
  WHERE signup_date >= '2024-01-01'
)
SELECT 
  c.cohort_month,
  DATE_DIFF(e.event_date, c.cohort_month, DAY) AS days_since_signup,
  COUNT(DISTINCT e.user_id) AS active_users
FROM cohorts c
JOIN `project.dataset.events_daily_summary` e
  ON c.user_id = e.user_id
WHERE e.event_date >= '2024-01-01'
  AND e.event_name = 'app_opened'
GROUP BY c.cohort_month, days_since_signup
ORDER BY c.cohort_month, days_since_signup
```

---

## Summary Checklist

Before running any query, verify:

- [ ] Partition column filtered (event_date, signup_date)
- [ ] Date range is reasonable (typically ≤ 90 days)
- [ ] Clustering columns used in WHERE clause
- [ ] Specific columns selected (no SELECT *)
- [ ] Correct table chosen (raw vs aggregated vs dimensional)
- [ ] JSON extraction minimized
- [ ] Query cost estimated and acceptable
