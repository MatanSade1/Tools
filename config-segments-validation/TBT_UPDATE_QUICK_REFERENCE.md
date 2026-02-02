# Time-Board-Tasks Update: Quick Reference

## 🔄 What Changed?

### Before ❌
```
timed_board_task_started event
└─ tbt_snapshot
   └─ config_segment: "default" ← Used this as actual segment
```

### After ✅
```
1. timed_board_task_started (cycle=1)
   └─ liveops_id: 4266

2. ↓ Find most recent before TBT event

3. dynamic_configuration_loaded
   └─ active_segments: [...]
      └─ Find where liveops_id=4266 AND config_type="TimedBoardTaskFeatureConfigData"
         └─ config_segment: "timed_task_11" ← Use this as actual segment
```

---

## 🎯 Two Key Changes

### Change #1: Only Cycle 1
```sql
-- OLD: Any cycle
WHERE mp_event_name = 'timed_board_task_started'

-- NEW: Only first cycle
WHERE mp_event_name = 'timed_board_task_started'
  AND JSON_EXTRACT_SCALAR(tbt_snapshot, '$.cycle') = '1'
```

### Change #2: Actual Segment from Config Event
```python
# OLD: From tbt_snapshot
actual_segment = tbt_snapshot.get('config_segment')

# NEW: From active_segments in dynamic_configuration_loaded
active_segments = parse_json(config_event.active_segments)
for seg in active_segments:
    if seg['liveops_id'] == liveops_id and 
       seg['config_type'] == 'TimedBoardTaskFeatureConfigData':
        actual_segment = seg['liveops_segment']  # ← Use liveops_segment
```

---

## 📋 Example Scenario

**User:** `67f5a8b3c902d14e2a1f9c4d`  
**Date:** `2026-01-26`

### Step-by-Step Flow:

```
1. User fires: timed_board_task_started
   - cycle: 1
   - liveops_id: 4266
   - timestamp: 2026-01-26 14:30:00

2. Query finds: dynamic_configuration_loaded (most recent before 14:30:00)
   - timestamp: 2026-01-26 14:25:15
   - active_segments: [
       {"config_type": "FirstTimeOffer", ...},
       {"config_type": "TimedBoardTaskFeatureConfigData", 
        "liveops_id": 4266,
        "config_segment": "default",
        "liveops_segment": "timed_task_11"},  ← MATCH! Use liveops_segment
       {"config_type": "RaceConfigData", ...}
     ]

3. Extract actual segment: "timed_task_11" (from liveops_segment)

4. Compare with expected segment from "distinct_id_segmentation_list" tab
```

---

## 🧪 Testing

```bash
# Test TBT validation with new logic
python3 mission_config_validator.py \
  --live-ops-id 4266 \
  --feature time-board-tasks \
  --days-back 2 \
  --config-spreadsheet-id 1b68uDDLuGGawiWWIARA5AvB1TU5Yrv1drIVDezznmmg
```

---

## 📚 Documentation

- **Full Details:** `TBT_ACTUAL_SEGMENT_LOGIC.md`
- **Update Summary:** `TBT_VALIDATION_UPDATE_SUMMARY.md`
- **GitHub:** https://github.com/PeerPlayGames/pp-data-tools/tree/main/config-segments-validation

---

## ⚡ Quick Facts

| Aspect | Value |
|--------|-------|
| **Cycle Filtered** | `cycle=1` only |
| **Config Event** | `dynamic_configuration_loaded` |
| **Lookback Window** | 7 days before TBT event |
| **Match Criteria** | `liveops_id` + `config_type` |
| **Config Type** | `"TimedBoardTaskFeatureConfigData"` |

---

**Updated:** January 27, 2026  
**Commit:** `5d0c442`
