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
from flask import jsonify
import google.cloud.logging

def setup_logging():
    # Check if running in Cloud environment
    if os.getenv('FUNCTION_TARGET') or os.getenv('K_SERVICE'):
        # Running in Cloud Run/Cloud Functions - use Cloud Logging
        try:
            # Instantiates a Cloud Logging client
            logging_client = google.cloud.logging.Client()
            
            # Integrates Cloud Logging handler with Python logging
            # This maps Python logging levels to Cloud Logging severity levels
            logging_client.setup_logging()
            
            logger = logging.getLogger('BigQueryAlerts')
            logger.setLevel(logging.INFO)
            logger.info("✅ Cloud Logging integration enabled - severity levels will be correct")
            
        except Exception as e:
            # Fallback if Cloud Logging setup fails
            logger = logging.getLogger('BigQueryAlerts')
            logger.setLevel(logging.INFO)
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            logger.addHandler(handler)
            logger.warning(f"Cloud Logging setup failed, using standard logging: {e}")
        
    else:
        # Running locally - use file-based logging
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"bigquery_alerts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        logger = logging.getLogger('BigQueryAlerts')
        logger.setLevel(logging.INFO)
        
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # File handler
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

def is_execution_time_for_daily_alerts():
    """Check if current time is between 4:50AM and 5:49AM"""
    current_time = datetime.now().time()
    start_time = time(4, 50)
    end_time = time(5, 49)
    
    return start_time <= current_time <= end_time

def load_alerts_from_bigquery(client, resolution=None):
    query = """
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
    FROM `yotam-395120.peerplay.bigquery_alerts_to_slack_settings`
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
    if not creds_path:
        # Fallback to the default path if environment variable is not set
        creds_path = "/Users/guyzamir/Documents/Code/bigquery_alerts/json_key/yotam-395120-204239134151.json"
    
    logger.info(f"Looking for credentials at: {creds_path}")
    
    if not os.path.exists(creds_path):
        error_msg = f"Credentials file not found at: {creds_path}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)
    
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = creds_path
    
    # For local execution, also add Drive scopes
    try:
        credentials, project = google.auth.default(
            scopes=[
                "https://www.googleapis.com/auth/cloud-platform",
                "https://www.googleapis.com/auth/drive.readonly",
                "https://www.googleapis.com/auth/bigquery"
            ]
        )
        
        logger.info(f"✅ Using credentials from: {creds_path} with Drive and BigQuery scopes")
        return bigquery.Client(credentials=credentials, project=project)
        
    except Exception as e:
        logger.error(f"❌ Failed to create credentials with scopes: {str(e)}")
        logger.info("Falling back to default credentials without explicit scopes")
        return bigquery.Client()

class AlertProcessor:
    def __init__(self, resolution=None):
        self.logger = setup_logging()
        self.logger.info("Initializing Alert Processor")
        current_time = datetime.now()
        self.logger.info(f"Current execution time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            self.client = setup_credentials()
            self.alerts = load_alerts_from_bigquery(self.client, resolution)
            self.logger.info(f"Loaded {len(self.alerts)} active alerts from BigQuery for resolution {resolution}")
            
            # Test the history table exists and is accessible
            self.verify_history_table()
            
        except Exception as e:
            self.logger.error(f"Failed to initialize: {str(e)}")
            raise

    def verify_history_table(self):
        """Verify that the history table exists and is accessible"""
        try:
            test_query = """
            SELECT COUNT(*) as count 
            FROM `yotam-395120.peerplay.bigquery_alerts_execution_history` 
            WHERE 1=0
            """
            query_job = self.client.query(test_query)
            query_job.result()
            self.logger.info("History table verified and accessible")
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
        cooldown_query = """
        SELECT COUNT(*) as alerts_sent_today
        FROM `yotam-395120.peerplay.bigquery_alerts_execution_history`
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
            query_job = self.client.query(cooldown_query, job_config=job_config)
            results = query_job.result()
            
            for row in results:
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
        
        insert_query = """
        INSERT INTO `yotam-395120.peerplay.bigquery_alerts_execution_history`
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
            
            query_job = self.client.query(insert_query, job_config=job_config)
            query_job.result()  # Wait for the job to complete
            
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

        # Truncate SQL if too long
        sql_display = alert.sql
        if len(sql_display) > 1000:
            sql_display = sql_display[:1000] + "... (truncated)"

        # Add cooldown information for hourly alerts
        cooldown_text = ""
        if alert.resolution == 'H' and alert.max_hourly_alerts_per_day:
            cooldown_text = f"*Max alerts per day:*\n{alert.max_hourly_alerts_per_day}"
        else:
            cooldown_text = "*Max alerts per day:*\nUnlimited"

        message = {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"🚨 BigQuery Alert: {alert.name}",
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
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*SQL Query:*\n```{sql_display}```"
                    }
                },
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
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Data Query Link:*\n{alert.data_query_link or 'N/A'}"
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
            ]
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
            
            query_job = self.client.query(alert.sql)
            results = query_job.result()
            rows = list(results)
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
        processor = AlertProcessor(resolution)
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

if __name__ == "__main__":
    """
    Local execution entry point.
    This will be used when running the script directly on your laptop.
    """
    try:
        # Get resolution from command line arguments if specified
        resolution = sys.argv[1] if len(sys.argv) > 1 else None
        processor = AlertProcessor(resolution) 
        results = processor.process_all_alerts()
        processor.logger.info("Program completed successfully")
        print(json.dumps(results, indent=2))
    except Exception as e:
        logger = logging.getLogger('BigQueryAlerts')
        logger.error(f"Program failed with error: {str(e)}")
        sys.exit(1)