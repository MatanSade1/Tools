# BigQuery Alerts to Slack

A Cloud Run service that monitors BigQuery queries and sends alerts to Slack when thresholds are exceeded.

## Overview

This service reads alert configurations from a BigQuery table (`yotam-395120.peerplay.bigquery_alerts_to_slack_settings`), executes SQL queries, and sends Slack notifications when conditions are met.

## Service Details

- **Service Name**: `bigquery-alerts-to-slack`
- **Project ID**: `yotam-395120`
- **Project Number**: `57935720907`
- **Region**: `us-central1`
- **Service Account**: `bigquery-alerts-to-slack@yotam-395120.iam.gserviceaccount.com`
- **URL**: `https://bigquery-alerts-to-slack-aqglgkkvdq-uc.a.run.app`
- **Function Target**: `run_alerts`
- **Runtime**: Python 3.10

## Features

- **Hourly (H) and Daily (D) alerts**: Supports different alert resolutions
- **Threshold-based alerting**: Configurable thresholds per alert
- **Cooldown mechanism**: Limits hourly alerts per day
- **Execution history**: Tracks alert executions in BigQuery
- **Rich Slack messages**: Detailed alert notifications with query results
- **Cloud Logging integration**: Proper logging with severity levels

## BigQuery Tables

### Configuration Tables

**Production Table:**
- **Table**: `yotam-395120.peerplay.bigquery_alerts_to_slack_settings`
- **Purpose**: Stores alert configurations for production
- **Used by**: Cloud Run service and local runs (default)

**Stage Table (Test Mode):**
- **Table**: `yotam-395120.peerplay.bigquery_alerts_to_slack_settings_stage`
- **Purpose**: Stores alert configurations for testing
- **Used by**: Local runs with `--test` flag or `TEST_MODE=true`

**Key Fields** (both tables):
  - `name`: Alert name
  - `description`: Alert description
  - `sql`: SQL query to execute
  - `resolution`: 'H' (Hourly) or 'D' (Daily)
  - `owner`: Alert owner
  - `is_active`: 'T' for active alerts
  - `slack_alert_channel`: Slack channel name
  - `alert_id`: Unique alert identifier
  - `threshold_for_alerting`: Minimum value to trigger alert
  - `max_hourly_alerts_per_day`: Daily limit for hourly alerts

### History Tables

**Production Table:**
- **Table**: `yotam-395120.peerplay.bigquery_alerts_execution_history`
- **Purpose**: Tracks alert execution history for cooldown management (production)
- **Used by**: Cloud Run service and local runs (default)

**Stage Table (Test Mode):**
- **Table**: `yotam-395120.peerplay.bigquery_alerts_execution_history_stage`
- **Purpose**: Tracks alert execution history for testing
- **Used by**: Local runs with `--test` flag or `TEST_MODE=true`

**Key Fields** (both tables):
  - `alert_id`: Alert identifier
  - `execution_timestamp`: When the alert was executed
  - `execution_date`: Date of execution
  - `alert_generated`: Whether an alert was sent
  - `row_count`: Number of rows returned
  - `success`: Whether execution succeeded

## Slack Channels

The service supports multiple Slack channels:
- `data-alerts-sandbox`: Default/test channel
- `data-alerts-critical`: Critical alerts
- `data-alerts-non-critical`: Non-critical alerts

## Daily Alert Execution Window

Daily alerts (resolution='D') only execute between **4:50 AM and 5:49 AM** UTC.

## Local Development

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up credentials:
   - Set `GOOGLE_APPLICATION_CREDENTIALS` environment variable
   - Or use default credentials path (see `main.py` line 203)

3. Run locally:
   ```bash
   python main.py [H|D]
   ```
   Optional: Pass 'H' for hourly alerts or 'D' for daily alerts

## Test Mode

Test mode allows you to run the service locally using **stage tables** instead of production tables. This is useful for testing alert configurations without affecting production data.

### How Test Mode Works

When test mode is enabled:
- **Settings table**: Uses `yotam-395120.peerplay.bigquery_alerts_to_slack_settings_stage` instead of `yotam-395120.peerplay.bigquery_alerts_to_slack_settings`
- **History table**: Uses `yotam-395120.peerplay.bigquery_alerts_execution_history_stage` instead of `yotam-395120.peerplay.bigquery_alerts_execution_history`
- Alerts still send to Slack (same channels), but execution history is tracked separately

### Enabling Test Mode

**Option 1: Command line flag**
```bash
python main.py --test
python main.py H --test      # Run hourly alerts in test mode
python main.py D --test      # Run daily alerts in test mode
```

**Option 2: Environment variable**
```bash
export TEST_MODE=true
python main.py
```

**Option 3: Both**
```bash
export TEST_MODE=true
python main.py H --test
```

### Test Mode Examples

```bash
# Run all alerts in test mode
python main.py --test

# Run only hourly alerts in test mode
python main.py H --test

# Run only daily alerts in test mode
python main.py D --test

# Or use the convenience script
./run-test.sh        # Run all alerts in test mode
./run-test.sh H      # Run hourly alerts in test mode
./run-test.sh D      # Run daily alerts in test mode
```

### Important Notes

- Test mode is **disabled** when running on Cloud Run (production only)
- Test mode uses stage tables, so make sure they exist and have the same schema as production tables
- Slack alerts will still be sent (same channels), so be careful when testing
- Execution history is tracked separately in the stage history table

## Deployment

### Deploy to Cloud Run

```bash
gcloud run deploy bigquery-alerts-to-slack \
  --source . \
  --region us-central1 \
  --project yotam-395120 \
  --service-account bigquery-alerts-to-slack@yotam-395120.iam.gserviceaccount.com \
  --set-env-vars FUNCTION_TARGET=run_alerts \
  --allow-unauthenticated
```

### Required IAM Permissions

The service account needs:
- `roles/bigquery.dataViewer` - Read from configuration and history tables
- `roles/bigquery.jobUser` - Execute queries
- `roles/bigquery.dataEditor` - Write to history table
- `roles/drive.readonly` - Access Google Sheets (if using external tables)

## API Endpoints

### HTTP Trigger
- **URL**: `https://bigquery-alerts-to-slack-aqglgkkvdq-uc.a.run.app`
- **Method**: GET or POST
- **Query Parameters**:
  - `resolution` (optional): 'H' for hourly, 'D' for daily

### Example Request
```bash
curl "https://bigquery-alerts-to-slack-aqglgkkvdq-uc.a.run.app?resolution=H"
```

## Code Structure

- `main.py`: Main application code
  - `AlertProcessor`: Core alert processing logic
  - `AlertConfig`: Data class for alert configuration
  - `run_alerts()`: Cloud Run entry point
- `requirements.txt`: Python dependencies

## Notes

- The service uses Application Default Credentials (ADC) in Cloud Run
- Local execution requires explicit credentials file
- Hourly alerts respect `max_hourly_alerts_per_day` cooldown
- Daily alerts only run during the specified time window

