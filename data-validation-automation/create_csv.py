"""
Extract and split game data by version for comparative validation.
Uses intelligent sampling to get representative data from each version.
"""

import pandas as pd
import numpy as np
from google.cloud import bigquery
from google.oauth2 import service_account
from datetime import datetime
from pathlib import Path
import argparse
import math

# Configuration
project_id = 'yotam-395120'
dataset_id = 'peerplay'
table_id = 'vmp_master_event_normalized'
service_account_path = 'yotam-395120-0c59ae7bb76e.json'
TARGET_SAMPLE_SIZE = 10000  # Target 10K rows per version (default sample size)

def get_version_row_count(client: bigquery.Client, version: str, start_date: str, end_date: str) -> int:
    """Get the total number of rows for a specific version within the date range."""
    # Try to convert version to float, if it fails, use it as string
    try:
        version_float = float(version)
        version_filter = f"version_float = {version_float}"
    except ValueError:
        # If version can't be converted to float, use string comparison
        version_filter = f"CAST(version_float AS STRING) = '{version}'"
    
    query = f"""
    SELECT COUNT(*) as count
    FROM `{project_id}.{dataset_id}.{table_id}`
    WHERE {version_filter}
      AND date BETWEEN '{start_date}' AND '{end_date}'
    """
    
    count_df = client.query(query).result().to_dataframe()
    return count_df['count'].iloc[0]

def calculate_sampling_denominator(total_rows: int, target_rows: int) -> int:
    """Calculate the sampling denominator to get approximately target_rows."""
    if total_rows == 0 or target_rows == 0:
        return 1  # Return 1 to avoid division by zero
    return math.ceil(total_rows / target_rows)

