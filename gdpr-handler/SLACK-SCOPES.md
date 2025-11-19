# Required Slack Bot Token Scopes

For the GDPR Request Handler, you need **Bot Token Scopes** (not User Token Scopes).

## Required Scopes

Add these scopes in your Slack app settings:

### Essential (Required):
1. **`channels:history`** - View messages in public channels
2. **`channels:read`** - View basic information about public channels  
3. **`reactions:write`** - Add reactions to messages

### Optional (if using private channels):
4. **`groups:history`** - View messages in private channels
5. **`groups:read`** - View basic information about private channels

## How to Add Scopes

1. Go to: https://api.slack.com/apps/A09TVFPGM4K
2. Click **"OAuth & Permissions"** in the left sidebar
3. Scroll down to **"Scopes"** → **"Bot Token Scopes"**
4. Click **"Add an OAuth Scope"**
5. Search for and add each scope listed above
6. Scroll to the top and click **"Install to Workspace"**
7. Approve the permissions
8. Copy the **Bot User OAuth Token** (starts with `xoxb-`)

## Why Bot Token Scopes?

- The GDPR handler runs as an automated bot
- It needs to read messages and add reactions independently
- It doesn't act on behalf of a specific user
- Bot Token Scopes allow the app to work autonomously

## After Adding Scopes

Once you have the Bot User OAuth Token, store it:

```bash
cd gdpr-handler
./store-bot-token.sh
```

Then test:

```bash
export SLACK_BOT_TOKEN_NAME="slack-bot-token"
python gdpr-handler/test-slack-connection.py
```

