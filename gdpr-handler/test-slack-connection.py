#!/usr/bin/env python3
"""Test script to verify Slack Bot Token configuration."""
import sys
import os
from shared.config import get_config
from shared.slack_client import get_channel_id, get_slack_bot_token

def test_slack_connection():
    """Test Slack Bot Token and channel access."""
    print("=" * 50)
    print("Slack Connection Test")
    print("=" * 50)
    print()
    
    # Check token
    print("1. Checking Slack Bot Token...")
    token = get_slack_bot_token()
    if not token:
        print("   ❌ ERROR: SLACK_BOT_TOKEN or SLACK_BOT_TOKEN_NAME not configured")
        print()
        print("   To fix:")
        print("   - Set SLACK_BOT_TOKEN environment variable, OR")
        print("   - Set SLACK_BOT_TOKEN_NAME and ensure Secret Manager is configured")
        return False
    
    if not token.startswith("xoxb-"):
        print(f"   ⚠️  WARNING: Token doesn't start with 'xoxb-'. Got: {token[:10]}...")
    else:
        print(f"   ✅ Token found: {token[:15]}...")
    print()
    
    # Test channel access
    print("2. Testing channel access...")
    channel_name = "users-to-delete-their-personal-data"
    try:
        channel_id = get_channel_id(channel_name)
        if channel_id:
            print(f"   ✅ Channel '{channel_name}' found: {channel_id}")
        else:
            print(f"   ❌ ERROR: Channel '{channel_name}' not found")
            print()
            print("   Possible issues:")
            print("   - Bot is not invited to the channel")
            print("   - Channel name is incorrect")
            print("   - Bot doesn't have 'channels:read' scope")
            return False
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False
    print()
    
    # Test API connection
    print("3. Testing Slack API connection...")
    try:
        from slack_sdk import WebClient
        client = WebClient(token=token)
        auth_test = client.auth_test()
        if auth_test.get("ok"):
            print(f"   ✅ Connected to workspace: {auth_test.get('team')}")
            print(f"   ✅ Bot user: {auth_test.get('user')}")
        else:
            print(f"   ❌ Auth test failed: {auth_test.get('error')}")
            return False
    except ImportError:
        print("   ⚠️  WARNING: slack-sdk not installed. Install with: pip install slack-sdk")
        return False
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False
    print()
    
    print("=" * 50)
    print("✅ All tests passed! Slack connection is working.")
    print("=" * 50)
    return True

if __name__ == "__main__":
    success = test_slack_connection()
    sys.exit(0 if success else 1)

