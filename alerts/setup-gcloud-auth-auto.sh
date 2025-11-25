#!/bin/bash
# Automatic gcloud authentication setup script

set -e

echo "=========================================="
echo "Automatic Google Cloud Authentication Setup"
echo "=========================================="
echo ""

# Add gcloud to PATH
if [ -d "$HOME/google-cloud-sdk/bin" ]; then
    export PATH="$HOME/google-cloud-sdk/bin:$PATH"
    echo "✅ gcloud found in PATH"
else
    echo "❌ gcloud not found at ~/google-cloud-sdk/bin"
    echo "   Please install gcloud first or update the path"
    exit 1
fi

# Set project
PROJECT_ID="yotam-395120"
echo "Setting GCP project to: $PROJECT_ID"
gcloud config set project $PROJECT_ID --quiet

# Check if already authenticated
echo ""
echo "Checking existing authentication..."
if gcloud auth application-default print-access-token > /dev/null 2>&1; then
    echo "✅ Application Default Credentials already set up!"
    echo ""
    echo "Current authenticated account:"
    gcloud auth application-default print-access-token --format="value(account)" 2>/dev/null || gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -1
    echo ""
    echo "You're all set! You can now:"
    echo "  1. Create the BigQuery table: python3 alerts/create-bigquery-table.py"
    echo "  2. Run the collector locally: python3 alerts/test-local.py"
    exit 0
fi

# Check if user account is authenticated
echo "Checking user authentication..."
if gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    ACTIVE_ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -1)
    echo "✅ Found active account: $ACTIVE_ACCOUNT"
    echo ""
    echo "Setting up Application Default Credentials..."
    echo "This will use your existing gcloud authentication."
    
    # Try to use existing auth to set up ADC
    gcloud auth application-default login --no-launch-browser --quiet 2>&1 || {
        echo ""
        echo "⚠️  Interactive authentication required."
        echo "   Please run this command manually:"
        echo "   gcloud auth application-default login"
        echo ""
        echo "   Or run the interactive script:"
        echo "   ./alerts/setup-gcloud-auth.sh"
        exit 1
    }
else
    echo "❌ No active authentication found."
    echo ""
    echo "Please authenticate first by running:"
    echo "  gcloud auth login"
    echo ""
    echo "Then run this script again, or run:"
    echo "  ./alerts/setup-gcloud-auth.sh"
    exit 1
fi

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
    echo "❌ Authentication verification failed."
    exit 1
fi

