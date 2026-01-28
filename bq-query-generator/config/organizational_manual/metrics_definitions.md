# Organizational Metrics Definitions

This document defines all standard metrics used across the organization. Use these definitions to ensure consistency in reporting and analysis.

---

## User Activity Metrics

### Daily Active Users (DAU)

**Definition:** Unique users who performed at least one qualifying activity on a given day.

**Qualifying events:**
- `app_opened`
- `session_start`
- Any user interaction event

**Calculation:**
```sql
SELECT 
  event_date,
  COUNT(DISTINCT user_id) AS dau
FROM `project.dataset.events_daily_summary`
WHERE event_date >= CURRENT_DATE() - 30
  AND event_name IN ('app_opened', 'session_start')
GROUP BY event_date
```

**Notes:**
- Use `events_daily_summary` for fast calculation
- Background events don't count
- Must be an authenticated user (has user_id, not just distinct_id)

---

### Monthly Active Users (MAU)

**Definition:** Unique users who performed at least one qualifying activity in the last 30 days.

**Calculation:**
```sql
SELECT 
  COUNT(DISTINCT user_id) AS mau
FROM `project.dataset.events_daily_summary`
WHERE event_date >= CURRENT_DATE() - 30
  AND event_name IN ('app_opened', 'session_start')
```

**Notes:**
- Rolling 30-day window
- For calendar month MAU, use `DATE_TRUNC(event_date, MONTH)`

---

### Weekly Active Users (WAU)

**Definition:** Unique users who performed at least one qualifying activity in the last 7 days.

**Calculation:**
```sql
SELECT 
  COUNT(DISTINCT user_id) AS wau
FROM `project.dataset.events_daily_summary`
WHERE event_date >= CURRENT_DATE() - 7
  AND event_name IN ('app_opened', 'session_start')
```

---

### Stickiness Ratio

**Definition:** DAU / MAU ratio, indicating how frequently monthly users engage.

**Calculation:**
```sql
WITH dau AS (
  SELECT COUNT(DISTINCT user_id) AS daily_users
  FROM `project.dataset.events_daily_summary`
  WHERE event_date = CURRENT_DATE() - 1
    AND event_name IN ('app_opened', 'session_start')
),
mau AS (
  SELECT COUNT(DISTINCT user_id) AS monthly_users
  FROM `project.dataset.events_daily_summary`
  WHERE event_date >= CURRENT_DATE() - 30
    AND event_name IN ('app_opened', 'session_start')
)
SELECT 
  dau.daily_users,
  mau.monthly_users,
  SAFE_DIVIDE(dau.daily_users, mau.monthly_users) AS stickiness_ratio
FROM dau, mau
```

**Interpretation:**
- 0.2 = 20% stickiness (users engage 6 days/month on average)
- 0.5 = 50% stickiness (users engage 15 days/month on average)
- Higher is better; >0.3 is considered good for most apps

---

## User Acquisition Metrics

### New Users

**Definition:** Users who signed up on a given day.

**Calculation:**
```sql
SELECT 
  signup_date,
  COUNT(*) AS new_users
FROM `project.dataset.users_dim`
WHERE signup_date >= CURRENT_DATE() - 30
GROUP BY signup_date
ORDER BY signup_date
```

**Notes:**
- Based on `signup_date` in users_dim
- Includes all users regardless of activation status

---

### Activated Users

**Definition:** New users who completed the onboarding flow on their signup day.

**Calculation:**
```sql
WITH signups AS (
  SELECT 
    user_id,
    signup_date
  FROM `project.dataset.users_dim`
  WHERE signup_date >= CURRENT_DATE() - 30
),
activations AS (
  SELECT DISTINCT 
    user_id,
    DATE(event_timestamp) AS activation_date
  FROM `project.dataset.events_raw`
  WHERE event_date >= CURRENT_DATE() - 30
    AND event_name = 'onboarding_completed'
)
SELECT 
  s.signup_date,
  COUNT(DISTINCT s.user_id) AS new_users,
  COUNT(DISTINCT a.user_id) AS activated_users,
  SAFE_DIVIDE(COUNT(DISTINCT a.user_id), COUNT(DISTINCT s.user_id)) AS activation_rate
FROM signups s
LEFT JOIN activations a 
  ON s.user_id = a.user_id 
  AND s.signup_date = a.activation_date
GROUP BY s.signup_date
ORDER BY s.signup_date
```

---

### Activation Rate

**Definition:** Percentage of new users who complete onboarding.

