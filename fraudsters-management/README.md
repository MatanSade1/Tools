# Fraudsters Management Cloud Run Service

A Cloud Run service that automates the fraud detection and management process, converting the Jupyter notebook workflow into a production-ready scheduled service.

## Overview

This service executes a 4-step fraud detection process:

1. **Calculate potential_fraudsters table** - Analyzes all users using 14 fraud detection patterns
2. **Calculate offer_wall_progression_cheaters table** - Filters potential fraudsters for offerwall cheaters
3. **Update fraudsters table** - Updates the main fraudsters table with platform/date-specific logic
4. **Update Mixpanel cohort** - Updates user profiles in Mixpanel with fraudster markers

## Service Details

- **Service Name**: `fraudsters-management`
- **Project ID**: `yotam-395120`
- **Region**: `us-central1`
- **Service Account**: `fraudsters-management@yotam-395120.iam.gserviceaccount.com`
- **Schedule**: Daily at 11AM UTC via Cloud Scheduler
- **Runtime**: Python 3.10
- **Memory**: 2Gi
- **CPU**: 2
- **Timeout**: 3600s (1 hour)

## Features

- **Error Alerting**: Sends Slack alerts to `#data-alerts-critical` when any query fails
- **Audit Logging**: Logs all step start/end times to `process_audit_log` table in BigQuery
- **Run ID Tracking**: Each execution has a unique UUID for correlation
- **Resilient Execution**: Continues processing remaining steps even if one fails
- **Mixpanel Integration**: Updates user profiles with consistent cohort marker

## Fraud Detection Patterns

The service detects 14 different fraud patterns:

1. Fast progression (chapter 20+ in <24h without purchase)
2. Excessive harvests (>21 harvests per day)
3. Suspicious purchases (price = 0.01)
4. Rapid purchases (consecutive purchases 1-7 seconds apart on Apple)
5. Purchase flow anomalies (consecutive successful purchases without clicks)
6. High balance violations (>245K credits or >850K metapoints)
7. Negative balance violations
8. Large jump violations (40K+ credits or 100K+ metapoints without reward events)
9. Privacy screen abandonment
10. Rapid chapter progression with low credit spend
11. Refund abuse (>25% refund rate with >5 purchases)
12. High tutorial balance without purchases
13. Multiple purchases in Chapter 1
14. Duplicate transaction ID usage

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
  --service-account fraudsters-management@yotam-395120.iam.gserviceaccount.com \
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
2. Slack alert is sent to `#data-alerts-critical` with:
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
- **Slack Alerts**: Error notifications sent to `#data-alerts-critical`

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

- `main.py` - Main service code with all 4 steps
- `requirements.txt` - Python dependencies
- `deploy.sh` - Deployment script
- `README.md` - This file

## Notes

- The service uses Application Default Credentials (ADC) in Cloud Run
- Local execution requires explicit credentials file
- Mixpanel cohort marker is consistent: `fraudster_cohort_active_v7`
- All BigQuery queries are extracted from the original Jupyter notebook
- Service processes steps sequentially, but continues on errors

