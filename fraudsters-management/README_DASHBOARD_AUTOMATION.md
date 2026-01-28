# Looker Studio Dashboard Automation

This directory contains scripts to **actually create and edit Looker Studio dashboards** using browser automation, since the Looker Studio API doesn't support programmatic dashboard creation.

## ⚠️ Important Note

**Looker Studio does NOT have an API for creating dashboards, charts, or controllers.**

The scripts in this directory use **browser automation (Playwright)** to interact with the Looker Studio UI and create dashboards programmatically.

## Scripts

### 1. `create_looker_dashboard.py`
Generates dashboard configuration and SQL queries. This is the foundation.

**Usage:**
```bash
python3 create_looker_dashboard.py --generate-url
```

**Output:**
- `looker_dashboard_config.json` - Complete dashboard configuration
- SQL queries for all charts
- Setup instructions

### 2. `build_looker_dashboard.py`
Basic browser automation to create dashboards.

**Usage:**
```bash
# Install Playwright first
pip install playwright
playwright install chromium

# Run the automation
python3 build_looker_dashboard.py
```

**What it does:**
- ✅ Opens Looker Studio
- ✅ Creates a new report
- ✅ Adds BigQuery data sources
- ⚠️  Charts and controllers require manual creation (with instructions)

### 3. `build_looker_dashboard_advanced.py`
Advanced automation with configuration-driven approach.

**Usage:**
```bash
python3 build_looker_dashboard_advanced.py --config looker_dashboard_config.json
```

**What it does:**
- ✅ All of the basic automation
- ✅ Reads from configuration file
- ✅ Provides step-by-step guidance for chart creation
- ✅ Can be extended with specific UI selectors

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browser
playwright install chromium
```

## How It Works

1. **Browser Automation**: Uses Playwright to control a Chromium browser
2. **UI Interaction**: Clicks buttons, fills forms, navigates pages
3. **Configuration-Driven**: Reads dashboard structure from JSON config
4. **Hybrid Approach**: Automates what's possible, guides for the rest

## Limitations

### What CAN be automated:
- ✅ Opening Looker Studio
- ✅ Creating new reports
- ✅ Adding BigQuery data sources
- ✅ Basic navigation

### What's DIFFICULT to automate:
- ⚠️  Creating charts (UI is complex and dynamic)
- ⚠️  Adding controllers/filters (many nested steps)
- ⚠️  Configuring chart properties (dynamic selectors)
- ⚠️  Layout management (drag-and-drop)

### Why it's difficult:
1. **Dynamic UI**: Looker Studio's UI changes frequently
2. **Complex Selectors**: Elements don't have stable IDs/classes
3. **Loading States**: Many async operations
4. **Authentication**: Google login is complex

## Solution: Hybrid Approach

The scripts use a **hybrid approach**:

1. **Automate the easy parts**: Data sources, report creation
2. **Guide the hard parts**: Step-by-step instructions for charts
3. **Extensible**: You can add specific selectors for your Looker Studio version

## Extending the Automation

To fully automate chart creation, you need to:

1. **Inspect the UI**: Use browser dev tools to find selectors
2. **Add selectors**: Update the scripts with specific selectors
3. **Handle loading**: Wait for elements to appear
4. **Test thoroughly**: UI changes can break automation

### Example: Adding a Scorecard

```python
def create_scorecard_automated(self, metric_field: str, title: str):
    # Step 1: Click "Add a chart"
    self.page.click("button[aria-label='Add a chart']")
    time.sleep(1)
    
    # Step 2: Select "Scorecard"
    self.page.click("text=Scorecard")
    time.sleep(1)
    
    # Step 3: Select metric field
    self.page.click(f"text={metric_field}")
    time.sleep(1)
    
    # Step 4: Set title
    title_input = self.page.locator("input[placeholder='Chart title']")
    title_input.fill(title)
    
    # Step 5: Apply
    self.page.click("button:has-text('Apply')")
    time.sleep(2)
```

**Note**: These selectors are examples and may not work with your Looker Studio version. You'll need to inspect the actual UI.

## Recommended Workflow

1. **Generate Configuration**:
   ```bash
   python3 create_looker_dashboard.py
   ```

2. **Run Basic Automation**:
   ```bash
   python3 build_looker_dashboard.py
   ```
   This will:
   - Open Looker Studio
   - Create a report
   - Add data sources
   - Keep browser open for you to add charts

3. **Add Charts Manually** (for now):
   - Use the instructions provided
   - Or extend the scripts with specific selectors

4. **Extend Automation** (optional):
   - Inspect Looker Studio UI
   - Add specific selectors to the scripts
   - Test and refine

## Troubleshooting

### Browser doesn't open
- Check Playwright installation: `playwright install chromium`
- Try running with `--headless false` to see the browser

### Selectors don't work
- Looker Studio UI may have changed
- Inspect the page and update selectors
- Use browser dev tools to find stable selectors

### Authentication issues
- Log in manually the first time
- The script will use your existing session
- For headless mode, you may need to save cookies

### Charts not creating
- This is expected - chart creation is complex
- Use the manual instructions provided
- Or extend the scripts with specific selectors

## Future Improvements

Potential enhancements:
1. **Screenshot-based automation**: Use image recognition
2. **API reverse-engineering**: Find internal APIs
3. **Template-based**: Create templates and duplicate them
4. **Community contributions**: Share working selectors

## Alternative Solutions

If full automation isn't feasible:

1. **Templates**: Create dashboard templates manually, duplicate programmatically
2. **Google Apps Script**: Automate data preparation
3. **Looker (not Looker Studio)**: Has full API support
4. **Custom Connectors**: Build connectors for your data sources

## Support

For issues or questions:
1. Check the script output for specific errors
2. Inspect the browser window (if not headless)
3. Update selectors based on current Looker Studio UI
4. Extend the scripts with your specific needs

## Example: Complete Dashboard Creation

```bash
# Step 1: Generate configuration
python3 create_looker_dashboard.py --generate-url

# Step 2: Run automation (will open browser)
python3 build_looker_dashboard_advanced.py

# Step 3: Follow on-screen instructions to complete charts
# (or extend the script to automate chart creation)
```

The scripts will handle:
- ✅ Login
- ✅ Report creation
- ✅ Data source connections
- 📝 Chart creation (with guidance)

You'll need to either:
- Follow the manual instructions, OR
- Extend the scripts with specific UI selectors

