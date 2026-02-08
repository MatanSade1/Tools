"""Google Sheets client for reading configuration."""
import os
import json
import logging
from typing import Dict, List, Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from shared.config import get_config


def get_sheets_service():
    """
    Get Google Sheets API service client.
    
    Uses Application Default Credentials (ADC) in Cloud Functions,
    or service account credentials if provided.
    """
    try:
        # Try to use service account credentials if provided
        service_account_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
        if service_account_file and os.path.exists(service_account_file):
            credentials = service_account.Credentials.from_service_account_file(
                service_account_file,
                scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
            )
            return build('sheets', 'v4', credentials=credentials)
        
        # Otherwise use Application Default Credentials (works in Cloud Functions)
        return build('sheets', 'v4')
    except Exception as e:
        logging.error(f"Error creating Sheets service: {e}")
        raise


def read_config_from_sheets(spreadsheet_id: str, range_name: str = "Sheet1!A:Z") -> List[List]:
    """
    Read data from Google Sheets.
    
    Args:
        spreadsheet_id: The ID of the spreadsheet (from URL)
        range_name: The A1 notation range to read (default: all columns in Sheet1)
    
    Returns:
        List of rows, where each row is a list of cell values
    """
    try:
        service = get_sheets_service()
        sheet = service.spreadsheets()
        result = sheet.values().get(
            spreadsheetId=spreadsheet_id,
            range=range_name
        ).execute()
        
        values = result.get('values', [])
        print(f"Read {len(values)} rows from spreadsheet")
        return values
    except HttpError as error:
        logging.error(f"Error reading from Google Sheets: {error}")
        raise
    except Exception as e:
        logging.error(f"Unexpected error reading from Google Sheets: {e}")
        raise


