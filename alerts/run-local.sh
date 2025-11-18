#!/bin/bash
# Local development setup and run script for alerts project

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Script is in alerts/, so go up one level to get project root
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=========================================="
echo "Alerts Project - Local Setup & Run"
echo "=========================================="
echo ""
echo "Project root: $PROJECT_ROOT"
echo ""

# Change to project root
cd "$PROJECT_ROOT" || {
    echo "❌ Error: Could not change to project root: $PROJECT_ROOT"
    exit 1
}

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
pip install -r alerts/rt-mp-collector/requirements.txt
echo "✅ Dependencies installed"

# Check for .env file
if [ ! -f .env ]; then
    echo ""
    echo "⚠️  No .env file found!"
    echo "Creating .env from .env.example..."
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "✅ .env file created from template"
        echo ""
        echo "⚠️  Please edit .env file with your actual values:"
        echo "   - GCP_PROJECT_ID"
        echo "   - MIXPANEL_PROJECT_ID"
        echo "   - MIXPANEL_API_SECRET or MIXPANEL_API_SECRET_NAME"
        echo "   - SLACK_WEBHOOK_URL"
        echo ""
        read -p "Press Enter after you've updated .env file..."
    else
        echo "❌ .env.example not found. Please create .env manually."
        exit 1
    fi
fi

# Load environment variables
echo ""
echo "Loading environment variables from .env..."
export $(cat .env | grep -v '^#' | xargs)
echo "✅ Environment variables loaded"

# Check GCP authentication
echo ""
echo "Checking GCP authentication..."
if ! command -v gcloud &> /dev/null; then
    echo "⚠️  gcloud CLI not found"
    echo "   For BigQuery access, you need to install Google Cloud SDK:"
    echo "   macOS: brew install --cask google-cloud-sdk"
    echo "   Then run: gcloud auth application-default login"
    echo ""
    echo "   Continuing anyway (BigQuery operations may fail)..."
elif ! gcloud auth application-default print-access-token &>/dev/null 2>&1; then
    echo "⚠️  GCP Application Default Credentials not set"
    echo "Running: gcloud auth application-default login"
    gcloud auth application-default login
else
    echo "✅ GCP authentication verified"
fi

# Verify required environment variables
echo ""
echo "Verifying required environment variables..."
MISSING_VARS=()

if [ -z "$GCP_PROJECT_ID" ]; then
    MISSING_VARS+=("GCP_PROJECT_ID")
fi
if [ -z "$MIXPANEL_PROJECT_ID" ]; then
    MISSING_VARS+=("MIXPANEL_PROJECT_ID")
fi
if [ -z "$MIXPANEL_API_SECRET" ] && [ -z "$MIXPANEL_API_SECRET_NAME" ]; then
    MISSING_VARS+=("MIXPANEL_API_SECRET or MIXPANEL_API_SECRET_NAME")
fi

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    echo "❌ Missing required environment variables:"
    for var in "${MISSING_VARS[@]}"; do
        echo "   - $var"
    done
    echo ""
    echo "Please update your .env file and try again."
    exit 1
fi

echo "✅ All required environment variables are set"

# Run the function
echo ""
echo "=========================================="
echo "Running rt-mp-collector locally..."
echo "=========================================="
echo ""

# Run using the test script which handles imports correctly
python3 alerts/test-local.py

echo ""
echo "=========================================="
echo "Local run complete"
echo "=========================================="

