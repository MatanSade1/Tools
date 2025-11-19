#!/usr/bin/env python3
"""Test the full GDPR handler flow (dry run - no BigQuery insert)."""
import sys
import os
from datetime import date, datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.slack_client import read_slack_channel_messages, get_channel_id, add_reaction_to_message
from shared.config import get_config

def has_emoji(message, emoji_name):
    """Check if message has emoji reaction."""
    reactions = message.get("reactions", [])
    for reaction in reactions:
        if reaction.get("name") == emoji_name:
            return True
    return False

def main():
    token = os.getenv("SLACK_BOT_TOKEN")
    if not token:
        print("❌ ERROR: SLACK_BOT_TOKEN not set")
        sys.exit(1)
    
    config = get_config()
    channel_name = config.get("gdpr_slack_channel", "users-to-delete-their-personal-data")
    
    print("=" * 60)
    print("GDPR Handler - Full Flow Test (Dry Run)")
    print("=" * 60)
    print()
    print(f"Channel: {channel_name}")
    
    # Get channel ID
    channel_id = get_channel_id(channel_name)
    if not channel_id:
        print(f"❌ Channel not found")
        sys.exit(1)
    
    print(f"Channel ID: {channel_id}")
    print()
    
    # Test with a small date range (last 7 days)
    end_date = date.today()
    start_date = date.fromordinal(end_date.toordinal() - 7)
    
    print(f"Date range: {start_date} to {end_date}")
    print()
    print("Fetching messages...")
    
    try:
        messages = read_slack_channel_messages(channel_name, start_date, end_date)
        print(f"✅ Fetched {len(messages)} messages")
        print()
    except Exception as e:
        print(f"❌ Error fetching messages: {e}")
        sys.exit(1)
    
    # Filter messages
    print("Filtering messages (blue car emoji, no computer emoji)...")
    filtered = []
    for msg in messages:
        has_blue_car = (
            has_emoji(msg, "blue_car") or 
            ":blue_car:" in msg.get("text", "") or
            "🚗" in msg.get("text", "")
        )
        has_computer = (
            has_emoji(msg, "computer") or
            ":computer:" in msg.get("text", "") or
            "💻" in msg.get("text", "")
        )
        
        if has_blue_car and not has_computer:
            filtered.append(msg)
    
    print(f"✅ Found {len(filtered)} messages matching criteria")
    print()
    
    if filtered:
        print("Sample messages:")
        for i, msg in enumerate(filtered[:3], 1):
            text = msg.get("text", "")[:100]
            ts = msg.get("ts", "")
            print(f"  {i}. [{ts}] {text}...")
        print()
        print(f"Total messages to process: {len(filtered)}")
        print()
        print("✅ Ready to process! Run the actual handler to:")
        print("  1. Parse messages and extract user data")
        print("  2. Create BigQuery records")
        print("  3. Add computer emoji to processed messages")
    else:
        print("ℹ️  No messages found matching the criteria in this date range")
        print("   (Messages need blue car emoji but no computer emoji)")
    
    print()
    print("=" * 60)

if __name__ == "__main__":
    main()

