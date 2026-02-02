#!/bin/bash
# Mission Configuration Validator - Run Script

set -e

echo "=========================================="
echo "Mission Configuration Validator"
echo "=========================================="
echo

# Check if running from correct directory
if [ ! -f "mission_config_validator.py" ]; then
    echo "❌ Error: Please run this script from the Tools directory"
    exit 1
fi

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed"
    exit 1
fi

# Check if dependencies are installed
echo "📦 Checking dependencies..."
if ! python3 -c "import pandas" 2>/dev/null; then
    echo "⚠️  Dependencies not installed. Installing..."
    pip3 install -r requirements.txt
    echo "✅ Dependencies installed"
else
    echo "✅ Dependencies already installed"
fi
echo

# Check GCP authentication
echo "🔐 Checking GCP authentication..."
if ! gcloud auth application-default print-access-token &> /dev/null; then
    echo "⚠️  GCP authentication not configured"
    echo "   Running: gcloud auth application-default login"
    gcloud auth application-default login
    echo "✅ GCP authentication configured"
else
    echo "✅ GCP authentication configured"
fi
echo

# Check if arguments were provided
if [ $# -eq 0 ]; then
    echo "Usage examples:"
    echo "  $0 --live-ops-id 4253 --feature missions                           # Today only"
    echo "  $0 --live-ops-id 4253 --feature missions --days-back 7             # Last 7 days"
    echo "  $0 --live-ops-id 4253 --feature missions --start-date 2026-01-26 --end-date 2026-01-26"
    echo
    echo "Running with default: today only, live-ops-id 4253, feature missions"
    echo
    python3 mission_config_validator.py --live-ops-id 4253 --feature missions
else
    # Run with provided arguments
    echo "🚀 Starting validation with custom parameters..."
    echo
    python3 mission_config_validator.py "$@"
fi

echo
echo "=========================================="
echo "✅ Done!"
echo "=========================================="
