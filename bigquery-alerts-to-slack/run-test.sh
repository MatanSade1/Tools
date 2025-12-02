#!/bin/bash

# Convenience script to run the service in test mode

set -e

echo "🧪 Running BigQuery Alerts to Slack in TEST MODE"
echo ""

# Check if resolution argument is provided
RESOLUTION="${1:-}"

# Build command
CMD="python main.py"
if [ -n "$RESOLUTION" ]; then
    CMD="$CMD $RESOLUTION"
fi
CMD="$CMD --test"

echo "Command: $CMD"
echo ""

# Run the command
$CMD

