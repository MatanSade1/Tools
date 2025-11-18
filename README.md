# Mixpanel to BigQuery Alert System

A Python-based data pipeline that collects events from Mixpanel, stores them in BigQuery, and monitors for abnormal behavior with Slack alerts.

## Overview

This system consists of two main components:

1. **Data Collector**: Fetches events from Mixpanel API every 15 minutes and stores them in BigQuery
2. **Anomaly Detector**: Queries BigQuery to detect abnormal behavior (>5 events per minute) and sends Slack alerts

## Features

- **Configurable Event List**: Manage events to collect and monitor via `config/events_config.json`
- **Per-Event Alert Configuration**: Each event can have its own threshold, time window, and Slack channel
- **Idempotent Data Collection**: Handles duplicates and retries
- **Rich Slack Alerts**: Detailed alerts with event counts, sample data, and BigQuery links
- **Cloud Functions Deployment**: Ready for GCP Cloud Functions v2

## Project Structure

```
/
├── collector/              # Data collection Cloud Function
│   ├── main.py
│   └── requirements.txt
├── detector/               # Anomaly detection Cloud Function
│   ├── main.py
│   └── requirements.txt
├── shared/                 # Shared utilities
│   ├── bigquery_client.py
│   ├── slack_client.py
│   └── config.py
├── config/
│   └── events_config.json  # Event configuration
├── .env.example           # Environment variables template
├── requirements.txt       # Shared dependencies
├── deploy.sh             # Deployment script
└── README.md
```

## Configuration

### Events Configuration

Edit `config/events_config.json` to manage events:

```json
{
  "events": [
    {
      "name": "impression_error_null_pointer_detected",
      "enabled": true,
      "alert_threshold": 5,
      "alert_channel": "#alerts-errors",
      "time_window_minutes": 1
    },
    {
      "name": "another_event",
      "enabled": true,
      "alert_threshold": 10,
      "alert_channel": "#alerts-general",
      "time_window_minutes": 1
    }
  ]
}
```

- `name`: Mixpanel event name
- `enabled`: Whether to collect and monitor this event
- `alert_threshold`: Maximum events per minute before alerting
- `alert_channel`: Slack channel to send alerts to
- `time_window_minutes`: Time window for anomaly detection

### Environment Variables

Copy `.env.example` to `.env` and configure:

**Required:**
- `MIXPANEL_PROJECT_ID`: Your Mixpanel project ID
- `GCP_PROJECT_ID`: Your GCP project ID
- `SLACK_WEBHOOK_URL`: Slack incoming webhook URL

**Mixpanel API Secret (choose one):**
- `MIXPANEL_API_SECRET_NAME`: Name of secret in Secret Manager (recommended)
- `MIXPANEL_API_SECRET`: Mixpanel API secret as environment variable (less secure)

**Optional:**
- `BIGQUERY_DATASET`: BigQuery dataset name (default: `mixpanel_data`)
- `BIGQUERY_TABLE`: BigQuery table name (default: `mixpanel_events`)
- `EVENTS_CONFIG`: JSON string of events config (alternative to file)
- `EVENTS_CONFIG_GCS_PATH`: GCS path to events config file

**Authentication:**
- The system uses Application Default Credentials (ADC) for BigQuery access
- Cloud Functions automatically use the service account attached to the function
- Ensure the service account has the required IAM roles (see IAM Setup section)

## BigQuery Schema

The system automatically creates the following table:

- `event_timestamp` (TIMESTAMP) - Event time from Mixpanel
- `inserted_at` (TIMESTAMP) - When record was inserted
- `event_name` (STRING) - Event name
- `properties` (JSON) - All event properties from Mixpanel
- `distinct_id` (STRING) - User/distinct ID
- `event_id` (STRING) - Unique event identifier

## Deployment

### Prerequisites

1. Google Cloud SDK installed and configured
2. GCP project with billing enabled
3. Mixpanel API credentials
4. Slack webhook URL

### IAM Setup

Before deploying, ensure the Cloud Functions service account has the necessary permissions:

1. **Get the default service account email:**
   ```bash
   PROJECT_ID="your_gcp_project"
   SERVICE_ACCOUNT="${PROJECT_ID}@appspot.gserviceaccount.com"
   ```

2. **Grant BigQuery permissions:**
   ```bash
   # Grant BigQuery Data Editor role (to insert data)
   gcloud projects add-iam-policy-binding $PROJECT_ID \
       --member="serviceAccount:${SERVICE_ACCOUNT}" \
       --role="roles/bigquery.dataEditor"
   
   # Grant BigQuery Job User role (to run queries)
   gcloud projects add-iam-policy-binding $PROJECT_ID \
       --member="serviceAccount:${SERVICE_ACCOUNT}" \
       --role="roles/bigquery.jobUser"
   
   # Grant BigQuery Data Viewer role (to read data)
   gcloud projects add-iam-policy-binding $PROJECT_ID \
       --member="serviceAccount:${SERVICE_ACCOUNT}" \
       --role="roles/bigquery.dataViewer"
   ```

