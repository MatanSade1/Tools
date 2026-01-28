#!/bin/bash

# Deployment script for temp-users-cohort Cloud Run service

set -e

PROJECT_ID="yotam-395120"
REGION="us-central1"
SERVICE_NAME="temp-users-cohort"
SERVICE_ACCOUNT="bigquery-alerts-to-slack@yotam-395120.iam.gserviceaccount.com"

echo "🚀 Deploying $SERVICE_NAME to Cloud Run..."
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo ""

# Check if service account exists
echo "Checking service account..."
if ! gcloud iam service-accounts describe $SERVICE_ACCOUNT --project=$PROJECT_ID &>/dev/null; then
    echo "Error: Service account $SERVICE_ACCOUNT does not exist"
    exit 1
else
    echo "Service account $SERVICE_ACCOUNT exists"
fi

# Deploy the service
echo ""
echo "Deploying Cloud Run service..."
gcloud run deploy $SERVICE_NAME \
  --source . \
  --region $REGION \
  --project $PROJECT_ID \
  --service-account $SERVICE_ACCOUNT \
  --set-env-vars GCP_PROJECT_ID=$PROJECT_ID \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --timeout 600 \
  --max-instances 1 \
  --platform managed

echo ""
echo "✅ Deployment complete!"
echo ""

# Get service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
  --region $REGION \
  --project $PROJECT_ID \
  --format="value(status.url)")

echo "Service URL: $SERVICE_URL"
echo ""

# Create or update Cloud Scheduler job
echo "Setting up Cloud Scheduler job..."
SCHEDULER_JOB_NAME="temp-users-cohort-daily"

# Check if job exists
if gcloud scheduler jobs describe $SCHEDULER_JOB_NAME --location=$REGION --project=$PROJECT_ID &>/dev/null; then
    echo "Updating existing scheduler job..."
    gcloud scheduler jobs update http $SCHEDULER_JOB_NAME \
        --location=$REGION \
        --schedule="0 11 * * *" \
        --uri="$SERVICE_URL" \
        --http-method=POST \
        --time-zone="UTC" \
        --attempt-deadline=600s \
        --project=$PROJECT_ID
else
    echo "Creating new scheduler job..."
    gcloud scheduler jobs create http $SCHEDULER_JOB_NAME \
        --location=$REGION \
        --schedule="0 11 * * *" \
        --uri="$SERVICE_URL" \
        --http-method=POST \
        --time-zone="UTC" \
        --attempt-deadline=600s \
        --project=$PROJECT_ID
fi

echo ""
echo "✅ Cloud Scheduler job configured:"
echo "   Name: $SCHEDULER_JOB_NAME"
echo "   Schedule: 0 11 * * * (11AM UTC daily)"
echo "   URL: $SERVICE_URL"
echo ""
echo "🎉 All done! Service is scheduled to run daily at 11AM UTC"

