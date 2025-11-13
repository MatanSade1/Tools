"""
Singular GDPR deletion integration.

Handles deletion requests to Singular via their GDPR API.
API Documentation: https://support.singular.net/hc/en-us/articles/360037587312-GDPR-Data-Deletion
"""

import requests
import logging
from typing import List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class SingularClient:
    """Client for Singular GDPR API operations."""

    def __init__(self, api_key: str):
        """
        Initialize Singular client.

        Args:
            api_key: Singular API key for authentication
        """
        self.api_key = api_key
        self.base_url = "https://api.singular.net/api/v1/gdpr"

    def create_deletion_request(self, user_id: str, id_type: str = "user_id") -> Dict[str, Any]:
        """
        Create a GDPR deletion request for a user.

        Args:
            user_id: The user identifier to delete
            id_type: Type of identifier (user_id, idfa, idfv, gaid, etc.)

        Returns:
            Dictionary containing the deletion request status

        Raises:
            requests.RequestException: If the API request fails
        """
        url = f"{self.base_url}/delete"

        payload = {
            "identifiers": [
                {
                    "type": id_type,
                    "value": user_id
                }
            ]
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=30
            )

            response.raise_for_status()
            result = response.json()

            logger.info(f"Singular deletion request created for user {user_id}: {result}")

            return {
                "success": True,
                "user_id": user_id,
                "id_type": id_type,
                "request_id": result.get("request_id"),
                "status": result.get("status", "submitted"),
                "timestamp": datetime.utcnow().isoformat()
            }

        except requests.RequestException as e:
            logger.error(f"Failed to create Singular deletion request for user {user_id}: {e}")
            return {
                "success": False,
                "user_id": user_id,
                "id_type": id_type,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    def batch_delete_users(
        self,
        user_ids: List[str],
        id_type: str = "user_id"
    ) -> List[Dict[str, Any]]:
        """
        Create deletion requests for multiple users.

        Args:
            user_ids: List of user identifiers to delete
            id_type: Type of identifier for all users

        Returns:
            List of results for each user deletion request
        """
        results = []

        for user_id in user_ids:
            result = self.create_deletion_request(user_id, id_type)
            results.append(result)

        success_count = sum(1 for r in results if r.get("success"))
        logger.info(
            f"Singular batch deletion completed: "
            f"{success_count}/{len(user_ids)} successful"
        )

        return results

    def check_deletion_status(self, request_id: str) -> Dict[str, Any]:
        """
        Check the status of a deletion request.

        Args:
            request_id: The request ID returned from create_deletion_request

        Returns:
            Dictionary containing the current status of the deletion request
        """
        url = f"{self.base_url}/status/{request_id}"

        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }

        try:
            response = requests.get(
                url,
                headers=headers,
                timeout=30
            )

            response.raise_for_status()
            result = response.json()

            logger.info(f"Singular deletion status for request {request_id}: {result}")

            return {
                "success": True,
                "request_id": request_id,
                "status": result.get("status"),
                "timestamp": datetime.utcnow().isoformat()
            }

        except requests.RequestException as e:
            logger.error(f"Failed to check Singular deletion status for request {request_id}: {e}")
            return {
                "success": False,
                "request_id": request_id,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
