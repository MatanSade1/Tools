# UA Cohort Dashboard - Quick Start

This script creates a Looker Studio dashboard for the `ua_cohort` table.

## Dashboard Details

- **Dashboard Name**: `ua_cohort_llm_test`
- **Table**: `yotam-395120.peerplay.ua_cohort`
- **Filters**:
  - County (dropdown)
  - Platform (dropdown)
  - Install Date (date range)
  - Media Source (dropdown)
  - Campaign Name (dropdown)
- **Chart**: ROAS D0 by Install Date (time series/line chart)

## Quick Start

### 1. Install Playwright (if not already installed)

```bash
pip install playwright
playwright install chromium
```

### 2. Run the Script

```bash
cd fraudsters-management
python3 create_ua_cohort_dashboard.py
```

The script will:
1. ✅ Open Looker Studio in a browser
2. ✅ Create a new report named "ua_cohort_llm_test"
3. ✅ Add the BigQuery data source (`yotam-395120.peerplay.ua_cohort`)
4. ✅ Add all 5 filters/controllers
5. ✅ Create the ROAS D0 time series chart

## Field Name Notes

**Important**: The script uses these field names. If your table has different column names, you may need to adjust:

- `county` - If your table uses `country`, update the script
- `platform` - Should match your table column
- `install_date` - Should match your table column
- `media_source` - If your table uses `media source` (with space), update the script
- `campaign_name` - If your table uses `campaign name` (with space), update the script
- `roas_d0` - Should match your table column

## Options

```bash
# Run in headless mode (no browser window)
python3 create_ua_cohort_dashboard.py --headless

# Slow down operations for debugging
python3 create_ua_cohort_dashboard.py --slow 2000

# Non-interactive mode (won't pause for input)
python3 create_ua_cohort_dashboard.py --non-interactive
```

## What to Expect

1. **Browser Opens**: A Chromium browser will open
2. **Login**: You may need to log in to Google/Looker Studio (first time only)
3. **Automation**: The script will automatically:
   - Create the report
   - Add the data source
   - Set up filters
   - Create the chart
4. **Manual Steps**: Some steps may require manual confirmation if selectors change

## Troubleshooting

### Playwright Not Installed
```bash
pip install playwright
playwright install chromium
```

### Field Names Don't Match
Edit `create_ua_cohort_dashboard.py` and update the field names in:
- `FILTERS` list (line ~20)
- `CHART_CONFIG` (line ~30)

### Selectors Don't Work
Looker Studio's UI may have changed. The script will:
- Try multiple selectors
- Provide manual instructions if automation fails
- Pause for you to complete steps manually

### Browser Closes Too Fast
Remove `--non-interactive` flag or add a pause at the end of the script.

## Result

After running, you'll have:
- ✅ A dashboard named "ua_cohort_llm_test"
- ✅ Connected to `yotam-395120.peerplay.ua_cohort`
- ✅ 5 filters ready to use
- ✅ ROAS D0 chart showing trends over install_date

## Next Steps

After the dashboard is created:
1. Review the chart and filters
2. Adjust styling/layout as needed
3. Share the dashboard with your team
4. Set up scheduled refreshes if needed

