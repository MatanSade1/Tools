"""Slack webhook client for sending alerts."""
import os
import json
import requests
from typing import Dict, List, Optional
from datetime import datetime, date
from shared.config import get_config


def send_slack_alert(
    event_name: str,
    alert_data: List[Dict],
    channel: Optional[str] = None,
    webhook_url: Optional[str] = None
):
    """
    Send alert to Slack channel.
    
    Args:
        event_name: Name of the event that triggered the alert
        alert_data: List of dicts with keys: minute_timestamp, event_count, sample_events
        channel: Slack channel to send to (overrides default webhook channel)
        webhook_url: Custom webhook URL (overrides default)
    """
    config = get_config()
    webhook = webhook_url or config.get("slack_webhook_url")
    
    if not webhook:
        print("Warning: No Slack webhook URL configured, skipping alert")
        return
    
    # Format message
    message = format_slack_message(event_name, alert_data, channel)
    
    # Send to Slack
    try:
        response = requests.post(
            webhook,
            json=message,
            timeout=10
        )
        response.raise_for_status()
        print(f"Successfully sent Slack alert for {event_name}")
    except requests.exceptions.RequestException as e:
        print(f"Error sending Slack alert: {e}")
        raise


def format_slack_message(
    event_name: str,
    alert_data: List[Dict],
    channel: Optional[str] = None
) -> Dict:
    """
    Format alert data as Slack message.
    
    Args:
        event_name: Name of the event
        alert_data: List of alert data per minute
        channel: Optional channel override
    
    Returns:
        Formatted Slack message dict
    """
    total_events = sum(a["event_count"] for a in alert_data)
    max_count = max(a["event_count"] for a in alert_data) if alert_data else 0
    
    # Build blocks
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"🚨 Alert: Abnormal Event Activity Detected"
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Event:*\n`{event_name}`"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Total Events:*\n{total_events}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Max per Minute:*\n{max_count}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Time:*\n{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
                }
            ]
        }
    ]
    
    # Add details for each minute
    for alert in alert_data:
        minute_str = alert["minute_timestamp"].strftime("%Y-%m-%d %H:%M:%S UTC")
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{minute_str}*\n*Count:* {alert['event_count']} events"
            }
        })
        
        # Add sample events if available
        if alert.get("sample_events"):
            sample_text = "Sample events:\n"
            for i, sample in enumerate(alert["sample_events"][:3], 1):
                props = sample.get("properties", {})
                props_str = json.dumps(props, indent=2) if props else "No properties"
                sample_text += f"```{props_str}```\n"
            
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": sample_text
                }
            })
    
    # Add divider
    blocks.append({"type": "divider"})
    
    # Add BigQuery link
    config = get_config()
    bq_project = config["gcp_project_id"]
    bq_dataset = config["bigquery_dataset"]
    bq_table = config["bigquery_table"]
    
    query_url = (
        f"https://console.cloud.google.com/bigquery?"
        f"project={bq_project}&"
        f"ws=!1m5!1m4!4m3!1s{bq_project}!2s{bq_dataset}!3s{bq_table}"
    )
    
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"<{query_url}|View in BigQuery>"
        }
    })
    
    message = {
        "blocks": blocks
    }
    
    # Add channel override if provided (for Slack apps with channel parameter support)
    if channel:
        message["channel"] = channel
    
    return message


def get_slack_webhook_url(channel: str) -> str:
    """
    Get the Slack webhook URL for a specific channel.
    
    Args:
        channel: Channel name (e.g., 'data-alerts-sandbox', 'data-alerts-critical', 'data-alerts-non-critical')
                 Can include or exclude the '#' prefix
    
    Returns:
        Full webhook URL for the channel
    """
    base_url = "https://hooks.slack.com/services/T03SBHW3W4S"
    
    channel_tokens = {
        'data-alerts-sandbox': 'B089W8NRF1A/fjiKtqyUekCbnxLRnFRRx3cp',
        'data-alerts-critical': 'B08C1BKGYJ3/g3o3p9JNKPVybiIQIxUp77Cy',
        'data-alerts-non-critical': 'B08CUJ7PMDX/YXoVzLajPWgyYcqEvMvzQyGL'
    }
    
    # Handle channel names with or without #
    channel_clean = channel.lstrip('#')
    
    token = channel_tokens.get(channel_clean)
    if not token:
        print(f"Warning: No webhook token found for channel {channel}, using sandbox channel")
        token = channel_tokens['data-alerts-sandbox']
    
    return f"{base_url}/{token}"


