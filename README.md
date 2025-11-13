# GDPR Request Automation Tool

A comprehensive tool for automating GDPR data deletion requests across multiple platforms: Mixpanel, Singular, and BigQuery.

## Features

- **Automated Deletion Requests**: Create deletion requests in Mixpanel and Singular
- **BigQuery Data Deletion**: Delete user data from specified BigQuery tables
- **Status Tracking**: Track deletion status in a dedicated BigQuery table
- **Batch Processing**: Process multiple users in a single operation
- **Comprehensive Logging**: Detailed logs of all operations
- **Error Handling**: Robust error handling and reporting

## Architecture

The tool is organized into several modules:

- **config.py**: Configuration management
- **mixpanel.py**: Mixpanel GDPR API integration
- **singular.py**: Singular GDPR API integration
- **bigquery.py**: BigQuery data deletion and status tracking
- **orchestrator.py**: Coordinates all deletion operations
- **main.py**: CLI entry point

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd Tools
```

2. Create a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure the tool:
```bash
cp config.example.yaml config.yaml
# Edit config.yaml with your credentials
```

## Configuration

Edit `config.yaml` with your credentials and settings:

```yaml
mixpanel:
  project_id: "YOUR_MIXPANEL_PROJECT_ID"
  token: "YOUR_MIXPANEL_PROJECT_TOKEN"
  api_secret: "YOUR_MIXPANEL_API_SECRET"

singular:
  api_key: "YOUR_SINGULAR_API_KEY"

bigquery:
  project_id: "YOUR_GCP_PROJECT_ID"
  credentials_path: "/path/to/service-account-key.json"
  status_table: "gdpr.deletion_status"
  tables_to_delete:
    - "analytics.user_events"
    - "analytics.user_profiles"
```

### Required Credentials

1. **Mixpanel**:
   - Project ID: Found in your Mixpanel project settings
   - Token: Your project token
   - API Secret: Your API secret for authentication

2. **Singular**:
   - API Key: Obtained from Singular dashboard

3. **BigQuery**:
   - Project ID: Your GCP project ID
   - Service Account Credentials: JSON key file with BigQuery permissions
   - Required permissions: `bigquery.tables.delete`, `bigquery.tables.updateData`, `bigquery.tables.create`

## Usage

### Setup

First, create the BigQuery status tracking table:

```bash
python main.py setup
```

### Process Deletions

Process deletion requests for specific users:

```bash
# Single or multiple users (comma-separated)
python main.py process --users user123,user456,user789

# From a file (one user ID per line)
python main.py process --users-file users.txt
```

### Check Status

Check the deletion status for a specific user:

```bash
python main.py status --user-id user123
```

### Advanced Options

```bash
# Specify custom BigQuery column name
python main.py process --users user123 --user-id-column custom_user_id

# Specify Singular ID type
python main.py process --users user123 --singular-id-type idfa

# Use custom config file
python main.py --config custom-config.yaml process --users user123

# Enable debug logging
python main.py --log-level DEBUG process --users user123
```

## Workflow

For each user, the tool performs the following steps:

1. **Update Status**: Sets deletion status to "in_progress" in BigQuery
2. **Mixpanel Deletion**: Creates a deletion request via Mixpanel GDPR API
3. **Singular Deletion**: Creates a deletion request via Singular GDPR API
4. **BigQuery Deletion**: Deletes user data from specified tables
5. **Status Update**: Updates the status table with results from all platforms

## Status Tracking

The BigQuery status table contains:

- `user_id`: User identifier
- `request_date`: When the deletion was requested
- `deletion_status`: Overall status (pending, in_progress, completed, failed)
- `mixpanel_status`: Mixpanel deletion status
- `mixpanel_task_id`: Mixpanel task ID for tracking
- `singular_status`: Singular deletion status
- `singular_request_id`: Singular request ID for tracking
- `bigquery_status`: BigQuery deletion status
- `bigquery_tables_affected`: List of affected tables
- `last_updated`: Last status update timestamp
- `error_message`: Error details if deletion failed
- `completed_date`: Completion timestamp

## Logging

All operations are logged to:
- Console (stdout)
- Log file: `gdpr_tool.log`

Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL

## Error Handling

The tool continues processing even if individual deletions fail:
- Each platform deletion is independent
- Failures are logged and tracked in the status table
- The tool reports overall success/failure statistics
- Exit code 1 if any deletions fail

## Security Best Practices

1. **Never commit config.yaml** - It contains sensitive credentials
2. **Use service accounts** with minimal required permissions
3. **Rotate credentials** regularly
4. **Store credentials securely** (e.g., use secret managers in production)
5. **Audit logs** regularly for suspicious activity
6. **Test with non-production data** first

## API Documentation

- [Mixpanel GDPR API](https://developer.mixpanel.com/reference/delete-user-gdpr-api)
- [Singular GDPR API](https://support.singular.net/hc/en-us/articles/360037587312-GDPR-Data-Deletion)
- [BigQuery Python Client](https://cloud.google.com/python/docs/reference/bigquery/latest)

## Project Structure

```
Tools/
├── gdpr_tool/
│   ├── __init__.py
│   ├── config.py
│   ├── mixpanel.py
│   ├── singular.py
│   ├── bigquery.py
│   └── orchestrator.py
├── main.py
├── requirements.txt
├── config.example.yaml
├── .gitignore
└── README.md
```

## Troubleshooting

### "Configuration file not found"
- Ensure `config.yaml` exists and is properly formatted
- Check the `--config` parameter if using a custom path

### "Authentication failed"
- Verify all credentials in `config.yaml`
- Check service account permissions for BigQuery
- Ensure API keys are active and not expired

### "Table not found"
- Run `python main.py setup` to create the status table
- Verify BigQuery dataset exists
- Check table names in configuration

### "Permission denied"
- Verify BigQuery service account has required permissions
- Check Mixpanel and Singular API key permissions

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

[Add your license here]

## Support

For issues and questions:
- Check the logs in `gdpr_tool.log`
- Review the API documentation links above
- Open an issue in the repository