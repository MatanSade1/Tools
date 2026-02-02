# Mission Configuration Validator - Build Summary

## ✅ What Was Built

A complete Python-based validation tool that compares user mission configurations across three data sources:

1. **User Spreadsheet** - Contains actual user configurations
2. **BigQuery Table** - Contains segment assignments
3. **Config Spreadsheet** - Contains expected configurations per segment

The tool validates:
- ✅ Segment assignments (BigQuery vs expected)
- ✅ Mission configurations (8 positions × 4 fields each)

Results are written to a new tab in an output spreadsheet with detailed differences.

## 📁 Files Created

### Core Files
1. **`mission_config_validator.py`** - Main validation script (420 lines)
   - Fetches data from 2 spreadsheets and BigQuery
   - Validates segments and configurations
   - Writes results to output spreadsheet
   - Handles flexible column name detection
   - Provides detailed error reporting

2. **`MISSION_VALIDATION_README.md`** - Comprehensive documentation
   - Architecture diagram
   - Setup instructions
   - Usage examples
   - Troubleshooting guide

3. **`run_mission_validator.sh`** - Convenience run script
   - Checks dependencies
   - Verifies GCP authentication
   - Runs the validator

4. **`test_mission_validator_setup.py`** - Setup verification script
   - Tests all dependencies
   - Verifies authentication
   - Checks spreadsheet and BigQuery access

### Updated Files
5. **`requirements.txt`** - Added dependencies:
   - `pandas>=2.0.0`
   - `google-api-python-client>=2.100.0`
   - `google-auth>=2.23.0`
   - `google-auth-oauthlib>=1.1.0`
   - `google-auth-httplib2>=0.1.1`

## 🚀 Quick Start

### 1. Test Your Setup
```bash
cd /Users/matansade/Tools
python3 test_mission_validator_setup.py
```

This will verify:
- ✅ Python dependencies installed
- ✅ GCP authentication configured
- ✅ BigQuery access working
- ✅ Spreadsheet access working

### 2. Run the Validator

**Option A: Using the run script (recommended)**
```bash
./run_mission_validator.sh
```

**Option B: Direct execution**
```bash
python3 mission_config_validator.py
```

### 3. Check Results

The validator will create a new tab in the output spreadsheet:
- Tab name: `validation_YYYYMMDD_HHMMSS`
- URL: https://docs.google.com/spreadsheets/d/1hph4x2MPemtTD8B8TSO8yjV2jH6XuM19CySTsujpFDw

## 📊 Data Flow

```
Step 1: Read User Data
  ↓ User Spreadsheet (1YZ-7pqKmYb43UnSXYneZT20elkcc1UTb9hDI4tjUhio)
  ├─ distinct_id
  ├─ config_segment
  └─ 32 config fields (8 positions × 4 fields)

Step 2: Read Expected Configs
  ↓ Config Spreadsheet (1L94yMz3iahaJdTCAE5v5NAPFfnLJ9DHVjlTWf11CIKM)
  ├─ SegmentId
  └─ 32 expected config fields per segment

Step 3: Query BigQuery
  ↓ yotam-395120.peerplay.mission_segmentation_test
  ├─ distinct_id
  └─ segment_name

Step 4: Validate
  ├─ Segment match? (segment_name == config_segment)
  └─ Config match? (32 fields comparison)

Step 5: Write Results
  ↓ Output Spreadsheet (1hph4x2MPemtTD8B8TSO8yjV2jH6XuM19CySTsujpFDw)
  ├─ distinct_id
  ├─ is_difference (yes/no)
  ├─ difference_type (segment/config)
  └─ detailed_difference (human-readable)
```

## 🔧 Configuration

### Spreadsheet IDs (in `mission_config_validator.py`)
```python
USER_SPREADSHEET_ID = "1YZ-7pqKmYb43UnSXYneZT20elkcc1UTb9hDI4tjUhio"
CONFIG_SPREADSHEET_ID = "1L94yMz3iahaJdTCAE5v5NAPFfnLJ9DHVjlTWf11CIKM"
OUTPUT_SPREADSHEET_ID = "1hph4x2MPemtTD8B8TSO8yjV2jH6XuM19CySTsujpFDw"
```

### BigQuery Table
```python
BQ_PROJECT = "yotam-395120"
BQ_DATASET = "peerplay"
BQ_TABLE = "mission_segmentation_test"
```

### Validation Parameters
```python
NUM_POSITIONS = 8  # Number of mission positions
FIELDS_PER_POSITION = ["item_id", "item_quantity", "mission_type", "target_amount"]
```

## 🎯 Validation Logic

### Segment Validation
1. For each user, query BigQuery for their `segment_name`
2. Compare with `config_segment` from user spreadsheet
3. If mismatch → Report as "segment" difference
4. If user not in BigQuery → Report as "segment" difference

