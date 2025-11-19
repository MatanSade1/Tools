#!/bin/bash
# Quick run script (assumes setup is already done)

set -e

# Load .env file if it exists
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/.env" ]; then
    export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs)
fi

# Set environment variables
# Token must be set in environment or .env file
if [ -z "$SLACK_BOT_TOKEN" ]; then
    echo "❌ ERROR: SLACK_BOT_TOKEN not set"
    echo "Set it with: export SLACK_BOT_TOKEN='xoxb-your-token-here'"
    echo "Or create gdpr-handler/.env file (see .env.example)"
    exit 1
fi

export GCP_PROJECT_ID="${GCP_PROJECT_ID:-yotam-395120}"
export PYTHONPATH=/Users/matansade/Tools:$PYTHONPATH

# Default to last 7 days if no arguments provided
if [ $# -eq 0 ]; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
        START_DATE=$(date -v-7d +%Y-%m-%d)
        END_DATE=$(date +%Y-%m-%d)
    else
        START_DATE=$(date -d "7 days ago" +%Y-%m-%d)
        END_DATE=$(date +%Y-%m-%d)
    fi
    echo "Using default date range: $START_DATE to $END_DATE"
    echo ""
else
    START_DATE=$1
    END_DATE=$2
fi

# Run the handler
python3 gdpr-handler/main.py --start-date "$START_DATE" --end-date "$END_DATE"

