"""BigQuery client utilities for storing and querying Mixpanel events."""
from typing import List, Dict, Optional
from google.cloud import bigquery
from google.cloud.exceptions import NotFound
import json
from datetime import datetime, timedelta, date
from shared.config import get_config


def get_bigquery_client():
    """Get BigQuery client instance."""
    return bigquery.Client(project=get_config()["gcp_project_id"])


def ensure_table_exists():
    """Create BigQuery table if it doesn't exist."""
    client = get_bigquery_client()
    config = get_config()
    dataset_id = config["bigquery_dataset"]
    table_id = config["bigquery_table"]
    
    dataset_ref = client.dataset(dataset_id)
    
    # Create dataset if it doesn't exist
    try:
        client.get_dataset(dataset_ref)
    except NotFound:
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = "US"
        dataset = client.create_dataset(dataset, exists_ok=True)
        print(f"Created dataset {dataset_id}")
    
    # Create table if it doesn't exist
    table_ref = dataset_ref.table(table_id)
    try:
        client.get_table(table_ref)
        print(f"Table {table_id} already exists")
    except NotFound:
        schema = [
            bigquery.SchemaField("event_timestamp", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("inserted_at", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("event_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("properties", "JSON", mode="NULLABLE"),
            bigquery.SchemaField("distinct_id", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("event_id", "STRING", mode="NULLABLE"),
        ]
        table = bigquery.Table(table_ref, schema=schema)
        table = client.create_table(table)
        print(f"Created table {table_id}")


def insert_events(events: List[Dict]):
    """
    Insert events into BigQuery.
    
    Args:
        events: List of event dictionaries with keys:
            - event_timestamp: ISO format timestamp
            - event_name: Event name
            - properties: Dict of event properties
            - distinct_id: User/distinct ID
            - event_id: Unique event identifier
    """
    if not events:
        return
    
    client = get_bigquery_client()
    config = get_config()
    dataset_id = config["bigquery_dataset"]
    table_id = config["bigquery_table"]
    
    ensure_table_exists()
    
    rows_to_insert = []
    inserted_at = datetime.utcnow()
    
    for event in events:
        row = {
            "event_timestamp": event.get("event_timestamp"),
            "inserted_at": inserted_at.isoformat(),
            "event_name": event.get("event_name"),
            "properties": json.dumps(event.get("properties", {})),
            "distinct_id": event.get("distinct_id"),
            "event_id": event.get("event_id"),
        }
        rows_to_insert.append(row)
    
    table_ref = client.dataset(dataset_id).table(table_id)
    errors = client.insert_rows_json(table_ref, rows_to_insert)
    
    if errors:
        raise Exception(f"Error inserting rows: {errors}")
    
    print(f"Successfully inserted {len(rows_to_insert)} events")


def query_events_by_minute(
    event_name: str,
    start_time: datetime,
    end_time: datetime
) -> List[Dict]:
    """
    Query events grouped by minute.
    
    Args:
        event_name: Name of the event to query
        start_time: Start of time window
        end_time: End of time window
    
    Returns:
        List of dicts with keys: minute_timestamp, event_count, sample_events
    """
    client = get_bigquery_client()
    config = get_config()
    dataset_id = config["bigquery_dataset"]
    table_id = config["bigquery_table"]
    
    query = f"""
    SELECT
        TIMESTAMP_TRUNC(event_timestamp, MINUTE) as minute_timestamp,
        COUNT(*) as event_count,
        ARRAY_AGG(
            STRUCT(
                event_id,
                distinct_id,
                properties
            )
            LIMIT 3
        ) as sample_events
    FROM `{config["gcp_project_id"]}.{dataset_id}.{table_id}`
    WHERE event_name = @event_name
        AND event_timestamp >= @start_time
        AND event_timestamp < @end_time
    GROUP BY minute_timestamp
    ORDER BY minute_timestamp DESC
    """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("event_name", "STRING", event_name),
            bigquery.ScalarQueryParameter("start_time", "TIMESTAMP", start_time),
            bigquery.ScalarQueryParameter("end_time", "TIMESTAMP", end_time),
        ]
    )
    
    query_job = client.query(query, job_config=job_config)
    results = query_job.result()
    
    return [
        {
            "minute_timestamp": row.minute_timestamp,
            "event_count": row.event_count,
            "sample_events": [
                {
                    "event_id": e.event_id,
                    "distinct_id": e.distinct_id,
                    "properties": json.loads(e.properties) if e.properties else {}
                }
                for e in row.sample_events
            ]
        }
        for row in results
    ]


def ensure_rt_table_exists():
    """Create RT BigQuery table if it doesn't exist."""
    client = get_bigquery_client()
    config = get_config()
    dataset_id = config.get("rt_mp_dataset", config["bigquery_dataset"])
    table_id = config.get("rt_mp_table", "rt_mp_events")
    
    dataset_ref = client.dataset(dataset_id)
    
    # Create dataset if it doesn't exist
    try:
        client.get_dataset(dataset_ref)
    except NotFound:
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = "US"
        dataset = client.create_dataset(dataset, exists_ok=True)
        print(f"Created dataset {dataset_id}")
    
    # Create table if it doesn't exist
    table_ref = dataset_ref.table(table_id)
    try:
        client.get_table(table_ref)
        print(f"Table {table_id} already exists")
    except NotFound:
        schema = [
            bigquery.SchemaField("event_timestamp", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("inserted_at", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("event_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("properties", "JSON", mode="NULLABLE"),
            bigquery.SchemaField("distinct_id", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("event_id", "STRING", mode="NULLABLE"),
        ]
        table = bigquery.Table(table_ref, schema=schema)
        table = client.create_table(table)
        print(f"Created table {table_id}")


def insert_events_to_rt_table(events: List[Dict]):
    """
    Insert events into RT BigQuery table (rt_mp_events).
    
    Args:
        events: List of event dictionaries with keys:
            - event_timestamp: ISO format timestamp
            - event_name: Event name
            - properties: Dict of event properties
            - distinct_id: User/distinct ID
            - event_id: Unique event identifier
    """
    if not events:
        return
    
    client = get_bigquery_client()
    config = get_config()
    dataset_id = config.get("rt_mp_dataset", config["bigquery_dataset"])
    table_id = config.get("rt_mp_table", "rt_mp_events")
    
    ensure_rt_table_exists()
    
    rows_to_insert = []
    inserted_at = datetime.utcnow()
    
    for event in events:
        row = {
            "event_timestamp": event.get("event_timestamp"),
            "inserted_at": inserted_at.isoformat(),
            "event_name": event.get("event_name"),
            "properties": json.dumps(event.get("properties", {})),
            "distinct_id": event.get("distinct_id"),
            "event_id": event.get("event_id"),
        }
        rows_to_insert.append(row)
    
    table_ref = client.dataset(dataset_id).table(table_id)
    errors = client.insert_rows_json(table_ref, rows_to_insert)
    
    if errors:
        raise Exception(f"Error inserting rows: {errors}")
    
    print(f"Successfully inserted {len(rows_to_insert)} events into {dataset_id}.{table_id}")


def query_events_by_hour(
    event_name: str,
    start_time: datetime,
    end_time: datetime
) -> int:
    """
    Query events and return count for the specified time window.
    
    Args:
        event_name: Name of the event to query
        start_time: Start of time window
        end_time: End of time window
    
    Returns:
        Count of events in the time window
    """
    client = get_bigquery_client()
    config = get_config()
    dataset_id = config.get("rt_mp_dataset", config["bigquery_dataset"])
    table_id = config.get("rt_mp_table", "rt_mp_events")
    
    query = f"""
    SELECT COUNT(*) as event_count
    FROM `{config["gcp_project_id"]}.{dataset_id}.{table_id}`
    WHERE event_name = @event_name
        AND event_timestamp >= @start_time
        AND event_timestamp < @end_time
    """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("event_name", "STRING", event_name),
            bigquery.ScalarQueryParameter("start_time", "TIMESTAMP", start_time),
            bigquery.ScalarQueryParameter("end_time", "TIMESTAMP", end_time),
        ]
    )
    
    query_job = client.query(query, job_config=job_config)
    results = query_job.result()
    
    # Get the count from the first (and only) row
    for row in results:
        return row.event_count
    
    return 0


def query_distinct_users_by_hour(
    event_name: str,
    start_time: datetime,
    end_time: datetime
) -> int:
    """
    Query distinct users who had a specific event in the time window.
    
    Args:
        event_name: Name of the event to query
        start_time: Start of time window
        end_time: End of time window
    
    Returns:
        Count of distinct users who had the event
    """
    client = get_bigquery_client()
    config = get_config()
    dataset_id = config.get("rt_mp_dataset", config["bigquery_dataset"])
    table_id = config.get("rt_mp_table", "rt_mp_events")
    
    query = f"""
    SELECT COUNT(DISTINCT distinct_id) as distinct_user_count
    FROM `{config["gcp_project_id"]}.{dataset_id}.{table_id}`
    WHERE event_name = @event_name
        AND event_timestamp >= @start_time
        AND event_timestamp < @end_time
        AND distinct_id IS NOT NULL
    """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("event_name", "STRING", event_name),
            bigquery.ScalarQueryParameter("start_time", "TIMESTAMP", start_time),
            bigquery.ScalarQueryParameter("end_time", "TIMESTAMP", end_time),
        ]
    )
    
    query_job = client.query(query, job_config=job_config)
    results = query_job.result()
    
    # Get the count from the first (and only) row
    for row in results:
        return row.distinct_user_count
    
    return 0


def query_total_active_users_by_hour(
    start_time: datetime,
    end_time: datetime
) -> int:
    """
    Query distinct users who had ANY event in the time window (total active users).
    
    Args:
        start_time: Start of time window
        end_time: End of time window
    
    Returns:
        Count of distinct users who had any event
    """
    client = get_bigquery_client()
    config = get_config()
    dataset_id = config.get("rt_mp_dataset", config["bigquery_dataset"])
    table_id = config.get("rt_mp_table", "rt_mp_events")
    
    query = f"""
    SELECT COUNT(DISTINCT distinct_id) as distinct_user_count
    FROM `{config["gcp_project_id"]}.{dataset_id}.{table_id}`
    WHERE event_timestamp >= @start_time
        AND event_timestamp < @end_time
        AND distinct_id IS NOT NULL
    """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("start_time", "TIMESTAMP", start_time),
            bigquery.ScalarQueryParameter("end_time", "TIMESTAMP", end_time),
        ]
    )
    
    query_job = client.query(query, job_config=job_config)
    results = query_job.result()
    
    # Get the count from the first (and only) row
    for row in results:
        return row.distinct_user_count
    
    return 0


