"""
MAX User-Level Ad Revenue Collector

Cloud Run service that fetches user-level ad revenue data from AppLovin MAX API
and stores it in BigQuery. Runs daily at 10 AM UTC via Cloud Scheduler.

Process:
1. Delete data from last 2 days in BigQuery
2. Fetch iOS data for last 2 days from MAX API
3. Fetch Android data for last 2 days from MAX API
4. Insert all records into BigQuery
"""

import os
import csv
import io
import logging
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

import requests
from flask import Flask, jsonify, request
from google.cloud import bigquery
from google.cloud import secretmanager
from google.cloud.exceptions import NotFound

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "yotam-395120")
BIGQUERY_TABLE = os.environ.get("BIGQUERY_TABLE", "yotam-395120.peerplay.max_revenue_data")
MAX_API_KEY_SECRET = os.environ.get("MAX_API_KEY_SECRET", "max-api-key")
MAX_API_ENDPOINT = "https://r.applovin.com/max/userAdRevenueReport"

# Platform configurations
PLATFORMS = [
    {
        "name": "ios",
        "platform": "ios",
        "application": "com.peerplay.megamerge",
        "store_id": "6459056553"
    },
    {
        "name": "android",
        "platform": "android",
        "application": "com.peerplay.megamerge",
        "store_id": "com.peerplay.megamerge"
    }
]

# Days to fetch (and delete)
DAYS_TO_FETCH = 2

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5

# Flask app
app = Flask(__name__)


def get_api_key() -> str:
    """
    Retrieve the MAX API key from Secret Manager.
    Falls back to environment variable if Secret Manager fails.
    """
    # First try environment variable (for local testing)
    api_key = os.environ.get("MAX_API_KEY")
    if api_key:
        logger.info("Using MAX API key from environment variable")
        return api_key
    
    # Try Secret Manager
    try:
        client = secretmanager.SecretManagerServiceClient()
        secret_name = f"projects/{PROJECT_ID}/secrets/{MAX_API_KEY_SECRET}/versions/latest"
        response = client.access_secret_version(request={"name": secret_name})
        api_key = response.payload.data.decode("UTF-8")
        logger.info("Successfully retrieved MAX API key from Secret Manager")
        return api_key
    except Exception as e:
        logger.error(f"Failed to retrieve API key from Secret Manager: {e}")
        raise ValueError(f"Could not retrieve MAX API key: {e}")


def get_bigquery_client() -> bigquery.Client:
    """Get BigQuery client instance."""
    return bigquery.Client(project=PROJECT_ID)


def get_date_range() -> Tuple[str, str]:
    """
    Calculate the date range for the last 2 days.
    Returns (start_date, end_date) in YYYY-MM-DD format.
    """
    today = datetime.utcnow().date()
    end_date = today - timedelta(days=1)  # Yesterday
    start_date = today - timedelta(days=DAYS_TO_FETCH)  # 2 days ago
    
    return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")


def delete_existing_data(client: bigquery.Client, start_date: str, end_date: str) -> int:
    """
    Delete existing data for the date range from BigQuery.
    Uses partition-aware delete for efficiency.
    
    Returns the number of rows deleted.
    """
    # Parse table reference
    table_parts = BIGQUERY_TABLE.split(".")
    if len(table_parts) != 3:
        raise ValueError(f"Invalid table format: {BIGQUERY_TABLE}. Expected project.dataset.table")
    
    project, dataset, table = table_parts
    
    # Delete query - uses partition pruning on date column
    delete_query = f"""
    DELETE FROM `{project}.{dataset}.{table}`
    WHERE DATE(date) >= '{start_date}'
      AND DATE(date) <= '{end_date}'
    """
    
    logger.info(f"Deleting data from {start_date} to {end_date}")
    logger.info(f"Query: {delete_query}")
    
    try:
        query_job = client.query(delete_query)
        query_job.result()  # Wait for completion
        
        rows_deleted = query_job.num_dml_affected_rows or 0
        logger.info(f"Successfully deleted {rows_deleted} rows")
        return rows_deleted
    except NotFound:
        logger.warning(f"Table {BIGQUERY_TABLE} not found. Will create on first insert.")
        return 0
    except Exception as e:
        logger.error(f"Error deleting data: {e}")
        raise


