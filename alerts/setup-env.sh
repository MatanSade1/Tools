#!/bin/bash
# Setup script for alerts project environment variables
# This script helps you set up your environment variables securely

set -e

echo "=========================================="
echo "Alerts Project - Environment Setup"
echo "=========================================="
echo ""

# Check if .env file already exists
if [ -f .env ]; then
    echo "⚠️  .env file already exists!"
    read -p "Do you want to overwrite it? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted. Existing .env file preserved."
        exit 0
    fi
fi

echo "Please provide the following configuration values:"
echo ""

# GCP Project
read -p "GCP Project ID: " GCP_PROJECT_ID
if [ -z "$GCP_PROJECT_ID" ]; then
    echo "❌ GCP Project ID is required"
    exit 1
fi

# Mixpanel Project
read -p "Mixpanel Project ID: " MIXPANEL_PROJECT_ID
if [ -z "$MIXPANEL_PROJECT_ID" ]; then
    echo "❌ Mixpanel Project ID is required"
    exit 1
fi

# Mixpanel Secret
echo ""
echo "Mixpanel API Secret:"
echo "  1) Use Secret Manager (recommended)"
echo "  2) Use environment variable (less secure)"
read -p "Choose option (1 or 2): " SECRET_OPTION

if [ "$SECRET_OPTION" = "1" ]; then
    read -p "Secret Manager secret name [mixpanel-api-secret]: " MIXPANEL_API_SECRET_NAME
    MIXPANEL_API_SECRET_NAME=${MIXPANEL_API_SECRET_NAME:-mixpanel-api-secret}
    MIXPANEL_API_SECRET=""
else
    read -sp "Mixpanel API Secret: " MIXPANEL_API_SECRET
    echo ""
    MIXPANEL_API_SECRET_NAME=""
fi

# Slack Webhook
read -p "Slack Webhook URL: " SLACK_WEBHOOK_URL
if [ -z "$SLACK_WEBHOOK_URL" ]; then
    echo "⚠️  Warning: Slack Webhook URL is empty. Alerts will be skipped."
fi

# Optional settings
echo ""
read -p "GCP Region [us-central1]: " GCP_REGION
GCP_REGION=${GCP_REGION:-us-central1}

read -p "BigQuery Dataset [peerplay]: " RT_MP_DATASET
RT_MP_DATASET=${RT_MP_DATASET:-peerplay}

read -p "BigQuery Table [rt_mp_events]: " RT_MP_TABLE
RT_MP_TABLE=${RT_MP_TABLE:-rt_mp_events}

# Create .env file
cat > .env << EOF
# GCP Configuration
GCP_PROJECT_ID=$GCP_PROJECT_ID
GCP_REGION=$GCP_REGION

# Mixpanel Configuration
MIXPANEL_PROJECT_ID=$MIXPANEL_PROJECT_ID

# Mixpanel API Secret
EOF

if [ -n "$MIXPANEL_API_SECRET_NAME" ]; then
    echo "MIXPANEL_API_SECRET_NAME=$MIXPANEL_API_SECRET_NAME" >> .env
    echo "# MIXPANEL_API_SECRET=  # Not used when using Secret Manager" >> .env
else
    echo "# MIXPANEL_API_SECRET_NAME=  # Not used when using env var" >> .env
    echo "MIXPANEL_API_SECRET=$MIXPANEL_API_SECRET" >> .env
fi

cat >> .env << EOF

# Slack Configuration
SLACK_WEBHOOK_URL=$SLACK_WEBHOOK_URL

# BigQuery Configuration
RT_MP_DATASET=$RT_MP_DATASET
RT_MP_TABLE=$RT_MP_TABLE
EOF

echo ""
echo "✅ .env file created successfully!"
echo ""
echo "⚠️  IMPORTANT:"
echo "   - The .env file is in .gitignore and will NOT be committed"
echo "   - Keep your secrets secure"
echo "   - For production, use Secret Manager instead of environment variables"
echo ""
echo "To use these variables, source them before deployment:"
echo "   source .env"
echo "   ./deploy.sh"
echo ""

