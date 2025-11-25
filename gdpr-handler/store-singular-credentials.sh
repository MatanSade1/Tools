#!/bin/bash
# Store Singular API credentials in Secret Manager

set -e

PROJECT_ID="${GCP_PROJECT_ID:-yotam-395120}"
API_KEY_SECRET_NAME="singular-api-key"
API_SECRET_SECRET_NAME="singular-api-secret"

echo "=========================================="
echo "Store Singular API Credentials"
echo "=========================================="
echo ""
echo "This script will store your Singular API credentials securely."
echo ""
read -sp "Paste your Singular API Key: " SINGULAR_API_KEY
echo ""
read -sp "Paste your Singular API Secret: " SINGULAR_API_SECRET
echo ""
echo ""

# Validate inputs
if [ -z "$SINGULAR_API_KEY" ]; then
    echo "❌ ERROR: API Key cannot be empty"
    exit 1
fi

if [ -z "$SINGULAR_API_SECRET" ]; then
    echo "❌ ERROR: API Secret cannot be empty"
    exit 1
fi

# Check if gcloud is available
if ! command -v gcloud &> /dev/null; then
    echo "⚠️  gcloud CLI not found. Skipping Secret Manager setup."
    echo ""
    echo "You can set the credentials as environment variables instead:"
    echo "  export SINGULAR_API_KEY='$SINGULAR_API_KEY'"
    echo "  export SINGULAR_API_SECRET='$SINGULAR_API_SECRET'"
    exit 0
fi

# Store API Key
if gcloud secrets describe "$API_KEY_SECRET_NAME" --project="$PROJECT_ID" &>/dev/null 2>&1; then
    echo "Secret '$API_KEY_SECRET_NAME' already exists. Updating..."
    echo -n "$SINGULAR_API_KEY" | gcloud secrets versions add "$API_KEY_SECRET_NAME" \
        --data-file=- \
        --project="$PROJECT_ID" > /dev/null 2>&1
    echo "✅ API Key secret updated successfully!"
else
    echo "Creating new secret '$API_KEY_SECRET_NAME'..."
    echo -n "$SINGULAR_API_KEY" | gcloud secrets create "$API_KEY_SECRET_NAME" \
        --data-file=- \
        --project="$PROJECT_ID" > /dev/null 2>&1
    echo "✅ API Key secret created successfully!"
fi

# Store API Secret
if gcloud secrets describe "$API_SECRET_SECRET_NAME" --project="$PROJECT_ID" &>/dev/null 2>&1; then
    echo "Secret '$API_SECRET_SECRET_NAME' already exists. Updating..."
    echo -n "$SINGULAR_API_SECRET" | gcloud secrets versions add "$API_SECRET_SECRET_NAME" \
        --data-file=- \
        --project="$PROJECT_ID" > /dev/null 2>&1
    echo "✅ API Secret secret updated successfully!"
else
    echo "Creating new secret '$API_SECRET_SECRET_NAME'..."
    echo -n "$SINGULAR_API_SECRET" | gcloud secrets create "$API_SECRET_SECRET_NAME" \
        --data-file=- \
        --project="$PROJECT_ID" > /dev/null 2>&1
    echo "✅ API Secret secret created successfully!"
fi

echo ""
echo "=========================================="
echo "✅ Credentials stored successfully!"
echo "=========================================="
echo ""
echo "To use these secrets, set:"
echo "  export SINGULAR_API_KEY_NAME='$API_KEY_SECRET_NAME'"
echo "  export SINGULAR_API_SECRET_NAME='$API_SECRET_SECRET_NAME'"
echo ""
echo "Or use environment variables directly:"
echo "  export SINGULAR_API_KEY='$SINGULAR_API_KEY'"
echo "  export SINGULAR_API_SECRET='$SINGULAR_API_SECRET'"
echo ""

