# Slack App Setup Guide for GDPR Request Handler

This guide will walk you through setting up a Slack app and bot to read messages from the `users-to-delete-their-personal-data` channel and add reactions to messages.

## Step 1: Create a Slack App

1. Go to [https://api.slack.com/apps](https://api.slack.com/apps)
2. Click **"Create New App"**
3. Choose **"From scratch"**
4. Enter an app name (e.g., "GDPR Request Handler")
5. Select your workspace
6. Click **"Create App"**

## Step 2: Configure Bot Token Scopes

1. In your app settings, go to **"OAuth & Permissions"** in the left sidebar
2. Scroll down to **"Scopes"** → **"Bot Token Scopes"**
3. Add the following scopes:
   - `channels:history` - View messages in public channels
   - `channels:read` - View basic information about public channels
   - `groups:history` - View messages in private channels (if needed)
   - `groups:read` - View basic information about private channels (if needed)
   - `reactions:write` - Add reactions to messages

## Step 3: Install App to Workspace

1. Scroll up to the top of the **"OAuth & Permissions"** page
2. Click **"Install to Workspace"**
3. Review the permissions and click **"Allow"**
4. You will be redirected back to the OAuth & Permissions page

## Step 4: Copy Bot User OAuth Token

1. On the **"OAuth & Permissions"** page, you'll see **"Bot User OAuth Token"**
2. The token starts with `xoxb-`
3. Click **"Copy"** to copy the token
4. **Important**: Keep this token secure and never commit it to version control

## Step 5: Store Token Securely

You have two options for storing the token:

### Option A: Secret Manager (Recommended)

1. Create a secret in Google Cloud Secret Manager:
   ```bash
   echo -n "xoxb-your-token-here" | gcloud secrets create slack-bot-token \
       --data-file=- \
       --project=YOUR_GCP_PROJECT_ID
   ```

2. Grant access to the service account (if using Cloud Functions):
   ```bash
   gcloud secrets add-iam-policy-binding slack-bot-token \
       --member="serviceAccount:YOUR_SERVICE_ACCOUNT@YOUR_PROJECT.iam.gserviceaccount.com" \
       --role="roles/secretmanager.secretAccessor" \
       --project=YOUR_GCP_PROJECT_ID
   ```

3. Set environment variable:
   ```bash
   export SLACK_BOT_TOKEN_NAME="slack-bot-token"
   ```

### Option B: Environment Variable (Less Secure)

1. Set environment variable:
   ```bash
   export SLACK_BOT_TOKEN="xoxb-your-token-here"
   ```

## Step 6: Invite Bot to Channel

1. Go to the `users-to-delete-their-personal-data` channel in Slack
2. Type `/invite @GDPR Request Handler` (or whatever you named your app)
3. Or go to channel settings → Integrations → Add apps → Find your app

## Step 7: Verify Setup

You can verify the setup by running a test:

```bash
python -c "
from shared.slack_client import get_channel_id
channel_id = get_channel_id('users-to-delete-their-personal-data')
print(f'Channel ID: {channel_id}')
"
```

If you see a channel ID, the setup is successful!

## Troubleshooting

### "Channel not found" error
- Make sure the bot is invited to the channel
- Check that the channel name is correct (case-sensitive)
- For private channels, ensure the bot has `groups:read` and `groups:history` scopes

### "Invalid token" error
- Verify the token starts with `xoxb-`
- Check that the token hasn't been revoked
- Ensure the app is installed to the workspace

### "Missing scope" error
- Go back to OAuth & Permissions and add the missing scope
- Reinstall the app to the workspace after adding scopes

### Bot can't add reactions
- Ensure `reactions:write` scope is added
- Check that the bot is a member of the channel
- Verify the message timestamp is correct

## Security Best Practices

1. **Never commit tokens to version control**
   - Use Secret Manager or environment variables
   - Add `.env` to `.gitignore` if using local development

2. **Rotate tokens regularly**
   - If a token is compromised, regenerate it in Slack app settings
   - Update the secret in Secret Manager

3. **Use least privilege**
   - Only grant the minimum scopes needed
   - Don't grant admin scopes unless necessary

4. **Monitor usage**
   - Check Slack app usage in the Slack admin dashboard
   - Review logs for unexpected activity

## Additional Resources

- [Slack API Documentation](https://api.slack.com/)
- [Slack SDK for Python](https://slack.dev/python-slack-sdk/)
- [Google Cloud Secret Manager](https://cloud.google.com/secret-manager/docs)