def fetch_max_api_data(
    api_key: str,
    platform_config: Dict,
    start_date: str,
    end_date: str
) -> List[Dict]:
    """
    Fetch user-level ad revenue data from MAX API for a specific platform.
    
    The MAX User-Level API requires a single date per request, so we loop through each day.
    The API returns a JSON with a URL to the actual CSV file.
    
    Returns a list of dictionaries, each representing a row of data.
    """
    platform_name = platform_config["name"]
    logger.info(f"Fetching {platform_name} data from {start_date} to {end_date}")
    
    all_records = []
    
    # Parse dates and iterate through each day
    from datetime import datetime as dt
    start = dt.strptime(start_date, "%Y-%m-%d")
    end = dt.strptime(end_date, "%Y-%m-%d")
    
    current = start
    while current <= end:
        date_str = current.strftime("%Y-%m-%d")
        logger.info(f"Fetching {platform_name} data for {date_str}")
        
        # Use store_id only (API doesn't allow both store_id and application)
        params = {
            "api_key": api_key,
            "platform": platform_config["platform"],
            "store_id": platform_config["store_id"],
            "date": date_str,
            "aggregated": "false"
        }
        
        for attempt in range(MAX_RETRIES):
            try:
                logger.info(f"API request attempt {attempt + 1}/{MAX_RETRIES} for {platform_name} on {date_str}")
                
                response = requests.get(
                    MAX_API_ENDPOINT,
                    params=params,
                    timeout=60
                )
                
                if response.status_code == 200:
                    # Parse JSON response to get CSV URL
                    try:
                        json_response = response.json()
                        logger.info(f"API Response: status={json_response.get('status')}")
                        
                        if json_response.get("status") != 200:
                            logger.warning(f"API returned status {json_response.get('status')} for {platform_name} on {date_str}")
                            break
                        
                        # Get the CSV URL (prefer ad_revenue_report_url for complete data)
                        csv_url = json_response.get("ad_revenue_report_url") or json_response.get("url")
                        
                        if not csv_url:
                            logger.warning(f"No CSV URL in response for {platform_name} on {date_str}")
                            break
                        
                        # Download the CSV file
                        logger.info(f"Downloading CSV from S3...")
                        csv_response = requests.get(csv_url, timeout=300)
                        
                        if csv_response.status_code == 200:
                            csv_content = csv_response.text
                            if csv_content.strip():
                                records = parse_csv_response(csv_content, platform_name)
                                all_records.extend(records)
                                logger.info(f"Fetched {len(records)} records for {platform_name} on {date_str}")
                            else:
                                logger.info(f"No data for {platform_name} on {date_str}")
                        else:
                            logger.error(f"Failed to download CSV: {csv_response.status_code}")
                        
                        break  # Success, move to next day
                        
                    except ValueError as e:
                        logger.error(f"Invalid JSON response: {e}")
                        logger.error(f"Response text: {response.text[:500]}")
                        break
                
                elif response.status_code == 429:
                    wait_time = RETRY_DELAY_SECONDS * (attempt + 1) * 2
                    logger.warning(f"Rate limited. Waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                
                else:
                    logger.error(f"API error for {platform_name} on {date_str}: {response.status_code} - {response.text[:500]}")
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAY_SECONDS * (attempt + 1))
                        continue
                    break
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Request timeout for {platform_name} on {date_str}, attempt {attempt + 1}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY_SECONDS * (attempt + 1))
                    continue
                break
            
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error for {platform_name} on {date_str}: {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY_SECONDS * (attempt + 1))
                    continue
                break
        
        # Move to next day
        current += timedelta(days=1)
    
    logger.info(f"Total records fetched for {platform_name}: {len(all_records)}")
    return all_records


def parse_csv_response(csv_content: str, platform_name: str) -> List[Dict]:
    """
    Parse CSV response from MAX API into list of dictionaries.
    Maps CSV columns to BigQuery schema.
    
    Expected MAX API columns (non-aggregated):
    - Date, Ad Unit ID, Ad Unit Name, Placement, IDFA, IDFV, User Id, Revenue
    - Ad Format, Ad Placement, Country, Device Type, Network, Waterfall, Custom Data
    """
    records = []
    
    # Log first 500 chars of response to see column names
    logger.info(f"CSV Response preview: {csv_content[:500]}")
    
    # Use StringIO to read CSV from string
    csv_file = io.StringIO(csv_content)
    reader = csv.DictReader(csv_file)
    
    # Log available columns
    if reader.fieldnames:
        logger.info(f"Available columns: {reader.fieldnames}")
    
    for row in reader:
        try:
            # Handle the date field
            # MAX API uses "Date" column with format like "2019-07-29 15:53:07.39"
            date_str = row.get("Date", "")
            date_value = None
            
            if date_str:
                try:
                    # Try parsing with milliseconds: "2019-07-29 15:53:07.39"
                    base_str = date_str.split(".")[0]
                    dt = datetime.strptime(base_str, "%Y-%m-%d %H:%M:%S")
                    if "." in date_str:
                        ms_part = date_str.split(".")[1]
                        ms_part = ms_part.ljust(6, '0')[:6]
                        dt = dt.replace(microsecond=int(ms_part))
                    date_value = dt.isoformat()
                except ValueError:
                    try:
                        # Try date only format
                        dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
                        date_value = dt.isoformat()
                    except ValueError:
                        logger.warning(f"Could not parse date: {date_str}")
                        date_value = None
            
            # Parse revenue as float
            revenue_str = row.get("Revenue", "0")
            try:
                revenue = float(revenue_str) if revenue_str else 0.0
            except ValueError:
                revenue = 0.0
            
            record = {
                "date": date_value,
                "ad_unit_id": row.get("Ad Unit ID", ""),
                "ad_unit_name": row.get("Ad Unit Name", ""),
                "waterfall": row.get("Waterfall", ""),
                "ad_format": row.get("Ad Format", ""),
                "placement": row.get("Placement", ""),
                "country": row.get("Country", ""),
                "device_type": row.get("Device Type", ""),
                "idfa": row.get("IDFA", ""),
                "idfv": row.get("IDFV", ""),
                "user_id": row.get("User Id", ""),  # Note: "User Id" with lowercase 'd'
                "revenue": revenue,
                "ad_placement": row.get("Ad Placement", ""),
                "platform": platform_name
            }
            
            # Only add records with valid dates
            if date_value:
                records.append(record)
            else:
                logger.warning(f"Skipping record with invalid/missing date: {row}")
                
        except Exception as e:
            logger.warning(f"Error parsing row: {e}. Row: {row}")
            continue
    
    return records


