#!/bin/bash
#
# Deployment script for UA Cohort Query Tool
#
# This script:
# 1. Creates the service account with required permissions
# 2. Stores secrets in Secret Manager (Claude API key, Slack tokens)
# 3. Deploys the Cloud Run service
#
# Usage: ./deploy.sh
#
# Prerequisites:
# - gcloud CLI installed and authenticated
# - You have the Claude API key ready
# - You have created a Slack app (see README.md)
#

set -e  # Exit on error

# =============================================================================
# Configuration
# =============================================================================

PROJECT_ID="yotam-395120"
PROJECT_NUMBER="57935720907"
REGION="us-central1"

# Service configuration
SERVICE_NAME="ua-cohort-query"
SERVICE_ACCOUNT_NAME="ua-cohort-query"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# Secret Manager
CLAUDE_API_KEY_SECRET="claude-api-key"
SLACK_BOT_TOKEN_SECRET="ua-cohort-slack-bot-token"
SLACK_SIGNING_SECRET="ua-cohort-slack-signing-secret"

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

create_secret_if_not_exists() {
    local secret_name=$1
    local secret_description=$2
    
    if gcloud secrets describe ${secret_name} --project=${PROJECT_ID} &> /dev/null; then
        echo "Secret ${secret_name} already exists"
        echo ""
        echo "To update the secret value, run:"
        echo "  echo -n 'YOUR_VALUE' | gcloud secrets versions add ${secret_name} --data-file=-"
    else
        echo "Creating secret ${secret_name}..."
        echo ""
        echo "${secret_description}"
        read -s SECRET_VALUE
        echo ""
        
        if [ -z "${SECRET_VALUE}" ]; then
            echo "WARNING: Secret value was empty, skipping..."
            return
        fi
        
        echo -n "${SECRET_VALUE}" | gcloud secrets create ${secret_name} \
            --data-file=- \
            --project=${PROJECT_ID}
        
        echo "Secret created successfully"
    fi
    
    # Grant service account access to the secret
    gcloud secrets add-iam-policy-binding ${secret_name} \
        --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
        --role="roles/secretmanager.secretAccessor" \
        --project=${PROJECT_ID} \
        --quiet 2>/dev/null || true
}

# =============================================================================
# Main Deployment
# =============================================================================

echo_step "UA Cohort Query Tool Deployment"
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
        --display-name="UA Cohort Query Service Account" \
        --description="Service account for UA Cohort Query Slack tool"
    echo "Service account created"
fi

# Grant required roles
echo "Granting IAM roles..."

# BigQuery Data Viewer - for SELECT queries only
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
    --role="roles/bigquery.dataViewer" \
    --condition=None \
    --quiet

# BigQuery Job User - for running queries
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
    --role="roles/bigquery.jobUser" \
    --condition=None \
    --quiet

# Secret Manager Secret Accessor - for API keys
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
    --role="roles/secretmanager.secretAccessor" \
    --condition=None \
    --quiet

echo "IAM roles granted"

# =============================================================================
# Step 2: Store Secrets in Secret Manager
# =============================================================================

echo_step "Step 2: Setting up Secret Manager"

echo "Setting up Claude API key..."
create_secret_if_not_exists "${CLAUDE_API_KEY_SECRET}" "Please enter the Claude API key (it will not be displayed):"

echo ""
echo "Setting up Slack Bot Token..."
create_secret_if_not_exists "${SLACK_BOT_TOKEN_SECRET}" "Please enter the Slack Bot Token (starts with xoxb-):"

echo ""
echo "Setting up Slack Signing Secret..."
create_secret_if_not_exists "${SLACK_SIGNING_SECRET}" "Please enter the Slack Signing Secret:"

echo ""
echo "Secret Manager configured"

# =============================================================================
# Step 3: Build and Deploy Cloud Run Service
# =============================================================================

echo_step "Step 3: Building and Deploying Cloud Run Service"

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
    --set-env-vars "GCP_PROJECT_ID=${PROJECT_ID},CLAUDE_API_KEY_SECRET=${CLAUDE_API_KEY_SECRET},SLACK_BOT_TOKEN_SECRET=${SLACK_BOT_TOKEN_SECRET},SLACK_SIGNING_SECRET_NAME=${SLACK_SIGNING_SECRET}" \
    --memory 512Mi \
    --timeout 300 \
    --min-instances 0 \
    --max-instances 10 \
    --allow-unauthenticated

echo "Cloud Run service deployed"

# Get the service URL
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
    --platform managed \
    --region ${REGION} \
    --format 'value(status.url)')

echo "Service URL: ${SERVICE_URL}"

# =============================================================================
# Summary
# =============================================================================

echo_step "Deployment Complete!"

echo "Summary:"
echo "  - Service Account: ${SERVICE_ACCOUNT_EMAIL}"
echo "  - Cloud Run Service: ${SERVICE_NAME}"
echo "  - Cloud Run URL: ${SERVICE_URL}"
echo ""
echo "============================================================"
echo "NEXT STEPS: Configure Slack App"
echo "============================================================"
echo ""
echo "1. Go to your Slack app settings: https://api.slack.com/apps"
echo ""
echo "2. Navigate to 'Slash Commands' and create a new command:"
echo "   - Command: /uacohort"
echo "   - Request URL: ${SERVICE_URL}/slack/command"
echo "   - Short Description: Query UA cohort data"
echo "   - Usage Hint: [your question about UA data]"
echo ""
echo "3. Make sure your app has the following OAuth scopes:"
echo "   - chat:write"
echo "   - files:write"
echo "   - commands"
echo ""
echo "4. Install the app to your workspace"
echo ""
echo "============================================================"
echo "TESTING"
echo "============================================================"
echo ""
echo "To test the service without Slack:"
echo "  curl '${SERVICE_URL}/test?q=Give%20me%20the%20total%20cost%20for%20January%202024'"
echo ""
echo "To view logs:"
echo "  gcloud logging read 'resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${SERVICE_NAME}\"' --limit=50"
echo ""



