"""
Pinecone vector store operations for storing and retrieving document embeddings.
"""

import os
import time
from typing import List, Dict, Optional, Tuple
from pinecone import Pinecone, ServerlessSpec
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class VectorStore:
    """Manages Pinecone vector database operations."""
    
    def __init__(self, index_name: str = None, dimension: int = 3072, metric: str = "cosine"):
        """
        Initialize Pinecone vector store.
        
        Args:
            index_name: Name of the Pinecone index
            dimension: Dimension of vectors (3072 for text-embedding-3-large)
            metric: Distance metric (cosine, euclidean, dotproduct)
        """
        api_key = os.getenv("PINECONE_API_KEY")
        if not api_key:
            raise ValueError("PINECONE_API_KEY not found in environment variables")
        
        self.index_name = index_name or os.getenv("PINECONE_INDEX_NAME", "bq-query-knowledge")
        self.dimension = dimension
        self.metric = metric
        
        # Initialize Pinecone
        self.pc = Pinecone(api_key=api_key)
        self.index = None
    
    def create_index(self, cloud: str = "aws", region: str = "us-east-1"):
        """
        Create a new Pinecone index if it doesn't exist.
        
        Args:
            cloud: Cloud provider (aws, gcp, azure)
            region: Cloud region
        """
        existing_indexes = [index.name for index in self.pc.list_indexes()]
        
        if self.index_name in existing_indexes:
            print(f"Index '{self.index_name}' already exists")
        else:
            print(f"Creating index '{self.index_name}'...")
            self.pc.create_index(
                name=self.index_name,
                dimension=self.dimension,
                metric=self.metric,
                spec=ServerlessSpec(
                    cloud=cloud,
                    region=region
                )
            )
            
            # Wait for index to be ready
            while not self.pc.describe_index(self.index_name).status['ready']:
                print("Waiting for index to be ready...")
                time.sleep(1)
            
            print(f"Index '{self.index_name}' created successfully")
    
    def connect_index(self):
        """Connect to an existing Pinecone index."""
        try:
            self.index = self.pc.Index(self.index_name)
            stats = self.index.describe_index_stats()
            print(f"Connected to index '{self.index_name}'")
            print(f"Total vectors: {stats.total_vector_count}")
            return True
        except Exception as e:
            print(f"Error connecting to index: {e}")
            return False
    
    def upsert_vectors(self, vectors: List[Tuple[str, List[float], Dict]], 
                       namespace: str = "organizational-docs", batch_size: int = 100):
        """
        Insert or update vectors in the index.
        
        Args:
            vectors: List of tuples (id, vector, metadata)
            namespace: Namespace to organize vectors
            batch_size: Number of vectors to upsert per batch
        """
        if not self.index:
            if not self.connect_index():
                raise RuntimeError("Not connected to index")
        
        total = len(vectors)
        print(f"Upserting {total} vectors to namespace '{namespace}'...")
        
        for i in range(0, total, batch_size):
            batch = vectors[i:i + batch_size]
            self.index.upsert(vectors=batch, namespace=namespace)
            print(f"Upserted {min(i + batch_size, total)}/{total} vectors")
        
        print("Upsert complete!")
    
    def query_similar(self, query_vector: List[float], top_k: int = 8, 
                     namespace: str = "organizational-docs", 
                     score_threshold: float = 0.7,
                     filter_dict: Optional[Dict] = None) -> List[Dict]:
        """
        Query for similar vectors.
        
        Args:
            query_vector: Query embedding vector
            top_k: Number of results to return
            namespace: Namespace to query
            score_threshold: Minimum similarity score (0-1)
            filter_dict: Optional metadata filter
            
        Returns:
            List of matches with id, score, and metadata
        """
        if not self.index:
            if not self.connect_index():
                raise RuntimeError("Not connected to index")
        
        results = self.index.query(
            namespace=namespace,
            vector=query_vector,
            top_k=top_k,
            include_metadata=True,
            filter=filter_dict
        )
        
        # Filter by score threshold
        matches = []
        for match in results.matches:
            if match.score >= score_threshold:
                matches.append({
                    'id': match.id,
                    'score': match.score,
                    'metadata': match.metadata
                })
        
        return matches
    
    def delete_namespace(self, namespace: str = "organizational-docs"):
        """Delete all vectors in a namespace."""
        if not self.index:
            if not self.connect_index():
                raise RuntimeError("Not connected to index")
        
        self.index.delete(delete_all=True, namespace=namespace)
        print(f"Deleted all vectors in namespace '{namespace}'")
    
    def get_stats(self) -> Dict:
        """Get index statistics."""
        if not self.index:
            if not self.connect_index():
                raise RuntimeError("Not connected to index")
        
        return self.index.describe_index_stats()


if __name__ == "__main__":
    # Test vector store
    vs = VectorStore()
    
    # Create or connect to index
    vs.create_index()
    vs.connect_index()
    
    # Get stats
    stats = vs.get_stats()
    print(f"\nIndex stats: {stats}")
