"""Cloud Function for RT Mixpanel event collection and alerting."""
import os
import json
import requests
import base64
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from shared.config import get_config, get_rt_mp_config
from shared.bigquery_client import insert_events_to_rt_table, query_events_by_hour, query_distinct_users_by_hour, query_total_active_users_by_hour
from shared.slack_client import send_rt_alert
from shared.sheets_client import get_config_from_sheets


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
        
        # Step 0: Read config from Google Sheets if configured
        sheets_spreadsheet_id = os.getenv("RT_MP_CONFIG_SHEETS_ID")
        if sheets_spreadsheet_id:
            try:
                sheets_range = os.getenv("RT_MP_CONFIG_SHEETS_RANGE", "Sheet1!A:Z")
                rt_config = get_config_from_sheets(
                    spreadsheet_id=sheets_spreadsheet_id,
                    range_name=sheets_range
                )
                print(f"Configuration loaded from Google Sheets: {len(rt_config.get('events', []))} events configured")
            except Exception as e:
                print(f"Warning: Failed to read config from Google Sheets: {e}")
                print("Falling back to existing config file")
                rt_config = get_rt_mp_config()
        else:
            # Use existing config file
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
        print(f"Collection and threshold check window: last {collection_frequency} minutes")
        
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
            match_type = event_config.get("match_type", "exact")
            print(f"Collecting events for: {event_name} (match_type: {match_type})")
            
            try:
                # Pass the full config to allow fetch_mixpanel_events to choose auth method
                events = fetch_mixpanel_events(
                    event_name=event_name,
                    start_time=start_time,
                    end_time=end_time,
                    api_secret=config.get("mixpanel_api_secret"),  # May be None if using Service Account
                    project_id=config["mixpanel_project_id"],
                    match_type=match_type
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
            aggregation_type = event_config.get("aggregation_type", "count distinct users")  # "count distinct users" or "percentage"
            threshold = event_config.get("alert_threshold", 10)
            channel = event_config.get("alert_channel", "#data-alerts-sandbox")
            meaningful_name = event_config.get("meaningful_name", event_name)
            match_type = event_config.get("match_type", "exact")
            
            print(f"Checking threshold for {event_name} (aggregation: {aggregation_type}, threshold: {threshold}, match_type: {match_type})")
            
            try:
                # Use Export API to count events in the last 15 minutes
                window_end = datetime.utcnow()
                window_start = window_end - timedelta(minutes=collection_frequency)
                
                should_alert = False
                alert_value = None
                
                try:
                    # Count-based: use Export API to count distinct users in the last 15 minutes
                    distinct_user_count = count_distinct_users_export_api(
                    event_name=event_name,
                        start_time=window_start,
                        end_time=window_end,
                        api_secret=config.get("mixpanel_api_secret"),
                        project_id=config["mixpanel_project_id"],
                        match_type=match_type
                    )
                    
                    window_minutes = int((window_end - window_start).total_seconds() / 60)
                    print(f"Distinct users for {event_name} in last {window_minutes} minutes (from Mixpanel Export API): {distinct_user_count}")
                    alert_value = distinct_user_count
                    should_alert = distinct_user_count > threshold
                        
                except Exception as bq_error:
                    # BigQuery not available (local testing) - use collected events
                    print(f"⚠️  BigQuery not available, using collected events (local testing only)")
                    
                    if aggregation_type == "percentage":
                        # Calculate from collected events
                        error_user_set = set()
                        total_user_set = set()
                        
                        for event in all_events:
                            distinct_id = event.get("distinct_id")
                            if distinct_id:
                                total_user_set.add(distinct_id)
                                event_name_from_event = event.get("event_name", "")
                                # Check if event matches (exact or prefix)
                                if match_type == "prefix":
                                    if event_name_from_event.startswith(event_name):
                                        error_user_set.add(distinct_id)
                                else:
                                    if event_name_from_event == event_name:
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
                        print(f"🚨 Alert triggered for {event_name}: {alert_value} distinct users (threshold: {threshold})")
                        
                        try:
                            send_rt_alert(
                                meaningful_name=meaningful_name,
                                event_name=event_name,
                            event_count=alert_value,
                                threshold=threshold,
                                channel=channel,
                            start_time=window_start,
                            end_time=window_end,
                            aggregation_type=aggregation_type,
                            total_active_users=None,
                            percentage=None
                            )
                            
                            # Update alert cache
                            _last_alert_cache[cache_key] = datetime.utcnow()
                            alerts_sent += 1
                            
                        except Exception as e:
                            print(f"Error sending alert for {event_name}: {e}")
                            # Continue with other events
                            continue
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


# Cloud Run Flask app wrapper
try:
    from flask import Flask, request as flask_request, jsonify
    
    app = Flask(__name__)
    
    @app.route('/', methods=['GET', 'POST'])
    def handle_request():
        """Cloud Run entry point that wraps the Cloud Function handler."""
        try:
            # Create a request-like object for compatibility with Cloud Functions format
            class CloudRunRequest:
                def __init__(self, flask_req):
                    self.method = flask_req.method
                    self.path = flask_req.path
                    self.args = flask_req.args
                    self.json = flask_req.get_json(silent=True)
                    self.headers = flask_req.headers
                    self.data = flask_req.get_data()
            
            # Call the original function
            result = rt_mp_collector(CloudRunRequest(flask_request))
            
            # Return JSON response
            if isinstance(result, dict):
                return jsonify(result), 200
            else:
                return jsonify({"status": "success", "result": str(result)}), 200
                
        except Exception as e:
            print(f"Error handling request: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({"status": "error", "message": str(e)}), 500
    
    if __name__ == '__main__':
        app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
        
except ImportError:
    # Flask not available, running as Cloud Function
    pass


def count_distinct_users_export_api(
    event_name: str,
    start_time: datetime,
    end_time: datetime,
    api_secret: str,
    project_id: str,
    match_type: str = "exact"
) -> int:
    """
    Count distinct users from Mixpanel Export API for a specific event in the time window.
    
    Uses Mixpanel Export API to count distinct users who had the event.
    
    Args:
        event_name: Name of the event to count (or prefix if match_type is "prefix")
        start_time: Start of time range
        end_time: End of time range
        api_secret: Mixpanel API secret
        project_id: Mixpanel project ID
        match_type: "exact" for exact match, "prefix" for prefix matching
    
    Returns:
        Count of distinct users who had the event in the time window
    """
    now = datetime.utcnow()
    if start_time > now:
        raise ValueError(f"Start time {start_time} is in the future")
    if end_time > now:
        print(f"Warning: End time {end_time} is in the future, adjusting to now")
        end_time = now
    if end_time < start_time:
        raise ValueError(f"End time {end_time} is before start time {start_time}")
    
    base_url = "https://data.mixpanel.com/api/2.0/export"
    
    from_date = start_time.strftime("%Y-%m-%d")
    to_date = end_time.strftime("%Y-%m-%d")
    
    today = now.strftime("%Y-%m-%d")
    if from_date > today:
        from_date = today
    if to_date > today:
        to_date = today
    
    # For prefix matching, we can't filter by event in the API query
    # We'll query all events and filter by prefix in code
    if match_type == "prefix":
        params = {
            "from_date": from_date,
            "to_date": to_date
        }
        print(f"Using prefix matching for events starting with: {event_name}")
    else:
        params = {
            "from_date": from_date,
            "to_date": to_date,
            "event": json.dumps([event_name])
        }
    
    if not api_secret or not api_secret.strip():
        raise ValueError("Mixpanel API secret is required. Set MIXPANEL_API_SECRET")
    
    auth = base64.b64encode(f"{api_secret}:".encode()).decode()
    
    start_timestamp = int(start_time.timestamp())
    end_timestamp = int(end_time.timestamp())
    
    max_retries = 2
    retry_count = 0
    
    while retry_count <= max_retries:
        try:
            response = requests.get(
                base_url,
                params=params,
                headers={
                    "Authorization": f"Basic {auth}",
                    "Accept": "text/plain",
                    "User-Agent": "RT-MP-Collector/1.0"
                },
                stream=True,
                timeout=300
            )
            
            if response.status_code == 200:
                distinct_users = set()
                lines_processed = 0
                
                try:
                    # Wrap iter_lines in try-except to catch connection errors during streaming
                    for line in response.iter_lines(decode_unicode=True):
                        if not line:
                            continue
                        
                        lines_processed += 1
                        
                        try:
                            event = json.loads(line)
                            event_name_from_api = event.get("event", "")
                            
                            # Check if event matches (exact or prefix)
                            matches = False
                            if match_type == "prefix":
                                matches = event_name_from_api.startswith(event_name)
                            else:
                                matches = event_name_from_api == event_name
                            
                            if matches:
                                event_time = event.get("properties", {}).get("time")
                                if event_time and start_timestamp <= event_time <= end_timestamp:
                                    distinct_id = event.get("properties", {}).get("distinct_id")
                                    if distinct_id:
                                        distinct_users.add(distinct_id)
                        except (json.JSONDecodeError, KeyError, TypeError):
                            continue
                    
                    print(f"Successfully processed {lines_processed} lines from Mixpanel Export API")
                    return len(distinct_users)
                    
                except (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError, 
                        requests.exceptions.Timeout, OSError) as stream_error:
                    # Connection error during streaming - retry if we haven't exceeded max retries
                    print(f"⚠️  Connection error during streaming (processed {lines_processed} lines): {stream_error}")
                    if retry_count < max_retries:
                        retry_count += 1
                        import time
                        wait_time = retry_count * 2
                        print(f"Retrying in {wait_time} seconds... (attempt {retry_count}/{max_retries})")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"⚠️  Max retries exceeded. Returning 0 distinct users.")
                        return 0
                        
            elif response.status_code == 429:
                # Rate limited, wait and retry
                if retry_count < max_retries:
                    import time
                    wait_time = (retry_count + 1) * 5
                    print(f"Rate limited, waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                    retry_count += 1
                    continue
                else:
                    print(f"⚠️  Mixpanel Export API rate limited after {max_retries} retries")
                    return 0
            else:
                print(f"⚠️  Mixpanel Export API returned {response.status_code}: {response.text[:200]}")
                return 0
                
        except (requests.exceptions.RequestException, OSError) as e:
            # Network or connection error - retry if we haven't exceeded max retries
            print(f"⚠️  Error connecting to Mixpanel Export API: {e}")
            if retry_count < max_retries:
                retry_count += 1
                import time
                wait_time = retry_count * 2
                print(f"Retrying in {wait_time} seconds... (attempt {retry_count}/{max_retries})")
                time.sleep(wait_time)
                continue
            else:
                print(f"⚠️  Max retries exceeded. Error: {e}")
                import traceback
                traceback.print_exc()
                return 0
        except Exception as e:
            # Other unexpected errors - don't retry
            print(f"⚠️  Unexpected error counting events from Mixpanel Export API: {e}")
            import traceback
            traceback.print_exc()
            return 0
    
    # Should not reach here, but return 0 as fallback
    return 0


def fetch_mixpanel_events(
    event_name: str,
    start_time: datetime,
    end_time: datetime,
    api_secret: str,
    project_id: str,
    match_type: str = "exact"
) -> List[Dict]:
    """
    Fetch events from Mixpanel Export API.
    
    Args:
        event_name: Name of the event to fetch (or prefix if match_type is "prefix")
        start_time: Start of time range
        end_time: End of time range
        api_secret: Mixpanel API secret
        project_id: Mixpanel project ID
        match_type: "exact" for exact match, "prefix" for prefix matching
    
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
    # For prefix matching, we can't filter by event in the API query
    # We'll query all events and filter by prefix in code
    if match_type == "prefix":
        params = {
            "from_date": from_date,
            "to_date": to_date
        }
        print(f"Using prefix matching for events starting with: {event_name}")
    else:
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
                try:
                    # Wrap iter_lines in try-except to catch connection errors during streaming
                    for line in response.iter_lines(decode_unicode=True):
                        if not line:
                            continue
                        
                        try:
                            event = json.loads(line)
                            event_count += 1
                            event_name_from_api = event.get("event", "")
                            
                            # Check if event matches (exact or prefix)
                            matches = False
                            if match_type == "prefix":
                                matches = event_name_from_api.startswith(event_name)
                            else:
                                matches = event_name_from_api == event_name
                            
                            if matches:
                                # Filter by timestamp within our window
                                event_time = event.get("properties", {}).get("time")
                                if event_time and start_timestamp <= event_time <= end_timestamp:
                                    all_events.append(transform_mixpanel_event(event))
                        except (json.JSONDecodeError, KeyError, TypeError) as e:
                            continue
                    
                    print(f"Processed {event_count} events from Mixpanel, {len(all_events)} matched criteria")
                    break
                    
                except (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError, 
                        requests.exceptions.Timeout, OSError) as stream_error:
                    # Connection error during streaming - retry
                    print(f"⚠️  Connection error during streaming (processed {event_count} events): {stream_error}")
                    retry_count += 1
                    if retry_count >= max_retries:
                        print(f"⚠️  Max retries exceeded. Returning {len(all_events)} events collected so far.")
                        break
                    import time
                    wait_time = retry_count * 2
                    print(f"Retrying in {wait_time} seconds... (attempt {retry_count + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                
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


def query_mixpanel_distinct_users(
    event_name: Optional[str],
    start_time: datetime,
    end_time: datetime,
    api_secret: str,
    project_id: str
) -> int:
    """
    Query Mixpanel Query API to get distinct user count for a specific event or all events.
    
    Uses Mixpanel Query API /events endpoint which is more efficient than Export API.
    
    Args:
        event_name: Name of the event (None for all events = total active users)
        start_time: Start of time range
        end_time: End of time range
        api_secret: Mixpanel API secret
        project_id: Mixpanel project ID
    
    Returns:
        Count of distinct users
    """
    now = datetime.utcnow()
    if start_time > now:
        raise ValueError(f"Start time {start_time} is in the future")
    if end_time > now:
        print(f"Warning: End time {end_time} is in the future, adjusting to now")
        end_time = now
    if end_time < start_time:
        raise ValueError(f"End time {end_time} is before start time {start_time}")
    
    # Mixpanel Query API endpoint
    base_url = "https://mixpanel.com/api/2.0/events"
    
    from_date = start_time.strftime("%Y-%m-%d")
    to_date = end_time.strftime("%Y-%m-%d")
    
    today = now.strftime("%Y-%m-%d")
    if from_date > today:
        from_date = today
    if to_date > today:
        to_date = today
    
    # For hourly aggregation, use unit='hour' and interval=1
    # This gives us distinct users per hour, which is more accurate than minute-by-minute
    window_hours = (end_time - start_time).total_seconds() / 3600
    if window_hours >= 1:
        # Use hourly aggregation
        params = {
            'type': 'unique',  # Get distinct user counts
            'unit': 'hour',
            'interval': 1,  # 1 hour intervals
            'from_date': from_date,
            'to_date': to_date
        }
        interval_type = "hourly"
    else:
        # For windows less than 1 hour, use minute aggregation
        interval_minutes = int((end_time - start_time).total_seconds() / 60)
        if interval_minutes < 1:
            interval_minutes = 1
        params = {
            'type': 'unique',
            'unit': 'minute',
            'interval': interval_minutes,
            'from_date': from_date,
            'to_date': to_date
        }
        interval_type = f"{interval_minutes}-minute"
    
    # Query API requires event parameter - try without it first for "all events"
    if event_name:
        params['event'] = json.dumps([event_name])
        query_type = f"event '{event_name}'"
    else:
        # Try to query without event parameter for "all events"
        # Some Query API endpoints might support this
        query_type = "all events (total active users)"
        # If this doesn't work, we'll get an error and fall back
    
    if not api_secret or not api_secret.strip():
        raise ValueError("Mixpanel API secret is required. Set MIXPANEL_API_SECRET")
    
    # Query API uses API secret as username, empty password
    auth = base64.b64encode(f"{api_secret}:".encode()).decode()
    
    print(f"Querying Mixpanel Query API for distinct users ({query_type}): {from_date} to {to_date}, {interval_type} intervals")
    
    try:
        response = requests.get(
            base_url,
            params=params,
            headers={
                "Authorization": f"Basic {auth}",
                "Accept": "application/json",
                "User-Agent": "RT-MP-Collector/1.0"
            },
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Query API with type='unique' returns distinct user counts
            # Response format:
            # {
            #   "data": {
            #     "values": {
            #       "purchase_successful": {
            #         "2025-11-19 21:15": 1234,  # Number of distinct users
            #         "2025-11-19 21:30": 5678
            #       }
            #     }
            #   }
            # }
            
            total_uniques = 0
            
            print(f"Query API response structure: {list(data.keys())}")
            # Log full response for debugging (first 2000 chars to see the actual format)
            response_str = json.dumps(data, indent=2)
            print(f"Query API full response: {response_str[:2000]}")
            
            if 'data' in data:
                data_obj = data['data']
                
                # Check if 'values' exists
                if 'values' in data_obj:
                    values = data_obj['values']
                    print(f"Found {len(values)} event(s) in response")
                    
                    # Find the event key
                    event_key = None
                    if event_name and event_name in values:
                        event_key = event_name
                    elif len(values) > 0:
                        # Use first key if available
                        event_key = list(values.keys())[0]
                        print(f"Using event key: {event_key}")
                    
                    if event_key:
                        time_series = values[event_key]
                        print(f"Time series data type: {type(time_series)}, keys: {list(time_series.keys())[:3] if isinstance(time_series, dict) else 'N/A'}")
                        
                        # Handle different response formats
                        if isinstance(time_series, dict):
                            # Check if values are dicts (with uniques) or just numbers
                            sample_value = list(time_series.values())[0] if time_series else None
                            
                            if isinstance(sample_value, dict):
                                # Format: {"2025-11-19 21:15": {"uniques": 1234, "count": 5678}}
                                # Sum uniques across all intervals (users might appear in multiple intervals)
                                for time_str, metrics in time_series.items():
                                    if isinstance(metrics, dict):
                                        uniques = metrics.get('uniques', 0)
                                        # For a single interval query, we should get one value
                                        # But if multiple intervals, we take the max (or could sum)
                                        total_uniques = max(total_uniques, uniques)
                                    else:
                                        # Fallback: use the value directly if it's a number
                                        total_uniques = max(total_uniques, int(metrics) if isinstance(metrics, (int, float)) else 0)
                            elif isinstance(sample_value, (int, float)):
                                # Format: {"2025-11-19 21:15": 1234} or {"2025-11-19 00:00:00": 1234}
                                # With type='unique', these values ARE the distinct user counts per interval
                                # We need to filter intervals that overlap with our time window
                                # For distinct users across overlapping intervals, we take the max (union)
                                
                                interval_values = []
                                for time_str, uniques_count in time_series.items():
                                    try:
                                        # Parse time string - try different formats
                                        interval_time = None
                                        for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"]:
                                            try:
                                                interval_time = datetime.strptime(time_str, fmt)
                                                break
                                            except ValueError:
                                                continue
                                        
                                        if interval_time:
                                            # Check if this interval overlaps with our time window
                                            # Determine interval duration based on unit
                                            if interval_type == "hourly":
                                                interval_end = interval_time + timedelta(hours=1)
                                            else:
                                                # Minute intervals - calculate from params
                                                interval_mins = params.get('interval', 1)
                                                interval_end = interval_time + timedelta(minutes=interval_mins)
                                            
                                            if interval_time < end_time and interval_end > start_time:
                                                interval_values.append(int(uniques_count))
                                                print(f"  Interval {time_str} ({interval_time} to {interval_end}): {uniques_count} uniques (overlaps window)")
                                        else:
                                            # Can't parse time, include it to be safe
                                            interval_values.append(int(uniques_count))
                                    except (ValueError, TypeError) as e:
                                        print(f"  Warning: Could not parse interval time '{time_str}': {e}")
                                        interval_values.append(int(uniques_count))
                                
                                if interval_values:
                                    # For hourly aggregation, we typically get one interval that matches our hour window
                                    # For distinct users, we take the max (union) of overlapping intervals
                                    # This is accurate for hourly windows
                                    if interval_type == "hourly" and len(interval_values) == 1:
                                        # Single hour interval - use it directly
                                        total_uniques = interval_values[0]
                                        print(f"Query API returned {total_uniques} distinct users for {query_type} (single hour interval)")
                                    else:
                                        # Multiple intervals - take max (union) for distinct users
                                        total_uniques = max(interval_values)
                                        print(f"Query API: {len(interval_values)} interval(s) overlap window, uniques: {interval_values}, using max: {total_uniques}")
                                else:
                                    print(f"⚠️  No intervals found overlapping time window {start_time} to {end_time}")
                                    total_uniques = 0
                            else:
                                print(f"⚠️  Unexpected time series value format: {type(sample_value)}")
                                print(f"Sample value: {sample_value}")
                                return 0
                        else:
                            print(f"⚠️  Time series is not a dict: {type(time_series)}")
                            return 0
                        
                        print(f"Mixpanel Query API returned {total_uniques} distinct users for {query_type}")
                        return total_uniques
                    else:
                        print(f"⚠️  No event key found in response")
                        return 0
                else:
                    print(f"⚠️  No 'values' key in data object. Keys: {list(data_obj.keys())}")
                    # Try to print the actual response for debugging
                    print(f"Response data: {json.dumps(data, indent=2)[:500]}")
                    return 0
            else:
                print(f"⚠️  No 'data' key in response. Keys: {list(data.keys())}")
                print(f"Response: {json.dumps(data, indent=2)[:500]}")
                return 0
        else:
            error_msg = f"Mixpanel Query API returned {response.status_code}"
            try:
                error_body = response.text[:500]
                error_msg += f": {error_body}"
                print(f"⚠️  {error_msg}")
            except:
                pass
            
            # If querying "all events" without event parameter failed, return 0
            # The caller will handle the fallback to specific events
            if not event_name and response.status_code == 400:
                return 0
            
            print(f"⚠️  {error_msg}, using BigQuery fallback")
            # Fallback to BigQuery
            if event_name:
                return query_distinct_users_by_hour(event_name, start_time, end_time)
            else:
                return query_total_active_users_by_hour(start_time, end_time)
            
    except Exception as e:
        print(f"⚠️  Error querying Mixpanel Query API: {e}, using BigQuery fallback")
        import traceback
        traceback.print_exc()
        # Fallback to BigQuery
        if event_name:
            return query_distinct_users_by_hour(event_name, start_time, end_time)
        else:
            return query_total_active_users_by_hour(start_time, end_time)


def fetch_total_active_users_from_mixpanel(
    start_time: datetime,
    end_time: datetime,
    api_secret: str,
    project_id: str
) -> int:
    """
    Fetch total active users (users who had ANY event).
    
    Since Mixpanel Query API requires an event parameter, we use Export API
    but with optimized processing - we'll process events more efficiently
    by focusing on the time window.
    
    Args:
        start_time: Start of time range
        end_time: End of time range
        api_secret: Mixpanel API secret
        project_id: Mixpanel project ID
    
    Returns:
        Count of distinct users who had any event
    """
    # Query API requires event parameter, so we can't query "all events" directly
    # Use Export API but with better optimization - only process events in our time window
    now = datetime.utcnow()
    if start_time > now:
        raise ValueError(f"Start time {start_time} is in the future")
    if end_time > now:
        print(f"Warning: End time {end_time} is in the future, adjusting to now")
        end_time = now
    if end_time < start_time:
        raise ValueError(f"End time {end_time} is before start time {start_time}")
    
    base_url = "https://data.mixpanel.com/api/2.0/export"
    
    from_date = start_time.strftime("%Y-%m-%d")
    to_date = end_time.strftime("%Y-%m-%d")
    
    today = now.strftime("%Y-%m-%d")
    if from_date > today:
        from_date = today
    if to_date > today:
        to_date = today
    
    # Query ALL events (no event filter) to get total active users
    params = {
        "from_date": from_date,
        "to_date": to_date
    }
    
    if not api_secret or not api_secret.strip():
        raise ValueError("Mixpanel API secret is required. Set MIXPANEL_API_SECRET")
    
    auth = base64.b64encode(f"{api_secret}:".encode()).decode()
    
    start_timestamp = int(start_time.timestamp())
    end_timestamp = int(end_time.timestamp())
    
    print(f"Fetching total active users from Mixpanel Export API (all events): {from_date} to {to_date}")
    print(f"Time window: {start_time} UTC to {end_time} UTC (timestamps: {start_timestamp} to {end_timestamp})")
    print(f"  Note: Mixpanel dashboard might show times in a different timezone (e.g., PST/PDT = UTC-8)")
    
    try:
        response = requests.get(
            base_url,
            params=params,
            headers={
                "Authorization": f"Basic {auth}",
                "Accept": "text/plain",
                "User-Agent": "RT-MP-Collector/1.0"
            },
            stream=True,
            timeout=300
        )
        
        if response.status_code == 200:
            distinct_users = set()
            event_count = 0
            events_in_window = 0
            max_events = 5000000  # Increased limit significantly (5M events) to capture more events
            
            print(f"Processing events to find distinct users (max {max_events} events)...")
            print(f"Time window: {start_time} UTC to {end_time} UTC (timestamps: {start_timestamp} to {end_timestamp})")
            print(f"  If Mixpanel dashboard shows different timezone, adjust accordingly")
            
            # Track events by timestamp to understand distribution
            events_before_window = 0
            events_after_window = 0
            earliest_event_time = None
            latest_event_time = None
            
            try:
                # Wrap iter_lines in try-except to catch connection errors during streaming
                for line in response.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    
                    if event_count >= max_events:
                        print(f"⚠️  Reached processing limit ({max_events} events), found {events_in_window} in time window")
                        print(f"   Events before window: {events_before_window}, after window: {events_after_window}")
                        if earliest_event_time:
                            print(f"   Earliest event: {datetime.fromtimestamp(earliest_event_time)} UTC (timestamp: {earliest_event_time})")
                        if latest_event_time:
                            print(f"   Latest event: {datetime.fromtimestamp(latest_event_time)} UTC (timestamp: {latest_event_time})")
                        print(f"   Target window: {start_time} to {end_time} UTC (timestamps: {start_timestamp} to {end_timestamp})")
                        break
                    
                    try:
                        event = json.loads(line)
                        event_count += 1
                        
                        # Filter by timestamp within our window
                        event_time = event.get("properties", {}).get("time")
                        if event_time:
                            # Track earliest and latest event times
                            if earliest_event_time is None or event_time < earliest_event_time:
                                earliest_event_time = event_time
                            if latest_event_time is None or event_time > latest_event_time:
                                latest_event_time = event_time
                            
                            if event_time < start_timestamp:
                                events_before_window += 1
                            elif event_time > end_timestamp:
                                events_after_window += 1
                            elif start_timestamp <= event_time <= end_timestamp:
                                events_in_window += 1
                                distinct_id = event.get("properties", {}).get("distinct_id")
                                if distinct_id:
                                    distinct_users.add(distinct_id)
                            
                            # Log first few events and periodic updates for debugging
                            if event_count <= 10 or event_count % 100000 == 0:
                                dt = datetime.fromtimestamp(event_time)
                                in_window = start_timestamp <= event_time <= end_timestamp
                                print(f"  Event {event_count}: timestamp={event_time} ({dt} UTC), in_window={in_window}, events_in_window={events_in_window}, distinct_users={len(distinct_users)}")
                    except (json.JSONDecodeError, KeyError, TypeError) as e:
                        if event_count <= 5:
                            print(f"  Error parsing event {event_count}: {e}")
                        continue
                
                if events_in_window == 0:
                    print(f"⚠️  Processed {event_count} events but found 0 in time window, using BigQuery fallback")
                    return query_total_active_users_by_hour(start_time, end_time)
                
                print(f"Processed {event_count} events from Mixpanel ({events_in_window} in time window), found {len(distinct_users)} distinct active users")
                return len(distinct_users)
                
            except (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError, 
                    requests.exceptions.Timeout, OSError) as stream_error:
                # Connection error during streaming
                print(f"⚠️  Connection error during streaming (processed {event_count} events): {stream_error}")
                if events_in_window == 0:
                    print(f"⚠️  No events processed in time window, using BigQuery fallback")
                    return query_total_active_users_by_hour(start_time, end_time)
                else:
                    print(f"⚠️  Returning partial result: {len(distinct_users)} distinct users from {events_in_window} events")
                    return len(distinct_users)
        else:
            print(f"⚠️  Mixpanel Export API returned {response.status_code}, using BigQuery fallback")
            return query_total_active_users_by_hour(start_time, end_time)
            
    except Exception as e:
        print(f"⚠️  Error fetching total active users from Mixpanel: {e}, using BigQuery fallback")
        import traceback
        traceback.print_exc()
        return query_total_active_users_by_hour(start_time, end_time)

