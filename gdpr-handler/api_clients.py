"""API clients for Mixpanel and Singular GDPR deletion requests."""
import os
import requests
from typing import Optional, Dict
from shared.config import get_config


def create_mixpanel_gdpr_request(distinct_id: str, compliance_type: str = "gdpr") -> Optional[str]:
    """
    Create a GDPR deletion request in Mixpanel.
    
    Supports multiple authentication methods:
    1. OAuth Token (Bearer token) - from Profile & Preferences → Data & Privacy
    2. Service Account (Username + Secret) - from Project Settings → Service Accounts
    3. Export API Secret - from Project Settings → Service Accounts
    
    Args:
        distinct_id: The user's distinct_id in Mixpanel
        compliance_type: Type of compliance request (default: "gdpr")
    
    Returns:
        Request ID if successful, None otherwise
    """
    config = get_config()
    
    # Mixpanel GDPR API requires BOTH:
    # 1. Project token (in query parameter) - identifies the project
    # 2. OAuth token (in Bearer header) - authenticates the request
    
    # Get OAuth token (for Bearer authentication)
    oauth_token = config.get("mixpanel_gdpr_token")
    
    # Get project token (for query parameter)
    # Try MIXPANEL_PROJECT_TOKEN first, then fall back to mixpanel_project_id if it's a token
    project_token = os.getenv("MIXPANEL_PROJECT_TOKEN") or config.get("mixpanel_project_id")
    
    # If no explicit project token, use the default one we know
    if not project_token:
        project_token = "0e73d8fa8567c5bf2820b408701fa7be"  # Default project token
    
    # Try Service Account credentials (alternative method)
    service_account_username = config.get("mixpanel_service_account_username")
    service_account_secret = config.get("mixpanel_service_account_secret")
    
    # Try Export API Secret (alternative method)
    export_api_secret = config.get("mixpanel_api_secret")
    
    # Determine authentication method
    auth_method = None
    headers = {}
    auth = None
    url = "https://mixpanel.com/api/app/data-deletions/v3.0/"
    
    if oauth_token and project_token:
        # Method 1: OAuth Bearer token + Project token (recommended for GDPR API)
        auth_method = "oauth"
        headers["Authorization"] = f"Bearer {oauth_token}"
        url = f"{url}?token={project_token}"
    elif service_account_username and service_account_secret:
        # Method 2: Service Account Basic Auth
        auth_method = "service_account"
        auth = (service_account_username, service_account_secret)
        url = f"{url}?token={project_token}" if project_token else url
    elif export_api_secret:
        # Method 3: Export API Secret Basic Auth
        auth_method = "api_secret"
        auth = (export_api_secret, "")
        url = f"{url}?token={project_token}" if project_token else url
    else:
        raise ValueError(
            "Mixpanel GDPR API requires:\n"
            "  - MIXPANEL_GDPR_TOKEN (OAuth token from Profile & Preferences → Data & Privacy)\n"
            "  - MIXPANEL_PROJECT_TOKEN or MIXPANEL_PROJECT_ID (project token, default: 0e73d8fa8567c5bf2820b408701fa7be)\n"
            "  OR\n"
            "  - MIXPANEL_SERVICE_ACCOUNT_USERNAME + MIXPANEL_SERVICE_ACCOUNT_SECRET\n"
            "  - MIXPANEL_API_SECRET (Export API Secret)"
        )
    
    payload = {
        "distinct_ids": [distinct_id],  # API expects an array
        "compliance_type": compliance_type.upper()  # GDPR should be uppercase
    }
    
    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            auth=auth,
            timeout=30
        )
        response.raise_for_status()
        
        result = response.json()
        # Mixpanel v3.0 API returns task_id in results
        # Format: {'status': 'ok', 'results': {'task_id': '...'}}
        if result.get("status") == "ok" and result.get("results"):
            request_id = result["results"].get("task_id")
        else:
            # Fallback to other possible fields
            request_id = result.get("request_id") or result.get("id") or result.get("deletion_request_id") or result.get("task_id")
        
        if request_id:
            print(f"✅ Created Mixpanel GDPR request for {distinct_id}: {request_id}")
            return str(request_id)
        else:
            print(f"⚠️  Mixpanel GDPR request created but no request_id in response: {result}")
            return None
            
    except requests.exceptions.RequestException as e:
        # If v3.0 fails, try alternative endpoints
        error_status = None
        if hasattr(e, 'response') and e.response is not None:
            error_status = e.response.status_code
        
        # Try alternative endpoint with different auth
        if error_status in [403, 404, 401]:
            print(f"⚠️  v3.0 endpoint failed ({error_status}), trying alternative endpoint...")
            
            # Try with Basic Auth on v3.0 (without token in URL)
            if auth_method == "oauth" and auth:
                try:
                    response_alt = requests.post(
                        url,
                        json=payload,
                        auth=auth,
                        timeout=30
                    )
                    response_alt.raise_for_status()
                    result_alt = response_alt.json()
                    request_id = result_alt.get("request_id") or result_alt.get("id")
                    if request_id:
                        print(f"✅ Created Mixpanel GDPR request for {distinct_id}: {request_id}")
                        return str(request_id)
                except:
                    pass
        
        print(f"❌ Error creating Mixpanel GDPR request for {distinct_id}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                print(f"   Error details: {error_detail}")
            except:
                print(f"   Response: {e.response.text[:500]}")
        return None


def create_singular_gdpr_request(distinct_id: str) -> Optional[str]:
    """
    Create a GDPR deletion request in Singular using OpenDSR API.
    
    Args:
        distinct_id: The user's distinct_id (used as user_id in Singular)
    
    Returns:
        subject_request_id if successful, None otherwise
    """
    config = get_config()
    api_key = config.get("singular_api_key")
    api_secret = config.get("singular_api_secret")
    
    if not api_key or not api_secret:
        raise ValueError("SINGULAR_API_KEY and SINGULAR_API_SECRET (or their _NAME variants) must be configured")
    
    # Singular OpenDSR API endpoint
    url = "https://api.singular.net/api/v1/opendsr"
    
    # Singular uses Basic Auth with API key and secret
    auth = (api_key, api_secret)
    
    # OpenDSR request payload
    payload = {
        "request_type": "deletion",
        "regulation": "gdpr",
        "user_id": distinct_id,
        "user_id_type": "custom"
    }
    
    try:
        response = requests.post(url, auth=auth, json=payload, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        # Singular returns subject_request_id in the response
        subject_request_id = result.get("subject_request_id") or result.get("request_id")
        
        if subject_request_id:
            print(f"✅ Created Singular GDPR request for {distinct_id}: {subject_request_id}")
            return str(subject_request_id)
        else:
            print(f"⚠️  Singular GDPR request created but no subject_request_id in response: {result}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error creating Singular GDPR request for {distinct_id}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                print(f"   Error details: {error_detail}")
            except:
                print(f"   Response: {e.response.text}")
        return None

