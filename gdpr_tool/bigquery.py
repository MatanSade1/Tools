"""
BigQuery data deletion and status tracking.

Handles:
1. Deletion of user data from specified BigQuery tables
2. Tracking deletion status in a dedicated status table
"""

from google.cloud import bigquery
from google.cloud.exceptions import GoogleCloudError
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class BigQueryClient:
    """Client for BigQuery data deletion and status tracking operations."""

    def __init__(
        self,
        project_id: str,
        credentials_path: Optional[str] = None,
        status_table: str = "gdpr_deletion_status"
    ):
        """
        Initialize BigQuery client.

        Args:
            project_id: GCP project ID
            credentials_path: Path to service account credentials JSON (optional)
            status_table: Fully qualified table name for status tracking
                         (format: dataset.table)
        """
        self.project_id = project_id
        self.status_table = status_table

        if credentials_path:
            self.client = bigquery.Client.from_service_account_json(
                credentials_path,
                project=project_id
            )
        else:
            # Use default credentials (from environment or gcloud)
            self.client = bigquery.Client(project=project_id)

    def delete_user_data(
        self,
        user_id: str,
        tables: List[str],
        user_id_column: str = "user_id"
    ) -> Dict[str, Any]:
        """
        Delete user data from specified BigQuery tables.

        Args:
            user_id: The user ID to delete
            tables: List of fully qualified table names (format: dataset.table)
            user_id_column: Column name containing the user ID

        Returns:
            Dictionary containing deletion results
        """
        results = {
            "user_id": user_id,
            "tables": {},
            "success": True,
            "timestamp": datetime.utcnow().isoformat()
        }

        for table in tables:
            try:
                query = f"""
                DELETE FROM `{self.project_id}.{table}`
                WHERE {user_id_column} = @user_id
                """

                job_config = bigquery.QueryJobConfig(
                    query_parameters=[
                        bigquery.ScalarQueryParameter("user_id", "STRING", user_id)
                    ]
                )

                query_job = self.client.query(query, job_config=job_config)
                query_job.result()  # Wait for the job to complete

                num_deleted = query_job.num_dml_affected_rows or 0

                results["tables"][table] = {
                    "success": True,
                    "rows_deleted": num_deleted
                }

                logger.info(f"Deleted {num_deleted} rows for user {user_id} from {table}")

            except GoogleCloudError as e:
                logger.error(f"Failed to delete user {user_id} data from {table}: {e}")
                results["tables"][table] = {
                    "success": False,
                    "error": str(e)
                }
                results["success"] = False

        return results

    def batch_delete_users(
        self,
        user_ids: List[str],
        tables: List[str],
        user_id_column: str = "user_id"
    ) -> List[Dict[str, Any]]:
        """
        Delete data for multiple users from specified tables.

        Args:
            user_ids: List of user IDs to delete
            tables: List of fully qualified table names
            user_id_column: Column name containing the user ID

        Returns:
            List of deletion results for each user
        """
        results = []

        for user_id in user_ids:
            result = self.delete_user_data(user_id, tables, user_id_column)
            results.append(result)

        success_count = sum(1 for r in results if r.get("success"))
        logger.info(
            f"BigQuery batch deletion completed: "
            f"{success_count}/{len(user_ids)} successful"
        )

        return results

    def create_status_table(self) -> bool:
        """
        Create the GDPR deletion status tracking table if it doesn't exist.

        Returns:
            True if table was created or already exists, False on error
        """
        try:
            schema = [
                bigquery.SchemaField("user_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("request_date", "TIMESTAMP", mode="REQUIRED"),
                bigquery.SchemaField("deletion_status", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("mixpanel_status", "STRING"),
                bigquery.SchemaField("mixpanel_task_id", "STRING"),
                bigquery.SchemaField("singular_status", "STRING"),
                bigquery.SchemaField("singular_request_id", "STRING"),
                bigquery.SchemaField("bigquery_status", "STRING"),
                bigquery.SchemaField("bigquery_tables_affected", "STRING"),
                bigquery.SchemaField("last_updated", "TIMESTAMP", mode="REQUIRED"),
                bigquery.SchemaField("error_message", "STRING"),
                bigquery.SchemaField("completed_date", "TIMESTAMP"),
            ]

            table_ref = self.client.dataset(
                self.status_table.split('.')[0]
            ).table(self.status_table.split('.')[1])

            table = bigquery.Table(table_ref, schema=schema)
            table = self.client.create_table(table, exists_ok=True)

            logger.info(f"Status table {self.status_table} is ready")
            return True

        except GoogleCloudError as e:
            logger.error(f"Failed to create status table: {e}")
            return False

    def update_deletion_status(
        self,
        user_id: str,
        status: str,
        mixpanel_result: Optional[Dict[str, Any]] = None,
        singular_result: Optional[Dict[str, Any]] = None,
        bigquery_result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Update or insert deletion status for a user.

        Args:
            user_id: The user ID
            status: Overall deletion status (pending, in_progress, completed, failed)
            mixpanel_result: Result from Mixpanel deletion
            singular_result: Result from Singular deletion
            bigquery_result: Result from BigQuery deletion
            error_message: Error message if deletion failed

        Returns:
            True if update was successful, False otherwise
        """
        try:
            now = datetime.utcnow().isoformat()

            # Extract details from results
            mixpanel_status = mixpanel_result.get("status") if mixpanel_result else None
            mixpanel_task_id = mixpanel_result.get("task_id") if mixpanel_result else None

            singular_status = singular_result.get("status") if singular_result else None
            singular_request_id = singular_result.get("request_id") if singular_result else None

            bigquery_status = "completed" if bigquery_result and bigquery_result.get("success") else None
            bigquery_tables = ",".join(bigquery_result.get("tables", {}).keys()) if bigquery_result else None

            completed_date = now if status == "completed" else None

            # Use MERGE to insert or update
            query = f"""
            MERGE `{self.project_id}.{self.status_table}` T
            USING (
                SELECT
                    @user_id AS user_id,
                    CURRENT_TIMESTAMP() AS request_date,
                    @status AS deletion_status,
                    @mixpanel_status AS mixpanel_status,
                    @mixpanel_task_id AS mixpanel_task_id,
                    @singular_status AS singular_status,
                    @singular_request_id AS singular_request_id,
                    @bigquery_status AS bigquery_status,
                    @bigquery_tables AS bigquery_tables_affected,
                    CURRENT_TIMESTAMP() AS last_updated,
                    @error_message AS error_message,
                    TIMESTAMP(@completed_date) AS completed_date
            ) S
            ON T.user_id = S.user_id
            WHEN MATCHED THEN
                UPDATE SET
                    deletion_status = S.deletion_status,
                    mixpanel_status = COALESCE(S.mixpanel_status, T.mixpanel_status),
                    mixpanel_task_id = COALESCE(S.mixpanel_task_id, T.mixpanel_task_id),
                    singular_status = COALESCE(S.singular_status, T.singular_status),
                    singular_request_id = COALESCE(S.singular_request_id, T.singular_request_id),
                    bigquery_status = COALESCE(S.bigquery_status, T.bigquery_status),
                    bigquery_tables_affected = COALESCE(S.bigquery_tables_affected, T.bigquery_tables_affected),
                    last_updated = S.last_updated,
                    error_message = S.error_message,
                    completed_date = COALESCE(S.completed_date, T.completed_date)
            WHEN NOT MATCHED THEN
                INSERT (
                    user_id, request_date, deletion_status,
                    mixpanel_status, mixpanel_task_id,
                    singular_status, singular_request_id,
                    bigquery_status, bigquery_tables_affected,
                    last_updated, error_message, completed_date
                )
                VALUES (
                    S.user_id, S.request_date, S.deletion_status,
                    S.mixpanel_status, S.mixpanel_task_id,
                    S.singular_status, S.singular_request_id,
                    S.bigquery_status, S.bigquery_tables_affected,
                    S.last_updated, S.error_message, S.completed_date
                )
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("user_id", "STRING", user_id),
                    bigquery.ScalarQueryParameter("status", "STRING", status),
                    bigquery.ScalarQueryParameter("mixpanel_status", "STRING", mixpanel_status),
                    bigquery.ScalarQueryParameter("mixpanel_task_id", "STRING", mixpanel_task_id),
                    bigquery.ScalarQueryParameter("singular_status", "STRING", singular_status),
                    bigquery.ScalarQueryParameter("singular_request_id", "STRING", singular_request_id),
                    bigquery.ScalarQueryParameter("bigquery_status", "STRING", bigquery_status),
                    bigquery.ScalarQueryParameter("bigquery_tables", "STRING", bigquery_tables),
                    bigquery.ScalarQueryParameter("error_message", "STRING", error_message),
                    bigquery.ScalarQueryParameter("completed_date", "STRING", completed_date),
                ]
            )

            query_job = self.client.query(query, job_config=job_config)
            query_job.result()  # Wait for the job to complete

            logger.info(f"Updated deletion status for user {user_id}: {status}")
            return True

        except GoogleCloudError as e:
            logger.error(f"Failed to update deletion status for user {user_id}: {e}")
            return False

    def get_deletion_status(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the current deletion status for a user.

        Args:
            user_id: The user ID to check

        Returns:
            Dictionary containing the status information, or None if not found
        """
        try:
            query = f"""
            SELECT *
            FROM `{self.project_id}.{self.status_table}`
            WHERE user_id = @user_id
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("user_id", "STRING", user_id)
                ]
            )

            query_job = self.client.query(query, job_config=job_config)
            results = list(query_job.result())

            if results:
                return dict(results[0])
            return None

        except GoogleCloudError as e:
            logger.error(f"Failed to get deletion status for user {user_id}: {e}")
            return None
