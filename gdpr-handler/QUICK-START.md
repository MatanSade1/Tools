# Quick Start Guide - Slack App Setup

Follow these steps to set up your Slack app. This should take about 5 minutes.

## Step 1: Create Slack App (2 minutes)

1. **Open**: https://api.slack.com/apps
2. **Click**: "Create New App" → "From scratch"
3. **Enter**:
   - App Name: `GDPR Request Handler` (or any name you prefer)
   - Pick Workspace: Select your workspace
4. **Click**: "Create App"

## Step 2: Add Bot Token Scopes (1 minute)

1. In the left sidebar, click **"OAuth & Permissions"**
2. Scroll down to **"Scopes"** → **"Bot Token Scopes"**
3. **Click "Add an OAuth Scope"** and add these scopes:
   - `channels:history` - View messages in public channels
   - `channels:read` - View basic information about public channels
   - `reactions:write` - Add reactions to messages
4. **Optional** (if using private channels):
   - `groups:history` - View messages in private channels
   - `groups:read` - View basic information about private channels

## Step 3: Install App to Workspace (1 minute)

1. Scroll to the top of the **"OAuth & Permissions"** page
2. **Click**: "Install to Workspace"
3. **Review** the permissions (should show the scopes you added)
4. **Click**: "Allow"
5. You'll be redirected back to the OAuth & Permissions page

## Step 4: Copy Bot Token (30 seconds)

1. On the **"OAuth & Permissions"** page, find **"Bot User OAuth Token"**
2. The token starts with `xoxb-`
3. **Click "Copy"** to copy the token
4. **Keep this token secure** - you'll need it in the next step

## Step 5: Store Token (1 minute)

You have two options:

### Option A: Secret Manager (Recommended for production)

Run the setup script:
```bash
cd gdpr-handler
./setup-slack-token.sh
```

Or manually:
```bash
# Set your GCP project (if not already set)
export GCP_PROJECT_ID="yotam-395120"

# Create secret (paste your token when prompted)
echo -n "xoxb-your-token-here" | gcloud secrets create slack-bot-token \
    --data-file=- \
    --project=$GCP_PROJECT_ID

# Set environment variable
export SLACK_BOT_TOKEN_NAME="slack-bot-token"
```

### Option B: Environment Variable (Quick testing)

```bash
export SLACK_BOT_TOKEN="xoxb-your-token-here"
```

## Step 6: Invite Bot to Channel (30 seconds)

1. Go to Slack and open the `users-to-delete-their-personal-data` channel
2. Type: `/invite @GDPR Request Handler` (or whatever you named your app)
3. Press Enter
4. The bot should appear in the channel member list

## Step 7: Test Connection

Run the test script:
```bash
python gdpr-handler/test-slack-connection.py
```

You should see:
```
✅ Token found: xoxb-...
✅ Channel 'users-to-delete-their-personal-data' found: C...
✅ Connected to workspace: Your Workspace
✅ Bot user: gdpr-request-handler
✅ All tests passed! Slack connection is working.
```

## Troubleshooting

### "Channel not found"
- Make sure you invited the bot to the channel (Step 6)
- Check the channel name is exactly `users-to-delete-their-personal-data` (case-sensitive)

### "Invalid token"
- Verify the token starts with `xoxb-`
- Make sure you copied the entire token
- Check that the app is installed to your workspace

### "Missing scope"
- Go back to Step 2 and add the missing scope
- Reinstall the app to workspace after adding scopes

### "Permission denied"
- Ensure the bot is a member of the channel
- Check that you have admin permissions to add bots to channels

## Next Steps

Once the test passes, you're ready to use the tool:

```bash
python gdpr-handler/main.py --start-date 2025-11-17 --end-date 2025-12-31
```

## Need Help?

- See [README-SLACK-SETUP.md](README-SLACK-SETUP.md) for detailed documentation
- Check [README.md](README.md) for usage instructions

