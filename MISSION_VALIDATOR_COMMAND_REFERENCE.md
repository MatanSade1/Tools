# Mission Validator - Command Reference

## 🎯 Complete Command Format

```bash
python3 mission_config_validator.py \
  --live-ops-id <ID> \
  --feature missions \
  [--config-spreadsheet-id <SPREADSHEET_ID>] \
  [--start-date YYYY-MM-DD] \
  [--end-date YYYY-MM-DD] \
  [--days-back N]
```

---

## 📋 All Parameters

### Required Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `--live-ops-id` | Live ops campaign ID | `4253` |
| `--feature` | Feature to validate | `missions` |

### Optional Parameters

| Parameter | Description | Default | Example |
|-----------|-------------|---------|---------|
| `--config-spreadsheet-id` | Config spreadsheet ID | `1L94yMz3i...` | `1ABC123XYZ` |
| `--start-date` | Start date (YYYY-MM-DD) | Today | `2026-01-26` |
| `--end-date` | End date (YYYY-MM-DD) | Today | `2026-01-26` |
| `--days-back` | Days back from today | - | `7` |

**Note**: Use either `--start-date`/`--end-date` OR `--days-back`, not both.

---

## 🚀 Common Usage Examples

### 1. Basic - Today Only (Default Config)
```bash
python3 mission_config_validator.py --live-ops-id 4253 --feature missions
```

### 2. Specific Date Range
```bash
python3 mission_config_validator.py \
  --live-ops-id 4253 \
  --feature missions \
  --start-date 2026-01-26 \
  --end-date 2026-01-26
```

### 3. Last 7 Days
```bash
python3 mission_config_validator.py \
  --live-ops-id 4253 \
  --feature missions \
  --days-back 7
```

### 4. Custom Config Spreadsheet
```bash
python3 mission_config_validator.py \
  --live-ops-id 4253 \
  --feature missions \
  --config-spreadsheet-id 1L94yMz3iahaJdTCAE5v5NAPFfnLJ9DHVjlTWf11CIKM
```

### 5. Full Custom Command
```bash
python3 mission_config_validator.py \
  --live-ops-id 4253 \
  --feature missions \
  --config-spreadsheet-id 1ABC123XYZ456 \
  --start-date 2026-01-20 \
  --end-date 2026-01-26
```

---

## 🔍 What Gets Validated

```
1. Query ACTUAL user data (from BigQuery vmp_master_event_normalized)
   - Filtered by: live_ops_id, date range, version, countries
   
2. Calculate EXPECTED segments (from BigQuery segmentation_parameters)
   - Dynamic calculation based on user behavior
   
3. Load expected configurations (from Google Spreadsheet)
   - Spreadsheet contains config per segment
   
4. Compare ACTUAL vs EXPECTED
   - Segment match?
   - Configuration match? (8 positions × 4 fields)
   
5. Output results to new spreadsheet tab
```

---

## 📊 Output

**Spreadsheet**: https://docs.google.com/spreadsheets/d/1hph4x2MPemtTD8B8TSO8yjV2jH6XuM19CySTsujpFDw

**Format**:
- New tab with timestamp: `validation_YYYYMMDD_HHMMSS`
- Columns: `distinct_id`, `is_difference`, `difference_type`, `detailed_difference`

---

## 🛠️ Using the Run Script

The run script provides a convenient wrapper:

```bash
# Default (today, default config)
./run_mission_validator.sh --live-ops-id 4253 --feature missions

# With custom parameters
./run_mission_validator.sh \
  --live-ops-id 4253 \
  --feature missions \
  --days-back 7 \
  --config-spreadsheet-id 1ABC...
```

---

## 📖 Help Command

Get full help and all options:

```bash
python3 mission_config_validator.py --help
```

---

## ✅ Default Values

| Parameter | Default Value |
|-----------|---------------|
| `--start-date` | Today's date |
| `--end-date` | Today's date |
| `--config-spreadsheet-id` | `1L94yMz3iahaJdTCAE5v5NAPFfnLJ9DHVjlTWf11CIKM` |

---

## 🎯 Quick Copy-Paste Commands

### Today Only
```bash
python3 mission_config_validator.py --live-ops-id 4253 --feature missions
```

### Last Week
```bash
python3 mission_config_validator.py --live-ops-id 4253 --feature missions --days-back 7
```

### Specific Date (Today Example)
```bash
python3 mission_config_validator.py --live-ops-id 4253 --feature missions --start-date 2026-01-26 --end-date 2026-01-26
```

### With Custom Config
```bash
python3 mission_config_validator.py --live-ops-id 4253 --feature missions --config-spreadsheet-id 1L94yMz3iahaJdTCAE5v5NAPFfnLJ9DHVjlTWf11CIKM
```

---

## 🔗 Related Documentation

- **Full README**: [`MISSION_VALIDATION_README.md`](MISSION_VALIDATION_README.md)
- **V2 Changes**: [`MISSION_VALIDATOR_V2_CHANGES.md`](MISSION_VALIDATOR_V2_CHANGES.md)
- **Quick Start**: [`MISSION_VALIDATOR_QUICKSTART.md`](MISSION_VALIDATOR_QUICKSTART.md)
