#!/bin/bash
# Script to set up gcloud authentication for BigQuery

echo "=========================================="
echo "Setting up Google Cloud Authentication"
echo "=========================================="
echo ""

# Add gcloud to PATH if not already there
if [ -d "$HOME/google-cloud-sdk/bin" ]; then
    export PATH="$HOME/google-cloud-sdk/bin:$PATH"
    echo "✅ Added gcloud to PATH"
else
    echo "❌ gcloud not found. Please install it first."
    exit 1
fi

# Set the project
PROJECT_ID="yotam-395120"
echo "Setting GCP project to: $PROJECT_ID"
gcloud config set project $PROJECT_ID

# Authenticate for Application Default Credentials
echo ""
echo "Setting up Application Default Credentials..."
echo "This will open a browser window for authentication."
echo ""
gcloud auth application-default login

# Verify authentication
echo ""
echo "Verifying authentication..."
if gcloud auth application-default print-access-token > /dev/null 2>&1; then
    echo "✅ Authentication successful!"
    echo ""
    echo "You can now:"
    echo "  1. Create the BigQuery table: python3 alerts/create-bigquery-table.py"
    echo "  2. Run the collector locally: python3 alerts/test-local.py"
else
    echo "❌ Authentication failed. Please try again."
    exit 1
fi

