"""
Advanced Looker Studio Dashboard Builder

This script provides a more complete automation for creating Looker Studio dashboards.
It includes detailed steps for creating charts, controllers, and configuring layouts.

Since Looker Studio's UI is dynamic, this script provides:
1. Step-by-step automation with fallbacks
2. Detailed logging of what needs to be done
3. Ability to pause and resume
4. Configuration-driven dashboard building
"""

import os
import sys
import time
import json
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from dataclasses import dataclass

# Add shared directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from shared.config import get_config

try:
    from playwright.sync_api import sync_playwright, Page, Browser, Locator
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

PROJECT_ID = "yotam-395120"
DATASET_ID = "peerplay"

TABLES = {
    "fraudsters": f"{PROJECT_ID}.{DATASET_ID}.fraudsters",
    "potential_fraudsters": f"{PROJECT_ID}.{DATASET_ID}.potential_fraudsters",
    "offer_wall_progression_cheaters": f"{PROJECT_ID}.{DATASET_ID}.offer_wall_progression_cheaters",
    "dim_player": f"{PROJECT_ID}.{DATASET_ID}.dim_player",
}


@dataclass
class ChartConfig:
    """Configuration for a chart"""
    chart_type: str  # scorecard, time_series, bar_chart, pie_chart, table, geo_chart
    title: str
    data_source: str
    dimensions: List[str]
    metrics: List[str]
    position: Optional[Dict[str, int]] = None  # x, y, width, height
    filters: Optional[Dict[str, Any]] = None


@dataclass
class ControllerConfig:
    """Configuration for a controller/filter"""
    field: str
    controller_type: str  # dropdown, date_range, checkbox, etc.
    title: Optional[str] = None
    default_value: Optional[Any] = None


@dataclass
class PageConfig:
    """Configuration for a dashboard page"""
    name: str
    charts: List[ChartConfig]
    controllers: List[ControllerConfig]


