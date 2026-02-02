# Mission Configuration Validator

## Overview

This tool validates user mission configurations by comparing data across Google Sheets and BigQuery. It performs two types of validation:

1. **Segment Validation**: Verifies that users have the correct segment assignment in BigQuery
2. **Configuration Validation**: Compares mission configurations between actual user values and expected segment values

## Architecture

```
┌─────────────────────┐
│ User Spreadsheet    │  ← Actual user configurations
│ (distinct_id +      │
│  config values)     │
└──────────┬──────────┘
           │
           ├──────────────────┐
           │                  │
           ▼                  ▼
┌─────────────────────┐  ┌─────────────────────┐
│ BigQuery            │  │ Config Spreadsheet  │
│ mission_seg_test    │  │ (Expected configs   │
│ (segment_name)      │  │  per segment)       │
└──────────┬──────────┘  └──────────┬──────────┘
           │                        │
           └────────┬───────────────┘
                    │
                    ▼
         ┌─────────────────────┐
         │ Validation Script   │
         └──────────┬──────────┘
                    │
                    ▼
         ┌─────────────────────┐
         │ Output Spreadsheet  │
         │ (Results with       │
         │  differences)       │
         └─────────────────────┘
```

## Data Sources

### 1. User Spreadsheet (Input)
- **ID**: `1YZ-7pqKmYb43UnSXYneZT20elkcc1UTb9hDI4tjUhio`
- **Contains**: User distinct_ids and their actual mission configurations
- **Required Columns**:
  - `distinct_id` - User identifier
  - `config_segment` - Expected segment for the user
  - Configuration fields for 8 positions (auto-detected):
    - `item_id_1` through `item_id_8`
    - `item_quantity_1` through `item_quantity_8`
    - `mission_type_1` through `mission_type_8`
    - `target_amount_1` through `target_amount_8`

### 2. BigQuery Table
- **Project**: `yotam-395120`
- **Dataset**: `peerplay`
- **Table**: `mission_segmentation_test`
- **Columns**:
  - `distinct_id` - User identifier
  - `segment_name` - Actual segment assigned to user
  - `config_types` - Configuration metadata (not used in validation)

### 3. Configuration Spreadsheet (Expected Values)
- **ID**: `1L94yMz3iahaJdTCAE5v5NAPFfnLJ9DHVjlTWf11CIKM`
- **Contains**: Expected configurations for each segment
- **Required Columns**:
  - `SegmentId` - Segment identifier (used for matching)
  - For each position 1-8:
    - `SubConfig{N}Reward1Id` - Expected item_id for position N
    - `SubConfig{N}Reward1Count` - Expected item_quantity for position N
    - `SubConfig{N}Type` - Expected mission_type for position N
    - `SubConfig{N}Amount` - Expected target_amount for position N

### 4. Output Spreadsheet
- **ID**: `1hph4x2MPemtTD8B8TSO8yjV2jH6XuM19CySTsujpFDw`
- **Creates**: New tab for each run with timestamp
- **Output Columns**:
  - `distinct_id` - User identifier
  - `is_difference` - "yes" or "no"
  - `difference_type` - "segment", "config", or empty
  - `detailed_difference` - Human-readable description of differences

## Setup

### 1. Install Dependencies

```bash
cd /Users/matansade/Tools
pip install -r requirements.txt
```

### 2. Configure Authentication

The tool uses Google Cloud authentication for both BigQuery and Google Sheets access. Make sure you have:

1. **GCP Credentials**: Application Default Credentials (ADC) configured
   ```bash
   gcloud auth application-default login
   ```

2. **Google Sheets API Access**: The service account or user must have:
   - Read access to the user and config spreadsheets
   - Write access to the output spreadsheet

### 3. Environment Variables (Optional)

You can set the GCP project ID:
```bash
export GCP_PROJECT_ID="yotam-395120"
```

## Usage

### Run the Validator

```bash
python mission_config_validator.py
```