def send_rt_alert(
    meaningful_name: str,
    event_name: str,
    event_count: int,
    threshold: int,
    channel: Optional[str] = None,
    webhook_url: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None
):
    """
    Send RT alert to Slack channel with custom format.
    
    Args:
        meaningful_name: Human-readable name for the alert
        event_name: Name of the event that triggered the alert
        event_count: Current count of events
        threshold: Threshold that was exceeded
        channel: Slack channel to send to (required if webhook_url not provided)
        webhook_url: Custom webhook URL (optional, overrides channel-based lookup)
        start_time: Start time of the aggregation window (optional)
        end_time: End time of the aggregation window (optional)
    """
    # Use provided webhook_url or get channel-specific webhook
    if webhook_url:
        webhook = webhook_url
    elif channel:
        webhook = get_slack_webhook_url(channel)
    else:
        print("Warning: No Slack webhook URL or channel configured, skipping alert")
        return
    
    # Format message (remove channel from message since webhook URL determines channel)
    message = format_rt_alert_message(
        meaningful_name=meaningful_name,
        event_name=event_name,
        event_count=event_count,
        threshold=threshold,
        start_time=start_time,
        end_time=end_time
    )
    
    # Send to Slack
    try:
        response = requests.post(
            webhook,
            json=message,
            timeout=10
        )
        response.raise_for_status()
        print(f"Successfully sent RT Slack alert for {event_name} to {channel or 'custom webhook'}")
    except requests.exceptions.RequestException as e:
        print(f"Error sending RT Slack alert: {e}")
        raise


def format_rt_alert_message(
    meaningful_name: str,
    event_name: str,
    event_count: int,
    threshold: int,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None
) -> Dict:
    """
    Format RT alert data as Slack message.
    
    Format includes: meaningful name, current count, start/end time windows, event_name, threshold
    
    Args:
        meaningful_name: Human-readable name for the alert
        event_name: Name of the event
        event_count: Current count of events
        threshold: Threshold that was exceeded
        start_time: Start time of the aggregation window (optional)
        end_time: End time of the aggregation window (optional)
    
    Returns:
        Formatted Slack message dict
    """
    # Format start and end times separately
    if start_time:
        start_time_str = start_time.strftime('%Y-%m-%d %H:%M:%S UTC')
    else:
        start_time_str = "N/A"
    
    if end_time:
        end_time_str = end_time.strftime('%Y-%m-%d %H:%M:%S UTC')
    else:
        end_time_str = "N/A"
    
    # Build blocks with required format
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"🚨 Alert: {meaningful_name}"
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Meaningful Name:*\n{meaningful_name}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Current Count:*\n{event_count}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Start Time Window:*\n{start_time_str}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*End Time Window:*\n{end_time_str}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Event Name:*\n`{event_name}`"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Threshold:*\n{threshold}"
                }
            ]
        }
    ]
    
    message = {
        "blocks": blocks
    }
    
    return message


def get_slack_bot_token() -> Optional[str]:
    """
    Get Slack Bot Token from configuration.
    
    Returns:
        Slack Bot Token (OAuth token starting with xoxb-) or None
    """
    config = get_config()
    return config.get("slack_bot_token")


