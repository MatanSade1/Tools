#!/usr/bin/env python3
"""
BQ Query Generator - CLI entry point

A RAG-based tool that converts natural language requests into BigQuery SQL queries
using organizational knowledge from vector embeddings.
"""

import sys
import click
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.query_generator import QueryGenerator


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """
    BQ Query Generator - Convert plain text to BigQuery SQL
    
    A RAG-based tool that uses your organizational knowledge to generate
    optimized BigQuery SQL queries from natural language requests.
    """
    pass


@cli.command()
@click.argument('request', required=True)
@click.option('--verbose', '-v', is_flag=True, help='Show detailed generation process')
@click.option('--copy', '-c', is_flag=True, help='Copy query to clipboard (requires pyperclip)')
def query(request: str, verbose: bool, copy: bool):
    """
    Generate a BigQuery SQL query from a natural language REQUEST.
    
    Example:
        python main.py query "Show me daily active users for last 7 days"
    """
    try:
        # Initialize generator
        qg = QueryGenerator()
        
        # Generate query
        result = qg.generate(request, verbose=verbose)
        
        # Display results
        print("\n" + "="*70)
        print("GENERATED SQL QUERY")
        print("="*70)
        print(result['query'])
        print("\n" + "-"*70)
        print("EXPLANATION")
        print("-"*70)
        print(result['explanation'])
        
        # Show context sources if verbose
        if verbose and result.get('context'):
            print("\n" + "-"*70)
            print("CONTEXT SOURCES")
            print("-"*70)
            for i, ctx in enumerate(result['context'], 1):
                metadata = ctx.get('metadata', {})
                print(f"{i}. [{metadata.get('source', 'Unknown')}] "
                      f"{metadata.get('title', 'Untitled')} "
                      f"(relevance: {ctx.get('score', 0):.2f})")
        
        print()
        
        # Copy to clipboard if requested
        if copy:
            try:
                import pyperclip
                pyperclip.copy(result['query'])
                print("✓ Query copied to clipboard!\n")
            except ImportError:
                print("⚠️  pyperclip not installed. Install with: pip install pyperclip\n")
        
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


@cli.command()
def interactive():
    """
    Run in interactive mode for multiple queries.
    
    Allows you to enter multiple requests in a conversation-style interface.
    """
    try:
        qg = QueryGenerator()
        qg.interactive_mode()
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--reset', is_flag=True, help='Delete existing vectors before setup')
def setup(reset: bool):
    """
    Set up the vector database with organizational documentation.
    
    This command:
    1. Reads all markdown files from config/organizational_manual/
    2. Chunks documents by sections
    3. Generates embeddings using OpenAI
    4. Uploads vectors to Pinecone
    
    Run this once before using the query generator, or whenever you update
    the organizational documentation.
    """
    if reset:
        if not click.confirm('⚠️  This will delete all existing vectors. Continue?'):
            click.echo("Aborted.")
            return
    
    try:
        from setup_vectordb import VectorDBSetup
        
        setup_tool = VectorDBSetup()
        setup_tool.setup(reset=reset)
        
    except Exception as e:
        click.echo(f"❌ Error during setup: {e}", err=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


@cli.command()
def test():
    """
    Test all components (embeddings, vector store, LLM).
    
    Verifies that all API keys are configured correctly and services are accessible.
    """
    click.echo("\n" + "="*70)
    click.echo("BQ Query Generator - Component Tests")
    click.echo("="*70 + "\n")
    
    # Test embeddings
    click.echo("Testing OpenAI embeddings...")
    try:
        from src.embeddings import EmbeddingGenerator
        embedder = EmbeddingGenerator()
        test_embedding = embedder.generate_embedding("test query")
        click.echo(f"✓ OpenAI embeddings working ({len(test_embedding)} dimensions)\n")
    except Exception as e:
        click.echo(f"✗ OpenAI embeddings failed: {e}\n", err=True)
    
    # Test Pinecone
    click.echo("Testing Pinecone connection...")
    try:
        from src.vector_store import VectorStore
        vs = VectorStore()
        if vs.connect_index():
            stats = vs.get_stats()
            click.echo(f"✓ Pinecone connected (vectors: {stats.total_vector_count})\n")
        else:
            click.echo("✗ Pinecone connection failed\n", err=True)
    except Exception as e:
        click.echo(f"✗ Pinecone failed: {e}\n", err=True)
    
    # Test Claude
    click.echo("Testing Claude AI...")
    try:
        from src.llm_client import LLMClient
        llm = LLMClient()
        if llm.test_connection():
            click.echo("✓ Claude AI connected\n")
        else:
            click.echo("✗ Claude AI connection failed\n", err=True)
    except Exception as e:
        click.echo(f"✗ Claude AI failed: {e}\n", err=True)
    
    click.echo("="*70 + "\n")


if __name__ == "__main__":
    cli()
