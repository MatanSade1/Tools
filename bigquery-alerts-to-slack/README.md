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
- **Memory**: 2GiB
- **CPU**: 2 vCPUs
- **Timeout**: 3600 seconds (1 hour)
- **Max Instances**: 1

## Features

- **Hourly (H) and Daily (D) alerts**: Supports different alert resolutions
- **Multi-channel threshold-based alerting**: Configurable thresholds per channel (sandbox, non-critical, critical)
- **Per-channel cooldown mechanism**: Independent daily limits for each Slack channel
- **Multi-channel alerting**: Alerts can be sent to multiple channels simultaneously when multiple thresholds are met
- **Execution history**: Tracks alert executions in BigQuery with channel-specific logging
- **Rich Slack messages**: Detailed alert notifications with query results
- **Cloud Logging integration**: Proper logging with severity levels
- **Query timeout protection**: 90-second timeout (30s submit + 60s result) to prevent hanging queries

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
  - `alert_id`: Unique alert identifier (required for hourly alerts with cooldown)
  - `jira_id`: Jira ticket ID (optional)
  - `data_query_link`: Link to data query (optional)
  - `notion_doc_link`: Link to Notion documentation (optional)
  
  **Multi-Channel Threshold Fields:**
  - `threshold_sandbox`: Threshold for sandbox channel (INT64, nullable)
  - `threshold_non_critical`: Threshold for non-critical channel (INT64, nullable)
  - `threshold_critical`: Threshold for critical channel (INT64, nullable)
  - At least one threshold must be defined for an alert to be active
  
  **Per-Channel Cooldown Fields** (hourly alerts only):
  - `max_hourly_alerts_sandbox`: Daily limit for sandbox channel (INT64, nullable, NULL = unlimited)
  - `max_hourly_alerts_non_critical`: Daily limit for non-critical channel (INT64, nullable, NULL = unlimited)
  - `max_hourly_alerts_critical`: Daily limit for critical channel (INT64, nullable, NULL = unlimited)

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
  - `alert_name`: Name of the alert
  - `execution_timestamp`: When the alert was executed
  - `execution_date`: Date of execution
  - `alert_generated`: Whether an alert was sent (BOOL)
  - `row_count`: Number of rows returned by the query
  - `threshold_value`: Threshold value that was checked
  - `slack_channel`: Slack channel name (for multi-channel tracking)
  - `resolution`: Alert resolution ('H' or 'D')
  - `success`: Whether execution succeeded (BOOL)
  - `error_message`: Error message if execution failed (STRING, nullable)

## Multi-Channel Alert System

The service supports **three Slack channels** with independent thresholds and cooldowns:

- **`data-alerts-sandbox`**: Sandbox/test channel
- **`data-alerts-non-critical`**: Non-critical alerts channel
- **`data-alerts-critical`**: Critical alerts channel

### How Multi-Channel Alerting Works

1. **Threshold Checking**: After executing a query, the service checks the row count against each defined threshold:
   - If `row_count >= threshold_sandbox` → alert sent to `data-alerts-sandbox`
   - If `row_count >= threshold_non_critical` → alert sent to `data-alerts-non-critical`
   - If `row_count >= threshold_critical` → alert sent to `data-alerts-critical`

2. **Multiple Channels**: An alert can be sent to **multiple channels simultaneously** if multiple thresholds are met. For example:
   - If `threshold_sandbox=10`, `threshold_non_critical=50`, `threshold_critical=100`
   - And query returns 75 rows
   - Then alerts are sent to both `data-alerts-sandbox` and `data-alerts-non-critical` (but not critical)

3. **Per-Channel Cooldown**: Each channel has its own independent cooldown limit:
   - Hourly alerts respect `max_hourly_alerts_*` per channel
   - Cooldown is tracked separately for each channel
   - If one channel is in cooldown, other channels can still receive alerts

4. **Channel-Specific Logging**: Each alert execution is logged separately for each channel, allowing independent cooldown tracking.

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

Use the provided deployment script:

```bash
./deploy.sh
```

Or deploy manually:

```bash
gcloud run deploy bigquery-alerts-to-slack \
  --source . \
  --region us-central1 \
  --project yotam-395120 \
  --service-account bigquery-alerts-to-slack@yotam-395120.iam.gserviceaccount.com \
  --set-env-vars FUNCTION_TARGET=run_alerts,GUNICORN_TIMEOUT=120 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 3600 \
  --max-instances 1 \
  --platform managed
```

### Resource Configuration

- **Memory**: 2GiB (allows for complex queries and concurrent operations)
- **CPU**: 2 vCPUs (improves query processing performance)
- **Timeout**: 3600 seconds (1 hour) - service-level timeout
- **Query Timeout**: 90 seconds (30s submit + 60s result) - per-query timeout to prevent hanging
- **Max Instances**: 1 (ensures single execution at a time)

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

## Query Execution & Timeouts

### Query Timeout Protection

The service implements timeout protection to prevent hanging queries:

- **Query Submission**: 30 seconds timeout
- **Result Retrieval**: 60 seconds timeout
- **Result Iteration**: 60 seconds timeout
- **Total Query Timeout**: 90 seconds maximum

If a query exceeds these timeouts:
- The query job is cancelled to free up resources
- The execution is logged as failed with detailed error information
- The service continues processing other alerts
- Error logs include BigQuery job ID for debugging

### Cooldown Check Timeout

Cooldown checks also have timeout protection:
- **Cooldown Query**: 45 seconds total (15s submit + 15s result + 15s iteration)
- If cooldown check times out, the alert is allowed to proceed (fail-open behavior)

### Execution Logging Timeout

Execution logging has its own timeout:
- **Logging Query**: 35 seconds total (5s submit + 30s result)
- Uses a separate BigQuery client to avoid connection pool issues

## Notes

- The service uses Application Default Credentials (ADC) in Cloud Run
- Local execution requires explicit credentials file
- Hourly alerts respect per-channel `max_hourly_alerts_*` cooldown limits
- Daily alerts only run during the specified time window (4:50 AM - 5:49 AM UTC)
- At least one threshold (sandbox, non-critical, or critical) must be defined for an alert to be active
- Alerts without `alert_id` cannot use the cooldown mechanism (cooldown is disabled for those alerts)
- Query timeouts are logged with detailed information including exception type and BigQuery job ID

