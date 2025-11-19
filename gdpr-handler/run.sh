#!/bin/bash
# Quick run script (assumes setup is already done)
#
# Usage:
#   ./gdpr-handler/run.sh                    # Last 7 days (default)
#   ./gdpr-handler/run.sh 2025-11-17 2025-12-31  # Custom date range
#   ./gdpr-handler/run.sh --help             # Show help

set -e

# Show help if requested
if [ "$1" == "--help" ] || [ "$1" == "-h" ]; then
    echo "GDPR Handler - Quick Run Script"
    echo ""
    echo "Usage:"
    echo "  ./gdpr-handler/run.sh                                    # Last 7 days (default)"
    echo "  ./gdpr-handler/run.sh <start-date> <end-date>            # Custom date range"
    echo "  ./gdpr-handler/run.sh 2025-11-17 2025-12-31             # Example"
    echo ""
    echo "Date format: YYYY-MM-DD (e.g., 2025-11-17)"
    echo ""
    exit 0
fi

# Load .env file if it exists
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/.env" ]; then
    # Source the .env file to export variables
    set -a
    source "$SCRIPT_DIR/.env"
    set +a
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

# Handle date arguments
if [ $# -eq 0 ]; then
    # No arguments: use last 7 days
    if [[ "$OSTYPE" == "darwin"* ]]; then
        START_DATE=$(date -v-7d +%Y-%m-%d)
        END_DATE=$(date +%Y-%m-%d)
    else
        START_DATE=$(date -d "7 days ago" +%Y-%m-%d)
        END_DATE=$(date +%Y-%m-%d)
    fi
    echo "Using default date range: $START_DATE to $END_DATE"
    echo ""
elif [ $# -eq 2 ]; then
    # Two arguments: start date and end date
    START_DATE=$1
    END_DATE=$2
    
    # Validate date format (basic check)
    if [[ ! "$START_DATE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] || [[ ! "$END_DATE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
        echo "❌ ERROR: Invalid date format"
        echo "Dates must be in YYYY-MM-DD format (e.g., 2025-11-17)"
        exit 1
    fi
    
    echo "Using custom date range: $START_DATE to $END_DATE"
    echo ""
else
    echo "❌ ERROR: Invalid number of arguments"
    echo ""
    echo "Usage:"
    echo "  ./gdpr-handler/run.sh                                    # Last 7 days"
    echo "  ./gdpr-handler/run.sh <start-date> <end-date>            # Custom range"
    echo "  ./gdpr-handler/run.sh 2025-11-17 2025-12-31             # Example"
    echo ""
    exit 1
fi

# Run the handler
python3 gdpr-handler/main.py --start-date "$START_DATE" --end-date "$END_DATE"

