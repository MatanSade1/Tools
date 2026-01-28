#!/bin/bash
# Script to start Chrome with remote debugging enabled for Looker Studio automation

PORT=${1:-9222}

echo "🚀 Starting Chrome with remote debugging on port $PORT"
echo "   This allows the automation script to control your existing Chrome browser"
echo ""

# Close existing Chrome instances (optional - comment out if you want to keep them)
# pkill -f "Google Chrome"

# Start Chrome with remote debugging
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=$PORT &

echo "✅ Chrome started with remote debugging"
echo "   You can now run: python3 create_ua_cohort_dashboard.py"
echo "   The script will connect to this Chrome instance"

