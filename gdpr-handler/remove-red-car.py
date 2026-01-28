#!/usr/bin/env python3
"""Remove red_car emoji from messages in a date range."""
import sys
import os
from datetime import datetime, date

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.slack_client import read_slack_channel_messages, remove_reaction, get_channel_id
from shared.config import get_config
from typing import Dict


def has_emoji(message: Dict, emoji_name: str) -> bool:
    """
    Check if a message has a specific emoji reaction.
    
    Args:
        message: Slack message dictionary
        emoji_name: Emoji name (e.g., "blue_car", "computer", "red_car")
    
    Returns:
        True if message has the emoji, False otherwise
    """
    reactions = message.get("reactions", [])
    for reaction in reactions:
        if reaction.get("name") == emoji_name:
            return True
    return False


def remove_red_car_emojis(start_date: date, end_date: date, channel_name: str = None):
    """Remove red_car emoji from all messages in the date range."""
    config = get_config()
    
    if not channel_name:
        channel_name = config.get("gdpr_slack_channel", "users-to-delete-their-personal-data")
    
    print(f"Removing red_car emojis from channel: {channel_name}")
    print(f"Date range: {start_date} to {end_date}")
    
    # Get channel ID
    try:
        channel_id = get_channel_id(channel_name)
        if not channel_id:
            raise ValueError(f"Channel '{channel_name}' not found")
    except Exception as e:
        raise ValueError(f"Error accessing channel '{channel_name}': {e}")
    
    # Fetch messages
    print(f"Fetching messages from Slack...")
    messages = read_slack_channel_messages(channel_name, start_date, end_date)
    print(f"Found {len(messages)} messages")
    
    # Find messages with car emoji (red car - Slack uses "car" as the emoji name)
    messages_with_car = []
    for message in messages:
        has_car = has_emoji(message, "car")
        if has_car:
            messages_with_car.append(message)
    
    print(f"Found {len(messages_with_car)} messages with car emoji")
    
    # Remove car emoji from each message
    removed_count = 0
    error_count = 0
    
    for message in messages_with_car:
        message_ts = message.get("ts")
        if message_ts:
            try:
                success = remove_reaction(channel_id, message_ts, "car")
                if success:
                    print(f"✅ Removed car emoji from message {message_ts}")
                    removed_count += 1
                else:
                    print(f"⚠️  Failed to remove car emoji from message {message_ts}")
                    error_count += 1
            except Exception as e:
                print(f"❌ Error removing car emoji from message {message_ts}: {e}")
                error_count += 1
    
    print(f"\n✅ Removed car emoji from {removed_count} messages")
    if error_count > 0:
        print(f"⚠️  {error_count} messages had errors")


def parse_date(date_str: str) -> date:
    """Parse date string in YYYY-MM-DD format."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}. Use YYYY-MM-DD")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 remove-red-car.py <start-date> <end-date>")
        print("Example: python3 remove-red-car.py 2025-09-27 2025-10-09")
        sys.exit(1)
    
    start_date = parse_date(sys.argv[1])
    end_date = parse_date(sys.argv[2])
    
    if start_date > end_date:
        raise ValueError("Start date must be before or equal to end date")
    
    try:
        remove_red_car_emojis(start_date, end_date)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

