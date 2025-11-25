#!/bin/bash
# One-step gcloud authentication setup - minimal manual interaction required

set -e

echo "=========================================="
echo "Google Cloud Authentication Setup"
echo "=========================================="
echo ""

# Add gcloud to PATH
export PATH="$HOME/google-cloud-sdk/bin:$PATH"

# Verify gcloud is available
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud not found. Please install it first."
    exit 1
fi

# Set project
PROJECT_ID="yotam-395120"
echo "✅ Setting GCP project to: $PROJECT_ID"
gcloud config set project $PROJECT_ID --quiet

# Check if already authenticated
if gcloud auth application-default print-access-token > /dev/null 2>&1; then
    echo "✅ Application Default Credentials already configured!"
    echo ""
    echo "You're all set! You can now:"
    echo "  1. Create the BigQuery table: python3 alerts/create-bigquery-table.py"
    echo "  2. Run the collector locally: python3 alerts/test-local.py"
    exit 0
fi

# Set up Application Default Credentials
echo ""
echo "Setting up Application Default Credentials..."
echo "This will open your browser for authentication."
echo ""
echo "📋 Instructions:"
echo "   1. A browser window will open"
echo "   2. Sign in with your Google account"
echo "   3. Click 'Allow' to grant permissions"
echo "   4. Copy the verification code shown"
echo "   5. Paste it here when prompted"
echo ""
read -p "Press Enter to continue and open browser..."
echo ""

# Open browser and authenticate
gcloud auth application-default login

# Verify
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

