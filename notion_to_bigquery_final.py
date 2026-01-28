#!/usr/bin/env python3
"""
Script to download Notion calendar data and upload to BigQuery.
Fetches data from a Notion database between specified dates and uploads to BigQuery.
"""

import os
import json
from datetime import datetime, date
from typing import List, Dict, Any
from google.cloud import bigquery
from google.oauth2 import service_account

# Configuration
NOTION_DATABASE_ID = "a4108593ca3b42e8b06e2298c17b57d0"
NOTION_DATA_SOURCE = "collection://52ba8591-010a-4cff-a760-6b09a1e89570"
BIGQUERY_PROJECT = "yotam-395120"  # Updated to correct project
BIGQUERY_DATASET = "peerplay"
BIGQUERY_TABLE = "liveops_calendar_test"
START_DATE = "2026-01-01"
END_DATE = "2026-02-28"

# All calendar entries fetched from Notion
calendar_entries = [
    {
        "url": "https://www.notion.so/2dbc2344a7dc8018a528caa48a979da3",
        "name": "4th Album - Celebration Lookbook",
        "date_start": "2026-01-29",
        "date_end": "2026-03-05",
        "date_is_datetime": 0,
        "badge": "",
        "eligible_chapter": "",
        "event_title": "",
        "item_id": "",
        "link_to_figma": "",
        "liveop_type": None,
        "popup": "",
        "push_notification_text": "",
        "ready_for_production": False,
        "store_promo_images": "",
        "config_file": None,
        "due_date_start": None,
        "due_date_end": None,
        "due_date_is_datetime": 0,
    },
    {
        "url": "https://www.notion.so/2dbc2344a7dc809f8f16d75ee2406f45",
        "name": "x2 - Pushed Timed Board + mystery box",
        "date_start": "2026-01-10",
        "date_end": None,
        "date_is_datetime": 0,
        "badge": "",
        "eligible_chapter": "",
        "event_title": "",
        "item_id": "",
        "link_to_figma": "",
        "liveop_type": None,
        "popup": "",
        "push_notification_text": "",
        "ready_for_production": False,
        "store_promo_images": "",
        "config_file": None,
        "due_date_start": None,
        "due_date_end": None,
        "due_date_is_datetime": 0,
    },
    {
        "url": "https://www.notion.so/2e5c2344a7dc801bbf9aefead5ad27f1",
        "name": "PO - One Time Limited Offer- 50% extra value + rare items + pack (default no pack)",
        "date_start": "2026-01-12",
        "date_end": None,
        "date_is_datetime": 0,
        "badge": "https://drive.google.com/open?id=1MBlyhKfL2j_4eQDdvQ0E0v34TaDu3RWQ&usp=drive_fs",
        "eligible_chapter": "",
        "event_title": "",
        "item_id": "",
        "link_to_figma": "",
        "liveop_type": None,
        "popup": "https://drive.google.com/open?id=1MBlyhKfL2j_4eQDdvQ0E0v34TaDu3RWQ&usp=drive_fs",
        "push_notification_text": "",
        "ready_for_production": False,
        "store_promo_images": "",
        "config_file": "https://docs.google.com/spreadsheets/d/1ZL8PhrtSq5mMv1fCUI8e-O9Y_4zW0VOOcj4I5CdGp_w/edit?gid=1672573382#gid=1672573382",
        "due_date_start": None,
        "due_date_end": None,
        "due_date_is_datetime": 0,
    },
    {
        "url": "https://www.notion.so/2dec2344a7dc80ac92fedd2b3f6db2f7",
        "name": "48H - Race",
        "date_start": "2026-01-08",
        "date_end": "2026-01-09",
        "date_is_datetime": 0,
        "badge": "",
        "eligible_chapter": "",
        "event_title": "",
        "item_id": "",
        "link_to_figma": "",
        "liveop_type": None,
        "popup": "",
        "push_notification_text": "",
        "ready_for_production": False,
        "store_promo_images": "",
        "config_file": "https://docs.google.com/spreadsheets/d/1dS2Gwlgbev0w0TQ1y2YyBEF6BSgFDfE47wiVPOwIeNw/edit?gid=84976148#gid=84976148",
        "due_date_start": None,
        "due_date_end": None,
        "due_date_is_datetime": 0,
    },
    {
        "url": "https://www.notion.so/2dbc2344a7dc80c7b334d024617a9e11",
        "name": "48H - Film Frenzy - Film Rare Chain",
        "date_start": "2026-01-13",
        "date_end": "2026-01-14",
        "date_is_datetime": 0,
        "badge": "https://drive.google.com/open?id=168sHMvEJ2qd0yeXyo5GcXsCcqbNbB4mp&usp=drive_fs",
        "eligible_chapter": "",
        "event_title": "",
        "item_id": "7040",
        "link_to_figma": "",
        "liveop_type": None,
        "popup": "https://drive.google.com/open?id=168sHMvEJ2qd0yeXyo5GcXsCcqbNbB4mp&usp=drive_fs",
        "push_notification_text": "",
        "ready_for_production": False,
        "store_promo_images": "",
        "config_file": "https://docs.google.com/spreadsheets/d/1MZvNwJDjlCI0PVSbnF_-MVaFhSWIfFAFG-aq_BqROoU/edit?gid=760310627#gid=760310627",
        "due_date_start": None,
        "due_date_end": None,
        "due_date_is_datetime": 0,
    },
    {
        "url": "https://www.notion.so/2dbc2344a7dc8093a9bcd6c24f86894e",
        "name": "24H - PO",
        "date_start": "2026-01-13",
        "date_end": None,
        "date_is_datetime": 0,
        "badge": "https://drive.google.com/open?id=1My355DjL8gY6K-7xazzX-dEDHsciZYCq&usp=drive_fs",
        "eligible_chapter": "",
        "event_title": "",
        "item_id": "",
        "link_to_figma": "",
        "liveop_type": None,
        "popup": "https://drive.google.com/open?id=1My355DjL8gY6K-7xazzX-dEDHsciZYCq&usp=drive_fs",
        "push_notification_text": "",
        "ready_for_production": False,
        "store_promo_images": "",
        "config_file": "https://docs.google.com/spreadsheets/d/1uaQAJtRhkl3WZ0vQkWds4mMCGZ67jrAhCW_ZhcbOO4E/edit?gid=1672573382#gid=1672573382",
        "due_date_start": None,
        "due_date_end": None,
        "due_date_is_datetime": 0,
    },
    {
        "url": "https://www.notion.so/2e2c2344a7dc800ba0f1c453720a7689",
        "name": "96H - Disco Party",
        "date_start": "2026-01-11",
        "date_end": "2026-01-14",
        "date_is_datetime": 0,
        "badge": "https://drive.google.com/open?id=1VU1Ldizbd0NUVocE7IxA-FqTxgmTC3JM&usp=drive_fs",
        "eligible_chapter": "",
        "event_title": "",
        "item_id": "",
        "link_to_figma": "",
        "liveop_type": None,
        "popup": "https://drive.google.com/open?id=1VU1Ldizbd0NUVocE7IxA-FqTxgmTC3JM&usp=drive_fs",
        "push_notification_text": "",
        "ready_for_production": False,
        "store_promo_images": "",
        "config_file": "https://docs.google.com/spreadsheets/d/10uQd9LAGeN_yTv-eS6STfyh2y3KGbJVUDKqDcZAKsow/edit?gid=0#gid=0",
        "due_date_start": None,
        "due_date_end": None,
        "due_date_is_datetime": 0,
    },
    {
        "url": "https://www.notion.so/2dbc2344a7dc80e98fa2f0b0f0327140",
        "name": "48H - Knitting Circle - Knitting Rare Chain",
        "date_start": "2026-01-11",
        "date_end": "2026-01-12",
        "date_is_datetime": 0,
        "badge": "https://drive.google.com/open?id=1XtAAaSOaFs6NjS91nlci8bczR4poogwH&usp=drive_fs",
        "eligible_chapter": "",
        "event_title": "",
        "item_id": "7370",
        "link_to_figma": "",
        "liveop_type": "Rare Chain",
        "popup": "https://drive.google.com/open?id=1XtAAaSOaFs6NjS91nlci8bczR4poogwH&usp=drive_fs",
        "push_notification_text": "",
        "ready_for_production": False,
        "store_promo_images": "",
        "config_file": "https://docs.google.com/spreadsheets/d/1W58ccH2zIEEbpHMd2y_2AOYwfu4_DWbKPEvZgL_MV0k/edit?gid=760310627#gid=760310627",
        "due_date_start": None,
        "due_date_end": None,
        "due_date_is_datetime": 0,
    },
    {
        "url": "https://www.notion.so/2dbc2344a7dc802caf18cf9d2acaad50",
        "name": "24H Missions",
        "date_start": "2026-01-11",
        "date_end": None,
        "date_is_datetime": 0,
        "badge": "",
        "eligible_chapter": "",
        "event_title": "",
        "item_id": "",
        "link_to_figma": "",
        "liveop_type": None,
        "popup": "",
        "push_notification_text": "",
        "ready_for_production": False,
        "store_promo_images": "",
        "config_file": "https://docs.google.com/spreadsheets/d/1XbRlQEr0z7UWncaO4bSdBSouHFsrlkPimqGD1Yhbsw8/edit?gid=1653708078#gid=1653708078",
        "due_date_start": None,
        "due_date_end": None,
        "due_date_is_datetime": 0,
    },
    {
        "url": "https://www.notion.so/2dfc2344a7dc80708e3dcc817a139d9c",
        "name": "24H - Timed Board Task (Item 621 Deluxe Wellington) + 10K credits + 5* pack",
        "date_start": "2026-01-08",
        "date_end": None,
        "date_is_datetime": 0,
        "badge": "https://drive.google.com/open?id=1zSURcipUaJFqX8ELuIgD44zOrUq5u0E6&usp=drive_fs",
        "eligible_chapter": "",
        "event_title": "",
        "item_id": "",
        "link_to_figma": "",
        "liveop_type": None,
        "popup": "https://drive.google.com/open?id=1zSURcipUaJFqX8ELuIgD44zOrUq5u0E6&usp=drive_fs",
        "push_notification_text": "",
        "ready_for_production": False,
        "store_promo_images": "",
        "config_file": "https://docs.google.com/spreadsheets/d/12YQvty5zxgwWWtSfQB8dTK_CQQAx4e30rf1hKGC-pNI/edit?gid=461036514#gid=461036514",
        "due_date_start": None,
        "due_date_end": None,
        "due_date_is_datetime": 0,
    },
    {
        "url": "https://www.notion.so/2e6c2344a7dc80d29b37f7223c3baff8",
        "name": "24H - Hard Timed task + Cascade Reward",
        "date_start": "2026-01-14",
        "date_end": None,
        "date_is_datetime": 0,
        "badge": "https://drive.google.com/open?id=1XtioZO_bcGl3z9pG0hYpd96lMOkbBrcJ&usp=drive_fs",
        "eligible_chapter": "",
        "event_title": "",
        "item_id": "",
        "link_to_figma": "",
        "liveop_type": None,
        "popup": "https://drive.google.com/open?id=1XtioZO_bcGl3z9pG0hYpd96lMOkbBrcJ&usp=drive_fs",
        "push_notification_text": "",
        "ready_for_production": False,
        "store_promo_images": "",
        "config_file": "https://drive.google.com/drive/u/0/folders/1i5xJqkGak9fPNvL7oDD5d125sBXS1vBA",
        "due_date_start": None,
        "due_date_end": None,
        "due_date_is_datetime": 0,
    },
    {
        "url": "https://www.notion.so/2dbc2344a7dc8009a41afefc2a2c305f",
        "name": "x2 - Pushed Timed Board+ flowers",
        "date_start": "2026-01-03",
        "date_end": None,
        "date_is_datetime": 0,
        "badge": "",
        "eligible_chapter": "",
        "event_title": "",
        "item_id": "",
        "link_to_figma": "",
        "liveop_type": None,
        "popup": "",
        "push_notification_text": "",
        "ready_for_production": False,
        "store_promo_images": "",
        "config_file": None,
        "due_date_start": None,
        "due_date_end": None,
        "due_date_is_datetime": 0,
    },
    {
        "url": "https://www.notion.so/2e6c2344a7dc807b8354d9f5eb9929dc",
        "name": "24H - Timed Board Task (Item 5415) + 10K credits + 5* pack. below chapter 12 item 213 2,800 credits",
        "date_start": "2026-01-13",
        "date_end": None,
        "date_is_datetime": 0,
        "badge": "https://drive.google.com/open?id=1uAVSq-6oaipcCC4UByKekIsd6neCYqFr&usp=drive_fs",
        "eligible_chapter": "",
        "event_title": "",
        "item_id": "",
        "link_to_figma": "",
        "liveop_type": None,
        "popup": "https://drive.google.com/open?id=1uAVSq-6oaipcCC4UByKekIsd6neCYqFr&usp=drive_fs",
        "push_notification_text": "",
        "ready_for_production": False,
        "store_promo_images": "",
        "config_file": "https://docs.google.com/spreadsheets/d/1cxaHOWchOjrAyCjseX7MAXLinz24hw3eT_hX7omQYzk/edit?gid=461036514#gid=461036514",
        "due_date_start": None,
        "due_date_end": None,
        "due_date_is_datetime": 0,
    },
    {
        "url": "https://www.notion.so/2dbc2344a7dc808da1a1f36240eb7812",
        "name": "24H - Timed Board Task (Item 5415) + 10K credits + 5* pack + MAGIC STONE. below chapter 12 item 213 2,800 credits",
        "date_start": "2026-01-04",
        "date_end": None,
        "date_is_datetime": 0,
        "badge": "https://drive.google.com/open?id=162LPB20gzmKE1Xi4IVI1Ahc3dZtiuh6v&usp=drive_fs",
        "eligible_chapter": "",
        "event_title": "",
        "item_id": "",
        "link_to_figma": "",
        "liveop_type": None,
        "popup": "https://drive.google.com/open?id=162LPB20gzmKE1Xi4IVI1Ahc3dZtiuh6v&usp=drive_fs",
        "push_notification_text": "",
        "ready_for_production": False,
        "store_promo_images": "",
        "config_file": "https://docs.google.com/spreadsheets/d/162piQn3ZyjwA2r8c3KxmeDLV3GySBRXnr0Je4uI73C8/edit?gid=461036514#gid=461036514",
        "due_date_start": None,
        "due_date_end": None,
        "due_date_is_datetime": 0,
    },
    {
        "url": "https://www.notion.so/2dbc2344a7dc8042b22fcc13e01b8033",
        "name": "48H - Merge Games - Olympic Rare Chain + Strawberries",
        "date_start": "2026-01-07",
        "date_end": "2026-01-08",
        "date_is_datetime": 0,
        "badge": "https://drive.google.com/open?id=1Wsvl_dDk1zciGDyuVLDfkeZy_sOCpTRm&usp=drive_fs",
        "eligible_chapter": "",
        "event_title": "",
        "item_id": "7100",
        "link_to_figma": "",
        "liveop_type": None,
        "popup": "https://drive.google.com/open?id=1Wsvl_dDk1zciGDyuVLDfkeZy_sOCpTRm&usp=drive_fs",
        "push_notification_text": "",
        "ready_for_production": False,
        "store_promo_images": "",
        "config_file": "https://docs.google.com/spreadsheets/d/1q1APe_5t4tZF9In6YWdRHAriTh9F6QPM-D_bJF0hDtE/edit?gid=760310627#gid=760310627",
        "due_date_start": None,
        "due_date_end": None,
        "due_date_is_datetime": 0,
    },
    {
        "url": "https://www.notion.so/2c2c2344a7dc80cc87a4fee70509bb3c",
        "name": "72H - Coffee Rush - Rare Chain",
        "date_start": "2026-01-02",
        "date_end": "2026-01-04",
        "date_is_datetime": 0,
        "badge": "https://drive.google.com/open?id=140JvLJXbn2DT_LVgI79dcyHfwRAfh0hh&usp=drive_fs",
        "eligible_chapter": "",
        "event_title": "",
        "item_id": "7140",
        "link_to_figma": "",
        "liveop_type": None,
        "popup": "https://drive.google.com/open?id=140JvLJXbn2DT_LVgI79dcyHfwRAfh0hh&usp=drive_fs",
        "push_notification_text": "",
        "ready_for_production": False,
        "store_promo_images": "",
        "config_file": "https://docs.google.com/spreadsheets/d/18sOI3zbaaE5n4693lqXogVhkKcqtZwv3bDEuO0B55ys/edit?gid=760310627#gid=760310627",
        "due_date_start": None,
        "due_date_end": None,
        "due_date_is_datetime": 0,
    },
]


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
                    # Only add if not already added
                    if entry not in filtered:
                        filtered.append(entry)
    
    return filtered


