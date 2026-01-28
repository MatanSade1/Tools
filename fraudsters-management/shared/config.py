"""Configuration management for Mixpanel to BigQuery pipeline."""
import os
import json
from typing import Dict, List, Optional
from google.cloud import storage
from google.cloud import secretmanager


def load_events_config() -> List[Dict]:
    """
    Load events configuration from file, GCS, or environment variable.
    
    Priority:
    1. GCS path (EVENTS_CONFIG_GCS_PATH)
    2. Environment variable (EVENTS_CONFIG as JSON string)
    3. Local file (config/events_config.json)
    
    Returns:
        List of event configuration dictionaries
    """
    # Try GCS path first
    gcs_path = os.getenv("EVENTS_CONFIG_GCS_PATH")
    if gcs_path:
        try:
            bucket_name, blob_name = gcs_path.replace("gs://", "").split("/", 1)
            client = storage.Client()
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            config_str = blob.download_as_text()
            config = json.loads(config_str)
            return config.get("events", [])
        except Exception as e:
            print(f"Error loading config from GCS: {e}")
            # Fall through to other methods
    
    # Try environment variable
    env_config = os.getenv("EVENTS_CONFIG")
    if env_config:
        try:
            config = json.loads(env_config)
            return config.get("events", [])
        except json.JSONDecodeError as e:
            print(f"Error parsing EVENTS_CONFIG: {e}")
            # Fall through to file
    
    # Try local file (multiple possible paths for Cloud Functions)
    possible_paths = [
        os.path.join(os.path.dirname(__file__), "..", "config", "events_config.json"),
        os.path.join(os.path.dirname(__file__), "config", "events_config.json"),
        "config/events_config.json",
        "/config/events_config.json",
    ]
    
    for config_path in possible_paths:
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
                    return config.get("events", [])
            except Exception as e:
                print(f"Error loading config file {config_path}: {e}")
                continue
    
    # Default fallback
    return [
        {
            "name": "impression_error_null_pointer_detected",
            "enabled": True,
            "alert_threshold": 5,
            "alert_channel": "#alerts-errors",
            "time_window_minutes": 1
        }
    ]


def get_secret(secret_name: str, project_id: Optional[str] = None) -> Optional[str]:
    """
    Get secret from Secret Manager.
    
    Args:
        secret_name: Name of the secret (e.g., "mixpanel-api-secret")
        project_id: GCP project ID (defaults to GCP_PROJECT_ID env var)
    
    Returns:
        Secret value or None if not found
    """
    try:
        if not project_id:
            project_id = os.getenv("GCP_PROJECT_ID")
        if not project_id:
            return None
        
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"Error accessing secret {secret_name}: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_config() -> Dict:
    """
    Get all configuration from environment variables or Secret Manager.
    
    Priority for secrets:
    1. Secret Manager (if MIXPANEL_API_SECRET_NAME is set)
    2. Environment variable (MIXPANEL_API_SECRET)
    
    For Service Account authentication:
    - MIXPANEL_SERVICE_ACCOUNT_USERNAME (Service Account username)
    - MIXPANEL_SERVICE_ACCOUNT_SECRET (Service Account secret)
    """
    project_id = os.getenv("GCP_PROJECT_ID")
    
    # Try Secret Manager first if secret name is provided
    mixpanel_secret_name = os.getenv("MIXPANEL_API_SECRET_NAME")
    mixpanel_api_secret = None
    if mixpanel_secret_name and project_id:
        mixpanel_api_secret = get_secret(mixpanel_secret_name, project_id)
    
    # Fall back to environment variable
    if not mixpanel_api_secret:
        mixpanel_api_secret = os.getenv("MIXPANEL_API_SECRET")
    
    # Service Account credentials (alternative to API secret)
    service_account_username = os.getenv("MIXPANEL_SERVICE_ACCOUNT_USERNAME")
    service_account_secret = os.getenv("MIXPANEL_SERVICE_ACCOUNT_SECRET")
    
    # Try Secret Manager first if secret name is provided for Slack Bot Token
    slack_bot_token_name = os.getenv("SLACK_BOT_TOKEN_NAME")
    slack_bot_token = None
    if slack_bot_token_name and project_id:
        slack_bot_token = get_secret(slack_bot_token_name, project_id)
    
    # Fall back to environment variable
    if not slack_bot_token:
        slack_bot_token = os.getenv("SLACK_BOT_TOKEN")
    
    # Mixpanel GDPR Token (for GDPR deletion requests)
    mixpanel_gdpr_token_name = os.getenv("MIXPANEL_GDPR_TOKEN_NAME")
    mixpanel_gdpr_token = None
    if mixpanel_gdpr_token_name and project_id:
        mixpanel_gdpr_token = get_secret(mixpanel_gdpr_token_name, project_id)
    
    # Fall back to environment variable
    if not mixpanel_gdpr_token:
        mixpanel_gdpr_token = os.getenv("MIXPANEL_GDPR_TOKEN")
    
    # Singular API credentials (for OpenDSR GDPR requests)
    singular_api_key_name = os.getenv("SINGULAR_API_KEY_NAME")
    singular_api_key = None
    if singular_api_key_name and project_id:
        singular_api_key = get_secret(singular_api_key_name, project_id)
    
    # Fall back to environment variable
    if not singular_api_key:
        singular_api_key = os.getenv("SINGULAR_API_KEY")
    
    singular_api_secret_name = os.getenv("SINGULAR_API_SECRET_NAME")
    singular_api_secret = None
    if singular_api_secret_name and project_id:
        singular_api_secret = get_secret(singular_api_secret_name, project_id)
    
    # Fall back to environment variable
    if not singular_api_secret:
        singular_api_secret = os.getenv("SINGULAR_API_SECRET")
    
    # Singular property_id (format: "Platform:AppIdentifier")
    singular_property_id = os.getenv("SINGULAR_PROPERTY_ID")
    
    return {
        "mixpanel_api_secret": mixpanel_api_secret,
        "mixpanel_service_account_username": service_account_username,
        "mixpanel_service_account_secret": service_account_secret,
        "mixpanel_project_id": os.getenv("MIXPANEL_PROJECT_ID"),
        "mixpanel_gdpr_token": mixpanel_gdpr_token,
        "gcp_project_id": project_id,
        "bigquery_dataset": os.getenv("BIGQUERY_DATASET", "mixpanel_data"),
        "bigquery_table": os.getenv("BIGQUERY_TABLE", "mixpanel_events"),
        "rt_mp_dataset": os.getenv("RT_MP_DATASET", "peerplay"),
        "rt_mp_table": os.getenv("RT_MP_TABLE", "rt_mp_events"),
        "slack_webhook_url": os.getenv("SLACK_WEBHOOK_URL"),
        "slack_bot_token": slack_bot_token,
        "gdpr_slack_channel": os.getenv("GDPR_SLACK_CHANNEL", "users-to-delete-their-personal-data"),
        "singular_api_key": singular_api_key,
        "singular_api_secret": singular_api_secret,
        "singular_property_id": singular_property_id,
    }


