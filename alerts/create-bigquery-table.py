#!/usr/bin/env python3
"""Script to create the rt_mp_events table in BigQuery"""

import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# Load .env if exists
env_file = os.path.join(project_root, '.env')
if os.path.exists(env_file):
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file)
    except ImportError:
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

from shared.bigquery_client import ensure_rt_table_exists
from shared.config import get_config

def main():
    print("="*60)
    print("Creating BigQuery table: rt_mp_events")
    print("="*60)
    print()
    
    config = get_config()
    dataset_id = config.get("rt_mp_dataset", "peerplay")
    table_id = config.get("rt_mp_table", "rt_mp_events")
    project_id = config.get("gcp_project_id")
    
    print(f"Project ID: {project_id}")
    print(f"Dataset: {dataset_id}")
    print(f"Table: {table_id}")
    print(f"Full path: {project_id}.{dataset_id}.{table_id}")
    print()
    
    try:
        ensure_rt_table_exists()
        print()
        print("✅ Success! Table created or already exists.")
        print(f"   You can now query: SELECT * FROM `{project_id}.{dataset_id}.{table_id}` LIMIT 10")
    except Exception as e:
        print(f"❌ Error creating table: {e}")
        print()
        print("Possible issues:")
        print("1. BigQuery authentication not set up")
        print("   Run: gcloud auth application-default login")
        print("2. Dataset doesn't exist and you don't have permission to create it")
        print("3. Project ID is incorrect")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

