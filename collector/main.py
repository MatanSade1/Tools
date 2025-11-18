"""Cloud Function to collect events from Mixpanel and store in BigQuery."""
import os
import json
import requests
from datetime import datetime, timedelta
from typing import List, Dict
from shared.config import get_config, get_enabled_events
from shared.bigquery_client import insert_events


def collect_mixpanel_events(request):
    """
    Cloud Function entry point for collecting Mixpanel events.
    
    Collects events from the last 15 minutes for all enabled events
    and stores them in BigQuery.
    """
    try:
        config = get_config()
        
        # Validate configuration
        if not config["mixpanel_api_secret"]:
            raise ValueError("MIXPANEL_API_SECRET not configured")
        if not config["mixpanel_project_id"]:
            raise ValueError("MIXPANEL_PROJECT_ID not configured")
        
        # Get enabled events
        events_config = get_enabled_events()
        if not events_config:
            print("No enabled events to collect")
            return {"status": "success", "message": "No enabled events"}
        
        # Calculate time range (last 15 minutes)
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=15)
        
        print(f"Collecting events from {start_time} to {end_time}")
        
        all_events = []
        
        # Collect events for each configured event
        for event_config in events_config:
            event_name = event_config["name"]
            print(f"Collecting events for: {event_name}")
            
            try:
                events = fetch_mixpanel_events(
                    event_name=event_name,
                    start_time=start_time,
                    end_time=end_time,
                    api_secret=config["mixpanel_api_secret"],
                    project_id=config["mixpanel_project_id"]
                )
                
                print(f"Fetched {len(events)} events for {event_name}")
                all_events.extend(events)
                
            except Exception as e:
                print(f"Error collecting events for {event_name}: {e}")
                # Continue with other events
                continue
        
        # Insert all events into BigQuery
        if all_events:
            insert_events(all_events)
            print(f"Successfully stored {len(all_events)} events in BigQuery")
        else:
            print("No events to store")
        
        return {
            "status": "success",
            "events_collected": len(all_events),
            "events_by_name": {
                event_config["name"]: len([e for e in all_events if e["event_name"] == event_config["name"]])
                for event_config in events_config
            }
        }
        
    except Exception as e:
        print(f"Error in collect_mixpanel_events: {e}")
        raise


def fetch_mixpanel_events(
    event_name: str,
    start_time: datetime,
    end_time: datetime,
    api_secret: str,
    project_id: str
) -> List[Dict]:
    """
    Fetch events from Mixpanel Export API.
    
    Args:
        event_name: Name of the event to fetch
        start_time: Start of time range
        end_time: End of time range
        api_secret: Mixpanel API secret
        project_id: Mixpanel project ID
    
    Returns:
        List of event dictionaries
    """
    # Mixpanel Export API endpoint
    base_url = "https://mixpanel.com/api/2.0/export"
    
    # Convert to date strings (YYYY-MM-DD format)
    from_date = start_time.strftime("%Y-%m-%d")
    to_date = end_time.strftime("%Y-%m-%d")
    
    all_events = []
    
    # Mixpanel Export API returns all events for the date range
    # We need to filter by event name and timestamp after fetching
    params = {
        "from_date": from_date,
        "to_date": to_date,
        "format": "json"
    }
    
    # Mixpanel uses basic auth with API secret
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            response = requests.get(
                base_url,
                params=params,
                auth=(api_secret, ""),
                timeout=60
            )
            
            if response.status_code == 200:
                # Mixpanel export API returns newline-delimited JSON
                lines = response.text.strip().split("\n")
                if not lines or lines == [""]:
                    break
                
                # Filter events by name and timestamp
                start_timestamp = int(start_time.timestamp())
                end_timestamp = int(end_time.timestamp())
                
                for line in lines:
                    if line.strip():
                        try:
                            event = json.loads(line)
                            # Filter by event name
                            if event.get("event") == event_name:
                                # Filter by timestamp within our window
                                event_time = event.get("properties", {}).get("time")
                                if event_time and start_timestamp <= event_time <= end_timestamp:
                                    all_events.append(transform_mixpanel_event(event))
                        except (json.JSONDecodeError, KeyError, TypeError):
                            continue
                
                break
                
            elif response.status_code == 429:
                # Rate limited, wait and retry
                import time
                wait_time = (retry_count + 1) * 5
                print(f"Rate limited, waiting {wait_time} seconds...")
                time.sleep(wait_time)
                retry_count += 1
                continue
            else:
                response.raise_for_status()
                
        except requests.exceptions.RequestException as e:
            retry_count += 1
            if retry_count >= max_retries:
                raise
            import time
            time.sleep(5)
    
    return all_events


def transform_mixpanel_event(mixpanel_event: Dict) -> Dict:
    """
    Transform Mixpanel event format to our BigQuery schema.
    
    Args:
        mixpanel_event: Raw event from Mixpanel API
    
    Returns:
        Transformed event dict
    """
    # Mixpanel event structure:
    # {
    #   "event": "event_name",
    #   "properties": {
    #     "time": 1234567890,
    #     "distinct_id": "user123",
    #     ...
    #   }
    # }
    
    properties = mixpanel_event.get("properties", {})
    event_timestamp = properties.get("time")
    
    # Convert Unix timestamp to ISO format
    if event_timestamp:
        dt = datetime.fromtimestamp(event_timestamp)
        event_timestamp_iso = dt.isoformat()
    else:
        event_timestamp_iso = datetime.utcnow().isoformat()
    
    return {
        "event_timestamp": event_timestamp_iso,
        "event_name": mixpanel_event.get("event"),
        "properties": properties,
        "distinct_id": properties.get("distinct_id"),
        "event_id": properties.get("$insert_id") or f"{properties.get('distinct_id', 'unknown')}_{event_timestamp}_{mixpanel_event.get('event')}"
    }

