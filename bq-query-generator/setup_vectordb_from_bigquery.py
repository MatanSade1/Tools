"""
Setup script to populate Pinecone vector database from BigQuery metadata tables.
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Tuple
from src.embeddings import EmbeddingGenerator
from src.vector_store import VectorStore
from src.bigquery_loader import BigQueryMetadataLoader
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class VectorDBSetupFromBigQuery:
    """Setup utility for populating vector database from BigQuery tables."""
    
    def __init__(self, config_path: str = "config/config.json"):
        """
        Initialize setup utility.
        
        Args:
            config_path: Path to configuration file
        """
        # Load configuration
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        # Initialize components
        self.embedder = EmbeddingGenerator(
            model=self.config['embeddings']['model']
        )
        
        self.vector_store = VectorStore(
            index_name=self.config['pinecone']['index_name'],
            dimension=self.config['pinecone']['dimension'],
            metric=self.config['pinecone']['metric']
        )
        
        self.bq_loader = BigQueryMetadataLoader()
    
    def load_documents_from_bigquery(self) -> List[Dict[str, str]]:
        """
        Load all documents from BigQuery metadata tables.
        
        Returns:
            List of document dicts with 'id', 'content', 'metadata' keys
        """
        print("\n" + "="*70)
        print("Loading organizational knowledge from BigQuery...")
        print("="*70 + "\n")
        
        documents = self.bq_loader.format_for_embedding()
        
        print(f"✓ Loaded from BigQuery:")
        all_data = self.bq_loader.load_all()
        print(f"  - {len(all_data['guardrails'])} guardrails")
        print(f"  - {len(all_data['tables'])} tables")
        print(f"  - {len(all_data['columns'])} columns")
        print(f"  - {len(all_data['metrics'])} metrics")
        print(f"\n✓ Formatted into {len(documents)} documents for embedding")
        
        return documents
    
    def generate_embeddings(self, documents: List[Dict[str, str]]) -> List[Tuple[str, List[float], Dict]]:
        """
        Generate embeddings for all documents.
        
        Args:
            documents: List of document dicts
            
        Returns:
            List of tuples (id, embedding, metadata) for Pinecone
        """
        print(f"\n" + "="*70)
        print(f"Generating embeddings for {len(documents)} documents...")
        print("="*70 + "\n")
        
        # Extract texts
        texts = [doc['content'] for doc in documents]
        
        # Generate embeddings in batch
        embeddings = self.embedder.generate_embeddings_batch(texts)
        
        print(f"✓ Generated {len(embeddings)} embeddings")
        
        # Prepare vectors for Pinecone
        vectors = []
        for doc, embedding in zip(documents, embeddings):
            vectors.append((
                doc['id'],
                embedding,
                doc['metadata']
            ))
        
        return vectors
    
    def setup(self, reset: bool = False):
        """
        Run complete setup: read from BigQuery, embed, and upload to Pinecone.
        
        Args:
            reset: If True, delete existing vectors before uploading
        """
        print("\n" + "="*70)
        print("BQ Query Generator - Vector Database Setup from BigQuery")
        print("="*70 + "\n")
        
        # Step 1: Create/connect to index
        print("Step 1: Setting up Pinecone index...")
        self.vector_store.create_index(
            cloud=self.config['pinecone'].get('cloud', 'aws'),
            region=self.config['pinecone'].get('region', 'us-east-1')
        )
        self.vector_store.connect_index()
        
        # Reset if requested
        if reset:
            print("\nResetting vector database...")
            self.vector_store.delete_namespace("organizational-docs")
        
        # Step 2: Load from BigQuery
        print("\nStep 2: Loading organizational knowledge from BigQuery...")
        documents = self.load_documents_from_bigquery()
        
        if not documents:
            print("\n⚠️  WARNING: No documents found in BigQuery tables!")
            print("Please add data to the following tables:")
            print("  - yotam-395120.peerplay.query_gen_guardrails")
            print("  - yotam-395120.peerplay.query_gen_tables")
            print("  - yotam-395120.peerplay.query_gen_columns")
            print("  - yotam-395120.peerplay.query_gen_known_metrics")
            return
        
        # Step 3: Generate embeddings
        print("\nStep 3: Generating embeddings...")
        vectors = self.generate_embeddings(documents)
        
        # Step 4: Upload to Pinecone
        print("\nStep 4: Uploading to Pinecone...")
        self.vector_store.upsert_vectors(
            vectors=vectors,
            namespace="organizational-docs",
            batch_size=100
        )
        
        # Step 5: Verify
        print("\nStep 5: Verifying upload...")
        stats = self.vector_store.get_stats()
        print(f"\nIndex statistics:")
        print(f"  Total vectors: {stats.total_vector_count}")
        print(f"  Namespaces: {stats.namespaces}")
        
        print("\n" + "="*70)
        print("✓ Setup complete! Vector database is ready.")
        print("="*70 + "\n")
        print("Your organizational knowledge from BigQuery is now searchable!")
        print("\nYou can now use the query generator:")
        print("  python main.py query \"your request here\"")
        print("  python main.py interactive\n")
        
        print("To add more knowledge:")
        print("  1. INSERT data into BigQuery metadata tables")
        print("  2. Re-run: python setup_vectordb_from_bigquery.py --reset")
        print("  3. New data will be embedded and searchable!\n")


def main():
    """Main setup function."""
    import sys
    
    reset = '--reset' in sys.argv
    
    if reset:
        response = input("⚠️  This will delete all existing vectors. Continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            return
    
    try:
        setup = VectorDBSetupFromBigQuery()
        setup.setup(reset=reset)
    except Exception as e:
        print(f"\n❌ Error during setup: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
