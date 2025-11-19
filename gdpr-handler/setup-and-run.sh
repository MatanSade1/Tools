#!/bin/bash
# Complete setup and run script for GDPR Handler

set -e

echo "=========================================="
echo "GDPR Handler - Setup and Run"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Check if we're in the right directory
if [ ! -f "gdpr-handler/main.py" ]; then
    echo "❌ Error: Please run this from the Tools directory"
    echo "   cd /Users/matansade/Tools"
    exit 1
fi

# Step 2: Install dependencies
echo "📦 Step 1: Installing dependencies..."
pip3 install -q slack-sdk google-cloud-bigquery google-cloud-secret-manager || {
    echo "❌ Error installing dependencies"
    exit 1
}
echo -e "${GREEN}✅ Dependencies installed${NC}"
echo ""

# Step 3: Set environment variables
echo "🔧 Step 2: Setting up environment variables..."

# Check if token is set
if [ -z "$SLACK_BOT_TOKEN" ]; then
    echo -e "${YELLOW}⚠️  SLACK_BOT_TOKEN not set${NC}"
    echo "Please set it:"
    echo "  export SLACK_BOT_TOKEN='xoxb-your-token-here'"
    echo ""
    read -sp "Or enter token now (will not be saved): " token_input
    echo ""
    if [ -n "$token_input" ]; then
        export SLACK_BOT_TOKEN="$token_input"
    else
        echo "❌ Token required. Exiting."
        exit 1
    fi
else
    echo "Using SLACK_BOT_TOKEN from environment"
fi

export GCP_PROJECT_ID="${GCP_PROJECT_ID:-yotam-395120}"
export PYTHONPATH=/Users/matansade/Tools:$PYTHONPATH

echo -e "${GREEN}✅ Environment variables set${NC}"
echo ""

# Step 4: Get date range
echo "📅 Step 3: Date range selection"
echo ""
echo "Choose date range:"
echo "  1) Last 7 days"
echo "  2) Last 30 days"
echo "  3) Custom dates"
echo ""
read -p "Enter choice (1-3): " choice

case $choice in
    1)
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            START_DATE=$(date -v-7d +%Y-%m-%d)
            END_DATE=$(date +%Y-%m-%d)
        else
            # Linux
            START_DATE=$(date -d "7 days ago" +%Y-%m-%d)
            END_DATE=$(date +%Y-%m-%d)
        fi
        ;;
    2)
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            START_DATE=$(date -v-30d +%Y-%m-%d)
            END_DATE=$(date +%Y-%m-%d)
        else
            # Linux
            START_DATE=$(date -d "30 days ago" +%Y-%m-%d)
            END_DATE=$(date +%Y-%m-%d)
        fi
        ;;
    3)
        read -p "Enter start date (YYYY-MM-DD): " START_DATE
        read -p "Enter end date (YYYY-MM-DD): " END_DATE
        ;;
    *)
        echo "Invalid choice, using last 7 days"
        if [[ "$OSTYPE" == "darwin"* ]]; then
            START_DATE=$(date -v-7d +%Y-%m-%d)
            END_DATE=$(date +%Y-%m-%d)
        else
            START_DATE=$(date -d "7 days ago" +%Y-%m-%d)
            END_DATE=$(date +%Y-%m-%d)
        fi
        ;;
esac

echo ""
echo -e "${GREEN}✅ Date range: $START_DATE to $END_DATE${NC}"
echo ""

# Step 5: Run the handler
echo "🚀 Step 4: Running GDPR Handler..."
echo ""
python3 gdpr-handler/main.py --start-date "$START_DATE" --end-date "$END_DATE"

echo ""
echo "=========================================="
echo "✅ Complete!"
echo "=========================================="

