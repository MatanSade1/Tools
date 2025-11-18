#!/bin/bash
# Deployment script for Mixpanel to BigQuery Alert System

set -e

PROJECT_ID=${GCP_PROJECT_ID:-$(gcloud config get-value project)}
REGION=${GCP_REGION:-us-central1}

echo "Deploying to project: $PROJECT_ID"
echo "Region: $REGION"

# Create temporary directories with shared code
TMP_DIR=$(mktemp -d)
echo "Using temp directory: $TMP_DIR"

# Function to prepare function directory
prepare_function() {
    local func_name=$1
    local func_dir="$TMP_DIR/$func_name"
    mkdir -p "$func_dir"
    
    # Copy function files
    cp -r "./$func_name"/* "$func_dir/" 2>/dev/null || true
    
    # Copy shared directory
    cp -r ./shared "$func_dir/"
    
    # Copy config directory
    mkdir -p "$func_dir/config"
    cp -r ./config/* "$func_dir/config/" 2>/dev/null || true
    
    echo "$func_dir"
}

# Prepare collector
COLLECTOR_DIR=$(prepare_function "collector")
echo "Prepared collector in: $COLLECTOR_DIR"

# Build environment variables for collector
COLLECTOR_ENV_VARS="MIXPANEL_PROJECT_ID=$MIXPANEL_PROJECT_ID,GCP_PROJECT_ID=$PROJECT_ID,BIGQUERY_DATASET=$BIGQUERY_DATASET,BIGQUERY_TABLE=$BIGQUERY_TABLE"

# Add Mixpanel secret (either from env var or Secret Manager name)
if [ -n "$MIXPANEL_API_SECRET_NAME" ]; then
    COLLECTOR_ENV_VARS="$COLLECTOR_ENV_VARS,MIXPANEL_API_SECRET_NAME=$MIXPANEL_API_SECRET_NAME"
    echo "Using Secret Manager for Mixpanel API secret: $MIXPANEL_API_SECRET_NAME"
elif [ -n "$MIXPANEL_API_SECRET" ]; then
    COLLECTOR_ENV_VARS="$COLLECTOR_ENV_VARS,MIXPANEL_API_SECRET=$MIXPANEL_API_SECRET"
    echo "Using environment variable for Mixpanel API secret"
else
    echo "Warning: No Mixpanel API secret configured (set MIXPANEL_API_SECRET or MIXPANEL_API_SECRET_NAME)"
fi

# Deploy Collector Function
echo "Deploying Collector Function..."
gcloud functions deploy mixpanel-collector \
    --gen2 \
    --runtime=python311 \
    --region=$REGION \
    --source="$COLLECTOR_DIR" \
    --entry-point=collect_mixpanel_events \
    --trigger-http \
    --allow-unauthenticated \
    --set-env-vars="$COLLECTOR_ENV_VARS" \
    --memory=512MB \
    --timeout=540s \
    --max-instances=10

# Prepare detector
DETECTOR_DIR=$(prepare_function "detector")
echo "Prepared detector in: $DETECTOR_DIR"

# Deploy Detector Function
echo "Deploying Detector Function..."
gcloud functions deploy mixpanel-detector \
    --gen2 \
    --runtime=python311 \
    --region=$REGION \
    --source="$DETECTOR_DIR" \
    --entry-point=detect_anomalies \
    --trigger-http \
    --allow-unauthenticated \
    --set-env-vars="GCP_PROJECT_ID=$PROJECT_ID,BIGQUERY_DATASET=$BIGQUERY_DATASET,BIGQUERY_TABLE=$BIGQUERY_TABLE,SLACK_WEBHOOK_URL=$SLACK_WEBHOOK_URL" \
    --memory=256MB \
    --timeout=300s \
    --max-instances=5

# Prepare rt-alerts-tool
RT_ALERTS_DIR=$(prepare_function "rt-alerts-tool")
echo "Prepared rt-alerts-tool in: $RT_ALERTS_DIR"

# Build environment variables for rt-alerts-tool
RT_ALERTS_ENV_VARS="MIXPANEL_PROJECT_ID=$MIXPANEL_PROJECT_ID,GCP_PROJECT_ID=$PROJECT_ID,SLACK_WEBHOOK_URL=$SLACK_WEBHOOK_URL"

# Add Mixpanel secret (either from env var or Secret Manager name)
if [ -n "$MIXPANEL_API_SECRET_NAME" ]; then
    RT_ALERTS_ENV_VARS="$RT_ALERTS_ENV_VARS,MIXPANEL_API_SECRET_NAME=$MIXPANEL_API_SECRET_NAME"
elif [ -n "$MIXPANEL_API_SECRET" ]; then
    RT_ALERTS_ENV_VARS="$RT_ALERTS_ENV_VARS,MIXPANEL_API_SECRET=$MIXPANEL_API_SECRET"
fi

# Deploy RT Alerts Tool Function
echo "Deploying RT Alerts Tool Function..."
gcloud functions deploy rt-alerts-tool \
    --gen2 \
    --runtime=python311 \
    --region=$REGION \
    --source="$RT_ALERTS_DIR" \
    --entry-point=rt_alerts_tool \
    --trigger-http \
    --allow-unauthenticated \
    --set-env-vars="$RT_ALERTS_ENV_VARS" \
    --memory=256MB \
    --timeout=60s \
    --max-instances=10

# Get function URLs
COLLECTOR_URL=$(gcloud functions describe mixpanel-collector --gen2 --region=$REGION --format="value(serviceConfig.uri)")
DETECTOR_URL=$(gcloud functions describe mixpanel-detector --gen2 --region=$REGION --format="value(serviceConfig.uri)")
RT_ALERTS_URL=$(gcloud functions describe rt-alerts-tool --gen2 --region=$REGION --format="value(serviceConfig.uri)")

echo "Collector URL: $COLLECTOR_URL"
echo "Detector URL: $DETECTOR_URL"
echo "RT Alerts Tool URL: $RT_ALERTS_URL"

# Create Cloud Scheduler jobs
echo "Creating Cloud Scheduler jobs..."

# Collector: Every 15 minutes
gcloud scheduler jobs create http mixpanel-collector-job \
    --location=$REGION \
    --schedule="*/15 * * * *" \
    --uri="$COLLECTOR_URL" \
    --http-method=GET \
    --time-zone="UTC" \
    --attempt-deadline=600s \
    || echo "Collector job may already exist"

# Detector: Every 5 minutes
gcloud scheduler jobs create http mixpanel-detector-job \
    --location=$REGION \
    --schedule="*/5 * * * *" \
    --uri="$DETECTOR_URL" \
    --http-method=GET \
    --time-zone="UTC" \
    --attempt-deadline=300s \
    || echo "Detector job may already exist"

# RT Alerts Tool: Every 2 minutes (near real-time)
gcloud scheduler jobs create http rt-alerts-tool-job \
    --location=$REGION \
    --schedule="*/2 * * * *" \
    --uri="$RT_ALERTS_URL" \
    --http-method=GET \
    --time-zone="UTC" \
    --attempt-deadline=120s \
    || echo "RT Alerts Tool job may already exist"

# Prepare rt-mp-collector (from alerts project)
RT_MP_COLLECTOR_DIR="$TMP_DIR/rt-mp-collector"
mkdir -p "$RT_MP_COLLECTOR_DIR"

# Copy function files from alerts/rt-mp-collector
cp -r "./alerts/rt-mp-collector"/* "$RT_MP_COLLECTOR_DIR/" 2>/dev/null || true

# Copy shared directory
cp -r ./shared "$RT_MP_COLLECTOR_DIR/"

# Copy alerts config directory
mkdir -p "$RT_MP_COLLECTOR_DIR/config"
cp -r ./alerts/config/* "$RT_MP_COLLECTOR_DIR/config/" 2>/dev/null || true

# Also copy main config directory (for backward compatibility)
cp -r ./config/* "$RT_MP_COLLECTOR_DIR/config/" 2>/dev/null || true

echo "Prepared rt-mp-collector in: $RT_MP_COLLECTOR_DIR"

# Build environment variables for rt-mp-collector
RT_MP_COLLECTOR_ENV_VARS="MIXPANEL_PROJECT_ID=$MIXPANEL_PROJECT_ID,GCP_PROJECT_ID=$PROJECT_ID,SLACK_WEBHOOK_URL=$SLACK_WEBHOOK_URL"

# Add RT table config (defaults to mixpanel_data.rt_mp_events)
RT_MP_DATASET=${RT_MP_DATASET:-mixpanel_data}
RT_MP_TABLE=${RT_MP_TABLE:-rt_mp_events}
RT_MP_COLLECTOR_ENV_VARS="$RT_MP_COLLECTOR_ENV_VARS,RT_MP_DATASET=$RT_MP_DATASET,RT_MP_TABLE=$RT_MP_TABLE"

# Add Mixpanel secret (either from env var or Secret Manager name)
if [ -n "$MIXPANEL_API_SECRET_NAME" ]; then
    RT_MP_COLLECTOR_ENV_VARS="$RT_MP_COLLECTOR_ENV_VARS,MIXPANEL_API_SECRET_NAME=$MIXPANEL_API_SECRET_NAME"
elif [ -n "$MIXPANEL_API_SECRET" ]; then
    RT_MP_COLLECTOR_ENV_VARS="$RT_MP_COLLECTOR_ENV_VARS,MIXPANEL_API_SECRET=$MIXPANEL_API_SECRET"
fi

# Deploy RT MP Collector Function
echo "Deploying RT MP Collector Function..."
gcloud functions deploy rt-mp-collector \
    --gen2 \
    --runtime=python311 \
    --region=$REGION \
    --source="$RT_MP_COLLECTOR_DIR" \
    --entry-point=rt_mp_collector \
    --trigger-http \
    --allow-unauthenticated \
    --set-env-vars="$RT_MP_COLLECTOR_ENV_VARS" \
    --memory=512MB \
    --timeout=540s \
    --max-instances=10

# Get RT MP Collector URL
RT_MP_COLLECTOR_URL=$(gcloud functions describe rt-mp-collector --gen2 --region=$REGION --format="value(serviceConfig.uri)")
echo "RT MP Collector URL: $RT_MP_COLLECTOR_URL"

# RT MP Collector: Every 15 minutes
gcloud scheduler jobs create http rt-mp-collector-job \
    --location=$REGION \
    --schedule="*/15 * * * *" \
    --uri="$RT_MP_COLLECTOR_URL" \
    --http-method=GET \
    --time-zone="UTC" \
    --attempt-deadline=600s \
    || echo "RT MP Collector job may already exist"

# Cleanup
rm -rf "$TMP_DIR"

echo "Deployment complete!"
echo ""
echo "Next steps:"
echo "1. Update events configuration in config/events_config.json or set EVENTS_CONFIG env var"
echo "2. Ensure service account has BigQuery permissions"
echo "3. Test functions manually or wait for scheduled runs"

