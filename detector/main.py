"""Cloud Function to detect anomalies and send Slack alerts."""
import os
from datetime import datetime, timedelta
from typing import Dict, List
from shared.config import get_config, load_events_config
from shared.bigquery_client import query_events_by_minute
from shared.slack_client import send_slack_alert


# In-memory cache for last alert time per event per minute
# In production, consider using Cloud Firestore or Redis
_last_alert_cache: Dict[str, datetime] = {}


def detect_anomalies(request):
    """
    Cloud Function entry point for anomaly detection.
    
    Checks all configured events for abnormal behavior and sends
    Slack alerts when thresholds are exceeded.
    """
    try:
        config = get_config()
        
        # Validate configuration
        if not config["slack_webhook_url"]:
            print("Warning: SLACK_WEBHOOK_URL not configured, alerts will be skipped")
        
        # Get events configuration
        events_config = load_events_config()
        enabled_events = [e for e in events_config if e.get("enabled", True)]
        
        if not enabled_events:
            print("No enabled events to monitor")
            return {"status": "success", "message": "No enabled events"}
        
        print(f"Monitoring {len(enabled_events)} events")
        
        alerts_sent = 0
        
        # Check each event
        for event_config in enabled_events:
            event_name = event_config["name"]
            threshold = event_config.get("alert_threshold", 5)
            time_window = event_config.get("time_window_minutes", 1)
            channel = event_config.get("alert_channel")
            
            print(f"Checking {event_name} (threshold: {threshold}, window: {time_window} min)")
            
            try:
                # Query recent events
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(minutes=time_window + 5)  # Add buffer
                
                minute_data = query_events_by_minute(
                    event_name=event_name,
                    start_time=start_time,
                    end_time=end_time
                )
                
                # Find minutes exceeding threshold
                abnormal_minutes = [
                    m for m in minute_data
                    if m["event_count"] > threshold
                ]
                
                if abnormal_minutes:
                    # Filter out recently alerted minutes
                    new_alerts = filter_recent_alerts(event_name, abnormal_minutes)
                    
                    if new_alerts:
                        print(f"Alert triggered for {event_name}: {len(new_alerts)} abnormal minutes")
                        
                        # Send Slack alert
                        try:
                            send_slack_alert(
                                event_name=event_name,
                                alert_data=new_alerts,
                                channel=channel,
                                webhook_url=config.get("slack_webhook_url")
                            )
                            
                            # Update alert cache
                            for alert in new_alerts:
                                cache_key = f"{event_name}_{alert['minute_timestamp'].isoformat()}"
                                _last_alert_cache[cache_key] = datetime.utcnow()
                            
                            alerts_sent += 1
                            
                        except Exception as e:
                            print(f"Error sending alert for {event_name}: {e}")
                            # Continue with other events
                            continue
                    else:
                        print(f"No new alerts for {event_name} (recently alerted)")
                else:
                    print(f"No anomalies detected for {event_name}")
                    
            except Exception as e:
                print(f"Error checking {event_name}: {e}")
                # Continue with other events
                continue
        
        return {
            "status": "success",
            "events_checked": len(enabled_events),
            "alerts_sent": alerts_sent
        }
        
    except Exception as e:
        print(f"Error in detect_anomalies: {e}")
        raise


def filter_recent_alerts(event_name: str, abnormal_minutes: List[Dict]) -> List[Dict]:
    """
    Filter out minutes that were recently alerted (within last 5 minutes).
    
    Args:
        event_name: Name of the event
        abnormal_minutes: List of abnormal minute data
    
    Returns:
        Filtered list of new alerts
    """
    new_alerts = []
    now = datetime.utcnow()
    
    for minute_data in abnormal_minutes:
        minute_ts = minute_data["minute_timestamp"]
        cache_key = f"{event_name}_{minute_ts.isoformat()}"
        
        # Check if we've alerted for this minute recently
        last_alert = _last_alert_cache.get(cache_key)
        if last_alert:
            # If we alerted within last 5 minutes, skip
            if (now - last_alert).total_seconds() < 300:
                continue
        
        new_alerts.append(minute_data)
    
    return new_alerts

