#!/usr/bin/env python3
"""
GDPR Request Automation Tool - Main CLI Entry Point

Usage:
    python main.py process --users user1,user2,user3
    python main.py process --users-file users.txt
    python main.py status --user-id user123
    python main.py setup
"""

import click
import logging
import sys
from typing import List

from gdpr_tool.config import Config
from gdpr_tool.mixpanel import MixpanelClient
from gdpr_tool.singular import SingularClient
from gdpr_tool.bigquery import BigQueryClient
from gdpr_tool.orchestrator import GDPROrchestrator


def setup_logging(log_level: str = "INFO"):
    """Configure logging for the application."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('gdpr_tool.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )


def load_user_ids_from_file(file_path: str) -> List[str]:
    """Load user IDs from a text file (one per line)."""
    with open(file_path, 'r') as f:
        return [line.strip() for line in f if line.strip()]


def create_orchestrator(config: Config) -> GDPROrchestrator:
    """Create and configure the GDPR orchestrator."""
    # Initialize Mixpanel client
    mixpanel_config = config.mixpanel
    mixpanel_client = MixpanelClient(
        project_id=mixpanel_config['project_id'],
        token=mixpanel_config['token'],
        api_secret=mixpanel_config['api_secret']
    )

    # Initialize Singular client
    singular_config = config.singular
    singular_client = SingularClient(
        api_key=singular_config['api_key']
    )

    # Initialize BigQuery client
    bq_config = config.bigquery
    bigquery_client = BigQueryClient(
        project_id=bq_config['project_id'],
        credentials_path=bq_config.get('credentials_path'),
        status_table=bq_config.get('status_table', 'gdpr.deletion_status')
    )

    # Create orchestrator
    return GDPROrchestrator(mixpanel_client, singular_client, bigquery_client)


@click.group()
@click.option('--config', default='config.yaml', help='Path to configuration file')
@click.option('--log-level', default='INFO', help='Logging level')
@click.pass_context
def cli(ctx, config, log_level):
    """GDPR Request Automation Tool"""
    setup_logging(log_level)
    ctx.ensure_object(dict)
    ctx.obj['config_path'] = config


@cli.command()
@click.pass_context
def setup(ctx):
    """Setup the BigQuery status tracking table."""
    try:
        config = Config(ctx.obj['config_path'])
        orchestrator = create_orchestrator(config)

        click.echo("Creating BigQuery status tracking table...")
        success = orchestrator.setup_status_table()

        if success:
            click.echo("✓ Status table created successfully")
        else:
            click.echo("✗ Failed to create status table", err=True)
            sys.exit(1)

    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--users', help='Comma-separated list of user IDs')
@click.option('--users-file', help='Path to file containing user IDs (one per line)')
@click.option('--user-id-column', default='user_id', help='Column name for user ID in BigQuery')
@click.option('--singular-id-type', default='user_id', help='ID type for Singular API')
@click.pass_context
def process(ctx, users, users_file, user_id_column, singular_id_type):
    """
    Process GDPR deletion requests for users.

    Provide user IDs either via --users or --users-file.
    """
    try:
        # Load configuration
        config = Config(ctx.obj['config_path'])

        # Get user IDs
        if users:
            user_ids = [u.strip() for u in users.split(',')]
        elif users_file:
            user_ids = load_user_ids_from_file(users_file)
        else:
            click.echo("Error: Must provide either --users or --users-file", err=True)
            sys.exit(1)

        if not user_ids:
            click.echo("Error: No user IDs provided", err=True)
            sys.exit(1)

        # Get BigQuery tables from config
        bq_config = config.bigquery
        tables = bq_config.get('tables_to_delete', [])

        if not tables:
            click.echo("Warning: No BigQuery tables specified in config", err=True)

        click.echo(f"Processing GDPR deletion for {len(user_ids)} user(s)...")
        click.echo(f"BigQuery tables: {', '.join(tables)}")

        # Create orchestrator and process deletions
        orchestrator = create_orchestrator(config)

        results = orchestrator.process_batch_deletion(
            user_ids,
            tables,
            user_id_column,
            singular_id_type
        )

        # Display results
        success_count = sum(1 for r in results if r.get("overall_success"))
        click.echo(f"\n{'='*60}")
        click.echo(f"Results: {success_count}/{len(user_ids)} successful")
        click.echo(f"{'='*60}\n")

        for result in results:
            user_id = result['user_id']
            status = "✓" if result['overall_success'] else "✗"

            click.echo(f"{status} User: {user_id}")
            click.echo(f"  Mixpanel: {result['mixpanel'].get('success', False)}")
            click.echo(f"  Singular: {result['singular'].get('success', False)}")
            click.echo(f"  BigQuery: {result['bigquery'].get('success', False)}")
            click.echo()

        if success_count < len(user_ids):
            sys.exit(1)

    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)
        logging.exception("Failed to process deletions")
        sys.exit(1)


@cli.command()
@click.option('--user-id', required=True, help='User ID to check status for')
@click.pass_context
def status(ctx, user_id):
    """Check the deletion status for a specific user."""
    try:
        config = Config(ctx.obj['config_path'])
        orchestrator = create_orchestrator(config)

        click.echo(f"Checking deletion status for user: {user_id}")

        status_info = orchestrator.get_deletion_status(user_id)

        if status_info:
            click.echo(f"\n{'='*60}")
            click.echo(f"User ID: {status_info.get('user_id')}")
            click.echo(f"Overall Status: {status_info.get('deletion_status')}")
            click.echo(f"Request Date: {status_info.get('request_date')}")
            click.echo(f"Last Updated: {status_info.get('last_updated')}")
            click.echo(f"\nMixpanel Status: {status_info.get('mixpanel_status')}")
            click.echo(f"Mixpanel Task ID: {status_info.get('mixpanel_task_id')}")
            click.echo(f"\nSingular Status: {status_info.get('singular_status')}")
            click.echo(f"Singular Request ID: {status_info.get('singular_request_id')}")
            click.echo(f"\nBigQuery Status: {status_info.get('bigquery_status')}")
            click.echo(f"BigQuery Tables: {status_info.get('bigquery_tables_affected')}")

            if status_info.get('error_message'):
                click.echo(f"\nError: {status_info.get('error_message')}")

            if status_info.get('completed_date'):
                click.echo(f"\nCompleted: {status_info.get('completed_date')}")

            click.echo(f"{'='*60}\n")
        else:
            click.echo(f"No deletion record found for user: {user_id}")

    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    cli(obj={})
