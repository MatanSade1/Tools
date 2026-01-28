# Events and Parameters Dictionary

This document defines all events tracked in our application and their associated parameters. Use this as a reference when writing queries or analyzing user behavior.

---

## Event Naming Convention

**Format:** `object_action` (e.g., `button_clicked`, `screen_viewed`, `user_signup`)

**Rules:**
- Lowercase with underscores
- Present tense for state changes
- Past tense for completed actions
- Be specific and descriptive

---

## Core Application Events

### app_opened

**Description:** Fired when user opens the application and it comes to foreground.

**When triggered:** App launch or app returning from background

**Parameters:**
| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| platform | string | Device platform | ios, android, web |
| app_version | string | Application version | 2.5.1 |
| os_version | string | Operating system version | iOS 17.2, Android 14 |
| device_model | string | Device model | iPhone 15 Pro, Pixel 8 |
| is_first_open | boolean | First time opening app | true, false |
| referrer | string | How user found the app | organic, facebook_ad, google |

**Usage:**
```sql
SELECT 
  event_date,
  COUNT(*) AS app_opens,
  COUNT(DISTINCT user_id) AS unique_users
FROM `project.dataset.events_raw`
WHERE event_date >= CURRENT_DATE() - 7
  AND event_name = 'app_opened'
GROUP BY event_date
```

---

### session_start

**Description:** Marks the beginning of a user session.

**When triggered:** After 30 minutes of inactivity, the next event triggers a new session

**Parameters:**
| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| session_id | string | Unique session identifier | sess_abc123 |
| platform | string | Device platform | ios, android, web |
| entry_point | string | How session started | app_open, deep_link, push_notification |

---

### session_end

**Description:** Marks the end of a user session.

**When triggered:** 30 minutes after last activity or explicit app close

**Parameters:**
| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| session_id | string | Session identifier | sess_abc123 |
| duration_seconds | integer | Session length in seconds | 345 |
| event_count | integer | Number of events in session | 15 |

---

## User Authentication Events

### user_signup

**Description:** User creates a new account.

**When triggered:** Successful account creation

**Parameters:**
| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| signup_method | string | How user signed up | email, google, apple, facebook |
| platform | string | Signup platform | ios, android, web |
| referrer_source | string | Marketing source | organic, paid_search, social |
| referrer_campaign | string | Campaign name | summer_2024, launch_promo |

**Usage:**
```sql
-- Signups by method
SELECT 
  JSON_EXTRACT_SCALAR(properties, '$.signup_method') AS signup_method,
  COUNT(*) AS signups
FROM `project.dataset.events_raw`
WHERE event_date >= CURRENT_DATE() - 30
  AND event_name = 'user_signup'
GROUP BY signup_method
ORDER BY signups DESC
```

---

### user_login

**Description:** Existing user logs into their account.

**When triggered:** Successful authentication

**Parameters:**
| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| login_method | string | Authentication method | email, google, apple, facebook |
| is_automatic | boolean | Auto-login vs manual | true, false |

---

### user_logout

**Description:** User explicitly logs out.

**When triggered:** User clicks logout button

**Parameters:**
| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| platform | string | Logout platform | ios, android, web |

---

## Onboarding Events

### onboarding_started

**Description:** User begins the onboarding flow.

**When triggered:** First onboarding screen shown

**Parameters:**
| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| onboarding_version | string | Version of onboarding flow | v2.1 |

---

### onboarding_step_viewed

**Description:** User views an onboarding step.

**When triggered:** Each onboarding screen view

**Parameters:**
| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| step_number | integer | Step in sequence | 1, 2, 3 |
| step_name | string | Name of step | welcome, permissions, profile_setup |
| onboarding_version | string | Version of flow | v2.1 |

---

### onboarding_step_completed

**Description:** User completes an onboarding step.

**When triggered:** User clicks "Next" or "Continue"

**Parameters:**
| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| step_number | integer | Step number | 1, 2, 3 |
| step_name | string | Step name | welcome, permissions, profile_setup |
| duration_seconds | integer | Time spent on step | 45 |

---

### onboarding_completed

**Description:** User completes entire onboarding flow.

