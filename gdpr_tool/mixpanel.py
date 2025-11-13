"""
Mixpanel GDPR deletion integration.

Handles deletion requests to Mixpanel via their GDPR API.
API Documentation: https://developer.mixpanel.com/reference/delete-user-gdpr-api
"""

import requests
import logging
from typing import List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class MixpanelClient:
    """Client for Mixpanel GDPR API operations."""

    def __init__(self, project_id: str, token: str, api_secret: str):
        """
        Initialize Mixpanel client.

        Args:
            project_id: Mixpanel project ID
            token: Mixpanel project token
            api_secret: Mixpanel API secret for authentication
        """
        self.project_id = project_id
        self.token = token
        self.api_secret = api_secret
        self.base_url = "https://mixpanel.com/api/app/data-retrievals/v3.0"

    def create_deletion_request(self, user_id: str) -> Dict[str, Any]:
        """
        Create a GDPR deletion request for a user.

        Args:
            user_id: The distinct_id of the user to delete

        Returns:
            Dictionary containing the deletion task ID and status

        Raises:
            requests.RequestException: If the API request fails
        """
        url = f"{self.base_url}/?token={self.token}"

        payload = {
            "distinct_ids": [user_id],
            "compliance_type": "GDPR"
        }

        headers = {
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                auth=(self.api_secret, ''),
                timeout=30
            )

            response.raise_for_status()
            result = response.json()

            logger.info(f"Mixpanel deletion request created for user {user_id}: {result}")

            return {
                "success": True,
                "user_id": user_id,
                "task_id": result.get("results", [{}])[0].get("task_id"),
                "status": result.get("status"),
                "timestamp": datetime.utcnow().isoformat()
            }

        except requests.RequestException as e:
            logger.error(f"Failed to create Mixpanel deletion request for user {user_id}: {e}")
            return {
                "success": False,
                "user_id": user_id,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    def batch_delete_users(self, user_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Create deletion requests for multiple users.

        Args:
            user_ids: List of user distinct_ids to delete

        Returns:
            List of results for each user deletion request
        """
        results = []

        for user_id in user_ids:
            result = self.create_deletion_request(user_id)
            results.append(result)

        success_count = sum(1 for r in results if r.get("success"))
        logger.info(
            f"Mixpanel batch deletion completed: "
            f"{success_count}/{len(user_ids)} successful"
        )

        return results

    def check_deletion_status(self, task_id: str) -> Dict[str, Any]:
        """
        Check the status of a deletion request.

        Args:
            task_id: The task ID returned from create_deletion_request

        Returns:
            Dictionary containing the current status of the deletion task
        """
        url = f"{self.base_url}/{task_id}?token={self.token}"

        try:
            response = requests.get(
                url,
                auth=(self.api_secret, ''),
                timeout=30
            )

            response.raise_for_status()
            result = response.json()

            logger.info(f"Mixpanel deletion status for task {task_id}: {result}")

            return {
                "success": True,
                "task_id": task_id,
                "status": result.get("status"),
                "timestamp": datetime.utcnow().isoformat()
            }

        except requests.RequestException as e:
            logger.error(f"Failed to check Mixpanel deletion status for task {task_id}: {e}")
            return {
                "success": False,
                "task_id": task_id,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
