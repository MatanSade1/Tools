# Time-Board-Tasks Validation Update Summary

**Date:** January 27, 2026  
**Feature:** Time-Board-Tasks (TBT)  
**Status:** ✅ Complete & Pushed to GitHub

---

## 🎯 Changes Made

### 1. Filter for Cycle = 1 Only
**Previous:** Validated all `timed_board_task_started` events regardless of cycle.  
**Updated:** Now only validates events where `cycle=1` (the first cycle).

**Impact:** More accurate validation by focusing on the initial configuration shown to users.

### 2. New Actual Segment Source
**Previous:** Actual segment was extracted from `config_segment` in `tbt_snapshot`.  
**Updated:** Actual segment is now extracted from `active_segments` parameter in the most recent `dynamic_configuration_loaded` event prior to the TBT event.

**Why?** The `dynamic_configuration_loaded` event reflects the exact configuration the client received, providing a more accurate source of truth.

---

## 🔍 How It Works Now

### Step 1: Query TBT Events with Cycle = 1
```sql
SELECT distinct_id, tbt_snapshot, res_timestamp
FROM vmp_master_event_normalized
WHERE mp_event_name = 'timed_board_task_started'
  AND JSON_EXTRACT_SCALAR(tbt_snapshot, '$.cycle') = '1'
  AND JSON_EXTRACT_SCALAR(tbt_snapshot, '$.liveops_id') = '<live_ops_id>'
```

### Step 2: Find Most Recent `dynamic_configuration_loaded` Event
```sql
LEFT JOIN dynamic_configuration_loaded cfg
  ON tbt.distinct_id = cfg.distinct_id
  AND cfg.res_timestamp < tbt.res_timestamp
  AND cfg.date >= DATE_SUB(start_date, INTERVAL 7 DAY)
```

### Step 3: Parse `active_segments` JSON Array
Example `active_segments`:
```json
[
  {
    "config_id": 616,
    "config_segment": "timed_task_11",
    "config_type": "TimedBoardTaskFeatureConfigData",
    "liveops_id": 4266,
    "liveops_segment": "timed_task_11"
  },
  ...other configs...
]
```

### Step 4: Match by `liveops_id` and `config_type`
```python
for segment_config in active_segments:
    if (segment_config.get('liveops_id') == liveops_id_from_tbt and 
        segment_config.get('config_type') == 'TimedBoardTaskFeatureConfigData'):
        actual_segment = segment_config.get('config_segment')
        break
```

---

## 📝 Files Updated

1. **`mission_config_validator.py`**
   - Lines 82-123: Updated BigQuery query with CTE for config events
   - Lines 200-234: Added logic to parse `active_segments` and extract actual segment

2. **New Documentation**
   - `TBT_ACTUAL_SEGMENT_LOGIC.md`: Comprehensive explanation of the new logic

3. **Shared Utilities**
   - `shared/slack_client.py`: Added to GitHub repo

---

## 🚀 Testing

### Test Command
```bash
python3 mission_config_validator.py \
  --live-ops-id 4266 \
  --feature time-board-tasks \
  --days-back 2 \
  --config-spreadsheet-id 1b68uDDLuGGawiWWIARA5AvB1TU5Yrv1drIVDezznmmg
```

### Expected Behavior
- Only events with `cycle=1` are validated
- Actual segment is pulled from `dynamic_configuration_loaded` event
- If no matching config event is found, a warning is logged

---

## 🔗 GitHub

**Repository:** https://github.com/PeerPlayGames/pp-data-tools  
**Directory:** `config-segments-validation/`  
**Commit:** `5d0c442` - "feat: Update TBT validation to get actual segment from dynamic_configuration_loaded event"

---

## 📊 Comparison: Actual Segment Source by Feature

| Feature | Actual Segment Source | Event Used |
|---------|----------------------|------------|
| **Missions** | `config_segment` in `missions_snapshot` | `impression_missions_popup` |
| **Race** | Pre-assigned in "list for liveops" tab | `impression_race_popup` (level 1) |
| **Time-Board-Tasks** | `config_segment` in `active_segments` | `dynamic_configuration_loaded` |

---

## ✅ Validation Checks (Unchanged)

The following validation checks remain the same:

1. **Segment Match**: Expected segment vs actual segment
2. **Task ID**: `task_id` (event) = `Item1Id` (config)
3. **Item IDs**: `item_id_1/2/3` (event) exist in `Reward1-5Id` (config)
4. **Item Quantities**: `item_quantity_1` (event) exists in `Reward1-5Count` (config)

---

## 🎓 Key Learnings

1. **Client-side Truth**: `dynamic_configuration_loaded` provides the most accurate representation of what the client actually received.
2. **Cycle Filtering**: Focusing on `cycle=1` ensures we're validating the initial user experience.
3. **JSON Parsing**: Robust handling of nested JSON structures is essential for extracting configuration data.

---

## 📞 Contact

For questions or issues with this update, contact the data team.
