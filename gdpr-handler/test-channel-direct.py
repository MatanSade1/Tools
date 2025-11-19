#!/usr/bin/env python3
"""Test channel access directly by channel name."""
import sys
import os

token = os.getenv("SLACK_BOT_TOKEN")
if not token:
    print("❌ ERROR: SLACK_BOT_TOKEN not set")
    sys.exit(1)

try:
    from slack_sdk import WebClient
except ImportError:
    print("❌ ERROR: slack-sdk not installed")
    sys.exit(1)

client = WebClient(token=token)

print("Testing Slack connection...")
print()

# Test auth
auth = client.auth_test()
if not auth.get("ok"):
    print(f"❌ Auth failed: {auth.get('error')}")
    sys.exit(1)

print(f"✅ Connected to: {auth.get('team')}")
print(f"✅ Bot user: {auth.get('user')}")
print()

# Try to get channel by name directly (if we know the channel ID)
channel_name = "users-to-delete-their-personal-data"

# Method 1: Try conversations.list with pagination
print(f"Attempting to find channel: {channel_name}")
print()

try:
    # Try with channels:read scope
    response = client.conversations_list(types="public_channel,private_channel", limit=1000)
    
    if response.get("ok"):
        channels = response.get("channels", [])
        print(f"✅ Found {len(channels)} channels")
        
        # Look for our channel
        found = False
        for channel in channels:
            if channel.get("name") == channel_name:
                channel_id = channel.get("id")
                print(f"✅ Channel '{channel_name}' found: {channel_id}")
                found = True
                
                # Try to read messages
                try:
                    history = client.conversations_history(channel=channel_id, limit=1)
                    if history.get("ok"):
                        print(f"✅ Can read messages from channel")
                    else:
                        print(f"⚠️  Cannot read messages: {history.get('error')}")
                except Exception as e:
                    print(f"⚠️  Error reading messages: {e}")
                break
        
        if not found:
            print(f"❌ Channel '{channel_name}' not found in list")
            print()
            print("Possible reasons:")
            print("- Bot is not invited to the channel")
            print("- Channel name is different")
            print("- Need to check private channels separately")
    else:
        error = response.get("error")
        print(f"❌ Error: {error}")
        
        if error == "missing_scope":
            needed = response.get("needed", [])
            provided = response.get("provided", [])
            print()
            print("Missing scopes:")
            if isinstance(needed, str):
                print(f"  Needed: {needed}")
            else:
                for scope in needed:
                    if scope not in provided:
                        print(f"  - {scope}")
            print()
            print("To fix:")
            print("1. Go to: https://api.slack.com/apps/A09TVFPGM4K")
            print("2. Click 'OAuth & Permissions'")
            print("3. Add the missing scopes listed above")
            print("4. Click 'Reinstall to Workspace' (IMPORTANT!)")
            print("5. Approve the permissions")
            print()
            print("⚠️  NOTE: You MUST reinstall after adding scopes!")
            
except Exception as e:
    print(f"❌ Error: {e}")