def parse_sheets_config_to_json(rows: List[List]) -> Dict:
    """
    Parse spreadsheet rows into RT MP events config JSON format.
    
    Expected columns (first row is header):
    - event_name (or Event Name)
    - enabled (or Enabled) - true/false or yes/no
    - aggregation_type (or Aggregation Type) - e.g., "count distinct users"
    - alert_threshold (or Alert Threshold) - number
    - alert_channel (or Alert Channel) - e.g., "#data-alerts-critical"
    - meaningful_name (or Meaningful Name) - human-readable name
    - match_type (or Match Type) - "exact" or "prefix"
    - collection_frequency_minutes (optional, can be in separate row or column)
    
    Args:
        rows: List of rows from spreadsheet (first row should be headers)
    
    Returns:
        Configuration dictionary in rt_mp_events_config.json format
    """
    if not rows or len(rows) < 2:
        raise ValueError("Spreadsheet must have at least a header row and one data row")
    
    # Parse header row (case-insensitive)
    headers = [str(h).strip().lower() for h in rows[0]]
    
    # Find column indices
    col_map = {}
    for i, header in enumerate(headers):
        # Event name - more flexible matching (only set once)
        if 'event_name' not in col_map:
            if ('event' in header and 'name' in header) or header == 'event' or (header == 'name' and not any('event' in h for h in headers)):
                col_map['event_name'] = i
        # Enabled
        if 'enabled' in header and 'enabled' not in col_map:
            col_map['enabled'] = i
        # Table name (BigQuery table to query)
        elif ('table_name' in header or header == 'table name') and 'table_name' not in col_map:
            col_map['table_name'] = i
        # Event name column (column in BQ table with event names)
        elif ('event_name_column' in header or header == 'event name column') and 'event_name_column' not in col_map:
            col_map['event_name_column'] = i
        # Distinct ID column
        elif ('distinct_id_column' in header or header == 'distinct id column') and 'distinct_id_column' not in col_map:
            col_map['distinct_id_column'] = i
        # Timestamp column
        elif ('timestamp_column' in header or header == 'timestamp column') and 'timestamp_column' not in col_map:
            col_map['timestamp_column'] = i
        # Date column (partition column for cost optimization)
        elif ('date_column' in header or header == 'date column') and 'date_column' not in col_map:
            col_map['date_column'] = i
        # Aggregation type
        elif ('aggregation' in header and 'type' in header) or (header == 'aggregation' and 'aggregation_type' not in col_map):
            col_map['aggregation_type'] = i
        # Alert threshold
        elif ('threshold' in header or 'alert_threshold' in header) and 'alert_threshold' not in col_map:
            col_map['alert_threshold'] = i
        # Alert channel
        elif 'channel' in header and 'alert_channel' not in col_map:
            col_map['alert_channel'] = i
        # Meaningful name
        elif (('meaningful' in header and 'name' in header) or header == 'meaningful') and 'meaningful_name' not in col_map:
            col_map['meaningful_name'] = i
        # Match type
        elif (('match' in header and 'type' in header) or header == 'match') and 'match_type' not in col_map:
            col_map['match_type'] = i
        # Collection frequency
        elif (('collection' in header and 'frequency' in header) or 'frequency' in header) and 'collection_frequency_minutes' not in col_map:
            col_map['collection_frequency_minutes'] = i
    
    # Default collection frequency (can be overridden)
    collection_frequency = 15
    
    # Parse data rows
    events = []
    for row_idx, row in enumerate(rows[1:], start=2):  # Start at 2 because row 1 is header
        if not row or all(not cell or str(cell).strip() == '' for cell in row):
            continue  # Skip empty rows
        
        event = {}
        
        # Required: event_name
        if 'event_name' in col_map:
            event_name_idx = col_map['event_name']
            if event_name_idx < len(row) and row[event_name_idx]:
                event['name'] = str(row[event_name_idx]).strip()
            else:
                logging.warning(f"Row {row_idx} missing event_name, skipping")
                continue
        else:
            # Try to find event name in first column if not explicitly found
            if not col_map.get('event_name') and len(row) > 0 and row[0]:
                event['name'] = str(row[0]).strip()
                print(f"Using first column as event_name for row {row_idx}: {event['name']}")
            else:
                logging.warning(f"Row {row_idx} missing event_name, skipping")
                continue
        
        # Optional: enabled (default: true)
        if 'enabled' in col_map:
            enabled_idx = col_map['enabled']
            if enabled_idx < len(row) and row[enabled_idx]:
                enabled_val = str(row[enabled_idx]).strip().lower()
                event['enabled'] = enabled_val in ('true', 'yes', '1', 'y', 'enabled')
            else:
                event['enabled'] = True
        else:
            event['enabled'] = True
        
        # Optional: aggregation_type (default: "count distinct users")
        if 'aggregation_type' in col_map:
            agg_idx = col_map['aggregation_type']
            if agg_idx < len(row) and row[agg_idx]:
                event['aggregation_type'] = str(row[agg_idx]).strip()
            else:
                event['aggregation_type'] = "count distinct users"
        else:
            event['aggregation_type'] = "count distinct users"
        
        # Required: alert_threshold
        if 'alert_threshold' in col_map:
            threshold_idx = col_map['alert_threshold']
            if threshold_idx < len(row) and row[threshold_idx]:
                try:
                    event['alert_threshold'] = float(row[threshold_idx])
                except (ValueError, TypeError):
                    logging.warning(f"Row {row_idx} has invalid alert_threshold, skipping")
                    continue
            else:
                logging.warning(f"Row {row_idx} missing alert_threshold, skipping")
                continue
        else:
            raise ValueError("Spreadsheet must have an 'alert_threshold' or 'Alert Threshold' column")
        
        # Optional: alert_channel (default: "#data-alerts-sandbox")
        if 'alert_channel' in col_map:
            channel_idx = col_map['alert_channel']
            if channel_idx < len(row) and row[channel_idx]:
                channel = str(row[channel_idx]).strip()
                if not channel.startswith('#'):
                    channel = '#' + channel
                event['alert_channel'] = channel
            else:
                event['alert_channel'] = "#data-alerts-sandbox"
        else:
            event['alert_channel'] = "#data-alerts-sandbox"
        
        # Optional: meaningful_name (default: event_name)
        if 'meaningful_name' in col_map:
            name_idx = col_map['meaningful_name']
            if name_idx < len(row) and row[name_idx]:
                event['meaningful_name'] = str(row[name_idx]).strip()
            else:
                event['meaningful_name'] = event['name']
        else:
            event['meaningful_name'] = event['name']
        
        # Optional: match_type (default: "exact")
        if 'match_type' in col_map:
            match_idx = col_map['match_type']
            if match_idx < len(row) and row[match_idx]:
                event['match_type'] = str(row[match_idx]).strip().lower()
            else:
                event['match_type'] = "exact"
        else:
            event['match_type'] = "exact"
        
        # Required: table_name (BigQuery table to query)
        if 'table_name' in col_map:
            table_idx = col_map['table_name']
            if table_idx < len(row) and row[table_idx]:
                event['table_name'] = str(row[table_idx]).strip()
            else:
                print(f"Warning: Row {row_idx} missing table_name, skipping")
                continue
        else:
            print(f"Warning: No table_name column found in spreadsheet, skipping row {row_idx}")
            continue
        
        # Required: event_name_column (column in BQ table that contains the event name)
        if 'event_name_column' in col_map:
            col_idx = col_map['event_name_column']
            if col_idx < len(row) and row[col_idx]:
                event['event_name_column'] = str(row[col_idx]).strip()
            else:
                print(f"Warning: Row {row_idx} missing event_name_column, skipping")
                continue
        else:
            print(f"Warning: No event_name_column column found in spreadsheet, skipping row {row_idx}")
            continue
        
        # Optional: distinct_id_column (default: "distinct_id")
        if 'distinct_id_column' in col_map:
            col_idx = col_map['distinct_id_column']
            if col_idx < len(row) and row[col_idx]:
                event['distinct_id_column'] = str(row[col_idx]).strip()
            else:
                event['distinct_id_column'] = "distinct_id"
        else:
            event['distinct_id_column'] = "distinct_id"
        
        # Optional: timestamp_column (default: "event_timestamp")
        if 'timestamp_column' in col_map:
            col_idx = col_map['timestamp_column']
            if col_idx < len(row) and row[col_idx]:
                event['timestamp_column'] = str(row[col_idx]).strip()
            else:
                event['timestamp_column'] = "event_timestamp"
        else:
            event['timestamp_column'] = "event_timestamp"
        
        # Optional: date_column (default: "event_date")
        if 'date_column' in col_map:
            col_idx = col_map['date_column']
            if col_idx < len(row) and row[col_idx]:
                event['date_column'] = str(row[col_idx]).strip()
            else:
                event['date_column'] = "event_date"
        else:
            event['date_column'] = "event_date"
        
        # Check for collection_frequency_minutes in this row or separate config
        if 'collection_frequency_minutes' in col_map:
            freq_idx = col_map['collection_frequency_minutes']
            if freq_idx < len(row) and row[freq_idx]:
                try:
                    collection_frequency = int(row[freq_idx])
                except (ValueError, TypeError):
                    pass  # Keep default
        
        events.append(event)
    
    return {
        "events": events,
        "collection_frequency_minutes": collection_frequency
    }


