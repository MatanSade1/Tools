#!/bin/bash
# Script to help set up Slack Bot Token in Secret Manager

set -e

PROJECT_ID="${GCP_PROJECT_ID:-yotam-395120}"
SECRET_NAME="slack-bot-token"

echo "=========================================="
echo "Slack Bot Token Setup for GDPR Handler"
echo "=========================================="
echo ""
echo "This script will help you store your Slack Bot Token in Secret Manager."
echo ""
echo "Prerequisites:"
echo "1. You have created a Slack app at https://api.slack.com/apps"
echo "2. You have installed the app to your workspace"
echo "3. You have copied the Bot User OAuth Token (starts with xoxb-)"
echo ""
read -p "Press Enter to continue or Ctrl+C to exit..."
echo ""

# Check if secret already exists
if gcloud secrets describe "$SECRET_NAME" --project="$PROJECT_ID" &>/dev/null; then
    echo "⚠️  Secret '$SECRET_NAME' already exists in project '$PROJECT_ID'"
    read -p "Do you want to update it? (y/n): " update_choice
    if [[ ! "$update_choice" =~ ^[Yy]$ ]]; then
        echo "Exiting. To use existing secret, set: export SLACK_BOT_TOKEN_NAME=$SECRET_NAME"
        exit 0
    fi
    echo ""
    read -sp "Enter your Slack Bot Token (xoxb-...): " SLACK_TOKEN
    echo ""
    echo ""
    echo -n "$SLACK_TOKEN" | gcloud secrets versions add "$SECRET_NAME" \
        --data-file=- \
        --project="$PROJECT_ID"
    echo "✅ Secret updated successfully!"
else
    echo "Creating new secret '$SECRET_NAME' in project '$PROJECT_ID'..."
    read -sp "Enter your Slack Bot Token (xoxb-...): " SLACK_TOKEN
    echo ""
    echo ""
    echo -n "$SLACK_TOKEN" | gcloud secrets create "$SECRET_NAME" \
        --data-file=- \
        --project="$PROJECT_ID"
    echo "✅ Secret created successfully!"
fi

echo ""
echo "=========================================="
echo "Next Steps:"
echo "=========================================="
echo "1. Set the environment variable:"
echo "   export SLACK_BOT_TOKEN_NAME=$SECRET_NAME"
echo ""
echo "2. If using a service account, grant it access:"
echo "   gcloud secrets add-iam-policy-binding $SECRET_NAME \\"
echo "       --member=\"serviceAccount:YOUR_SERVICE_ACCOUNT@$PROJECT_ID.iam.gserviceaccount.com\" \\"
echo "       --role=\"roles/secretmanager.secretAccessor\" \\"
echo "       --project=$PROJECT_ID"
echo ""
echo "3. Test the setup:"
echo "   python -c \"from shared.slack_client import get_channel_id; print(get_channel_id('users-to-delete-their-personal-data'))\""
echo ""