### Configuration Validation
Only runs if segment validation passes:

1. Look up expected config based on user's segment
2. For positions 1-8, compare:
   - `item_id_Y` ↔ `SubConfigYReward1Id`
   - `item_quantity_Y` ↔ `SubConfigYReward1Count`
   - `mission_type_Y` ↔ `SubConfigYType`
   - `target_amount_Y` ↔ `SubConfigYAmount`
3. Report all mismatches with position and field details

### Flexible Column Detection
The script auto-detects column names using patterns:
- `item_id_1`, `position_1_item_id`, `pos_1_item_id`, `p1_item_id`, `item_id1`
- Case-insensitive matching
- Handles spaces, underscores, hyphens

## 📋 Output Format

### Output Columns
| Column | Values | Description |
|--------|--------|-------------|
| `distinct_id` | User ID | User identifier |
| `is_difference` | "yes" / "no" | Whether differences were found |
| `difference_type` | "segment" / "config" / empty | Type of difference |
| `detailed_difference` | Text | Human-readable description |

### Example Output
```
distinct_id | is_difference | difference_type | detailed_difference
------------|---------------|-----------------|---------------------
user_001    | yes           | segment         | Segment mismatch - Expected: premium, BigQuery: basic
user_002    | yes           | config          | Position 1: item_id: expected=100, actual=200; mission_type: expected=daily, actual=weekly
user_003    | no            |                 |
```

## 🛠️ Prerequisites

### Required
1. **Python 3.7+** with pip
2. **GCP Authentication** configured
   ```bash
   gcloud auth application-default login
   ```

3. **Permissions**:
   - Read access to user and config spreadsheets
   - Write access to output spreadsheet
   - BigQuery read access to `yotam-395120.peerplay.mission_segmentation_test`

### Installation
```bash
pip3 install -r requirements.txt
```

## 📖 Usage Examples

### Example 1: First-time Setup
```bash
# 1. Test setup
python3 test_mission_validator_setup.py

# 2. If all tests pass, run validator
./run_mission_validator.sh
```

### Example 2: Quick Run
```bash
# Already configured? Just run it
python3 mission_config_validator.py
```

### Example 3: Troubleshooting
```bash
# If you get auth errors
gcloud auth application-default login

# If dependencies are missing
pip3 install -r requirements.txt

# Re-test setup
python3 test_mission_validator_setup.py
```

## 🐛 Troubleshooting

### Authentication Errors
```
❌ Error: Could not authenticate with GCP
```
**Fix**: Run `gcloud auth application-default login`

### Missing Dependencies
```
❌ ModuleNotFoundError: No module named 'pandas'
```
**Fix**: Run `pip3 install -r requirements.txt`

### Spreadsheet Access Denied
```
❌ Error: Requested entity was not found
```
**Fix**: 
- Verify spreadsheet IDs in the script
- Check you have read/write permissions
- Make sure spreadsheets are shared with your account

### BigQuery Access Error
```
❌ Error querying BigQuery: Access Denied
```
**Fix**:
- Verify you have BigQuery access to `yotam-395120.peerplay`
- Check the table exists: `mission_segmentation_test`

### Column Not Found
```
❌ Could not find distinct_id column
```
**Fix**: 
- Check your user spreadsheet has a `distinct_id` column
- Supported names: `distinct_id`, `distinctid`, `user_id`, etc.

## 🔍 Key Features

### ✅ Robust Column Detection
- Automatically finds columns with flexible naming
- Case-insensitive matching
- Supports multiple naming conventions

### ✅ Comprehensive Validation
- Validates 32 configuration fields per user (8 positions × 4 fields)
- Provides detailed difference descriptions
- Handles missing data gracefully

### ✅ Batch Processing
- Queries BigQuery once for all users
- Efficient data fetching from spreadsheets
- Progress reporting during validation

### ✅ Error Handling
- Graceful handling of missing users in BigQuery
- Auto-fallback to CSV if spreadsheet write fails
- Detailed error messages with actionable fixes

### ✅ Timestamped Output
- Each run creates a new tab with timestamp
- Preserves historical validation results
- Easy to track changes over time

## 📚 Documentation

- **Full Documentation**: [`MISSION_VALIDATION_README.md`](MISSION_VALIDATION_README.md)
- **Main Tools README**: [`README.md`](README.md)

## 🎉 Ready to Use!

Your mission configuration validator is ready. To get started:

```bash
# Test your setup
python3 test_mission_validator_setup.py

# Run the validator
./run_mission_validator.sh

# Or run directly
python3 mission_config_validator.py
```

Results will appear in a new tab in the output spreadsheet!
