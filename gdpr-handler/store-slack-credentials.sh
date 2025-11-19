#!/bin/bash
# Store Slack app credentials (for reference, not for direct use)

APP_ID="A09TVFPGM4K"
CLIENT_ID="3895608132162.9947533565155"
CLIENT_SECRET="ef9356eca5bbc5e1f170187ba991e820"
SIGNING_SECRET="273d88c99ed7cf2178e38546af127c39"
VERIFICATION_TOKEN="gpzsZKbMsNppdfL1RAGJ6u8v"

echo "Slack App Credentials (for reference):"
echo "App ID: $APP_ID"
echo "Client ID: $CLIENT_ID"
echo ""
echo "⚠️  NOTE: These are OAuth credentials, not the Bot Token we need."
echo ""
echo "To get the Bot User OAuth Token:"
echo "1. Go to: https://api.slack.com/apps/$APP_ID"
echo "2. Click 'OAuth & Permissions'"
echo "3. Find 'Bot User OAuth Token' (starts with xoxb-)"
echo "4. Copy it and run: ./setup-slack-token.sh"
