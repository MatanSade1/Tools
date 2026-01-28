#!/bin/bash

# Quick setup script for Notion OAuth

echo "=========================================="
echo "Notion OAuth Setup - Quick Start"
echo "=========================================="
echo ""

# Check if credentials are set
if [ -z "$NOTION_CLIENT_ID" ] || [ -z "$NOTION_CLIENT_SECRET" ]; then
    echo "⚠️  OAuth credentials not found in environment"
    echo ""
    echo "Please set your credentials:"
    echo ""
    echo "  export NOTION_CLIENT_ID='your-client-id'"
    echo "  export NOTION_CLIENT_SECRET='your-client-secret'"
    echo ""
    echo "Get them from: https://www.notion.so/my-integrations"
    echo ""
    echo "Or edit notion_oauth_flow.py directly"
    echo "=========================================="
    exit 1
fi

echo "✅ OAuth credentials found"
echo ""
echo "Step 1: Running OAuth authorization flow..."
echo "  (This will open your browser)"
echo ""

python3 /Users/matansade/Tools/notion_oauth_flow.py

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Authorization successful!"
    echo ""
    read -p "Press Enter to fetch calendar data and upload to BigQuery..."
    echo ""
    echo "Step 2: Fetching data from Notion..."
    python3 /Users/matansade/Tools/fetch_notion_oauth.py
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "=========================================="
        echo "✅ SUCCESS! Data uploaded to BigQuery"
        echo "=========================================="
        echo ""
        echo "Verify with:"
        echo "  bq query --use_legacy_sql=false \"SELECT COUNT(*) FROM \\\`yotam-395120.peerplay.liveops_calendar_test_2\\\`\""
    else
        echo ""
        echo "❌ Failed to fetch data"
    fi
else
    echo ""
    echo "❌ Authorization failed"
    echo ""
    echo "Make sure:"
    echo "  1. You created a Public integration at https://www.notion.so/my-integrations"
    echo "  2. Set redirect URI to: http://localhost:8080/oauth/callback"
    echo "  3. OAuth credentials are correct"
fi
