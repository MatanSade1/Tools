"""
Load organizational knowledge from BigQuery metadata tables instead of markdown files.
"""

import os
from typing import List, Dict
from google.cloud import bigquery
from dotenv import load_dotenv

load_dotenv()


class BigQueryMetadataLoader:
    """Load organizational knowledge from BigQuery metadata tables."""
    
    def __init__(self, project_id: str = "yotam-395120", dataset: str = "peerplay"):
        """
        Initialize BigQuery client.
        
        Args:
            project_id: GCP project ID
            dataset: BigQuery dataset containing metadata tables
        """
        self.project_id = project_id
        self.dataset = dataset
        self.client = bigquery.Client(project=project_id)
        
        # Table names
        self.guardrails_table = f"{project_id}.{dataset}.query_gen_guardrails"
        self.tables_table = f"{project_id}.{dataset}.query_gen_tables"
        self.columns_table = f"{project_id}.{dataset}.query_gen_columns"
        self.metrics_table = f"{project_id}.{dataset}.query_gen_known_metrics"
    
    def load_guardrails(self) -> List[Dict]:
        """Load all guardrails from BigQuery."""
        query = f"""
        SELECT 
            guardrails_name,
            guardrails_description,
            created_at,
            updated_at
        FROM `{self.guardrails_table}`
        ORDER BY created_at DESC
        """
        
        results = self.client.query(query).result()
        guardrails = []
        
        for row in results:
            guardrails.append({
                'name': row.guardrails_name,
                'description': row.guardrails_description,
                'created_at': row.created_at,
                'updated_at': row.updated_at
            })
        
        return guardrails
    
    def load_tables(self) -> List[Dict]:
        """Load all table metadata from BigQuery."""
        query = f"""
        SELECT 
            table_name,
            table_description,
            table_partition,
            table_clusters_list,
            usage_description,
            created_at,
            updated_at
        FROM `{self.tables_table}`
        ORDER BY created_at DESC
        """
        
        results = self.client.query(query).result()
        tables = []
        
        for row in results:
            tables.append({
                'name': row.table_name,
                'description': row.table_description,
                'partition': row.table_partition,
                'clusters': row.table_clusters_list or [],
                'usage': row.usage_description,
                'created_at': row.created_at,
                'updated_at': row.updated_at
            })
        
        return tables
    
    def load_columns(self, table_name: str = None) -> List[Dict]:
        """
        Load column metadata from BigQuery.
        
        Args:
            table_name: Optional filter for specific table
        """
        where_clause = ""
        if table_name:
            where_clause = f"WHERE related_table = '{table_name}'"
        
        query = f"""
        SELECT 
            column_name,
            related_table,
            column_type,
            is_partition,
            is_cluster,
            is_primary_key,
            column_description,
            created_at,
            updated_at
        FROM `{self.columns_table}`
        {where_clause}
        ORDER BY related_table, column_name
        """
        
        results = self.client.query(query).result()
        columns = []
        
        for row in results:
            columns.append({
                'name': row.column_name,
                'table': row.related_table,
                'type': row.column_type,
                'is_partition': row.is_partition,
                'is_cluster': row.is_cluster,
                'is_primary_key': row.is_primary_key,
                'description': row.column_description,
                'created_at': row.created_at,
                'updated_at': row.updated_at
            })
        
        return columns
    
    def load_metrics(self) -> List[Dict]:
        """Load all known metrics from BigQuery."""
        query = f"""
        SELECT 
            metric_name,
            metric_description,
            metric_query_example,
            created_at,
            updated_at
        FROM `{self.metrics_table}`
        ORDER BY created_at DESC
        """
        
        results = self.client.query(query).result()
        metrics = []
        
        for row in results:
            metrics.append({
                'name': row.metric_name,
                'description': row.metric_description,
                'query_example': row.metric_query_example,
                'created_at': row.created_at,
                'updated_at': row.updated_at
            })
        
        return metrics
    
    def load_all(self) -> Dict[str, List[Dict]]:
        """Load all metadata from BigQuery."""
        return {
            'guardrails': self.load_guardrails(),
            'tables': self.load_tables(),
            'columns': self.load_columns(),
            'metrics': self.load_metrics()
        }
    
    def format_for_embedding(self) -> List[Dict[str, str]]:
        """
        Format all metadata as documents ready for embedding.
        
        Returns:
            List of dicts with 'id', 'content', 'metadata' keys
        """
        documents = []
        all_data = self.load_all()
        
        # Format guardrails
        for idx, guardrail in enumerate(all_data['guardrails']):
            content = f"""# Guardrail: {guardrail['name']}

**Description:** {guardrail['description']}

**Type:** Query Generation Rule

This is a mandatory rule that the query generator must follow when creating SQL queries.
"""
            documents.append({
                'id': f"guardrail_{idx}",
                'content': content,
                'metadata': {
                    'source': 'guardrails',
                    'name': guardrail['name'],
                    'title': guardrail['name'],  # Add title for LLM
                    'content': content,  # Add content for LLM
                    'type': 'guardrail'
                }
            })
        
        # Format tables
        for idx, table in enumerate(all_data['tables']):
            clusters_str = ', '.join(table['clusters']) if table['clusters'] else 'None'
            content = f"""# Table: {table['name']}

**Description:** {table['description']}

**Partition Column:** {table['partition'] or 'None'}
**Clustering Columns:** {clusters_str}

**Usage Guidance:**
{table['usage'] or 'No specific usage guidance provided.'}

**When to use this table:**
{table['usage'] or 'Use when you need to query ' + table['name']}
"""
            documents.append({
                'id': f"table_{idx}",
                'content': content,
                'metadata': {
                    'source': 'tables',
                    'name': table['name'],
                    'title': table['name'],  # Add title for LLM
                    'content': content,  # Add content for LLM
                    'type': 'table'
                }
            })
        
        # Format columns (one vector per column)
        for col in all_data['columns']:
            table_name = col['table']
            col_name = col['name']
            
            # Build flags
            flags = []
            if col['is_partition']:
                flags.append('PARTITION')
            if col['is_cluster']:
                flags.append('CLUSTER')
            if col['is_primary_key']:
                flags.append('PRIMARY KEY')
            
            flags_str = f" [{', '.join(flags)}]" if flags else ""
            desc = col['description'] or 'No description provided yet.'
            
            # Create detailed content for this column
            content = f"""# Column: {col_name}

**Table:** {table_name}
**Type:** {col['type']}
**Flags:** {flags_str if flags else 'None'}

**Description:** {desc}

**Technical Details:**
- Column Name: {col_name}
- Data Type: {col['type']}
- Is Partition Column: {'Yes' if col['is_partition'] else 'No'}
- Is Clustering Column: {'Yes' if col['is_cluster'] else 'No'}
- Is Primary Key: {'Yes' if col['is_primary_key'] else 'No'}

This column belongs to table {table_name}.
"""
            
            # Create unique ID for this column
            safe_table = table_name.replace('.', '_').replace('-', '_')
            safe_column = col_name.replace('.', '_').replace('-', '_')
            
            documents.append({
                'id': f"column_{safe_table}_{safe_column}",
                'content': content,
                'metadata': {
                    'source': 'columns',
                    'table': table_name,
                    'column_name': col_name,
                    'title': f"{col_name} ({table_name})",
                    'content': content,
                    'type': 'column',
                    'column_type': col['type'],
                    'is_partition': str(col['is_partition']),
                    'is_cluster': str(col['is_cluster'])
                }
            })
        
        # Format metrics
        for idx, metric in enumerate(all_data['metrics']):
            content = f"""# Metric: {metric['name']}

**Description:** {metric['description']}

**Calculation Example:**
```sql
{metric['query_example']}
```

**How to calculate this metric:**
Use the query pattern above as a reference. This is how we calculate {metric['name']} in our organization.
"""
            documents.append({
                'id': f"metric_{idx}",
                'content': content,
                'metadata': {
                    'source': 'metrics',
                    'name': metric['name'],
                    'title': metric['name'],  # Add title for LLM
                    'content': content,  # Add content for LLM
                    'type': 'metric'
                }
            })
        
        return documents


if __name__ == "__main__":
    # Test the loader
    loader = BigQueryMetadataLoader()
    
    print("Loading metadata from BigQuery...")
    print()
    
    guardrails = loader.load_guardrails()
    tables = loader.load_tables()
    columns = loader.load_columns()
    metrics = loader.load_metrics()
    
    print(f"✓ Loaded {len(guardrails)} guardrails")
    print(f"✓ Loaded {len(tables)} tables")
    print(f"✓ Loaded {len(columns)} columns")
    print(f"✓ Loaded {len(metrics)} metrics")
    print()
    
    documents = loader.format_for_embedding()
    print(f"✓ Formatted {len(documents)} documents for embedding")
    print()
    
    if documents:
        print("Sample document:")
        print(documents[0]['content'][:200] + "...")
