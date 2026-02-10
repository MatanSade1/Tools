# Fraudsters Management Cloud Run Service

A Cloud Run service that automates the fraud detection and management process, converting the Jupyter notebook workflow into a production-ready scheduled service.

## Overview

This service executes a 4-step fraud detection process:

1. **Calculate potential_fraudsters table** - Analyzes all users using 15 fraud detection patterns
2. **Calculate offer_wall_progression_cheaters table** - Filters potential fraudsters for offerwall cheaters
3. **Update fraudsters table** - Updates the main fraudsters table with platform/date-specific logic
4. **Update Mixpanel cohort** - Updates user profiles in Mixpanel with fraudster markers

## Service Details

- **Service Name**: `fraudsters-management`
- **Project ID**: `yotam-395120`
- **Region**: `us-central1`
- **Service Account**: `bigquery-alerts-to-slack@yotam-395120.iam.gserviceaccount.com`
- **Schedule**: Daily at 11AM UTC via Cloud Scheduler
- **Runtime**: Python 3.10
- **Memory**: 2Gi
- **CPU**: 2
- **Timeout**: 3600s (1 hour)

## Features

- **Error Alerting**: Sends Slack alerts to `#matan-coralogix-alerts` when any query fails
- **Audit Logging**: Logs all step start/end times to `process_audit_log` table in BigQuery
- **Run ID Tracking**: Each execution has a unique UUID for correlation
- **Resilient Execution**: Continues processing remaining steps even if one fails
- **Mixpanel Integration**: Updates user profiles with consistent cohort marker

## Fraud Detection Patterns

The service detects 15 different fraud patterns:

1. **Fast Progression** - Chapter 20+ in <24h without purchase
2. **Excessive Harvests** - ≥22 net harvests per day on >2 different days
3. **Suspicious Purchases** - Purchases with price = $0.01
4. **Rapid Purchases** - Consecutive purchases 1-7 seconds apart (Apple only)
5. **Purchase Flow Anomalies** - Consecutive successful purchases without clicks
6. **High Balance Violations** - >245K credits or >850K metapoints
7. **Negative Balance Violations** - Negative credit or metapoint balance
8. **Large Jump Violations** - 40K+ credits or 100K+ metapoints without reward events (checks current + next 2 events)
9. **Privacy Screen Abandonment** - Privacy impression without agree click
10. **Rapid Chapter Progression** - >5 chapters/day with <500 credits/chapter (DISABLED)
11. **Refund Abuse** - >25% refund rate with >5 purchases (Android)
12. **High Tutorial Balance** - >4,950 credits in chapters 1-3 without purchases
13. **Multiple Chapter 1 Purchases** - >1 purchase in chapter 1 (installed after 2025-03-01)
14. **Duplicate Transaction ID** - Same transaction_id/google_order_number/checkout_id used multiple times (Apple, Google Play, Stash)
15. **Penny Purchases** - 2+ purchases at exactly $0.01 price

## Platform-Specific Rules

### Apple Users
- **Installed OR last purchased on/after 2025-08-13**: Only `duplicate_transaction_flag` or `penny_purchase_flag`
- **Installed AND last purchased before 2025-08-13**: All patterns apply

### Android Users
- **Installed OR last purchased on/after 2025-04-17**: Only `duplicate_transaction_flag` or `penny_purchase_flag`
- **Installed AND last purchased before 2025-04-17**: All patterns except Apple-specific (3, 4, 5)

## Deployment

### Prerequisites

- Google Cloud SDK installed and authenticated
- Access to project `yotam-395120`
- Service account permissions

### Deploy to Cloud Run

```bash
cd fraudsters-management
./deploy.sh
```

The deployment script will:
1. Create service account if it doesn't exist
2. Grant necessary BigQuery permissions
3. Deploy the Cloud Run service
4. Create/update Cloud Scheduler job for 11AM UTC daily execution

### Manual Deployment

```bash
gcloud run deploy fraudsters-management \
  --source . \
  --region us-central1 \
  --project yotam-395120 \
  --service-account bigquery-alerts-to-slack@yotam-395120.iam.gserviceaccount.com \
  --set-env-vars GCP_PROJECT_ID=yotam-395120 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 3600 \
  --max-instances 1
```

## Required IAM Permissions

