#!/usr/bin/env python3
"""Test fetching and filtering messages from Slack channel."""
import sys
import os
from datetime import date

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
channel_name = "users-to-delete-their-personal-data"

print("=" * 60)
print("Testing Message Fetching and Filtering")
print("=" * 60)
print()

# Get channel ID
print("1. Finding channel...")
channels = client.conversations_list(types="public_channel,private_channel", limit=1000)
channel_id = None
for ch in channels.get("channels", []):
    if ch.get("name") == channel_name:
        channel_id = ch.get("id")
        break

if not channel_id:
    print(f"❌ Channel '{channel_name}' not found")
    sys.exit(1)

print(f"   ✅ Channel found: {channel_id}")
print()

# Fetch messages from last 30 days
print("2. Fetching messages (last 30 days)...")
from datetime import datetime, timedelta
end_date = date.today()
start_date = end_date - timedelta(days=30)

start_ts = int(datetime.combine(start_date, datetime.min.time()).timestamp())
end_ts = int(datetime.combine(end_date, datetime.max.time()).timestamp())

all_messages = []
cursor = None
while True:
    params = {
        "channel": channel_id,
        "oldest": str(start_ts),
        "latest": str(end_ts),
        "limit": 200
    }
    if cursor:
        params["cursor"] = cursor
    
    response = client.conversations_history(**params)
    if not response.get("ok"):
        print(f"   ❌ Error: {response.get('error')}")
        break
    
    messages = response.get("messages", [])
    all_messages.extend(messages)
    
    cursor = response.get("response_metadata", {}).get("next_cursor")
    if not cursor:
        break

print(f"   ✅ Fetched {len(all_messages)} messages")
print()

# Filter messages
print("3. Filtering messages (blue car emoji, no computer emoji)...")

def has_emoji_reaction(msg, emoji_name):
    reactions = msg.get("reactions", [])
    for r in reactions:
        if r.get("name") == emoji_name:
            return True
    return False

filtered = []
for msg in all_messages:
    text = msg.get("text", "")
    has_blue_car = (
        has_emoji_reaction(msg, "blue_car") or
        ":blue_car:" in text or
        "🚗" in text
    )
    has_computer = (
        has_emoji_reaction(msg, "computer") or
        ":computer:" in text or
        "💻" in text
    )
    
    if has_blue_car and not has_computer:
        filtered.append(msg)

print(f"   ✅ Found {len(filtered)} messages matching criteria")
print()

if filtered:
    print("4. Sample messages:")
    for i, msg in enumerate(filtered[:5], 1):
        text = msg.get("text", "")[:150].replace("\n", " ")
        ts = msg.get("ts", "")
        dt = datetime.fromtimestamp(float(ts))
        print(f"   {i}. [{dt.strftime('%Y-%m-%d %H:%M')}] {text}...")
        print()
    
    print("=" * 60)
    print(f"✅ Ready! Found {len(filtered)} messages to process")
    print("=" * 60)
    print()
    print("Next step: Run the actual handler:")
    print("  export SLACK_BOT_TOKEN='...'")
    print("  export GCP_PROJECT_ID='yotam-395120'")
    print("  python3 gdpr-handler/main.py --start-date 2025-11-17 --end-date 2025-12-31")
else:
    print("ℹ️  No messages found matching criteria")
    print("   (Need: blue car emoji, no computer emoji)")