def validate_sheets_config(rows: List[List], col_map: Dict[str, int]) -> List[Dict]:
    """
    Validate spreadsheet configuration and return list of validation errors.
    
    Args:
        rows: List of rows from spreadsheet (first row should be headers)
        col_map: Column mapping dictionary
    
    Returns:
        List of validation error dictionaries with keys: row_number, field, error_message
    """
    validation_errors = []
    
    # Mandatory fields
    mandatory_fields = ['event_name', 'enabled', 'aggregation_type', 'alert_threshold', 
                       'alert_channel', 'meaningful_name', 'match_type']
    
    # Allowed values
    allowed_aggregation_types = ['count distinct users']
    allowed_channels = ['#data-alerts-critical', '#data-alerts-non-critical', '#data-alerts-sandbox']
    allowed_match_types = ['exact', 'prefix']
    
    # Parse data rows
    for row_idx, row in enumerate(rows[1:], start=2):  # Start at 2 because row 1 is header
        if not row or all(not cell or str(cell).strip() == '' for cell in row):
            continue  # Skip empty rows
        
        row_errors = []
        
        # Check mandatory fields
        for field in mandatory_fields:
            if field not in col_map:
                row_errors.append({
                    'row_number': row_idx,
                    'field': field,
                    'error_message': f'Missing mandatory field: {field}'
                })
                continue
            
            field_idx = col_map[field]
            if field_idx >= len(row) or not row[field_idx] or str(row[field_idx]).strip() == '':
                row_errors.append({
                    'row_number': row_idx,
                    'field': field,
                    'error_message': f'Missing mandatory field: {field}'
                })
        
        # Validate enabled field (if present)
        if 'enabled' in col_map:
            enabled_idx = col_map['enabled']
            if enabled_idx < len(row) and row[enabled_idx]:
                enabled_val = str(row[enabled_idx]).strip().lower()
                if enabled_val not in ('true', 'false', 'yes', 'no', '1', '0', 'y', 'n', 'enabled', 'disabled'):
                    row_errors.append({
                        'row_number': row_idx,
                        'field': 'enabled',
                        'error_message': f'Invalid value: "{row[enabled_idx]}". Must be true/false'
                    })
        
        # Validate aggregation_type
        if 'aggregation_type' in col_map:
            agg_idx = col_map['aggregation_type']
            if agg_idx < len(row) and row[agg_idx]:
                agg_val = str(row[agg_idx]).strip()
                if agg_val not in allowed_aggregation_types:
                    row_errors.append({
                        'row_number': row_idx,
                        'field': 'aggregation_type',
                        'error_message': f'Invalid value: "{agg_val}". Allowed values: {", ".join(allowed_aggregation_types)}'
                    })
        
        # Validate alert_threshold
        if 'alert_threshold' in col_map:
            threshold_idx = col_map['alert_threshold']
            if threshold_idx < len(row) and row[threshold_idx]:
                try:
                    threshold_val = float(row[threshold_idx])
                    if threshold_val <= 0:
                        row_errors.append({
                            'row_number': row_idx,
                            'field': 'alert_threshold',
                            'error_message': f'Invalid value: {threshold_val}. Must be a positive number'
                        })
                except (ValueError, TypeError):
                    row_errors.append({
                        'row_number': row_idx,
                        'field': 'alert_threshold',
                        'error_message': f'Invalid value: "{row[threshold_idx]}". Must be a positive number'
                    })
        
        # Validate alert_channel
        if 'alert_channel' in col_map:
            channel_idx = col_map['alert_channel']
            if channel_idx < len(row) and row[channel_idx]:
                channel = str(row[channel_idx]).strip()
                if not channel.startswith('#'):
                    channel = '#' + channel
                if channel not in allowed_channels:
                    row_errors.append({
                        'row_number': row_idx,
                        'field': 'alert_channel',
                        'error_message': f'Invalid value: "{channel}". Allowed values: {", ".join(allowed_channels)}'
                    })
        
        # Validate match_type
        if 'match_type' in col_map:
            match_idx = col_map['match_type']
            if match_idx < len(row) and row[match_idx]:
                match_val = str(row[match_idx]).strip().lower()
                if match_val not in allowed_match_types:
                    row_errors.append({
                        'row_number': row_idx,
                        'field': 'match_type',
                        'error_message': f'Invalid value: "{match_val}". Allowed values: {", ".join(allowed_match_types)}'
                    })
        
        validation_errors.extend(row_errors)
    
    return validation_errors


