# Alerts Project - RT Mixpanel Collector

This project collects Mixpanel events every 15 minutes, stores them in BigQuery, and sends Slack alerts when thresholds are exceeded.

## Quick Setup Verification

Before deploying, verify your GCP setup:

```bash
# Make sure gcloud CLI is installed
# macOS: brew install --cask google-cloud-sdk

# Run verification script
./alerts/verify-gcp-setup.sh
```

The script will:
- ✅ Check if gcloud CLI is installed
- ✅ Verify authentication
- ✅ Check current GCP project
- ✅ Verify all required APIs are enabled
- ✅ Check billing status
- ✅ Optionally enable missing APIs

## Required APIs

The following APIs must be enabled:
- Cloud Functions API (`cloudfunctions.googleapis.com`)
- Cloud Scheduler API (`cloudscheduler.googleapis.com`)
- BigQuery API (`bigquery.googleapis.com`)
- Secret Manager API (`secretmanager.googleapis.com`)

## Manual API Verification

If you prefer to check manually:

```bash
# Check current project
gcloud config get-value project

# List enabled APIs
gcloud services list --enabled

# Enable required APIs
gcloud services enable cloudfunctions.googleapis.com
gcloud services enable cloudscheduler.googleapis.com
gcloud services enable bigquery.googleapis.com
gcloud services enable secretmanager.googleapis.com
```

## Configuration Setup

### Environment Variables

**Required environment variables:**

```bash
export GCP_PROJECT_ID="your-gcp-project-id"
export MIXPANEL_PROJECT_ID="your-mixpanel-project-id"
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```

**Mixpanel API Secret (choose one):**

Option 1 - Secret Manager (recommended):
```bash
export MIXPANEL_API_SECRET_NAME="mixpanel-api-secret"
```

Option 2 - Environment variable (less secure):
```bash
export MIXPANEL_API_SECRET="your-mixpanel-api-secret"
```

**Optional (have defaults):**
```bash
export RT_MP_DATASET="mixpanel_data"    # Default
export RT_MP_TABLE="rt_mp_events"        # Default
export GCP_REGION="us-central1"          # Default
```

### Quick Setup Script

Use the interactive setup script:
```bash
./alerts/setup-env.sh
```

This will create a `.env` file (which is automatically ignored by git).

### Security Notes

⚠️ **IMPORTANT:**
- Never commit secrets to git
- The `.env` file is in `.gitignore` and will NOT be committed
- Use Secret Manager for production deployments
- Keep your Slack webhook URL secure

### Configuration File

Edit `alerts/config/rt_mp_events_config.json` to configure:
- Event names (must match Mixpanel exactly, case-sensitive)
- Alert thresholds (events per hour)
- Slack channels
- Collection frequency

## Next Steps

After verifying APIs are enabled and setting environment variables, proceed with:
1. IAM permissions setup
2. Secret Manager setup (recommended)
3. Deployment

See main README.md for complete deployment instructions.

