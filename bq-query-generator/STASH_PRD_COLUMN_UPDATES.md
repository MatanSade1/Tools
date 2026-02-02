# Column Descriptions Update - Stash Integration PRD

**Date:** February 1, 2026  
**Source:** [Stash Integration PRD (Section 11: Analytics Requirements)](https://www.notion.so/peerplay/Stash-Integration-PRD-2b0c2344a7dc80e8b354d09a7f2c9058)

---

## Summary

Updated column descriptions in `query_gen_columns` table based on Stash Integration PRD Analytics Requirements.

### Affected Tables
1. **Table:** `yotam-395120.peerplay.vmp_master_event_normalized` (Client Events)
   - **Columns Updated:** 12

2. **Table:** `yotam-395120.peerplay.verification_service_events` (Server Events)
   - **Columns Updated:** 16
   - **Columns Not Found:** 5 (will be added when Stash integration is deployed)

**Total Columns Updated: 28**

---

## Server-Side Events (verification_service_events)

### Mandatory Parameters (All Events)

#### 1. endpoint_name
**Type:** STRING  
**Description:** The service endpoint name that generated this event. Values: apple_purchases (for existing Apple verification events), stash_checkout_link, stash_purchase_verification, stash_webhook.

#### 2. date
**Type:** DATE  
**Description:** Time of the event in format yyyy-mm-dd. Used for partitioning the table.

#### 3. distinct_id
**Type:** STRING  
**Description:** User unique identifier. Same distinct_id used across client events and server events.

#### 4. request_id
**Type:** STRING  
**Description:** Unique request identifier for tracking requests across services.

#### 5. game_id
**Type:** INT  
**Description:** Game identifier. Merge Cruise = 1. Same logic as client events.

#### 6. event_name
**Type:** STRING  
**Description:** Name of the server event. Examples: checkout_link_request, checkout_link_error, checkout_link_response, purchase_verification_request, purchase_verification_decline, purchase_verification_approval.

#### 7. version_float
**Type:** FLOAT  
**Description:** Client version as float. Derived from client metadata for server events.

### Event-Specific Parameters

#### 8. product_id
**Type:** STRING  
**Description:** The SKU for which the checkout link or verification is requested (e.g., com.peerplay.mergecruise.credits1799).

#### 9. purchase_funnel_id
**Type:** STRING  
**Description:** Internal purchase funnel identifier. Links server events to client purchase funnel.

#### 10. transaction_id
**Type:** STRING  
**Description:** Stash order ID. Used to track the transaction through the entire flow.

#### 11. currency
**Type:** STRING  
**Description:** Currency code for the transaction (e.g., USD, CAD, EUR).

#### 12. storefront
**Type:** STRING  
**Description:** Store identifier. Used in purchase verification events.

#### 13. price
**Type:** FLOAT  
**Description:** Transaction price. Used in verification approval/decline events.

#### 14. tax
**Type:** STRING  
**Description:** Tax string provided by Stash. Included in purchase_verification_approval.

#### 15. payment_method
**Type:** STRING  
**Description:** Payment method used for the transaction. Included in purchase_verification_approval.

#### 16. cta_name
**Type:** STRING  
**Description:** CTA name for server-tracked actions. Consistent with client cta_name values.

### Columns Not Yet in Schema (5)

These columns are mentioned in the PRD but not found in the current schema:
- **event_time** - Will replace request_timestamp
- **amount** - Purchase amount
- **currency_id** - Alternative to currency string
- **error** - Error/decline reason
- **checkout_link** - Stash checkout URL

Note: These will likely be added when Stash integration is deployed.

---

## Client Events (vmp_master_event_normalized)

### 1. is_dp_enabled
**Type:** INT  
**Description:** Indication if direct pay (Stash) is enabled for the user. 1 = enabled, 0 = disabled. Added to impression_scapes and impression_settings events.

### 2. payment_platform
**Type:** STRING  
**Description:** Defines the payment service used in the purchase flow (googleplay, apple, stash). Added to purchase_click, purchase_native_popup_impression, purchase_failed, purchase_successful, rewards_store, purchase_transaction_approval_sent, purchase_verification_timeout, purchase_verification_decline, purchase_verification_approval, purchase_verification_request. Note: User may have purchase_click with one payment_platform but complete flow with another.

### 3. price_original
**Type:** FLOAT  
**Description:** The exact payment amount the user paid in local currency (e.g., 2.99 for CAD $2.99 purchase). Added to purchase_click, purchase_native_popup_impression, purchase_failed, purchase_successful.

### 4. currency
**Type:** STRING  
**Description:** The local currency used for the purchase (e.g., CAD, USD, EUR). Added to purchase_click, purchase_native_popup_impression, purchase_failed, purchase_successful, purchase_transaction_approval_sent, purchase_verification_timeout, purchase_verification_decline, purchase_verification_approval, purchase_verification_request.

### 5. purchase_id
**Type:** STRING  
**Description:** Purchase identifier. For Stash purchases, this contains the stash order_id value. Used across purchase flow events.

### 6. dp_live_ops_id
**Type:** INT  
**Description:** The LiveOps ID used for direct pay (Stash). Added to purchase_click, purchase_native_popup_impression, purchase_failed, purchase_successful, rewards_store, purchase_transaction_approval_sent, purchase_verification_timeout, purchase_verification_decline, purchase_verification_approval, and all direct pay events.

### 7. dp_segment_id
**Type:** STRING  
**Description:** The segment ID the user had for the direct pay LiveOps. Should also exist in active_segments. Added to purchase flow and direct pay events.

### 8. presented_offers
**Type:** ARRAY  
**Description:** JSON array containing SKUs and their prices for offers currently viewed by user. Structure: [{sku: 'com.peerplay.mergecruise.credits1799', price_usd: 17.99, original_price: 15.99, currency: 'EUR', type: 'paid'}]. Added to impression_offer_popup, impression_store, impression_first_time_offer_popup, impression_disco_popup, disco_spin_end. For free offers (disco/rolling), type is 'free' and price fields are null.

### 9. is_fallback_purchase_flow
**Type:** INT  
**Description:** Indicates if purchase funnel started after failed Stash purchase when user clicked 'try again'. 1 = purchase started after try again, 0 = normal purchase flow. Added to purchase_click, purchase_native_popup_impression, purchase_failed, purchase_successful, rewards_store, purchase_transaction_approval_sent, purchase_verification_timeout, purchase_verification_decline, purchase_verification_approval.

### 10. checkout_id
**Type:** STRING  
**Description:** The Stash checkout ID provided by Stash after checkout create command. Added to purchase_native_popup_impression, purchase_failed, purchase_successful, rewards_store, purchase_transaction_approval_sent.

### 11. purchase_funnel_id
**Type:** STRING  
**Description:** Internal purchase identifier used throughout the purchase funnel. For impression_dp_unlock event, sent only in PurchaseAttempt and PostPurchaseIAP triggers.

### 12. cta_name
**Type:** STRING  
**Description:** CTA button name clicked by user. For click_in_dp_unlock event: enable, decline, close. For other purchase events: indicates user action taken (e.g., select_stash, select_iap, continue, pay).

---

## Impact

### Before Update
- Columns with descriptions: 61
- Total columns: 1,654
- Coverage: 3.7%

### After Update
- Columns with descriptions: 89 (+28)
- Total columns: 1,654
- Coverage: 5.4%

### vmp_master_event_normalized (Client Events)
- Total columns: 88
- With descriptions: 32 (20 existing + 12 new)
- Coverage: 36.4%

### verification_service_events (Server Events)
- Total columns: 78
- With descriptions: 16 (0 existing + 16 new)
- Coverage: 20.5%

---

## Pinecone Sync

✅ **All 28 column vectors updated in Pinecone**
- Namespace: `organizational-docs`
- Total vectors: 1,702
- Distribution:
  - 14 guardrails
  - 24 tables
  - 1,657 columns (89 with descriptions)
  - 7 metrics

---

## Usage

The query generator now understands Stash integration context for both client and server events. Users can ask questions like:

**Client-Side Queries:**
- "Show me all Stash purchases in the last 7 days"
- "What is the payment_platform distribution for purchases?"
- "How many users have direct pay enabled?"
- "Get checkout failures by currency"

**Server-Side Queries:**
- "Show checkout link errors in the last week"
- "What's the approval rate for Stash purchase verifications?"
- "Get all transactions by endpoint_name"
- "Show payment methods used for approved purchases"

**Cross-Reference Queries:**
- "Join client events with server verification events by purchase_funnel_id"
- "Show the complete purchase flow from click to approval for Stash transactions"
- "Compare client-side and server-side timestamps for purchase verification"

The RAG system will retrieve the relevant column descriptions from both tables and generate accurate BigQuery SQL with proper joins.

---

## Next Steps

1. Monitor query generation accuracy for Stash-related requests
2. Add descriptions to remaining columns as needed
3. Update descriptions when Stash integration evolves
4. Consider adding more analytics events from the PRD

---

**Reference:** For full PRD details, see [Stash Integration PRD](https://www.notion.so/peerplay/Stash-Integration-PRD-2b0c2344a7dc80e8b354d09a7f2c9058)
