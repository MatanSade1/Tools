#!/usr/bin/env python3
"""Script to verify Mixpanel API secret and test authentication"""

import sys
import os
import requests
from datetime import datetime, timedelta

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

def test_mixpanel_auth():
    """Test Mixpanel authentication with different methods"""
    
    api_secret = os.getenv('MIXPANEL_API_SECRET', '')
    project_id = os.getenv('MIXPANEL_PROJECT_ID', '')
    
    if not api_secret:
        print("❌ MIXPANEL_API_SECRET not set")
        return
    
    if not project_id:
        print("❌ MIXPANEL_PROJECT_ID not set")
        return
    
    print("="*60)
    print("Mixpanel API Secret Verification")
    print("="*60)
    print()
    print(f"Project ID: {project_id}")
    print(f"API Secret (first 8 chars): {api_secret[:8]}...")
    print(f"Secret length: {len(api_secret)} characters")
    print()
    
    # Test date range (yesterday to today)
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')
    today = datetime.utcnow().strftime('%Y-%m-%d')
    
    url = 'https://api.mixpanel.com/api/2.0/export'
    params = {
        'from_date': yesterday,
        'to_date': today,
        'format': 'json'
    }
    
    print("Testing Export API authentication...")
    print(f"Date range: {yesterday} to {today}")
    print()
    
    try:
        response = requests.get(url, params=params, auth=(api_secret, ''), timeout=30)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text[:300]}")
        print()
        
        if response.status_code == 200:
            print("✅ SUCCESS! Authentication works!")
            print(f"   Received {len(response.text)} bytes of data")
        elif response.status_code == 401:
            print("❌ Authentication failed (401)")
            print()
            print("Possible issues:")
            print("1. This might be a Service Account secret, not Export API secret")
            print("2. The Export API secret might not be enabled for your project")
            print("3. The secret might have been rotated or expired")
            print()
            print("To fix:")
            print(f"   Go to: https://mixpanel.com/project/{project_id}/settings")
            print("   Navigate to: Project Settings → Service Accounts")
            print("   Look for: 'Export API Secret' (separate from Service Account)")
            print("   Ensure: Export API permissions are enabled")
        else:
            print(f"❌ Unexpected status: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_mixpanel_auth()