def ensure_table_exists(client: bigquery.Client):
    """
    Create the BigQuery table if it doesn't exist.
    Uses day partitioning on the date column.
    """
    table_parts = BIGQUERY_TABLE.split(".")
    if len(table_parts) != 3:
        raise ValueError(f"Invalid table format: {BIGQUERY_TABLE}")
    
    project, dataset_id, table_id = table_parts
    
    # Check if dataset exists, create if not
    dataset_ref = client.dataset(dataset_id, project=project)
    try:
        client.get_dataset(dataset_ref)
    except NotFound:
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = "US"
        client.create_dataset(dataset, exists_ok=True)
        logger.info(f"Created dataset {dataset_id}")
    
    # Check if table exists
    table_ref = dataset_ref.table(table_id)
    try:
        client.get_table(table_ref)
        logger.info(f"Table {BIGQUERY_TABLE} already exists")
        return
    except NotFound:
        pass
    
    # Create table with schema and partitioning
    schema = [
        bigquery.SchemaField("date", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("ad_unit_id", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("ad_unit_name", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("waterfall", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("ad_format", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("placement", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("country", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("device_type", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("idfa", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("idfv", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("user_id", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("revenue", "FLOAT", mode="NULLABLE"),
        bigquery.SchemaField("ad_placement", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("platform", "STRING", mode="NULLABLE"),
    ]
    
    table = bigquery.Table(table_ref, schema=schema)
    
    # Configure day partitioning on date column
    table.time_partitioning = bigquery.TimePartitioning(
        type_=bigquery.TimePartitioningType.DAY,
        field="date"
    )
    
    table = client.create_table(table)
    logger.info(f"Created table {BIGQUERY_TABLE} with day partitioning on 'date' column")


def insert_records(client: bigquery.Client, records: List[Dict]) -> int:
    """
    Insert records into BigQuery using streaming inserts.
    
    Returns the number of records inserted.
    """
    if not records:
        logger.info("No records to insert")
        return 0
    
    # Ensure table exists
    ensure_table_exists(client)
    
    # Prepare rows for insertion (remove platform field as it's not in the table)
    rows_to_insert = []
    for record in records:
        row = {k: v for k, v in record.items() if k != "platform"}
        rows_to_insert.append(row)
    
    # Insert in batches (BigQuery streaming insert limit is 10000 rows per request)
    batch_size = 5000
    total_inserted = 0
    errors_list = []
    
    for i in range(0, len(rows_to_insert), batch_size):
        batch = rows_to_insert[i:i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(rows_to_insert) + batch_size - 1) // batch_size
        
        logger.info(f"Inserting batch {batch_num}/{total_batches} ({len(batch)} records)")
        
        table_parts = BIGQUERY_TABLE.split(".")
        table_ref = client.dataset(table_parts[1], project=table_parts[0]).table(table_parts[2])
        
        errors = client.insert_rows_json(table_ref, batch)
        
        if errors:
            logger.error(f"Errors inserting batch {batch_num}: {errors[:5]}")  # Log first 5 errors
            errors_list.extend(errors)
        else:
            total_inserted += len(batch)
    
    if errors_list:
        logger.warning(f"Completed with {len(errors_list)} errors. Successfully inserted {total_inserted} records.")
    else:
        logger.info(f"Successfully inserted {total_inserted} records")
    
    return total_inserted


def run_collection() -> Dict:
    """
    Main collection process:
    1. Delete data from last 2 days
    2. Fetch iOS data for last 2 days
    3. Fetch Android data for last 2 days
    4. Insert all records into BigQuery
    
    Returns a summary of the operation.
    """
    start_time = datetime.utcnow()
    logger.info("=" * 60)
    logger.info("Starting MAX Revenue Collection")
    logger.info("=" * 60)
    
    try:
        # Get API key
        api_key = get_api_key()
        
        # Get BigQuery client
        bq_client = get_bigquery_client()
        
        # Calculate date range
        start_date, end_date = get_date_range()
        logger.info(f"Date range: {start_date} to {end_date}")
        
        # Step 1: Delete existing data for the date range
        logger.info("-" * 40)
        logger.info("Step 1: Deleting existing data")
        logger.info("-" * 40)
        rows_deleted = delete_existing_data(bq_client, start_date, end_date)
        
        # Step 2 & 3: Fetch data from MAX API for both platforms
        all_records = []
        platform_stats = {}
        
        for platform_config in PLATFORMS:
            platform_name = platform_config["name"]
            logger.info("-" * 40)
            logger.info(f"Step: Fetching {platform_name.upper()} data")
            logger.info("-" * 40)
            
            try:
                records = fetch_max_api_data(
                    api_key=api_key,
                    platform_config=platform_config,
                    start_date=start_date,
                    end_date=end_date
                )
                all_records.extend(records)
                platform_stats[platform_name] = {
                    "records_fetched": len(records),
                    "status": "success"
                }
            except Exception as e:
                logger.error(f"Failed to fetch {platform_name} data: {e}")
                platform_stats[platform_name] = {
                    "records_fetched": 0,
                    "status": "error",
                    "error": str(e)
                }
        
        # Step 4: Insert records into BigQuery
        logger.info("-" * 40)
        logger.info("Step 4: Inserting records into BigQuery")
        logger.info("-" * 40)
        rows_inserted = insert_records(bq_client, all_records)
        
        # Calculate duration
        end_time = datetime.utcnow()
        duration_seconds = (end_time - start_time).total_seconds()
        
        # Build result summary
        result = {
            "status": "success",
            "timestamp": start_time.isoformat(),
            "date_range": {
                "start": start_date,
                "end": end_date
            },
            "rows_deleted": rows_deleted,
            "rows_inserted": rows_inserted,
            "total_records_fetched": len(all_records),
            "platform_stats": platform_stats,
            "duration_seconds": duration_seconds
        }
        
        logger.info("=" * 60)
        logger.info("Collection completed successfully")
        logger.info(f"Summary: Deleted {rows_deleted} rows, Inserted {rows_inserted} rows")
        logger.info(f"Duration: {duration_seconds:.2f} seconds")
        logger.info("=" * 60)
        
        return result
        
    except Exception as e:
        end_time = datetime.utcnow()
        duration_seconds = (end_time - start_time).total_seconds()
        
        error_result = {
            "status": "error",
            "timestamp": start_time.isoformat(),
            "error": str(e),
            "error_type": type(e).__name__,
            "duration_seconds": duration_seconds
        }
        
        logger.error("=" * 60)
        logger.error(f"Collection FAILED: {e}")
        logger.error(f"Duration: {duration_seconds:.2f} seconds")
        logger.error("=" * 60)
        
        return error_result


# Flask routes

@app.route("/", methods=["GET", "POST"])
def handle_request():
    """
    Main endpoint for Cloud Scheduler.
    Accepts both GET (for testing) and POST (from Cloud Scheduler).
    """
    logger.info(f"Received {request.method} request")
    
    try:
        result = run_collection()
        
        if result.get("status") == "success":
            return jsonify(result), 200
        else:
            # Return 500 for errors so Cloud Scheduler can retry
            return jsonify(result), 500
            
    except Exception as e:
        logger.exception(f"Unhandled error: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__
        }), 500


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for Cloud Run."""
    return jsonify({"status": "healthy"}), 200


@app.route("/test", methods=["GET"])
def test_endpoint():
    """
    Test endpoint that validates configuration without running collection.
    Useful for debugging deployment issues.
    """
    try:
        # Test API key retrieval
        api_key = get_api_key()
        api_key_preview = api_key[:8] + "..." if len(api_key) > 8 else api_key
        
        # Test BigQuery connection
        bq_client = get_bigquery_client()
        
        # Calculate date range
        start_date, end_date = get_date_range()
        
        return jsonify({
            "status": "ok",
            "config": {
                "project_id": PROJECT_ID,
                "bigquery_table": BIGQUERY_TABLE,
                "max_api_key_preview": api_key_preview,
                "date_range": {
                    "start": start_date,
                    "end": end_date
                },
                "platforms": [p["name"] for p in PLATFORMS]
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__
        }), 500


if __name__ == "__main__":
    # Run locally for testing
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)

