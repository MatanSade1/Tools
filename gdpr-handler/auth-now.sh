#!/bin/bash
# Quick script to authenticate with GCP

export PATH="/Users/matansade/google-cloud-sdk/bin:$PATH"

echo "Setting up GCP authentication..."
echo "This will open a browser for you to sign in."
echo ""

gcloud auth application-default login --project=yotam-395120

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Authentication successful!"
    echo ""
    echo "You can now run the GDPR handler:"
    echo "  ./gdpr-handler/run.sh 2025-11-16 2025-11-17"
else
    echo ""
    echo "❌ Authentication failed. Please try again."
fi