**When triggered:** Last onboarding step completed

**Parameters:**
| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| total_duration_seconds | integer | Total onboarding time | 180 |
| steps_completed | integer | Number of steps completed | 5 |
| skipped_steps | integer | Number of steps skipped | 0 |

---

### onboarding_skipped

**Description:** User skips onboarding flow.

**When triggered:** User clicks "Skip" button

**Parameters:**
| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| step_number | integer | Step where skipped | 2 |
| step_name | string | Step name | permissions |

---

## Navigation Events

### screen_viewed

**Description:** User views a screen in the app.

**When triggered:** Screen becomes visible

**Parameters:**
| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| screen_name | string | Name of screen | home, profile, settings, search |
| screen_class | string | Technical screen identifier | HomeViewController, ProfileScreen |
| previous_screen | string | Last screen viewed | home, search |
| referrer | string | How user got to screen | navigation, deep_link, push |

**Usage:**
```sql
-- Most viewed screens
SELECT 
  JSON_EXTRACT_SCALAR(properties, '$.screen_name') AS screen_name,
  COUNT(*) AS views,
  COUNT(DISTINCT user_id) AS unique_viewers
FROM `project.dataset.events_raw`
WHERE event_date >= CURRENT_DATE() - 7
  AND event_name = 'screen_viewed'
GROUP BY screen_name
ORDER BY views DESC
LIMIT 20
```

---

### button_clicked

**Description:** User clicks/taps a button.

**When triggered:** Button tap/click

**Parameters:**
| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| button_id | string | Button identifier | cta_signup, nav_settings, action_share |
| button_text | string | Visible button text | Sign Up, Settings, Share |
| screen_name | string | Screen containing button | home, profile |
| button_position | string | Location on screen | header, footer, center |

---

### tab_selected

**Description:** User switches tabs in navigation.

**When triggered:** Tab bar item selected

**Parameters:**
| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| tab_name | string | Tab selected | home, search, profile, settings |
| previous_tab | string | Previously active tab | home |

---

## Content Interaction Events

### content_viewed

**Description:** User views a piece of content.

**When triggered:** Content becomes visible on screen

**Parameters:**
| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| content_id | string | Unique content identifier | post_12345, article_789 |
| content_type | string | Type of content | post, article, video, product |
| content_title | string | Content title | "How to use our app" |
| content_category | string | Content category | tutorial, news, product |
| author_id | string | Content creator | user_67890 |

---

### content_liked

**Description:** User likes/favorites content.

**When triggered:** Like/heart button clicked

**Parameters:**
| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| content_id | string | Content identifier | post_12345 |
| content_type | string | Content type | post, article, video |
| action | string | Like or unlike | like, unlike |

---

### content_shared

**Description:** User shares content.

**When triggered:** Share button clicked and share completed

**Parameters:**
| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| content_id | string | Content identifier | post_12345 |
| content_type | string | Content type | post, article, video |
| share_method | string | How shared | copy_link, facebook, twitter, whatsapp |
| share_destination | string | Where shared | external_app, internal_message |

---

### search_performed

**Description:** User performs a search.

**When triggered:** Search submitted

**Parameters:**
| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| search_query | string | Search text (hashed for privacy) | hash_abc123 |
| search_category | string | Search category filter | all, users, posts, products |
| results_count | integer | Number of results | 42 |
| screen_name | string | Where search performed | search_screen, home |

---

### search_result_clicked

**Description:** User clicks a search result.

**When triggered:** Search result selected

**Parameters:**
| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| search_query | string | Original search (hashed) | hash_abc123 |
| result_position | integer | Position in results (0-indexed) | 0, 1, 2 |
| result_id | string | Clicked result identifier | post_12345 |
| result_type | string | Type of result | user, post, product |

---

## Commerce Events

### product_viewed

**Description:** User views a product detail page.

**When triggered:** Product page loaded

**Parameters:**
| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| product_id | string | Product identifier | prod_12345 |
| product_name | string | Product name | Premium Subscription |
| product_category | string | Product category | subscription, feature, content |
| price_usd | float | Price in USD | 9.99 |
| currency | string | Currency code | USD, EUR, GBP |

