"""
Automatic schema synchronization from BigQuery to query_gen_columns table.
Detects schema changes and updates column metadata.
"""

import os
import re
from typing import List, Dict, Optional, Tuple
from google.cloud import bigquery
from dotenv import load_dotenv

load_dotenv()


class SchemaSync:
    """Synchronize BigQuery table schemas with query_gen_columns table."""
    
    def __init__(self, project_id: str = "yotam-395120", dataset: str = "peerplay"):
        """
        Initialize SchemaSync.
        
        Args:
            project_id: GCP project ID
            dataset: BigQuery dataset containing metadata tables
        """
        self.project_id = project_id
        self.dataset = dataset
        self.client = bigquery.Client(project=project_id)
        self.columns_table = f"{project_id}.{dataset}.query_gen_columns"
    
    def fetch_table_schema(self, table_name: str) -> List[Dict]:
        """
        Fetch schema for a table from BigQuery INFORMATION_SCHEMA.
        
        Args:
            table_name: Full table name (e.g., 'project.dataset.table')
            
        Returns:
            List of column dicts with name, type, is_partition, is_cluster
        """
        # Parse table name
        parts = table_name.split('.')
        if len(parts) != 3:
            raise ValueError(f"Invalid table name format. Expected 'project.dataset.table', got '{table_name}'")
        
        table_project, table_dataset, table_only = parts
        
        # First, check if it's a view or table
        is_view = self._is_view(table_project, table_dataset, table_only)
        
        # Get column information
        query = f"""
        SELECT 
            column_name,
            data_type,
            is_partitioning_column
        FROM `{table_project}.{table_dataset}.INFORMATION_SCHEMA.COLUMNS`
        WHERE table_name = '{table_only}'
        ORDER BY ordinal_position
        """
        
        results = self.client.query(query).result()
        columns = []
        
        for row in results:
            columns.append({
                'name': row.column_name,
                'type': row.data_type,
                'is_partition': row.is_partitioning_column == 'YES'
            })
        
        if not columns:
            raise ValueError(f"No columns found for table '{table_name}'. Does it exist?")
        
        # Get clustering columns
        clustering_cols = self._get_clustering_columns(table_project, table_dataset, table_only, is_view)
        
        # Mark clustering columns
        for col in columns:
            col['is_cluster'] = col['name'] in clustering_cols
        
        return columns
    
    def _is_view(self, project: str, dataset: str, table: str) -> bool:
        """Check if a table is actually a view."""
        query = f"""
        SELECT table_name
        FROM `{project}.{dataset}.INFORMATION_SCHEMA.VIEWS`
        WHERE table_name = '{table}'
        LIMIT 1
        """
        
        results = list(self.client.query(query).result())
        return len(results) > 0
    
    def _get_clustering_columns(self, project: str, dataset: str, table: str, is_view: bool) -> List[str]:
        """
        Get clustering columns for a table.
        
        If it's a view, try to detect the underlying table and get its clustering.
        """
        try:
            # Try direct clustering first
            query = f"""
            SELECT column_name
            FROM `{project}.{dataset}.INFORMATION_SCHEMA.CLUSTERING_COLUMNS`
            WHERE table_name = '{table}'
            ORDER BY rank
            """
            
            results = list(self.client.query(query).result())
            
            if results:
                return [row.column_name for row in results]
        except Exception:
            # CLUSTERING_COLUMNS might not be accessible or table doesn't have clustering
            pass
        
        # If it's a view and no clustering found, try to detect underlying table
        if is_view:
            try:
                underlying_table = self._get_underlying_table(project, dataset, table)
                if underlying_table:
                    underlying_parts = underlying_table.split('.')
                    if len(underlying_parts) == 3:
                        return self._get_clustering_columns(
                            underlying_parts[0], 
                            underlying_parts[1], 
                            underlying_parts[2], 
                            is_view=False
                        )
            except Exception:
                pass
        
        return []
    
    def _get_underlying_table(self, project: str, dataset: str, view: str) -> Optional[str]:
        """
        Try to detect the underlying table from a view definition.
        
        Uses simple regex to find FROM clauses. Not perfect but works for most cases.
        """
        query = f"""
        SELECT view_definition
        FROM `{project}.{dataset}.INFORMATION_SCHEMA.VIEWS`
        WHERE table_name = '{view}'
        """
        
        results = list(self.client.query(query).result())
        if not results:
            return None
        
        view_def = results[0].view_definition
        
        # Look for FROM `project.dataset.table` pattern
        pattern = r'FROM\s+`([^`]+)`'
        matches = re.findall(pattern, view_def, re.IGNORECASE)
        
        if matches:
            # Return first match (main table)
            return matches[0]
        
        return None
    
    def get_current_columns(self, table_name: str) -> List[Dict]:
        """
        Get current columns for a table from query_gen_columns.
        
        Args:
            table_name: Full table name
            
        Returns:
            List of column dicts from our metadata table
        """
        query = f"""
        SELECT 
            column_name,
            column_type,
            is_partition,
            is_cluster,
            is_primary_key,
            column_description
        FROM `{self.columns_table}`
        WHERE related_table = '{table_name}'
        ORDER BY column_name
        """
        
        results = self.client.query(query).result()
        columns = []
        
        for row in results:
            columns.append({
                'name': row.column_name,
                'type': row.column_type,
                'is_partition': row.is_partition,
                'is_cluster': row.is_cluster,
                'is_primary_key': row.is_primary_key,
                'description': row.column_description
            })
        
        return columns
    
    def compute_diff(self, current: List[Dict], new_schema: List[Dict]) -> Dict[str, List]:
        """
        Compare current columns with new schema and compute differences.
        
        Args:
            current: Current columns from query_gen_columns
            new_schema: New schema from BigQuery INFORMATION_SCHEMA
            
        Returns:
            Dict with keys: added, updated, removed
        """
        current_names = {col['name']: col for col in current}
        new_names = {col['name']: col for col in new_schema}
        
        added = []
        updated = []
        removed = []
        
        # Find added columns
        for name, col in new_names.items():
            if name not in current_names:
                added.append(col)
        
        # Find updated columns (technical fields changed)
        for name, new_col in new_names.items():
            if name in current_names:
                curr_col = current_names[name]
                
                # Check if any technical field changed
                if (curr_col['type'] != new_col['type'] or
                    curr_col['is_partition'] != new_col['is_partition'] or
                    curr_col['is_cluster'] != new_col['is_cluster']):
                    
                    # Include description to preserve it
                    new_col['description'] = curr_col.get('description', '')
                    new_col['is_primary_key'] = curr_col.get('is_primary_key', False)
                    updated.append(new_col)
        
        # Find removed columns
        for name in current_names:
            if name not in new_names:
                removed.append(current_names[name])
        
        return {
            'added': added,
            'updated': updated,
            'removed': removed
        }
    
    def apply_changes(self, table_name: str, changes: Dict[str, List]) -> Dict[str, int]:
        """
        Apply schema changes to query_gen_columns table.
        
        Args:
            table_name: Full table name
            changes: Dict with added, updated, removed lists
            
        Returns:
            Dict with counts: deleted, updated, inserted
        """
        stats = {'deleted': 0, 'updated': 0, 'inserted': 0}
        
        # 1. Delete removed columns
        if changes['removed']:
            removed_names = [col['name'] for col in changes['removed']]
            placeholders = ', '.join([f"'{name}'" for name in removed_names])
            
            delete_query = f"""
            DELETE FROM `{self.columns_table}`
            WHERE related_table = '{table_name}'
            AND column_name IN ({placeholders})
            """
            
            job = self.client.query(delete_query)
            job.result()  # Wait for completion
            stats['deleted'] = len(removed_names)
        
        # 2. Update existing columns (technical fields only, preserve description)
        for col in changes['updated']:
            update_query = f"""
            UPDATE `{self.columns_table}`
            SET 
                column_type = '{col['type']}',
                is_partition = {col['is_partition']},
                is_cluster = {col['is_cluster']},
                updated_at = CURRENT_TIMESTAMP()
            WHERE related_table = '{table_name}'
            AND column_name = '{col['name']}'
            """
            
            job = self.client.query(update_query)
            job.result()
            stats['updated'] += 1
        
        # 3. Insert new columns (BATCH INSERT for performance)
        if changes['added']:
            # Build single INSERT with multiple rows
            values_list = []
            for col in changes['added']:
                # Escape single quotes in column name and type
                safe_name = col['name'].replace("'", "\\'")
                safe_type = col['type'].replace("'", "\\'")
                
                values_list.append(f"""(
                    '{safe_name}',
                    '{table_name}',
                    '{safe_type}',
                    {col['is_partition']},
                    {col['is_cluster']},
                    FALSE,
                    '',
                    CURRENT_TIMESTAMP(),
                    CURRENT_TIMESTAMP()
                )""")
            
            # Single batch insert
            insert_query = f"""
            INSERT INTO `{self.columns_table}`
            (column_name, related_table, column_type, is_partition, is_cluster, 
             is_primary_key, column_description, created_at, updated_at)
            VALUES
            {','.join(values_list)}
            """
            
            job = self.client.query(insert_query)
            job.result()
            stats['inserted'] = len(changes['added'])
        
        return stats
    
    def sync_table(self, table_name: str, dry_run: bool = False) -> Tuple[Dict[str, List], Dict[str, int]]:
        """
        Main synchronization method for a single table.
        
        Args:
            table_name: Full table name
            dry_run: If True, only compute diff without applying changes
            
        Returns:
            Tuple of (changes dict, stats dict)
        """
        # Fetch new schema from BigQuery
        new_schema = self.fetch_table_schema(table_name)
        
        # Get current columns from our metadata table
        current = self.get_current_columns(table_name)
        
        # Compute differences
        changes = self.compute_diff(current, new_schema)
        
        # Apply changes if not dry run
        stats = {'deleted': 0, 'updated': 0, 'inserted': 0}
        if not dry_run:
            stats = self.apply_changes(table_name, changes)
        
        return changes, stats


if __name__ == "__main__":
    # Test schema sync
    sync = SchemaSync()
    
    # Test with a known table
    table_name = "yotam-395120.peerplay.events"
    
    print(f"Fetching schema for: {table_name}")
    schema = sync.fetch_table_schema(table_name)
    
    print(f"\nFound {len(schema)} columns:")
    for col in schema[:5]:  # Show first 5
        flags = []
        if col['is_partition']:
            flags.append('PARTITION')
        if col['is_cluster']:
            flags.append('CLUSTER')
        flags_str = f" [{', '.join(flags)}]" if flags else ""
        print(f"  - {col['name']} ({col['type']}){flags_str}")
    
    if len(schema) > 5:
        print(f"  ... and {len(schema) - 5} more")
