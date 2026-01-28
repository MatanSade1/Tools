# UA Cohort Query Tool

A Slack slash command tool that allows marketing media buyers to query the UA cohort BigQuery table using natural language questions, powered by Claude AI.

## Features

- **Natural Language Queries**: Ask questions in plain English about UA cohort data
- **Automatic SQL Generation**: Claude generates optimized BigQuery SQL from your questions
- **Security Validation**: All queries are validated to ensure only SELECT statements on the ua_cohort table
- **Smart Response Formatting**:
  - Single values: Direct Slack message
  - Small result sets (≤10 rows): Formatted table in Slack
  - Large result sets: CSV file uploaded to Slack

## Example Questions

```
/uacohort Give me the total cost per month from Jan 2024 till today
/uacohort What is the D7 ROAS split by platform for last week?
/uacohort Show me the avg retention for offerwalls in the last 10 weeks
/uacohort Give me the ltv roas for september month
/uacohort What's the projected monthly spend based on current daily average?
```

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│    Slack    │────▶│  Cloud Run  │────▶│   Claude    │
│  /uacohort  │     │   Service   │     │   (SQL Gen) │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  BigQuery   │
                    │  ua_cohort  │
                    └─────────────┘
```

## Setup

### Prerequisites

1. **GCP Project**: Access to `yotam-395120` project with permissions to:
   - Create Cloud Run services
   - Create service accounts
   - Manage Secret Manager secrets
   - Query BigQuery

2. **Claude API Key**: Get an API key from [Anthropic Console](https://console.anthropic.com/)

3. **Slack Workspace**: Admin access to create a Slack app

### Step 1: Create Slack App

1. Go to [Slack API Apps](https://api.slack.com/apps)

2. Click **Create New App** → **From scratch**

3. Enter:
   - App Name: `UA Cohort Query`
   - Workspace: Select your workspace

4. Under **OAuth & Permissions**, add these Bot Token Scopes:
   - `chat:write` - Send messages
   - `files:write` - Upload CSV files
   - `commands` - Handle slash commands

5. Click **Install to Workspace** and authorize

6. Copy the **Bot User OAuth Token** (starts with `xoxb-`)

7. Under **Basic Information**, copy the **Signing Secret**

### Step 2: Deploy the Service

1. Navigate to the project directory:
   ```bash
   cd /Users/matansade/Tools/ua-cohort-query
   ```

2. Run the deployment script:
   ```bash
   ./deploy.sh
   ```

3. When prompted, enter:
   - Claude API key
   - Slack Bot Token
   - Slack Signing Secret

4. After deployment, copy the Cloud Run URL from the output

### Step 3: Configure Slash Command

1. Back in Slack App settings, go to **Slash Commands**

2. Click **Create New Command**

3. Configure:
   - **Command**: `/uacohort`
   - **Request URL**: `https://[YOUR-CLOUD-RUN-URL]/slack/command`
   - **Short Description**: Query UA cohort data with natural language
   - **Usage Hint**: `[your question about UA data]`

4. Click **Save**

### Step 4: Test

In any Slack channel:
```
/uacohort Give me the total cost for January 2024
```

## Development

### Local Testing

1. Set environment variables:
   ```bash
   export CLAUDE_API_KEY="your-claude-api-key"
   export SLACK_BOT_TOKEN="xoxb-your-token"
   export SLACK_SIGNING_SECRET="your-signing-secret"
   export SKIP_SLACK_VERIFICATION="true"  # Skip signature verification locally
   export GCP_PROJECT_ID="yotam-395120"
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run locally:
   ```bash
   python main.py
   ```

4. Test with curl:
   ```bash
   curl "http://localhost:8080/test?q=Give%20me%20the%20total%20cost%20for%20January%202024"
   ```

### Project Structure

```
ua-cohort-query/
├── main.py              # Flask app, Slack handlers, orchestration
├── query_generator.py   # Claude integration for SQL generation
├── query_validator.py   # SQL validation and security
├── requirements.txt     # Python dependencies
├── Dockerfile          # Container configuration
├── deploy.sh           # Deployment script
└── README.md           # This file
```

## Security

This tool implements multiple layers of security:

1. **Slack Request Verification**: All requests are verified using Slack's signing secret
2. **Query Validation**: 
   - Only SELECT statements allowed
   - Only `ua_cohort` table can be accessed
   - SQL injection patterns are blocked
   - DDL/DML statements are blocked
3. **IAM Permissions**: Service account has read-only BigQuery access
4. **Secret Management**: All credentials stored in GCP Secret Manager

## UA Cohort Table Schema

The tool queries `yotam-395120.peerplay.ua_cohort` which contains:

### Dimensions
- `install_date`, `week`, `month`, `year`
- `platform` (Android, Apple)
- `country`
- `mediasource`
- `campaign_name`
- `media_type` (Offerwalls, Non-Offerwalls, Organic)
- `is_test_campaign`

### Core Metrics
- `installs`, `cost`, `rt_cost`

### Cohort Metrics (D0, D1, D3, D7, D14, D21, D30, D45, D60, D75, D90, D120, D150, D180, D210, D240, D270, D300, D330, D360)
- ROAS: `d{X}_total_net_revenue`
- FTDs: `d{X}_ftds`
- Retention: `d{X}_retention`
- Payer Retention: `d{X}_payers_retention`

### Lifetime Metrics
- `ltv_total_net_revenue`
- `ltv_ftds`

## Troubleshooting

### "Could not generate query"
- Try rephrasing your question more specifically
- Reference specific columns or metrics mentioned in the schema

### "Query validation failed"
- The generated query tried to access other tables or modify data
- Rephrase to focus on reading data from ua_cohort

### "No results found"
- Check your date ranges
- Verify filter values exist in the data

### View Logs
```bash
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="ua-cohort-query"' --limit=50
```

## Cost Considerations

- **Cloud Run**: Pay only when handling requests (typically < $5/month for moderate usage)
- **Claude API**: ~$0.01-0.03 per query depending on complexity
- **BigQuery**: Minimal for SELECT queries on partitioned data

## Support

For issues or feature requests, contact the Data team.



