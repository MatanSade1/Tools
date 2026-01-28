# GDPR Request Handler

A comprehensive tool to process Slack messages from the `users-to-delete-their-personal-data` channel, create GDPR deletion requests across multiple platforms (Mixpanel, Singular, AppLovin), and track their completion status.

## Overview

This tool automates the entire GDPR deletion workflow:
1. **Scans Slack messages** in a specified date range
2. **Validates messages** using a three-word check ("delete", "user", "ticket")
3. **Creates deletion requests** in Mixpanel, Singular, and AppLovin Max mediation
4. **Tracks completion status** across all platforms
5. **Updates BigQuery records** with progress
6. **Manages emoji reactions** in Slack to visualize status

## Features

- ✅ **Message Validation**: Filters messages containing "delete", "user", and "ticket" (case-insensitive)
- ✅ **Two-Phase Processing**: 
  - Phase 1: New request processing (creates deletion requests)
  - Phase 2: Status check processing (monitors completion)
- ✅ **Multi-Platform Integration**:
  - Mixpanel GDPR API
  - Singular OpenDSR API
  - AppLovin Max Partner Deletion API
- ✅ **14-Day Inactivity Check**: Only processes users inactive for 14+ days
- ✅ **Status Tracking**: Automatic status checks with emoji progression
- ✅ **Performance Optimized**: Batch BigQuery queries for efficiency
- ✅ **Smart Skipping**: Skips API calls for already completed requests

## Prerequisites

1. **Slack Bot Token**: See [README-SLACK-SETUP.md](README-SLACK-SETUP.md) for setup instructions
2. **Google Cloud Authentication**: Configured for BigQuery access
3. **API Credentials**:
   - Mixpanel GDPR Token (OAuth token or Service Account)
   - Singular API Key
   - AppLovin GDPR API Key
4. **Python Dependencies**: Install with `pip install -r requirements.txt`

## Installation

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up API credentials (see [API-SETUP.md](API-SETUP.md) for details):
   - **Mixpanel**: Store token in Secret Manager or environment variable
   - **Singular**: Store API key in Secret Manager or environment variable
   - **AppLovin**: Store API key in Secret Manager or environment variable

3. Set up Slack Bot Token (choose one):
   - **Option A (Recommended)**: Store in Secret Manager
     ```bash
     export SLACK_BOT_TOKEN_NAME="slack-bot-token"
     ```
   - **Option B**: Use environment variable
     ```bash
     export SLACK_BOT_TOKEN="xoxb-your-token-here"
     ```

