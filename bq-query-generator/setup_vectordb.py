"""
Setup script to populate Pinecone vector database with organizational documentation.
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Tuple
from src.embeddings import EmbeddingGenerator
from src.vector_store import VectorStore
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class VectorDBSetup:
    """Setup utility for populating vector database with organizational docs."""
    
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
        
        self.docs_dir = Path("config/organizational_manual")
    
    def read_markdown_files(self) -> List[Dict[str, str]]:
        """
        Read all markdown files from organizational manual directory.
        
        Returns:
            List of dicts with 'filename', 'content' keys
        """
        docs = []
        
        if not self.docs_dir.exists():
            raise FileNotFoundError(f"Documentation directory not found: {self.docs_dir}")
        
        md_files = list(self.docs_dir.glob("*.md"))
        
        if not md_files:
            raise ValueError(f"No markdown files found in {self.docs_dir}")
        
        print(f"Found {len(md_files)} markdown files:")
        for md_file in md_files:
            print(f"  - {md_file.name}")
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
                docs.append({
                    'filename': md_file.name,
                    'content': content
                })
        
        return docs
    
    def chunk_documents(self, docs: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Chunk documents by sections for better context preservation.
        
        Args:
            docs: List of document dicts
            
        Returns:
            List of chunk dicts with metadata
        """
        all_chunks = []
        
        print(f"\nChunking documents...")
        
        for doc in docs:
            filename = doc['filename']
            content = doc['content']
            
            # Chunk by markdown sections
            sections = self.embedder.chunk_markdown_by_sections(content)
            
            print(f"  {filename}: {len(sections)} sections")
            
            for i, section in enumerate(sections):
                chunk_id = f"{filename.replace('.md', '')}_{i}"
                all_chunks.append({
                    'id': chunk_id,
                    'content': section['content'],
                    'metadata': {
                        'source': filename,
                        'title': section['title'],
                        'level': section['level'],
                        'chunk_index': i,
                        'content': section['content']  # Store content in metadata for retrieval
                    }
                })
        
        print(f"\nTotal chunks: {len(all_chunks)}")
        return all_chunks
    
    def generate_embeddings(self, chunks: List[Dict[str, str]]) -> List[Tuple[str, List[float], Dict]]:
        """
        Generate embeddings for all chunks.
        
        Args:
            chunks: List of chunk dicts
            
        Returns:
            List of tuples (id, embedding, metadata) for Pinecone
        """
        print(f"\nGenerating embeddings for {len(chunks)} chunks...")
        
        # Extract texts
        texts = [chunk['content'] for chunk in chunks]
        
        # Generate embeddings in batch
        embeddings = self.embedder.generate_embeddings_batch(texts)
        
        print(f"✓ Generated {len(embeddings)} embeddings")
        
        # Prepare vectors for Pinecone
        vectors = []
        for chunk, embedding in zip(chunks, embeddings):
            vectors.append((
                chunk['id'],
                embedding,
                chunk['metadata']
            ))
        
        return vectors
    
    def setup(self, reset: bool = False):
        """
        Run complete setup: read docs, chunk, embed, and upload to Pinecone.
        
        Args:
            reset: If True, delete existing vectors before uploading
        """
        print("\n" + "="*60)
        print("BQ Query Generator - Vector Database Setup")
        print("="*60 + "\n")
        
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
        
        # Step 2: Read markdown files
        print("\nStep 2: Reading organizational documentation...")
        docs = self.read_markdown_files()
        
        # Step 3: Chunk documents
        print("\nStep 3: Chunking documents by sections...")
        chunks = self.chunk_documents(docs)
        
        # Step 4: Generate embeddings
        print("\nStep 4: Generating embeddings...")
        vectors = self.generate_embeddings(chunks)
        
        # Step 5: Upload to Pinecone
        print("\nStep 5: Uploading to Pinecone...")
        self.vector_store.upsert_vectors(
            vectors=vectors,
            namespace="organizational-docs",
            batch_size=100
        )
        
        # Step 6: Verify
        print("\nStep 6: Verifying upload...")
        stats = self.vector_store.get_stats()
        print(f"\nIndex statistics:")
        print(f"  Total vectors: {stats.total_vector_count}")
        print(f"  Namespaces: {stats.namespaces}")
        
        print("\n" + "="*60)
        print("✓ Setup complete! Vector database is ready.")
        print("="*60 + "\n")
        print("You can now use the query generator:")
        print("  python main.py query \"your request here\"")
        print("  python main.py interactive\n")


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
        setup = VectorDBSetup()
        setup.setup(reset=reset)
    except Exception as e:
        print(f"\n❌ Error during setup: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
