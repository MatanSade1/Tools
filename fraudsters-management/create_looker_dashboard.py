"""
Looker Studio Dashboard Builder for Fraudsters Management

This script creates Looker Studio dashboards programmatically using:
1. Looker Studio Linking API for dynamic report URLs
2. BigQuery data source configuration
3. Dashboard template generation
4. Looker Studio API for asset management (if available)

IMPORTANT LIMITATIONS:
- Looker Studio API does NOT support full programmatic dashboard creation
- The API can only manage assets (search, permissions) - not create dashboards
- This script generates configurations and templates that must be manually imported
- Requires Google Workspace/Cloud Identity for API access

WORKAROUNDS:
- Use the generated configuration JSON to manually create dashboards
- Use the Linking API to create dynamic URLs to pre-configured reports
- Use Google Apps Script to automate data preparation
"""

import os
import json
import urllib.parse
from typing import Dict, List, Optional, Any
from datetime import datetime
import sys

# Add shared directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from shared.config import get_config
from shared.bigquery_client import get_bigquery_client
from google.cloud import bigquery

# Try to import Google API client (optional - for advanced features)
try:
    from googleapiclient.discovery import build
    from google.oauth2 import service_account
    HAS_GOOGLE_API = True
except ImportError:
    HAS_GOOGLE_API = False
    print("⚠️  google-api-python-client not installed. Some advanced features will be unavailable.")
    print("   Install with: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")

# Configuration
PROJECT_ID = "yotam-395120"
DATASET_ID = "peerplay"

# BigQuery tables for fraudsters management
TABLES = {
    "potential_fraudsters": f"{PROJECT_ID}.{DATASET_ID}.potential_fraudsters",
    "potential_fraudsters_stage": f"{PROJECT_ID}.{DATASET_ID}.potential_fraudsters_stage",
    "fraudsters": f"{PROJECT_ID}.{DATASET_ID}.fraudsters",
    "fraudsters_stage": f"{PROJECT_ID}.{DATASET_ID}.fraudsters_stage",
    "offer_wall_progression_cheaters": f"{PROJECT_ID}.{DATASET_ID}.offer_wall_progression_cheaters",
    "dim_player": f"{PROJECT_ID}.{DATASET_ID}.dim_player",
}


