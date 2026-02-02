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


@cli.command(name='sync-columns')
@click.option('--table', '-t', help='Full table name to sync (e.g., project.dataset.table)')
@click.option('--all', '-a', 'sync_all', is_flag=True, help='Sync all tables from query_gen_tables')
@click.option('--dry-run', is_flag=True, help='Show changes without applying them')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed sync progress')
def sync_columns(table: str, sync_all: bool, dry_run: bool, verbose: bool):
    """
    Automatically sync table columns from BigQuery schema to query_gen_columns.
    
    This command:
    1. Fetches the actual schema from BigQuery INFORMATION_SCHEMA
    2. Compares with existing columns in query_gen_columns
    3. Detects added, updated, and removed columns
    4. Updates query_gen_columns table
    5. Incrementally syncs changes to Pinecone
    
    Examples:
        # Sync a specific table
        python main.py sync-columns --table "yotam-395120.peerplay.events"
        
        # Preview changes without applying
        python main.py sync-columns --table "yotam-395120.peerplay.events" --dry-run
        
        # Sync all tables registered in query_gen_tables
        python main.py sync-columns --all
    """
    if not table and not sync_all:
        click.echo("❌ Error: Must specify either --table or --all", err=True)
        click.echo("Try: python main.py sync-columns --help")
        sys.exit(1)
    
    try:
        from src.schema_sync import SchemaSync
        from src.incremental_sync import IncrementalPineconeSync
        from src.vector_store import VectorStore
        from src.embeddings import EmbeddingGenerator
        from src.bigquery_loader import BigQueryMetadataLoader
        
        # Initialize components
        schema_sync = SchemaSync()
        
        # Get tables to sync
        tables_to_sync = []
        if sync_all:
            # Load all tables from query_gen_tables
            loader = BigQueryMetadataLoader()
            all_tables = loader.load_tables()
            tables_to_sync = [t['name'] for t in all_tables]
            click.echo(f"\n🔄 Syncing {len(tables_to_sync)} tables from query_gen_tables...\n")
        else:
            tables_to_sync = [table]
        
        # Sync each table
        total_stats = {'deleted': 0, 'updated': 0, 'inserted': 0, 'tables': 0}
        
        for table_name in tables_to_sync:
            click.echo("="*70)
            click.echo(f"Syncing: {table_name}")
            click.echo("="*70)
            
            try:
                # Fetch and compare schema
                if verbose:
                    click.echo("\n📊 Fetching schema from BigQuery...")
                
                changes, stats = schema_sync.sync_table(table_name, dry_run=dry_run)
                
                # Display changes
                total_changes = len(changes['added']) + len(changes['updated']) + len(changes['removed'])
                
                if total_changes == 0:
                    click.echo("\n✓ Schema is up-to-date. No changes needed.\n")
                    continue
                
                click.echo(f"\n📋 Changes detected: {total_changes} total")
                
                if changes['added']:
                    click.echo(f"\n  ➕ Added: {len(changes['added'])} new columns")
                    for col in changes['added'][:5]:
                        click.echo(f"     - {col['name']} ({col['type']})")
                    if len(changes['added']) > 5:
                        click.echo(f"     ... and {len(changes['added']) - 5} more")
                
                if changes['updated']:
                    click.echo(f"\n  🔄 Updated: {len(changes['updated'])} columns")
                    for col in changes['updated'][:5]:
                        click.echo(f"     - {col['name']}: schema changed")
                    if len(changes['updated']) > 5:
                        click.echo(f"     ... and {len(changes['updated']) - 5} more")
                
                if changes['removed']:
                    click.echo(f"\n  ➖ Removed: {len(changes['removed'])} columns")
                    for col in changes['removed'][:5]:
                        click.echo(f"     - {col['name']}")
                    if len(changes['removed']) > 5:
                        click.echo(f"     ... and {len(changes['removed']) - 5} more")
                
                if dry_run:
                    click.echo("\n⚠️  Dry run - no changes applied\n")
                else:
                    # Apply changes (already done in sync_table)
                    click.echo(f"\n✓ Updated query_gen_columns:")
                    click.echo(f"  - Deleted: {stats['deleted']} rows")
                    click.echo(f"  - Updated: {stats['updated']} rows")
                    click.echo(f"  - Inserted: {stats['inserted']} rows")
                    
                    # Sync to Pinecone incrementally
                    if total_changes > 0:
                        click.echo("\n🔄 Syncing to Pinecone...")
                        
                        vs = VectorStore()
                        embedder = EmbeddingGenerator()
                        loader = BigQueryMetadataLoader()
                        pinecone_sync = IncrementalPineconeSync(vs, embedder, loader)
                        
                        pinecone_stats = pinecone_sync.sync_columns_for_table(
                            table_name, 
                            changes, 
                            verbose=verbose
                        )
                        
                        click.echo(f"✓ Pinecone updated:")
                        click.echo(f"  - Deleted: {pinecone_stats['deleted']} vectors")
                        click.echo(f"  - Updated: {pinecone_stats['updated']} vectors")
                        click.echo(f"  - Added: {pinecone_stats['added']} vectors")
                        if pinecone_stats.get('skipped', 0) > 0:
                            click.echo(f"  - Skipped: {pinecone_stats['skipped']} columns (no description)")
                    
                    # Update totals
                    total_stats['deleted'] += stats['deleted']
                    total_stats['updated'] += stats['updated']
                    total_stats['inserted'] += stats['inserted']
                    total_stats['tables'] += 1
                    
                    click.echo()
                
            except Exception as e:
                click.echo(f"\n❌ Error syncing {table_name}: {e}\n", err=True)
                if verbose:
                    import traceback
                    traceback.print_exc()
                continue
        
        # Summary
        if sync_all and not dry_run:
            click.echo("="*70)
            click.echo("SUMMARY")
            click.echo("="*70)
            click.echo(f"✓ Synced {total_stats['tables']} tables")
            click.echo(f"  - Total deleted: {total_stats['deleted']}")
            click.echo(f"  - Total updated: {total_stats['updated']}")
            click.echo(f"  - Total inserted: {total_stats['inserted']}")
            click.echo()
        
    except Exception as e:
        click.echo(f"\n❌ Error: {e}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    cli()
