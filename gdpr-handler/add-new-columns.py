#!/usr/bin/env python3
"""Add install_date and last_activity_date columns to existing BigQuery table."""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.bigquery_client import get_bigquery_client
from google.cloud import bigquery

def add_new_columns():
    """Add install_date and last_activity_date columns to the table."""
    client = get_bigquery_client()
    
    project_id = "yotam-395120"
    dataset_id = "peerplay"
    table_id = "personal_data_deletion_tool"
    
    print("=" * 60)
    print("Adding new columns to BigQuery table")
    print("=" * 60)
    print()
    
    table_ref = client.dataset(dataset_id, project=project_id).table(table_id)
    
    try:
        table = client.get_table(table_ref)
        existing_fields = {field.name for field in table.schema}
        
        print(f"Current columns: {len(existing_fields)}")
        print()
        
        # Check which columns need to be added
        columns_to_add = []
        
        if "install_date" not in existing_fields:
            columns_to_add.append(("install_date", "DATE"))
            print("  - install_date (DATE) - needs to be added")
        
        if "last_activity_date" not in existing_fields:
            columns_to_add.append(("last_activity_date", "DATE"))
            print("  - last_activity_date (DATE) - needs to be added")
        
        if not columns_to_add:
            print("✅ All columns already exist")
            return
        
        print()
        print(f"Adding {len(columns_to_add)} columns...")
        
        # Add columns using ALTER TABLE
        for col_name, col_type in columns_to_add:
            alter_query = f"""
            ALTER TABLE `{project_id}.{dataset_id}.{table_id}`
            ADD COLUMN IF NOT EXISTS {col_name} {col_type}
            """
            
            try:
                alter_job = client.query(alter_query)
                alter_job.result()
                print(f"  ✅ Added column: {col_name}")
            except Exception as e:
                # If ALTER TABLE doesn't work, try updating schema directly
                print(f"  ⚠️  ALTER TABLE failed, trying schema update: {e}")
                new_schema = list(table.schema)
                new_schema.append(bigquery.SchemaField(col_name, col_type, mode="NULLABLE"))
                table.schema = new_schema
                client.update_table(table, ["schema"])
                print(f"  ✅ Added column via schema update: {col_name}")
        
        print()
        print("=" * 60)
        print("✅ Columns added successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    add_new_columns()