**Target:** >40% activation within 24 hours

**See:** Activated Users query above

---

## Retention Metrics

### Day N Retention

**Definition:** Percentage of users from a cohort who return on day N after signup.

**Common intervals:** Day 1, Day 7, Day 30

**Calculation:**
```sql
WITH cohort AS (
  SELECT 
    user_id,
    signup_date
  FROM `project.dataset.users_dim`
  WHERE signup_date = '2024-01-01'  -- Specific cohort
),
returns AS (
  SELECT 
    c.user_id,
    c.signup_date,
    e.event_date,
    DATE_DIFF(e.event_date, c.signup_date, DAY) AS days_since_signup
  FROM cohort c
  JOIN `project.dataset.events_daily_summary` e
    ON c.user_id = e.user_id
  WHERE e.event_name IN ('app_opened', 'session_start')
    AND e.event_date > c.signup_date
)
SELECT 
  COUNT(DISTINCT CASE WHEN days_since_signup = 1 THEN user_id END) AS day1_retained,
  COUNT(DISTINCT CASE WHEN days_since_signup = 7 THEN user_id END) AS day7_retained,
  COUNT(DISTINCT CASE WHEN days_since_signup = 30 THEN user_id END) AS day30_retained,
  COUNT(DISTINCT c.user_id) AS cohort_size,
  SAFE_DIVIDE(COUNT(DISTINCT CASE WHEN days_since_signup = 1 THEN user_id END), COUNT(DISTINCT c.user_id)) AS day1_retention_rate,
  SAFE_DIVIDE(COUNT(DISTINCT CASE WHEN days_since_signup = 7 THEN user_id END), COUNT(DISTINCT c.user_id)) AS day7_retention_rate,
  SAFE_DIVIDE(COUNT(DISTINCT CASE WHEN days_since_signup = 30 THEN user_id END), COUNT(DISTINCT c.user_id)) AS day30_retention_rate
FROM cohort c
LEFT JOIN returns r ON c.user_id = r.user_id
```

**Benchmarks:**
- Day 1: >40% is good
- Day 7: >25% is good
- Day 30: >15% is good

---

### Rolling Retention

**Definition:** Percentage of users who were active in the previous period and remain active in the current period.

**Calculation:**
```sql
WITH last_period AS (
  SELECT DISTINCT user_id
  FROM `project.dataset.events_daily_summary`
  WHERE event_date >= CURRENT_DATE() - 14
    AND event_date < CURRENT_DATE() - 7
    AND event_name IN ('app_opened', 'session_start')
),
current_period AS (
  SELECT DISTINCT user_id
  FROM `project.dataset.events_daily_summary`
  WHERE event_date >= CURRENT_DATE() - 7
    AND event_name IN ('app_opened', 'session_start')
)
SELECT 
  COUNT(DISTINCT lp.user_id) AS previous_period_users,
  COUNT(DISTINCT cp.user_id) AS retained_users,
  SAFE_DIVIDE(COUNT(DISTINCT cp.user_id), COUNT(DISTINCT lp.user_id)) AS retention_rate
FROM last_period lp
LEFT JOIN current_period cp ON lp.user_id = cp.user_id
```

---

## Engagement Metrics

### Session Count

**Definition:** Number of distinct sessions in a time period.

**Session definition:** Activity separated by >30 minutes of inactivity.

**Calculation:**
```sql
SELECT 
  event_date,
  SUM(unique_sessions) AS total_sessions
FROM `project.dataset.events_daily_summary`
WHERE event_date >= CURRENT_DATE() - 30
GROUP BY event_date
ORDER BY event_date
```

**Notes:**
- Pre-calculated in `events_daily_summary`
- Uses 30-minute session timeout

---

### Average Session Duration

**Definition:** Average time between first and last event in a session.

**Calculation:**
```sql
SELECT 
  event_date,
  AVG(TIMESTAMP_DIFF(last_event_timestamp, first_event_timestamp, SECOND)) / 60 AS avg_session_minutes
FROM `project.dataset.events_daily_summary`
WHERE event_date >= CURRENT_DATE() - 30
  AND first_event_timestamp < last_event_timestamp  -- Filter single-event sessions
GROUP BY event_date
ORDER BY event_date
```

---

### Events Per User

**Definition:** Average number of events triggered per user.

