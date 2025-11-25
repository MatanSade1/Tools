#!/bin/bash
# Store Mixpanel GDPR Token in Secret Manager

set -e

PROJECT_ID="${GCP_PROJECT_ID:-yotam-395120}"
SECRET_NAME="mixpanel-gdpr-token"

echo "=========================================="
echo "Store Mixpanel GDPR Token"
echo "=========================================="
echo ""
echo "This script will store your Mixpanel GDPR token securely."
echo ""
read -sp "Paste your Mixpanel GDPR Token: " MIXPANEL_TOKEN
echo ""
echo ""

# Validate token format (basic check - not empty)
if [ -z "$MIXPANEL_TOKEN" ]; then
    echo "❌ ERROR: Token cannot be empty"
    exit 1
fi

# Check if gcloud is available
if ! command -v gcloud &> /dev/null; then
    echo "⚠️  gcloud CLI not found. Skipping Secret Manager setup."
    echo ""
    echo "You can set the token as an environment variable instead:"
    echo "  export MIXPANEL_GDPR_TOKEN='$MIXPANEL_TOKEN'"
    echo ""
    echo "Or store it manually later:"
    echo "  echo -n '$MIXPANEL_TOKEN' | gcloud secrets create $SECRET_NAME \\"
    echo "      --data-file=- --project=$PROJECT_ID"
    exit 0
fi

# Check if secret exists
if gcloud secrets describe "$SECRET_NAME" --project="$PROJECT_ID" &>/dev/null 2>&1; then
    echo "Secret '$SECRET_NAME' already exists. Updating..."
    echo -n "$MIXPANEL_TOKEN" | gcloud secrets versions add "$SECRET_NAME" \
        --data-file=- \
        --project="$PROJECT_ID" > /dev/null 2>&1
    echo "✅ Secret updated successfully!"
else
    echo "Creating new secret '$SECRET_NAME'..."
    echo -n "$MIXPANEL_TOKEN" | gcloud secrets create "$SECRET_NAME" \
        --data-file=- \
        --project="$PROJECT_ID" > /dev/null 2>&1
    echo "✅ Secret created successfully!"
fi

echo ""
echo "=========================================="
echo "✅ Token stored successfully!"
echo "=========================================="
echo ""
echo "To use this secret, set:"
echo "  export MIXPANEL_GDPR_TOKEN_NAME='$SECRET_NAME'"
echo ""
echo "Or use environment variable directly:"
echo "  export MIXPANEL_GDPR_TOKEN='$MIXPANEL_TOKEN'"
echo ""

