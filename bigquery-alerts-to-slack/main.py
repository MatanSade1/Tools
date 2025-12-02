import os
import sys
from google.cloud import bigquery
import google.auth
from google.auth.transport.requests import Request
import functions_framework
from datetime import datetime, time, date
import logging
from pathlib import Path
import json
from typing import Dict, Any
import requests
from dataclasses import dataclass
from flask import Flask, jsonify, request as flask_request
import google.cloud.logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

def setup_logging():
    # Get logger first (singleton pattern - same instance returned)
    logger = logging.getLogger('BigQueryAlerts')
    
    # If logger already has handlers configured, return it to avoid duplicates
    if logger.handlers:
        return logger
    
    # Check if running in Cloud environment
    if os.getenv('FUNCTION_TARGET') or os.getenv('K_SERVICE'):
        # Running in Cloud Run/Cloud Functions - use Cloud Logging
        try:
            # Instantiates a Cloud Logging client
            logging_client = google.cloud.logging.Client()
            
            # Integrates Cloud Logging handler with Python logging
            # This maps Python logging levels to Cloud Logging severity levels
            logging_client.setup_logging()
            
            logger.setLevel(logging.INFO)
            # Prevent propagation to root logger to avoid duplicate logs
            # setup_logging() adds a handler to root logger, and by default child loggers propagate
            logger.propagate = False
            
            # Add Cloud Logging handler directly to this logger
            cloud_handler = logging_client.get_default_handler()
            logger.addHandler(cloud_handler)
            
            logger.info("✅ Cloud Logging integration enabled - severity levels will be correct")
            
        except Exception as e:
            # Fallback if Cloud Logging setup fails
            logger.setLevel(logging.INFO)
            # Only add handler if not already present
            if not logger.handlers:
                handler = logging.StreamHandler()
                handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
                logger.addHandler(handler)
            logger.warning(f"Cloud Logging setup failed, using standard logging: {e}")
        
    else:
        # Running locally - use file-based logging
        logger.setLevel(logging.INFO)
        
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        # Console handler (only add if not already present)
        if not any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler) for h in logger.handlers):
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
        
        # File handler (create new file each time for local runs)
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"bigquery_alerts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        logger.info("Local logging enabled")
    
    return logger
@dataclass
class AlertConfig:
    name: str
    description: str 
    sql: str
    resolution: str
    owner: str
    is_active: str
    slack_alert_channel: str
    alert_id: str = None
    jira_id: str = None
    data_query_link: str = None
    notion_doc_link: str = None
    threshold_for_alerting: int = None
    max_hourly_alerts_per_day: int = None

def is_test_mode():
    """Check if running in test mode based on environment variable or command line"""
    # Check environment variable first
    if os.getenv('TEST_MODE', '').lower() in ['true', '1', 'yes']:
        return True
    # Check command line arguments
    if '--test' in sys.argv or '--test-mode' in sys.argv:
        return True
    return False

def get_settings_table_name():
    """Get the settings table name based on test mode"""
    if is_test_mode():
        return 'yotam-395120.peerplay.bigquery_alerts_to_slack_settings_stage'
    return 'yotam-395120.peerplay.bigquery_alerts_to_slack_settings'

def get_history_table_name():
    """Get the history table name based on test mode"""
    if is_test_mode():
        return 'yotam-395120.peerplay.bigquery_alerts_execution_history_stage'
    return 'yotam-395120.peerplay.bigquery_alerts_execution_history'

def is_execution_time_for_daily_alerts():
    """Check if current time is between 4:50AM and 5:49AM"""
    current_time = datetime.now().time()
    start_time = time(4, 50)
    end_time = time(5, 49)
    
    return start_time <= current_time <= end_time