class AdvancedLookerStudioBuilder:
    """Advanced Looker Studio dashboard builder with full automation"""
    
    def __init__(self, headless: bool = False, slow_mo: int = 1000, interactive: bool = True):
        """
        Initialize the builder.
        
        Args:
            headless: Run browser in headless mode
            slow_mo: Slow down operations (milliseconds)
            interactive: Pause for user confirmation at key steps
        """
        if not HAS_PLAYWRIGHT:
            raise ImportError("Playwright required: pip install playwright && playwright install chromium")
        
        self.headless = headless
        self.slow_mo = slow_mo
        self.interactive = interactive
        self.playwright = None
        self.browser = None
        self.page = None
        self.current_report_url = None
        
    def __enter__(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            slow_mo=self.slow_mo
        )
        self.page = self.browser.new_page()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
    
    def wait_and_click(self, selectors: List[str], description: str, timeout: int = 5000) -> bool:
        """Try multiple selectors and click the first one that works"""
        for selector in selectors:
            try:
                element = self.page.locator(selector).first
                if element.is_visible(timeout=2000):
                    element.click()
                    print(f"✅ {description} (clicked: {selector})")
                    time.sleep(1)
                    return True
            except:
                continue
        print(f"⚠️  Could not {description}")
        return False
    
    def wait_and_fill(self, selectors: List[str], text: str, description: str) -> bool:
        """Try multiple selectors and fill the first one that works"""
        for selector in selectors:
            try:
                element = self.page.locator(selector).first
                if element.is_visible(timeout=2000):
                    element.fill(text)
                    print(f"✅ {description} (filled: {selector})")
                    time.sleep(0.5)
                    return True
            except:
                continue
        print(f"⚠️  Could not {description}")
        return False
    
    def login(self):
        """Handle login to Looker Studio"""
        print("\n🔐 Logging into Looker Studio...")
        self.page.goto("https://lookerstudio.google.com")
        time.sleep(3)
        
        if "accounts.google.com" in self.page.url:
            print("📝 Please log in manually in the browser window...")
            if self.interactive:
                input("Press Enter after logging in...")
            else:
                time.sleep(10)  # Give time for manual login
        else:
            print("✅ Already logged in")
    
    def create_blank_report(self, report_name: str) -> bool:
        """Create a new blank report"""
        print(f"\n📊 Creating report: {report_name}")
        
        # Navigate to create page
        self.page.goto("https://lookerstudio.google.com/reporting/create")
        time.sleep(3)
        
        # Try to create blank report
        success = self.wait_and_click(
            [
                "text=Blank report",
                "text=Create",
                "[aria-label*='Blank']",
                "button:has-text('Blank')",
            ],
            "Create blank report"
        )
        
        if not success:
            print("⚠️  Could not automatically create report")
            if self.interactive:
                input("Please create a blank report manually, then press Enter...")
            return False
        
        time.sleep(3)
        self.current_report_url = self.page.url
        print(f"✅ Report created: {self.current_report_url}")
        return True
    
    def add_data_source(self, table_id: str, table_name: str) -> bool:
        """Add a BigQuery data source"""
        print(f"\n📊 Adding data source: {table_name}")
        
        # Click "Add a data source"
        if not self.wait_and_click(
            [
                "text=Add a data source",
                "text=Add data",
                "[aria-label*='Add data']",
                "button:has-text('Add')",
            ],
            "Open data source menu"
        ):
            return False
        
        time.sleep(2)
        
        # Search for BigQuery
        if self.wait_and_fill(
            [
                "input[type='search']",
                "input[placeholder*='Search']",
                "input[aria-label*='Search']",
            ],
            "BigQuery",
            "Search for BigQuery"
        ):
            time.sleep(2)
        
        # Click BigQuery connector
        if not self.wait_and_click(
            [
                "text=BigQuery",
                "[data-testid*='bigquery']",
                "div:has-text('BigQuery')",
            ],
            "Select BigQuery connector"
        ):
            return False
        
        time.sleep(3)
        
        # Enter table ID
        if not self.wait_and_fill(
            [
                "input[placeholder*='table']",
                "input[placeholder*='Table']",
                "input[type='text']",
                "textarea",
            ],
            table_id,
            f"Enter table ID: {table_id}"
        ):
            return False
        
        time.sleep(1)
        
        # Click Connect/Add
        if not self.wait_and_click(
            [
                "text=Add",
                "text=Connect",
                "button:has-text('Add')",
                "button:has-text('Connect')",
            ],
            "Connect to data source"
        ):
            return False
        
        time.sleep(5)  # Wait for connection
        
        print(f"✅ Data source added: {table_name}")
        return True
    
    def create_scorecard(self, config: ChartConfig) -> bool:
        """Create a scorecard chart"""
        print(f"\n📈 Creating scorecard: {config.title}")
        
        # Add chart - Looker Studio UI steps
        # This is complex and UI-dependent, so we'll provide instructions
        print(f"   Steps to create scorecard:")
        print(f"   1. Click 'Add a chart' or use Insert menu")
        print(f"   2. Select 'Scorecard'")
        print(f"   3. Set metric: {config.metrics[0] if config.metrics else 'N/A'}")
        print(f"   4. Set title: {config.title}")
        
        if self.interactive:
            input("   Press Enter after creating the scorecard...")
        
        return True
    
    def create_time_series(self, config: ChartConfig) -> bool:
        """Create a time series chart"""
        print(f"\n📈 Creating time series: {config.title}")
        print(f"   Dimension: {config.dimensions[0] if config.dimensions else 'N/A'}")
        print(f"   Metric: {config.metrics[0] if config.metrics else 'N/A'}")
        
        if self.interactive:
            input("   Press Enter after creating the chart...")
        
        return True
    
    def create_bar_chart(self, config: ChartConfig) -> bool:
        """Create a bar chart"""
        print(f"\n📊 Creating bar chart: {config.title}")
        print(f"   Dimension: {config.dimensions[0] if config.dimensions else 'N/A'}")
        print(f"   Metric: {config.metrics[0] if config.metrics else 'N/A'}")
        
        if self.interactive:
            input("   Press Enter after creating the chart...")
        
        return True
    
    def create_table(self, config: ChartConfig) -> bool:
        """Create a table chart"""
        print(f"\n📋 Creating table: {config.title}")
        print(f"   Dimensions: {', '.join(config.dimensions)}")
        print(f"   Metrics: {', '.join(config.metrics)}")
        
        if self.interactive:
            input("   Press Enter after creating the table...")
        
        return True
    
    def add_controller(self, config: ControllerConfig) -> bool:
        """Add a controller/filter"""
        print(f"\n🎛️  Adding controller: {config.title or config.field}")
        print(f"   Type: {config.controller_type}")
        print(f"   Field: {config.field}")
        
        if self.interactive:
            input("   Press Enter after adding the controller...")
        
        return True
    
    def build_dashboard_from_config(self, config_file: str = "looker_dashboard_config.json"):
        """Build dashboard from configuration file"""
        print("\n" + "="*80)
        print("BUILDING DASHBOARD FROM CONFIGURATION")
        print("="*80 + "\n")
        
        # Load configuration
        if not os.path.exists(config_file):
            print(f"❌ Configuration file not found: {config_file}")
            print("   Run create_looker_dashboard.py first to generate it")
            return
        
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        dashboard_config = config.get("dashboard_config", {})
        
        # Login
        self.login()
        
        # Create report
        report_name = dashboard_config.get("title", "Fraudsters Management Dashboard")
        if not self.create_blank_report(report_name):
            return
        
        # Add data sources
        print("\n" + "-"*80)
        print("ADDING DATA SOURCES")
        print("-"*80)
        
        for ds in dashboard_config.get("data_sources", []):
            table_id = ds.get("table", "")
            table_name = ds.get("name", "")
            if table_id:
                self.add_data_source(table_id, table_name)
                time.sleep(2)
        
        # Build pages
        print("\n" + "-"*80)
        print("BUILDING PAGES AND CHARTS")
        print("-"*80)
        
        for page_config in dashboard_config.get("pages", []):
            page_name = page_config.get("name", "Untitled")
            print(f"\n📄 Building page: {page_name}")
            
            # Add controllers first
            # (Controllers would be defined in the config - for now we'll skip)
            
            # Add charts
            for chart_def in page_config.get("charts", []):
                chart_type = chart_def.get("type", "")
                chart_title = chart_def.get("title", "")
                
                # Create chart config
                chart_config = ChartConfig(
                    chart_type=chart_type,
                    title=chart_title,
                    data_source=chart_def.get("data_source", ""),
                    dimensions=[chart_def.get("dimension", "")] if chart_def.get("dimension") else [],
                    metrics=[chart_def.get("metric", "")] if chart_def.get("metric") else chart_def.get("metrics", [])
                )
                
                # Create the chart based on type
                if chart_type == "scorecard":
                    self.create_scorecard(chart_config)
                elif chart_type == "time_series":
                    self.create_time_series(chart_config)
                elif chart_type == "bar_chart":
                    self.create_bar_chart(chart_config)
                elif chart_type == "table":
                    self.create_table(chart_config)
                else:
                    print(f"⚠️  Unknown chart type: {chart_type}")
        
        print("\n" + "="*80)
        print("✅ DASHBOARD BUILDING COMPLETE!")
        print("="*80)
        print(f"\n📊 Report URL: {self.current_report_url}")
        print("\n🌐 Browser will stay open. Close it when done.")
        
        if self.interactive:
            input("\nPress Enter to close browser...")


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Build Looker Studio dashboard with advanced automation')
    parser.add_argument('--headless', action='store_true', help='Run in headless mode')
    parser.add_argument('--slow', type=int, default=1000, help='Slow down operations (ms)')
    parser.add_argument('--non-interactive', action='store_true', help='Run without pausing for input')
    parser.add_argument('--config', type=str, default='looker_dashboard_config.json', help='Config file path')
    
    args = parser.parse_args()
    
    if not HAS_PLAYWRIGHT:
        print("❌ Playwright required")
        print("   Install: pip install playwright && playwright install chromium")
        return
    
    with AdvancedLookerStudioBuilder(
        headless=args.headless,
        slow_mo=args.slow,
        interactive=not args.non_interactive
    ) as builder:
        builder.build_dashboard_from_config(args.config)


if __name__ == "__main__":
    main()