The service account needs:
- `roles/bigquery.jobUser` - Execute queries
- `roles/bigquery.dataEditor` - Write to fraudsters tables and audit log
- `roles/bigquery.dataViewer` - Read from source tables
- `roles/drive.readonly` - Access Google Drive (for googleplay_sales external table)

## Environment Variables

- `GCP_PROJECT_ID` - Set to `yotam-395120` (configured in deploy script)
- `MIXPANEL_PROJECT_TOKEN` - Hardcoded in service: `0e73d8fa8567c5bf2820b408701fa7be`
- `SLACK_BOT_TOKEN_NAME` or `SLACK_BOT_TOKEN` - For error alerts (uses shared/config.py)

## API Endpoints

### HTTP Trigger
- **URL**: Cloud Run service URL (returned after deployment)
- **Method**: GET or POST
- **Response**: JSON with execution results

### Example Response

```json
{
  "success": true,
  "run_id": "014ed315-c541-4bbb-8c28-d262c7b0d176",
  "steps": [
    {
      "step": "Step 1",
      "success": true,
      "result": {"success": true, "step": 1}
    },
    ...
  ],
  "start_time": "2025-12-04T11:00:00",
  "end_time": "2025-12-04T11:15:00"
}
```

## Error Handling

When any step fails:
1. Error is logged to Cloud Logging
2. Slack alert is sent to `#matan-coralogix-alerts` with:
   - Step number
   - Error message
   - Run ID
   - Query details (if applicable)
   - Link to Cloud Logging
3. Process continues with remaining steps
4. Final response indicates which steps succeeded/failed

## Monitoring

- **Cloud Logging**: All logs are written to Cloud Logging with run_id for correlation
- **Audit Table**: Step start/end times logged to `yotam-395120.peerplay.process_audit_log`
- **Slack Alerts**: Error notifications sent to `#matan-coralogix-alerts`

## Local Testing

```bash
# Set environment variables
export GCP_PROJECT_ID=yotam-395120
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json

# Run locally
python main.py
```

Or use Flask directly:
```bash
flask run --host=0.0.0.0 --port=8080
```

## Code Structure

- `main.py` - Main service code with all 4 steps (production)
- `main_dev.py` - Development version targeting staging tables
- `requirements.txt` - Python dependencies
- `deploy.sh` - Deployment script
- `README.md` - This file
- `shared/` - Shared utilities (bigquery_client, slack_client)

## Fraudsters Table Schema

| Column | Type | Description |
|--------|------|-------------|
| distinct_id | STRING | Unique user identifier |
| manual_identification_fraud_purchase_flag | INTEGER | Manual fraud identification (0/1) |
| fast_progression_flag | INTEGER | Pattern 1 (0/1) |
| excessive_harvests_flag | INTEGER | Pattern 2 (0/1) |
| suspicious_purchase_flag | INTEGER | Pattern 3 (0/1) |
| rapid_purchases_flag | INTEGER | Pattern 4 (0/1) |
| purchase_flow_anomaly_flag | INTEGER | Pattern 5 (0/1) |
| high_balance_flag | INTEGER | Pattern 6 (0/1) |
| negative_balance_flag | INTEGER | Pattern 7 (0/1) |
| large_jump_flag | INTEGER | Pattern 8 (0/1) |
| privacy_abandonment_flag | INTEGER | Pattern 9 (0/1) |
| rapid_chapter_progression_flag | INTEGER | Pattern 10 (0/1) - DISABLED |
| refund_abuse_flag | INTEGER | Pattern 11 (0/1) |
| high_tutorial_balance_flag | INTEGER | Pattern 12 (0/1) |
| multiple_chapter1_purchases_flag | INTEGER | Pattern 13 (0/1) |
| duplicate_transaction_flag | INTEGER | Pattern 14 (0/1) |
| penny_purchase_flag | INTEGER | Pattern 15 (0/1) |

## Notes

- The service uses Application Default Credentials (ADC) in Cloud Run
- Local execution requires explicit credentials file with Drive scopes
- Mixpanel cohort marker is consistent: `fraudster_cohort_active_v8`
- All BigQuery queries are extracted from the original Jupyter notebook
- Service processes steps sequentially, but continues on errors
- Pattern 14 now supports Apple, Google Play, and Stash payment platforms