def load_alerts_from_bigquery(client, resolution=None, settings_table=None):
    if settings_table is None:
        settings_table = get_settings_table_name()
    
    query = f"""
    SELECT 
        name, 
        description, 
        sql, 
        resolution, 
        owner, 
        is_active, 
        COALESCE(slack_alert_channel, 'data-alerts-sandbox') as slack_alert_channel,
        alert_id,
        jira_id,
        data_query_link,
        notion_doc_link,
        threshold_for_alerting,
        max_hourly_alerts_per_day
    FROM `{settings_table}`
    WHERE is_active = 'T'
    """
    if resolution:
        query += f" AND resolution = '{resolution}'"
    
    query_job = client.query(query)
    results = query_job.result()
    
    alerts = []
    logger = logging.getLogger('BigQueryAlerts')
    
    for row in results:
        # Check if resolution is valid
        if row.resolution not in ['H', 'D']:
            logger.error(f"Invalid resolution '{row.resolution}' for alert '{row.name}'. Must be 'H' or 'D'. This alert will be skipped.")
            continue
            
        # For Daily alerts, check if we're in the execution window
        if row.resolution == 'D' and not is_execution_time_for_daily_alerts():
            logger.info(f"Skipping daily alert '{row.name}' as current time is not between 4:50AM and 5:49AM")
            continue
            
        # Check threshold_for_alerting
        threshold = None
        if hasattr(row, 'threshold_for_alerting') and row.threshold_for_alerting is not None:
            try:
                threshold = int(row.threshold_for_alerting)
                if threshold <= 0:
                    logger.error(f"Invalid threshold_for_alerting value for alert '{row.name}': {threshold}. Must be a positive integer. This alert will be skipped.")
                    continue
            except (ValueError, TypeError):
                logger.error(f"Invalid threshold_for_alerting value for alert '{row.name}': {row.threshold_for_alerting}. Must be a valid integer. This alert will be processed with default threshold.")
                threshold = None
        
        # Check max_hourly_alerts_per_day for hourly alerts
        max_hourly_alerts = None
        if row.resolution == 'H' and hasattr(row, 'max_hourly_alerts_per_day') and row.max_hourly_alerts_per_day is not None:
            try:
                max_hourly_alerts = int(row.max_hourly_alerts_per_day)
                if max_hourly_alerts <= 0:
                    logger.error(f"Invalid max_hourly_alerts_per_day value for alert '{row.name}': {max_hourly_alerts}. Must be a positive integer. This alert will use unlimited alerts.")
                    max_hourly_alerts = None
            except (ValueError, TypeError):
                logger.error(f"Invalid max_hourly_alerts_per_day value for alert '{row.name}': {row.max_hourly_alerts_per_day}. Must be a valid integer. This alert will use unlimited alerts.")
                max_hourly_alerts = None
                
        alert = AlertConfig(
            name=row.name,
            description=row.description,
            sql=row.sql,
            resolution=row.resolution,
            owner=row.owner,
            is_active=row.is_active,
            slack_alert_channel=row.slack_alert_channel,
            alert_id=row.alert_id if hasattr(row, 'alert_id') else None,
            jira_id=row.jira_id if hasattr(row, 'jira_id') else None,
            data_query_link=row.data_query_link if hasattr(row, 'data_query_link') else None,
            notion_doc_link=row.notion_doc_link if hasattr(row, 'notion_doc_link') else None,
            threshold_for_alerting=threshold,
            max_hourly_alerts_per_day=max_hourly_alerts
        )
        alerts.append(alert)
    
    return alerts

def setup_credentials():
    logger = logging.getLogger('BigQueryAlerts')
    
    if os.getenv('FUNCTION_TARGET') or os.getenv('K_SERVICE'):
        logger.info("Running in Cloud environment, using default credentials with Drive scopes")
        
        # CRITICAL: Add Drive scopes for external tables linked to Google Sheets
        try:
            credentials, project = google.auth.default(
                scopes=[
                    "https://www.googleapis.com/auth/cloud-platform",
                    "https://www.googleapis.com/auth/drive.readonly",
                    "https://www.googleapis.com/auth/bigquery"
                ]
            )
            
            # Refresh credentials to ensure scopes are applied
            credentials.refresh(Request())
            
            logger.info("✅ Credentials created successfully with Drive and BigQuery scopes")
            return bigquery.Client(credentials=credentials, project=project)
            
        except Exception as e:
            logger.error(f"❌ Failed to create credentials with scopes: {str(e)}")
            logger.info("Falling back to default credentials without explicit scopes")
            return bigquery.Client()
    
    # Local execution path
    creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    
    # If GOOGLE_APPLICATION_CREDENTIALS is set, use it
    if creds_path and os.path.exists(creds_path):
        logger.info(f"Using credentials from GOOGLE_APPLICATION_CREDENTIALS: {creds_path}")
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = creds_path
    else:
        # Try to use Application Default Credentials (ADC)
        logger.info("GOOGLE_APPLICATION_CREDENTIALS not set or file not found, attempting to use Application Default Credentials")
        try:
            # Test if ADC is available
            credentials, project = google.auth.default()
            logger.info("✅ Application Default Credentials found")
        except Exception as e:
            # Fallback to hardcoded path (for backward compatibility)
            fallback_path = "/Users/guyzamir/Documents/Code/bigquery_alerts/json_key/yotam-395120-204239134151.json"
            if os.path.exists(fallback_path):
                logger.info(f"Using fallback credentials path: {fallback_path}")
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = fallback_path
                creds_path = fallback_path
            else:
                error_msg = f"Credentials not found. Please set GOOGLE_APPLICATION_CREDENTIALS or configure Application Default Credentials. Fallback path also not found: {fallback_path}"
                logger.error(error_msg)
                raise FileNotFoundError(error_msg)
    
    # For local execution, also add Drive scopes
    try:
        credentials, project = google.auth.default(
            scopes=[
                "https://www.googleapis.com/auth/cloud-platform",
                "https://www.googleapis.com/auth/drive.readonly",
                "https://www.googleapis.com/auth/bigquery"
            ]
        )
        
        if creds_path:
            logger.info(f"✅ Using credentials from: {creds_path} with Drive and BigQuery scopes")
        else:
            logger.info(f"✅ Using Application Default Credentials with Drive and BigQuery scopes")
        return bigquery.Client(credentials=credentials, project=project)
        
    except Exception as e:
        logger.error(f"❌ Failed to create credentials with scopes: {str(e)}")
        logger.info("Falling back to default credentials without explicit scopes")
        return bigquery.Client()

