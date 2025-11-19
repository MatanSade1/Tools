# GDPR Request Handler

A tool to process Slack messages from the `users-to-delete-their-personal-data` channel and create BigQuery records for user deletion requests.

## Overview

This tool scans Slack messages in a specified date range, identifies messages with a blue car emoji (but no computer emoji), extracts user deletion request information, and creates records in BigQuery. After processing a message, it adds a computer emoji reaction to mark it as processed.

## Features

- Scans Slack channel messages for a specified date range
- Filters messages with blue car emoji (but no computer emoji)
- Extracts `distinct_id`, `request_date`, and `ticket_id` from messages
- Creates BigQuery records in `yotam-395120.peerplay.personal_data_deletion_tool`
- Adds computer emoji reaction to processed messages
- Handles pagination for large message histories

## Prerequisites

1. **Slack Bot Token**: See [README-SLACK-SETUP.md](README-SLACK-SETUP.md) for setup instructions
2. **Google Cloud Authentication**: Configured for BigQuery access
3. **Python Dependencies**: Install with `pip install -r requirements.txt`

## Installation

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up Slack Bot Token (choose one):
   - **Option A (Recommended)**: Store in Secret Manager
     ```bash
     export SLACK_BOT_TOKEN_NAME="slack-bot-token"
     ```
   - **Option B**: Use environment variable
     ```bash
     export SLACK_BOT_TOKEN="xoxb-your-token-here"
     ```

3. Configure GCP project (if not already set):
   ```bash
   export GCP_PROJECT_ID="your-gcp-project-id"
   ```

## Usage

Run the tool with start and end dates:

```bash
python gdpr-handler/main.py --start-date 2025-11-17 --end-date 2025-12-31
```

### Command Line Arguments

- `--start-date` (required): Start date for message scanning (YYYY-MM-DD)
- `--end-date` (required): End date for message scanning (YYYY-MM-DD)
- `--channel` (optional): Slack channel name (defaults to `users-to-delete-their-personal-data`)

### Example

```bash
# Process messages from November 17, 2025 to December 31, 2025
python gdpr-handler/main.py --start-date 2025-11-17 --end-date 2025-12-31

# Process messages from a specific channel
python gdpr-handler/main.py --start-date 2025-11-17 --end-date 2025-12-31 --channel my-channel
```

## How It Works

1. **Fetch Messages**: Retrieves all messages from the Slack channel in the specified date range
2. **Filter Messages**: Identifies messages with:
   - Blue car emoji (🚗 or :blue_car:) as a reaction or in text
   - No computer emoji (💻 or :computer:) as a reaction or in text
3. **Parse Messages**: Extracts:
   - `distinct_id`: Game user ID (from message text)
   - `request_date`: Date from message text or message timestamp
   - `ticket_id`: Ticket identifier (from message text)
4. **Create BigQuery Records**: Inserts records with default values:
   - `mixpanel_deletion_status`: "pending"
   - `singular_deletion_status`: "pending"
   - `bigquery_deletion_status`: "not started"
   - `game_state_status`: "not started"
   - `is_request_completed`: False
5. **Mark as Processed**: Adds computer emoji reaction to the Slack message

## BigQuery Schema

The tool creates records in `yotam-395120.peerplay.personal_data_deletion_tool` with the following schema:

- `distinct_id` (STRING) - Game user ID
- `request_date` (DATE) - Date of deletion request
- `ticket_id` (STRING) - Ticket identifier
- `mixpanel_request_id` (STRING) - Mixpanel deletion request ID
- `mixpanel_deletion_status` (STRING) - "completed" or "pending"
- `singular_request_id` (STRING) - Singular deletion request ID
- `singular_deletion_status` (STRING) - "completed" or "pending"
- `bigquery_deletion_status` (STRING) - "completed" or "not started"
- `game_state_status` (STRING) - "completed" or "not started"
- `is_request_completed` (BOOLEAN) - True if all deletions completed
- `slack_message_ts` (STRING) - Slack message timestamp
- `inserted_at` (TIMESTAMP) - When record was created

## Message Parsing

The tool uses regex patterns to extract information from message text:

- **distinct_id**: Looks for patterns like "user_id: 12345", "distinct_id: 12345", or alphanumeric strings of 8+ characters
- **ticket_id**: Looks for patterns like "ticket: 12345", "ticket_id: 12345", or "#12345"
- **request_date**: Looks for date patterns (YYYY-MM-DD, MM/DD/YYYY) or uses message timestamp

If parsing fails for a message, it will be skipped with a warning.

## Error Handling

- Messages that cannot be parsed are logged with a warning and skipped
- BigQuery insertion errors will stop processing and raise an exception
- Slack API errors (e.g., adding reactions) are logged but don't stop processing

## Troubleshooting

### "Channel not found" error
- Verify the bot is invited to the channel
- Check that the channel name is correct (case-sensitive)
- See [README-SLACK-SETUP.md](README-SLACK-SETUP.md) for setup instructions

### "SLACK_BOT_TOKEN must be configured" error
- Set `SLACK_BOT_TOKEN` or `SLACK_BOT_TOKEN_NAME` environment variable
- Verify the token is valid and starts with `xoxb-`

### "Invalid date format" error
- Use YYYY-MM-DD format for dates (e.g., 2025-11-17)
- Ensure start date is before or equal to end date

### BigQuery errors
- Verify GCP authentication is configured
- Check that the service account has BigQuery permissions
- Ensure the project `yotam-395120` exists and you have access

## Security Notes

- Never commit Slack Bot Tokens to version control
- Use Secret Manager for production deployments
- The tool requires read access to Slack channels and write access to BigQuery

## Related Documentation

- [Slack App Setup Guide](README-SLACK-SETUP.md) - Detailed instructions for setting up the Slack app
- [Shared Utilities](../shared/) - Reusable Slack and BigQuery client functions

