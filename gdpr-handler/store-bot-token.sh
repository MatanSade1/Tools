#!/bin/bash
# Quick script to store Slack Bot Token

set -e

PROJECT_ID="${GCP_PROJECT_ID:-yotam-395120}"
SECRET_NAME="slack-bot-token"

echo "=========================================="
echo "Store Slack Bot Token"
echo "=========================================="
echo ""
echo "Your Slack App ID: A09TVFPGM4K"
echo "App URL: https://api.slack.com/apps/A09TVFPGM4K"
echo ""
echo "To get your Bot Token:"
echo "1. Go to the app page above"
echo "2. Click 'OAuth & Permissions'"
echo "3. Find 'Bot User OAuth Token' (starts with xoxb-)"
echo "4. Copy it"
echo ""
read -sp "Paste your Bot User OAuth Token (xoxb-...): " SLACK_TOKEN
echo ""
echo ""

# Validate token format
if [[ ! "$SLACK_TOKEN" =~ ^xoxb- ]]; then
    echo "❌ ERROR: Token should start with 'xoxb-'"
    echo "   Got: ${SLACK_TOKEN:0:10}..."
    exit 1
fi

# Check if secret exists
if gcloud secrets describe "$SECRET_NAME" --project="$PROJECT_ID" &>/dev/null; then
    echo "⚠️  Secret '$SECRET_NAME' already exists. Updating..."
    echo -n "$SLACK_TOKEN" | gcloud secrets versions add "$SECRET_NAME" \
        --data-file=- \
        --project="$PROJECT_ID" &>/dev/null
    echo "✅ Secret updated!"
else
    echo "Creating secret '$SECRET_NAME'..."
    echo -n "$SLACK_TOKEN" | gcloud secrets create "$SECRET_NAME" \
        --data-file=- \
        --project="$PROJECT_ID" &>/dev/null
    echo "✅ Secret created!"
fi

echo ""
echo "=========================================="
echo "✅ Token stored successfully!"
echo "=========================================="
echo ""
echo "Set this environment variable:"
echo "  export SLACK_BOT_TOKEN_NAME=$SECRET_NAME"
echo ""
echo "Or test it now:"
echo "  export SLACK_BOT_TOKEN_NAME=$SECRET_NAME"
echo "  python gdpr-handler/test-slack-connection.py"
echo ""