class AlertProcessor:
    def __init__(self, resolution=None, test_mode=None):
        self.logger = setup_logging()
        self.test_mode = test_mode if test_mode is not None else is_test_mode()
        
        if self.test_mode:
            self.logger.info("🧪 TEST MODE ENABLED - Using stage tables")
        else:
            self.logger.info("🚀 PRODUCTION MODE - Using production tables")
        
        self.logger.info("Initializing Alert Processor")
        current_time = datetime.now()
        self.logger.info(f"Current execution time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            self.client = setup_credentials()
            # Use stage table in test mode, production table otherwise
            if self.test_mode:
                settings_table = 'yotam-395120.peerplay.bigquery_alerts_to_slack_settings_stage'
            else:
                settings_table = 'yotam-395120.peerplay.bigquery_alerts_to_slack_settings'
            self.alerts = load_alerts_from_bigquery(self.client, resolution, settings_table)
            self.logger.info(f"Loaded {len(self.alerts)} active alerts from BigQuery table: {settings_table} for resolution {resolution}")
            
            # Test the history table exists and is accessible
            self.verify_history_table()
            
        except Exception as e:
            self.logger.error(f"Failed to initialize: {str(e)}")
            raise

    def verify_history_table(self):
        """Verify that the history table exists and is accessible"""
        try:
            if self.test_mode:
                history_table = 'yotam-395120.peerplay.bigquery_alerts_execution_history_stage'
            else:
                history_table = 'yotam-395120.peerplay.bigquery_alerts_execution_history'
            test_query = f"""
            SELECT COUNT(*) as count 
            FROM `{history_table}` 
            WHERE 1=0
            """
            query_job = self.client.query(test_query)
            query_job.result()
            self.logger.info(f"History table verified and accessible: {history_table}")
        except Exception as e:
            self.logger.error(f"History table verification failed: {str(e)}")
            self.logger.error("This will prevent cooldown functionality from working properly")

    def check_hourly_alert_cooldown(self, alert: AlertConfig) -> bool:
        """
        Check if an hourly alert has exceeded its daily limit.
        Returns True if alert can be sent, False if it's in cooldown.
        """
        if alert.resolution != 'H' or alert.max_hourly_alerts_per_day is None:
            return True  # No cooldown for daily alerts or unlimited hourly alerts
        
        # Ensure alert_id exists for cooldown check
        if not alert.alert_id:
            self.logger.warning(f"Alert '{alert.name}' has no alert_id, cannot check cooldown. Allowing alert.")
            return True
        
        current_date = date.today()
        
        # Query to count how many alerts were generated today for this alert_id
        if self.test_mode:
            history_table = 'yotam-395120.peerplay.bigquery_alerts_execution_history_stage'
        else:
            history_table = 'yotam-395120.peerplay.bigquery_alerts_execution_history'
        cooldown_query = f"""
        SELECT COUNT(*) as alerts_sent_today
        FROM `{history_table}`
        WHERE alert_id = @alert_id
          AND execution_date = @current_date
          AND alert_generated = TRUE
          AND success = TRUE
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("alert_id", "INT64", int(alert.alert_id)),
                bigquery.ScalarQueryParameter("current_date", "DATE", current_date)
            ]
        )
        
        try:
            self.logger.info(f"Checking cooldown for alert_id {alert.alert_id} on date {current_date}")
            
            # Add timeout to prevent hanging queries (45 seconds total for cooldown check)
            # Use ThreadPoolExecutor to ensure timeout is enforced even if BigQuery client hangs
            # Wrap both query submission and result waiting in timeout
            # Increased timeouts to allow for table operations after cleanup
            query_job = None
            try:
                with ThreadPoolExecutor(max_workers=1) as executor:
                    # Submit the query in a thread with timeout
                    future_query = executor.submit(self.client.query, cooldown_query, job_config)
                    query_job = future_query.result(timeout=15)  # 15 seconds to submit query
                    
                    # Wait for query result with timeout
                    future_result = executor.submit(query_job.result, timeout=15)
                    results = future_result.result(timeout=15)  # 15 seconds to get result
            except (FuturesTimeoutError, Exception) as timeout_error:
                # Try to cancel the query job to free up resources
                if query_job:
                    try:
                        query_job.cancel()
                        self.logger.info(f"Cancelled timed-out cooldown query job for alert '{alert.name}' (ID: {alert.alert_id})")
                    except Exception as cancel_error:
                        self.logger.warning(f"Failed to cancel cooldown query job: {str(cancel_error)}")
                
                self.logger.warning(
                    f"Cooldown check query timed out for alert '{alert.name}' (ID: {alert.alert_id}). "
                    f"Allowing alert to proceed (fail open). Error: {str(timeout_error)}"
                )
                return True  # Fail open - allow alert if we can't check cooldown
            
            # Wrap result iteration in timeout as well - iteration can trigger additional API calls
            try:
                with ThreadPoolExecutor(max_workers=1) as executor:
                    # Convert results to list with timeout (this forces all pages to be fetched)
                    future_list = executor.submit(lambda: list(results))
                    rows_list = future_list.result(timeout=15)  # 15 seconds to iterate/fetch all pages
            except (FuturesTimeoutError, Exception) as iteration_timeout:
                self.logger.warning(
                    f"Cooldown check result iteration timed out for alert '{alert.name}' (ID: {alert.alert_id}). "
                    f"Allowing alert to proceed (fail open). Error: {str(iteration_timeout)}"
                )
                return True  # Fail open - allow alert if we can't iterate results
            
            for row in rows_list:
                alerts_sent_today = row.alerts_sent_today
                
                self.logger.info(
                    f"Cooldown check for alert '{alert.name}' (ID: {alert.alert_id}): "
                    f"{alerts_sent_today} alerts sent today, max allowed: {alert.max_hourly_alerts_per_day}"
                )
                
                if alerts_sent_today >= alert.max_hourly_alerts_per_day:
                    self.logger.info(
                        f"Alert '{alert.name}' is in cooldown. "
                        f"Already sent {alerts_sent_today} alerts today (max: {alert.max_hourly_alerts_per_day})"
                    )
                    return False
                else:
                    return True
                    
        except Exception as e:
            self.logger.error(f"Error checking cooldown for alert '{alert.name}': {str(e)}")
            # If we can't check cooldown, allow the alert to proceed (fail open)
            return True
        
        return True

    def log_alert_execution(self, alert: AlertConfig, alert_generated: bool, row_count: int = None, 
                          threshold: int = None, success: bool = True, error_message: str = None):
        """
        Log the alert execution to the history table for cooldown tracking.
        """
        # Skip logging if alert doesn't have an alert_id
        if not alert.alert_id:
            self.logger.warning(f"Cannot log execution for alert '{alert.name}' - no alert_id provided")
            return False
        
        current_timestamp = datetime.now()
        current_date = current_timestamp.date()
        
        # Convert alert_id to integer
        try:
            alert_id_int = int(alert.alert_id)
        except (ValueError, TypeError):
            self.logger.error(f"Invalid alert_id '{alert.alert_id}' for alert '{alert.name}' - cannot convert to integer")
            return False
        
        # Ensure proper data types and handle None values
        alert_generated_bool = alert_generated if alert_generated is not None else False
        success_bool = success if success is not None else True
        row_count_int = row_count if row_count is not None else 0
        threshold_int = threshold if threshold is not None else 1
        alert_name_str = str(alert.name) if alert.name is not None else ""
        slack_channel_str = str(alert.slack_alert_channel) if alert.slack_alert_channel is not None else ""
        resolution_str = str(alert.resolution) if alert.resolution is not None else ""
        error_message_str = str(error_message) if error_message is not None else ""
        
        if self.test_mode:
            history_table = 'yotam-395120.peerplay.bigquery_alerts_execution_history_stage'
        else:
            history_table = 'yotam-395120.peerplay.bigquery_alerts_execution_history'
        insert_query = f"""
        INSERT INTO `{history_table}`
        (alert_id, alert_name, execution_timestamp, execution_date, alert_generated, 
         row_count, threshold_value, slack_channel, resolution, success, error_message)
        VALUES (@alert_id, @alert_name, @execution_timestamp, @execution_date, @alert_generated,
                @row_count, @threshold_value, @slack_channel, @resolution, @success, @error_message)
        """
        
        # Create parameters with explicit type checking
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("alert_id", "INT64", alert_id_int),
                bigquery.ScalarQueryParameter("alert_name", "STRING", alert_name_str),
                bigquery.ScalarQueryParameter("execution_timestamp", "TIMESTAMP", current_timestamp),
                bigquery.ScalarQueryParameter("execution_date", "DATE", current_date),
                bigquery.ScalarQueryParameter("alert_generated", "BOOL", alert_generated_bool),
                bigquery.ScalarQueryParameter("row_count", "INT64", row_count_int),
                bigquery.ScalarQueryParameter("threshold_value", "INT64", threshold_int),
                bigquery.ScalarQueryParameter("slack_channel", "STRING", slack_channel_str),
                bigquery.ScalarQueryParameter("resolution", "STRING", resolution_str),
                bigquery.ScalarQueryParameter("success", "BOOL", success_bool),
                bigquery.ScalarQueryParameter("error_message", "STRING", error_message_str)
            ]
        )
        
        try:
            self.logger.info(f"Attempting to log execution for alert '{alert.name}' (ID: {alert_id_int})")
            self.logger.info(f"Log parameters: alert_generated={alert_generated_bool}, success={success_bool}, date={current_date}")
            
            # Create a separate BigQuery client for execution logging to avoid connection pool issues
            # If the main client's connection is blocked, this ensures execution logging can still proceed
            logging_client = setup_credentials()
            
            # Add timeout to prevent hanging queries (35 seconds total for execution logging)
            # Use ThreadPoolExecutor to ensure timeout is enforced even if BigQuery client hangs
            # Wrap both query submission and result waiting in timeout
            # Increased timeout to 30 seconds for result retrieval to allow for table operations
            query_job = None
            try:
                with ThreadPoolExecutor(max_workers=1) as executor:
                    # Submit the query in a thread with timeout using the separate client
                    future_query = executor.submit(logging_client.query, insert_query, job_config)
                    query_job = future_query.result(timeout=5)  # 5 seconds to submit query
                    
                    # Wait for query result with timeout
                    future_result = executor.submit(query_job.result, timeout=30)
                    future_result.result(timeout=30)  # 30 seconds to get result
            except (FuturesTimeoutError, Exception) as timeout_error:
                # Try to cancel the query job to free up resources
                if query_job:
                    try:
                        query_job.cancel()
                        self.logger.info(f"Cancelled timed-out query job for alert '{alert.name}' (ID: {alert_id_int})")
                    except Exception as cancel_error:
                        self.logger.warning(f"Failed to cancel query job: {str(cancel_error)}")
                
                self.logger.warning(
                    f"Execution logging query timed out for alert '{alert.name}' (ID: {alert_id_int}). "
                    f"Logging failed. Error: {str(timeout_error)}"
                )
                return False  # Return False since logging failed
            
            self.logger.info(f"✅ Alert execution logged successfully for '{alert.name}' (ID: {alert_id_int})")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to log alert execution for '{alert.name}' (ID: {alert_id_int}): {str(e)}")
            return False

    def get_slack_webhook_url(self, channel: str) -> str:
        base_url = "https://hooks.slack.com/services/T03SBHW3W4S"
        
        channel_tokens = {
            'data-alerts-sandbox': 'B089W8NRF1A/fjiKtqyUekCbnxLRnFRRx3cp',
            'data-alerts-critical': 'B08C1BKGYJ3/g3o3p9JNKPVybiIQIxUp77Cy',
            'data-alerts-non-critical': 'B08CUJ7PMDX/YXoVzLajPWgyYcqEvMvzQyGL'
        }
        
        token = channel_tokens.get(channel)
        if not token:
            self.logger.warning(f"No webhook token found for channel {channel}, using sandbox channel")
            token = channel_tokens['data-alerts-sandbox']
        
        return f"{base_url}/{token}"

    def serialize_for_json(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return str(obj)

    def format_slack_message(self, alert: AlertConfig, row_count: int, first_row: Dict[str, Any]) -> Dict[str, Any]:
        # Truncate long values in the first row
        formatted_row = {}
        for key, value in first_row.items():
            serialized_value = self.serialize_for_json(value)
            if len(serialized_value) > 1000:
                formatted_row[key] = serialized_value[:1000] + "... (truncated)"
            else:
                formatted_row[key] = serialized_value

        # Add cooldown information for hourly alerts
        cooldown_text = ""
        if alert.resolution == 'H' and alert.max_hourly_alerts_per_day:
            cooldown_text = f"*Max alerts per day:*\n{alert.max_hourly_alerts_per_day}"
        else:
            cooldown_text = "*Max alerts per day:*\nUnlimited"

        # Format header text based on test mode
        if self.test_mode:
            header_text = f"🧪 TEST: {alert.name}"
        else:
            header_text = f"🚨 {alert.name}"

        # Build message blocks
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": header_text,
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Description:*\n{alert.description}"
                    }
                ]
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Alert ID:*\n{alert.alert_id or 'N/A'}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Owner:*\n{alert.owner or 'N/A'}"
                    }
                ]
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Resolution (D/H):*\n{alert.resolution}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": cooldown_text
                    }
                ]
            }
        ]

        # SQL Query section removed per user request

        blocks.extend([
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Number of query returned rows:*\n{row_count}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Threshold for alerting:*\n{alert.threshold_for_alerting or 'N/A'}"
                    }
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*First query returned row:*\n```{json.dumps(formatted_row, indent=2)}```"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Jira ID:*\n{alert.jira_id or 'N/A'}"
                    }
                ]
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Notion Doc:*\n{alert.notion_doc_link or 'N/A'}"
                    }
                ]
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Alert generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
                    }
                ]
            },
            {
                "type": "divider"
            }
        ])

        # Format message for mobile notifications
        # text: Used as notification preview (shows only alert title and channel)
        # username: Empty string removes sender name from notification
        mobile_notification_text = f"{alert.name} - {alert.slack_alert_channel}"
        message = {
            "text": mobile_notification_text,  # Notification preview - shows only alert title and channel
            "username": "",  # Remove sender name from mobile notification
            "blocks": blocks
        }
        return message

    def send_to_slack(self, message: Dict[str, Any], channel: str) -> bool:
        webhook_url = self.get_slack_webhook_url(channel)
        
        if not webhook_url:
            self.logger.error(f"Slack webhook URL not configured for channel: {channel}")
            return False
            
        try:
            response = requests.post(
                webhook_url,
                data=json.dumps(message),
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()
            self.logger.info(f"Message sent to Slack channel {channel} successfully")
            return True
        except Exception as e:
            self.logger.error(f"Error sending message to Slack channel {channel}: {str(e)}")
            return False

    def process_alert(self, alert: AlertConfig) -> Dict[str, Any]:
        try:
            # Check cooldown for hourly alerts ONLY if alert has an alert_id
            if alert.resolution == 'H' and alert.alert_id:
                if not self.check_hourly_alert_cooldown(alert):
                    self.logger.info(f"Alert '{alert.name}' skipped due to cooldown")
                    # Log the execution as skipped (not generated)
                    logging_success = self.log_alert_execution(
                        alert, 
                        alert_generated=False, 
                        success=True, 
                        error_message="Skipped due to cooldown"
                    )
                    if not logging_success:
                        self.logger.warning(f"Failed to log cooldown skip for alert '{alert.name}'")
                    
                    return {
                        'success': True,
                        'alert_generated': False,
                        'skipped_reason': 'cooldown',
                        'max_hourly_alerts_per_day': alert.max_hourly_alerts_per_day,
                        'timestamp': datetime.now().isoformat(),
                        'slack_channel': alert.slack_alert_channel,
                        'logging_success': logging_success
                    }
            elif alert.resolution == 'H' and not alert.alert_id:
                self.logger.warning(f"Hourly alert '{alert.name}' has no alert_id - cooldown mechanism disabled")
            
            # Add timeout to prevent hanging queries for main alert execution
            # Use ThreadPoolExecutor to ensure timeout is enforced even if BigQuery client hangs
            # Wrap both query submission and result waiting in timeout
            # Reduced timeouts to catch before Gunicorn worker timeout (~30s)
            query_job = None
            try:
                with ThreadPoolExecutor(max_workers=1) as executor:
                    # Submit the query in a thread with timeout
                    future_query = executor.submit(self.client.query, alert.sql)
                    query_job = future_query.result(timeout=10)  # 10 seconds to submit query
                    
                    # Wait for query result with timeout
                    future_result = executor.submit(query_job.result, timeout=20)
                    results = future_result.result(timeout=20)  # 20 seconds to get result
            except (FuturesTimeoutError, Exception) as timeout_error:
                # Try to cancel the query job to free up resources
                if query_job:
                    try:
                        query_job.cancel()
                        self.logger.info(f"Cancelled timed-out alert query job for alert '{alert.name}' (ID: {alert.alert_id or 'N/A'})")
                    except Exception as cancel_error:
                        self.logger.warning(f"Failed to cancel alert query job: {str(cancel_error)}")
                
                self.logger.error(
                    f"Alert query timed out for alert '{alert.name}' (ID: {alert.alert_id or 'N/A'}). "
                    f"Alert execution failed. Error: {str(timeout_error)}"
                )
                
                # Log the execution as failed
                logging_success = self.log_alert_execution(
                    alert, 
                    alert_generated=False, 
                    row_count=0,
                    threshold=alert.threshold_for_alerting or 1,
                    success=False,
                    error_message=f"Query timeout: {str(timeout_error)}"
                )
                
                return {
                    'success': False,
                    'row_count': 0,
                    'threshold': alert.threshold_for_alerting or 1,
                    'alert_generated': False,
                    'error': f"Query timeout: {str(timeout_error)}",
                    'timestamp': datetime.now().isoformat(),
                    'slack_channel': alert.slack_alert_channel,
                    'logging_success': logging_success
                }
            
            # Wrap result iteration in timeout as well - iteration can trigger additional API calls
            try:
                with ThreadPoolExecutor(max_workers=1) as executor:
                    # Convert results to list with timeout (this forces all pages to be fetched)
                    future_list = executor.submit(lambda: list(results))
                    rows = future_list.result(timeout=30)  # 30 seconds to iterate/fetch all pages
            except (FuturesTimeoutError, Exception) as iteration_timeout:
                # Try to cancel the query job to free up resources
                if query_job:
                    try:
                        query_job.cancel()
                        self.logger.info(f"Cancelled timed-out alert query job after iteration timeout for alert '{alert.name}' (ID: {alert.alert_id or 'N/A'})")
                    except Exception as cancel_error:
                        self.logger.warning(f"Failed to cancel alert query job: {str(cancel_error)}")
                
                self.logger.error(
                    f"Alert query result iteration timed out for alert '{alert.name}' (ID: {alert.alert_id or 'N/A'}). "
                    f"Alert execution failed. Error: {str(iteration_timeout)}"
                )
                
                # Log the execution as failed
                logging_success = self.log_alert_execution(
                    alert, 
                    alert_generated=False, 
                    row_count=0,
                    threshold=alert.threshold_for_alerting or 1,
                    success=False,
                    error_message=f"Result iteration timeout: {str(iteration_timeout)}"
                )
                
                return {
                    'success': False,
                    'row_count': 0,
                    'threshold': alert.threshold_for_alerting or 1,
                    'alert_generated': False,
                    'error': f"Result iteration timeout: {str(iteration_timeout)}",
                    'timestamp': datetime.now().isoformat(),
                    'slack_channel': alert.slack_alert_channel,
                    'logging_success': logging_success
                }
            
            row_count = len(rows)
            
            # Define newline characters outside the f-string
            newline = '\n'
            carriage_return = '\r'

            # Log alert definition with separate entries
            self.logger.info(f"Processing Alert: {alert.name}")
            self.logger.info(f"Alert ID: {alert.alert_id or 'N/A'}")
            self.logger.info(f"Alert Description: {alert.description}")
            self.logger.info(f"Alert Owner: {alert.owner or 'N/A'}")
            self.logger.info(f"Slack Channel: {alert.slack_alert_channel}")

            # Log SQL query - single line with newlines removed
            self.logger.info(f"Alert SQL: {alert.sql.replace(newline, ' ').replace(carriage_return, ' ').strip()}")

            # Log configuration
            self.logger.info(f"Threshold: {alert.threshold_for_alerting or 'N/A (using default of 1)'}")
            self.logger.info(f"Max hourly alerts: {alert.max_hourly_alerts_per_day or 'Unlimited'}")

            # Log resolution - single line with newlines removed
            self.logger.info(f"Resolution: {alert.resolution.replace(newline, ' ').replace(carriage_return, ' ').strip()}")

            # Log execution result
            self.logger.info(f"Alert Execution Result for {alert.name}: {row_count} records returned")
                        
            # Check if there are rows to analyze
            if row_count == 0:
                self.logger.info("No rows returned - no alert will be generated")
                # Log the execution
                logging_success = self.log_alert_execution(alert, alert_generated=False, row_count=row_count, 
                                       threshold=alert.threshold_for_alerting or 1)
                return {
                    'success': True,
                    'row_count': 0,
                    'threshold': alert.threshold_for_alerting or 1,
                    'alert_generated': False,
                    'timestamp': datetime.now().isoformat(),
                    'slack_channel': alert.slack_alert_channel,
                    'logging_success': logging_success
                }
            
            # Get the first row for analysis and reporting
            first_row = dict(rows[0])
            
            # Check for count columns with value 0
            count_columns = [col for col in first_row.keys() if 'count' in col.lower()]
            if count_columns and all(first_row[col] == 0 for col in count_columns):
                self.logger.info("Count query returned all zeros - no alert will be generated")
                # Log the execution
                logging_success = self.log_alert_execution(alert, alert_generated=False, row_count=row_count, 
                                       threshold=alert.threshold_for_alerting or 1)
                return {
                    'success': True,
                    'row_count': row_count,
                    'count_columns': count_columns,
                    'all_zeros': True,
                    'threshold': alert.threshold_for_alerting or 1,
                    'alert_generated': False,
                    'timestamp': datetime.now().isoformat(),
                    'slack_channel': alert.slack_alert_channel,
                    'logging_success': logging_success
                }
            
            # Determine if alert should be generated based on threshold logic
            should_generate_alert = False
            threshold = alert.threshold_for_alerting or 1  # Default to 1 if not specified
            
            # Check row count against threshold
            if row_count >= threshold:
                should_generate_alert = True
            # If there are count columns, also check if any exceed the threshold
            elif count_columns:
                for col in count_columns:
                    if isinstance(first_row[col], (int, float)) and first_row[col] >= threshold:
                        should_generate_alert = True
                        break
            
            slack_success = True
            logging_success = True
            
            if should_generate_alert:
                self.logger.info(f"Alert will be generated. Number of returned rows = {row_count}, threshold = {threshold}")
                self.logger.info(f"First row of results: {first_row}")
                
                message = self.format_slack_message(alert, row_count, first_row)
                slack_success = self.send_to_slack(message, alert.slack_alert_channel)
                
                # Log the execution AFTER sending to Slack
                logging_success = self.log_alert_execution(alert, alert_generated=True, row_count=row_count, 
                                       threshold=threshold, success=slack_success)
                
                if logging_success:
                    self.logger.info(f"✅ Alert execution logged successfully for '{alert.name}' with alert_generated=True")
                else:
                    self.logger.error(f"❌ Failed to log alert execution for '{alert.name}'")
            else:
                self.logger.info(f"Alert will not be generated. Values do not meet threshold = {threshold}")
                # Log the execution
                logging_success = self.log_alert_execution(alert, alert_generated=False, row_count=row_count, 
                                       threshold=threshold)
            
            return {
                'success': True,
                'row_count': row_count,
                'threshold': threshold,
                'alert_generated': should_generate_alert,
                'max_hourly_alerts_per_day': alert.max_hourly_alerts_per_day,
                'timestamp': datetime.now().isoformat(),
                'slack_channel': alert.slack_alert_channel,
                'slack_success': slack_success,
                'logging_success': logging_success
            }
            
        except Exception as e:
            error_msg = f"Error processing alert '{alert.name}': {str(e)}"
            self.logger.error(error_msg)
            # Log the execution with error
            logging_success = self.log_alert_execution(alert, alert_generated=False, success=False, error_message=str(e))
            return {
                'success': False,
                'error': error_msg,
                'timestamp': datetime.now().isoformat(),
                'slack_channel': alert.slack_alert_channel,
                'logging_success': logging_success
            }

    def process_all_alerts(self) -> list:
        self.logger.info("Starting alert processing")
        results = []
        
        for alert in self.alerts:
            result = self.process_alert(alert)
            results.append({
                'alert_name': alert.name,
                'result': result
            })
        
        self.logger.info("Completed processing all alerts")
        
        # Summary of logging success
        successful_logs = sum(1 for r in results if r['result'].get('logging_success', False))
        total_alerts = len(results)
        self.logger.info(f"Logging summary: {successful_logs}/{total_alerts} alerts logged successfully")
        
        return results

@functions_framework.http
def run_alerts(request):
    """
    HTTP Cloud Function entry point.
    This function will be triggered by Cloud Scheduler via HTTP.
    
    Args:
        request (flask.Request): The request object.
        
    Returns:
        The response text, or any set of values that can be turned into a
        Response object using `make_response`.
    """
    logger = setup_logging()
    logger.info("Starting Alert Processor Cloud Run Function")
    
    try:
        # Get resolution from query parameters if specified
        resolution = request.args.get('resolution')
        # Test mode is disabled for Cloud Run (production only)
        processor = AlertProcessor(resolution, test_mode=False)
        results = processor.process_all_alerts()
        logger.info("Alert Processor Cloud Run Function completed successfully")
        
        # Return results as JSON with flask's jsonify for proper response
        return jsonify({
            'success': True,
            'results': results,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Alert Processor Cloud Run Function failed: {str(e)}")
        # Return error as JSON
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500  # HTTP 500 status code for internal server error

# Expose Flask app for Cloud Run/gunicorn
# Create Flask app and wrap the functions_framework handler
app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
@app.route('/<path:path>', methods=['GET', 'POST'])
def handle_request(path=''):
    """Cloud Run entry point that wraps the functions_framework handler."""
    try:
        # Create a request-like object compatible with functions_framework
        class CloudRunRequest:
            def __init__(self, flask_req):
                self.method = flask_req.method
                self.path = flask_req.path
                self.args = flask_req.args
                self.json = flask_req.get_json(silent=True)
                self.headers = flask_req.headers
                self.data = flask_req.get_data()
        
        # Call the original function
        result = run_alerts(CloudRunRequest(flask_request))
        
        # Return the result (it's already a Flask response from jsonify)
        return result
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger = logging.getLogger('BigQueryAlerts')
        logger.error(f"Error handling request: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

if __name__ == "__main__":
    """
    Local execution entry point.
    This will be used when running the script directly on your laptop.
    
    Usage:
        python main.py [H|D] [--test|--test-mode]
        
    Examples:
        python main.py              # Run all alerts in production mode
        python main.py H           # Run hourly alerts in production mode
        python main.py --test      # Run all alerts in test mode (uses stage tables)
        python main.py H --test    # Run hourly alerts in test mode
    """
    try:
        # Parse command line arguments
        resolution = None
        test_mode = False
        
        for arg in sys.argv[1:]:
            if arg in ['H', 'D']:
                resolution = arg
            elif arg in ['--test', '--test-mode']:
                test_mode = True
        
        # Check environment variable for test mode
        if not test_mode:
            test_mode = is_test_mode()
        
        if test_mode:
            print("🧪 TEST MODE: Using stage tables")
            print("   - Settings table: yotam-395120.peerplay.bigquery_alerts_to_slack_settings_stage")
            print("   - History table: yotam-395120.peerplay.bigquery_alerts_execution_history_stage")
        else:
            print("🚀 PRODUCTION MODE: Using production tables")
            print("   - Settings table: yotam-395120.peerplay.bigquery_alerts_to_slack_settings")
            print("   - History table: yotam-395120.peerplay.bigquery_alerts_execution_history")
        
        processor = AlertProcessor(resolution, test_mode=test_mode) 
        results = processor.process_all_alerts()
        processor.logger.info("Program completed successfully")
        print(json.dumps(results, indent=2))
    except Exception as e:
        logger = logging.getLogger('BigQueryAlerts')
        logger.error(f"Program failed with error: {str(e)}")
        sys.exit(1)