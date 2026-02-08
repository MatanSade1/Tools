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
    
    # Create table if it doesn't exist, or add missing columns if it does
    table_ref = dataset_ref.table(table_id)
    try:
        existing_table = client.get_table(table_ref)
        print(f"Table {project_id}.{dataset_id}.{table_id} already exists")
        
        # Check if new columns need to be added
        existing_fields = {field.name for field in existing_table.schema}
        required_fields = {"install_date", "last_activity_date"}
        missing_fields = required_fields - existing_fields
        
        if missing_fields:
            print(f"Adding missing columns: {missing_fields}")
            new_schema = list(existing_table.schema)
            
            if "install_date" not in existing_fields:
                new_schema.append(bigquery.SchemaField("install_date", "DATE", mode="NULLABLE"))
            if "last_activity_date" not in existing_fields:
                new_schema.append(bigquery.SchemaField("last_activity_date", "DATE", mode="NULLABLE"))
            
            existing_table.schema = new_schema
            client.update_table(existing_table, ["schema"])
            print(f"✅ Added columns: {missing_fields}")
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
            bigquery.SchemaField("install_date", "DATE", mode="NULLABLE"),
            bigquery.SchemaField("last_activity_date", "DATE", mode="NULLABLE"),
            bigquery.SchemaField("inserted_at", "TIMESTAMP", mode="REQUIRED"),
        ]
        table = bigquery.Table(table_ref, schema=schema)
        table = client.create_table(table)
        print(f"Created table {project_id}.{dataset_id}.{table_id}")


def get_player_dates(distinct_ids: List[str]) -> Dict[str, Dict]:
    """
    Get install_date and last_activity_date from dim_player table.
    
    Args:
        distinct_ids: List of distinct_id values to query
    
    Returns:
        Dictionary mapping distinct_id to {install_date, last_activity_date}
    """
    if not distinct_ids:
        return {}
    
    client = get_bigquery_client()
    
    # Build query with IN clause
    placeholders = ", ".join([f"'{did}'" for did in distinct_ids])
    query = f"""
    SELECT 
        distinct_id,
        install_date,
        DATE(last_event_time) as last_activity_date
    FROM `peerplay.dim_player`
    WHERE distinct_id IN ({placeholders})
    """
    
    try:
        results = client.query(query).result()
        player_data = {}
        for row in results:
            player_data[row.distinct_id] = {
                "install_date": row.install_date,
                "last_activity_date": row.last_activity_date
            }
        return player_data
    except Exception as e:
        print(f"Warning: Error fetching player data from dim_player: {e}")
        return {}


