#!/usr/bin/env python3
"""
Notion OAuth 2.0 flow implementation.
Handles authorization and token exchange.
"""

import os
import sys
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, urlencode
import requests
import json

# Configuration - SET THESE FROM YOUR NOTION INTEGRATION
NOTION_CLIENT_ID = os.getenv('NOTION_CLIENT_ID', 'YOUR_CLIENT_ID_HERE')
NOTION_CLIENT_SECRET = os.getenv('NOTION_CLIENT_SECRET', 'YOUR_CLIENT_SECRET_HERE')
REDIRECT_URI = 'http://localhost:8080/oauth/callback'

# Notion OAuth endpoints
AUTHORIZE_URL = 'https://api.notion.com/v1/oauth/authorize'
TOKEN_URL = 'https://api.notion.com/v1/oauth/token'

# Global to store the authorization code
auth_code = None


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Handle OAuth callback from Notion."""
    
    def do_GET(self):
        global auth_code
        
        # Parse the callback URL
        parsed_path = urlparse(self.path)
        params = parse_qs(parsed_path.query)
        
        if 'code' in params:
            auth_code = params['code'][0]
            
            # Send success response
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'''
                <html>
                <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                    <h1 style="color: green;">✅ Authorization Successful!</h1>
                    <p>You can close this window and return to the terminal.</p>
                </body>
                </html>
            ''')
        elif 'error' in params:
            error = params['error'][0]
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(f'''
                <html>
                <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                    <h1 style="color: red;">❌ Authorization Failed</h1>
                    <p>Error: {error}</p>
                </body>
                </html>
            '''.encode())
        
    def log_message(self, format, *args):
        # Suppress server logs
        pass


def get_authorization_url():
    """Generate the Notion authorization URL."""
    params = {
        'client_id': NOTION_CLIENT_ID,
        'response_type': 'code',
        'owner': 'user',
        'redirect_uri': REDIRECT_URI,
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def exchange_code_for_token(code):
    """Exchange authorization code for access token."""
    auth = (NOTION_CLIENT_ID, NOTION_CLIENT_SECRET)
    
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI,
    }
    
    response = requests.post(TOKEN_URL, auth=auth, json=data)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"❌ Error exchanging code: {response.status_code}")
        print(response.text)
        return None


def start_oauth_flow():
    """Start the OAuth flow."""
    global auth_code
    
    print("=" * 80)
    print("Notion OAuth 2.0 Authorization")
    print("=" * 80)
    print()
    
    # Step 1: Open browser for authorization
    auth_url = get_authorization_url()
    print("Opening browser for Notion authorization...")
    print(f"If browser doesn't open, visit: {auth_url}")
    print()
    webbrowser.open(auth_url)
    
    # Step 2: Start local server to receive callback
    print("Starting local server to receive callback...")
    print("Waiting for authorization...")
    print()
    
    server = HTTPServer(('localhost', 8080), OAuthCallbackHandler)
    server.handle_request()  # Handle one request and shut down
    
    if not auth_code:
        print("❌ Authorization failed: No code received")
        return None
    
    print("✅ Authorization code received")
    print()
    
    # Step 3: Exchange code for token
    print("Exchanging code for access token...")
    token_response = exchange_code_for_token(auth_code)
    
    if not token_response:
        return None
    
    # Save token
    access_token = token_response.get('access_token')
    workspace_name = token_response.get('workspace_name', 'Unknown')
    workspace_id = token_response.get('workspace_id')
    bot_id = token_response.get('bot_id')
    
    print("✅ Access token received!")
    print()
    print("Token Information:")
    print(f"  Workspace: {workspace_name}")
    print(f"  Workspace ID: {workspace_id}")
    print(f"  Bot ID: {bot_id}")
    print()
    
    # Save token to file
    token_file = '/Users/matansade/Tools/notion_token.json'
    with open(token_file, 'w') as f:
        json.dump(token_response, f, indent=2)
    
    print(f"✅ Token saved to: {token_file}")
    print()
    print("=" * 80)
    print("Authorization Complete!")
    print("=" * 80)
    print()
    print("Next step: Run fetch_notion_oauth.py to download the calendar data")
    
    return access_token


def main():
    if NOTION_CLIENT_ID == 'YOUR_CLIENT_ID_HERE':
        print("=" * 80)
        print("❌ Error: OAuth credentials not set")
        print("=" * 80)
        print()
        print("Please set your Notion OAuth credentials:")
        print()
        print("Option 1 - Environment variables:")
        print("  export NOTION_CLIENT_ID='your-client-id'")
        print("  export NOTION_CLIENT_SECRET='your-client-secret'")
        print()
        print("Option 2 - Edit this script:")
        print("  Open notion_oauth_flow.py and replace:")
        print("  NOTION_CLIENT_ID = 'YOUR_CLIENT_ID_HERE'")
        print("  NOTION_CLIENT_SECRET = 'YOUR_CLIENT_SECRET_HERE'")
        print()
        print("Get your credentials from: https://www.notion.so/my-integrations")
        print("=" * 80)
        sys.exit(1)
    
    access_token = start_oauth_flow()
    
    if not access_token:
        print("❌ OAuth flow failed")
        sys.exit(1)


if __name__ == '__main__':
    main()
