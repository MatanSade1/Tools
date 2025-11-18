#!/bin/bash
# Script to verify GCP setup and required APIs for alerts project

set -e

echo "=========================================="
echo "GCP Setup Verification for Alerts Project"
echo "=========================================="
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ ERROR: gcloud CLI is not installed"
    echo ""
    echo "Please install Google Cloud SDK:"
    echo "  macOS: brew install --cask google-cloud-sdk"
    echo "  Or visit: https://cloud.google.com/sdk/docs/install"
    echo ""
    exit 1
fi

echo "✅ gcloud CLI is installed"
echo ""

# Check authentication
echo "Checking authentication..."
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -1 &> /dev/null; then
    echo "❌ ERROR: Not authenticated with gcloud"
    echo ""
    echo "Please run: gcloud auth login"
    echo ""
    exit 1
fi

ACTIVE_ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -1)
echo "✅ Authenticated as: $ACTIVE_ACCOUNT"
echo ""

# Get current project
CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null || echo "")
if [ -z "$CURRENT_PROJECT" ]; then
    echo "⚠️  WARNING: No project is currently set"
    echo ""
    echo "Please set a project with: gcloud config set project YOUR_PROJECT_ID"
    echo ""
    read -p "Do you want to continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo "✅ Current project: $CURRENT_PROJECT"
    echo ""
fi

# Required APIs
REQUIRED_APIS=(
    "cloudfunctions.googleapis.com"
    "cloudscheduler.googleapis.com"
    "bigquery.googleapis.com"
    "secretmanager.googleapis.com"
)

echo "Checking required APIs..."
echo ""

ALL_ENABLED=true

for API in "${REQUIRED_APIS[@]}"; do
    API_NAME=$(echo $API | sed 's/\.googleapis\.com//' | tr '.' ' ' | awk '{for(i=1;i<=NF;i++) $i=toupper(substr($i,1,1)) tolower(substr($i,2));}1' | tr ' ' ' ')
    
    if gcloud services list --enabled --filter="name:$API" --format="value(name)" 2>/dev/null | grep -q "^$API$"; then
        echo "✅ $API_NAME API is enabled"
    else
        echo "❌ $API_NAME API is NOT enabled"
        ALL_ENABLED=false
    fi
done

echo ""

if [ "$ALL_ENABLED" = false ]; then
    echo "=========================================="
    echo "⚠️  Some APIs are not enabled"
    echo "=========================================="
    echo ""
    echo "To enable all required APIs, run:"
    echo ""
    for API in "${REQUIRED_APIS[@]}"; do
        if ! gcloud services list --enabled --filter="name:$API" --format="value(name)" 2>/dev/null | grep -q "^$API$"; then
            API_NAME=$(echo $API | sed 's/\.googleapis\.com//')
            echo "  gcloud services enable $API"
        fi
    done
    echo ""
    read -p "Do you want to enable missing APIs now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        for API in "${REQUIRED_APIS[@]}"; do
            if ! gcloud services list --enabled --filter="name:$API" --format="value(name)" 2>/dev/null | grep -q "^$API$"; then
                echo "Enabling $API..."
                gcloud services enable $API
            fi
        done
        echo ""
        echo "✅ All APIs enabled!"
    fi
else
    echo "=========================================="
    echo "✅ All required APIs are enabled!"
    echo "=========================================="
fi

echo ""
echo "Checking billing status..."
BILLING_ENABLED=$(gcloud beta billing projects describe $CURRENT_PROJECT --format="value(billingAccountName)" 2>/dev/null || echo "")
if [ -n "$BILLING_ENABLED" ]; then
    echo "✅ Billing is enabled"
    echo "   Billing Account: $BILLING_ENABLED"
else
    echo "⚠️  WARNING: Billing may not be enabled"
    echo "   Cloud Functions require billing to be enabled"
fi

echo ""
echo "=========================================="
echo "Verification Complete"
echo "=========================================="

