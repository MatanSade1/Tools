#!/usr/bin/env python3
"""Find the channel and check if bot is invited."""
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

print("Searching for channel: users-to-delete-their-personal-data")
print()

# Get all channels
response = client.conversations_list(types="public_channel,private_channel", limit=1000)

if not response.get("ok"):
    print(f"❌ Error: {response.get('error')}")
    sys.exit(1)

channels = response.get("channels", [])
print(f"Found {len(channels)} channels")
print()

# Look for exact match
exact_match = None
partial_matches = []

for channel in channels:
    name = channel.get("name", "")
    if name == "users-to-delete-their-personal-data":
        exact_match = channel
    elif "delete" in name.lower() or "personal" in name.lower() or "data" in name.lower():
        partial_matches.append(channel)

if exact_match:
    print("✅ Found exact match:")
    print(f"   Name: {exact_match.get('name')}")
    print(f"   ID: {exact_match.get('id')}")
    print(f"   Is Private: {exact_match.get('is_private', False)}")
    print(f"   Is Member: {exact_match.get('is_member', False)}")
    print()
    
    if not exact_match.get('is_member'):
        print("⚠️  WARNING: Bot is NOT a member of this channel!")
        print()
        print("To fix:")
        print("1. Go to the channel in Slack")
        print("2. Type: /invite @gpdrhandler")
        print("   (or whatever your bot name is)")
        print("3. Or go to channel settings → Integrations → Add apps")
    else:
        print("✅ Bot is a member of the channel!")
        print()
        # Try to read messages
        try:
            history = client.conversations_history(channel=exact_match.get('id'), limit=1)
            if history.get("ok"):
                print("✅ Can read messages from channel!")
            else:
                print(f"⚠️  Cannot read messages: {history.get('error')}")
        except Exception as e:
            print(f"⚠️  Error reading messages: {e}")
else:
    print("❌ Channel 'users-to-delete-their-personal-data' not found")
    print()
    
    if partial_matches:
        print("Found similar channels:")
        for ch in partial_matches[:5]:
            print(f"  - {ch.get('name')} (ID: {ch.get('id')}, Private: {ch.get('is_private')}, Member: {ch.get('is_member')})")
        print()
    
    print("Possible reasons:")
    print("1. Channel name is different")
    print("2. Bot is not invited to the channel")
    print("3. Channel doesn't exist")
    print()
    print("To invite bot:")
    print("1. Go to the channel in Slack")
    print("2. Type: /invite @gpdrhandler")
    print("3. Or check channel settings → Integrations")

