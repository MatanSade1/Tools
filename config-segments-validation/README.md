# Configuration & Segments Validation Tool

This directory contains the validation tool for comparing actual user data against expected configurations and segment assignments for various features.

## 📁 Contents

### Main Scripts
- **`mission_config_validator.py`** - Main validation script
- **`run_mission_validator.sh`** - Helper script to run validations
- **`test_mission_validator_setup.py`** - Setup verification script

### Supported Features
1. **Missions** - Daily/weekly mission validation
2. **Race** - Race event configuration validation
3. **Time-Board-Tasks (TBT)** - Timed board task validation

### Documentation
- **`MISSION_VALIDATION_README.md`** - Complete overview
- **`MISSION_VALIDATOR_QUICKSTART.md`** - Quick start guide
- **`VALIDATOR_QUICK_REFERENCE.md`** - Command reference
- **`RACE_VALIDATION_LOGIC_EXPLAINED.md`** - Race validation details
- **`VALIDATOR_RACE_FEATURE_SUMMARY.md`** - Race feature summary
- **`VALIDATOR_TIME_BOARD_TASKS_SUMMARY.md`** - TBT feature summary
- **`TBT_ALL_FIXES_COMPLETE.md`** - TBT fixes documentation

### Validation Results
CSV files containing historical validation results:
- `validation_results_YYYYMMDD_HHMMSS.csv`

## 🚀 Quick Start

```bash
# Basic usage
python3 mission_config_validator.py \
  --live-ops-id 4252 \
  --start-date 2026-01-26 \
  --end-date 2026-01-26 \
  --feature time-board-tasks \
  --config-spreadsheet-id YOUR_SPREADSHEET_ID
```

## 📊 Features

### Validation Types
- **Segment Validation**: Compare actual vs expected user segments
- **Configuration Validation**: Compare event parameters vs expected config values

### Output Formats
- Google Sheets (with auto-generated tabs)
- CSV files (backup)

### Version Support
- Modern versions (>=0.378)
- Legacy versions (<0.378) with `--version-filter`

## 🔧 Requirements

- Python 3.9+
- Google Cloud SDK (authenticated)
- BigQuery access
- Google Sheets API access

## 📝 Usage Examples

### Race Validation
```bash
python3 mission_config_validator.py \
  --feature race \
  --live-ops-id 4230 \
  --start-date 2026-01-26 \
  --end-date 2026-01-26 \
  --config-spreadsheet-id 1M5LUieqAxtwAcOhexxBgMkwV0lh85YQgGVhatUyQjIY
```

### TBT Validation (Old Version)
```bash
python3 mission_config_validator.py \
  --feature time-board-tasks \
  --live-ops-id 4252 \
  --start-date 2026-01-26 \
  --end-date 2026-01-26 \
  --config-spreadsheet-id 1b68uDDLuGGawiWWIARA5AvB1TU5Yrv1drIVDezznmmg \
  --version-filter "<0.378" \
  --segment-tab distinct_id_segmentation_list \
  --skip-config-validation
```

## 📚 More Information

See individual documentation files for detailed information on each feature and validation type.
