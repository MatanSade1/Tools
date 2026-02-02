# Mission Validator V2 - Changes Summary

## 🎉 What Changed

The validator has been updated to be more **robust and production-ready** by replacing hardcoded spreadsheets with **dynamic BigQuery queries**.

### ✅ Version 2 Improvements

| Aspect | V1 (Old) | V2 (New) |
|--------|----------|----------|
| **User Data Source** | Static spreadsheet | BigQuery query with date filters |
| **Segment Calculation** | Static table (`mission_segmentation_test`) | Dynamic calculation using `segmentation_parameters` |
| **Date Range** | Fixed data in spreadsheet | Flexible date range parameters |
| **Live Ops ID** | Hardcoded | Command-line parameter |
| **Data Freshness** | Manual spreadsheet updates | Real-time BigQuery data |

---

## 📊 New Data Sources

### 1. User Data (ACTUAL configurations)
**Old**: Google Spreadsheet  
**New**: BigQuery Query

```sql
SELECT distinct_id, missions_snapshot, event_time
FROM `yotam-395120.peerplay.vmp_master_event_normalized`
WHERE date BETWEEN start_date AND end_date
  AND mp_event_name = 'impression_missions_popup'
  AND live_ops_id = {parameter}
  -- + filters for version, countries, fraudsters
```

### 2. Segment Calculation (EXPECTED segments)
**Old**: Static `mission_segmentation_test` table  
**New**: Dynamic segmentation logic

```sql
-- Calculates segments based on:
- median_14_active_days_total_credits_spend
- credit_spend_active_days
- last_chapter

-- Segments: mission_1, mission_2, above_chapter_12, 
--           mission_1_chapter_12, mission_2_chapter_12, default
```

### 3. Expected Configurations
**Unchanged**: Still uses config spreadsheet with segment definitions

---

## 🚀 How to Use V2

### Basic Usage (Today Only)
```bash
python3 mission_config_validator.py --live-ops-id 4253 --feature missions
```

### Specific Date
```bash
python3 mission_config_validator.py --live-ops-id 4253 --start-date 2026-01-26 --end-date 2026-01-26 --feature missions
```

### Last N Days
```bash
python3 mission_config_validator.py --live-ops-id 4253 --days-back 7 --feature missions
```

### Custom Config Spreadsheet
```bash
python3 mission_config_validator.py --live-ops-id 4253 --feature missions \
  --config-spreadsheet-id 1ABC123XYZ456
```

### Using the Run Script
```bash
# Default (today, live-ops-id 4253, feature missions)
./run_mission_validator.sh

# Custom parameters
./run_mission_validator.sh --live-ops-id 4253 --days-back 7 --feature missions
```

---

## 📋 Command-Line Arguments

| Argument | Required | Description | Example |
|----------|----------|-------------|---------|
| `--live-ops-id` | ✅ Yes | Live ops campaign ID | `4253` |
| `--feature` | ✅ Yes | Feature to validate | `missions` |
| `--config-spreadsheet-id` | ⚪ No | Config spreadsheet ID | `1L94yMz3i...` |
| `--start-date` | ⚪ No | Start date (YYYY-MM-DD) | `2026-01-26` |
| `--end-date` | ⚪ No | End date (YYYY-MM-DD) | `2026-01-26` |
| `--days-back` | ⚪ No | Days back from today | `7` |

**Notes**: 
- If no dates specified, defaults to today only
- Currently only `missions` feature is supported (extensible for future features)
- Config spreadsheet defaults to `1L94yMz3iahaJdTCAE5v5NAPFfnLJ9DHVjlTWf11CIKM` (missions config)

---

## 🔍 What Gets Validated

### Flow:
```
1. Query ACTUAL user data from BigQuery
   ↓
2. Calculate EXPECTED segments dynamically
   ↓
3. Compare ACTUAL vs EXPECTED
   ↓
4. Write results to spreadsheet
```

