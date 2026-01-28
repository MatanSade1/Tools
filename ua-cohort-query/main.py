"""
UA Cohort Slack Query Tool

A Slack slash command tool that allows marketing media buyers to query the
UA cohort BigQuery table using natural language questions, powered by Claude Opus 4.5.

Usage:
    /uacohort Give me the total cost per month from Jan 2024 till today
"""

import os
import io
import csv
import json
import hmac
import hashlib
import time
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List

from flask import Flask, request, jsonify
from google.cloud import bigquery
from google.cloud import secretmanager
import requests

from query_generator import QueryGenerator
from query_validator import QueryValidator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "yotam-395120")
UA_COHORT_TABLE = "yotam-395120.peerplay.ua_cohort"

# Secret names
CLAUDE_API_KEY_SECRET = os.environ.get("CLAUDE_API_KEY_SECRET", "claude-api-key")
SLACK_BOT_TOKEN_SECRET = os.environ.get("SLACK_BOT_TOKEN_SECRET", "ua-cohort-slack-bot-token")
SLACK_SIGNING_SECRET_NAME = os.environ.get("SLACK_SIGNING_SECRET_NAME", "ua-cohort-slack-signing-secret")

# Response thresholds
MAX_ROWS_FOR_TABLE = 10

# Flask app
app = Flask(__name__)

# Cached clients
_bigquery_client = None
_query_generator = None
_query_validator = None
_slack_bot_token = None
_slack_signing_secret = None


def get_secret(secret_name: str, project_id: str = None) -> Optional[str]:
    """Retrieve a secret from Secret Manager."""
    try:
        if not project_id:
            project_id = PROJECT_ID
        
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        logger.error(f"Error accessing secret {secret_name}: {e}")
        # Fall back to environment variable
        env_var = secret_name.upper().replace("-", "_")
        return os.environ.get(env_var)


def get_bigquery_client() -> bigquery.Client:
    """Get or create BigQuery client instance."""
    global _bigquery_client
    if _bigquery_client is None:
        _bigquery_client = bigquery.Client(project=PROJECT_ID)
    return _bigquery_client


def get_query_generator() -> QueryGenerator:
    """Get or create QueryGenerator instance."""
    global _query_generator
    if _query_generator is None:
        api_key = get_secret(CLAUDE_API_KEY_SECRET)
        if not api_key:
            raise ValueError("Claude API key not found")
        _query_generator = QueryGenerator(api_key)
    return _query_generator


def get_query_validator() -> QueryValidator:
    """Get or create QueryValidator instance."""
    global _query_validator
    if _query_validator is None:
        _query_validator = QueryValidator(UA_COHORT_TABLE)
    return _query_validator


def get_slack_bot_token() -> str:
    """Get Slack bot token."""
    global _slack_bot_token
    if _slack_bot_token is None:
        _slack_bot_token = get_secret(SLACK_BOT_TOKEN_SECRET)
        if not _slack_bot_token:
            raise ValueError("Slack bot token not found")
    return _slack_bot_token


def get_slack_signing_secret() -> str:
    """Get Slack signing secret."""
    global _slack_signing_secret
    if _slack_signing_secret is None:
        _slack_signing_secret = get_secret(SLACK_SIGNING_SECRET_NAME)
        if not _slack_signing_secret:
            raise ValueError("Slack signing secret not found")
    return _slack_signing_secret


