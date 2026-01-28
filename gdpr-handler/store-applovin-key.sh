#!/bin/bash
# Store AppLovin Max GDPR API Key in Secret Manager

set -e

PROJECT_ID="${GCP_PROJECT_ID:-yotam-395120}"
SECRET_NAME="applovin-gdpr-api-key"

echo "=========================================="
echo "Store AppLovin Max GDPR API Key"
echo "=========================================="
echo ""
echo "This script will store your AppLovin Max GDPR API key securely."
echo ""
read -sp "Paste your AppLovin Max GDPR API Key: " APPLOVIN_KEY
echo ""
echo ""

# Validate key format (basic check - not empty)
if [ -z "$APPLOVIN_KEY" ]; then
    echo "❌ ERROR: API key cannot be empty"
    exit 1
fi

# Check if gcloud is available
if ! command -v gcloud &> /dev/null; then
    echo "⚠️  gcloud CLI not found. Skipping Secret Manager setup."
    echo ""
    echo "You can set the key as an environment variable instead:"
    echo "  export APPLOVIN_GDPR_API_KEY='$APPLOVIN_KEY'"
    echo ""
    echo "Or store it manually later:"
    echo "  echo -n '$APPLOVIN_KEY' | gcloud secrets create $SECRET_NAME \\"
    echo "      --data-file=- --project=$PROJECT_ID"
    exit 0
fi

# Check if secret exists
if gcloud secrets describe "$SECRET_NAME" --project="$PROJECT_ID" &>/dev/null 2>&1; then
    echo "Secret '$SECRET_NAME' already exists. Updating..."
    echo -n "$APPLOVIN_KEY" | gcloud secrets versions add "$SECRET_NAME" \
        --data-file=- \
        --project="$PROJECT_ID" > /dev/null 2>&1
    echo "✅ Secret updated successfully!"
else
    echo "Creating new secret '$SECRET_NAME'..."
    echo -n "$APPLOVIN_KEY" | gcloud secrets create "$SECRET_NAME" \
        --data-file=- \
        --project="$PROJECT_ID" > /dev/null 2>&1
    echo "✅ Secret created successfully!"
fi

echo ""
echo "=========================================="
echo "✅ API key stored successfully!"
echo "=========================================="
echo ""
echo "To use this secret, set:"
echo "  export APPLOVIN_GDPR_API_KEY_NAME='$SECRET_NAME'"
echo ""
echo "Or use environment variable directly:"
echo "  export APPLOVIN_GDPR_API_KEY='$APPLOVIN_KEY'"
echo ""

