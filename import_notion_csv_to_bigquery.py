#!/usr/bin/env python3
"""
Script to import Notion calendar CSV export to BigQuery.
Creates table: yotam-395120.peerplay.liveops_calendar_test_2
"""

import os
import sys
import csv
from datetime import datetime
from typing import List, Dict, Any
from google.cloud import bigquery

# Configuration
BIGQUERY_PROJECT = "yotam-395120"
BIGQUERY_DATASET = "peerplay"
BIGQUERY_TABLE = "liveops_calendar_test_2"
START_DATE = "2026-01-01"
END_DATE = "2026-02-28"


def parse_notion_date(date_str: str) -> tuple:
    """
    Parse Notion date string which can be:
    - Single date: "January 2, 2026"
    - Date range: "January 2, 2026 → January 4, 2026"
    Returns: (start_date, end_date) in YYYY-MM-DD format
    """
    if not date_str or date_str.strip() == '':
        return None, None
    
    # Split by arrow if it's a range
    if '→' in date_str:
        parts = date_str.split('→')
        start_str = parts[0].strip()
        end_str = parts[1].strip()
    else:
        start_str = date_str.strip()
        end_str = None
    
    # Parse dates
    try:
        start_date = datetime.strptime(start_str, "%B %d, %Y").strftime("%Y-%m-%d")
    except:
        try:
            start_date = datetime.strptime(start_str, "%Y-%m-%d").strftime("%Y-%m-%d")
        except:
            return None, None
    
    end_date = None
    if end_str:
        try:
            end_date = datetime.strptime(end_str, "%B %d, %Y").strftime("%Y-%m-%d")
        except:
            try:
                end_date = datetime.strptime(end_str, "%Y-%m-%d").strftime("%Y-%m-%d")
            except:
                pass
    
    return start_date, end_date


def parse_boolean(value: str) -> bool:
    """Parse Notion checkbox value."""
    if not value:
        return False
    return value.strip().lower() in ['yes', 'true', 'checked', '✓', '☑', '✅']


def is_in_date_range(date_str: str, start_range: str, end_range: str) -> bool:
    """Check if a date is within the specified range."""
    if not date_str:
        return False
    
    try:
        date = datetime.strptime(date_str, "%Y-%m-%d").date()
        start = datetime.strptime(start_range, "%Y-%m-%d").date()
        end = datetime.strptime(end_range, "%Y-%m-%d").date()
        return start <= date <= end
    except:
        return False


def parse_csv_row(row: Dict[str, str]) -> Dict[str, Any]:
    """Parse a CSV row into a BigQuery-compatible record."""
    # Parse the date field
    date_start, date_end = parse_notion_date(row.get('Date', ''))
    due_date_start, due_date_end = parse_notion_date(row.get('Due Date', ''))
    
    # Handle Config File (might have multiple files separated by commas)
    config_file = row.get('Config File', '').strip()
    if config_file and config_file.startswith('http'):
        # Take the first URL if multiple
        config_file = config_file.split(',')[0].strip()
    else:
        config_file = None
    
    return {
        'url': row.get('url', row.get('URL', '')).strip(),
        'name': row.get('Name', '').strip(),
        'date_start': date_start,
        'date_end': date_end,
        'date_is_datetime': 0,  # Notion doesn't export datetime info in CSV
        'badge': row.get('Badge', '').strip(),
        'eligible_chapter': row.get('Eligible chapter', '').strip(),
        'event_title': row.get('Event Title', '').strip(),
        'item_id': row.get('Item ID', '').strip(),
        'link_to_figma': row.get('Link to Figma', '').strip(),
        'liveop_type': row.get('Liveop Type', '').strip() or None,
        'popup': row.get('Popup', '').strip(),
        'push_notification_text': row.get('Push Notification Text', '').strip(),
        'ready_for_production': parse_boolean(row.get('Ready for production', '')),
        'store_promo_images': row.get('Store Promo Images', '').strip(),
        'config_file': config_file,
        'due_date_start': due_date_start,
        'due_date_end': due_date_end,
        'due_date_is_datetime': 0,
        'created_at': datetime.utcnow().isoformat(),
    }


def read_csv_file(csv_path: str) -> List[Dict[str, Any]]:
    """Read and parse CSV file."""
    entries = []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                entry = parse_csv_row(row)
                if entry['date_start']:  # Only include entries with a valid date
                    entries.append(entry)
            except Exception as e:
                print(f"Warning: Could not parse row: {e}")
                print(f"Row data: {row}")
                continue
    
    return entries


