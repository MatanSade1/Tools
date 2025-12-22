#!/bin/bash
#
# Deployment script for MAX Revenue Collector
#
# This script:
# 1. Creates the service account with required permissions
# 2. Stores the API key in Secret Manager
# 3. Creates the BigQuery table (with partitioning)
# 4. Deploys the Cloud Run service
# 5. Creates the Cloud Scheduler job (10 AM UTC daily)
#
# Usage: ./deploy.sh
#

set -e  # Exit on error

# =============================================================================
# Configuration
# =============================================================================

PROJECT_ID="yotam-395120"
PROJECT_NUMBER="57935720907"
REGION="us-central1"

# Service configuration
SERVICE_NAME="max-revenue-collector"
SERVICE_ACCOUNT_NAME="max-revenue-collector"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# Secret Manager
SECRET_NAME="max-api-key"

# BigQuery
BQ_DATASET="peerplay"
BQ_TABLE="max_revenue_data"
BQ_FULL_TABLE="${PROJECT_ID}.${BQ_DATASET}.${BQ_TABLE}"

# Cloud Scheduler
SCHEDULER_JOB_NAME="max-revenue-collector-daily"
SCHEDULER_SCHEDULE="0 10 * * *"  # 10 AM UTC daily

# Image configuration
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

# =============================================================================
# Helper Functions
# =============================================================================

echo_step() {
    echo ""
    echo "============================================================"
    echo "  $1"
    echo "============================================================"
    echo ""
}

check_gcloud() {
    if ! command -v gcloud &> /dev/null; then
        echo "ERROR: gcloud CLI is not installed"
        echo "Please install from: https://cloud.google.com/sdk/docs/install"
        exit 1
    fi
}

# =============================================================================
# Main Deployment
# =============================================================================

echo_step "MAX Revenue Collector Deployment"
echo "Project ID: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "Service: ${SERVICE_NAME}"

check_gcloud

# Set project
gcloud config set project ${PROJECT_ID}

# =============================================================================
# Step 1: Create Service Account
# =============================================================================

echo_step "Step 1: Creating Service Account"

# Check if service account exists
if gcloud iam service-accounts describe ${SERVICE_ACCOUNT_EMAIL} &> /dev/null; then
    echo "Service account ${SERVICE_ACCOUNT_EMAIL} already exists"
else
    echo "Creating service account ${SERVICE_ACCOUNT_NAME}..."
    gcloud iam service-accounts create ${SERVICE_ACCOUNT_NAME} \
        --display-name="MAX Revenue Collector Service Account" \
        --description="Service account for MAX Revenue Collector Cloud Run service"
    echo "Service account created"
fi

# Grant required roles
echo "Granting IAM roles..."

# BigQuery Data Editor - for insert/delete
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
    --role="roles/bigquery.dataEditor" \
    --condition=None \
    --quiet

# BigQuery Job User - for running queries
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
    --role="roles/bigquery.jobUser" \
    --condition=None \
    --quiet

# Secret Manager Secret Accessor - for API key
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
    --role="roles/secretmanager.secretAccessor" \
    --condition=None \
    --quiet

echo "IAM roles granted"

# =============================================================================
# Step 2: Store API Key in Secret Manager
# =============================================================================

echo_step "Step 2: Setting up Secret Manager"

# Check if secret exists
if gcloud secrets describe ${SECRET_NAME} --project=${PROJECT_ID} &> /dev/null; then
    echo "Secret ${SECRET_NAME} already exists"
    echo ""
    echo "To update the secret value, run:"
    echo "  echo -n 'YOUR_API_KEY' | gcloud secrets versions add ${SECRET_NAME} --data-file=-"
else
    echo "Creating secret ${SECRET_NAME}..."
    echo ""
    echo "Please enter the MAX API key (it will not be displayed):"
    read -s MAX_API_KEY
    
    if [ -z "${MAX_API_KEY}" ]; then
        echo "ERROR: API key cannot be empty"
        exit 1
    fi
    
    echo -n "${MAX_API_KEY}" | gcloud secrets create ${SECRET_NAME} \
        --data-file=- \
        --project=${PROJECT_ID}
    
    echo "Secret created successfully"
fi

# Grant service account access to the secret
gcloud secrets add-iam-policy-binding ${SECRET_NAME} \
    --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
    --role="roles/secretmanager.secretAccessor" \
    --project=${PROJECT_ID} \
    --quiet

