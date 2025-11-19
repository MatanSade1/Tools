#!/usr/bin/env python3
"""Remove computer emoji reactions from Slack messages."""
import sys
import os
from datetime import date, datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.slack_client import read_slack_channel_messages, get_channel_id, get_slack_bot_token
from shared.config import get_config

def has_emoji(message, emoji_name):
    """Check if message has emoji reaction."""
    reactions = message.get("reactions", [])
    for reaction in reactions:
        if reaction.get("name") == emoji_name:
            return True
    return False

def remove_reaction(channel_id, message_timestamp, emoji_name):
    """Remove an emoji reaction from a Slack message."""
    try:
        from slack_sdk import WebClient
    except ImportError:
        raise ImportError("slack-sdk is required. Install it with: pip install slack-sdk")
    
    bot_token = get_slack_bot_token()
    if not bot_token:
        raise ValueError("SLACK_BOT_TOKEN or SLACK_BOT_TOKEN_NAME must be configured")
    
    client = WebClient(token=bot_token)
    
    # Remove colons if present (e.g., :computer: -> computer)
    emoji_clean = emoji_name.strip(':')
    
    try:
        response = client.reactions_remove(
            channel=channel_id,
            timestamp=message_timestamp,
            name=emoji_clean
        )
        return response.get("ok", False)
    except Exception as e:
        print(f"Error removing reaction {emoji_name} from message: {e}")
        return False

def main():
    """Remove computer emoji from messages on November 16th."""
    config = get_config()
    channel_name = config.get("gdpr_slack_channel", "users-to-delete-their-personal-data")
    
    print("=" * 60)
    print("Remove Computer Emoji from Messages")
    print("=" * 60)
    print()
    print(f"Channel: {channel_name}")
    
    # Get channel ID
    channel_id = get_channel_id(channel_name)
    if not channel_id:
        print(f"❌ Channel '{channel_name}' not found")
        sys.exit(1)
    
    print(f"Channel ID: {channel_id}")
    print()
    
    # Fetch messages from November 16th
    target_date = date(2025, 11, 16)
    start_date = target_date
    end_date = date(2025, 11, 17)  # Up to but not including Nov 17
    
    print(f"Fetching messages from {start_date}...")
    
    try:
        from shared.slack_client import read_slack_channel_messages
        messages = read_slack_channel_messages(channel_name, start_date, end_date)
        print(f"✅ Fetched {len(messages)} messages")
        print()
    except Exception as e:
        print(f"❌ Error fetching messages: {e}")
        sys.exit(1)
    
    # Find messages with computer emoji
    messages_with_computer = []
    for msg in messages:
        if has_emoji(msg, "computer"):
            messages_with_computer.append(msg)
    
    print(f"Found {len(messages_with_computer)} messages with computer emoji")
    print()
    
    if not messages_with_computer:
        print("No messages with computer emoji found. Nothing to remove.")
        return
    
    # Remove computer emoji from each message
    removed_count = 0
    for msg in messages_with_computer:
        msg_ts = msg.get("ts")
        msg_text = msg.get("text", "")[:100]
        msg_time = datetime.fromtimestamp(float(msg_ts)).strftime("%Y-%m-%d %H:%M:%S")
        
        print(f"Removing computer emoji from message [{msg_time}]: {msg_text}...")
        
        success = remove_reaction(channel_id, msg_ts, "computer")
        if success:
            print(f"  ✅ Removed computer emoji")
            removed_count += 1
        else:
            print(f"  ❌ Failed to remove computer emoji")
        print()
    
    print("=" * 60)
    print(f"✅ Complete! Removed computer emoji from {removed_count} messages")
    print("=" * 60)
    print()
    print("You can now re-run the GDPR handler to process these messages:")
    print("  ./gdpr-handler/run.sh 2025-11-16 2025-11-17")

if __name__ == "__main__":
    main()