def verify_slack_request(request_body: bytes, timestamp: str, signature: str) -> bool:
    """Verify that the request came from Slack."""
    try:
        signing_secret = get_slack_signing_secret()
        
        # Check timestamp to prevent replay attacks
        if abs(time.time() - float(timestamp)) > 60 * 5:
            logger.warning("Slack request timestamp too old")
            return False
        
        # Create the signature base string
        sig_basestring = f"v0:{timestamp}:{request_body.decode('utf-8')}"
        
        # Create the signature
        my_signature = 'v0=' + hmac.new(
            signing_secret.encode('utf-8'),
            sig_basestring.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(my_signature, signature)
    except Exception as e:
        logger.error(f"Error verifying Slack request: {e}")
        return False


def execute_query(sql: str) -> Tuple[List[Dict], int]:
    """Execute a SQL query and return results."""
    client = get_bigquery_client()
    
    logger.info(f"Executing query: {sql}")
    
    query_job = client.query(sql)
    results = query_job.result()
    
    # Convert to list of dicts
    rows = []
    for row in results:
        rows.append(dict(row))
    
    return rows, len(rows)


def format_single_value(value: Any, column_name: str) -> str:
    """Format a single value result."""
    # Format based on column name hints
    if isinstance(value, float):
        if 'roas' in column_name.lower() or 'pct' in column_name.lower() or 'percent' in column_name.lower():
            return f"{value * 100:.2f}%"
        elif 'cost' in column_name.lower() or 'revenue' in column_name.lower() or 'cpi' in column_name.lower() or 'cpa' in column_name.lower():
            return f"${value:,.2f}"
        else:
            return f"{value:,.2f}"
    elif isinstance(value, int):
        return f"{value:,}"
    else:
        return str(value)


def format_table_response(rows: List[Dict]) -> str:
    """Format rows as a Slack code block table."""
    if not rows:
        return "No results found."
    
    # Get column names
    columns = list(rows[0].keys())
    
    # Calculate column widths
    col_widths = {}
    for col in columns:
        col_widths[col] = max(
            len(str(col)),
            max(len(str(row.get(col, ''))) for row in rows)
        )
    
    # Build header
    header = " | ".join(str(col).ljust(col_widths[col]) for col in columns)
    separator = "-+-".join("-" * col_widths[col] for col in columns)
    
    # Build rows
    row_lines = []
    for row in rows:
        row_str = " | ".join(
            str(row.get(col, '')).ljust(col_widths[col]) 
            for col in columns
        )
        row_lines.append(row_str)
    
    table = f"```\n{header}\n{separator}\n" + "\n".join(row_lines) + "\n```"
    return table


def create_csv_content(rows: List[Dict]) -> str:
    """Create CSV content from rows."""
    if not rows:
        return ""
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def send_slack_message(channel: str, text: str, thread_ts: str = None) -> bool:
    """Send a message to Slack."""
    try:
        token = get_slack_bot_token()
        
        response = requests.post(
            "https://slack.com/api/chat.postMessage",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json={
                "channel": channel,
                "text": text,
                "thread_ts": thread_ts
            },
            timeout=30
        )
        
        result = response.json()
        if not result.get("ok"):
            logger.error(f"Slack API error: {result.get('error')}")
            return False
        return True
    except Exception as e:
        logger.error(f"Error sending Slack message: {e}")
        return False


def upload_csv_to_slack(channel: str, csv_content: str, filename: str, 
                        initial_comment: str = None, thread_ts: str = None) -> bool:
    """Upload a CSV file to Slack."""
    try:
        token = get_slack_bot_token()
        
        response = requests.post(
            "https://slack.com/api/files.upload",
            headers={
                "Authorization": f"Bearer {token}"
            },
            data={
                "channels": channel,
                "filename": filename,
                "filetype": "csv",
                "initial_comment": initial_comment or "",
                "thread_ts": thread_ts or ""
            },
            files={
                "file": (filename, csv_content.encode('utf-8'), "text/csv")
            },
            timeout=60
        )
        
        result = response.json()
        if not result.get("ok"):
            logger.error(f"Slack file upload error: {result.get('error')}")
            return False
        return True
    except Exception as e:
        logger.error(f"Error uploading file to Slack: {e}")
        return False


def process_query(question: str, channel: str, user_id: str, response_url: str) -> None:
    """Process a user query and send results to Slack."""
    try:
        # Generate SQL query using Claude
        generator = get_query_generator()
        sql_query, explanation = generator.generate_query(question)
        
        if not sql_query:
            send_delayed_response(response_url, 
                f"I couldn't understand your question. Please try rephrasing it.\n\nDetails: {explanation}")
            return
        
        # Validate the query
        validator = get_query_validator()
        is_valid, validation_error = validator.validate(sql_query)
        
        if not is_valid:
            send_delayed_response(response_url,
                f"The generated query failed security validation: {validation_error}\n\n"
                f"Please try rephrasing your question to focus on SELECT queries on the UA cohort table.")
            return
        
        # Execute the query
        try:
            rows, row_count = execute_query(sql_query)
        except Exception as e:
            logger.error(f"Query execution error: {e}")
            send_delayed_response(response_url,
                f"Error executing query: {str(e)}\n\n"
                f"Generated SQL:\n```{sql_query}```")
            return
        
        # Format and send response
        if row_count == 0:
            send_delayed_response(response_url, "No results found for your query.")
        elif row_count == 1 and len(rows[0]) == 1:
            # Single value - send as message
            col_name = list(rows[0].keys())[0]
            value = rows[0][col_name]
            formatted_value = format_single_value(value, col_name)
            send_delayed_response(response_url,
                f"*{col_name}*: {formatted_value}\n\n"
                f"_Query:_ `{sql_query}`")
        elif row_count <= MAX_ROWS_FOR_TABLE:
            # Small result set - format as table
            table = format_table_response(rows)
            send_delayed_response(response_url,
                f"*Results ({row_count} rows):*\n{table}\n\n"
                f"_Query:_ `{sql_query}`")
        else:
            # Large result set - upload as CSV
            csv_content = create_csv_content(rows)
            filename = f"ua_cohort_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            # First send acknowledgment
            send_delayed_response(response_url,
                f"Found {row_count} rows. Uploading CSV file...\n\n"
                f"_Query:_ `{sql_query}`")
            
            # Then upload file
            upload_csv_to_slack(
                channel=channel,
                csv_content=csv_content,
                filename=filename,
                initial_comment=f"Query results: {row_count} rows"
            )
    
    except Exception as e:
        logger.exception(f"Error processing query: {e}")
        send_delayed_response(response_url,
            f"An error occurred while processing your query: {str(e)}")


def send_delayed_response(response_url: str, text: str) -> bool:
    """Send a delayed response to Slack using the response URL."""
    try:
        response = requests.post(
            response_url,
            json={
                "response_type": "in_channel",
                "text": text
            },
            timeout=30
        )
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Error sending delayed response: {e}")
        return False


# Flask routes

@app.route("/", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "service": "ua-cohort-query"}), 200