3. **If using Secret Manager (recommended), grant Secret Manager Secret Accessor:**
   ```bash
   gcloud projects add-iam-policy-binding $PROJECT_ID \
       --member="serviceAccount:${SERVICE_ACCOUNT}" \
       --role="roles/secretmanager.secretAccessor"
   ```

### Secret Manager Setup (Recommended)

For better security, store the Mixpanel API secret in Secret Manager:

1. **Create the secret:**
   ```bash
   echo -n "your_mixpanel_api_secret" | gcloud secrets create mixpanel-api-secret \
       --data-file=- \
       --project=$PROJECT_ID
   ```

2. **Grant access to the service account:**
   ```bash
   gcloud secrets add-iam-policy-binding mixpanel-api-secret \
       --member="serviceAccount:${SERVICE_ACCOUNT}" \
       --role="roles/secretmanager.secretAccessor" \
       --project=$PROJECT_ID
   ```

3. **Use the secret name in deployment:**
   ```bash
   export MIXPANEL_API_SECRET_NAME="mixpanel-api-secret"
   ```

### Deploy to Cloud Functions

1. Set environment variables:
   ```bash
   export MIXPANEL_PROJECT_ID="your_project_id"
   export GCP_PROJECT_ID="your_gcp_project"
   export BIGQUERY_DATASET="mixpanel_data"
   export BIGQUERY_TABLE="mixpanel_events"
   export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
   
   # Option 1: Use Secret Manager (recommended)
   export MIXPANEL_API_SECRET_NAME="mixpanel-api-secret"
   
   # Option 2: Use environment variable (less secure)
   # export MIXPANEL_API_SECRET="your_secret"
   ```

2. Make deploy script executable:
   ```bash
   chmod +x deploy.sh
   ```

3. Run deployment:
   ```bash
   ./deploy.sh
   ```

The script will:
- Deploy both Cloud Functions
- Create Cloud Scheduler jobs:
  - Collector: Runs every 15 minutes
  - Detector: Runs every 5 minutes

**Note**: The system supports both Secret Manager and environment variables for the Mixpanel API secret. Secret Manager is recommended for production deployments.

### Manual Testing

Test the collector:
```bash
curl https://YOUR-REGION-YOUR-PROJECT.cloudfunctions.net/mixpanel-collector
```

Test the detector:
```bash
curl https://YOUR-REGION-YOUR-PROJECT.cloudfunctions.net/mixpanel-detector
```

## Local Development

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install -r collector/requirements.txt
   pip install -r detector/requirements.txt
   ```

2. Set up environment variables (use `.env` file with `python-dotenv`)

3. Test collector locally:
   ```python
   from collector.main import collect_mixpanel_events
   collect_mixpanel_events(None)
   ```

4. Test detector locally:
   ```python
   from detector.main import detect_anomalies
   detect_anomalies(None)
   ```

## How It Works

1. **Collection**: Every 15 minutes, the collector:
   - Reads enabled events from configuration
   - Fetches events from Mixpanel Export API for the last 15 minutes
   - Transforms and stores events in BigQuery

2. **Detection**: Every 5 minutes, the detector:
   - Reads event configurations
   - Queries BigQuery for recent events
   - Groups events by minute
   - Detects minutes exceeding thresholds
   - Sends Slack alerts to configured channels

3. **Alerting**: When threshold is exceeded:
   - Formats rich Slack message with event details
   - Includes sample event data for debugging
   - Provides BigQuery link for investigation
   - Prevents duplicate alerts (5-minute cooldown)

## Adding New Events

1. Edit `config/events_config.json`
2. Add new event entry with desired threshold and channel
3. Redeploy functions (or update `EVENTS_CONFIG` environment variable)
4. The system will automatically start collecting and monitoring

## Troubleshooting

- **No events collected**: 
  - Check Mixpanel API credentials (verify `MIXPANEL_API_SECRET` or `MIXPANEL_API_SECRET_NAME` is set correctly)
  - Verify event names match exactly (case-sensitive)
  - Check Cloud Function logs for authentication errors
  
- **Alerts not sent**: 
  - Verify Slack webhook URL is correct
  - Check channel permissions (webhook must have access to the channel)
  - Review detector function logs for errors
  
- **BigQuery errors**: 
  - Ensure service account has required IAM roles (`roles/bigquery.dataEditor`, `roles/bigquery.jobUser`, `roles/bigquery.dataViewer`)
  - Verify `GCP_PROJECT_ID`, `BIGQUERY_DATASET`, and `BIGQUERY_TABLE` are set correctly
  - Check that the dataset exists or will be created automatically
  
- **Secret Manager errors**:
  - Verify the secret exists: `gcloud secrets list --project=$PROJECT_ID`
  - Check service account has `roles/secretmanager.secretAccessor` role
  - Ensure `MIXPANEL_API_SECRET_NAME` matches the secret name exactly
  
- **Rate limiting**: Mixpanel API has rate limits; the system handles retries automatically

## License

MIT