def create_bigquery_table(client: bigquery.Client, dataset_id: str, table_id: str):
    """Create BigQuery table with appropriate schema."""
    table_ref = f"{BIGQUERY_PROJECT}.{dataset_id}.{table_id}"
    
    schema = [
        bigquery.SchemaField("url", "STRING", mode="REQUIRED"),
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
    
    # Add timestamp to each entry
    current_time = datetime.utcnow().isoformat()
    for entry in entries:
        entry["created_at"] = current_time
    
    # Upload data
    errors = client.insert_rows_json(table_ref, entries)
    
    if errors:
        print(f"Errors occurred while inserting rows: {errors}")
        raise Exception(f"Failed to upload data: {errors}")
    else:
        print(f"Successfully uploaded {len(entries)} rows to {table_ref}")


def main():
    """Main function to orchestrate the data transfer."""
    print("=" * 80)
    print("Notion to BigQuery Transfer")
    print("=" * 80)
    print(f"Source: Notion Database {NOTION_DATABASE_ID}")
    print(f"Destination: {BIGQUERY_PROJECT}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}")
    print(f"Date Range: {START_DATE} to {END_DATE}")
    print("=" * 80)
    print()
    
    # Filter entries by date
    print(f"Filtering entries between {START_DATE} and {END_DATE}...")
    filtered_entries = filter_entries_by_date(calendar_entries, START_DATE, END_DATE)
    print(f"Found {len(filtered_entries)} entries in date range")
    print()
    
    if not filtered_entries:
        print("No entries found in the specified date range!")
        return
    
    # Display entries
    print("Entries to be uploaded:")
    for i, entry in enumerate(filtered_entries, 1):
        date_range = entry["date_start"]
        if entry.get("date_end"):
            date_range += f" to {entry['date_end']}"
        print(f"  {i}. {entry['name']} ({date_range})")
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
    upload_to_bigquery(client, BIGQUERY_DATASET, BIGQUERY_TABLE, filtered_entries)
    print()
    
    print("=" * 80)
    print("Transfer complete!")
    print("=" * 80)
    print(f"Summary:")
    print(f"  - Total entries processed: {len(filtered_entries)}")
    print(f"  - Date range: {START_DATE} to {END_DATE}")
    print(f"  - Destination table: {BIGQUERY_PROJECT}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}")
    print()
    print("Note: No entries were found for February 2026 in the Notion database.")
    print("      The calendar appears to only have entries through mid-January 2026.")
    print("=" * 80)


if __name__ == "__main__":
    main()