### Validation Logic:
1. **Segment Match**: Does actual segment = expected segment?
2. **Config Match**: Do all 8 positions × 4 fields match?

---

## 📊 Example Run

```bash
$ python3 mission_config_validator.py --live-ops-id 4253 --start-date 2026-01-26 --end-date 2026-01-26 --feature missions

================================================================================
Mission Configuration Validator - Feature: MISSIONS
================================================================================

📖 Querying user data from BigQuery...
   Live Ops ID: 4253
   Date Range: 2026-01-26 to 2026-01-26
   Running query...
✅ Fetched 239 users from BigQuery
✅ Parsed 239 users with mission data

📖 Reading expected configurations from spreadsheet...
✅ Read 6 segment configurations

🔍 Calculating expected segments for 239 users...
✅ Calculated segments for 237 users
⚠️  2 users not in segmentation_parameters or don't meet criteria

🔍 Validating 239 users...
✅ Validation complete!
   Total users: 239
   Differences found: 2
   Perfect matches (actual = expected): 237

📝 Writing 239 results to output spreadsheet...
✅ Created new tab: validation_20260126_161905

================================================================================
✅ Validation complete! Check the output spreadsheet for results.
================================================================================
```

---

## 💾 Output

**Same as V1** - Results written to spreadsheet:
- New tab with timestamp
- Columns: `distinct_id`, `is_difference`, `difference_type`, `detailed_difference`
- URL: https://docs.google.com/spreadsheets/d/1hph4x2MPemtTD8B8TSO8yjV2jH6XuM19CySTsujpFDw

---

## 🔧 Filters Applied

The validator automatically filters out:
- ❌ Old app versions (< 0.378)
- ❌ Test countries (UA, IL, AM)
- ❌ Potential fraudsters
- ❌ Users with state loss issues

---

## 🆚 V1 vs V2 Comparison

### V1 Limitations:
- ❌ Required manual spreadsheet updates
- ❌ Fixed to one spreadsheet dataset
- ❌ Couldn't filter by date range
- ❌ Hardcoded live ops ID
- ❌ Static segment assignments

### V2 Advantages:
- ✅ Real-time BigQuery data
- ✅ Flexible date ranges
- ✅ Parameterized live ops ID
- ✅ Dynamic segment calculation
- ✅ More users validated (239 vs 162 in V1)
- ✅ Production-ready

---

## 🎯 Key Benefits

1. **Real-time Data**: Always validates against latest data
2. **Flexible**: Run for any date range or live ops campaign
3. **Accurate**: Dynamic segmentation matches production logic
4. **Scalable**: Can handle more users efficiently
5. **Auditable**: Clear parameters in output tab name

---

## 📝 Notes

### "NOT FOUND" Users
Users marked as "Expected (BigQuery): NOT FOUND" are:
- Present in impression events
- NOT in `segmentation_parameters` table
- OR don't meet segmentation criteria (active days < 1, inactive > 45 days)

This is expected for:
- Very new users
- Inactive users
- Users outside segmentation scope

---

## 🚀 Quick Start

```bash
# 1. Run for today
./run_mission_validator.sh --live-ops-id 4253 --feature missions

# 2. Run for last week
./run_mission_validator.sh --live-ops-id 4253 --feature missions --days-back 7

# 3. Run for specific dates
./run_mission_validator.sh --live-ops-id 4253 --feature missions \
  --start-date 2026-01-20 --end-date 2026-01-26
```

---

## 📚 Documentation

- **Full README**: [`MISSION_VALIDATION_README.md`](MISSION_VALIDATION_README.md)
- **Quick Start**: [`MISSION_VALIDATOR_QUICKSTART.md`](MISSION_VALIDATOR_QUICKSTART.md)
- **V1 Summary**: [`MISSION_VALIDATOR_SUMMARY.md`](MISSION_VALIDATOR_SUMMARY.md)
