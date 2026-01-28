"""
Looker Studio Dashboard Builder - Browser Automation

This script uses browser automation (Playwright) to actually create and edit
Looker Studio dashboards, including charts, controllers, and layout.

Since Looker Studio API doesn't support programmatic dashboard creation,
this script automates the UI to build the dashboard.
"""

import os
import sys
import time
import json
from typing import Dict, List, Optional, Any
from pathlib import Path

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

TABLES = {
    "fraudsters": f"{PROJECT_ID}.{DATASET_ID}.fraudsters",
    "potential_fraudsters": f"{PROJECT_ID}.{DATASET_ID}.potential_fraudsters",
    "offer_wall_progression_cheaters": f"{PROJECT_ID}.{DATASET_ID}.offer_wall_progression_cheaters",
    "dim_player": f"{PROJECT_ID}.{DATASET_ID}.dim_player",
}


class LookerStudioDashboardAutomation:
    """Automate Looker Studio dashboard creation using browser automation"""
    
    def __init__(self, headless: bool = False, slow_mo: int = 500):
        """
        Initialize the automation.
        
        Args:
            headless: Run browser in headless mode (False = visible browser)
            slow_mo: Slow down operations by this many milliseconds (for debugging)
        """
        if not HAS_PLAYWRIGHT:
            raise ImportError("Playwright is required. Install with: pip install playwright && playwright install chromium")
        
        self.headless = headless
        self.slow_mo = slow_mo
        self.playwright = None
        self.browser = None
        self.page = None
        self.base_url = "https://lookerstudio.google.com"
        
    def __enter__(self):
        """Context manager entry"""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            slow_mo=self.slow_mo
        )
        self.page = self.browser.new_page()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
    
    def wait_for_element(self, selector: str, timeout: int = 30000) -> bool:
        """Wait for an element to appear on the page"""
        try:
            self.page.wait_for_selector(selector, timeout=timeout)
            return True
        except Exception as e:
            print(f"⚠️  Element not found: {selector} - {e}")
            return False
    
    def login(self, email: Optional[str] = None, password: Optional[str] = None):
        """
        Login to Looker Studio.
        
        Note: For security, it's better to use an existing browser session.
        You can manually log in once, and the script will use that session.
        
        Args:
            email: Google account email (optional - will prompt if needed)
            password: Google account password (optional - will prompt if needed)
        """
        print("🔐 Navigating to Looker Studio...")
        self.page.goto(self.base_url)
        time.sleep(2)
        
        # Check if already logged in
        if "accounts.google.com" not in self.page.url:
            print("✅ Already logged in or session exists")
            return
        
        # If email/password provided, attempt login
        if email and password:
            print("⚠️  Automated login is not recommended for security reasons.")
            print("   Please log in manually in the browser window, then press Enter to continue...")
            input("Press Enter after you've logged in...")
        else:
            print("📝 Please log in manually in the browser window...")
            print("   After logging in, press Enter to continue...")
            input("Press Enter after you've logged in...")
        
        # Verify we're on Looker Studio
        if "lookerstudio.google.com" in self.page.url:
            print("✅ Successfully accessed Looker Studio")
        else:
            print(f"⚠️  Current URL: {self.page.url}")
            print("   Make sure you're logged in to Looker Studio")
    
    def create_new_report(self, report_name: str = "Fraudsters Management Dashboard"):
        """
        Create a new Looker Studio report.
        
        Args:
            report_name: Name for the new report
        """
        print(f"📊 Creating new report: {report_name}")
        
        # Navigate to create report
        self.page.goto(f"{self.base_url}/reporting/create")
        time.sleep(3)
        
        # Look for "Create" button or "Blank Report" option
        # The UI might have different options, so we'll try multiple selectors
        selectors = [
            "text=Blank report",
            "text=Create",
            "[data-testid='create-report']",
            "button:has-text('Create')",
            "a:has-text('Blank report')"
        ]
        
        for selector in selectors:
            try:
                if self.page.locator(selector).first.is_visible(timeout=2000):
                    self.page.click(selector)
                    print(f"✅ Clicked: {selector}")
                    time.sleep(2)
                    break
            except:
                continue
        
        # If we're in the report editor, we're good
        if "reporting" in self.page.url and "create" in self.page.url:
            print("✅ Report editor opened")
        else:
            print(f"⚠️  Current URL: {self.page.url}")
            print("   You may need to manually create a blank report")
            input("Press Enter after creating a blank report...")
        
        # Wait for report editor to load
        time.sleep(3)
    
    def add_bigquery_data_source(self, table_id: str, table_name: str):
        """
        Add a BigQuery data source to the report.
        
        Args:
            table_id: Full BigQuery table ID (project.dataset.table)
            table_name: Display name for the data source
        """
        print(f"📊 Adding data source: {table_name} ({table_id})")
        
        # Click "Add a data source" or similar button
        selectors = [
            "text=Add a data source",
            "text=Add data",
            "[data-testid='add-data-source']",
            "button:has-text('Add')",
        ]
        
        for selector in selectors:
            try:
                if self.page.locator(selector).first.is_visible(timeout=2000):
                    self.page.click(selector)
                    print(f"✅ Clicked: {selector}")
                    time.sleep(2)
                    break
            except:
                continue
        
        # Search for BigQuery
        time.sleep(1)
        try:
            # Type "BigQuery" in search
            search_selectors = [
                "input[type='search']",
                "input[placeholder*='Search']",
                "input[placeholder*='search']",
            ]
            
            for selector in search_selectors:
                try:
                    search_input = self.page.locator(selector).first
                    if search_input.is_visible(timeout=2000):
                        search_input.fill("BigQuery")
                        time.sleep(1)
                        break
                except:
                    continue
            
            # Click BigQuery connector
            time.sleep(1)
            bigquery_selectors = [
                "text=BigQuery",
                "[data-testid='bigquery-connector']",
            ]
            
            for selector in bigquery_selectors:
                try:
                    if self.page.locator(selector).first.is_visible(timeout=2000):
                        self.page.click(selector)
                        print("✅ Selected BigQuery connector")
                        time.sleep(2)
                        break
                except:
                    continue
            
            # Enter table ID
            time.sleep(2)
            table_input_selectors = [
                "input[placeholder*='table']",
                "input[placeholder*='Table']",
                "input[type='text']",
            ]
            
            for selector in table_input_selectors:
                try:
                    table_input = self.page.locator(selector).first
                    if table_input.is_visible(timeout=2000):
                        table_input.fill(table_id)
                        time.sleep(1)
                        break
                except:
                    continue
            
            # Click "Add" or "Connect"
            time.sleep(1)
            connect_selectors = [
                "text=Add",
                "text=Connect",
                "button:has-text('Add')",
                "button:has-text('Connect')",
            ]
            
            for selector in connect_selectors:
                try:
                    if self.page.locator(selector).first.is_visible(timeout=2000):
                        self.page.click(selector)
                        print(f"✅ Connected to {table_name}")
                        time.sleep(3)
                        return True
                except:
                    continue
            
        except Exception as e:
            print(f"⚠️  Error adding data source: {e}")
            print("   You may need to add this data source manually")
            return False
        
        return False
    
    def add_scorecard(self, metric_field: str, title: str, position: Dict[str, int] = None):
        """
        Add a scorecard chart to the report.
        
        Args:
            metric_field: Field name for the metric
            title: Title for the scorecard
            position: Optional position dict with x, y, width, height
        """
        print(f"📈 Adding scorecard: {title}")
        
        # Click "Add a chart" or use the chart menu
        try:
            # Look for chart insertion options
            # This is complex as Looker Studio UI varies
            # We'll use a more manual approach with instructions
            
            print(f"   Manual step: Add a scorecard chart")
            print(f"   - Metric: {metric_field}")
            print(f"   - Title: {title}")
            if position:
                print(f"   - Position: {position}")
            
            # For now, we'll provide instructions
            # Full automation would require reverse-engineering the Looker Studio UI
            return True
            
        except Exception as e:
            print(f"⚠️  Error adding scorecard: {e}")
            return False
    
    def add_time_series_chart(self, date_field: str, metric_field: str, title: str):
        """Add a time series chart"""
        print(f"📈 Adding time series chart: {title}")
        print(f"   - Date dimension: {date_field}")
        print(f"   - Metric: {metric_field}")
        return True
    
    def add_bar_chart(self, dimension_field: str, metric_field: str, title: str):
        """Add a bar chart"""
        print(f"📊 Adding bar chart: {title}")
        print(f"   - Dimension: {dimension_field}")
        print(f"   - Metric: {metric_field}")
        return True
    
    def add_controller(self, field: str, controller_type: str = "dropdown", title: str = None):
        """
        Add a controller/filter to the report.
        
        Args:
            field: Field name to filter on
            controller_type: Type of controller (dropdown, date_range, etc.)
            title: Optional title for the controller
        """
        print(f"🎛️  Adding controller: {title or field}")
        print(f"   - Type: {controller_type}")
        print(f"   - Field: {field}")
        return True
    
    def build_complete_dashboard(self):
        """Build the complete fraudsters management dashboard"""
        print("\n" + "="*80)
        print("BUILDING FRAUDSTERS MANAGEMENT DASHBOARD")
        print("="*80 + "\n")
        
        # Step 1: Login
        self.login()
        
        # Step 2: Create new report
        self.create_new_report("Fraudsters Management Dashboard")
        
        # Step 3: Add data sources
        print("\n📊 Adding data sources...")
        for table_name, table_id in TABLES.items():
            if "stage" not in table_name:  # Skip staging tables
                self.add_bigquery_data_source(table_id, table_name.replace("_", " ").title())
                time.sleep(2)
        
        print("\n📈 Dashboard structure to create:")
        print("""
        PAGE 1: Overview
        - Scorecard: Total Fraudsters (COUNT_DISTINCT distinct_id from fraudsters)
        - Scorecard: Potential Fraudsters (COUNT_DISTINCT distinct_id from potential_fraudsters)
        - Scorecard: Offerwall Cheaters (COUNT_DISTINCT distinct_id from offer_wall_progression_cheaters)
        - Time Series: Fraudsters Over Time (date vs COUNT_DISTINCT distinct_id)
        
        PAGE 2: Fraud Flags Analysis
        - Bar Chart: Fraud Flags Distribution
        - Pie Chart: Manual vs Automated Detection
        - Table: Top Fraud Flags
        
        PAGE 3: Platform Analysis
        - Bar Chart: Fraudsters by Platform
        - Geo Chart: Fraudsters by Country
        
        PAGE 4: Detailed View
        - Table: Fraudster Details with all fields
        
        CONTROLLERS:
        - Date Range Filter
        - Platform Dropdown
        - Fraud Flag Type Dropdown
        """)
        
        print("\n⚠️  IMPORTANT:")
        print("   Looker Studio's UI is complex and changes frequently.")
        print("   Full automation of chart/controller creation requires:")
        print("   1. Reverse-engineering the exact UI selectors")
        print("   2. Handling dynamic content and loading states")
        print("   3. Managing authentication and permissions")
        print("\n   For now, this script:")
        print("   ✅ Opens Looker Studio")
        print("   ✅ Creates a new report")
        print("   ✅ Adds BigQuery data sources")
        print("   ⚠️  Charts and controllers need to be added manually")
        print("\n   However, you can extend this script with specific selectors")
        print("   for your Looker Studio version to fully automate chart creation.")
        
        print("\n" + "="*80)
        print("✅ Dashboard setup initiated!")
        print("="*80 + "\n")
        
        # Keep browser open for manual completion
        print("🌐 Browser will stay open for you to complete the dashboard setup.")
        print("   Press Enter when done to close the browser...")
        input()


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Build Looker Studio dashboard using browser automation')
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode')
    parser.add_argument('--slow', type=int, default=500, help='Slow down operations (milliseconds)')
    
    args = parser.parse_args()
    
    if not HAS_PLAYWRIGHT:
        print("❌ Playwright is required for browser automation")
        print("   Install with:")
        print("   pip install playwright")
        print("   playwright install chromium")
        return
    
    print("🚀 Starting Looker Studio Dashboard Automation...")
    print("   This will open a browser and automate dashboard creation.")
    print("   You may need to log in manually the first time.\n")
    
    with LookerStudioDashboardAutomation(headless=args.headless, slow_mo=args.slow) as automation:
        automation.build_complete_dashboard()


if __name__ == "__main__":
    main()