echo "Secret Manager configured"

# =============================================================================
# Step 3: Create BigQuery Table
# =============================================================================

echo_step "Step 3: Creating BigQuery Table"

# Check if table exists
if bq show ${BQ_FULL_TABLE} &> /dev/null; then
    echo "Table ${BQ_FULL_TABLE} already exists"
else
    echo "Creating table ${BQ_FULL_TABLE} with day partitioning..."
    
    # Create table with schema and partitioning
    bq mk --table \
        --time_partitioning_field=date \
        --time_partitioning_type=DAY \
        --description="MAX User-Level Ad Revenue Data" \
        ${BQ_FULL_TABLE} \
        date:TIMESTAMP,ad_unit_id:STRING,ad_unit_name:STRING,waterfall:STRING,ad_format:STRING,placement:STRING,country:STRING,device_type:STRING,idfa:STRING,idfv:STRING,user_id:STRING,revenue:FLOAT,ad_placement:STRING
    
    echo "Table created successfully"
fi

# =============================================================================
# Step 4: Build and Deploy Cloud Run Service
# =============================================================================

echo_step "Step 4: Building and Deploying Cloud Run Service"

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "${SCRIPT_DIR}"

echo "Building container image..."
gcloud builds submit --tag ${IMAGE_NAME} .

echo "Deploying to Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \
    --image ${IMAGE_NAME} \
    --platform managed \
    --region ${REGION} \
    --service-account ${SERVICE_ACCOUNT_EMAIL} \
    --set-env-vars "GCP_PROJECT_ID=${PROJECT_ID},BIGQUERY_TABLE=${BQ_FULL_TABLE},MAX_API_KEY_SECRET=${SECRET_NAME}" \
    --memory 512Mi \
    --timeout 600 \
    --min-instances 0 \
    --max-instances 1 \
    --no-allow-unauthenticated

echo "Cloud Run service deployed"

# Get the service URL
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
    --platform managed \
    --region ${REGION} \
    --format 'value(status.url)')

echo "Service URL: ${SERVICE_URL}"

# =============================================================================
# Step 5: Create Cloud Scheduler Job
# =============================================================================

echo_step "Step 5: Creating Cloud Scheduler Job"

# Delete existing job if it exists
if gcloud scheduler jobs describe ${SCHEDULER_JOB_NAME} --location=${REGION} &> /dev/null; then
    echo "Deleting existing scheduler job..."
    gcloud scheduler jobs delete ${SCHEDULER_JOB_NAME} --location=${REGION} --quiet
fi

echo "Creating scheduler job: ${SCHEDULER_JOB_NAME}"
echo "Schedule: ${SCHEDULER_SCHEDULE} (10 AM UTC daily)"

gcloud scheduler jobs create http ${SCHEDULER_JOB_NAME} \
    --location=${REGION} \
    --schedule="${SCHEDULER_SCHEDULE}" \
    --uri="${SERVICE_URL}/" \
    --http-method=POST \
    --oidc-service-account-email=${SERVICE_ACCOUNT_EMAIL} \
    --oidc-token-audience=${SERVICE_URL}

echo "Scheduler job created"

# =============================================================================
# Summary
# =============================================================================

echo_step "Deployment Complete!"

echo "Summary:"
echo "  - Service Account: ${SERVICE_ACCOUNT_EMAIL}"
echo "  - Secret: ${SECRET_NAME}"
echo "  - BigQuery Table: ${BQ_FULL_TABLE}"
echo "  - Cloud Run Service: ${SERVICE_NAME}"
echo "  - Cloud Run URL: ${SERVICE_URL}"
echo "  - Scheduler Job: ${SCHEDULER_JOB_NAME}"
echo "  - Schedule: ${SCHEDULER_SCHEDULE} (10 AM UTC daily)"
echo ""
echo "To test the service manually, run:"
echo "  gcloud run services proxy ${SERVICE_NAME} --region=${REGION}"
echo "  curl http://localhost:8080/test"
echo ""
echo "To trigger a manual run:"
echo "  gcloud scheduler jobs run ${SCHEDULER_JOB_NAME} --location=${REGION}"
echo ""
echo "To view logs:"
echo "  gcloud logging read 'resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${SERVICE_NAME}\"' --limit=50"

