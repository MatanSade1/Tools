#!/usr/bin/env python3
"""Test script to verify AppLovin API key extraction from Secret Manager."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.config import get_config

def test_applovin_key_extraction():
    """Test that AppLovin API key can be extracted from Secret Manager or environment."""
    print("=" * 60)
    print("Testing AppLovin API Key Extraction")
    print("=" * 60)
    print()
    
    # Check environment variables
    print("1. Checking environment variables:")
    key_name = os.getenv("APPLOVIN_GDPR_API_KEY_NAME")
    key_direct = os.getenv("APPLOVIN_GDPR_API_KEY")
    project_id = os.getenv("GCP_PROJECT_ID", "yotam-395120")
    
    print(f"   APPLOVIN_GDPR_API_KEY_NAME: {key_name if key_name else '(not set)'}")
    print(f"   APPLOVIN_GDPR_API_KEY: {'*' * 20 if key_direct else '(not set)'}")
    print(f"   GCP_PROJECT_ID: {project_id}")
    print()
    
    # Get config
    print("2. Getting configuration from get_config():")
    try:
        config = get_config()
        applovin_key = config.get("applovin_gdpr_api_key")
        
        if applovin_key:
            print(f"   ✅ AppLovin API key found: {applovin_key[:10]}...{applovin_key[-5:] if len(applovin_key) > 15 else '***'}")
            print(f"   Key length: {len(applovin_key)} characters")
            print()
            print("   ✅ SUCCESS: AppLovin API key extraction works!")
            return True
        else:
            print("   ❌ AppLovin API key is None or empty")
            print()
            print("   ❌ FAILED: AppLovin API key not found")
            print()
            print("   To fix this:")
            if not key_name and not key_direct:
                print("   - Set APPLOVIN_GDPR_API_KEY_NAME='applovin-gdpr-api-key' (for Secret Manager)")
                print("   - OR set APPLOVIN_GDPR_API_KEY='your-key' (for direct env var)")
            elif key_name:
                print(f"   - Secret '{key_name}' may not exist in Secret Manager")
                print(f"   - Or you may not have permission to access it")
                print(f"   - Check: gcloud secrets describe {key_name} --project={project_id}")
            return False
    except Exception as e:
        print(f"   ❌ Error getting config: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_applovin_key_extraction()
    sys.exit(0 if success else 1)
