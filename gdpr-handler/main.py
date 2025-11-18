"""GDPR Request Handler - Process Slack messages for user deletion requests."""
import argparse
import re
from datetime import datetime, date
from typing import Dict, List, Optional
from shared.config import get_config
from shared.slack_client import (
    read_slack_channel_messages,
    add_reaction_to_message,
    get_channel_id
)
from shared.bigquery_client import insert_gdpr_requests


def parse_date(date_str: str) -> date:
    """Parse date string in YYYY-MM-DD format."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}. Expected YYYY-MM-DD")


def has_emoji(message: Dict, emoji_name: str) -> bool:
    """
    Check if a message has a specific emoji reaction.
    
    Args:
        message: Slack message dictionary
        emoji_name: Emoji name (e.g., "blue_car", "computer")
    
    Returns:
        True if message has the emoji, False otherwise
    """
    reactions = message.get("reactions", [])
    for reaction in reactions:
        if reaction.get("name") == emoji_name:
            return True
    return False


def extract_distinct_id(message_text: str) -> Optional[str]:
    """
    Extract distinct_id (game user ID) from message text.
    
    Args:
        message_text: Message text from Slack
    
    Returns:
        distinct_id if found, None otherwise
    """
    # Common patterns for user IDs:
    # - "user_id: 12345"
    # - "distinct_id: 12345"
    # - "User ID: 12345"
    # - "ID: 12345"
    # - Just a number/string that looks like an ID
    
    patterns = [
        r'(?:user[_\s]?id|distinct[_\s]?id|id)[:\s]+([a-zA-Z0-9_-]+)',
        r'(?:user[_\s]?id|distinct[_\s]?id|id)[:\s]+([a-zA-Z0-9_-]+)',
        r'\b([a-zA-Z0-9]{8,})\b',  # Alphanumeric string of 8+ chars
    ]
    
    for pattern in patterns:
        match = re.search(pattern, message_text, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None


def extract_ticket_id(message_text: str) -> Optional[str]:
    """
    Extract ticket_id from message text.
    
    Args:
        message_text: Message text from Slack
    
    Returns:
        ticket_id if found, None otherwise
    """
    # Common patterns for ticket IDs:
    # - "ticket: 12345"
    # - "ticket_id: 12345"
    # - "Ticket: 12345"
    # - "#12345" (if it's a ticket number)
    
    patterns = [
        r'(?:ticket[_\s]?id|ticket)[:\s]+([a-zA-Z0-9_-]+)',
        r'#(\d+)',  # Hash followed by digits
        r'ticket[:\s]+([a-zA-Z0-9_-]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, message_text, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None


def extract_request_date(message: Dict, message_text: str) -> Optional[date]:
    """
    Extract request_date from message text or use message timestamp.
    
    Args:
        message: Slack message dictionary
        message_text: Message text from Slack
    
    Returns:
        request_date if found, None otherwise
    """
    # Try to extract date from message text
    date_patterns = [
        r'(\d{4}-\d{2}-\d{2})',  # YYYY-MM-DD
        r'(\d{2}/\d{2}/\d{4})',  # MM/DD/YYYY
        r'(\d{2}-\d{2}-\d{4})',  # MM-DD-YYYY
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, message_text)
        if match:
            date_str = match.group(1)
            try:
                # Try YYYY-MM-DD first
                if '-' in date_str and len(date_str.split('-')[0]) == 4:
                    return datetime.strptime(date_str, "%Y-%m-%d").date()
                # Try MM/DD/YYYY or MM-DD-YYYY
                elif '/' in date_str:
                    return datetime.strptime(date_str, "%m/%d/%Y").date()
                elif '-' in date_str:
                    return datetime.strptime(date_str, "%m-%d-%Y").date()
            except ValueError:
                continue
    
    # Fall back to message timestamp
    if "ts" in message:
        try:
            ts = float(message["ts"])
            dt = datetime.fromtimestamp(ts)
            return dt.date()
        except (ValueError, TypeError):
            pass
    
    return None


def parse_message(message: Dict) -> Optional[Dict]:
    """
    Parse a Slack message to extract GDPR deletion request information.
    
    Args:
        message: Slack message dictionary
    
    Returns:
        Dictionary with distinct_id, request_date, ticket_id, slack_message_ts
        or None if parsing fails
    """
    message_text = message.get("text", "")
    
    distinct_id = extract_distinct_id(message_text)
    ticket_id = extract_ticket_id(message_text)
    request_date = extract_request_date(message, message_text)
    
    # At minimum, we need distinct_id
    if not distinct_id:
        return None
    
    return {
        "distinct_id": distinct_id,
        "request_date": request_date,
        "ticket_id": ticket_id,
        "slack_message_ts": message.get("ts"),
    }


def process_gdpr_requests(
    start_date: date,
    end_date: date,
    channel_name: Optional[str] = None
):
    """
    Process GDPR deletion requests from Slack channel.
    
    Args:
        start_date: Start date for message scanning
        end_date: End date for message scanning
        channel_name: Slack channel name (optional, uses config default if not provided)
    """
    config = get_config()
    
    if not channel_name:
        channel_name = config.get("gdpr_slack_channel", "users-to-delete-their-personal-data")
    
    print(f"Processing GDPR requests from channel: {channel_name}")
    print(f"Date range: {start_date} to {end_date}")
    
    # Get channel ID
    channel_id = get_channel_id(channel_name)
    if not channel_id:
        raise ValueError(f"Channel '{channel_name}' not found")
    
    # Fetch messages
    print(f"Fetching messages from Slack...")
    messages = read_slack_channel_messages(channel_name, start_date, end_date)
    
    # Filter messages: has blue car emoji but no computer emoji
    print("Filtering messages with blue car emoji (but no computer emoji)...")
    filtered_messages = []
    for message in messages:
        # Check for blue car emoji in reactions (primary check)
        # Also check for :blue_car: or 🚗 in text as fallback
        has_blue_car = (
            has_emoji(message, "blue_car") or 
            ":blue_car:" in message.get("text", "") or
            "🚗" in message.get("text", "")
        )
        
        # Check for computer emoji in reactions (primary check)
        # Also check for :computer: or 💻 in text as fallback
        has_computer = (
            has_emoji(message, "computer") or
            ":computer:" in message.get("text", "") or
            "💻" in message.get("text", "")
        )
        
        if has_blue_car and not has_computer:
            filtered_messages.append(message)
    
    print(f"Found {len(filtered_messages)} messages matching criteria")
    
    # Parse messages and create BigQuery records
    gdpr_requests = []
    processed_count = 0
    error_count = 0
    
    for message in filtered_messages:
        try:
            parsed = parse_message(message)
            if not parsed:
                print(f"Warning: Could not parse message {message.get('ts')}: {message.get('text', '')[:100]}")
                error_count += 1
                continue
            
            # Create BigQuery record
            gdpr_request = {
                "distinct_id": parsed["distinct_id"],
                "request_date": parsed["request_date"],
                "ticket_id": parsed["ticket_id"],
                "mixpanel_request_id": None,
                "mixpanel_deletion_status": "pending",
                "singular_request_id": None,
                "singular_deletion_status": "pending",
                "bigquery_deletion_status": "not started",
                "game_state_status": "not started",
                "is_request_completed": False,
                "slack_message_ts": parsed["slack_message_ts"],
            }
            
            gdpr_requests.append(gdpr_request)
            
            # Add computer emoji reaction to message
            message_ts = message.get("ts")
            if message_ts:
                success = add_reaction_to_message(channel_id, message_ts, "computer")
                if success:
                    print(f"Added computer emoji to message {message_ts} for user {parsed['distinct_id']}")
                else:
                    print(f"Warning: Failed to add computer emoji to message {message_ts}")
            
            processed_count += 1
            
        except Exception as e:
            print(f"Error processing message {message.get('ts')}: {e}")
            error_count += 1
            continue
    
    # Insert into BigQuery
    if gdpr_requests:
        print(f"Inserting {len(gdpr_requests)} GDPR deletion requests into BigQuery...")
        try:
            insert_gdpr_requests(gdpr_requests)
            print(f"Successfully processed {processed_count} requests")
        except Exception as e:
            print(f"Error inserting into BigQuery: {e}")
            raise
    else:
        print("No GDPR requests to insert")
    
    if error_count > 0:
        print(f"Warning: {error_count} messages had errors during processing")
    
    print("Processing complete!")


def main():
    """Main entry point for GDPR request handler."""
    parser = argparse.ArgumentParser(
        description="Process GDPR deletion requests from Slack channel"
    )
    parser.add_argument(
        "--start-date",
        required=True,
        type=str,
        help="Start date for message scanning (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end-date",
        required=True,
        type=str,
        help="End date for message scanning (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--channel",
        type=str,
        help="Slack channel name (optional, uses config default if not provided)"
    )
    
    args = parser.parse_args()
    
    start_date = parse_date(args.start_date)
    end_date = parse_date(args.end_date)
    
    if start_date > end_date:
        raise ValueError("Start date must be before or equal to end date")
    
    try:
        process_gdpr_requests(start_date, end_date, args.channel)
    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    main()

