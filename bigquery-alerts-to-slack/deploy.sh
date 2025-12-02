#!/bin/bash

# Deployment script for bigquery-alerts-to-slack Cloud Run service

set -e

PROJECT_ID="yotam-395120"
REGION="us-central1"
SERVICE_NAME="bigquery-alerts-to-slack"
SERVICE_ACCOUNT="bigquery-alerts-to-slack@yotam-395120.iam.gserviceaccount.com"

echo "🚀 Deploying $SERVICE_NAME to Cloud Run..."
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo ""

# Deploy the service
gcloud run deploy $SERVICE_NAME \
  --source . \
  --region $REGION \
  --project $PROJECT_ID \
  --service-account $SERVICE_ACCOUNT \
  --set-env-vars FUNCTION_TARGET=run_alerts,GUNICORN_TIMEOUT=120 \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --timeout 3600 \
  --max-instances 1 \
  --platform managed

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Service URL:"
gcloud run services describe $SERVICE_NAME \
  --region $REGION \
  --project $PROJECT_ID \
  --format="value(status.url)"

