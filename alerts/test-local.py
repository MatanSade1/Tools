#!/usr/bin/env python3
"""Simple test script to run rt-mp-collector locally"""

import sys
import os
import json

# Add project root to Python path
# Script is in alerts/, so go up one level to get project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Load environment variables from .env file if it exists
env_file = os.path.join(project_root, '.env')
if os.path.exists(env_file):
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file)
    except ImportError:
        # Fallback: manually parse .env file
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

def main():
    print("="*60)
    print("Testing rt-mp-collector locally")
    print("="*60)
    print()
    
    # Check environment variables
    required_vars = [
        "GCP_PROJECT_ID",
        "MIXPANEL_PROJECT_ID",
        "SLACK_WEBHOOK_URL"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print()
        print("Please set these variables or use the .env file")
        return 1
    
    if not os.getenv("MIXPANEL_API_SECRET") and not os.getenv("MIXPANEL_API_SECRET_NAME"):
        print("❌ Missing MIXPANEL_API_SECRET or MIXPANEL_API_SECRET_NAME")
        return 1
    
    print("✅ Environment variables verified")
    print()
    
    # Import and run
    # Note: Directory is rt-mp-collector (with hyphen), so we need to import differently
    try:
        import importlib.util
        collector_path = os.path.join(project_root, 'alerts', 'rt-mp-collector', 'main.py')
        spec = importlib.util.spec_from_file_location("rt_mp_collector_main", collector_path)
        rt_mp_collector_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rt_mp_collector_module)
        rt_mp_collector = rt_mp_collector_module.rt_mp_collector
        
        print("Running rt_mp_collector...")
        print("-"*60)
        
        result = rt_mp_collector(None)
        
        print()
        print("="*60)
        print("✅ Execution completed successfully!")
        print("="*60)
        print()
        print("Result:")
        print(json.dumps(result, indent=2))
        
        return 0
        
    except Exception as e:
        print()
        print("="*60)
        print("❌ Error during execution:")
        print("="*60)
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())