4. Configure GCP project (if not already set):
   ```bash
   export GCP_PROJECT_ID="yotam-395120"
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

### Message Validation

Messages must contain all three words (case-insensitive):
- **"delete"** - Indicates deletion request
- **"user"** - Matches "user", "userid", "user_id", etc.
- **"ticket"** - Ticket identifier

**Valid Examples:**
- "Please delete this user 6913266e014613e8a254be16. ticket 4412"
- "pls delete this user userId: 691872cb4d709d02d9143763 ticket 4435"
- "Hey @Matan Sade - another user asked to delete here account. Ticket number 4516 this is the user ID: 68ee7fd46d00d7426c931723."

**Invalid Examples:**
- "Delete user" (missing "ticket")
- "Delete ticket 123" (missing "user")
- "User wants to remove account" (missing "delete" and "ticket")

### Two-Phase Processing

#### Phase 1: New Request Processing

Messages **without** computer (💻) or white check mark (✅) emoji are processed as new requests:

1. **Parse Message**: Extracts `distinct_id`, `ticket_id`, and `request_date`
2. **Batch Fetch Data**: Efficiently queries BigQuery for:
   - Player activity dates (14-day check)
   - Advertising IDs (IDFA/GAID) for AppLovin
   - Existing records (to skip already completed requests)
3. **14-Day Inactivity Check**: Only processes users inactive for 14+ days
4. **Create Deletion Requests**:
   - **Mixpanel**: Creates GDPR deletion request via API
   - **Singular**: Creates OpenDSR erasure request via API
   - **AppLovin**: Creates batch deletion request for advertising IDs
5. **Create BigQuery Record**: Inserts record with initial statuses
6. **Add Computer Emoji**: Marks message as "in progress" (💻)

#### Phase 2: Status Check Processing

Messages **with** computer (💻) or white check mark (✅) emoji are checked for completion:

1. **Fetch Record**: Gets current status from BigQuery
2. **Skip if Completed**: If `is_request_completed=true`, skips further processing
3. **Check Status** (only if not already "completed"):
   - **Mixpanel**: Checks deletion status via API
   - **Singular**: Checks deletion status via API
   - **AppLovin**: Status is set at creation (synchronous)
4. **Update BigQuery**: Updates status fields
5. **Update Emojis**:
   - **Red Car (🚗)**: Added when Mixpanel, Singular, and AppLovin are all "completed"
   - **White Check Mark (✅)**: Added when all 5 steps are completed:
     - Mixpanel deletion
     - Singular deletion
     - AppLovin deletion
     - BigQuery deletion
     - GameState deletion
   - Removes red car and computer emojis when fully completed

### Performance Optimizations

- **Batch Queries**: All BigQuery queries are batched upfront (3 queries total regardless of message count)
- **Smart Skipping**: Skips API calls if status is already "completed" in BigQuery
- **Cached Data**: Reuses fetched data across message processing

### Status Flow

```
New Message
    ↓
[💻 Computer] → Processing started
    ↓
Mixpanel: pending → completed
Singular: pending → completed
AppLovin: pending → completed
    ↓
[🚗 Red Car] → All automatic deletions done
    ↓
BigQuery: not started → completed
GameState: not started → completed
    ↓
[✅ White Check Mark] → All deletions completed
```

## BigQuery Schema

The tool creates/updates records in `yotam-395120.peerplay.personal_data_deletion_tool` with the following schema:

### Core Fields

- `distinct_id` (STRING) - Game user ID
- `request_date` (DATE) - Date of deletion request
- `ticket_id` (STRING) - Ticket identifier
- `slack_message_ts` (STRING) - Slack message timestamp
- `inserted_at` (TIMESTAMP) - When record was created

### Deletion Status Fields

- `mixpanel_request_id` (STRING) - Mixpanel deletion request ID
- `mixpanel_deletion_status` (STRING) - "completed", "pending", or "not started"
- `singular_request_id` (STRING) - Singular deletion request ID
- `singular_deletion_status` (STRING) - "completed", "pending", or "not started"
- `max_mediation_deletion_status` (STRING) - "completed", "pending", or "not started"
- `bigquery_deletion_status` (STRING) - "completed" or "not started"
- `game_state_status` (STRING) - "completed" or "not started"
- `is_request_completed` (BOOLEAN) - True if all deletions completed

### Activity Fields

- `install_date` (DATE) - User install date
- `last_activity_date` (DATE) - Last activity date (used for 14-day check)

## API Integrations

### Mixpanel GDPR API

- **Endpoint**: `https://mixpanel.com/api/app/gdpr-delete/`
- **Method**: POST
- **Authentication**: OAuth Token (Bearer) or Service Account
- **Request**: Creates deletion request for a `distinct_id`
- **Response**: Returns `task_id` for status tracking
- **Status Check**: Polls status endpoint to check completion

### Singular OpenDSR API

- **Endpoint**: `https://api.singular.net/api/v1/opendsr`
- **Method**: POST
- **Authentication**: API Key (header)
- **Request**: Creates OpenDSR erasure request with:
  - `subject_request_id` (UUIDv4)
  - `subject_request_type`: "erasure"
  - `subject_identities`: User ID
  - `property_id`: Platform-specific (e.g., "Android:com.peerplay.megamerge")
- **Status Check**: Polls status endpoint to check completion

### AppLovin Max Partner Deletion API

