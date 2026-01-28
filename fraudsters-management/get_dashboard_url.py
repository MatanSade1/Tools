"""
Quick script to create a blank Looker Studio report and get its URL
"""
import time
from playwright.sync_api import sync_playwright

def create_report_and_get_url():
    """Create a blank report and return its URL"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=1000)
        page = browser.new_page()
        
        print("🔐 Opening Looker Studio...")
        page.goto("https://lookerstudio.google.com")
        time.sleep(3)
        
        # If on login page, wait
        if "accounts.google.com" in page.url:
            print("📝 Please log in...")
            input("Press Enter after logging in...")
        
        # Navigate to create report
        print("📊 Creating blank report...")
        page.goto("https://lookerstudio.google.com/reporting/create")
        time.sleep(5)
        
        # Check if we're on tutorial - if so, try to skip
        if "welcome" in page.url.lower() or "tutorial" in page.url.lower():
            print("⚠️  Tutorial page detected. Please:")
            print("   1. Click 'Create' in the top menu")
            print("   2. Select 'Report' or 'Blank report'")
            input("   Press Enter after creating the report...")
        
        # Wait a bit and get the URL
        time.sleep(3)
        current_url = page.url
        
        print(f"\n✅ Dashboard URL:")
        print(f"   {current_url}\n")
        
        # Keep browser open
        print("🌐 Browser will stay open. Copy the URL above.")
        input("Press Enter to close browser...")
        
        browser.close()
        
        return current_url

if __name__ == "__main__":
    url = create_report_and_get_url()
    print(f"\n📋 Final URL: {url}")



