"""API clients for Mixpanel and Singular GDPR deletion requests."""
import os
import uuid
import requests
from typing import Optional, Dict
from datetime import datetime, timezone
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


def create_singular_gdpr_request(distinct_id: str, property_id: Optional[str] = None) -> Optional[str]:
    """
    Create a GDPR deletion request in Singular using OpenDSR API.
    
    Args:
        distinct_id: The user's distinct_id (used as user_id in Singular)
        property_id: Optional property_id (e.g., "Android:com.peerplay.megamerge" or "iOS:com.peerplay.game")
                   If not provided, will try to fetch from dim_player based on last_platform
    
    Returns:
        subject_request_id if successful, None otherwise
    """
    config = get_config()
    api_key = config.get("singular_api_key") or config.get("singular_api_secret")
    
    if not api_key:
        raise ValueError("SINGULAR_API_KEY (or SINGULAR_API_SECRET) must be configured")
    
    # If property_id not provided, try to fetch from dim_player
    if not property_id:
        try:
            from shared.bigquery_client import get_bigquery_client
            client = get_bigquery_client()
            query = f"""
            SELECT last_platform
            FROM `peerplay.dim_player`
            WHERE distinct_id = @distinct_id
            LIMIT 1
            """
            from google.cloud import bigquery
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("distinct_id", "STRING", distinct_id),
                ]
            )
            results = client.query(query, job_config=job_config).result()
            row = next(results, None)
            if row and row.last_platform:
                platform = row.last_platform
                # Map platform to property_id
                if platform.lower() in ["android", "google"]:
                    property_id = "Android:com.peerplay.megamerge"
                elif platform.lower() in ["ios", "apple"]:
                    property_id = "iOS:com.peerplay.game"
                else:
                    print(f"⚠️  Unknown platform '{platform}', defaulting to Android")
                    property_id = "Android:com.peerplay.megamerge"
            else:
                print(f"⚠️  No platform found for user {distinct_id}, defaulting to Android")
                property_id = "Android:com.peerplay.megamerge"
        except Exception as e:
            print(f"⚠️  Error fetching platform for {distinct_id}: {e}, defaulting to Android")
            property_id = "Android:com.peerplay.megamerge"
    
    if property_id:
        print(f"📱 Detected platform: {property_id.split(':')[0]} → Using property_id: {property_id}")
    
    # Validate inputs
    if not property_id or not property_id.strip():
        raise ValueError("property_id cannot be empty")
    if not distinct_id or not distinct_id.strip():
        raise ValueError("distinct_id cannot be empty")
    
    # Singular GDPR API endpoint
    url = "https://gdpr.singular.net/api/gdpr/requests"
    
    # Singular uses API key directly in Authorization header (not Bearer token)
    headers = {
        "Content-Type": "application/json",
        "Authorization": api_key
    }
    
    # OpenDSR request payload - Singular requires full OpenDSR format
    subject_request_id = str(uuid.uuid4())
    submitted_time = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    
    payload = {
        "subject_request_id": subject_request_id,
        "subject_request_type": "erasure",
        "submitted_time": submitted_time,
        "subject_identities": [
            {
                "identity_type": "user_id",
                "identity_value": distinct_id.strip(),
                "identity_format": "raw"
            }
        ],
        "property_id": property_id.strip()
    }
    
    try:
        # Debug: Print payload being sent
        print(f"   Sending OpenDSR payload: property_id={property_id}, user_id={distinct_id}")
        print(f"   Subject request ID: {subject_request_id}")
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        # Singular returns the subject_request_id we sent (or may return it in response)
        returned_request_id = result.get("subject_request_id") or subject_request_id
        
        if returned_request_id:
            print(f"✅ Created Singular GDPR request for {distinct_id}: {returned_request_id}")
            return str(returned_request_id)
        else:
            print(f"⚠️  Singular GDPR request created but no subject_request_id in response: {result}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error creating Singular GDPR request for {distinct_id}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                print(f"   Error details: {error_detail}")
                # Print full response for debugging
                print(f"   Response status: {e.response.status_code}")
                print(f"   Response headers: {dict(e.response.headers)}")
            except:
                print(f"   Response text: {e.response.text[:500]}")
                print(f"   Response status: {e.response.status_code}")
        return None


def check_mixpanel_gdpr_status(task_id: str) -> Optional[str]:
    """
    Check the status of a Mixpanel GDPR deletion request.
    
    Args:
        task_id: The task_id returned when creating the deletion request
    
    Returns:
        "completed" or "pending" if successful, None otherwise
    """
    config = get_config()
    oauth_token = config.get("mixpanel_gdpr_token")
    project_token = os.getenv("MIXPANEL_PROJECT_TOKEN") or config.get("mixpanel_project_id")
    
    if not project_token:
        project_token = "0e73d8fa8567c5bf2820b408701fa7be"  # Default project token
    
    if not oauth_token:
        print("⚠️  MIXPANEL_GDPR_TOKEN not configured, cannot check status")
        return None
    
    url = f"https://mixpanel.com/api/app/data-deletions/v3.0/{task_id}?token={project_token}"
    headers = {"Authorization": f"Bearer {oauth_token}"}
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        # Extract status from response - Mixpanel returns status in results.status
        results_data = result.get("results", {})
        status = results_data.get("status") or result.get("status")
        
        # Normalize to lowercase for comparison
        status_lower = str(status).lower() if status else None
        
        # Check if completed - Mixpanel returns "SUCCESS" (uppercase) when completed
        if status_lower in ["completed", "success", "done"] or status == "SUCCESS":
            return "completed"
        elif status_lower in ["pending", "in_progress", "processing"]:
            return "pending"
        else:
            print(f"⚠️  Unknown Mixpanel status: {status}")
            return "pending"
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error checking Mixpanel status for {task_id}: {e}")
        return None


def check_singular_gdpr_status(subject_request_id: str) -> Optional[str]:
    """
    Check the status of a Singular GDPR deletion request.
    
    Args:
        subject_request_id: The subject_request_id returned when creating the deletion request
    
    Returns:
        "completed" or "pending" if successful, None otherwise
    """
    config = get_config()
    api_key = config.get("singular_api_key") or config.get("singular_api_secret")
    
    if not api_key:
        print("⚠️  SINGULAR_API_KEY not configured, cannot check status")
        return None
    
    url = f"https://gdpr.singular.net/api/gdpr/requests/{subject_request_id}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": api_key
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        # Extract status from response
        status = result.get("status") or result.get("request_status")
        
        if status in ["completed", "success", "done", "fulfilled"]:
            return "completed"
        elif status in ["pending", "in_progress", "processing", "received"]:
            return "pending"
        else:
            print(f"⚠️  Unknown Singular status: {status}")
            return "pending"
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error checking Singular status for {subject_request_id}: {e}")
        return None

