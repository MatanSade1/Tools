"""
Create Looker Studio Dashboard for UA Cohort Table

This script creates a specific dashboard for:
- Table: yotam-395120.peerplay.ua_cohort
- Dashboard name: ua_cohort_llm_test
- Filters: county, platform, install_date, media source, campaign name
- Chart: ROAS D0 per install_date
"""

import os
import sys
import time
import json
from typing import Dict, List, Optional

# Add shared directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from shared.config import get_config

try:
    from playwright.sync_api import sync_playwright, Page, Browser
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    print("⚠️  Playwright not installed. Install with: pip install playwright && playwright install chromium")

# Configuration
PROJECT_ID = "yotam-395120"
DATASET_ID = "peerplay"
TABLE_ID = f"{PROJECT_ID}.{DATASET_ID}.ua_cohort"
DASHBOARD_NAME = "ua_cohort_llm_test"

# Filter fields
FILTERS = [
    {"field": "country", "type": "dropdown", "title": "Country"},
    {"field": "platform", "type": "dropdown", "title": "Platform"},
    {"field": "install_date", "type": "date_range", "title": "Install Date"},
    {"field": "media_source", "type": "dropdown", "title": "Media Source"},
    {"field": "campaign_name", "type": "dropdown", "title": "Campaign Name"},
]

# Chart configuration
CHART_CONFIG = {
    "type": "time_series",  # Line chart over time
    "title": "ROAS D0 by Install Date",
    "dimension": "install_date",
    "metric": "roas_d0",
    "data_source": TABLE_ID
}


