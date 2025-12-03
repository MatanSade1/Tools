"""
Create new version CSV from BigQuery for comparative validation.
"""

import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account
from datetime import datetime
from pathlib import Path

# Configuration
project_id = 'yotam-395120'
dataset_id = 'peerplay'
table_id = 'data_validation_yotam_new_version03621'
service_account_path = 'yotam-395120-0c59ae7bb76e.json'
output_csv = 'game_data_new.csv'

def extract_data_from_bigquery():
    """Extract data from BigQuery and save to CSV"""
    print("Authenticating with BigQuery...")
    credentials = service_account.Credentials.from_service_account_file(
        service_account_path, scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    
    client = bigquery.Client(credentials=credentials, project=project_id)
    
    print(f"Extracting data from {project_id}.{dataset_id}.{table_id}...")
    
    # First, get the total number of rows
    count_query = f"""
    SELECT COUNT(*) as total_rows
    FROM `{project_id}.{dataset_id}.{table_id}`
    """
    total_rows = client.query(count_query).result().to_dataframe()['total_rows'].iloc[0]
    print(f"Total rows to process: {total_rows:,}")
    
    # Now get the actual data with progress tracking
    query = f"""
    SELECT *
    FROM `{project_id}.{dataset_id}.{table_id}`
    """
    
    print("Starting data extraction...")
    start_time = datetime.now()
    
    # Use the BigQuery Storage API for better performance
    df = client.query(query).to_dataframe(
        progress_bar_type='tqdm',
        create_bqstorage_client=True
    )
    
    end_time = datetime.now()
    duration = end_time - start_time
    
    print(f"\nData extraction completed:")
    print(f"- Retrieved {len(df):,} rows with {len(df.columns)} columns")
    print(f"- Duration: {duration}")
    print(f"- Average speed: {len(df)/duration.total_seconds():.2f} rows/second")
    
    # Save to CSV
    print(f"\nSaving data to {output_csv}...")
    df.to_csv(output_csv, index=False)
    print(f"Data saved successfully to {output_csv}")
    
    return df

def main():
    """Main function to create new version CSV."""
    # Check if old version exists
    if not Path('game_data.csv').exists():
        print("Error: game_data.csv (old version) not found!")
        print("Please ensure the old version CSV exists before running this script.")
        return
    
    print("Creating new version CSV...")
    df = extract_data_from_bigquery()
    
    print("\nSummary:")
    print(f"- Old version: game_data.csv")
    print(f"- New version: {output_csv}")
    print("\nYou can now run comparative validation using:")
    print(f"python3 compare_validate.py game_data.csv {output_csv}")

if __name__ == '__main__':
    main() 