class LookerStudioDashboardBuilder:
    """Build Looker Studio dashboards programmatically"""
    
    def __init__(self, project_id: str = PROJECT_ID, use_api: bool = False):
        self.project_id = project_id
        self.client = get_bigquery_client()
        self.use_api = use_api and HAS_GOOGLE_API
        self.looker_service = None
        
        if self.use_api:
            try:
                # Initialize Looker Studio API service
                # Note: This requires OAuth 2.0 credentials with domain-wide delegation
                credentials = self._get_credentials()
                if credentials:
                    self.looker_service = build('datastudio', 'v1', credentials=credentials)
                    print("✅ Looker Studio API initialized")
                else:
                    print("⚠️  Could not initialize Looker Studio API - using configuration generation only")
                    self.use_api = False
            except Exception as e:
                print(f"⚠️  Looker Studio API initialization failed: {e}")
                print("   Continuing with configuration generation only")
                self.use_api = False
    
    def _get_credentials(self):
        """Get OAuth 2.0 credentials for Looker Studio API"""
        # This requires service account with domain-wide delegation
        # or OAuth 2.0 user credentials
        try:
            # Try service account from environment
            service_account_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            if service_account_path and os.path.exists(service_account_path):
                credentials = service_account.Credentials.from_service_account_file(
                    service_account_path,
                    scopes=['https://www.googleapis.com/auth/datastudio']
                )
                return credentials
        except Exception as e:
            print(f"   Service account auth failed: {e}")
        
        return None
    
    def search_reports(self, query: Optional[str] = None) -> List[Dict]:
        """
        Search for existing Looker Studio reports using the API.
        
        Args:
            query: Search query string
        
        Returns:
            List of report metadata dictionaries
        """
        if not self.use_api or not self.looker_service:
            print("⚠️  Looker Studio API not available - cannot search reports")
            return []
        
        try:
            # Note: The actual API endpoint may differ - this is a placeholder
            # The Looker Studio API documentation should be consulted for exact endpoints
            print("⚠️  Report search requires specific API implementation")
            print("   Consult Looker Studio API docs for exact endpoints")
            return []
        except Exception as e:
            print(f"❌ Error searching reports: {e}")
            return []
        
    def generate_linking_api_url(
        self,
        report_id: Optional[str] = None,
        data_source_configs: Optional[List[Dict]] = None,
        page_id: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate a Looker Studio Linking API URL for dynamic dashboard access.
        
        Args:
            report_id: Existing Looker Studio report ID (optional)
            data_source_configs: List of data source configurations
            page_id: Specific page ID to link to
            filters: Dictionary of filters to apply
        
        Returns:
            Looker Studio URL with Linking API parameters
        """
        base_url = "https://lookerstudio.google.com/reporting"
        
        params = {}
        
        if report_id:
            params["reportId"] = report_id
        
        if data_source_configs:
            # Convert data source configs to URL parameters
            # Note: This is a simplified version - full implementation would require
            # proper encoding of data source configurations
            for i, ds_config in enumerate(data_source_configs):
                if "table" in ds_config:
                    params[f"ds.{i}.table"] = ds_config["table"]
                if "connector" in ds_config:
                    params[f"ds.{i}.connector"] = ds_config["connector"]
        
        if page_id:
            params["pageId"] = page_id
        
        if filters:
            for key, value in filters.items():
                params[f"params.{key}"] = str(value)
        
        if params:
            query_string = urllib.parse.urlencode(params)
            return f"{base_url}?{query_string}"
        
        return base_url
    
    def create_bigquery_data_source_config(
        self,
        table_name: str,
        table_id: str,
        connector_id: str = "bigquery"
    ) -> Dict[str, Any]:
        """
        Create a BigQuery data source configuration for Looker Studio.
        
        Args:
            table_name: Display name for the data source
            table_id: Full BigQuery table ID (project.dataset.table)
            connector_id: Connector type (default: bigquery)
        
        Returns:
            Data source configuration dictionary
        """
        return {
            "name": table_name,
            "connector": connector_id,
            "table": table_id,
            "type": "BIGQUERY",
            "projectId": self.project_id,
            "datasetId": table_id.split(".")[1] if "." in table_id else DATASET_ID,
            "tableId": table_id.split(".")[2] if table_id.count(".") >= 2 else table_id.split(".")[-1]
        }
    
    def generate_dashboard_config(self) -> Dict[str, Any]:
        """
        Generate a complete dashboard configuration for fraudsters management.
        
        Returns:
            Dictionary containing dashboard configuration
        """
        # Create data source configurations
        data_sources = []
        for table_key, table_id in TABLES.items():
            if "stage" not in table_key:  # Focus on production tables for main dashboard
                ds_config = self.create_bigquery_data_source_config(
                    table_name=table_key.replace("_", " ").title(),
                    table_id=table_id
                )
                data_sources.append(ds_config)
        
        # Define dashboard structure
        dashboard_config = {
            "title": "Fraudsters Management Dashboard",
            "description": "Comprehensive dashboard for monitoring and analyzing fraudster detection and management",
            "created_at": datetime.now().isoformat(),
            "data_sources": data_sources,
            "pages": [
                {
                    "name": "Overview",
                    "description": "High-level fraudster metrics and trends",
                    "charts": [
                        {
                            "type": "scorecard",
                            "title": "Total Fraudsters",
                            "metric": "COUNT_DISTINCT(distinct_id)",
                            "data_source": "fraudsters"
                        },
                        {
                            "type": "scorecard",
                            "title": "Potential Fraudsters",
                            "metric": "COUNT_DISTINCT(distinct_id)",
                            "data_source": "potential_fraudsters"
                        },
                        {
                            "type": "scorecard",
                            "title": "Offerwall Cheaters",
                            "metric": "COUNT_DISTINCT(distinct_id)",
                            "data_source": "offer_wall_progression_cheaters"
                        },
                        {
                            "type": "time_series",
                            "title": "Fraudsters Over Time",
                            "dimension": "date",
                            "metric": "COUNT_DISTINCT(distinct_id)",
                            "data_source": "fraudsters"
                        }
                    ]
                },
                {
                    "name": "Fraud Flags Analysis",
                    "description": "Breakdown of fraud detection flags",
                    "charts": [
                        {
                            "type": "bar_chart",
                            "title": "Fraud Flags Distribution",
                            "dimension": "flag_type",
                            "metric": "COUNT(distinct_id)",
                            "data_source": "fraudsters"
                        },
                        {
                            "type": "pie_chart",
                            "title": "Manual vs Automated Detection",
                            "dimension": "detection_type",
                            "metric": "COUNT(distinct_id)",
                            "data_source": "fraudsters"
                        },
                        {
                            "type": "table",
                            "title": "Top Fraud Flags",
                            "dimensions": ["flag_type", "distinct_id"],
                            "metrics": ["count"],
                            "data_source": "fraudsters"
                        }
                    ]
                },
                {
                    "name": "Platform Analysis",
                    "description": "Fraudster analysis by platform",
                    "charts": [
                        {
                            "type": "bar_chart",
                            "title": "Fraudsters by Platform",
                            "dimension": "platform",
                            "metric": "COUNT_DISTINCT(distinct_id)",
                            "data_source": "fraudsters"
                        },
                        {
                            "type": "geo_chart",
                            "title": "Fraudsters by Country",
                            "dimension": "country",
                            "metric": "COUNT_DISTINCT(distinct_id)",
                            "data_source": "fraudsters"
                        }
                    ]
                },
                {
                    "name": "Detailed View",
                    "description": "Detailed fraudster records and analysis",
                    "charts": [
                        {
                            "type": "table",
                            "title": "Fraudster Details",
                            "dimensions": [
                                "distinct_id",
                                "platform",
                                "country",
                                "install_date"
                            ],
                            "metrics": [
                                "total_fraud_flags",
                                "manual_identification_fraud_purchase_flag"
                            ],
                            "data_source": "fraudsters"
                        }
                    ]
                }
            ],
            "filters": [
                {
                    "name": "Date Range",
                    "type": "date_range",
                    "field": "date"
                },
                {
                    "name": "Platform",
                    "type": "dropdown",
                    "field": "platform"
                },
                {
                    "name": "Fraud Flag",
                    "type": "dropdown",
                    "field": "flag_type"
                }
            ]
        }
        
        return dashboard_config
    
    def generate_sql_queries_for_charts(self) -> Dict[str, str]:
        """
        Generate SQL queries that can be used to create charts in Looker Studio.
        
        Returns:
            Dictionary of chart names to SQL queries
        """
        queries = {
            "total_fraudsters": f"""
                SELECT COUNT(DISTINCT distinct_id) as total_fraudsters
                FROM `{TABLES['fraudsters']}`
            """,
            
            "fraudsters_over_time": f"""
                SELECT 
                    DATE(inserted_at) as date,
                    COUNT(DISTINCT distinct_id) as fraudster_count
                FROM `{TABLES['fraudsters']}`
                WHERE inserted_at >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
                GROUP BY date
                ORDER BY date
            """,
            
            "fraud_flags_breakdown": f"""
                SELECT 
                    CASE 
                        WHEN manual_identification_fraud_purchase_flag = 1 THEN 'Manual Identification'
                        WHEN fast_progression_flag = 1 THEN 'Fast Progression'
                        WHEN excessive_harvests_flag = 1 THEN 'Excessive Harvests'
                        WHEN suspicious_purchase_flag = 1 THEN 'Suspicious Purchase'
                        WHEN rapid_purchases_flag = 1 THEN 'Rapid Purchases'
                        WHEN purchase_flow_anomaly_flag = 1 THEN 'Purchase Flow Anomaly'
                        WHEN high_balance_flag = 1 THEN 'High Balance'
                        WHEN negative_balance_flag = 1 THEN 'Negative Balance'
                        WHEN large_jump_flag = 1 THEN 'Large Jump'
                        WHEN privacy_abandonment_flag = 1 THEN 'Privacy Abandonment'
                        WHEN rapid_chapter_progression_flag = 1 THEN 'Rapid Chapter Progression'
                        WHEN refund_abuse_flag = 1 THEN 'Refund Abuse'
                        WHEN high_tutorial_balance_flag = 1 THEN 'High Tutorial Balance'
                        WHEN multiple_chapter1_purchases_flag = 1 THEN 'Multiple Chapter 1 Purchases'
                        WHEN duplicate_transaction_flag = 1 THEN 'Duplicate Transaction'
                        ELSE 'Other'
                    END as flag_type,
                    COUNT(DISTINCT distinct_id) as count
                FROM `{TABLES['fraudsters']}`
                GROUP BY flag_type
                ORDER BY count DESC
            """,
            
            "platform_breakdown": f"""
                SELECT 
                    COALESCE(dp.first_platform, 'Unknown') as platform,
                    COUNT(DISTINCT f.distinct_id) as fraudster_count
                FROM `{TABLES['fraudsters']}` f
                LEFT JOIN `{TABLES['dim_player']}` dp ON f.distinct_id = dp.distinct_id
                GROUP BY platform
                ORDER BY fraudster_count DESC
            """,
            
            "fraudsters_by_country": f"""
                SELECT 
                    COALESCE(pf.first_country, 'Unknown') as country,
                    COUNT(DISTINCT f.distinct_id) as fraudster_count
                FROM `{TABLES['fraudsters']}` f
                LEFT JOIN `{TABLES['potential_fraudsters']}` pf ON f.distinct_id = pf.distinct_id
                GROUP BY country
                ORDER BY fraudster_count DESC
                LIMIT 20
            """,
            
            "manual_vs_automated": f"""
                SELECT 
                    CASE 
                        WHEN manual_identification_fraud_purchase_flag = 1 THEN 'Manual Detection'
                        ELSE 'Automated Detection'
                    END as detection_type,
                    COUNT(DISTINCT distinct_id) as count
                FROM `{TABLES['fraudsters']}`
                GROUP BY detection_type
            """,
            
            "recent_fraudsters": f"""
                SELECT 
                    f.distinct_id,
                    COALESCE(dp.first_platform, 'Unknown') as platform,
                    COALESCE(pf.first_country, 'Unknown') as country,
                    dp.install_date,
                    f.manual_identification_fraud_purchase_flag,
                    (f.fast_progression_flag + f.excessive_harvests_flag + 
                     f.suspicious_purchase_flag + f.rapid_purchases_flag +
                     f.purchase_flow_anomaly_flag + f.high_balance_flag +
                     f.negative_balance_flag + f.large_jump_flag +
                     f.privacy_abandonment_flag + f.rapid_chapter_progression_flag +
                     f.refund_abuse_flag + f.high_tutorial_balance_flag +
                     f.multiple_chapter1_purchases_flag + f.duplicate_transaction_flag) as total_flags
                FROM `{TABLES['fraudsters']}` f
                LEFT JOIN `{TABLES['dim_player']}` dp ON f.distinct_id = dp.distinct_id
                LEFT JOIN `{TABLES['potential_fraudsters']}` pf ON f.distinct_id = pf.distinct_id
                ORDER BY f.inserted_at DESC
                LIMIT 1000
            """
        }
        
        return queries
    
    def create_dashboard_import_file(self, output_path: str = "looker_dashboard_config.json"):
        """
        Create a JSON file with dashboard configuration that can be used as a reference
        or imported into Looker Studio.
        
        Args:
            output_path: Path to save the configuration file
        """
        config = self.generate_dashboard_config()
        queries = self.generate_sql_queries_for_charts()
        
        full_config = {
            "dashboard_config": config,
            "sql_queries": queries,
            "data_sources": [
                {
                    "name": ds["name"],
                    "table_id": ds["tableId"],
                    "full_table_id": TABLES.get(ds["name"].lower().replace(" ", "_"), "")
                }
                for ds in config["data_sources"]
            ],
            "instructions": {
                "step1": "Open Looker Studio (https://lookerstudio.google.com)",
                "step2": "Create a new report",
                "step3": "Add BigQuery data sources using the table IDs provided",
                "step4": "Use the SQL queries provided to create custom charts",
                "step5": "Organize charts according to the pages defined in dashboard_config"
            }
        }
        
        with open(output_path, 'w') as f:
            json.dump(full_config, f, indent=2)
        
        print(f"✅ Dashboard configuration saved to {output_path}")
        return output_path
    
    def create_automated_setup_script(self, output_path: str = "setup_looker_dashboard.sh"):
        """
        Create a shell script with automated setup commands.
        
        Args:
            output_path: Path to save the setup script
        """
        script_content = f"""#!/bin/bash
# Automated Looker Studio Dashboard Setup Script
# Generated by create_looker_dashboard.py

echo "🚀 Setting up Looker Studio Dashboard for Fraudsters Management"
echo ""

# Configuration
PROJECT_ID="{self.project_id}"
DATASET_ID="{DATASET_ID}"

echo "📊 Project: $PROJECT_ID"
echo "📁 Dataset: $DATASET_ID"
echo ""

echo "⚠️  IMPORTANT: Looker Studio does not support full programmatic dashboard creation."
echo "   This script provides the configuration and SQL queries needed."
echo "   You must manually create the dashboard in Looker Studio UI."
echo ""

echo "📋 Next Steps:"
echo "   1. Open https://lookerstudio.google.com"
echo "   2. Create a new report"
echo "   3. Add BigQuery data sources using the tables in looker_dashboard_config.json"
echo "   4. Use the SQL queries provided to create custom charts"
echo ""

echo "✅ Configuration file: looker_dashboard_config.json"
echo "✅ SQL queries are included in the configuration file"
echo ""
echo "🔗 To generate dynamic dashboard URLs, run:"
echo "   python create_looker_dashboard.py --generate-url"
echo ""
"""
        
        with open(output_path, 'w') as f:
            f.write(script_content)
        
        # Make executable
        os.chmod(output_path, 0o755)
        print(f"✅ Setup script saved to {output_path}")
        return output_path
    
    def print_setup_instructions(self):
        """Print step-by-step instructions for setting up the dashboard"""
        print("\n" + "="*80)
        print("LOOKER STUDIO DASHBOARD SETUP INSTRUCTIONS")
        print("="*80)
        print("\n⚠️  IMPORTANT LIMITATION:")
        print("   Looker Studio API does NOT support programmatic dashboard creation.")
        print("   This tool generates configurations that you must import manually.")
        print("")
        
        print("📊 Step 1: Create Data Sources in Looker Studio")
        print("   - Go to https://lookerstudio.google.com")
        print("   - Click 'Create' > 'Data Source'")
        print("   - Select 'BigQuery' connector")
        print("   - Authenticate with your Google account")
        print("   - Add the following tables:")
        for table_key, table_id in TABLES.items():
            if "stage" not in table_key:
                print(f"     • {table_key}: {table_id}")
        
        print("\n📈 Step 2: Create a New Report")
        print("   - Click 'Create' > 'Report'")
        print("   - Add the data sources you created in Step 1")
        print("   - Or use 'Add a data source' from within the report")
        
        print("\n📋 Step 3: Build Charts")
        print("   - Open 'looker_dashboard_config.json' for reference")
        print("   - Use the SQL queries provided to create custom SQL data sources")
        print("   - Add charts according to the dashboard_config structure:")
        print("     • Overview page: Scorecards and time series")
        print("     • Fraud Flags Analysis: Bar charts and pie charts")
        print("     • Platform Analysis: Bar charts and geo charts")
        print("     • Detailed View: Tables with fraudster details")
        
        print("\n🔗 Step 4: Generate Dynamic URLs (Optional)")
        print("   - Use the generate_linking_api_url() method to create")
        print("     dynamic dashboard URLs with filters")
        print("   - These URLs can be embedded in other applications")
        
        print("\n🤖 Step 5: Automation Options")
        print("   - Use Google Apps Script to automate data updates")
        print("   - Schedule BigQuery queries to refresh data")
        print("   - Use the Linking API for dynamic report access")
        
        print("\n" + "="*80)
        print("✅ Configuration file generated: looker_dashboard_config.json")
        print("✅ Setup script generated: setup_looker_dashboard.sh")
        print("="*80 + "\n")


def main():
    """Main function to generate Looker Studio dashboard configuration"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate Looker Studio dashboard configuration')
    parser.add_argument('--use-api', action='store_true', 
                       help='Attempt to use Looker Studio API (requires OAuth setup)')
    parser.add_argument('--generate-url', action='store_true',
                       help='Generate example Linking API URL')
    parser.add_argument('--output', type=str, default='looker_dashboard_config.json',
                       help='Output path for configuration file')
    
    args = parser.parse_args()
    
    print("🚀 Building Looker Studio Dashboard Configuration...")
    print(f"📊 Project: {PROJECT_ID}")
    print(f"📁 Dataset: {DATASET_ID}\n")
    
    if args.use_api and not HAS_GOOGLE_API:
        print("⚠️  --use-api specified but google-api-python-client not installed")
        print("   Install with: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
        print("   Continuing without API access...\n")
    
    builder = LookerStudioDashboardBuilder(use_api=args.use_api)
    
    # Generate and save configuration
    config_path = builder.create_dashboard_import_file(args.output)
    
    # Create setup script
    builder.create_automated_setup_script()
    
    # Print setup instructions
    builder.print_setup_instructions()
    
    # Generate example linking URL if requested
    if args.generate_url:
        example_url = builder.generate_linking_api_url(
            data_source_configs=[
                builder.create_bigquery_data_source_config(
                    "Fraudsters",
                    TABLES["fraudsters"]
                )
            ]
        )
        print(f"🔗 Example Linking API URL:\n{example_url}\n")
    
    print("✨ Dashboard configuration generation complete!")
    print("   Files generated:")
    print(f"   • {config_path}")
    print("   • setup_looker_dashboard.sh")
    print("\n   Next steps:")
    print("   1. Review looker_dashboard_config.json")
    print("   2. Follow the setup instructions above")
    print("   3. Use the SQL queries to create custom charts")
    print("   4. Manually create the dashboard in Looker Studio UI")


if __name__ == "__main__":
    main()

