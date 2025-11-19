#!/bin/bash
# Store Slack Bot Token in Secret Manager

set -e

PROJECT_ID="${GCP_PROJECT_ID:-yotam-395120}"
SECRET_NAME="slack-bot-token"
TOKEN="${SLACK_BOT_TOKEN:-}"

if [ -z "$TOKEN" ]; then
    echo "❌ ERROR: SLACK_BOT_TOKEN environment variable not set"
    echo ""
    echo "Usage:"
    echo "  export SLACK_BOT_TOKEN='xoxb-your-token-here'"
    echo "  ./store-token-secure.sh"
    exit 1
fi

echo "Storing Slack Bot Token in Secret Manager..."
echo "Project: $PROJECT_ID"
echo "Secret name: $SECRET_NAME"
echo ""

# Check if gcloud is available
if ! command -v gcloud &> /dev/null; then
    echo "⚠️  gcloud CLI not found. Skipping Secret Manager setup."
    echo ""
    echo "You can set the token as an environment variable instead:"
    echo "  export SLACK_BOT_TOKEN='$TOKEN'"
    echo ""
    echo "Or store it manually later:"
    echo "  echo -n '$TOKEN' | gcloud secrets create $SECRET_NAME \\"
    echo "      --data-file=- --project=$PROJECT_ID"
    exit 0
fi

# Check if secret exists
if gcloud secrets describe "$SECRET_NAME" --project="$PROJECT_ID" &>/dev/null 2>&1; then
    echo "Secret '$SECRET_NAME' already exists. Updating..."
    echo -n "$TOKEN" | gcloud secrets versions add "$SECRET_NAME" \
        --data-file=- \
        --project="$PROJECT_ID" > /dev/null 2>&1
    echo "✅ Secret updated successfully!"
else
    echo "Creating new secret '$SECRET_NAME'..."
    echo -n "$TOKEN" | gcloud secrets create "$SECRET_NAME" \
        --data-file=- \
        --project="$PROJECT_ID" > /dev/null 2>&1
    echo "✅ Secret created successfully!"
fi

echo ""
echo "To use this secret, set:"
echo "  export SLACK_BOT_TOKEN_NAME='$SECRET_NAME'"
echo ""
echo "Or use environment variable directly:"
echo "  export SLACK_BOT_TOKEN='$TOKEN'"
echo ""

