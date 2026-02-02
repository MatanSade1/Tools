# Race Validation Logic - Detailed Explanation

## Overview
The race validation compares **actual user configuration** (from events) against **expected configuration** (from spreadsheet) for users who participated in a race live ops.

---

## Data Flow

### 1. ACTUAL DATA (What Users Actually Received)

**Source**: BigQuery event `impression_race_popup`  
**Table**: `yotam-395120.peerplay.vmp_master_event_normalized`  
**Field**: `race_snapshot` (JSON column)  
**Important Filter**: Only events with `race_board_level = 1` are included

**Example race_snapshot**:
```json
{
  "config_id": 14,
  "config_segment": "Group1",
  "current_level": 2,
  "liveops_id": 4230,
  "liveops_segment": "default",
  "place_rewards": [
    {
      "item_1_name": "credits",
      "item_2_name": "Album Pack 1",
      "item_id_1": 1,
      "item_id_2": 60201,
      "item_quantity_1": 25,
      "item_quantity_2": 1,
      "place": 1
    },
    {
      "item_1_name": "credits",
      "item_id_1": 1,
      "item_quantity_1": 17,
      "place": 2
    },
    {
      "item_1_name": "credits",
      "item_id_1": 1,
      "item_quantity_1": 12,
      "place": 3
    }
  ],
  "target_points": 45
}
```

**Parsed into**:
```python
{
  'distinct_id': '...',
  'config_segment': 'Group1',           # ← ACTUAL segment user got
  'current_level': 2,                    # ← CRITICAL: determines which SubConfig to compare
  'target_points': 45,                   # ← ACTUAL target points
  'place_1_item_id_1': 1,               # ← ACTUAL place 1, item 1 ID
  'place_1_item_id_2': 60201,           # ← ACTUAL place 1, item 2 ID
  'place_1_item_quantity_1': 25,        # ← ACTUAL place 1, item 1 quantity
  'place_1_item_quantity_2': 1,         # ← ACTUAL place 1, item 2 quantity
  'place_2_item_id_1': 1,               # ← ACTUAL place 2, item 1 ID
  'place_2_item_quantity_1': 17,        # ← ACTUAL place 2, item 1 quantity
  'place_3_item_id_1': 1,               # ← ACTUAL place 3, item 1 ID
  'place_3_item_quantity_1': 12,        # ← ACTUAL place 3, item 1 quantity
}
```

---

### 2. EXPECTED SEGMENT (What Segment User Should Have)

**Source**: Google Sheets  
**Tab**: `'list for liveops'`  
**Columns**:
- Column A: `SegmentId` (the expected segment, e.g., "Group1", "Group2")
- Column C: `UserId` (the distinct_id)

**Logic**: 
- Read all rows from 'list for liveops' tab
- Match `distinct_id` from actual data to `UserId` in spreadsheet
- Get the corresponding `SegmentId` as expected segment

**Example**:
| SegmentId | ... | UserId           |
|-----------|-----|------------------|
| Group1    | ... | abc123def456     |
| Group2    | ... | xyz789uvw012     |

---

### 3. EXPECTED CONFIGURATION (What Config the Segment Should Have)

**Source**: Google Sheets (same spreadsheet as segments)  
**Tab**: `'Full config to upload'`  
**Columns**: Configuration by segment

**Column Format**: `SubConfig1<field>`

**IMPORTANT**: Race configuration **always** uses `SubConfig1*` columns, regardless of the user's `current_level` in the event.

| SegmentId | SubConfig1TargetPoints | SubConfig1Place1Reward1Id | SubConfig1Place1Reward2Id | SubConfig1Place1Reward1Count | SubConfig1Place1Reward2Count | ... |
|-----------|------------------------|---------------------------|---------------------------|------------------------------|------------------------------|-----|
| Group1    | 45                     | 1                         | 60201                     | 25                           | 1                            | ... |
| Group2    | 60                     | 1                         | 60202                     | 30                           | 1                            | ... |

**Key Point**: The `current_level` from the event indicates user progression through the race, but does NOT affect which configuration columns we compare against. We **always** compare against `SubConfig1*` columns.

---

## Validation Process

### Step 1: Segment Validation
```python
actual_segment = user_row['config_segment']  # From race_snapshot in event
expected_segment = segments_map[distinct_id]  # From 'list for liveops' tab

if actual_segment != expected_segment:
    → Flag as segment difference
```

### Step 2: Configuration Validation (if segment matches)

**Only runs if segment validation passed!**

The validation **always** compares against `SubConfig1*` columns, regardless of `current_level`:

```python
# Race always uses SubConfig1 for comparison
# current_level indicates progression but doesn't affect which config to compare

# 1. Compare target points
actual_target = user_row['target_points']  # e.g., 45
expected_target = config_row['SubConfig1TargetPoints']  # e.g., 45

# 2. Compare place rewards (3 places, up to 2 items each)
for place in [1, 2, 3]:
    for item_num in [1, 2]:
        # Compare item IDs
        actual_id = user_row[f'place_{place}_item_id_{item_num}']
        expected_id = config_row[f'SubConfig1Place{place}Reward{item_num}Id']
        
        # Compare item quantities
        actual_count = user_row[f'place_{place}_item_quantity_{item_num}']
        expected_count = config_row[f'SubConfig1Place{place}Reward{item_num}Count']
```

