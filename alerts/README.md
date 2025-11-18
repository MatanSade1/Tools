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

**⚠️ Important: Mixpanel Authentication Credentials**

Mixpanel has different credential types for different purposes:

1. **Project Token** (`0e73d8fa...`) - Used for tracking/importing events (client-side SDKs)
   - ❌ **Does NOT work** with Export API
   - Used for sending events TO Mixpanel, not reading FROM Mixpanel

2. **Export API Secret** - Used specifically for Export API
   - Get from: Project Settings → Service Accounts → Export API Secret
   - Format: Long alphanumeric string
   - Used with Basic Auth: `auth=(secret, "")`

3. **Service Account** (RECOMMENDED) - Username + Secret pair
   - Get from: Project Settings → Service Accounts → Create Service Account
   - Provides: Username and Secret
   - Used with Basic Auth: `auth=(username, secret)`
   - More secure and recommended by Mixpanel

**To get the correct credentials:**

1. Go to: https://mixpanel.com/project/2991947/settings
2. Navigate to: **Project Settings** → **Service Accounts**
3. **Option A (Recommended)**: Create a Service Account
   - Click "Add Service Account"
   - Copy the **Username** and **Secret**
   - Set environment variables:
     ```bash
     export MIXPANEL_SERVICE_ACCOUNT_USERNAME="your-username"
     export MIXPANEL_SERVICE_ACCOUNT_SECRET="your-secret"
     ```
4. **Option B**: Use Export API Secret
   - Look for "Export API Secret" section
   - Copy the secret
   - Set environment variable:
     ```bash
     export MIXPANEL_API_SECRET="your-export-api-secret"
     ```

**Note**: Project Tokens (like `0e73d8fa8567c5bf2820b408701fa7be`) cannot be used with the Export API.

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

## Local Development

### Quick Start

**Option 1: Use the automated setup script (recommended)**
```bash
./alerts/run-local.sh
```

This script will:
- ✅ Create a virtual environment (if needed)
- ✅ Install all dependencies
- ✅ Check for .env file and create from template if needed
- ✅ Load environment variables
- ✅ Verify GCP authentication
- ✅ Check required environment variables
- ✅ Run the function locally

**Option 2: Manual setup**
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install -r alerts/rt-mp-collector/requirements.txt

# Set up environment variables
source .env  # or export them manually

# Authenticate with GCP (required for BigQuery access)
gcloud auth application-default login

# Run the function
python3 alerts/test-local.py
```

**Option 3: Direct Python call**
```python
from alerts.rt_mp_collector.main import rt_mp_collector
result = rt_mp_collector(None)
print(result)
```

### Prerequisites for Local Development

- Python 3.8 or higher
- Google Cloud SDK installed and authenticated
- Environment variables set (via .env file or exports)
- GCP Application Default Credentials configured (`gcloud auth application-default login`)

### Local Testing Notes

⚠️ **Important:** When running locally:
- Events will be stored in your **actual** BigQuery table
- Slack alerts will be sent to your **actual** configured channel
- Use test channels/thresholds during development to avoid spam
- Consider temporarily disabling events in config (`"enabled": false`) for testing

### Troubleshooting Local Development

**Import errors:**
- Make sure you're in the project root directory
- Ensure virtual environment is activated
- Check that all dependencies are installed

**GCP authentication errors:**
- Run: `gcloud auth application-default login`
- Verify: `gcloud auth application-default print-access-token`

**BigQuery permission errors:**
- Ensure your user account has BigQuery permissions
- Check: `gcloud projects get-iam-policy yotam-395120`

**Environment variable errors:**
- Verify .env file exists and has correct values
- Check: `source .env && echo $GCP_PROJECT_ID`

## Next Steps

After verifying APIs are enabled and setting environment variables, proceed with:
1. IAM permissions setup
2. Secret Manager setup (recommended)
3. Deployment

See main README.md for complete deployment instructions.

