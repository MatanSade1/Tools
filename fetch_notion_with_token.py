#!/usr/bin/env python3
"""
Fetch all calendar entries from Notion using Integration token.
Uses deterministic database query API to get 100% of entries.
"""

import json
import requests
import os
from datetime import datetime
from typing import List, Dict, Any
from google.cloud import bigquery

# Configuration
NOTION_TOKEN = os.environ.get('NOTION_TOKEN', '')  # Set via environment variable
NOTION_API_VERSION = '2022-06-28'
DATABASE_ID = 'a4108593ca3b42e8b06e2298c17b57d0'
BIGQUERY_PROJECT = "yotam-395120"
BIGQUERY_DATASET = "peerplay"
BIGQUERY_TABLE = "liveops_calendar_test_2"
START_DATE = "2026-01-01"
END_DATE = "2026-02-28"


def query_notion_database(token: str, start_date: str, end_date: str):
    """Query Notion database with pagination - gets ALL entries deterministically."""
    url = f'https://api.notion.com/v1/databases/{DATABASE_ID}/query'
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Notion-Version': NOTION_API_VERSION,
        'Content-Type': 'application/json',
    }
    
    # Build filter for date range
    payload = {
        'filter': {
            'and': [
                {
                    'property': 'Date',
                    'date': {
                        'on_or_after': start_date
                    }
                },
                {
                    'property': 'Date',
                    'date': {
                        'on_or_before': end_date
                    }
                }
            ]
        },
        'page_size': 100
    }
    
    all_results = []
    has_more = True
    start_cursor = None
    page_num = 1
    
    print(f"Querying Notion database for entries between {start_date} and {end_date}...")
    print()
    
    while has_more:
        if start_cursor:
            payload['start_cursor'] = start_cursor
        
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            print(f"❌ Error querying database: {response.status_code}")
            print(response.text)
            break
        
        data = response.json()
        results = data.get('results', [])
        all_results.extend(results)
        
        has_more = data.get('has_more', False)
        start_cursor = data.get('next_cursor')
        
        print(f"  Page {page_num}: Fetched {len(results)} entries (Total: {len(all_results)})")
        page_num += 1
    
    print()
    print(f"✅ Successfully fetched {len(all_results)} entries from Notion")
    return all_results


def parse_notion_page(page: Dict) -> Dict[str, Any]:
    """Parse Notion page object into BigQuery-compatible format."""
    props = page.get('properties', {})
    
    # Helper to get property value
    def get_prop(name, prop_type='rich_text'):
        prop = props.get(name, {})
        if prop_type == 'title':
            title_list = prop.get('title', [])
            return title_list[0].get('plain_text', '') if title_list else ''
        elif prop_type == 'rich_text':
            text_list = prop.get('rich_text', [])
            return text_list[0].get('plain_text', '') if text_list else ''
        elif prop_type == 'url':
            return prop.get('url', '') or ''
        elif prop_type == 'select':
            select = prop.get('select')
            return select.get('name', '') if select else None
        elif prop_type == 'checkbox':
            return prop.get('checkbox', False)
        elif prop_type == 'date':
            date_obj = prop.get('date')
            if date_obj:
                return date_obj.get('start'), date_obj.get('end')
            return None, None
        elif prop_type == 'files':
            files = prop.get('files', [])
            if files:
                file_obj = files[0]
                if 'file' in file_obj:
                    return file_obj['file'].get('url', '')
                elif 'external' in file_obj:
                    return file_obj['external'].get('url', '')
            return None
        return ''
    
    date_start, date_end = get_prop('Date', 'date')
    due_date_start, due_date_end = get_prop('Due Date', 'date')
    
    # Extract date portion only (remove time if present)
    if date_start and 'T' in date_start:
        date_start = date_start.split('T')[0]
    if date_end and 'T' in date_end:
        date_end = date_end.split('T')[0]
    if due_date_start and 'T' in due_date_start:
        due_date_start = due_date_start.split('T')[0]
    if due_date_end and 'T' in due_date_end:
        due_date_end = due_date_end.split('T')[0]
    
    return {
        'url': page.get('url', ''),
        'name': get_prop('Name', 'title'),
        'date_start': date_start,
        'date_end': date_end,
        'date_is_datetime': 0,
        'badge': get_prop('Badge', 'url'),
        'eligible_chapter': get_prop('Eligible chapter', 'rich_text'),
        'event_title': get_prop('Event Title', 'rich_text'),
        'item_id': get_prop('Item ID', 'rich_text'),
        'link_to_figma': get_prop('Link to Figma', 'url'),
        'liveop_type': get_prop('Liveop Type', 'select'),
        'popup': get_prop('Popup', 'url'),
        'push_notification_text': get_prop('Push Notification Text', 'rich_text'),
        'ready_for_production': get_prop('Ready for production', 'checkbox'),
        'store_promo_images': get_prop('Store Promo Images', 'url'),
        'config_file': get_prop('Config File', 'files'),
        'due_date_start': due_date_start,
        'due_date_end': due_date_end,
        'due_date_is_datetime': 0,
        'created_at': datetime.utcnow().isoformat(),
    }


