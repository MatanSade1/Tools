#!/bin/bash
# Local Development Environment Setup for rt-mp-collector
# This file configures environment variables for LOCAL/DEV testing

echo "Setting up LOCAL/DEV environment variables for rt-mp-collector..."

# GCP Configuration
export GCP_PROJECT_ID="yotam-395120"

# Mixpanel Configuration
export MIXPANEL_PROJECT_ID="${MIXPANEL_PROJECT_ID:-your-mixpanel-project-id}"
# export MIXPANEL_API_SECRET="your-api-secret"  # Or use Secret Manager
# export MIXPANEL_API_SECRET_NAME="mixpanel-api-secret"

# BigQuery Configuration
export RT_MP_DATASET="peerplay"
export RT_MP_TABLE="rt_mp_events"

# Google Sheets Configuration - LOCAL/DEV
# Dev spreadsheet: https://docs.google.com/spreadsheets/d/1FhRUxYTgKB4MLh8IbLPuHfBQRv3ry6tBtAxcA7gS-cw/edit
export RT_MP_CONFIG_SHEETS_ID="1FhRUxYTgKB4MLh8IbLPuHfBQRv3ry6tBtAxcA7gS-cw"
export RT_MP_CONFIG_SHEETS_RANGE="Sheet1!A:Z"

# Slack Configuration
export SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL:-your-slack-webhook-url}"

echo "✅ Environment configured for LOCAL/DEV:"
echo "   - Google Sheets (DEV): 1FhRUxYTgKB4MLh8IbLPuHfBQRv3ry6tBtAxcA7gS-cw"
echo "   - GCP Project: $GCP_PROJECT_ID"
echo "   - BigQuery Table: $RT_MP_DATASET.$RT_MP_TABLE"
echo ""
echo "To use these settings, run:"
echo "   source alerts/setup-local-env.sh"
echo ""
