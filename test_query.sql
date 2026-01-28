-- Recipes Rewards Funnel Analysis - Individual Event Records
WITH
-- First identify users who triggered the first step (click_recipes_go_board)
first_step AS (
  SELECT
    distinct_id,
    recipes_milestone_id,
    version_float,
    mp_os,
    live_ops_id,
    TIMESTAMP_MILLIS(CAST(res_timestamp AS INT64)) AS event_time
  FROM `yotam-395120.peerplay.vmp_master_event_normalized`
  WHERE mp_event_name = 'click_recipes_go_board'
    AND date >= CURRENT_DATE
    AND recipes_milestone_id IS NOT NULL
    AND mp_country_code NOT IN ('UA', 'IL')
),

-- Then identify users who triggered the second step (rewards_recipes)
second_step AS (
  SELECT
    distinct_id,
    recipes_milestone_id,
    TIMESTAMP_MILLIS(CAST(res_timestamp AS INT64)) AS event_time
  FROM `yotam-395120.peerplay.vmp_master_event_normalized`
  WHERE mp_event_name = 'rewards_recipes'
    AND date >= CURRENT_DATE
    AND recipes_milestone_id IS NOT NULL
    AND mp_country_code NOT IN ('UA', 'IL')
)

-- Match users and get the first subsequent rewards event (if any)
SELECT
  f.distinct_id,
  f.version_float,
  f.mp_os,
  f.live_ops_id,
  f.recipes_milestone_id,
  f.event_time AS go_board_event_time,
  MIN(s.event_time) AS rewards_event_time,
  TIMESTAMP_DIFF(MIN(s.event_time), f.event_time, SECOND) AS time_between_events_seconds
FROM first_step f
LEFT JOIN second_step s
  ON f.distinct_id = s.distinct_id
  AND f.recipes_milestone_id = s.recipes_milestone_id
GROUP BY
  f.distinct_id,
  f.version_float,
  f.mp_os,
  f.live_ops_id,
  f.recipes_milestone_id,
  f.event_time
HAVING rewards_event_time IS NULL
ORDER BY f.event_time DESC


