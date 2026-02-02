"""
Incremental Pinecone synchronization for column changes.
Only updates vectors that have changed, avoiding full re-sync.
"""

from typing import List, Dict
from .vector_store import VectorStore
from .embeddings import EmbeddingGenerator
from .bigquery_loader import BigQueryMetadataLoader


class IncrementalPineconeSync:
    """Handle incremental updates to Pinecone for column changes."""
    
    def __init__(self, vector_store: VectorStore, embedder: EmbeddingGenerator, 
                 bq_loader: BigQueryMetadataLoader):
        """
        Initialize incremental sync.
        
        Args:
            vector_store: Pinecone vector store instance
            embedder: Embedding generator instance
            bq_loader: BigQuery metadata loader instance
        """
        self.vector_store = vector_store
        self.embedder = embedder
        self.bq_loader = bq_loader
        self.namespace = "organizational-docs"
    
    def _make_vector_id(self, table_name: str, column_name: str) -> str:
        """
        Create a safe vector ID for a column.
        
        Args:
            table_name: Full table name
            column_name: Column name
            
        Returns:
            Safe vector ID string
        """
        safe_table = table_name.replace('.', '_').replace('-', '_')
        safe_column = column_name.replace('.', '_').replace('-', '_')
        return f"column_{safe_table}_{safe_column}"
    
    def _format_column_content(self, table_name: str, col: Dict) -> str:
        """
        Format a single column as content for embedding.
        
        Args:
            table_name: Full table name
            col: Column dict with name, type, description, flags
            
        Returns:
            Formatted content string
        """
        flags = []
        if col.get('is_partition'):
            flags.append('PARTITION')
        if col.get('is_cluster'):
            flags.append('CLUSTER')
        if col.get('is_primary_key'):
            flags.append('PRIMARY KEY')
        
        flags_str = f" [{', '.join(flags)}]" if flags else ""
        desc = col.get('description', '') or 'No description provided yet.'
        
        content = f"""# Column: {col['name']}

**Table:** {table_name}
**Type:** {col['type']}
**Flags:** {flags_str if flags else 'None'}

**Description:** {desc}

**Technical Details:**
- Column Name: {col['name']}
- Data Type: {col['type']}
- Is Partition Column: {'Yes' if col.get('is_partition') else 'No'}
- Is Clustering Column: {'Yes' if col.get('is_cluster') else 'No'}
- Is Primary Key: {'Yes' if col.get('is_primary_key') else 'No'}

This column belongs to table {table_name}.
"""
        return content
    
    def sync_columns_for_table(self, table_name: str, changes: Dict[str, List], 
                               verbose: bool = False) -> Dict[str, int]:
        """
        Incrementally sync column changes to Pinecone for a specific table.
        
        Only creates vectors for columns that have descriptions (non-empty).
        Uses batch embedding for performance.
        
        Args:
            table_name: Full table name
            changes: Dict with added, updated, removed lists
            verbose: Whether to print progress
            
        Returns:
            Dict with counts: deleted, updated, added, skipped
        """
        stats = {'deleted': 0, 'updated': 0, 'added': 0, 'skipped': 0}
        
        # Ensure we're connected
        if not self.vector_store.index:
            self.vector_store.connect_index()
        
        # 1. Delete vectors for removed columns
        if changes['removed']:
            vector_ids = [
                self._make_vector_id(table_name, col['name']) 
                for col in changes['removed']
            ]
            
            if verbose:
                print(f"\n  Deleting {len(vector_ids)} vectors from Pinecone...")
            
            for vid in vector_ids:
                try:
                    self.vector_store.index.delete(ids=[vid], namespace=self.namespace)
                    stats['deleted'] += 1
                except Exception as e:
                    if verbose:
                        print(f"    Warning: Could not delete vector {vid}: {e}")
        
        # 2. Update vectors for modified columns (only if they have descriptions)
        if changes['updated']:
            if verbose:
                print(f"\n  Processing {len(changes['updated'])} updated columns...")
            
            # Fetch current column data from BigQuery
            all_columns = self.bq_loader.load_columns(table_name)
            columns_by_name = {col['name']: col for col in all_columns}
            
            # Filter to only columns with descriptions
            columns_to_embed = []
            for col in changes['updated']:
                fresh_col = columns_by_name.get(col['name'])
                if fresh_col and fresh_col.get('description') and fresh_col['description'].strip():
                    columns_to_embed.append(fresh_col)
                elif verbose:
                    stats['skipped'] += 1
            
            if columns_to_embed:
                if verbose:
                    print(f"    {len(columns_to_embed)} have descriptions, embedding in batch...")
                
                # Format all contents
                contents = [self._format_column_content(table_name, col) for col in columns_to_embed]
                
                # Generate embeddings in batch
                embeddings = self.embedder.generate_embeddings_batch(contents)
                
                # Prepare vectors for upsert
                vectors_to_upsert = []
                for col, embedding in zip(columns_to_embed, embeddings):
                    metadata = {
                        'source': 'columns',
                        'table': table_name,
                        'column_name': col['name'],
                        'title': f"{col['name']} ({table_name})",
                        'content': self._format_column_content(table_name, col),
                        'type': 'column',
                        'column_type': col['type'],
                        'is_partition': str(col['is_partition']),
                        'is_cluster': str(col['is_cluster'])
                    }
                    
                    vector_id = self._make_vector_id(table_name, col['name'])
                    vectors_to_upsert.append((vector_id, embedding, metadata))
                
                # Batch upsert
                if vectors_to_upsert:
                    self.vector_store.index.upsert(
                        vectors=vectors_to_upsert, 
                        namespace=self.namespace
                    )
                    stats['updated'] = len(vectors_to_upsert)
        
        # 3. Add vectors for new columns (only if they have descriptions)
        if changes['added']:
            if verbose:
                print(f"\n  Processing {len(changes['added'])} new columns...")
            
            # Fetch current column data from BigQuery
            all_columns = self.bq_loader.load_columns(table_name)
            columns_by_name = {col['name']: col for col in all_columns}
            
            # Filter to only columns with descriptions
            columns_to_embed = []
            for col in changes['added']:
                fresh_col = columns_by_name.get(col['name'])
                if not fresh_col:
                    # Column not in DB yet, use schema data (will have empty description)
                    fresh_col = {
                        'name': col['name'],
                        'type': col['type'],
                        'is_partition': col['is_partition'],
                        'is_cluster': col['is_cluster'],
                        'is_primary_key': False,
                        'description': ''
                    }
                
                # Only embed if has description
                if fresh_col.get('description') and fresh_col['description'].strip():
                    columns_to_embed.append(fresh_col)
                else:
                    stats['skipped'] += 1
                    if verbose:
                        print(f"    Skipping {col['name']} (no description)")
            
            if columns_to_embed:
                if verbose:
                    print(f"    {len(columns_to_embed)} have descriptions, embedding in batch...")
                
                # Format all contents
                contents = [self._format_column_content(table_name, col) for col in columns_to_embed]
                
                # Generate embeddings in batch
                embeddings = self.embedder.generate_embeddings_batch(contents)
                
                # Prepare vectors for upsert
                vectors_to_upsert = []
                for col, embedding in zip(columns_to_embed, embeddings):
                    metadata = {
                        'source': 'columns',
                        'table': table_name,
                        'column_name': col['name'],
                        'title': f"{col['name']} ({table_name})",
                        'content': self._format_column_content(table_name, col),
                        'type': 'column',
                        'column_type': col['type'],
                        'is_partition': str(col['is_partition']),
                        'is_cluster': str(col['is_cluster'])
                    }
                    
                    vector_id = self._make_vector_id(table_name, col['name'])
                    vectors_to_upsert.append((vector_id, embedding, metadata))
                
                # Batch upsert
                if vectors_to_upsert:
                    self.vector_store.index.upsert(
                        vectors=vectors_to_upsert, 
                        namespace=self.namespace
                    )
                    stats['added'] = len(vectors_to_upsert)
        
        return stats


if __name__ == "__main__":
    # Test incremental sync
    from .vector_store import VectorStore
    from .embeddings import EmbeddingGenerator
    from .bigquery_loader import BigQueryMetadataLoader
    
    print("Testing incremental Pinecone sync...")
    
    vs = VectorStore()
    vs.connect_index()
    
    embedder = EmbeddingGenerator()
    loader = BigQueryMetadataLoader()
    
    sync = IncrementalPineconeSync(vs, embedder, loader)
    
    # Test with mock changes
    test_changes = {
        'added': [],
        'updated': [],
        'removed': []
    }
    
    stats = sync.sync_columns_for_table(
        "yotam-395120.peerplay.events",
        test_changes,
        verbose=True
    )
    
    print(f"\nSync stats: {stats}")
