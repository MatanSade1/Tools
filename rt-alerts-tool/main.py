"""Cloud Function for near real-time Mixpanel event alerting."""
import os
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from shared.config import get_config, load_events_config
from shared.slack_client import send_slack_alert


# In-memory cache for last alert time per event
# In production, consider using Cloud Firestore or Redis
_last_alert_cache: Dict[str, datetime] = {}


def rt_alerts_tool(request):
    """
    Cloud Function entry point for near real-time Mixpanel alerting.
    
    Monitors events from the last 1-2 minutes using Mixpanel Query API
    and sends immediate alerts when thresholds are exceeded.
    """
    try:
        config = get_config()
        
        # Validate configuration
        if not config["mixpanel_api_secret"]:
            raise ValueError("MIXPANEL_API_SECRET not configured (set MIXPANEL_API_SECRET or MIXPANEL_API_SECRET_NAME)")
        if not config["mixpanel_project_id"]:
            raise ValueError("MIXPANEL_PROJECT_ID not configured")
        if not config.get("slack_webhook_url"):
            print("Warning: SLACK_WEBHOOK_URL not configured, alerts will be skipped")
        
        # Get events configuration
        events_config = load_events_config()
        enabled_events = [e for e in events_config if e.get("enabled", True)]
        
        if not enabled_events:
            print("No enabled events to monitor")
            return {"status": "success", "message": "No enabled events"}
        
        print(f"Monitoring {len(enabled_events)} events in near real-time")
        
        alerts_sent = 0
        
        # Check each event
        for event_config in enabled_events:
            event_name = event_config["name"]
            threshold = event_config.get("alert_threshold", 5)
            time_window = event_config.get("time_window_minutes", 1)
            channel = event_config.get("alert_channel")
            
            print(f"Checking {event_name} (threshold: {threshold}, window: {time_window} min)")
            
            try:
                # Query recent events using Mixpanel Query API
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(minutes=time_window + 1)  # Add 1 minute buffer
                
                event_count = query_mixpanel_recent_events(
                    event_name=event_name,
                    start_time=start_time,
                    end_time=end_time,
                    api_secret=config["mixpanel_api_secret"],
                    project_id=config["mixpanel_project_id"]
                )
                
                print(f"Found {event_count} events for {event_name} in the last {time_window} minutes")
                
                # Check if threshold is exceeded
                if event_count > threshold:
                    # Check if we've recently alerted for this event
                    cache_key = f"{event_name}_{end_time.strftime('%Y-%m-%d-%H-%M')}"
                    last_alert = _last_alert_cache.get(cache_key)
                    
                    # Only alert if we haven't alerted in the last 2 minutes
                    should_alert = True
                    if last_alert:
                        time_since_alert = (datetime.utcnow() - last_alert).total_seconds()
                        if time_since_alert < 120:  # 2 minutes cooldown
                            should_alert = False
                            print(f"Skipping alert for {event_name} (alerted {int(time_since_alert)}s ago)")
                    
                    if should_alert:
                        print(f"🚨 Alert triggered for {event_name}: {event_count} events (threshold: {threshold})")
                        
                        # Get sample events for the alert
                        sample_events = get_sample_events(
                            event_name=event_name,
                            start_time=start_time,
                            end_time=end_time,
                            api_secret=config["mixpanel_api_secret"],
                            project_id=config["mixpanel_project_id"],
                            limit=3
                        )
                        
                        # Format alert data
                        alert_data = [{
                            "minute_timestamp": end_time.replace(second=0, microsecond=0),
                            "event_count": event_count,
                            "sample_events": sample_events
                        }]
                        
                        # Send Slack alert
                        try:
                            send_slack_alert(
                                event_name=event_name,
                                alert_data=alert_data,
                                channel=channel,
                                webhook_url=config.get("slack_webhook_url")
                            )
                            
                            # Update alert cache
                            _last_alert_cache[cache_key] = datetime.utcnow()
                            alerts_sent += 1
                            
                        except Exception as e:
                            print(f"Error sending alert for {event_name}: {e}")
                            # Continue with other events
                            continue
                else:
                    print(f"No alert needed for {event_name} ({event_count} <= {threshold})")
                    
            except Exception as e:
                print(f"Error checking {event_name}: {e}")
                # Continue with other events
                continue
        
        return {
            "status": "success",
            "events_checked": len(enabled_events),
            "alerts_sent": alerts_sent,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        print(f"Error in rt_alerts_tool: {e}")
        raise


def query_mixpanel_recent_events(
    event_name: str,
    start_time: datetime,
    end_time: datetime,
    api_secret: str,
    project_id: str
) -> int:
    """
    Query Mixpanel for recent event count using Export API.
    
    For near real-time monitoring, queries the Export API for events
    within the specified time window. The Export API is more reliable
    than JQL for recent events.
    
    Args:
        event_name: Name of the event to query
        start_time: Start of time window
        end_time: End of time window
        api_secret: Mixpanel API secret
        project_id: Mixpanel project ID
    
    Returns:
        Count of events in the time window
    """
    return query_mixpanel_export_count(
        event_name, start_time, end_time, api_secret, project_id
    )


def query_mixpanel_export_count(
    event_name: str,
    start_time: datetime,
    end_time: datetime,
    api_secret: str,
    project_id: str
) -> int:
    """
    Query Mixpanel Export API to count events in the specified time window.
    
    This method queries the Export API and filters events by name and timestamp
    to get accurate counts for near real-time monitoring.
    
    Args:
        event_name: Name of the event to query
        start_time: Start of time window
        end_time: End of time window
        api_secret: Mixpanel API secret
        project_id: Mixpanel project ID
    
    Returns:
        Count of events matching the criteria
    """
    base_url = "https://mixpanel.com/api/2.0/export"
    
    from_date = start_time.strftime("%Y-%m-%d")
    to_date = end_time.strftime("%Y-%m-%d")
    
    params = {
        "from_date": from_date,
        "to_date": to_date,
        "format": "json"
    }
    
    start_timestamp = int(start_time.timestamp())
    end_timestamp = int(end_time.timestamp())
    
    count = 0
    
    try:
        response = requests.get(
            base_url,
            params=params,
            auth=(api_secret, ""),
            timeout=30
        )
        
        if response.status_code == 200:
            lines = response.text.strip().split("\n")
            for line in lines:
                if line.strip():
                    try:
                        event = json.loads(line)
                        if event.get("event") == event_name:
                            event_time = event.get("properties", {}).get("time")
                            if event_time and start_timestamp <= event_time <= end_timestamp:
                                count += 1
                    except (json.JSONDecodeError, KeyError, TypeError):
                        continue
    except Exception as e:
        print(f"Error in export API fallback: {e}")
    
    return count


def get_sample_events(
    event_name: str,
    start_time: datetime,
    end_time: datetime,
    api_secret: str,
    project_id: str,
    limit: int = 3
) -> List[Dict]:
    """
    Get sample events for alert details.
    
    Args:
        event_name: Name of the event
        start_time: Start of time window
        end_time: End of time window
        api_secret: Mixpanel API secret
        project_id: Mixpanel project ID
        limit: Maximum number of sample events to return
    
    Returns:
        List of sample event dictionaries
    """
    base_url = "https://mixpanel.com/api/2.0/export"
    
    from_date = start_time.strftime("%Y-%m-%d")
    to_date = end_time.strftime("%Y-%m-%d")
    
    params = {
        "from_date": from_date,
        "to_date": to_date,
        "format": "json"
    }
    
    start_timestamp = int(start_time.timestamp())
    end_timestamp = int(end_time.timestamp())
    
    sample_events = []
    
    try:
        response = requests.get(
            base_url,
            params=params,
            auth=(api_secret, ""),
            timeout=30
        )
        
        if response.status_code == 200:
            lines = response.text.strip().split("\n")
            for line in lines:
                if len(sample_events) >= limit:
                    break
                    
                if line.strip():
                    try:
                        event = json.loads(line)
                        if event.get("event") == event_name:
                            event_time = event.get("properties", {}).get("time")
                            if event_time and start_timestamp <= event_time <= end_timestamp:
                                sample_events.append({
                                    "event": event.get("event"),
                                    "properties": event.get("properties", {})
                                })
                    except (json.JSONDecodeError, KeyError, TypeError):
                        continue
    except Exception as e:
        print(f"Error getting sample events: {e}")
    
    return sample_events

