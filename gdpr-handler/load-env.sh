#!/bin/bash
# Load environment variables from .env file if it exists

if [ -f "gdpr-handler/.env" ]; then
    echo "Loading environment from .env file..."
    export $(grep -v '^#' gdpr-handler/.env | xargs)
fi