---

### add_to_cart

**Description:** User adds product to cart.

**When triggered:** Add to cart button clicked

**Parameters:**
| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| product_id | string | Product identifier | prod_12345 |
| product_name | string | Product name | Premium Subscription |
| price_usd | float | Price | 9.99 |
| quantity | integer | Quantity added | 1 |

---

### purchase_initiated

**Description:** User begins checkout process.

**When triggered:** Checkout button clicked

**Parameters:**
| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| cart_value_usd | float | Total cart value | 29.97 |
| item_count | integer | Number of items | 3 |
| payment_method | string | Selected payment method | credit_card, paypal, apple_pay |

---

### purchase_completed

**Description:** User successfully completes purchase.

**When triggered:** Payment confirmed

**Parameters:**
| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| transaction_id | string | Unique transaction ID | txn_abc123 |
| revenue_usd | float | Total revenue | 29.97 |
| tax_usd | float | Tax amount | 2.40 |
| shipping_usd | float | Shipping cost | 5.00 |
| currency | string | Currency | USD |
| payment_method | string | Payment method used | credit_card |
| product_ids | array | List of product IDs | ["prod_1", "prod_2"] |
| coupon_code | string | Discount code used | SAVE20 |

**Usage:**
```sql
-- Daily revenue
SELECT 
  event_date,
  COUNT(DISTINCT transaction_id) AS transactions,
  SUM(CAST(JSON_EXTRACT_SCALAR(properties, '$.revenue_usd') AS FLOAT64)) AS total_revenue
FROM `project.dataset.events_raw`
WHERE event_date >= CURRENT_DATE() - 30
  AND event_name = 'purchase_completed'
GROUP BY event_date
ORDER BY event_date
```

---

### subscription_started

**Description:** User starts a subscription.

**When triggered:** Subscription payment confirmed

**Parameters:**
| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| subscription_id | string | Subscription identifier | sub_abc123 |
| plan_name | string | Subscription plan | premium_monthly, pro_annual |
| price_usd | float | Subscription price | 9.99 |
| billing_period | string | Billing frequency | monthly, annual |
| trial_period_days | integer | Free trial length | 7, 14, 30 |
| is_trial | boolean | Whether it's a trial | true, false |

---

### subscription_renewed

**Description:** Subscription automatically renewed.

**When triggered:** Successful renewal payment

**Parameters:**
| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| subscription_id | string | Subscription ID | sub_abc123 |
| plan_name | string | Plan name | premium_monthly |
| price_usd | float | Renewal price | 9.99 |
| renewal_number | integer | How many renewals | 1, 2, 3 |

---

### subscription_cancelled

**Description:** User cancels subscription.

**When triggered:** Cancellation confirmed

**Parameters:**
| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| subscription_id | string | Subscription ID | sub_abc123 |
| plan_name | string | Plan name | premium_monthly |
| cancellation_reason | string | Why cancelled | too_expensive, not_using, found_alternative |
| months_subscribed | integer | Subscription length | 3 |

---

## Error & Performance Events

### error_occurred

**Description:** Application error happened.

**When triggered:** Caught exception or error

**Parameters:**
| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| error_type | string | Error category | network, api, crash |
| error_code | string | Error code | 404, 500, null_pointer |
| error_message | string | Error description | "Failed to load user data" |
| screen_name | string | Where error occurred | profile, home |
| is_fatal | boolean | Whether app crashed | true, false |

**Usage:**
```sql
-- Error frequency by type
SELECT 
  JSON_EXTRACT_SCALAR(properties, '$.error_type') AS error_type,
  JSON_EXTRACT_SCALAR(properties, '$.error_code') AS error_code,
  COUNT(*) AS error_count,
  COUNT(DISTINCT user_id) AS affected_users
FROM `project.dataset.events_raw`
WHERE event_date >= CURRENT_DATE() - 7
  AND event_name = 'error_occurred'
GROUP BY error_type, error_code
ORDER BY error_count DESC
```

---

### api_request_completed

**Description:** API request finished (success or failure).

**When triggered:** API call completes

