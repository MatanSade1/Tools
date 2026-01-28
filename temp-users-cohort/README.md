# Temp Users Cohort Service

A Cloud Run service that identifies temp users (users who had `impression_privacy` followed by `impression_restore_user_state_by_device_id` within 2 minutes on the same Android device) and updates Mixpanel cohorts.

## Overview

This service runs daily to:
1. **Scan the last 2 days** of events to identify temp users
2. **Insert new temp users** into `peerplay.state_loss_temp_users` table
3. **Update Mixpanel** user profiles with cohort marker `state_loss_temp_user_cohort_v1`

## Architecture

- **Cloud Run** service with Flask endpoint
- **BigQuery** for data storage and queries
- **Mixpanel API** for cohort updates
- **Slack** for error alerts
- **Cloud Scheduler** for daily execution (11:00 UTC)

## Temp User Detection Logic

A temp user is identified when:
- User has `impression_privacy` event
- Followed by `impression_restore_user_state_by_device_id` event within 2 minutes
- Both events occur on the same `device_id`
- User is on Android platform (`mp_os='Android'`)
- User's `distinct_id` is not already in `state_loss_temp_users` table

## Table Structure

The `state_loss_temp_users` table contains:
- `distinct_id` (STRING) - Unique user identifier

## Mixpanel Cohort Marker

The service sets the following Mixpanel user profile properties:
- `state_loss_temp_user_cohort_marker`: `state_loss_temp_user_cohort_v1`
- `state_loss_last_updated`: Timestamp of last update

## Configuration

### Environment Variables

- `GCP_PROJECT_ID`: GCP project ID (default: `yotam-395120`)
- `MIXPANEL_PROJECT_TOKEN`: Mixpanel project token (hardcoded: `0e73d8fa8567c5bf2820b408701fa7be`)
- `COHORT_MARKER`: Cohort marker value (default: `state_loss_temp_user_cohort_v1`)

### Service Account

Uses the same service account as fraudsters-management:
- `bigquery-alerts-to-slack@yotam-395120.iam.gserviceaccount.com`

Required permissions:
- BigQuery Data Editor
- BigQuery Job User
- BigQuery Data Viewer

## Deployment

### Prerequisites

1. Google Cloud SDK installed and configured
2. GCP project with billing enabled
3. Service account with required permissions
4. Slack webhook URL configured in shared config

### Deploy to Cloud Run

1. Navigate to the service directory:
   ```bash
   cd /Users/matansade/Tools/temp-users-cohort
   ```

2. Run the deployment script:
   ```bash
   ./deploy.sh
   ```

The script will:
- Deploy the Cloud Run service
- Create/update Cloud Scheduler job for daily execution at 11:00 UTC
- Configure memory (512Mi) and timeout (600s)

### Manual Deployment

```bash
gcloud run deploy temp-users-cohort \
  --source . \
  --region us-central1 \
  --project yotam-395120 \
  --service-account bigquery-alerts-to-slack@yotam-395120.iam.gserviceaccount.com \
  --set-env-vars GCP_PROJECT_ID=yotam-395120 \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --timeout 600 \
  --max-instances 1
```

## Local Development

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up environment variables (use `.env` file or export)

3. Run locally:
   ```bash
   python main.py
   ```

4. Test the endpoint:
   ```bash
   curl http://localhost:8080/
   ```

## Service Endpoints

### GET/POST `/`

Main endpoint that triggers the temp users cohort process.

**Response:**
```json
{
  "success": true,
  "run_id": "uuid",
  "steps": [
    {
      "step": "Step 1",
      "success": true,
      "result": {
        "step": 1,
        "inserted_count": 42
      }
    },
    {
      "step": "Step 2",
      "success": true,
      "result": {
        "step": 2,
        "updated_count": 1000
      }
    }
  ],
  "start_time": "2025-12-30T11:00:00",
  "end_time": "2025-12-30T11:05:00",
  "timestamp": "2025-12-30T11:05:00"
}
```

## Monitoring

### Cloud Logging

View logs in Cloud Console:
```
https://console.cloud.google.com/logs/query?project=yotam-395120&query=resource.type%3D%22cloud_run_revision%22%20resource.labels.service_name%3D%22temp-users-cohort%22
```

### Process Audit Log

The service logs all steps to `peerplay.process_audit_log` table:
- Process name: `temp_users_cohort`
- Logs: `start_step_1`, `end_step_1`, `start_step_2`, `end_step_2`

### Error Alerts

Errors are automatically sent to Slack via the `matan-coralogix-alerts` webhook.

## Troubleshooting

### No temp users found
- Check if there are any `impression_privacy` events in the last 2 days
- Verify Android filter (`mp_os='Android'`) is correct
- Check device_id matching logic

### Mixpanel update failures
- Verify Mixpanel API token is correct
- Check rate limits (service uses 1 second delay between batches)
- Review Mixpanel API response in logs

### BigQuery errors
- Verify service account has required permissions
- Check table `state_loss_temp_users` exists and has correct schema
- Review query execution logs

## Related Services

- **fraudsters-management**: Similar service for fraudster detection and cohort management
- Uses same service account and deployment pattern

## Future Enhancements

- Daily alert for users in table who were active yesterday
- Automatic removal of active users from table
- Dashboard exclusions (to be handled manually)



