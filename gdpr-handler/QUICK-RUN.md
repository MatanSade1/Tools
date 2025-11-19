# Quick Run Guide

## First Time Setup (One-time)

Run the interactive setup script:
```bash
cd /Users/matansade/Tools
./gdpr-handler/setup-and-run.sh
```

This will:
1. Install all dependencies
2. Set up environment variables
3. Let you choose a date range
4. Run the handler

## Quick Run (After Setup)

For quick runs, use the simple script:

**Default (last 7 days):**
```bash
cd /Users/matansade/Tools
./gdpr-handler/run.sh
```

**Custom date range:**
```bash
cd /Users/matansade/Tools
./gdpr-handler/run.sh 2025-11-17 2025-12-31
```

**Show help:**
```bash
./gdpr-handler/run.sh --help
```

The script accepts two arguments:
- First argument: Start date (YYYY-MM-DD)
- Second argument: End date (YYYY-MM-DD)

Example: Process messages from November 17 to December 31, 2025:
```bash
./gdpr-handler/run.sh 2025-11-17 2025-12-31
```

## Manual Run

If you prefer to run manually:
```bash
cd /Users/matansade/Tools
export SLACK_BOT_TOKEN='YOUR_TOKEN_HERE'  # Get from Slack app settings
export GCP_PROJECT_ID='yotam-395120'
export PYTHONPATH=/Users/matansade/Tools:$PYTHONPATH
python3 gdpr-handler/main.py --start-date 2025-11-17 --end-date 2025-12-31
```

**Note**: The run scripts have a default token configured. For security, you can override it with an environment variable.

## What It Does

1. Fetches messages from `users-to-delete-their-personal-data` channel
2. Finds messages with blue car emoji (but no computer emoji)
3. Extracts user info (distinct_id, request_date, ticket_id)
4. Creates BigQuery records
5. Adds computer emoji to mark messages as processed

## Tips

- Run weekly to process new requests
- Messages with computer emoji are skipped (already processed)
- Check BigQuery table: `yotam-395120.peerplay.personal_data_deletion_tool`

