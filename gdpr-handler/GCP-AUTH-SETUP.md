# GCP Authentication Setup for BigQuery

The GDPR handler needs GCP authentication to write to BigQuery. You have two options:

## Option 1: Install Google Cloud SDK (Recommended)

### Step 1: Install gcloud CLI

**On macOS:**
```bash
# Using Homebrew
brew install --cask google-cloud-sdk

# Or download from:
# https://cloud.google.com/sdk/docs/install
```

### Step 2: Authenticate

```bash
gcloud auth application-default login --project=yotam-395120
```

This will:
- Open a browser for authentication
- Store credentials locally
- Allow the script to access BigQuery

### Step 3: Verify

```bash
gcloud auth application-default print-access-token
```

If you see a token, authentication is working!

## Option 2: Use Service Account Key File

If you have a service account JSON key file:

### Step 1: Set environment variable

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your-service-account-key.json"
```

### Step 2: Add to your .env file (optional)

Add this line to `gdpr-handler/.env`:
```
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your-service-account-key.json
```

### Step 3: Verify

The script will automatically use this credential file.

## Quick Setup Script

If gcloud is installed, you can use:

```bash
./gdpr-handler/setup-gcp-auth.sh
```

## Required Permissions

The service account or your user account needs these BigQuery permissions:
- `roles/bigquery.dataEditor` - To insert data
- `roles/bigquery.jobUser` - To run queries
- `roles/bigquery.dataViewer` - To read data (optional)

## Troubleshooting

### "Your default credentials were not found"
- Make sure you've run `gcloud auth application-default login`
- Or set `GOOGLE_APPLICATION_CREDENTIALS` environment variable

### "Permission denied"
- Check that your account has BigQuery permissions
- Verify the project ID is correct: `yotam-395120`

### "Table not found"
- The table will be created automatically on first insert
- Make sure you have permission to create tables in the `peerplay` dataset

## Test Authentication

After setting up, test with:

```bash
python3 -c "
from google.cloud import bigquery
client = bigquery.Client(project='yotam-395120')
print('✅ Authentication working!')
"
```

