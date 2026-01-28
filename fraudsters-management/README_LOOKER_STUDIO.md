# Looker Studio Dashboard Builder

This tool generates Looker Studio dashboard configurations for the Fraudsters Management system.

## ⚠️ Important Limitations

**Looker Studio does NOT have a full API for programmatic dashboard creation.**

The Looker Studio API has severe limitations:
- ❌ Cannot create dashboards programmatically
- ❌ Cannot create charts or visualizations via API
- ✅ Can only manage assets (search, permissions) - requires Google Workspace
- ✅ Linking API can create dynamic URLs to pre-configured reports

## What This Tool Does

This script generates:
1. **Dashboard Configuration JSON** - Complete structure for your dashboard
2. **SQL Queries** - Pre-written queries for all charts
3. **Data Source Configurations** - BigQuery table connections
4. **Linking API URLs** - Dynamic dashboard URLs with filters
5. **Setup Instructions** - Step-by-step guide

## Quick Start

```bash
# Generate dashboard configuration
python3 create_looker_dashboard.py

# Generate with example Linking API URL
python3 create_looker_dashboard.py --generate-url

# Use Looker Studio API (requires OAuth setup)
python3 create_looker_dashboard.py --use-api
```

## Generated Files

- `looker_dashboard_config.json` - Complete dashboard configuration with SQL queries
- `setup_looker_dashboard.sh` - Automated setup script

## Manual Dashboard Creation

Since Looker Studio doesn't support full programmatic creation, you need to:

1. **Open Looker Studio**: https://lookerstudio.google.com
2. **Create Data Sources**: Add BigQuery tables from the config file
3. **Create Report**: Build a new report and add the data sources
4. **Add Charts**: Use the SQL queries from the config to create custom charts
5. **Organize Pages**: Follow the page structure in the config

## Dashboard Structure

The generated dashboard includes 4 pages:

### 1. Overview
- Total Fraudsters (scorecard)
- Potential Fraudsters (scorecard)
- Offerwall Cheaters (scorecard)
- Fraudsters Over Time (time series)

### 2. Fraud Flags Analysis
- Fraud Flags Distribution (bar chart)
- Manual vs Automated Detection (pie chart)
- Top Fraud Flags (table)

### 3. Platform Analysis
- Fraudsters by Platform (bar chart)
- Fraudsters by Country (geo chart)

### 4. Detailed View
- Fraudster Details (table with all fields)

## Using the Linking API

The Linking API allows you to create dynamic URLs to your dashboard:

```python
from create_looker_dashboard import LookerStudioDashboardBuilder

builder = LookerStudioDashboardBuilder()

# Generate URL with filters
url = builder.generate_linking_api_url(
    report_id="your-report-id",
    filters={"platform": "Apple", "date": "2025-01-01"}
)
```

## Data Sources

The dashboard connects to these BigQuery tables:

- `yotam-395120.peerplay.potential_fraudsters`
- `yotam-395120.peerplay.fraudsters`
- `yotam-395120.peerplay.offer_wall_progression_cheaters`
- `yotam-395120.peerplay.dim_player`

## SQL Queries

All SQL queries are included in `looker_dashboard_config.json` under the `sql_queries` key. These can be used to create custom SQL data sources in Looker Studio.

## Alternative Solutions

If you need more automation, consider:

1. **Google Apps Script** - Automate data preparation in Google Sheets
2. **Looker API** - If you have Looker (not Looker Studio), it has full API support
3. **Custom Connectors** - Build Looker Studio connectors for your data sources
4. **Templates** - Create dashboard templates and duplicate them programmatically

## Requirements

```bash
pip install google-cloud-bigquery google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

## Troubleshooting

### API Not Available
If you see "Looker Studio API not available", it means:
- You don't have Google Workspace/Cloud Identity
- OAuth credentials are not set up
- Domain-wide delegation is not configured

This is normal - the tool works without API access by generating configurations.

### BigQuery Access
Make sure your Google account has access to the BigQuery tables listed above.

## Next Steps

1. Review `looker_dashboard_config.json`
2. Follow the setup instructions printed by the script
3. Manually create the dashboard in Looker Studio UI
4. Use the SQL queries to build custom charts
5. Share the dashboard URL with your team

## Support

For Looker Studio API documentation:
- https://developers.google.com/looker-studio/integrate/api
- https://developers.google.com/looker-studio/integrate/linking-api

