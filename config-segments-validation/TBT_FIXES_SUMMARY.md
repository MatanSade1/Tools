# Time-Board-Tasks: Critical Fixes Summary

**Date:** January 27, 2026  
**Status:** ✅ Fixed and Validated

---

## 🐛 Issues Identified and Fixed

### Issue #1: Incorrect Cycle Filter Location ❌ → ✅

**Problem:**
```sql
-- WRONG: Looking for cycle inside JSON
AND JSON_EXTRACT_SCALAR(tbt_snapshot, '$.cycle') = '1'
```

**Root Cause:** The `cycle` column is a **top-level column** in the BigQuery schema, not inside the `tbt_snapshot` JSON.

**Fix:**
```sql
-- CORRECT: Use top-level column
AND cycle = 1
```

**Impact:** 
- **Before:** 0 users found
- **After:** 447 users found ✅

---

### Issue #2: Wrong Segment Field in active_segments ❌ → ✅

**Problem:**
```python
# WRONG: Using config_segment
actual_segment = segment_config.get('config_segment', '')
```

**Root Cause:** For Time-Board-Tasks, the actual segment is stored in `liveops_segment`, not `config_segment`.

**Example active_segments entry:**
```json
{
  "config_id": 616,
  "config_segment": "default",           ← NOT this
  "config_type": "TimedBoardTaskFeatureConfigData",
  "liveops_id": 4252,
  "liveops_segment": "timed_task_11"     ← USE this
}
```

**Fix:**
```python
# CORRECT: Use liveops_segment
actual_segment = segment_config.get('liveops_segment', '')
```

**Impact:**
- Now correctly extracts the actual segment from the `dynamic_configuration_loaded` event

---

## 📊 Validation Results After Fixes

### Test Configuration
- **Live Ops ID:** 4252
- **Date:** 2026-01-26
- **Feature:** time-board-tasks

### Results
- ✅ **Users found:** 447 (with cycle=1)
- ✅ **Expected segments matched:** 381 users
- ⚠️ **Missing expected segments:** 66 users (not in 'distinct_id_segmentation_list' tab)
- 📊 **Validation output:** https://docs.google.com/spreadsheets/d/1hph4x2MPemtTD8B8TSO8yjV2jH6XuM19CySTsujpFDw

---

## 🔍 How It Works Now (Correct Flow)

```
Step 1: Query timed_board_task_started events
├─ Filter: cycle = 1 (top-level column) ✅
├─ Filter: liveops_id from tbt_snapshot JSON
└─ Get: tbt_snapshot, res_timestamp

Step 2: Join with dynamic_configuration_loaded
├─ Condition: same distinct_id
├─ Condition: config event timestamp < tbt event timestamp
├─ Condition: within 7 days lookback
└─ Get: active_segments JSON

Step 3: Parse active_segments
├─ Find element where:
│  ├─ liveops_id matches (from tbt_snapshot)
│  └─ config_type = "TimedBoardTaskFeatureConfigData"
└─ Extract: liveops_segment ✅ (not config_segment)

Step 4: Compare
├─ Actual segment: from liveops_segment in active_segments
└─ Expected segment: from 'distinct_id_segmentation_list' tab
```

---

## 📝 Code Changes Made

### 1. Fixed Cycle Filter (Line ~95 in mission_config_validator.py)
```python
# BEFORE
AND JSON_EXTRACT_SCALAR({snapshot_field}, '$.cycle') = '1'

# AFTER
AND cycle = 1
```

### 2. Fixed Segment Extraction (Line ~225 in mission_config_validator.py)
```python
# BEFORE
actual_segment = segment_config.get('config_segment', '')

# AFTER
actual_segment = segment_config.get('liveops_segment', '')
```

---

## 📚 Updated Documentation

All documentation files have been updated to reflect these fixes:
- ✅ `TBT_ACTUAL_SEGMENT_LOGIC.md` - Updated to show `liveops_segment` usage
- ✅ `TBT_UPDATE_QUICK_REFERENCE.md` - Updated examples with correct field
- ✅ `TBT_QUERY_COMPARISON.md` - Updated SQL and Python code examples
- ✅ `TBT_FIXES_SUMMARY.md` - This document

---

## 🚀 Testing Commands

```bash
# Test with live_ops_id 4252
python3 mission_config_validator.py \
  --live-ops-id 4252 \
  --feature time-board-tasks \
  --start-date 2026-01-26 \
  --end-date 2026-01-26 \
  --config-spreadsheet-id 1b68uDDLuGGawiWWIARA5AvB1TU5Yrv1drIVDezznmmg

# Test with live_ops_id 4266
python3 mission_config_validator.py \
  --live-ops-id 4266 \
  --feature time-board-tasks \
  --days-back 2 \
  --config-spreadsheet-id 1b68uDDLuGGawiWWIARA5AvB1TU5Yrv1drIVDezznmmg
```

---

## 🎯 Key Learnings

1. **Always verify column locations** - Don't assume nested JSON, check the actual BigQuery schema
2. **Field naming matters** - `config_segment` vs `liveops_segment` have different meanings
3. **Feature-specific logic** - Time-Board-Tasks uses `liveops_segment`, other features may use different fields
4. **Test incrementally** - Fix one issue at a time and validate before moving to the next

---

## 🔗 Related Files

- `mission_config_validator.py` - Main validation script
- `TBT_ACTUAL_SEGMENT_LOGIC.md` - Detailed logic explanation
- `TBT_UPDATE_QUICK_REFERENCE.md` - Quick reference guide
- `TBT_QUERY_COMPARISON.md` - Before/after SQL comparison

---

**Commits:**
- Initial implementation: `5d0c442`
- Cycle filter fix: `[pending]`
- liveops_segment fix: `[pending]`

---

**Author:** Data Validation Team  
**Reviewed:** January 27, 2026