def read_slack_channel_messages(
    channel_name: str,
    start_date: date,
    end_date: date
) -> List[Dict]:
    """
    Read messages from a Slack channel using Slack Web API.
    
    Args:
        channel_name: Name of the channel (with or without #)
        start_date: Start date for filtering messages (inclusive)
        end_date: End date for filtering messages (inclusive)
    
    Returns:
        List of message dictionaries with keys: text, ts, user, reactions, etc.
    """
    try:
        from slack_sdk import WebClient
    except ImportError:
        raise ImportError("slack-sdk is required. Install it with: pip install slack-sdk")
    
    bot_token = get_slack_bot_token()
    if not bot_token:
        raise ValueError("SLACK_BOT_TOKEN or SLACK_BOT_TOKEN_NAME must be configured")
    
    client = WebClient(token=bot_token)
    
    # Clean channel name (remove # if present)
    channel_clean = channel_name.lstrip('#')
    
    # Get channel ID
    try:
        channels_response = client.conversations_list(types="public_channel,private_channel")
        channel_id = None
        for channel in channels_response["channels"]:
            if channel["name"] == channel_clean:
                channel_id = channel["id"]
                break
        
        if not channel_id:
            raise ValueError(f"Channel '{channel_name}' not found")
    except Exception as e:
        raise ValueError(f"Error finding channel '{channel_name}': {e}")
    
    # Convert dates to timestamps
    start_timestamp = datetime.combine(start_date, datetime.min.time()).timestamp()
    end_timestamp = datetime.combine(end_date, datetime.max.time()).timestamp()
    
    all_messages = []
    cursor = None
    
    # Fetch messages with pagination
    while True:
        try:
            params = {
                "channel": channel_id,
                "oldest": str(int(start_timestamp)),
                "latest": str(int(end_timestamp)),
                "limit": 200
            }
            if cursor:
                params["cursor"] = cursor
            
            response = client.conversations_history(**params)
            messages = response.get("messages", [])
            all_messages.extend(messages)
            
            # Check if there are more pages
            response_metadata = response.get("response_metadata", {})
            cursor = response_metadata.get("next_cursor")
            if not cursor:
                break
                
        except Exception as e:
            print(f"Error fetching messages: {e}")
            raise
    
    print(f"Fetched {len(all_messages)} messages from channel {channel_name}")
    return all_messages


def add_reaction_to_message(
    channel_id: str,
    message_timestamp: str,
    emoji: str
) -> bool:
    """
    Add an emoji reaction to a Slack message.
    
    Args:
        channel_id: Slack channel ID
        message_timestamp: Message timestamp (ts field from message)
        emoji: Emoji name (e.g., "computer" or "💻")
    
    Returns:
        True if successful, False otherwise
    """
    try:
        from slack_sdk import WebClient
    except ImportError:
        raise ImportError("slack-sdk is required. Install it with: pip install slack-sdk")
    
    bot_token = get_slack_bot_token()
    if not bot_token:
        raise ValueError("SLACK_BOT_TOKEN or SLACK_BOT_TOKEN_NAME must be configured")
    
    client = WebClient(token=bot_token)
    
    # Remove colons if present (e.g., :computer: -> computer)
    emoji_clean = emoji.strip(':')
    
    try:
        response = client.reactions_add(
            channel=channel_id,
            timestamp=message_timestamp,
            name=emoji_clean
        )
        return response.get("ok", False)
    except Exception as e:
        print(f"Error adding reaction {emoji} to message: {e}")
        return False


def get_channel_id(channel_name: str) -> Optional[str]:
    """
    Get Slack channel ID from channel name.
    
    Args:
        channel_name: Name of the channel (with or without #)
    
    Returns:
        Channel ID or None if not found
    """
    try:
        from slack_sdk import WebClient
    except ImportError:
        raise ImportError("slack-sdk is required. Install it with: pip install slack-sdk")
    
    bot_token = get_slack_bot_token()
    if not bot_token:
        raise ValueError("SLACK_BOT_TOKEN or SLACK_BOT_TOKEN_NAME must be configured")
    
    client = WebClient(token=bot_token)
    
    # Clean channel name (remove # if present)
    channel_clean = channel_name.lstrip('#')
    
    try:
        channels_response = client.conversations_list(types="public_channel,private_channel")
        for channel in channels_response["channels"]:
            if channel["name"] == channel_clean:
                return channel["id"]
        return None
    except Exception as e:
        print(f"Error finding channel '{channel_name}': {e}")
        return None

