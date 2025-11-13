"""
GDPR deletion orchestrator.

Coordinates deletion requests across Mixpanel, Singular, and BigQuery,
and tracks the status in BigQuery.
"""

import logging
from typing import List, Dict, Any
from datetime import datetime

from .mixpanel import MixpanelClient
from .singular import SingularClient
from .bigquery import BigQueryClient

logger = logging.getLogger(__name__)


class GDPROrchestrator:
    """Orchestrates GDPR deletion requests across multiple platforms."""

    def __init__(
        self,
        mixpanel_client: MixpanelClient,
        singular_client: SingularClient,
        bigquery_client: BigQueryClient
    ):
        """
        Initialize the orchestrator.

        Args:
            mixpanel_client: Configured Mixpanel client
            singular_client: Configured Singular client
            bigquery_client: Configured BigQuery client
        """
        self.mixpanel = mixpanel_client
        self.singular = singular_client
        self.bigquery = bigquery_client

    def process_deletion_request(
        self,
        user_id: str,
        bigquery_tables: List[str],
        user_id_column: str = "user_id",
        singular_id_type: str = "user_id"
    ) -> Dict[str, Any]:
        """
        Process a complete GDPR deletion request for a single user.

        Args:
            user_id: The user ID to delete
            bigquery_tables: List of BigQuery tables to delete from
            user_id_column: Column name for user ID in BigQuery tables
            singular_id_type: Type of identifier for Singular API

        Returns:
            Dictionary containing results from all platforms
        """
        logger.info(f"Starting GDPR deletion process for user {user_id}")

        result = {
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat(),
            "mixpanel": {},
            "singular": {},
            "bigquery": {},
            "overall_success": True
        }

        # Update status to in_progress
        self.bigquery.update_deletion_status(user_id, "in_progress")

        # Step 1: Create Mixpanel deletion request
        try:
            logger.info(f"Creating Mixpanel deletion request for user {user_id}")
            mixpanel_result = self.mixpanel.create_deletion_request(user_id)
            result["mixpanel"] = mixpanel_result

            if not mixpanel_result.get("success"):
                result["overall_success"] = False

        except Exception as e:
            logger.error(f"Mixpanel deletion failed for user {user_id}: {e}")
            result["mixpanel"] = {"success": False, "error": str(e)}
            result["overall_success"] = False

        # Step 2: Create Singular deletion request
        try:
            logger.info(f"Creating Singular deletion request for user {user_id}")
            singular_result = self.singular.create_deletion_request(
                user_id,
                singular_id_type
            )
            result["singular"] = singular_result

            if not singular_result.get("success"):
                result["overall_success"] = False

        except Exception as e:
            logger.error(f"Singular deletion failed for user {user_id}: {e}")
            result["singular"] = {"success": False, "error": str(e)}
            result["overall_success"] = False

        # Step 3: Delete data from BigQuery
        try:
            logger.info(f"Deleting BigQuery data for user {user_id}")
            bigquery_result = self.bigquery.delete_user_data(
                user_id,
                bigquery_tables,
                user_id_column
            )
            result["bigquery"] = bigquery_result

            if not bigquery_result.get("success"):
                result["overall_success"] = False

        except Exception as e:
            logger.error(f"BigQuery deletion failed for user {user_id}: {e}")
            result["bigquery"] = {"success": False, "error": str(e)}
            result["overall_success"] = False

        # Step 4: Update deletion status in BigQuery
        try:
            status = "completed" if result["overall_success"] else "failed"
            error_message = None

            if not result["overall_success"]:
                errors = []
                if not result["mixpanel"].get("success"):
                    errors.append(f"Mixpanel: {result['mixpanel'].get('error', 'unknown error')}")
                if not result["singular"].get("success"):
                    errors.append(f"Singular: {result['singular'].get('error', 'unknown error')}")
                if not result["bigquery"].get("success"):
                    errors.append(f"BigQuery: {result['bigquery'].get('error', 'unknown error')}")
                error_message = "; ".join(errors)

            self.bigquery.update_deletion_status(
                user_id,
                status,
                mixpanel_result=result["mixpanel"],
                singular_result=result["singular"],
                bigquery_result=result["bigquery"],
                error_message=error_message
            )

            logger.info(f"GDPR deletion process completed for user {user_id}: {status}")

        except Exception as e:
            logger.error(f"Failed to update deletion status for user {user_id}: {e}")

        return result

    def process_batch_deletion(
        self,
        user_ids: List[str],
        bigquery_tables: List[str],
        user_id_column: str = "user_id",
        singular_id_type: str = "user_id"
    ) -> List[Dict[str, Any]]:
        """
        Process GDPR deletion requests for multiple users.

        Args:
            user_ids: List of user IDs to delete
            bigquery_tables: List of BigQuery tables to delete from
            user_id_column: Column name for user ID in BigQuery tables
            singular_id_type: Type of identifier for Singular API

        Returns:
            List of results for each user
        """
        logger.info(f"Starting batch GDPR deletion for {len(user_ids)} users")

        results = []
        for user_id in user_ids:
            result = self.process_deletion_request(
                user_id,
                bigquery_tables,
                user_id_column,
                singular_id_type
            )
            results.append(result)

        success_count = sum(1 for r in results if r.get("overall_success"))
        logger.info(
            f"Batch GDPR deletion completed: "
            f"{success_count}/{len(user_ids)} successful"
        )

        return results

    def get_deletion_status(self, user_id: str) -> Dict[str, Any]:
        """
        Get the current deletion status for a user.

        Args:
            user_id: The user ID to check

        Returns:
            Dictionary containing the status information
        """
        return self.bigquery.get_deletion_status(user_id)

    def setup_status_table(self) -> bool:
        """
        Create the status tracking table if it doesn't exist.

        Returns:
            True if successful, False otherwise
        """
        return self.bigquery.create_status_table()