def filter_entries_by_date(entries: List[Dict[str, Any]], start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """Filter calendar entries by date range."""
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    
    filtered = []
    for entry in entries:
        if entry.get("date_start"):
            entry_date = datetime.strptime(entry["date_start"], "%Y-%m-%d").date()
            # Include entry if start date is within range OR if it has an end date that overlaps
            if start <= entry_date <= end:
                filtered.append(entry)
            elif entry.get("date_end"):
                entry_end_date = datetime.strptime(entry["date_end"], "%Y-%m-%d").date()
                # Check if the date range overlaps with our target range
                if entry_date <= end and entry_end_date >= start:
                    if entry not in filtered:
                        filtered.append(entry)
    
    return filtered


def create_bigquery_table(client: bigquery.Client, dataset_id: str, table_id: str):
    """Create BigQuery table with appropriate schema."""
    table_ref = f"{BIGQUERY_PROJECT}.{dataset_id}.{table_id}"
    
    schema = [
        bigquery.SchemaField("url", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("name", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("date_start", "DATE", mode="NULLABLE"),
        bigquery.SchemaField("date_end", "DATE", mode="NULLABLE"),
        bigquery.SchemaField("date_is_datetime", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("badge", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("eligible_chapter", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("event_title", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("item_id", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("link_to_figma", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("liveop_type", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("popup", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("push_notification_text", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("ready_for_production", "BOOLEAN", mode="NULLABLE"),
        bigquery.SchemaField("store_promo_images", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("config_file", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("due_date_start", "DATE", mode="NULLABLE"),
        bigquery.SchemaField("due_date_end", "DATE", mode="NULLABLE"),
        bigquery.SchemaField("due_date_is_datetime", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
    ]
    
    table = bigquery.Table(table_ref, schema=schema)
    
    # Try to delete if exists
    try:
        client.delete_table(table_ref)
        print(f"Deleted existing table {table_ref}")
    except Exception as e:
        print(f"Table {table_ref} doesn't exist or couldn't be deleted: {e}")
    
    # Create new table
    table = client.create_table(table)
    print(f"Created table {table_ref}")
    
    return table


def upload_to_bigquery(client: bigquery.Client, dataset_id: str, table_id: str, entries: List[Dict[str, Any]]):
    """Upload entries to BigQuery."""
    table_ref = f"{BIGQUERY_PROJECT}.{dataset_id}.{table_id}"
    
    # Upload data in batches if needed (BigQuery has limits)
    batch_size = 500
    total_uploaded = 0
    
    for i in range(0, len(entries), batch_size):
        batch = entries[i:i + batch_size]
        errors = client.insert_rows_json(table_ref, batch)
        
        if errors:
            print(f"Errors occurred while inserting batch {i//batch_size + 1}: {errors}")
        else:
            total_uploaded += len(batch)
            print(f"Successfully uploaded batch {i//batch_size + 1}: {len(batch)} rows")
    
    print(f"Total rows uploaded: {total_uploaded}")
    return total_uploaded


def main():
    """Main function to orchestrate the CSV import."""
    if len(sys.argv) < 2:
        print("Usage: python import_notion_csv_to_bigquery.py <csv_file_path>")
        print("\nExample:")
        print("  python import_notion_csv_to_bigquery.py notion_export.csv")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found: {csv_path}")
        sys.exit(1)
    
    print("=" * 80)
    print("Notion CSV to BigQuery Import")
    print("=" * 80)
    print(f"Source: {csv_path}")
    print(f"Destination: {BIGQUERY_PROJECT}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}")
    print(f"Date Range Filter: {START_DATE} to {END_DATE}")
    print("=" * 80)
    print()
    
    # Read CSV file
    print("Reading CSV file...")
    all_entries = read_csv_file(csv_path)
    print(f"Found {len(all_entries)} total entries in CSV")
    print()
    
    # Filter by date range
    print(f"Filtering entries between {START_DATE} and {END_DATE}...")
    filtered_entries = filter_entries_by_date(all_entries, START_DATE, END_DATE)
    print(f"Found {len(filtered_entries)} entries in date range")
    print()
    
    if not filtered_entries:
        print("No entries found in the specified date range!")
        return
    
    # Display sample entries
    print("Sample entries to be uploaded:")
    for i, entry in enumerate(filtered_entries[:5], 1):
        date_range = entry["date_start"]
        if entry.get("date_end"):
            date_range += f" to {entry['date_end']}"
        print(f"  {i}. {entry['name']} ({date_range})")
    if len(filtered_entries) > 5:
        print(f"  ... and {len(filtered_entries) - 5} more")
    print()
    
    # Initialize BigQuery client
    print("Initializing BigQuery client...")
    client = bigquery.Client(project=BIGQUERY_PROJECT)
    print()
    
    # Create table
    print("Creating BigQuery table...")
    create_bigquery_table(client, BIGQUERY_DATASET, BIGQUERY_TABLE)
    print()
    
    # Upload data
    print("Uploading data to BigQuery...")
    uploaded_count = upload_to_bigquery(client, BIGQUERY_DATASET, BIGQUERY_TABLE, filtered_entries)
    print()
    
    print("=" * 80)
    print("Import complete!")
    print("=" * 80)
    print(f"Summary:")
    print(f"  - Total entries in CSV: {len(all_entries)}")
    print(f"  - Entries in date range: {len(filtered_entries)}")
    print(f"  - Successfully uploaded: {uploaded_count}")
    print(f"  - Date range: {START_DATE} to {END_DATE}")
    print(f"  - Destination table: {BIGQUERY_PROJECT}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}")
    print("=" * 80)


if __name__ == "__main__":
    main()