def extract_data_from_bigquery(old_version: str, new_version: str, start_date: str, end_date: str, sample_size: int = None, preserve_purchase_events: bool = False) -> pd.DataFrame:
    """
    Extract data from BigQuery for both versions using intelligent sampling.
    
    Args:
        old_version: Version number (e.g., '0.3615')
        new_version: Version number (e.g., '0.3621')
        start_date: Start date for filtering events (YYYY-MM-DD)
        end_date: End date for filtering events (YYYY-MM-DD)
        sample_size: Number of rows to sample per version (overrides TARGET_SAMPLE_SIZE)
        preserve_purchase_events: If True, always include all purchase_successful events (may exceed sample size)
    """
    # Use custom sample size if provided, otherwise use default
    target_sample_size = sample_size if sample_size is not None else TARGET_SAMPLE_SIZE
    print("Authenticating with BigQuery...")
    credentials = service_account.Credentials.from_service_account_file(
        service_account_path, scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    
    client = bigquery.Client(credentials=credentials, project=project_id)
    
    # Get row counts for each version
    print("\nCounting rows in each version...")
    old_count = get_version_row_count(client, old_version, start_date, end_date)
    new_count = get_version_row_count(client, new_version, start_date, end_date)
    
    print(f"\nTotal rows found:")
    print(f"- Version {old_version}: {old_count:,} rows")
    print(f"- Version {new_version}: {new_count:,} rows")
    
    # Check if we have any data
    if old_count == 0 and new_count == 0:
        raise ValueError(
            f"No data found for versions {old_version} and {new_version} "
            f"in date range {start_date} to {end_date}. "
            f"Please verify:\n"
            f"1. The version numbers are correct (they may be stored as 0.37250 instead of 0.37.250)\n"
            f"2. The date range contains data for these versions\n"
            f"3. The versions exist in the database"
        )
    elif old_count == 0:
        raise ValueError(f"No data found for old version {old_version} in date range {start_date} to {end_date}")
    elif new_count == 0:
        raise ValueError(f"No data found for new version {new_version} in date range {start_date} to {end_date}")
    
    # Calculate sampling denominators
    old_denominator = calculate_sampling_denominator(old_count, target_sample_size)
    new_denominator = calculate_sampling_denominator(new_count, target_sample_size)
    
    print(f"\nSampling configuration:")
    print(f"- Old version ({old_version}): sampling ~1/{old_denominator} of data")
    print(f"- New version ({new_version}): sampling ~1/{new_denominator} of data")
    
    date_filter = f" AND date BETWEEN '{start_date}' AND '{end_date}'"
    
    # Helper function to create version filter
    def get_version_filter(version: str) -> str:
        try:
            version_float = float(version)
            return f"version_float = {version_float}"
        except ValueError:
            # If version can't be converted to float, use string comparison
            return f"CAST(version_float AS STRING) = '{version}'"
    
    old_version_filter = get_version_filter(old_version)
    new_version_filter = get_version_filter(new_version)
    
    if preserve_purchase_events:
        print(f"\n🛒 PRESERVE PURCHASE EVENTS MODE ENABLED")
        print(f"- All purchase_successful events will be included")
        print(f"- Additional sampling will fill remaining quota")
        print(f"- Total dataset may exceed {target_sample_size * 2:,} rows")
        
        # Query to get purchase events + sampled other events for both versions
        query = f"""
        WITH OldVersionPurchases AS (
            SELECT *, '{old_version}' as source_version, 'purchase' as sample_type
            FROM `{project_id}.{dataset_id}.{table_id}`
            WHERE {old_version_filter}
              AND mp_event_name = 'purchase_successful'
              {date_filter}
        ),
        OldVersionOtherSample AS (
            SELECT *, '{old_version}' as source_version, 'sampled' as sample_type
            FROM `{project_id}.{dataset_id}.{table_id}`
            WHERE {old_version_filter}
              AND mp_event_name != 'purchase_successful'
              AND MOD(ABS(FARM_FINGERPRINT(CAST(res_timestamp AS STRING))), {old_denominator}) = 0
              {date_filter}
            LIMIT {target_sample_size}
        ),
        NewVersionPurchases AS (
            SELECT *, '{new_version}' as source_version, 'purchase' as sample_type
            FROM `{project_id}.{dataset_id}.{table_id}`
            WHERE {new_version_filter}
              AND mp_event_name = 'purchase_successful'
              {date_filter}
        ),
        NewVersionOtherSample AS (
            SELECT *, '{new_version}' as source_version, 'sampled' as sample_type
            FROM `{project_id}.{dataset_id}.{table_id}`
            WHERE {new_version_filter}
              AND mp_event_name != 'purchase_successful'
              AND MOD(ABS(FARM_FINGERPRINT(CAST(res_timestamp AS STRING))), {new_denominator}) = 0
              {date_filter}
            LIMIT {target_sample_size}
        )
        SELECT * FROM OldVersionPurchases
        UNION ALL
        SELECT * FROM OldVersionOtherSample
        UNION ALL
        SELECT * FROM NewVersionPurchases
        UNION ALL
        SELECT * FROM NewVersionOtherSample
        """
    else:
        # Original sampling logic
        query = f"""
        WITH OldVersionSample AS (
            SELECT *, '{old_version}' as source_version, 'sampled' as sample_type
            FROM `{project_id}.{dataset_id}.{table_id}`
            WHERE {old_version_filter}
              AND MOD(ABS(FARM_FINGERPRINT(CAST(res_timestamp AS STRING))), {old_denominator}) = 0
              {date_filter}
            LIMIT {target_sample_size}
        ),
        NewVersionSample AS (
            SELECT *, '{new_version}' as source_version, 'sampled' as sample_type
            FROM `{project_id}.{dataset_id}.{table_id}`
            WHERE {new_version_filter}
              AND MOD(ABS(FARM_FINGERPRINT(CAST(res_timestamp AS STRING))), {new_denominator}) = 0
              {date_filter}
            LIMIT {target_sample_size}
        )
        SELECT * FROM OldVersionSample
        UNION ALL
        SELECT * FROM NewVersionSample
        """
    
    print("\nStarting data extraction...")
    if preserve_purchase_events:
        print(f"Expected rows: ~{target_sample_size * 2:,} + all purchase_successful events")
    else:
        print(f"Expected rows: ~{target_sample_size * 2:,} total")
    start_time = datetime.now()
    
    # Configure query job with timeout
    job_config = bigquery.QueryJobConfig()
    job_config.use_query_cache = True
    job_config.use_legacy_sql = False
    
    # Use standard BigQuery API (more stable for large datasets)
    df = client.query(query, job_config=job_config).to_dataframe(
        progress_bar_type='tqdm',
        create_bqstorage_client=False
    )
    
    print("✓ DataFrame download completed, processing...")
    
    end_time = datetime.now()
    duration = end_time - start_time
    
    print(f"\nData extraction completed:")
    print(f"- Retrieved {len(df):,} total rows")
    print(f"- Memory usage: {df.memory_usage(deep=True).sum() / 1024**2:.1f} MB")
    
    # Count versions efficiently (avoid creating multiple filtered DataFrames)
    version_counts = df['version_float'].value_counts()
    # Try to convert versions to float for comparison, otherwise use string matching
    try:
        old_version_float = float(old_version)
        new_version_float = float(new_version)
        old_count = version_counts.get(old_version_float, 0)
        new_count = version_counts.get(new_version_float, 0)
    except ValueError:
        # If versions can't be converted to float, match by string
        old_count = len(df[df['version_float'].astype(str) == old_version])
        new_count = len(df[df['version_float'].astype(str) == new_version])
    
    print(f"- Old version ({old_version}): {old_count:,} rows")
    print(f"- New version ({new_version}): {new_count:,} rows")
    
    # Show purchase event statistics if preserve mode was enabled
    if preserve_purchase_events and 'sample_type' in df.columns:
        purchase_counts = df[df['sample_type'] == 'purchase']['version_float'].value_counts()
        try:
            old_version_float = float(old_version)
            new_version_float = float(new_version)
            old_purchases = purchase_counts.get(old_version_float, 0)
            new_purchases = purchase_counts.get(new_version_float, 0)
        except ValueError:
            purchase_df = df[df['sample_type'] == 'purchase']
            old_purchases = len(purchase_df[purchase_df['version_float'].astype(str) == old_version])
            new_purchases = len(purchase_df[purchase_df['version_float'].astype(str) == new_version])
        total_purchases = old_purchases + new_purchases
        
        print(f"\n🛒 Purchase Events Preserved:")
        print(f"- Old version purchase_successful: {old_purchases:,} events")
        print(f"- New version purchase_successful: {new_purchases:,} events") 
        print(f"- Total purchase events: {total_purchases:,} events")
        
        if total_purchases > 0:
            total_expected = target_sample_size * 2
            excess = len(df) - total_expected
            if excess > 0:
                print(f"- Dataset exceeded target by {excess:,} rows due to preserved purchases")
            print(f"- Purchase events represent {(total_purchases/len(df)*100):.2f}% of dataset")
    print(f"- Duration: {duration}")
    print(f"- Average speed: {len(df)/duration.total_seconds():.2f} rows/second")
    print("- Proceeding to split and save data...")
    print(f"- DataFrame shape: {df.shape}")
    print(f"- DataFrame columns: {len(df.columns)}")
    
    # Simplified dtypes summary to avoid memory overhead
    print(f"- Data types: {len(df.dtypes.unique())} unique types")
    
    return df

def split_and_save_versions(df: pd.DataFrame, old_version: str, new_version: str):
    """
    Split the data by version and save to separate CSV files.
    
    Args:
        df: DataFrame containing both versions
        old_version: Old version number
        new_version: New version number
    """
    print(f"\n{'='*50}")
    print("ENTERING split_and_save_versions function")
    print(f"DataFrame received: {df.shape[0]:,} rows x {df.shape[1]} columns")
    print(f"Memory usage: {df.memory_usage(deep=True).sum() / 1024**2:.1f} MB")
    print(f"{'='*50}")
    
    print("\nSplitting data by version...")
    
    # Create output directory if it doesn't exist
    output_dir = Path('data')
    output_dir.mkdir(exist_ok=True)
    
    # Split and save old version
    print(f"Filtering data for old version ({old_version})...")
    try:
        old_version_float = float(old_version)
        old_df = df[df['version_float'] == old_version_float]
    except ValueError:
        old_df = df[df['version_float'].astype(str) == old_version]
    old_file = output_dir / 'game_data_old.csv'
    print(f"\nSaving old version ({old_version}):")
    print(f"- {len(old_df):,} rows")
    print(f"- Output file: {old_file}")
    print("- Writing CSV file... (this may take a few minutes)")
    start_time = datetime.now()
    old_df.to_csv(old_file, index=False)
    print(f"- Old version saved in {datetime.now() - start_time}")
    
    # Split and save new version
    print(f"Filtering data for new version ({new_version})...")
    try:
        new_version_float = float(new_version)
        new_df = df[df['version_float'] == new_version_float]
    except ValueError:
        new_df = df[df['version_float'].astype(str) == new_version]
    new_file = output_dir / 'game_data_new.csv'
    print(f"\nSaving new version ({new_version}):")
    print(f"- {len(new_df):,} rows")
    print(f"- Output file: {new_file}")
    print("- Writing CSV file... (this may take a few minutes)")
    start_time = datetime.now()
    new_df.to_csv(new_file, index=False)
    print(f"- New version saved in {datetime.now() - start_time}")
    
    print("\nData split and saved successfully!")
    print("\nYou can now run comparative validation using:")
    print(f"python3 compare_validate.py data/game_data_old.csv data/game_data_new.csv")

def main():
    """Main function to extract and split game data by version."""
    parser = argparse.ArgumentParser(description='Extract and split game data by version for validation.')
    parser.add_argument('old_version', help='Old version number (e.g., 0.3615)')
    parser.add_argument('new_version', help='New version number (e.g., 0.3621)')
    parser.add_argument('--start-date', type=str, required=True, help='(Required) Start date for filtering events (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, required=True, help='(Required) End date for filtering events (YYYY-MM-DD)')
    
    args = parser.parse_args()
    
    try:
        # Extract data for both versions
        df = extract_data_from_bigquery(args.old_version, args.new_version, args.start_date, args.end_date)
        
        # Split and save by version
        split_and_save_versions(df, args.old_version, args.new_version)
        
    except Exception as e:
        print(f"\nError: {str(e)}")
        return 1
    
    return 0

if __name__ == '__main__':
    import sys
    sys.exit(main())