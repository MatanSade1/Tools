# API Setup Guide

This guide explains how to set up the Mixpanel and Singular API credentials for the GDPR deletion request handler.

## Overview

The GDPR handler now automatically creates deletion requests in both Mixpanel and Singular when processing Slack messages. The request IDs are stored in BigQuery for tracking.

## Mixpanel Setup

### 1. Get Your Mixpanel GDPR Token

The Mixpanel GDPR token is: `0e73d8fa8567c5bf2820b408701fa7be`

⚠️ **IMPORTANT**: Store this token securely. Never commit it to git.

### 2. Store the Token

**Option A: Using Secret Manager (Recommended)**

```bash
cd /Users/matansade/Tools
./gdpr-handler/store-mixpanel-token.sh
```

When prompted, paste the token: `0e73d8fa8567c5bf2820b408701fa7be`

Then set the environment variable:
```bash
export MIXPANEL_GDPR_TOKEN_NAME="mixpanel-gdpr-token"
```

**Option B: Using Environment Variable**

```bash
export MIXPANEL_GDPR_TOKEN="0e73d8fa8567c5bf2820b408701fa7be"
```

### 3. Verify Setup

The Mixpanel GDPR API will be called automatically when processing deletion requests. The `mixpanel_request_id` will be stored in BigQuery.

## Singular Setup

### 1. Get Your Singular API Credentials

You need:
- **API Key**: Your Singular API key
- **API Secret**: Your Singular API secret

Get these from your Singular account settings.

### 2. Store the Credentials

**Option A: Using Secret Manager (Recommended)**

```bash
cd /Users/matansade/Tools
./gdpr-handler/store-singular-credentials.sh
```

When prompted, paste your API Key and API Secret.

Then set the environment variables:
```bash
export SINGULAR_API_KEY_NAME="singular-api-key"
export SINGULAR_API_SECRET_NAME="singular-api-secret"
```

**Option B: Using Environment Variables**

```bash
export SINGULAR_API_KEY="your-api-key"
export SINGULAR_API_SECRET="your-api-secret"
```

### 3. Verify Setup

The Singular OpenDSR API will be called automatically when processing deletion requests. The `singular_request_id` (subject_request_id) will be stored in BigQuery.

## How It Works

1. When a message with a blue car emoji (and no computer emoji) is found in Slack
2. The system extracts the `distinct_id` from the message
3. **Creates a deletion request in Mixpanel** using the GDPR API
4. **Creates a deletion request in Singular** using the OpenDSR API
5. **Stores the record in BigQuery** with both request IDs
6. Adds a computer emoji to the Slack message to mark it as processed

## BigQuery Schema

The following fields are populated automatically:
- `mixpanel_request_id`: The request ID returned by Mixpanel
- `mixpanel_deletion_status`: Set to "pending" if request created, "not started" if failed
- `singular_request_id`: The subject_request_id returned by Singular
- `singular_deletion_status`: Set to "pending" if request created, "not started" if failed

## Troubleshooting

### Mixpanel API Errors

- **Error: "MIXPANEL_GDPR_TOKEN must be configured"**
  - Make sure you've set `MIXPANEL_GDPR_TOKEN` or `MIXPANEL_GDPR_TOKEN_NAME`
  - Run `./gdpr-handler/store-mixpanel-token.sh` to store it

- **Error: "401 Unauthorized"**
  - Check that your token is correct
  - Verify the token has GDPR deletion permissions in Mixpanel

### Singular API Errors

- **Error: "SINGULAR_API_KEY and SINGULAR_API_SECRET must be configured"**
  - Make sure you've set both `SINGULAR_API_KEY` and `SINGULAR_API_SECRET` (or their `_NAME` variants)
  - Run `./gdpr-handler/store-singular-credentials.sh` to store them

- **Error: "401 Unauthorized"**
  - Check that your API key and secret are correct
  - Verify they have OpenDSR permissions in Singular

## References

- [Singular OpenDSR API Documentation](https://support.singular.net/hc/en-us/articles/360045674671-OpenDSR-GDPR-API-Reference)
- Mixpanel GDPR API: Uses Basic Auth with token as username

