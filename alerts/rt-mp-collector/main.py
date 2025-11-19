"""Cloud Function for RT Mixpanel event collection and alerting."""
import os
import json
import requests
import base64
from datetime import datetime, timedelta
from typing import List, Dict
from shared.config import get_config, get_rt_mp_config
from shared.bigquery_client import insert_events_to_rt_table, query_events_by_hour, query_distinct_users_by_hour, query_total_active_users_by_hour
from shared.slack_client import send_rt_alert


# In-memory cache for last alert time per event
# In production, consider using Cloud Firestore or Redis
_last_alert_cache: Dict[str, datetime] = {}


def rt_mp_collector(request):
    """
    Cloud Function entry point for RT Mixpanel collection and alerting.
    
    Collects events from Mixpanel (last 15 minutes), stores them in BigQuery,
    counts events per hour, and sends Slack alerts when thresholds are exceeded.
    """
    try:
        config = get_config()
        rt_config = get_rt_mp_config()
        
        # Validate configuration
        if not config["mixpanel_api_secret"]:
            raise ValueError("MIXPANEL_API_SECRET not configured (set MIXPANEL_API_SECRET or MIXPANEL_API_SECRET_NAME)")
        if not config["mixpanel_project_id"]:
            raise ValueError("MIXPANEL_PROJECT_ID not configured")
        if not config.get("slack_webhook_url"):
            print("Warning: SLACK_WEBHOOK_URL not configured, alerts will be skipped")
        
        # Get enabled events
        events_config = rt_config.get("events", [])
        enabled_events = [e for e in events_config if e.get("enabled", True)]
        
        if not enabled_events:
            print("No enabled events to collect")
            return {"status": "success", "message": "No enabled events"}
        
        collection_frequency = rt_config.get("collection_frequency_minutes", 15)
        
        print(f"Collecting events for {len(enabled_events)} enabled events")
        print(f"Collection window: last {collection_frequency} minutes")
        
        # Step 1: Collect events from Mixpanel (last 15 minutes)
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=collection_frequency)
        
        # Ensure we don't query future dates (Mixpanel doesn't allow this)
        if start_time > end_time:
            start_time = end_time - timedelta(minutes=1)
        
        print(f"Collecting events from {start_time} to {end_time}")
        print(f"Date range: {start_time.strftime('%Y-%m-%d')} to {end_time.strftime('%Y-%m-%d')}")
        
        all_events = []
        
        # Collect events for each configured event
        for event_config in enabled_events:
            event_name = event_config["name"]
            print(f"Collecting events for: {event_name}")
            
            try:
                # Pass the full config to allow fetch_mixpanel_events to choose auth method
                events = fetch_mixpanel_events(
                    event_name=event_name,
                    start_time=start_time,
                    end_time=end_time,
                    api_secret=config.get("mixpanel_api_secret"),  # May be None if using Service Account
                    project_id=config["mixpanel_project_id"]
                )
                
                print(f"Fetched {len(events)} events for {event_name}")
                all_events.extend(events)
                
            except Exception as e:
                print(f"Error collecting events for {event_name}: {e}")
                # Continue with other events
                continue
        
        # Step 2: Store events in BigQuery table rt_mp_events
        if all_events:
            try:
                insert_events_to_rt_table(all_events)
                print(f"Successfully stored {len(all_events)} events in BigQuery")
            except Exception as e:
                print(f"Error storing events in BigQuery: {e}")
                # Continue with alerting even if storage fails
        else:
            print("No events to store")
        
        # Step 3: Check thresholds and send alerts
        alerts_sent = 0
        
        # Track events by name for local testing (when BigQuery is not available)
        events_by_name = {}
        for event in all_events:
            event_name = event.get("event_name")
            if event_name:
                events_by_name[event_name] = events_by_name.get(event_name, 0) + 1
        
        for event_config in enabled_events:
            event_name = event_config["name"]
            threshold_type = event_config.get("threshold_type", "count")  # "count" or "percentage"
            threshold = event_config.get("alert_threshold", 10)
            channel = event_config.get("alert_channel", "#data-alerts-sandbox")
            meaningful_name = event_config.get("meaningful_name", event_name)
            
            print(f"Checking threshold for {event_name} (type: {threshold_type}, threshold: {threshold})")
            
            try:
                # Try to query BigQuery first, fall back to collected events for local testing
                # Use the same time window as collection frequency (15 minutes)
                window_end = datetime.utcnow()
                window_start = window_end - timedelta(minutes=collection_frequency)
                
                should_alert = False
                alert_value = None
                threshold_value = threshold
                total_active_users = None
                error_users = None
                
                try:
                    if threshold_type == "percentage":
                        # Percentage-based: (error users / total active users) > threshold
                        error_users = query_distinct_users_by_hour(
                            event_name=event_name,
                            start_time=window_start,
                            end_time=window_end
                        )
                        total_active_users = query_total_active_users_by_hour(
                            start_time=window_start,
                            end_time=window_end
                        )
                        
                        window_minutes = int((window_end - window_start).total_seconds() / 60)
                        print(f"Error users for {event_name} in last {window_minutes} minutes: {error_users}")
                        print(f"Total active users in last {window_minutes} minutes: {total_active_users}")
                        
                        if total_active_users > 0:
                            percentage = error_users / total_active_users
                            alert_value = percentage
                            print(f"Percentage: {percentage:.6f} ({percentage*100:.4f}%)")
                            should_alert = percentage > threshold
                        else:
                            print(f"⚠️  No active users found, skipping percentage check")
                            should_alert = False
                    else:
                        # Count-based: event_count > threshold
                        event_count = query_events_by_hour(
                            event_name=event_name,
                            start_time=window_start,
                            end_time=window_end
                        )
                        window_minutes = int((window_end - window_start).total_seconds() / 60)
                        print(f"Event count for {event_name} in last {window_minutes} minutes (from BigQuery): {event_count}")
                        alert_value = event_count
                        should_alert = event_count > threshold
                        
                except Exception as bq_error:
                    # BigQuery not available (local testing) - use collected events
                    print(f"⚠️  BigQuery not available, using collected events (local testing only)")
                    
                    if threshold_type == "percentage":
                        # Calculate from collected events
                        error_user_set = set()
                        total_user_set = set()
                        
                        for event in all_events:
                            distinct_id = event.get("distinct_id")
                            if distinct_id:
                                total_user_set.add(distinct_id)
                                if event.get("event_name") == event_name:
                                    error_user_set.add(distinct_id)
                        
                        error_users = len(error_user_set)
                        total_active_users = len(total_user_set)
                        
                        if total_active_users > 0:
                            percentage = error_users / total_active_users
                            alert_value = percentage
                            print(f"Percentage (from collected events): {percentage:.6f} ({percentage*100:.4f}%)")
                            should_alert = percentage > threshold
                        else:
                            should_alert = False
                    else:
                        event_count = events_by_name.get(event_name, 0)
                        alert_value = event_count
                        print(f"Event count (from collected events): {event_count}")
                        should_alert = event_count > threshold
                
                # Check if we've recently alerted for this event (2-hour cooldown)
                cache_key = f"{event_name}_{window_end.strftime('%Y-%m-%d-%H-%M')}"
                last_alert = _last_alert_cache.get(cache_key)
                
                if last_alert:
                    time_since_alert = (datetime.utcnow() - last_alert).total_seconds()
                    if time_since_alert < 7200:  # 2 hours cooldown
                        should_alert = False
                        print(f"Skipping alert for {event_name} (alerted {int(time_since_alert/60)} minutes ago)")
                
                if should_alert:
                    if threshold_type == "percentage":
                        print(f"🚨 Alert triggered for {event_name}: {alert_value*100:.4f}% ({error_users}/{total_active_users} users) exceeds threshold {threshold*100:.4f}%")
                    else:
                        print(f"🚨 Alert triggered for {event_name}: {alert_value} events (threshold: {threshold})")
                    
                    try:
                        send_rt_alert(
                            meaningful_name=meaningful_name,
                            event_name=event_name,
                            event_count=alert_value if threshold_type == "count" else error_users,
                            threshold=threshold,
                            channel=channel,
                            start_time=window_start,
                            end_time=window_end,
                            threshold_type=threshold_type,
                            total_active_users=total_active_users,
                            percentage=alert_value if threshold_type == "percentage" else None
                        )
                        
                        # Update alert cache
                        _last_alert_cache[cache_key] = datetime.utcnow()
                        alerts_sent += 1
                        
                    except Exception as e:
                        print(f"Error sending alert for {event_name}: {e}")
                        # Continue with other events
                        continue
                else:
                    if threshold_type == "percentage":
                        print(f"No alert needed for {event_name} ({alert_value*100:.4f}% <= {threshold*100:.4f}%)")
                    else:
                        print(f"No alert needed for {event_name} ({alert_value} <= {threshold})")
                    
            except Exception as e:
                print(f"Error checking threshold for {event_name}: {e}")
                import traceback
                traceback.print_exc()
                # Continue with other events
                continue
        
        return {
            "status": "success",
            "events_collected": len(all_events),
            "events_by_name": {
                event_config["name"]: len([e for e in all_events if e["event_name"] == event_config["name"]])
                for event_config in enabled_events
            },
            "alerts_sent": alerts_sent,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        print(f"Error in rt_mp_collector: {e}")
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
    # Validate date range
    now = datetime.utcnow()
    if start_time > now:
        raise ValueError(f"Start time {start_time} is in the future")
    if end_time > now:
        print(f"Warning: End time {end_time} is in the future, adjusting to now")
        end_time = now
    if end_time < start_time:
        raise ValueError(f"End time {end_time} is before start time {start_time}")
    
    # Mixpanel Export API endpoint
    # Use data.mixpanel.com (matching working example)
    # For EU: data-eu.mixpanel.com, For India: data-in.mixpanel.com
    base_url = "https://data.mixpanel.com/api/2.0/export"
    
    # Convert to date strings (YYYY-MM-DD format)
    # Mixpanel Export API requires dates, not timestamps
    from_date = start_time.strftime("%Y-%m-%d")
    to_date = end_time.strftime("%Y-%m-%d")
    
    # Ensure we're not querying future dates
    today = now.strftime("%Y-%m-%d")
    if from_date > today:
        from_date = today
    if to_date > today:
        to_date = today
    
    all_events = []
    
    # Mixpanel Export API parameters
    # Optionally filter by event name in query (more efficient)
    params = {
        "from_date": from_date,
        "to_date": to_date,
        "event": json.dumps([event_name])  # Filter by event name in query string
    }
    
    # Mixpanel Export API authentication
    # Based on working example: use base64 encoded Basic auth in header
    if not api_secret or not api_secret.strip():
        raise ValueError("Mixpanel API secret is required. Set MIXPANEL_API_SECRET")
    
    # Base64 encode the API secret for Basic auth (matching working example)
    auth = base64.b64encode(f"{api_secret}:".encode()).decode()
    api_secret_preview = api_secret[:8] + "..." if len(api_secret) > 8 else api_secret
    print(f"Using API Secret authentication: {api_secret_preview} (length: {len(api_secret)})")
    
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # Build full URL for debugging
            full_url = f"{base_url}?from_date={from_date}&to_date={to_date}&event={params['event']}"
            print(f"Fetching from Mixpanel: {from_date} to {to_date}")
            print(f"API endpoint: {base_url}")
            print(f"Event filter: {event_name}")
            
            # Mixpanel Export API uses HTTP Basic Auth in header (matching working example)
            # Use base64 encoded Basic auth in Authorization header
            response = requests.get(
                base_url,
                params=params,
                headers={
                    "Authorization": f"Basic {auth}",
                    "Accept": "text/plain",
                    "User-Agent": "RT-MP-Collector/1.0"
                },
                stream=True,  # Enable streaming for large responses
                timeout=300  # Longer timeout for streaming
            )
            
            if response.status_code == 200:
                # Mixpanel export API returns newline-delimited JSON (streamed)
                # Process line by line for efficiency (matching working example)
                start_timestamp = int(start_time.timestamp())
                end_timestamp = int(end_time.timestamp())
                
                event_count = 0
                for line in response.iter_lines():
                    if not line:
                        continue
                    
                    try:
                        event = json.loads(line)
                        event_count += 1
                        
                        # Filter by event name (though we already filtered in query)
                        if event.get("event") == event_name:
                            # Filter by timestamp within our window
                            event_time = event.get("properties", {}).get("time")
                            if event_time and start_timestamp <= event_time <= end_timestamp:
                                all_events.append(transform_mixpanel_event(event))
                    except (json.JSONDecodeError, KeyError, TypeError) as e:
                        continue
                
                print(f"Processed {event_count} events from Mixpanel, {len(all_events)} matched criteria")
                break
                
            elif response.status_code == 400:
                # Bad Request - log detailed error
                error_msg = f"Mixpanel API returned 400 Bad Request"
                try:
                    error_body = response.text
                    error_msg += f": {error_body}"
                    print(f"❌ {error_msg}")
                    print(f"   URL: {full_url}")
                    print(f"   Request params: {params}")
                    print(f"   Response headers: {dict(response.headers)}")
                except:
                    pass
                
                # Check if it's an authentication error
                if "unauthorized" in response.text.lower() or "authentication" in response.text.lower():
                    raise ValueError(f"Mixpanel API authentication failed. Check your API secret.")
                
                # For 400 errors, don't retry - the request is malformed
                raise requests.exceptions.HTTPError(f"{error_msg}")
                
            elif response.status_code == 401:
                # Unauthorized - authentication issue
                error_detail = "Mixpanel API authentication failed (401)."
                try:
                    error_body = response.text[:200]
                    if "AuthenticationRequired" in error_body or "Authentication required" in error_body:
                        error_detail += "\n   The API secret may be incorrect or invalid."
                        error_detail += "\n   Please verify:"
                        error_detail += "\n   1. You're using the Export API Secret (not Service Account secret)"
                        error_detail += "\n   2. Go to: https://mixpanel.com/project/{}/settings".format(project_id)
                        error_detail += "\n   3. Navigate to 'Project Settings' → 'Service Accounts'"
                        error_detail += "\n   4. Look for 'Export API Secret' (different from Service Account secret)"
                        error_detail += "\n   5. Ensure the secret has 'Export API' permissions enabled"
                        error_detail += f"\n   6. Your project ID is: {project_id}"
                        error_detail += "\n   7. Note: Service Account secrets use different authentication"
                        error_detail += "\n   8. The Export API requires a specific Export API Secret"
                except:
                    pass
                raise ValueError(error_detail)
                
            elif response.status_code == 403:
                # Forbidden - permission issue
                raise ValueError("Mixpanel API access forbidden (403). Check your API secret and project permissions.")
                
            elif response.status_code == 429:
                # Rate limited, wait and retry
                import time
                wait_time = (retry_count + 1) * 5
                print(f"Rate limited, waiting {wait_time} seconds...")
                time.sleep(wait_time)
                retry_count += 1
                continue
            else:
                # Other errors - log and raise
                error_msg = f"Mixpanel API returned {response.status_code}"
                try:
                    error_body = response.text[:500]  # First 500 chars
                    error_msg += f": {error_body}"
                except:
                    pass
                print(f"❌ {error_msg}")
                response.raise_for_status()
                
        except requests.exceptions.HTTPError as e:
            # Don't retry HTTP errors (4xx, 5xx) except 429
            raise
        except requests.exceptions.RequestException as e:
            retry_count += 1
            if retry_count >= max_retries:
                print(f"❌ Failed after {max_retries} retries: {e}")
                raise
            import time
            print(f"⚠️  Request failed, retrying ({retry_count}/{max_retries})...")
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