def query_custom_bq_event_count(
    table_name: str,
    event_name_column: str,
    event_name: str,
    distinct_id_column: str,
    timestamp_column: str,
    date_column: str,
    lookback_minutes: int,
    match_type: str = "exact"
) -> int:
    """
    Query a custom BigQuery table with partitioning to minimize costs.
    
    Args:
        table_name: Full table name (e.g., "yotam-395120.peerplay.processed_events")
        event_name_column: Column name that contains the event name
        event_name: Event name to filter on
        distinct_id_column: Column name that contains the distinct user ID
        timestamp_column: Column name that contains the event timestamp
        date_column: Date partition column name for cost optimization
        lookback_minutes: Number of minutes to look back
        match_type: "exact" for exact match, "prefix" for prefix matching
    
    Returns:
        Count of distinct users matching the criteria
    """
    client = get_bigquery_client()
    
    # Handle match type logic
    if match_type == "exact":
        event_filter = f"{event_name_column} = @event_name"
    else:  # prefix
        event_filter = f"{event_name_column} LIKE CONCAT(@event_name, '%')"
    
    # Query optimized with date partition and timestamp window
    query = f"""
        SELECT COUNT(DISTINCT {distinct_id_column}) as count
        FROM `{table_name}`
        WHERE {date_column} >= CURRENT_DATE() - 1  -- Safety buffer for timezones
        AND {timestamp_column} >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @lookback_minutes MINUTE)
        AND {event_filter}
    """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("event_name", "STRING", event_name),
            bigquery.ScalarQueryParameter("lookback_minutes", "INT64", lookback_minutes),
        ]
    )
    
    try:
        print(f"Executing BigQuery query on {table_name}")
        print(f"  Filter: {event_name_column} {match_type} '{event_name}'")
        print(f"  Lookback: {lookback_minutes} minutes")
        
        query_job = client.query(query, job_config=job_config)
        results = query_job.result()
        
        for row in results:
            count = row.count if row.count is not None else 0
            print(f"  Result: {count} distinct users")
            return count
            
    except Exception as e:
        print(f"Error querying custom BigQuery table {table_name}: {e}")
        import traceback
        traceback.print_exc()
        return 0
    
    return 0


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
            - install_date: Install date from dim_player (optional, will be fetched if not provided)
            - last_activity_date: Last activity date from dim_player (optional, will be fetched if not provided)
    """
    if not requests:
        return
    
    client = get_bigquery_client()
    
    # Table is in yotam-395120.peerplay.personal_data_deletion_tool
    project_id = "yotam-395120"
    dataset_id = "peerplay"
    table_id = "personal_data_deletion_tool"
    
    ensure_gdpr_table_exists()
    
    # Fetch player data for all distinct_ids that don't already have it
    distinct_ids_to_fetch = [
        req.get("distinct_id") 
        for req in requests 
        if req.get("distinct_id") and not req.get("install_date")
    ]
    
    player_data = {}
    if distinct_ids_to_fetch:
        print(f"Fetching player data for {len(distinct_ids_to_fetch)} users from dim_player...")
        player_data = get_player_dates(distinct_ids_to_fetch)
        print(f"✅ Fetched data for {len(player_data)} users")
    
    rows_to_insert = []
    inserted_at = datetime.utcnow()
    
    for req in requests:
        # Convert request_date to string if it's a date object
        request_date = req.get("request_date")
        if request_date and isinstance(request_date, date):
            request_date = request_date.strftime("%Y-%m-%d")
        elif request_date and isinstance(request_date, datetime):
            request_date = request_date.date().strftime("%Y-%m-%d")
        
        # Get player data if not already provided
        distinct_id = req.get("distinct_id")
        player_info = player_data.get(distinct_id, {}) if distinct_id else {}
        
        # Use provided values or fetch from player_data
        install_date = req.get("install_date")
        if not install_date and player_info.get("install_date"):
            install_date = player_info["install_date"]
        if install_date and isinstance(install_date, date):
            install_date = install_date.strftime("%Y-%m-%d")
        elif install_date and isinstance(install_date, datetime):
            install_date = install_date.date().strftime("%Y-%m-%d")
        
        last_activity_date = req.get("last_activity_date")
        if not last_activity_date and player_info.get("last_activity_date"):
            last_activity_date = player_info["last_activity_date"]
        if last_activity_date and isinstance(last_activity_date, date):
            last_activity_date = last_activity_date.strftime("%Y-%m-%d")
        elif last_activity_date and isinstance(last_activity_date, datetime):
            last_activity_date = last_activity_date.date().strftime("%Y-%m-%d")
        
        row = {
            "distinct_id": distinct_id,
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
            "install_date": install_date,
            "last_activity_date": last_activity_date,
            "inserted_at": inserted_at.isoformat(),
        }
        rows_to_insert.append(row)
    
    table_ref = client.dataset(dataset_id, project=project_id).table(table_id)
    errors = client.insert_rows_json(table_ref, rows_to_insert)
    
    if errors:
        raise Exception(f"Error inserting rows: {errors}")
    
    print(f"Successfully inserted {len(rows_to_insert)} GDPR deletion requests into {project_id}.{dataset_id}.{table_id}")