def create_bigquery_table(client: bigquery.Client):
    """Create BigQuery table."""
    table_ref = f"{BIGQUERY_PROJECT}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}"
    
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
    
    try:
        client.delete_table(table_ref)
        print(f"Deleted existing table {table_ref}")
    except:
        pass
    
    table = client.create_table(table)
    print(f"✅ Created table {table_ref}")
    return table


def main():
    print("=" * 80)
    print("Notion to BigQuery - Integration Token Method (Deterministic)")
    print("=" * 80)
    print(f"Source: Notion Database {DATABASE_ID}")
    print(f"Destination: {BIGQUERY_PROJECT}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}")
    print(f"Date Range: {START_DATE} to {END_DATE}")
    print("=" * 80)
    print()
    
    # Fetch data from Notion
    pages = query_notion_database(NOTION_TOKEN, START_DATE, END_DATE)
    
    if not pages:
        print("❌ No entries found in the specified date range")
        print()
        print("Possible reasons:")
        print("  1. The database doesn't have entries in this date range")
        print("  2. The integration doesn't have access to the database")
        print("     → Share the database with the integration in Notion")
        return
    
    print()
    print("Parsing entries...")
    entries = [parse_notion_page(page) for page in pages]
    print(f"✅ Parsed {len(entries)} entries")
    print()
    
    # Display sample entries
    print("Sample entries:")
    for i, entry in enumerate(entries[:10], 1):
        date_range = entry["date_start"] or "No date"
        if entry.get("date_end"):
            date_range += f" to {entry['date_end']}"
        print(f"  {i}. {entry['name']} ({date_range})")
    if len(entries) > 10:
        print(f"  ... and {len(entries) - 10} more")
    print()
    
    # Upload to BigQuery
    print("Uploading to BigQuery...")
    client = bigquery.Client(project=BIGQUERY_PROJECT)
    create_bigquery_table(client)
    print()
    
    table_ref = f"{BIGQUERY_PROJECT}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}"
    errors = client.insert_rows_json(table_ref, entries)
    
    if errors:
        print(f"❌ Errors during upload: {errors}")
    else:
        print(f"✅ Successfully uploaded {len(entries)} entries to BigQuery")
    
    print()
    print("=" * 80)
    print("Import Complete!")
    print("=" * 80)
    print(f"Summary:")
    print(f"  - Entries fetched from Notion: {len(entries)}")
    print(f"  - Date range: {START_DATE} to {END_DATE}")
    print(f"  - Destination: {BIGQUERY_PROJECT}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}")
    print()
    print("Verify with:")
    print(f"  bq query --use_legacy_sql=false \"SELECT COUNT(*) FROM \\`{BIGQUERY_PROJECT}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}\\`\"")
    print("=" * 80)


if __name__ == '__main__':
    main()