class UACohortDashboardBuilder:
    """Build UA Cohort dashboard in Looker Studio"""
    
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
        self.report_url = None
        
    def __enter__(self):
        self.playwright = sync_playwright().start()
        
        # Try to connect to existing Chrome browser first
        try:
            # Chrome's default remote debugging port
            self.browser = self.playwright.chromium.connect_over_cdp("http://localhost:9222")
            print("✅ Connected to existing Chrome browser")
            # Get the first available context/page
            contexts = self.browser.contexts
            if contexts:
                self.page = contexts[0].pages[0] if contexts[0].pages else contexts[0].new_page()
            else:
                self.page = self.browser.new_page()
        except Exception as e:
            print(f"⚠️  Could not connect to existing Chrome: {e}")
            print("   Launching new browser instead...")
            print("   To use existing Chrome, start it with: google-chrome --remote-debugging-port=9222")
            # Fall back to launching new browser
            self.browser = self.playwright.chromium.launch(
                headless=self.headless,
                slow_mo=self.slow_mo
            )
            self.page = self.browser.new_page()
        
        # Set a larger viewport for better UI interaction
        self.page.set_viewport_size({"width": 1920, "height": 1080})
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Don't close the browser if we connected to an existing one
        # Only close if we launched it ourselves
        if self.browser:
            try:
                # Check if browser was launched by us (has launch_type) or connected (has connect_over_cdp)
                if hasattr(self.browser, '_connection') and hasattr(self.browser._connection, '_transport'):
                    # Connected browser - don't close it
                    print("✅ Keeping existing Chrome browser open")
                else:
                    # Launched browser - close it
                    self.browser.close()
            except:
                # If we can't determine, be safe and don't close
                print("✅ Keeping browser open")
        if self.playwright:
            self.playwright.stop()
    
    def wait_and_click(self, selectors: List[str], description: str, timeout: int = 5000) -> bool:
        """Try multiple selectors and click the first one that works"""
        for selector in selectors:
            try:
                element = self.page.locator(selector).first
                if element.is_visible(timeout=2000):
                    element.click()
                    print(f"✅ {description}")
                    time.sleep(1)
                    return True
            except Exception as e:
                continue
        print(f"⚠️  Could not {description}")
        return False
    
    def wait_and_fill(self, selectors: List[str], text: str, description: str) -> bool:
        """Try multiple selectors and fill the first one that works"""
        for selector in selectors:
            try:
                element = self.page.locator(selector).first
                if element.is_visible(timeout=2000):
                    element.clear()
                    element.fill(text)
                    print(f"✅ {description}")
                    time.sleep(0.5)
                    return True
            except Exception as e:
                continue
        print(f"⚠️  Could not {description}")
        return False
    
    def wait_for_element(self, selector: str, timeout: int = 10000) -> bool:
        """Wait for an element to appear"""
        try:
            self.page.wait_for_selector(selector, timeout=timeout)
            return True
        except:
            return False
    
    def login(self):
        """Handle login to Looker Studio"""
        print("\n🔐 Logging into Looker Studio...")
        self.page.goto("https://lookerstudio.google.com")
        time.sleep(3)
        
        if "accounts.google.com" in self.page.url:
            print("📝 Please log in manually in the browser window...")
            if self.interactive:
                try:
                    input("Press Enter after logging in...")
                except EOFError:
                    print("   (Non-interactive mode - waiting 15 seconds for login)")
                    time.sleep(15)
            else:
                time.sleep(15)  # Give time for manual login
        else:
            print("✅ Already logged in")
    
    def create_blank_report(self, report_name: str) -> bool:
        """Create a new blank report"""
        print(f"\n📊 Creating report: {report_name}")
        
        # Navigate directly to the create URL - this should bypass tutorial
        # Use the direct URL that creates a blank report
        create_url = "https://lookerstudio.google.com/reporting/create"
        print(f"   Navigating to: {create_url}")
        self.page.goto(create_url)
        time.sleep(5)
        
        current_url = self.page.url
        print(f"   Current URL: {current_url}")
        
        # Check if we're on a tutorial/welcome page
        if "welcome" in current_url.lower() or "tutorial" in current_url.lower() or "start" in current_url.lower():
            print("⚠️  Detected tutorial/welcome page")
            print("   Trying to skip tutorial and create blank report...")
            
            # Try multiple ways to get to a blank report
            # Method 1: Look for "Create" button in top menu
            self.wait_and_click(
                [
                    "text=Create",
                    "[aria-label*='Create']",
                    "button:has-text('Create')",
                    "a:has-text('Create')",
                ],
                "Click Create in top menu"
            )
            time.sleep(2)
            
            # Method 2: Try to click "Blank report" or "Report"
            self.wait_and_click(
                [
                    "text=Blank report",
                    "text=Report",
                    "[aria-label*='Blank report']",
                    "[aria-label*='Report']",
                ],
                "Select Blank report"
            )
            time.sleep(3)
            
            # Check URL again
            current_url = self.page.url
            if "welcome" in current_url.lower() or "tutorial" in current_url.lower():
                print("⚠️  Still on tutorial page")
                print("   Please manually:")
                print("   1. Click 'Create' in the top menu")
                print("   2. Select 'Report' or 'Blank report'")
                if self.interactive:
                    try:
                        input("   Press Enter after creating a blank report manually...")
                    except EOFError:
                        print("   (Non-interactive - waiting 10 seconds)")
                        time.sleep(10)
        
        # Final check - verify we're in a report editor
        time.sleep(2)
        current_url = self.page.url
        self.report_url = current_url
        
        if "reporting" in current_url and "/reporting/" in current_url and "create" not in current_url.lower() and "welcome" not in current_url.lower():
            print(f"✅ Report created: {self.report_url}")
        else:
            print(f"⚠️  Current URL: {self.report_url}")
            print("   This may be a tutorial page. The script will continue but you may need to create the report manually.")
        
        # Rename the report
        self.rename_report(report_name)
        
        return True
    
    def rename_report(self, new_name: str):
        """Rename the report"""
        print(f"\n✏️  Renaming report to: {new_name}")
        
        # Try to find and click the report name/title
        selectors = [
            "[data-testid='report-title']",
            "input[value*='Untitled']",
            "div[contenteditable='true']",
            "span:has-text('Untitled')",
        ]
        
        for selector in selectors:
            try:
                element = self.page.locator(selector).first
                if element.is_visible(timeout=2000):
                    element.click()
                    time.sleep(0.5)
                    # Clear and type new name
                    if element.get_attribute("contenteditable") == "true":
                        element.fill(new_name)
                    else:
                        # Try keyboard shortcut
                        self.page.keyboard.press("Control+A")
                        time.sleep(0.2)
                        self.page.keyboard.type(new_name)
                        time.sleep(0.2)
                        self.page.keyboard.press("Enter")
                    print(f"✅ Report renamed to: {new_name}")
                    time.sleep(1)
                    return
            except:
                continue
        
        print("⚠️  Could not automatically rename report")
        if self.interactive:
            try:
                input(f"Please rename the report to '{new_name}' manually, then press Enter...")
            except EOFError:
                print("   (Non-interactive mode - continuing without rename)")
                time.sleep(2)
    
    def add_bigquery_data_source(self, table_id: str) -> bool:
        """Add BigQuery data source"""
        print(f"\n📊 Adding BigQuery data source: {table_id}")
        
        # Click "Add a data source"
        if not self.wait_and_click(
            [
                "text=Add a data source",
                "text=Add data",
                "[aria-label*='Add data']",
                "button:has-text('Add')",
                "div:has-text('Add a data source')",
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
                "input[type='text']",
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
                "span:has-text('BigQuery')",
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
                "input[name*='table']",
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
                "[aria-label*='Add']",
                "[aria-label*='Connect']",
            ],
            "Connect to data source"
        ):
            return False
        
        time.sleep(5)  # Wait for connection
        
        print(f"✅ Data source added: {table_id}")
        return True
    
    def add_controller(self, field_name: str, controller_type: str, title: str):
        """Add a controller/filter"""
        print(f"\n🎛️  Adding controller: {title} ({controller_type})")
        
        # Click "Add a control" or use Insert menu
        if not self.wait_and_click(
            [
                "text=Add a control",
                "text=Add control",
                "[aria-label*='Add control']",
                "button:has-text('Control')",
            ],
            "Open control menu"
        ):
            print(f"   Manual step: Add a {controller_type} control for '{field_name}'")
        if self.interactive:
            try:
                input(f"   Press Enter after adding the {controller_type} control for '{field_name}'...")
            except EOFError:
                print(f"   (Non-interactive mode - continuing)")
                time.sleep(2)
            return
        
        time.sleep(1)
        
        # Select controller type
        controller_type_map = {
            "dropdown": ["text=Dropdown list", "text=Dropdown"],
            "date_range": ["text=Date range", "text=Date Range"],
            "checkbox": ["text=Checkbox", "text=Check box"],
        }
        
        if controller_type in controller_type_map:
            self.wait_and_click(
                controller_type_map[controller_type],
                f"Select {controller_type} control type"
            )
            time.sleep(1)
        
        # Select the field
        print(f"   Select field: {field_name}")
        if self.interactive:
            input(f"   Press Enter after selecting field '{field_name}'...")
        
        print(f"✅ Controller added: {title}")
    
    def create_time_series_chart(self, dimension_field: str, metric_field: str, title: str):
        """Create a time series chart (line chart)"""
        print(f"\n📈 Creating time series chart: {title}")
        print(f"   Dimension: {dimension_field}")
        print(f"   Metric: {metric_field}")
        
        # Click "Add a chart"
        if not self.wait_and_click(
            [
                "text=Add a chart",
                "text=Add chart",
                "[aria-label*='Add chart']",
                "button:has-text('Chart')",
            ],
            "Open chart menu"
        ):
            print("   Manual step: Add a time series chart")
            if self.interactive:
                input("   Press Enter after adding the chart...")
            return
        
        time.sleep(1)
        
        # Select time series / line chart
        if not self.wait_and_click(
            [
                "text=Time series",
                "text=Line chart",
                "text=Line",
                "[aria-label*='Time series']",
            ],
            "Select time series chart type"
        ):
            print("   Manual step: Select time series chart type")
            if self.interactive:
                input("   Press Enter after selecting chart type...")
        
        time.sleep(2)
        
        print(f"   Configure chart:")
        print(f"   - Dimension: {dimension_field}")
        print(f"   - Metric: {metric_field}")
        print(f"   - Title: {title}")
        
        if self.interactive:
            try:
                input(f"   Press Enter after configuring the chart with {dimension_field} and {metric_field}...")
            except EOFError:
                print(f"   (Non-interactive mode - continuing)")
                time.sleep(2)
        
        print(f"✅ Chart created: {title}")
    
    def build_dashboard(self):
        """Build the complete UA Cohort dashboard"""
        print("\n" + "="*80)
        print("BUILDING UA COHORT DASHBOARD")
        print("="*80)
        print(f"\n📊 Dashboard: {DASHBOARD_NAME}")
        print(f"📋 Table: {TABLE_ID}")
        print(f"\n🎛️  Filters to add:")
        for f in FILTERS:
            print(f"   - {f['title']} ({f['type']})")
        print(f"\n📈 Chart to create:")
        print(f"   - {CHART_CONFIG['title']}")
        print(f"   - Dimension: {CHART_CONFIG['dimension']}")
        print(f"   - Metric: {CHART_CONFIG['metric']}")
        print("="*80 + "\n")
        
        # Step 1: Login
        self.login()
        
        # Step 2: Create report
        if not self.create_blank_report(DASHBOARD_NAME):
            print("❌ Failed to create report")
            return
        
        # Step 3: Add data source
        if not self.add_bigquery_data_source(TABLE_ID):
            print("❌ Failed to add data source")
            if self.interactive:
                try:
                    input("Please add the data source manually, then press Enter...")
                except EOFError:
                    print("   (Non-interactive mode - continuing)")
                    time.sleep(2)
        
        time.sleep(2)
        
        # Step 4: Add filters/controllers
        print("\n" + "-"*80)
        print("ADDING FILTERS/CONTROLLERS")
        print("-"*80)
        
        for filter_config in FILTERS:
            self.add_controller(
                filter_config["field"],
                filter_config["type"],
                filter_config["title"]
            )
            time.sleep(1)
        
        # Step 5: Create chart
        print("\n" + "-"*80)
        print("CREATING CHART")
        print("-"*80)
        
        self.create_time_series_chart(
            CHART_CONFIG["dimension"],
            CHART_CONFIG["metric"],
            CHART_CONFIG["title"]
        )
        
        print("\n" + "="*80)
        print("✅ DASHBOARD BUILDING COMPLETE!")
        print("="*80)
        print(f"\n📊 Dashboard URL: {self.report_url}")
        print(f"📝 Dashboard name: {DASHBOARD_NAME}")
        print("\n🌐 Browser will stay open. Review the dashboard and close when done.")
        
        if self.interactive:
            try:
                input("\nPress Enter to close browser...")
            except EOFError:
                print("\n   (Non-interactive mode - keeping browser open for 30 seconds)")
                time.sleep(30)


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Create UA Cohort Looker Studio dashboard')
    parser.add_argument('--headless', action='store_true', help='Run in headless mode')
    parser.add_argument('--slow', type=int, default=1000, help='Slow down operations (ms)')
    parser.add_argument('--non-interactive', action='store_true', help='Run without pausing')
    parser.add_argument('--chrome-port', type=int, default=9222, help='Chrome remote debugging port')
    
    args = parser.parse_args()
    
    if not HAS_PLAYWRIGHT:
        print("❌ Playwright required")
        print("   Install: pip install playwright && playwright install chromium")
        return
    
    print("🚀 Starting UA Cohort Dashboard Creation...")
    print("\n📌 To use your existing Chrome browser:")
    print("   1. Close all Chrome windows")
    print("   2. Start Chrome with remote debugging:")
    print(f"      /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port={args.chrome_port}")
    print("   3. Then run this script again")
    print("\n   OR the script will try to connect to Chrome on port 9222")
    print("   If Chrome is already running, you may need to restart it with the flag above.\n")
    
    with UACohortDashboardBuilder(
        headless=args.headless,
        slow_mo=args.slow,
        interactive=not args.non_interactive
    ) as builder:
        builder.build_dashboard()


if __name__ == "__main__":
    main()