**Calculation:**
```sql
SELECT 
  event_date,
  SUM(event_count) AS total_events,
  COUNT(DISTINCT user_id) AS total_users,
  SAFE_DIVIDE(SUM(event_count), COUNT(DISTINCT user_id)) AS events_per_user
FROM `project.dataset.events_daily_summary`
WHERE event_date >= CURRENT_DATE() - 30
GROUP BY event_date
ORDER BY event_date
```

---

## Revenue Metrics

### Lifetime Value (LTV)

**Definition:** Total revenue generated by a user since signup.

**Calculation:**
```sql
SELECT 
  user_id,
  lifetime_revenue_usd AS ltv
FROM `project.dataset.users_dim`
WHERE is_active = true
```

**Notes:**
- Pre-calculated in `users_dim`
- Updated daily
- Includes all revenue sources (subscriptions, in-app purchases, ads)

---

### Average Revenue Per User (ARPU)

**Definition:** Average revenue across all users in a time period.

**Calculation:**
```sql
WITH cohort AS (
  SELECT 
    user_id,
    DATE_TRUNC(signup_date, MONTH) AS signup_month
  FROM `project.dataset.users_dim`
  WHERE signup_date >= '2024-01-01'
)
SELECT 
  signup_month,
  COUNT(DISTINCT user_id) AS users,
  SUM(lifetime_revenue_usd) AS total_revenue,
  SAFE_DIVIDE(SUM(lifetime_revenue_usd), COUNT(DISTINCT user_id)) AS arpu
FROM cohort c
JOIN `project.dataset.users_dim` u USING(user_id)
GROUP BY signup_month
ORDER BY signup_month
```

---

### Average Revenue Per Paying User (ARPPU)

**Definition:** Average revenue across only paying users.

**Calculation:**
```sql
SELECT 
  DATE_TRUNC(signup_date, MONTH) AS signup_month,
  COUNT(DISTINCT CASE WHEN lifetime_revenue_usd > 0 THEN user_id END) AS paying_users,
  SUM(lifetime_revenue_usd) AS total_revenue,
  SAFE_DIVIDE(SUM(lifetime_revenue_usd), 
              COUNT(DISTINCT CASE WHEN lifetime_revenue_usd > 0 THEN user_id END)) AS arppu
FROM `project.dataset.users_dim`
WHERE signup_date >= '2024-01-01'
GROUP BY signup_month
ORDER BY signup_month
```

---

## Conversion Metrics

### Funnel Conversion Rate

**Definition:** Percentage of users who complete a multi-step process.

**Common funnels:**
- Signup: `signup_started` → `signup_completed`
- Purchase: `product_viewed` → `add_to_cart` → `purchase_completed`
- Onboarding: `app_opened` → `tutorial_started` → `tutorial_completed`

**Calculation template:**
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

---

## Platform & Geographic Metrics

### Platform Distribution

**Definition:** Distribution of users/events across platforms.

**Calculation:**
```sql
SELECT 
  platform,
  COUNT(DISTINCT user_id) AS users,
  SUM(event_count) AS events
FROM `project.dataset.events_daily_summary`
WHERE event_date >= CURRENT_DATE() - 30
GROUP BY platform
ORDER BY users DESC
```

---

### Geographic Distribution

**Definition:** Distribution of users by country.

**Calculation:**
```sql
SELECT 
  country,
  COUNT(*) AS users,
  COUNT(CASE WHEN is_active THEN 1 END) AS active_users,
  AVG(lifetime_revenue_usd) AS avg_ltv
FROM `project.dataset.users_dim`
GROUP BY country
ORDER BY users DESC
LIMIT 20
```

---

## Metric Calculation Best Practices

1. **Always specify time windows** - Don't calculate metrics without date filters
2. **Use appropriate granularity** - Daily summary for trends, raw events for details
3. **Handle edge cases** - Use SAFE_DIVIDE to avoid division by zero
4. **Filter out test users** - Exclude internal testing accounts (implement user_id filters)
5. **Document assumptions** - Specify what counts as "active", "retained", etc.
6. **Consistent event definitions** - Use same qualifying events across similar metrics

---

## Metric Refresh Schedule

| Metric Category | Refresh Frequency | Source Table | Lag |
|----------------|-------------------|--------------|-----|
| DAU/MAU/WAU | Hourly | events_daily_summary | 4 hours |
| Retention | Daily | events_daily_summary | 4 hours |
| LTV/Revenue | Daily | users_dim | 24 hours |
| Activation | Hourly | events_raw | Real-time |
| Funnels | Hourly | events_raw | Real-time |
