#!/bin/bash
# Setup GCP authentication for BigQuery

echo "=========================================="
echo "GCP Authentication Setup for BigQuery"
echo "=========================================="
echo ""

# Add gcloud to PATH if it exists
if [ -d "/Users/matansade/google-cloud-sdk/bin" ]; then
    export PATH="/Users/matansade/google-cloud-sdk/bin:$PATH"
fi

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI not found"
    echo ""
    echo "Please install Google Cloud SDK:"
    echo "  https://cloud.google.com/sdk/docs/install"
    echo ""
    echo "Or use a service account key file instead:"
    echo "  export GOOGLE_APPLICATION_CREDENTIALS=\"/path/to/service-account-key.json\""
    exit 1
fi

echo "✅ gcloud CLI found"
echo ""

# Check current project
CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null)
if [ -n "$CURRENT_PROJECT" ]; then
    echo "Current GCP project: $CURRENT_PROJECT"
    read -p "Use this project? (y/n) [y]: " use_current
    if [[ ! "$use_current" =~ ^[Nn]$ ]]; then
        PROJECT_ID="$CURRENT_PROJECT"
    else
        read -p "Enter GCP project ID: " PROJECT_ID
    fi
else
    read -p "Enter GCP project ID [yotam-395120]: " PROJECT_ID
    PROJECT_ID="${PROJECT_ID:-yotam-395120}"
fi

echo ""
echo "Setting up Application Default Credentials..."
echo "This will open a browser for authentication."
echo ""

gcloud auth application-default login --project="$PROJECT_ID"

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✅ Authentication successful!"
    echo "=========================================="
    echo ""
    echo "You can now run the GDPR handler:"
    echo "  ./gdpr-handler/run.sh 2025-11-16 2025-11-17"
    echo ""
else
    echo ""
    echo "❌ Authentication failed"
    echo ""
    echo "Alternative: Use a service account key file"
    echo "  export GOOGLE_APPLICATION_CREDENTIALS=\"/path/to/key.json\""
    exit 1
fi

