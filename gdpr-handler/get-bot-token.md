# How to Get Your Bot User OAuth Token

You've created the Slack app, but we need the **Bot User OAuth Token** (not the client credentials).

## Quick Steps:

1. **Go to**: https://api.slack.com/apps/A09TVFPGM4K (your app)
2. **Click**: "OAuth & Permissions" in the left sidebar
3. **Look for**: "Bot User OAuth Token" section (near the top)
4. **Copy**: The token that starts with `xoxb-`

## If You Don't See the Token:

The token only appears **after you install the app to your workspace**:

1. On the "OAuth & Permissions" page, scroll to the top
2. Click **"Install to Workspace"** (or "Reinstall to Workspace" if already installed)
3. Click **"Allow"** to approve the permissions
4. You'll be redirected back, and the **Bot User OAuth Token** will appear
5. Copy the token (it starts with `xoxb-`)

## Once You Have the Token:

Run this to store it securely:

```bash
cd gdpr-handler
./setup-slack-token.sh
```

Or set it as an environment variable:

```bash
export SLACK_BOT_TOKEN="xoxb-your-token-here"
```

Then test it:

```bash
python gdpr-handler/test-slack-connection.py
```

