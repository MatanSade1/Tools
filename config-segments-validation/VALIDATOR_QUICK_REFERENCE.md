# Configuration Validator - Quick Reference

## Quick Start

### Validate Missions (Today)
```bash
./run_mission_validator.sh --live-ops-id 4253 --feature missions --days-back 0
```

### Validate Race (Today)
```bash
./run_mission_validator.sh --live-ops-id 4230 --feature race --days-back 0
```

## Command Options

### Required Parameters
- `--live-ops-id <ID>`: Live ops ID to validate
- `--feature <missions|race>`: Feature to validate

### Date Options (choose one)
- `--days-back <N>`: Validate data from N days ago to today
- `--start-date <YYYY-MM-DD> --end-date <YYYY-MM-DD>`: Specific date range

### Optional Parameters
- `--config-spreadsheet-id <ID>`: Override default config spreadsheet

## Examples

### Validate Last Week
```bash
./run_mission_validator.sh --live-ops-id 4253 --feature missions --days-back 7
```

### Validate Specific Date Range
```bash
./run_mission_validator.sh \
  --live-ops-id 4230 \
  --feature race \
  --start-date 2026-01-20 \
  --end-date 2026-01-26
```

### Custom Config Sheet
```bash
python3 mission_config_validator.py \
  --live-ops-id 4253 \
  --feature missions \
  --days-back 0 \
  --config-spreadsheet-id YOUR_SPREADSHEET_ID
```

## Feature Defaults

### Missions
- **Event**: `impression_missions_popup`
- **Live Ops Field**: `live_ops_id`
- **Default Config Sheet**: `1L94yMz3iahaJdTCAE5v5NAPFfnLJ9DHVjlTWf11CIKM`
- **Validates**: Segment assignment + configuration

### Race
- **Event**: `impression_race_popup`
- **Live Ops Field**: `race_live_ops_id`
- **Default Config Sheet**: `1M5LUieqAxtwAcOhexxBgMkwV0lh85YQgGVhatUyQjIY`
- **Validates**: Configuration only (segments are assigned by config)

## Output

All results go to: `https://docs.google.com/spreadsheets/d/1hph4x2MPemtTD8B8TSO8yjV2jH6XuM19CySTsujpFDw`

Each run creates a new tab: `validation_YYYYMMDD_HHMMSS`

## Interpreting Results

### Perfect Match
```
distinct_id: 12345...
is_difference: no
```
✅ Configuration exactly matches expected values

### Segment Difference (Missions Only)
```
is_difference: yes
difference_type: segment
```
⚠️ User got wrong segment (actual ≠ expected)

### Config Difference
```
is_difference: yes
difference_type: config
```
❌ Configuration doesn't match expected values for their segment

## Common Live Ops IDs

| Feature | ID | Description |
|---------|--------|-------------|
| Missions | 4253 | Recent missions live ops |
| Race | 4230 | Recent race live ops |

## Troubleshooting

### No users found
- Check that the live-ops-id is correct
- Verify the date range has data
- Ensure users meet the filters (version ≥ 0.378, not fraudsters, etc.)

### Config not found
- Verify the config spreadsheet ID
- Check that segment names in the config match event data
- For race, ensure "Full config to upload" tab exists

### Authentication errors
Run:
```bash
gcloud auth application-default login \
  --scopes=https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/spreadsheets,https://www.googleapis.com/auth/bigquery
```

## File Locations

- **Main Script**: `mission_config_validator.py`
- **Run Script**: `run_mission_validator.sh`
- **Documentation**:
  - `MISSION_VALIDATOR_SUMMARY.md` - Overview
  - `MISSION_VALIDATOR_QUICKSTART.md` - Getting started
  - `MISSION_VALIDATOR_V2_CHANGES.md` - V2 updates
  - `MISSION_VALIDATOR_COMMAND_REFERENCE.md` - Detailed commands
  - `VALIDATOR_RACE_FEATURE_SUMMARY.md` - Race feature details
  - `VALIDATOR_QUICK_REFERENCE.md` - This file

## Quick Checks

### Check if script is working
```bash
python3 mission_config_validator.py --help
```

### View latest results
Open: https://docs.google.com/spreadsheets/d/1hph4x2MPemtTD8B8TSO8yjV2jH6XuM19CySTsujpFDw

Look for the most recent `validation_*` tab.