def ensure_gdpr_table_exists():
    """Create GDPR deletion requests BigQuery table if it doesn't exist."""
    client = get_bigquery_client()
    
    # Table is in yotam-395120.peerplay.personal_data_deletion_tool
    project_id = "yotam-395120"
    dataset_id = "peerplay"
    table_id = "personal_data_deletion_tool"
    
    dataset_ref = client.dataset(dataset_id, project=project_id)
    
    # Create dataset if it doesn't exist
    try:
        client.get_dataset(dataset_ref)
    except NotFound:
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = "US"
        dataset = client.create_dataset(dataset, exists_ok=True)
        print(f"Created dataset {project_id}.{dataset_id}")
    
    # Create table if it doesn't exist
    table_ref = dataset_ref.table(table_id)
    try:
        client.get_table(table_ref)
        print(f"Table {project_id}.{dataset_id}.{table_id} already exists")
    except NotFound:
        schema = [
            bigquery.SchemaField("distinct_id", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("request_date", "DATE", mode="NULLABLE"),
            bigquery.SchemaField("ticket_id", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("mixpanel_request_id", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("mixpanel_deletion_status", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("singular_request_id", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("singular_deletion_status", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("bigquery_deletion_status", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("game_state_status", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("is_request_completed", "BOOLEAN", mode="NULLABLE"),
            bigquery.SchemaField("slack_message_ts", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("inserted_at", "TIMESTAMP", mode="REQUIRED"),
        ]
        table = bigquery.Table(table_ref, schema=schema)
        table = client.create_table(table)
        print(f"Created table {project_id}.{dataset_id}.{table_id}")


def insert_gdpr_requests(requests: List[Dict]):
    """
    Insert GDPR deletion requests into BigQuery.
    
    Args:
        requests: List of request dictionaries with keys:
            - distinct_id: Game user ID
            - request_date: Date of deletion request (DATE or string YYYY-MM-DD)
            - ticket_id: Ticket identifier
            - mixpanel_request_id: Mixpanel deletion request ID (optional)
            - mixpanel_deletion_status: "completed" or "pending" (default: "pending")
            - singular_request_id: Singular deletion request ID (optional)
            - singular_deletion_status: "completed" or "pending" (default: "pending")
            - bigquery_deletion_status: "completed" or "not started" (default: "not started")
            - game_state_status: "completed" or "not started" (default: "not started")
            - is_request_completed: Boolean (default: False)
            - slack_message_ts: Slack message timestamp
    """
    if not requests:
        return
    
    client = get_bigquery_client()
    
    # Table is in yotam-395120.peerplay.personal_data_deletion_tool
    project_id = "yotam-395120"
    dataset_id = "peerplay"
    table_id = "personal_data_deletion_tool"
    
    ensure_gdpr_table_exists()
    
    rows_to_insert = []
    inserted_at = datetime.utcnow()
    
    for req in requests:
        # Convert request_date to string if it's a date object
        request_date = req.get("request_date")
        if request_date and isinstance(request_date, date):
            request_date = request_date.strftime("%Y-%m-%d")
        elif request_date and isinstance(request_date, datetime):
            request_date = request_date.date().strftime("%Y-%m-%d")
        
        row = {
            "distinct_id": req.get("distinct_id"),
            "request_date": request_date,
            "ticket_id": req.get("ticket_id"),
            "mixpanel_request_id": req.get("mixpanel_request_id"),
            "mixpanel_deletion_status": req.get("mixpanel_deletion_status", "pending"),
            "singular_request_id": req.get("singular_request_id"),
            "singular_deletion_status": req.get("singular_deletion_status", "pending"),
            "bigquery_deletion_status": req.get("bigquery_deletion_status", "not started"),
            "game_state_status": req.get("game_state_status", "not started"),
            "is_request_completed": req.get("is_request_completed", False),
            "slack_message_ts": req.get("slack_message_ts"),
            "inserted_at": inserted_at.isoformat(),
        }
        rows_to_insert.append(row)
    
    table_ref = client.dataset(dataset_id, project=project_id).table(table_id)
    errors = client.insert_rows_json(table_ref, rows_to_insert)
    
    if errors:
        raise Exception(f"Error inserting rows: {errors}")
    
    print(f"Successfully inserted {len(rows_to_insert)} GDPR deletion requests into {project_id}.{dataset_id}.{table_id}")