def get_enabled_events() -> List[Dict]:
    """Get list of enabled events from configuration."""
    events = load_events_config()
    return [e for e in events if e.get("enabled", True)]


def load_rt_mp_events_config() -> Dict:
    """
    Load RT Mixpanel events configuration from file, GCS, or environment variable.
    
    Priority:
    1. Environment variable (RT_MP_EVENTS_CONFIG as JSON string)
    2. GCS path (RT_MP_EVENTS_CONFIG_GCS_PATH)
    3. Local file (config/rt_mp_events_config.json)
    
    Returns:
        Configuration dictionary with events list and collection_frequency_minutes
    """
    # Try environment variable first
    env_config = os.getenv("RT_MP_EVENTS_CONFIG")
    if env_config:
        try:
            return json.loads(env_config)
        except json.JSONDecodeError as e:
            print(f"Error parsing RT_MP_EVENTS_CONFIG: {e}")
            # Fall through to other methods
    
    # Try GCS path
    gcs_path = os.getenv("RT_MP_EVENTS_CONFIG_GCS_PATH")
    if gcs_path:
        try:
            bucket_name, blob_name = gcs_path.replace("gs://", "").split("/", 1)
            client = storage.Client()
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            config_str = blob.download_as_text()
            return json.loads(config_str)
        except Exception as e:
            print(f"Error loading RT config from GCS: {e}")
            # Fall through to file
    
    # Try local file (multiple possible paths for Cloud Functions)
    # Priority: config/rt_mp_events_config.json (relative to function root) first
    possible_paths = [
        "config/rt_mp_events_config.json",  # First: relative to function root (most common in deployed functions)
        os.path.join(os.path.dirname(__file__), "..", "config", "rt_mp_events_config.json"),  # Second: relative to shared/
        os.path.join(os.path.dirname(__file__), "config", "rt_mp_events_config.json"),  # Third: in shared/config/
        os.path.join(os.path.dirname(__file__), "..", "alerts", "config", "rt_mp_events_config.json"),  # Fourth: alerts/config/
        "/config/rt_mp_events_config.json",  # Fifth: absolute path
    ]
    
    print("Attempting to load RT config from possible paths:")
    for config_path in possible_paths:
        print(f"  Trying: {config_path}")
        if os.path.exists(config_path):
            try:
                print(f"  ✅ Found config at: {config_path}")
                with open(config_path, "r") as f:
                    config = json.load(f)
                    print(f"  ✅ Successfully loaded RT config with {len(config.get('events', []))} events")
                    return config
            except Exception as e:
                print(f"  ❌ Error loading RT config file {config_path}: {e}")
                continue
        else:
            print(f"  ⚠️  Path does not exist: {config_path}")
    
    print("⚠️  WARNING: Could not find rt_mp_events_config.json in any expected location, using defaults")
    
    # Default fallback
    return {
        "events": [
            {
                "name": "impression_error_null_pointer_detected",
                "enabled": True,
                "alert_threshold": 10,
                "alert_channel": "#data-alerts-sandbox",
                "meaningful_name": "Null Pointer Error Detected"
            }
        ],
        "collection_frequency_minutes": 15
    }


def get_rt_mp_config() -> Dict:
    """
    Get RT Mixpanel events configuration.
    
    Returns:
        Configuration dictionary with events list and collection_frequency_minutes
    """
    return load_rt_mp_events_config()