The script will:
1. Read all users from the user spreadsheet
2. Fetch expected configurations from the config spreadsheet
3. Query BigQuery for actual segment assignments
4. Validate each user's segment and configuration
5. Write results to a new tab in the output spreadsheet

### Output

The script creates a new tab in the output spreadsheet with a timestamp (e.g., `validation_20260126_143025`).

Each row contains:
- **distinct_id**: User's identifier
- **is_difference**: 
  - `"yes"` - Differences found
  - `"no"` - Everything matches
- **difference_type**:
  - `"segment"` - Segment mismatch between BigQuery and expected
  - `"config"` - Configuration mismatch (segment is correct but values differ)
  - Empty if no difference
- **detailed_difference**: Detailed description of what doesn't match

### Example Output

```
distinct_id     | is_difference | difference_type | detailed_difference
----------------|---------------|-----------------|--------------------
user_123        | yes           | segment         | Segment mismatch - Expected: premium, BigQuery: basic
user_456        | yes           | config          | Position 1: item_id: expected=100, actual=200; mission_type: expected=daily, actual=weekly | Position 3: target_amount: expected=50, actual=75
user_789        | no            |                 |
```

## Validation Logic

### Segment Validation (Step 1)

1. Look up user's `distinct_id` in BigQuery `mission_segmentation_test` table
2. Compare `segment_name` (BigQuery) with `config_segment` (user spreadsheet)
3. If they don't match → Report as segment difference
4. If user not found in BigQuery → Report as segment difference with "User not found"

### Configuration Validation (Step 2)

Only performed if segment validation passes:

1. Look up expected configuration based on user's segment in config spreadsheet
2. For each of 8 positions, compare 4 fields:
   - `item_id_N` vs `SubConfigNReward1Id`
   - `item_quantity_N` vs `SubConfigNReward1Count`
   - `mission_type_N` vs `SubConfigNType`
   - `target_amount_N` vs `SubConfigNAmount`
3. Report all mismatches with position and field details

### Column Name Detection

The script automatically detects column names using flexible pattern matching:
- Case-insensitive matching
- Supports multiple naming patterns (e.g., `item_id_1`, `position_1_item_id`, `p1_item_id`)
- Handles spaces, underscores, and hyphens

## Troubleshooting

### "Could not find distinct_id column"
- Check that your user spreadsheet has a column named `distinct_id` (or similar)
- Supported variations: `distinct_id`, `distinctid`, `distinct id`, `user_id`, `userid`

### "Could not find config_segment column"
- Check that your user spreadsheet has a column for the expected segment
- Supported variations: `config_segment`, `configsegment`, `segment`, `segment_name`

### "Error querying BigQuery"
- Verify GCP authentication is configured: `gcloud auth application-default login`
- Check that you have read access to the BigQuery table
- Verify the table exists: `yotam-395120.peerplay.mission_segmentation_test`

### "Error writing to spreadsheet"
- Check that you have write access to the output spreadsheet
- If writing fails, results are automatically saved to a CSV file as backup

### Missing Configuration Fields
- The script will report missing fields in the detailed_difference column
- Empty or NULL values are handled gracefully

## Customization

To modify the spreadsheet IDs or BigQuery table, edit these constants in `mission_config_validator.py`:

```python
USER_SPREADSHEET_ID = "1YZ-7pqKmYb43UnSXYneZT20elkcc1UTb9hDI4tjUhio"
CONFIG_SPREADSHEET_ID = "1L94yMz3iahaJdTCAE5v5NAPFfnLJ9DHVjlTWf11CIKM"
OUTPUT_SPREADSHEET_ID = "1hph4x2MPemtTD8B8TSO8yjV2jH6XuM19CySTsujpFDw"

BQ_PROJECT = "yotam-395120"
BQ_DATASET = "peerplay"
BQ_TABLE = "mission_segmentation_test"

NUM_POSITIONS = 8  # Number of mission positions to validate
```

## Support

For issues or questions, contact the data team or check the [main Tools README](README.md).