- **Endpoint**: `https://api.applovin.com/gdpr/delete`
- **Method**: POST
- **Authentication**: API Key (query parameter)
- **Request**: Batch deletion of advertising IDs (IDFA/GAID)
  - Body: Newline-separated list of advertising IDs
  - Content-Type: `text/plain`
- **Response**: Returns `num_deleted_ids` or `num_valid_ids` (count of processed IDs)
- **Status**: Synchronous (status set immediately)

## Message Parsing

The tool uses regex patterns to extract information from message text:

- **distinct_id**: Looks for patterns like:
  - "user_id: 12345"
  - "distinct_id: 12345"
  - "User ID: 12345"
  - Alphanumeric strings of 8+ characters
- **ticket_id**: Looks for patterns like:
  - "ticket: 12345"
  - "ticket_id: 12345"
  - "#12345"
  - "Ticket number 12345"
- **request_date**: Looks for date patterns (YYYY-MM-DD, MM/DD/YYYY) or uses message timestamp

If parsing fails for a message, it will be skipped with a warning.

## Error Handling

- Messages that cannot be parsed are logged with a warning and skipped
- BigQuery insertion errors will stop processing and raise an exception
- Slack API errors (e.g., adding reactions) are logged but don't stop processing
- API errors (Mixpanel, Singular, AppLovin) are logged and marked as "pending"
- Status check errors are logged but don't stop processing

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

### API errors

**Mixpanel:**
- Verify OAuth token or Service Account credentials are correct
- Check that project token is valid
- See [MIXPANEL-AUTH-GUIDE.md](MIXPANEL-AUTH-GUIDE.md) for authentication setup

**Singular:**
- Verify API key is correct
- Check that property_id matches your app (Android/iOS)
- See [API-SETUP.md](API-SETUP.md) for setup instructions

**AppLovin:**
- Verify API key is correct
- Check that advertising IDs are valid (IDFA/GAID format)
- See [API-SETUP.md](API-SETUP.md) for setup instructions

### Process taking too long
- The tool now uses batch queries for better performance
- If still slow, check network connectivity to APIs
- Consider running on smaller date ranges

## Security Notes

- Never commit API keys or tokens to version control
- Use Secret Manager for production deployments
- The tool requires:
  - Read access to Slack channels
  - Write access to BigQuery
  - API access to Mixpanel, Singular, and AppLovin

## Related Documentation

- [Slack App Setup Guide](README-SLACK-SETUP.md) - Detailed instructions for setting up the Slack app
- [API Setup Guide](API-SETUP.md) - Instructions for configuring API credentials
- [Mixpanel Auth Guide](MIXPANEL-AUTH-GUIDE.md) - Mixpanel authentication options
- [Quick Start Guide](QUICK-START.md) - Quick setup instructions
- [Quick Run Guide](QUICK-RUN.md) - Simple run instructions
- [Shared Utilities](../shared/) - Reusable Slack and BigQuery client functions

## Process Flow Summary

```
1. Fetch messages from Slack channel (date range)
   ↓
2. Filter messages (must contain "delete", "user", "ticket")
   ↓
3. Split into two groups:
   - New messages (no computer/checkmark) → Phase 1
   - In-progress messages (has computer/checkmark) → Phase 2
   ↓
4. Phase 1: New Request Processing
   - Parse messages
   - Batch fetch player data, advertising IDs, existing records
   - For each message:
     - Check 14-day inactivity
     - Create Mixpanel deletion request
     - Create Singular deletion request
     - Create AppLovin deletion request (if advertising IDs exist)
     - Insert BigQuery record
     - Add computer emoji
   ↓
5. Phase 2: Status Check Processing
   - For each message:
     - Fetch record from BigQuery
     - Skip if already completed
     - Check Mixpanel status (if not completed)
     - Check Singular status (if not completed)
     - Update BigQuery with latest statuses
     - Update emojis (red car when 3 APIs done, checkmark when all done)
   ↓
6. Complete!
```