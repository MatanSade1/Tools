"""Cloud Function for real-time BigQuery event monitoring and alerting."""
import os
from datetime import datetime, timedelta
from typing import Dict

from shared.config import get_config, get_rt_mp_config
from shared.bigquery_client import query_custom_bq_event_count
from shared.slack_client import send_rt_alert
from shared.sheets_client import get_config_from_sheets


# In-memory cache for last alert time per event
# In production, consider using Cloud Firestore or Redis
_last_alert_cache: Dict[str, datetime] = {}


def rt_mp_collector(request):
    """
    Cloud Function entry point for real-time BigQuery event monitoring and alerting.
    
    Queries BigQuery tables for event counts and sends Slack alerts
    when thresholds are exceeded.
    """
    try:
        config = get_config()
        
        # Step 1: Read config from Google Sheets or local config file
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
            rt_config = get_rt_mp_config()
        
        # Validate Slack configuration
        if not config.get("slack_webhook_url"):
            print("Warning: SLACK_WEBHOOK_URL not configured, alerts will be skipped")
        
        # Get enabled events
        events_config = rt_config.get("events", [])
        enabled_events = [e for e in events_config if e.get("enabled", True)]
        
        if not enabled_events:
            print("No enabled events to monitor")
            return {"status": "success", "message": "No enabled events"}
        
        collection_frequency = rt_config.get("collection_frequency_minutes", 15)
        
        print(f"Monitoring {len(enabled_events)} enabled events")
        print(f"Lookback window: last {collection_frequency} minutes")
        
        # Step 2: Check thresholds and send alerts
        alerts_sent = 0
        events_checked = 0
        
        for event_config in enabled_events:
            event_name = event_config["name"]
            aggregation_type = event_config.get("aggregation_type", "count distinct users")
            threshold = event_config.get("alert_threshold", 10)
            channel = event_config.get("alert_channel", "#data-alerts-sandbox")
            meaningful_name = event_config.get("meaningful_name", event_name)
            match_type = event_config.get("match_type", "exact")
            
            # BigQuery table configuration
            table_name = event_config.get("table_name")
            event_name_column = event_config.get("event_name_column")
            distinct_id_column = event_config.get("distinct_id_column", "distinct_id")
            timestamp_column = event_config.get("timestamp_column", "event_timestamp")
            date_column = event_config.get("date_column", "event_date")
            
            # Validate required fields
            if not table_name or not event_name_column:
                print(f"⚠️  Skipping {event_name}: Missing table_name or event_name_column")
                continue
            
            print(f"Checking: {meaningful_name} ({event_name})")
            print(f"  Table: {table_name}, Column: {event_name_column}, Match: {match_type}, Threshold: {threshold}")
            
            try:
                window_end = datetime.utcnow()
                window_start = window_end - timedelta(minutes=collection_frequency)
                
                # Query BigQuery for distinct user count
                distinct_user_count = query_custom_bq_event_count(
                    table_name=table_name,
                    event_name_column=event_name_column,
                    event_name=event_name,
                    distinct_id_column=distinct_id_column,
                    timestamp_column=timestamp_column,
                    date_column=date_column,
                    lookback_minutes=collection_frequency,
                    match_type=match_type
                )
                
                events_checked += 1
                window_minutes = int((window_end - window_start).total_seconds() / 60)
                print(f"  Result: {distinct_user_count} distinct users in last {window_minutes} minutes")
                
                # Check if threshold is exceeded
                should_alert = distinct_user_count > threshold
                
                if should_alert:
                    # Check cooldown (2-hour cooldown per event)
                    cache_key = f"{event_name}_{window_end.strftime('%Y-%m-%d-%H')}"
                    last_alert = _last_alert_cache.get(cache_key)
                    
                    if last_alert:
                        time_since_alert = (datetime.utcnow() - last_alert).total_seconds()
                        if time_since_alert < 7200:  # 2 hours cooldown
                            should_alert = False
                            print(f"  Skipping alert (alerted {int(time_since_alert/60)} minutes ago)")
                    
                    if should_alert:
                        print(f"  🚨 ALERT: {distinct_user_count} distinct users > threshold {threshold}")
                        
                        try:
                            send_rt_alert(
                                meaningful_name=meaningful_name,
                                event_name=event_name,
                                event_count=distinct_user_count,
                                threshold=threshold,
                                channel=channel,
                                start_time=window_start,
                                end_time=window_end,
                                aggregation_type=aggregation_type,
                                total_active_users=None,
                                percentage=None
                            )
                            
                            _last_alert_cache[cache_key] = datetime.utcnow()
                            alerts_sent += 1
                            
                        except Exception as e:
                            print(f"  Error sending alert for {event_name}: {e}")
                            continue
                else:
                    print(f"  No alert needed ({distinct_user_count} <= {threshold})")
                    
            except Exception as e:
                print(f"  Error checking {event_name}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        print(f"\nCompleted: {events_checked} events checked, {alerts_sent} alerts sent")
        
        return {
            "status": "success",
            "events_checked": events_checked,
            "alerts_sent": alerts_sent,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        print(f"Error in rt_mp_collector: {e}")
        import traceback
        traceback.print_exc()
        raise


# Cloud Run Flask app wrapper
try:
    from flask import Flask, request as flask_request, jsonify
    
    app = Flask(__name__)
    
    @app.route('/', methods=['GET', 'POST'])
    def handle_request():
        """Cloud Run entry point that wraps the Cloud Function handler."""
        try:
            class CloudRunRequest:
                def __init__(self, flask_req):
                    self.method = flask_req.method
                    self.path = flask_req.path
                    self.args = flask_req.args
                    self.json = flask_req.get_json(silent=True)
                    self.headers = flask_req.headers
                    self.data = flask_req.get_data()
            
            result = rt_mp_collector(CloudRunRequest(flask_request))
            
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