@app.route("/slack/command", methods=["POST"])
def handle_slash_command():
    """Handle Slack slash command."""
    try:
        # Get raw body for signature verification
        raw_body = request.get_data()
        
        # Verify Slack request
        timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
        signature = request.headers.get("X-Slack-Signature", "")
        
        # Skip verification in development mode
        if os.environ.get("SKIP_SLACK_VERIFICATION") != "true":
            if not verify_slack_request(raw_body, timestamp, signature):
                logger.warning("Invalid Slack request signature")
                return jsonify({"error": "Invalid request signature"}), 401
        
        # Parse form data
        user_id = request.form.get("user_id")
        channel_id = request.form.get("channel_id")
        text = request.form.get("text", "").strip()
        response_url = request.form.get("response_url")
        
        logger.info(f"Received query from user {user_id} in channel {channel_id}: {text}")
        
        if not text:
            return jsonify({
                "response_type": "ephemeral",
                "text": "Please provide a question. Example: `/uacohort Give me the total cost per month from Jan 2024`"
            }), 200
        
        # Acknowledge immediately (Slack requires response within 3 seconds)
        # Process query in background
        import threading
        thread = threading.Thread(
            target=process_query,
            args=(text, channel_id, user_id, response_url)
        )
        thread.start()
        
        return jsonify({
            "response_type": "in_channel",
            "text": f"Processing your query: _{text}_\n\nPlease wait..."
        }), 200
    
    except Exception as e:
        logger.exception(f"Error handling slash command: {e}")
        return jsonify({
            "response_type": "ephemeral",
            "text": f"An error occurred: {str(e)}"
        }), 500


@app.route("/test", methods=["GET", "POST"])
def test_query():
    """Test endpoint for development."""
    try:
        if request.method == "GET":
            question = request.args.get("q", "Give me the total cost for January 2024")
        else:
            data = request.get_json() or {}
            question = data.get("question", "Give me the total cost for January 2024")
        
        logger.info(f"Test query: {question}")
        
        # Generate SQL
        generator = get_query_generator()
        sql_query, explanation = generator.generate_query(question)
        
        if not sql_query:
            return jsonify({
                "status": "error",
                "error": explanation
            }), 400
        
        # Validate
        validator = get_query_validator()
        is_valid, validation_error = validator.validate(sql_query)
        
        if not is_valid:
            return jsonify({
                "status": "error",
                "error": validation_error,
                "generated_sql": sql_query
            }), 400
        
        # Execute
        rows, row_count = execute_query(sql_query)
        
        return jsonify({
            "status": "success",
            "question": question,
            "sql": sql_query,
            "explanation": explanation,
            "row_count": row_count,
            "results": rows[:100]  # Limit to first 100 rows for testing
        }), 200
    
    except Exception as e:
        logger.exception(f"Test query error: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


if __name__ == "__main__":
    # Run locally for testing
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)