**Parameters:**
| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| endpoint | string | API endpoint | /api/v1/users, /api/v1/posts |
| method | string | HTTP method | GET, POST, PUT, DELETE |
| status_code | integer | HTTP status | 200, 404, 500 |
| duration_ms | integer | Request duration | 234 |
| is_success | boolean | Successful request | true, false |

---

## Push Notification Events

### push_notification_received

**Description:** Push notification delivered to device.

**When triggered:** Notification received

**Parameters:**
| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| notification_id | string | Notification identifier | notif_abc123 |
| campaign_id | string | Campaign identifier | campaign_xyz |
| notification_type | string | Type of notification | promotional, transactional, engagement |
| title | string | Notification title | "New message from..." |

---

### push_notification_opened

**Description:** User opens a push notification.

**When triggered:** Notification tapped

**Parameters:**
| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| notification_id | string | Notification ID | notif_abc123 |
| campaign_id | string | Campaign ID | campaign_xyz |
| time_to_open_seconds | integer | Time until opened | 120 |

---

## Parameter Extraction Examples

### Extract screen name from screen_viewed events
```sql
SELECT 
  event_date,
  JSON_EXTRACT_SCALAR(properties, '$.screen_name') AS screen_name,
  COUNT(*) AS views
FROM `project.dataset.events_raw`
WHERE event_date >= CURRENT_DATE() - 7
  AND event_name = 'screen_viewed'
GROUP BY event_date, screen_name
```

### Extract product info from purchases
```sql
SELECT 
  JSON_EXTRACT_SCALAR(properties, '$.transaction_id') AS transaction_id,
  CAST(JSON_EXTRACT_SCALAR(properties, '$.revenue_usd') AS FLOAT64) AS revenue,
  JSON_EXTRACT_SCALAR(properties, '$.payment_method') AS payment_method
FROM `project.dataset.events_raw`
WHERE event_date >= CURRENT_DATE() - 30
  AND event_name = 'purchase_completed'
```

### Extract multiple properties
```sql
SELECT 
  user_id,
  event_timestamp,
  JSON_EXTRACT_SCALAR(properties, '$.screen_name') AS screen_name,
  JSON_EXTRACT_SCALAR(properties, '$.button_id') AS button_id,
  JSON_EXTRACT_SCALAR(properties, '$.button_text') AS button_text
FROM `project.dataset.events_raw`
WHERE event_date >= CURRENT_DATE() - 7
  AND event_name = 'button_clicked'
```

---

## Common Event Patterns

### User Journey Analysis
```sql
-- Track user journey through screens
SELECT 
  user_id,
  event_timestamp,
  JSON_EXTRACT_SCALAR(properties, '$.screen_name') AS screen_name
FROM `project.dataset.events_raw`
WHERE event_date = CURRENT_DATE() - 1
  AND user_id = 'usr_12345'
  AND event_name = 'screen_viewed'
ORDER BY event_timestamp
```

### Conversion Funnel
```sql
-- Signup funnel
WITH signup_started AS (
  SELECT DISTINCT user_id FROM `project.dataset.events_raw`
  WHERE event_date >= CURRENT_DATE() - 7 AND event_name = 'user_signup_started'
),
signup_completed AS (
  SELECT DISTINCT user_id FROM `project.dataset.events_raw`
  WHERE event_date >= CURRENT_DATE() - 7 AND event_name = 'user_signup'
)
SELECT 
  COUNT(DISTINCT ss.user_id) AS started,
  COUNT(DISTINCT sc.user_id) AS completed,
  SAFE_DIVIDE(COUNT(DISTINCT sc.user_id), COUNT(DISTINCT ss.user_id)) AS conversion_rate
FROM signup_started ss
LEFT JOIN signup_completed sc ON ss.user_id = sc.user_id
```

---

## Event Volume Guidelines

**High-volume events** (>1M/day):
- `screen_viewed`
- `button_clicked`
- `app_opened`

**Medium-volume events** (100K-1M/day):
- `content_viewed`
- `search_performed`
- `tab_selected`

**Low-volume events** (<100K/day):
- `user_signup`
- `purchase_completed`
- `subscription_started`

When querying high-volume events, always use date filters and consider using `events_daily_summary` for aggregations.
