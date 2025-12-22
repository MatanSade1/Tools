# MAX Revenue Collector

A Cloud Run service that fetches user-level ad revenue data from the AppLovin MAX API and stores it in BigQuery.

## Overview

This service runs daily at 10 AM UTC and:

1. **Deletes** existing data from the last 2 days in BigQuery
2. **Fetches** iOS ad revenue data for the last 2 days from MAX API
3. **Fetches** Android ad revenue data for the last 2 days from MAX API
4. **Inserts** all records into BigQuery

### Why 2 Days?

Fetching and replacing 2 days of data ensures:
- Late-arriving data from the previous day is captured
- Any data corrections are applied
- No gaps in data due to timing issues

## Architecture

```
Cloud Scheduler (10 AM UTC) → Cloud Run Service → BigQuery
                                    ↓
                              AppLovin MAX API
                              (iOS + Android)
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GCP_PROJECT_ID` | Google Cloud project ID | `yotam-395120` |
| `BIGQUERY_TABLE` | Full BigQuery table path | `yotam-395120.peerplay.levelplay_revenue_data` |
| `MAX_API_KEY_SECRET` | Secret Manager secret name | `max-api-key` |
| `MAX_API_KEY` | API key (for local testing only) | - |

### BigQuery Table Schema

| Column | Type | Description |
|--------|------|-------------|
| `date` | TIMESTAMP | Event timestamp (partitioning column) |
| `ad_unit_id` | STRING | Ad unit identifier |
| `ad_unit_name` | STRING | Ad unit name |
| `waterfall` | STRING | Waterfall configuration |
| `ad_format` | STRING | Ad format (BANNER, INTERSTITIAL, etc.) |
| `placement` | STRING | Placement name |
| `country` | STRING | Country code |
| `device_type` | STRING | Device type (PHONE, TABLET) |
| `idfa` | STRING | iOS Identifier for Advertisers |
| `idfv` | STRING | iOS Identifier for Vendors |
| `user_id` | STRING | User identifier |
| `revenue` | FLOAT | Revenue amount |
| `ad_placement` | STRING | Ad placement identifier |

The table is partitioned by `date` for efficient querying.

### Platform Configuration

| Platform | Application | Store ID |
|----------|-------------|----------|
| iOS | com.peerplay.megamerge | 6459056553 |
| Android | com.peerplay.megamerge | com.peerplay.megamerge |

## Deployment

### Prerequisites

- Google Cloud SDK (`gcloud`) installed and authenticated
- `bq` command-line tool (comes with gcloud)
- Sufficient permissions to:
  - Create service accounts
  - Create secrets in Secret Manager
  - Create BigQuery tables
  - Deploy Cloud Run services
  - Create Cloud Scheduler jobs

### Deploy

```bash
# Make script executable
chmod +x deploy.sh

# Run deployment
./deploy.sh
```

The script will:
1. Create a service account with required permissions
2. Store the MAX API key in Secret Manager (prompts for input)
3. Create the BigQuery table with partitioning
4. Build and deploy the Cloud Run service
5. Create a Cloud Scheduler job for 10 AM UTC daily

### Manual Testing

After deployment, test the service:

```bash
# Test configuration
gcloud run services proxy max-revenue-collector --region=us-central1
# In another terminal:
curl http://localhost:8080/test

# Trigger a manual run
gcloud scheduler jobs run max-revenue-collector-daily --location=us-central1
```

## Local Development

### Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export GCP_PROJECT_ID=yotam-395120
export BIGQUERY_TABLE=yotam-395120.peerplay.levelplay_revenue_data
export MAX_API_KEY=your_api_key_here
```

### Run Locally

```bash
# Start the server
python main.py

# Test endpoints
curl http://localhost:8080/health
curl http://localhost:8080/test
curl -X POST http://localhost:8080/
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET/POST | Run the collection process |
| `/health` | GET | Health check |
| `/test` | GET | Validate configuration |

## Monitoring

### View Logs

```bash
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="max-revenue-collector"' --limit=50
```

### Check Scheduler Status

```bash
gcloud scheduler jobs describe max-revenue-collector-daily --location=us-central1
```

### Query Data in BigQuery

```sql
-- Count records by date
SELECT 
  DATE(date) as day,
  COUNT(*) as record_count,
  SUM(revenue) as total_revenue
FROM `yotam-395120.peerplay.levelplay_revenue_data`
GROUP BY 1
ORDER BY 1 DESC
LIMIT 10;

-- Check data by platform (via ad_unit_id patterns)
SELECT 
  DATE(date) as day,
  ad_format,
  country,
  COUNT(*) as impressions,
  SUM(revenue) as revenue
FROM `yotam-395120.peerplay.levelplay_revenue_data`
WHERE DATE(date) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
GROUP BY 1, 2, 3
ORDER BY 1 DESC, 5 DESC;
```

## Troubleshooting

### Common Issues

**API Key Issues**
- Verify the secret exists: `gcloud secrets describe max-api-key`
- Check service account has access: Check IAM bindings on the secret

**BigQuery Errors**
- Ensure service account has `bigquery.dataEditor` and `bigquery.jobUser` roles
- Verify table exists: `bq show yotam-395120:peerplay.levelplay_revenue_data`

**No Data Retrieved**
- Check API key is valid
- Verify application and store_id are correct
- Check date range (last 2 days may have no data if app is new)

**Scheduler Not Running**
- Check scheduler job status: `gcloud scheduler jobs describe max-revenue-collector-daily --location=us-central1`
- Verify service account has Cloud Run Invoker role

### Update API Key

```bash
echo -n 'NEW_API_KEY' | gcloud secrets versions add max-api-key --data-file=-
```

### Redeploy Service

```bash
./deploy.sh  # Safe to run multiple times
```

## Cost Considerations

- **Cloud Run**: Pay per request, ~$0.0000004 per 100ms
- **BigQuery**: Storage ~$0.02/GB/month, Queries ~$5/TB scanned
- **Cloud Scheduler**: Free for up to 3 jobs per month
- **Secret Manager**: Free for up to 10,000 access operations per month

Estimated monthly cost for daily runs: < $1

