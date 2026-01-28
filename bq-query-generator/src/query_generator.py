"""
Main RAG query generator that orchestrates embeddings, vector search, and LLM generation.
"""

import json
from typing import Dict, List
from .embeddings import EmbeddingGenerator
from .vector_store import VectorStore
from .llm_client import LLMClient


class QueryGenerator:
    """RAG-based SQL query generator."""
    
    def __init__(self, config_path: str = "config/config.json"):
        """
        Initialize the query generator with all components.
        
        Args:
            config_path: Path to configuration file
        """
        # Load configuration
        try:
            with open(config_path, 'r') as f:
                self.config = json.load(f)
        except FileNotFoundError:
            print(f"Warning: Config file not found at {config_path}, using defaults")
            self.config = self._default_config()
        
        # Initialize components
        self.embedder = EmbeddingGenerator(
            model=self.config['embeddings']['model']
        )
        
        self.vector_store = VectorStore(
            index_name=self.config['pinecone']['index_name'],
            dimension=self.config['pinecone']['dimension'],
            metric=self.config['pinecone']['metric']
        )
        
        self.llm = LLMClient(
            model=self.config['llm']['model'],
            temperature=self.config['llm']['temperature'],
            max_tokens=self.config['llm']['max_tokens']
        )
        
        # Connect to vector store
        self.vector_store.connect_index()
    
    def _default_config(self) -> Dict:
        """Return default configuration."""
        return {
            'pinecone': {
                'index_name': 'bq-query-knowledge',
                'dimension': 3072,
                'metric': 'cosine'
            },
            'embeddings': {
                'model': 'text-embedding-3-large',
                'chunk_size': 1000,
                'chunk_overlap': 200
            },
            'llm': {
                'model': 'claude-3-5-sonnet-20241022',
                'temperature': 0.1,
                'max_tokens': 2000
            },
            'retrieval': {
                'top_k': 8,
                'score_threshold': 0.7
            }
        }
    
    def generate(self, user_request: str, verbose: bool = False) -> Dict[str, str]:
        """
        Generate SQL query from natural language request.
        
        Args:
            user_request: Plain text description of desired query
            verbose: Whether to print detailed information
            
        Returns:
            Dict with 'query', 'explanation', and 'context' keys
        """
        if verbose:
            print(f"\n{'='*60}")
            print(f"USER REQUEST: {user_request}")
            print(f"{'='*60}\n")
        
        # Step 1: Generate embedding for user request
        if verbose:
            print("Step 1: Generating embedding for request...")
        
        query_embedding = self.embedder.generate_embedding(user_request)
        
        if verbose:
            print(f"✓ Generated {len(query_embedding)}-dimensional embedding\n")
        
        # Step 2: Query vector store for relevant context
        if verbose:
            print("Step 2: Searching vector database for relevant context...")
        
        matches = self.vector_store.query_similar(
            query_vector=query_embedding,
            top_k=self.config['retrieval']['top_k'],
            namespace="organizational-docs",
            score_threshold=self.config['retrieval']['score_threshold']
        )
        
        if verbose:
            print(f"✓ Found {len(matches)} relevant context chunks:\n")
            for i, match in enumerate(matches, 1):
                metadata = match.get('metadata', {})
                print(f"  {i}. [{metadata.get('source', 'Unknown')}] "
                      f"{metadata.get('title', 'Untitled')} "
                      f"(score: {match['score']:.3f})")
            print()
        
        if not matches:
            return {
                'query': '-- No relevant context found. Please ensure vector database is populated.',
                'explanation': 'Could not find relevant organizational context for this request.',
                'context': []
            }
        
        # Step 3: Generate SQL query using LLM with context
        if verbose:
            print("Step 3: Generating SQL query with Claude AI...\n")
        
        result = self.llm.generate_query(
            user_request=user_request,
            context_chunks=matches,
            verbose=verbose
        )
        
        # Add context information to result
        result['context'] = matches
        
        if verbose:
            print(f"✓ Query generated successfully!\n")
            print(f"{'='*60}\n")
        
        return result
    
    def interactive_mode(self):
        """Run in interactive mode for multiple queries."""
        print("\n" + "="*60)
        print("BQ Query Generator - Interactive Mode")
        print("="*60)
        print("\nType your query requests in plain English.")
        print("Commands: 'quit' or 'exit' to stop, 'verbose' to toggle details\n")
        
        verbose = False
        
        while True:
            try:
                user_input = input("\n🔍 Your request: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("\nGoodbye! 👋\n")
                    break
                
                if user_input.lower() == 'verbose':
                    verbose = not verbose
                    print(f"\nVerbose mode: {'ON' if verbose else 'OFF'}")
                    continue
                
                # Generate query
                result = self.generate(user_input, verbose=verbose)
                
                # Display results
                print("\n" + "="*60)
                print("GENERATED SQL QUERY:")
                print("="*60)
                print(result['query'])
                print("\n" + "-"*60)
                print("EXPLANATION:")
                print("-"*60)
                print(result['explanation'])
                print()
                
            except KeyboardInterrupt:
                print("\n\nGoodbye! 👋\n")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}\n")


if __name__ == "__main__":
    # Test query generator
    qg = QueryGenerator()
    
    # Test generation
    result = qg.generate(
        "Show me daily active users for the last 7 days",
        verbose=True
    )
    
    print("\n=== RESULT ===")
    print("Query:", result['query'])
    print("\nExplanation:", result['explanation'])