---

## Complete Comparison Matrix

For a user with `config_segment="Group1"` (regardless of `current_level`):

| Field | Actual Data Source | Expected Data Source | Comparison |
|-------|-------------------|---------------------|------------|
| **Segment** | `race_snapshot.config_segment` | 'list for liveops' tab, Column A (SegmentId) | String match |
| **Target Points** | `race_snapshot.target_points` | 'Full config to upload' tab, `SubConfig1TargetPoints` column | Numeric match |
| **Place 1, Item 1 ID** | `race_snapshot.place_rewards[0].item_id_1` | `SubConfig1Place1Reward1Id` | Numeric match |
| **Place 1, Item 2 ID** | `race_snapshot.place_rewards[0].item_id_2` | `SubConfig1Place1Reward2Id` | Numeric match |
| **Place 1, Item 1 Count** | `race_snapshot.place_rewards[0].item_quantity_1` | `SubConfig1Place1Reward1Count` | Numeric match |
| **Place 1, Item 2 Count** | `race_snapshot.place_rewards[0].item_quantity_2` | `SubConfig1Place1Reward2Count` | Numeric match |
| **Place 2, Item 1 ID** | `race_snapshot.place_rewards[1].item_id_1` | `SubConfig1Place2Reward1Id` | Numeric match |
| **Place 2, Item 2 ID** | `race_snapshot.place_rewards[1].item_id_2` | `SubConfig1Place2Reward2Id` | Numeric match |
| **Place 2, Item 1 Count** | `race_snapshot.place_rewards[1].item_quantity_1` | `SubConfig1Place2Reward1Count` | Numeric match |
| **Place 2, Item 2 Count** | `race_snapshot.place_rewards[1].item_quantity_2` | `SubConfig1Place2Reward2Count` | Numeric match |
| **Place 3, Item 1 ID** | `race_snapshot.place_rewards[2].item_id_1` | `SubConfig1Place3Reward1Id` | Numeric match |
| **Place 3, Item 2 ID** | `race_snapshot.place_rewards[2].item_id_2` | `SubConfig1Place3Reward2Id` | Numeric match |
| **Place 3, Item 1 Count** | `race_snapshot.place_rewards[2].item_quantity_1` | `SubConfig1Place3Reward1Count` | Numeric match |
| **Place 3, Item 2 Count** | `race_snapshot.place_rewards[2].item_quantity_2` | `SubConfig1Place3Reward2Count` | Numeric match |

---

## Key Points to Understand

### 1. Fixed SubConfig1 Comparison
- **IMPORTANT**: Race validation **always** compares against `SubConfig1*` columns
- The `current_level` field from the event is informational only (shows user progression)
- It does NOT affect which configuration columns we compare against
- All users, regardless of their level, are compared against `SubConfig1*`

### 2. Two-Stage Validation
1. **Segment Compare**: Does actual segment match expected segment?
2. **Config Compare**: Do the configuration values match? (only checked if segment matches)

### 3. Data Sources Summary
- **Actual Data**: BigQuery `impression_race_popup` event → `race_snapshot` JSON
- **Expected Segment**: Google Sheets 'list for liveops' tab (Column A: SegmentId, Column C: UserId)
- **Expected Config**: Google Sheets 'Full config to upload' tab (SubConfig columns by segment)

### 4. Potential Issues
- ❌ **Missing segment assignment**: User's `distinct_id` not found in 'list for liveops' → shows as "NOT FOUND"
- ❌ **Wrong segment**: User got "Group2" but should have "Group1" → segment difference
- ❌ **Wrong config for correct segment**: User in correct segment but rewards don't match → config difference
- ❌ **Missing SubConfig1 columns**: Config spreadsheet doesn't have SubConfig1* columns → config not found

---

## Example Scenario

### User: abc123def456

**Actual Data (from event)**:
- config_segment: "Group1"
- current_level: 2  ← (informational only, doesn't affect comparison)
- target_points: 45
- place_1_item_id_1: 1
- place_1_item_quantity_1: 25

**Expected Segment (from 'list for liveops')**:
- SegmentId: "Group1" ✅ Match!

**Expected Config (from 'Full config to upload', Group1 row)**:
- SubConfig1TargetPoints: 45 ✅ Match!
- SubConfig1Place1Reward1Id: 1 ✅ Match!
- SubConfig1Place1Reward1Count: 25 ✅ Match!

**Result**: ✅ Perfect match - no differences

---

## How to Debug Issues

### If you see many "NOT FOUND" differences:
→ Check that 'list for liveops' tab has all the distinct_ids from your actual data

### If you see segment differences:
→ Users are getting assigned to wrong segments - check segmentation logic

### If you see config differences:
→ Check that:
1. SubConfig columns for the correct level exist
2. Column names match exactly (case-insensitive matching is applied)
3. Values in the config spreadsheet are correct

### To manually verify a user:
1. Find their distinct_id in validation output
2. Look up their race_snapshot in BigQuery
3. Find them in 'list for liveops' tab to see their expected segment
4. Look up their segment in 'Full config to upload' tab
5. Compare SubConfig1* columns (always SubConfig1, regardless of user's level) against their actual values
