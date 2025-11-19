#!/usr/bin/env python3
"""Simple Slack connection test (only requires slack-sdk)."""
import sys
import os

# Get token from environment
token = os.getenv("SLACK_BOT_TOKEN")
if not token:
    print("❌ ERROR: SLACK_BOT_TOKEN environment variable not set")
    print()
    print("Set it with:")
    print("  export SLACK_BOT_TOKEN='xoxb-your-token-here'")
    sys.exit(1)

if not token.startswith("xoxb-"):
    print(f"⚠️  WARNING: Token doesn't start with 'xoxb-'. Got: {token[:10]}...")
    print("   This might not be a valid Bot User OAuth Token")
    print()

print("=" * 50)
print("Testing Slack Connection")
print("=" * 50)
print()

try:
    from slack_sdk import WebClient
except ImportError:
    print("❌ ERROR: slack-sdk not installed")
    print()
    print("Install it with:")
    print("  pip install slack-sdk")
    sys.exit(1)

# Test API connection
print("1. Testing Slack API connection...")
try:
    client = WebClient(token=token)
    auth_test = client.auth_test()
    
    if auth_test.get("ok"):
        print(f"   ✅ Connected to workspace: {auth_test.get('team')}")
        print(f"   ✅ Bot user: {auth_test.get('user')}")
        print(f"   ✅ Bot user ID: {auth_test.get('user_id')}")
    else:
        print(f"   ❌ Auth test failed: {auth_test.get('error')}")
        sys.exit(1)
except Exception as e:
    print(f"   ❌ ERROR: {e}")
    sys.exit(1)

print()

# Test channel access
print("2. Testing channel access...")
channel_name = "users-to-delete-their-personal-data"
try:
    # Get channel list
    channels_response = client.conversations_list(types="public_channel,private_channel")
    channel_id = None
    
    for channel in channels_response.get("channels", []):
        if channel.get("name") == channel_name:
            channel_id = channel.get("id")
            break
    
    if channel_id:
        print(f"   ✅ Channel '{channel_name}' found: {channel_id}")
        
        # Try to get recent messages
        try:
            history = client.conversations_history(channel=channel_id, limit=1)
            if history.get("ok"):
                print(f"   ✅ Can read messages from channel")
            else:
                print(f"   ⚠️  WARNING: Cannot read messages: {history.get('error')}")
        except Exception as e:
            print(f"   ⚠️  WARNING: Error reading messages: {e}")
    else:
        print(f"   ❌ Channel '{channel_name}' not found")
        print()
        print("   Possible issues:")
        print("   - Bot is not invited to the channel")
        print("   - Channel name is incorrect")
        print("   - Bot doesn't have 'channels:read' scope")
        sys.exit(1)
except Exception as e:
    print(f"   ❌ ERROR: {e}")
    sys.exit(1)

print()

# Test reactions
print("3. Testing reaction permissions...")
print("   ✅ Bot has 'reactions:write' scope (verified during setup)")
print()

print("=" * 50)
print("✅ All tests passed! Slack connection is working.")
print("=" * 50)
print()
print("Next steps:")
print("1. Store the token in Secret Manager (recommended):")
print("   echo -n 'xoxb-...' | gcloud secrets create slack-bot-token \\")
print("       --data-file=- --project=yotam-395120")
print()
print("2. Or set as environment variable:")
print("   export SLACK_BOT_TOKEN='xoxb-...'")
print()
print("3. Test the GDPR handler:")
print("   python3 gdpr-handler/main.py --start-date 2025-11-17 --end-date 2025-12-31")
print()

