#!/usr/bin/env python3
"""Debug script to see what reactions are on messages."""
import sys
import os
from datetime import datetime, date

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.slack_client import read_slack_channel_messages, get_channel_id
from shared.config import get_config


def debug_reactions(start_date: date, end_date: date, channel_name: str = None):
    """Show all reactions on messages in the date range."""
    config = get_config()
    
    if not channel_name:
        channel_name = config.get("gdpr_slack_channel", "users-to-delete-their-personal-data")
    
    print(f"Checking reactions on messages in channel: {channel_name}")
    print(f"Date range: {start_date} to {end_date}\n")
    
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
    print(f"Found {len(messages)} messages\n")
    
    # Show reactions for each message
    for i, message in enumerate(messages, 1):
        message_ts = message.get("ts")
        text_preview = message.get("text", "")[:50].replace("\n", " ")
        reactions = message.get("reactions", [])
        
        print(f"Message {i} (ts: {message_ts}):")
        print(f"  Text preview: {text_preview}...")
        print(f"  Reactions ({len(reactions)}):")
        
        if reactions:
            for reaction in reactions:
                name = reaction.get("name", "unknown")
                count = reaction.get("count", 0)
                users = reaction.get("users", [])
                print(f"    - {name} (count: {count}, users: {len(users)})")
        else:
            print("    (no reactions)")
        print()


def parse_date(date_str: str) -> date:
    """Parse date string in YYYY-MM-DD format."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}. Use YYYY-MM-DD")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 debug-reactions.py <start-date> <end-date>")
        print("Example: python3 debug-reactions.py 2025-09-27 2025-10-09")
        sys.exit(1)
    
    start_date = parse_date(sys.argv[1])
    end_date = parse_date(sys.argv[2])
    
    if start_date > end_date:
        raise ValueError("Start date must be before or equal to end date")
    
    try:
        debug_reactions(start_date, end_date)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

