#!/bin/bash
# Script to create AppLovin GDPR API Key secret in Secret Manager
# Requires: secretmanager.secrets.create permission

set -e

PROJECT_ID="${GCP_PROJECT_ID:-yotam-395120}"
SECRET_NAME="applovin-gdpr-api-key"
APPLOVIN_KEY="hDzo5Mpi16NVLw63p6aHxytQoPbKza2NumUcK_GRkdPbCBZOPmTmf0qtsZ06Xb1REcLirNWAEFyTQSzWtP_JTW"

echo "=========================================="
echo "Creating AppLovin GDPR API Key Secret"
echo "=========================================="
echo ""
echo "Project: $PROJECT_ID"
echo "Secret Name: $SECRET_NAME"
echo ""

# Check if secret already exists
if gcloud secrets describe "$SECRET_NAME" --project="$PROJECT_ID" &>/dev/null 2>&1; then
    echo "Secret '$SECRET_NAME' already exists. Updating with new version..."
    echo -n "$APPLOVIN_KEY" | gcloud secrets versions add "$SECRET_NAME" \
        --data-file=- \
        --project="$PROJECT_ID"
    echo "✅ Secret updated successfully!"
else
    echo "Creating new secret '$SECRET_NAME'..."
    echo -n "$APPLOVIN_KEY" | gcloud secrets create "$SECRET_NAME" \
        --data-file=- \
        --project="$PROJECT_ID"
    echo "✅ Secret created successfully!"
fi

echo ""
echo "=========================================="
echo "✅ Secret created/updated!"
echo "=========================================="
echo ""
echo "To use this secret, set:"
echo "  export APPLOVIN_GDPR_API_KEY_NAME='$SECRET_NAME'"
echo ""
echo "Then remove the APPLOVIN_GDPR_API_KEY from run.sh"
echo ""
