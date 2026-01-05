"""GDPR Request Handler - Process Slack messages for user deletion requests."""
import argparse
import re
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional
from shared.config import get_config
from shared.slack_client import (
    read_slack_channel_messages,
    add_reaction_to_message,
    remove_reaction,
    get_channel_id
)
from shared.bigquery_client import (
    insert_gdpr_requests,
    get_gdpr_request_by_ticket_id,
    update_gdpr_request_status,
    get_player_dates
)
from api_clients import (
    create_mixpanel_gdpr_request,
    create_singular_gdpr_request,
    check_mixpanel_gdpr_status,
    check_singular_gdpr_status
)


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


def is_valid_gdpr_message(message: Dict) -> bool:
    """
    Check if message contains all required words for GDPR deletion request.
    
    Required words (case-insensitive):
    - "delete"
    - "user" (matches "user", "userid", "user_id", etc.)
    - "ticket"
    
    Args:
        message: Slack message dictionary
    
    Returns:
        True if message contains all three required words, False otherwise
    """
    message_text = message.get("text", "").lower()
    
    has_delete = "delete" in message_text
    has_user = "user" in message_text  # Matches "user", "userid", "user_id", etc.
    has_ticket = "ticket" in message_text
    
    return has_delete and has_user and has_ticket


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
        r'(?:user[_\s]?id|distinct[_\s]?id|id)[:\s=]+([a-zA-Z0-9_-]+)',
        r'(?:user[_\s]?id|distinct[_\s]?id)[:\s=]+([a-zA-Z0-9_-]+)',
        r'\bdistinct[_\s]?id[:\s=]+([a-zA-Z0-9_-]+)',
        r'\b([a-zA-Z0-9]{8,})\b',  # Alphanumeric string of 8+ chars (fallback)
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
        r'ticket\s+number\s+(\d+)',  # "Ticket number 3880"
        r'ticket\s+(\d+)',  # "Ticket 3880"
        r'(?:ticket[_\s]?id|ticket)[:\s=]+(\d+)',  # "ticket: 3880" or "ticket_id: 3880"
        r'#(\d+)',  # Hash followed by digits
        r'ticket[:\s=]+([a-zA-Z0-9_-]+)',  # Fallback for non-numeric tickets
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
    try:
        channel_id = get_channel_id(channel_name)
        if not channel_id:
            raise ValueError(f"Channel '{channel_name}' not found. Make sure the bot is invited to the channel.")
    except Exception as e:
        raise ValueError(f"Error accessing channel '{channel_name}': {e}")
    
    # Fetch messages
    print(f"Fetching messages from Slack...")
    messages = read_slack_channel_messages(channel_name, start_date, end_date)
    
    # Filter messages: must contain "delete", "user", and "ticket" (case-insensitive)
    print("Filtering valid GDPR deletion request messages...")
    filtered_messages = []
    status_check_messages = []  # Messages with computer emoji for status checking
    
    for message in messages:
        # Check if message is a valid GDPR deletion request
        is_valid = is_valid_gdpr_message(message)
        
        if not is_valid:
            continue  # Skip messages that don't match the validation criteria
        
        has_computer = (
            has_emoji(message, "computer") or
            ":computer:" in message.get("text", "") or
            "💻" in message.get("text", "")
        )
        
        if not has_computer:
            filtered_messages.append(message)
        elif has_computer:
            status_check_messages.append(message)
    
    print(f"Found {len(filtered_messages)} new messages to process")
    print(f"Found {len(status_check_messages)} messages with computer emoji for status check")
    
    # Ensure table exists
    from shared.bigquery_client import ensure_gdpr_table_exists
    ensure_gdpr_table_exists()
    
    # Process new messages (Phase 1: New Request Processing)
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
            
            distinct_id = parsed["distinct_id"]
            print(f"\nProcessing deletion request for user: {distinct_id}")
            
            # Fetch player data to get last_activity_date
            player_data = get_player_dates([distinct_id])
            player_info = player_data.get(distinct_id, {})
            last_activity_date = player_info.get("last_activity_date")
            install_date = player_info.get("install_date")
            
            # 14-day activity check
            days_since_activity = None
            if last_activity_date:
                days_since_activity = (date.today() - last_activity_date).days
                print(f"📅 Last activity: {last_activity_date} ({days_since_activity} days ago)")
            
            mixpanel_request_id = None
            singular_request_id = None
            
            # Check if we should create deletion requests (14-day rule)
            if days_since_activity is None or days_since_activity >= 14:
                if days_since_activity is not None:
                    print(f"✅ {days_since_activity} days since last activity (>= 14 days) - Creating deletion requests")
                else:
                    print(f"⚠️  No last_activity_date found, proceeding with deletion requests")
                
                # Create Mixpanel GDPR request
                try:
                    print(f"Creating Mixpanel GDPR deletion request...")
                    mixpanel_request_id = create_mixpanel_gdpr_request(distinct_id, compliance_type="gdpr")
                except Exception as e:
                    print(f"⚠️  Failed to create Mixpanel request: {e}")
                
                # Create Singular GDPR request
                try:
                    print(f"Creating Singular GDPR deletion request...")
                    singular_request_id = create_singular_gdpr_request(distinct_id)
                except Exception as e:
                    print(f"⚠️  Failed to create Singular request: {e}")
                
                # Remove clock1 emoji if present, add computer emoji
                message_ts = message.get("ts")
                if message_ts:
                    try:
                        remove_reaction(channel_id, message_ts, "clock1")
                    except:
                        pass
                    try:
                        remove_reaction(channel_id, message_ts, "computer")
                    except:
                        pass
                    success = add_reaction_to_message(channel_id, message_ts, "computer")
                    if success:
                        print(f"✅ Added computer emoji to message {message_ts} for user {distinct_id}")
            else:
                # Less than 14 days - skip API requests, add clock1 emoji
                print(f"⏰ Only {days_since_activity} days since last activity (< 14 days) - Skipping deletion requests")
                print(f"   Will add clock1 emoji and create record without request IDs")
                
                message_ts = message.get("ts")
                if message_ts:
                    try:
                        remove_reaction(channel_id, message_ts, "computer")
                    except:
                        pass
                    try:
                        remove_reaction(channel_id, message_ts, "clock1")
                    except:
                        pass
                    success = add_reaction_to_message(channel_id, message_ts, "clock1")
                    if success:
                        print(f"✅ Added clock1 emoji to message {message_ts} for user {distinct_id}")
            
            # Create BigQuery record with API request IDs
            gdpr_request = {
                "distinct_id": distinct_id,
                "request_date": parsed["request_date"],
                "ticket_id": parsed["ticket_id"],
                "mixpanel_request_id": mixpanel_request_id,
                "mixpanel_deletion_status": "pending" if mixpanel_request_id else "not started",
                "singular_request_id": singular_request_id,
                "singular_deletion_status": "pending" if singular_request_id else "not started",
                "bigquery_deletion_status": "not started",
                "game_state_status": "not started",
                "is_request_completed": False,
                "slack_message_ts": parsed["slack_message_ts"],
                "install_date": install_date,
                "last_activity_date": last_activity_date,
            }
            
            gdpr_requests.append(gdpr_request)
            processed_count += 1
            
        except Exception as e:
            print(f"Error processing message {message.get('ts')}: {e}")
            error_count += 1
            continue
    
    # Insert into BigQuery
    if gdpr_requests:
        print(f"\nInserting {len(gdpr_requests)} GDPR deletion requests into BigQuery...")
        try:
            insert_gdpr_requests(gdpr_requests)
            print(f"Successfully processed {processed_count} requests")
        except Exception as e:
            print(f"Error inserting into BigQuery: {e}")
            raise
    
    # Process messages with computer emoji (Phase 2: Status Check Processing)
    status_check_count = 0
    status_error_count = 0
    
    for message in status_check_messages:
        try:
            parsed = parse_message(message)
            if not parsed or not parsed.get("ticket_id"):
                print(f"Warning: Could not parse message or missing ticket_id: {message.get('ts')}")
                continue
            
            ticket_id = parsed["ticket_id"]
            print(f"\nChecking status for ticket: {ticket_id}")
            
            # Get record from BigQuery
            record = get_gdpr_request_by_ticket_id(ticket_id)
            if not record:
                print(f"⚠️  No record found in BigQuery for ticket {ticket_id}")
                continue
            
            mixpanel_request_id = record.get("mixpanel_request_id")
            singular_request_id = record.get("singular_request_id")
            
            # Check Mixpanel status
            mixpanel_status = None
            if mixpanel_request_id:
                print(f"Checking Mixpanel status for request: {mixpanel_request_id}")
                mixpanel_status = check_mixpanel_gdpr_status(mixpanel_request_id)
                if mixpanel_status:
                    print(f"  Mixpanel status: {mixpanel_status}")
            else:
                print("  No Mixpanel request ID found")
            
            # Check Singular status
            singular_status = None
            if singular_request_id:
                print(f"Checking Singular status for request: {singular_request_id}")
                singular_status = check_singular_gdpr_status(singular_request_id)
                if singular_status:
                    print(f"  Singular status: {singular_status}")
            else:
                print("  No Singular request ID found")
            
            # Update BigQuery with latest statuses
            final_mixpanel_status = mixpanel_status if mixpanel_status else record.get("mixpanel_deletion_status")
            final_singular_status = singular_status if singular_status else record.get("singular_deletion_status")
            
            if mixpanel_status or singular_status:
                update_gdpr_request_status(
                    ticket_id,
                    mixpanel_status=mixpanel_status,
                    singular_status=singular_status
                )
            
            # Update emojis based on status
            message_ts = message.get("ts")
            if message_ts:
                mixpanel_done = (final_mixpanel_status == "completed")
                singular_done = (final_singular_status == "completed")
                
                # If both Mixpanel and Singular are completed, add red car
                if mixpanel_done and singular_done:
                    success = add_reaction_to_message(channel_id, message_ts, "car")
                    if success:
                        print(f"✅ Added car emoji to message {message_ts}")
                
                # Check if all deletions are completed
                bigquery_status = record.get("bigquery_deletion_status")
                game_state_status = record.get("game_state_status")
                
                bigquery_done = (bigquery_status == "completed")
                game_state_done = (game_state_status == "completed")
                
                if mixpanel_done and singular_done and bigquery_done and game_state_done:
                    # All deletions completed - add white check mark, remove red car and computer
                    try:
                        remove_reaction(channel_id, message_ts, "car")
                    except:
                        pass
                    try:
                        remove_reaction(channel_id, message_ts, "computer")
                    except:
                        pass
                    success = add_reaction_to_message(channel_id, message_ts, "white_check_mark")
                    if success:
                        print(f"✅ All deletions completed! Added white_check_mark emoji")
                    
                    update_gdpr_request_status(ticket_id, is_request_completed=True)
                    print(f"✅ Updated is_request_completed to true for ticket {ticket_id}")
                else:
                    pending_items = []
                    if not mixpanel_done:
                        pending_items.append(f"Mixpanel={final_mixpanel_status}")
                    if not singular_done:
                        pending_items.append(f"Singular={final_singular_status}")
                    if not bigquery_done:
                        pending_items.append(f"BigQuery={bigquery_status}")
                    if not game_state_done:
                        pending_items.append(f"GameState={game_state_status}")
                    print(f"⏳ Still waiting for: {', '.join(pending_items)}")
            
            status_check_count += 1
            
        except Exception as e:
            print(f"Error processing status check for message {message.get('ts')}: {e}")
            status_error_count += 1
            continue
    
    if status_check_count > 0:
        print(f"\n✅ Status check complete: {status_check_count} messages processed")
    
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