def get_config_from_sheets(
    spreadsheet_id: str,
    range_name: str = "Sheet1!A:Z"
) -> Dict:
    """
    Read and parse configuration from Google Sheets.
    
    Args:
        spreadsheet_id: The ID of the spreadsheet (from URL)
        range_name: The A1 notation range to read
    
    Returns:
        Configuration dictionary parsed from Google Sheets
    """
    print(f"Reading configuration from Google Sheets: {spreadsheet_id}")
    
    # Read raw rows from sheets
    rows = read_config_from_sheets(spreadsheet_id, range_name)
    
    # Parse header row to get column mapping (same logic as parse_sheets_config_to_json)
    headers = [str(h).strip().lower() for h in rows[0]]
    col_map = {}
    for i, header in enumerate(headers):
        if 'event_name' not in col_map:
            if ('event' in header and 'name' in header) or header == 'event' or (header == 'name' and not any('event' in h for h in headers)):
                col_map['event_name'] = i
        if 'enabled' in header and 'enabled' not in col_map:
            col_map['enabled'] = i
        elif ('table_name' in header or header == 'table name') and 'table_name' not in col_map:
            col_map['table_name'] = i
        elif ('event_name_column' in header or header == 'event name column') and 'event_name_column' not in col_map:
            col_map['event_name_column'] = i
        elif ('distinct_id_column' in header or header == 'distinct id column') and 'distinct_id_column' not in col_map:
            col_map['distinct_id_column'] = i
        elif ('timestamp_column' in header or header == 'timestamp column') and 'timestamp_column' not in col_map:
            col_map['timestamp_column'] = i
        elif ('date_column' in header or header == 'date column') and 'date_column' not in col_map:
            col_map['date_column'] = i
        elif ('aggregation' in header and 'type' in header) or (header == 'aggregation' and 'aggregation_type' not in col_map):
            col_map['aggregation_type'] = i
        elif ('threshold' in header or 'alert_threshold' in header) and 'alert_threshold' not in col_map:
            col_map['alert_threshold'] = i
        elif 'channel' in header and 'alert_channel' not in col_map:
            col_map['alert_channel'] = i
        elif (('meaningful' in header and 'name' in header) or header == 'meaningful') and 'meaningful_name' not in col_map:
            col_map['meaningful_name'] = i
        elif (('match' in header and 'type' in header) or header == 'match') and 'match_type' not in col_map:
            col_map['match_type'] = i
    
    # Validate configuration
    validation_errors = validate_sheets_config(rows, col_map)
    
    if validation_errors:
        logging.warning(f"Found {len(validation_errors)} validation errors in spreadsheet")
        
        # Get alert recipients from environment variable
        alert_recipients_str = os.getenv("RT_MP_VALIDATION_ALERT_RECIPIENTS", "matan.sade@peerplay.com")
        alert_recipients = [r.strip() for r in alert_recipients_str.split(",")]
        
        # Send DM alerts
        try:
            from shared.slack_client import send_validation_errors_dm
            send_validation_errors_dm(validation_errors, alert_recipients)
        except Exception as e:
            logging.warning(f"Failed to send validation error DMs: {e}")
        
        # Still parse and return config (with errors), but log them
        print("Continuing with configuration despite validation errors")
    
    # Parse to config format
    config = parse_sheets_config_to_json(rows)
    
    print(f"Successfully read {len(config.get('events', []))} events from Google Sheets")
    
    return config

