# Mixpanel GDPR API Authentication Guide

## Problem

The token `0e73d8fa8567c5bf2820b408701fa7be` is a **Project Token**, which is used for tracking/importing events. It does **NOT work** with the GDPR API.

## Solution: Get the Right Credentials

Mixpanel GDPR API requires one of the following authentication methods:

### Option 1: OAuth Token (Recommended for GDPR API) ⭐

**Best for:** GDPR deletion requests

**How to get it:**
1. Log in to Mixpanel: https://mixpanel.com
2. Click your initials in the top-right corner
3. Select **"Profile & Preferences"**
4. Navigate to the **"Data & Privacy"** tab
5. Generate an **OAuth token** with GDPR API scope
6. Copy the token

**How to use:**
```bash
export MIXPANEL_GDPR_TOKEN="your-oauth-token-here"
```

### Option 2: Service Account (Username + Secret)

**Best for:** General API access (works with GDPR API too)

**How to get it:**
1. Go to: https://mixpanel.com/project/2991947/settings
2. Navigate to: **Project Settings** → **Service Accounts**
3. Click **"Add Service Account"**
4. Copy the **Username** and **Secret**

**How to use:**
```bash
export MIXPANEL_SERVICE_ACCOUNT_USERNAME="your-username"
export MIXPANEL_SERVICE_ACCOUNT_SECRET="your-secret"
```

### Option 3: Export API Secret

**Best for:** Export API (may work with GDPR API)

**How to get it:**
1. Go to: https://mixpanel.com/project/2991947/settings
2. Navigate to: **Project Settings** → **Service Accounts**
3. Look for **"Export API Secret"** section
4. Copy the secret

**How to use:**
```bash
export MIXPANEL_API_SECRET="your-export-api-secret"
```

## Quick Setup

Once you have the credentials, store them securely:

**For OAuth Token:**
```bash
cd /Users/matansade/Tools
./gdpr-handler/store-mixpanel-token.sh
# When prompted, paste your OAuth token
export MIXPANEL_GDPR_TOKEN_NAME="mixpanel-gdpr-token"
```

**For Service Account:**
```bash
export MIXPANEL_SERVICE_ACCOUNT_USERNAME="your-username"
export MIXPANEL_SERVICE_ACCOUNT_SECRET="your-secret"
```

**For Export API Secret:**
```bash
export MIXPANEL_API_SECRET="your-export-api-secret"
```

## Test Authentication

After setting up credentials, test the API:

```bash
cd /Users/matansade/Tools
export PYTHONPATH=/Users/matansade/Tools:$PYTHONPATH
python3 -c "
import sys
sys.path.insert(0, 'gdpr-handler')
from api_clients import create_mixpanel_gdpr_request
result = create_mixpanel_gdpr_request('test-user-id', 'gdpr')
print(f'Result: {result}')
"
```

## Which Method Should I Use?

- **OAuth Token**: Best for GDPR-specific operations, easiest to get
- **Service Account**: More secure, recommended by Mixpanel, works for all APIs
- **Export API Secret**: If you already have it set up for other purposes

## Troubleshooting

### Error: "Unable to authenticate request"
- Make sure you're using the correct credential type (not a Project Token)
- Verify the token/credentials haven't expired
- Check that the credentials have the right permissions

### Error: "403 Forbidden"
- The token might not have GDPR API permissions
- Try using a Service Account instead

### Error: "404 Not Found"
- The endpoint might have changed
- Check Mixpanel's latest API documentation

## References

- [Mixpanel GDPR API Documentation](https://developer.mixpanel.com/reference/gdpr-api)
- [Mixpanel Service Accounts](https://developer.mixpanel.com/reference/service-accounts)
- [Mixpanel Privacy Documentation](https://docs.mixpanel.com/docs/privacy)


