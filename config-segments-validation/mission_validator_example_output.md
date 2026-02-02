# Mission Validator - Example Output

This document shows example outputs from the validator to help you understand the results.

## Example 1: Perfect Match ✅

**Input:**
- User's `config_segment`: `premium`
- BigQuery `segment_name`: `premium`
- All 8 positions match expected configuration

**Output:**
```
distinct_id: user_12345
is_difference: no
difference_type: 
detailed_difference: 
```

**Interpretation:** Everything is correct! ✅

---

## Example 2: Segment Mismatch ❌

**Input:**
- User's `config_segment`: `premium`
- BigQuery `segment_name`: `basic`

**Output:**
```
distinct_id: user_67890
is_difference: yes
difference_type: segment
detailed_difference: Segment mismatch - Expected: premium, BigQuery: basic
```

**Interpretation:** User is assigned to the wrong segment in BigQuery. The configuration comparison is skipped because the segment doesn't match.

**Action Required:** Update the user's segment in BigQuery or in the user spreadsheet.

---

## Example 3: User Not Found in BigQuery ❌

**Input:**
- User's `config_segment`: `premium`
- BigQuery: User not found

**Output:**
```
distinct_id: user_99999
is_difference: yes
difference_type: segment
detailed_difference: User not found in BigQuery. Expected segment: premium
```

**Interpretation:** The user exists in the user spreadsheet but not in the BigQuery `mission_segmentation_test` table.

**Action Required:** Add the user to BigQuery or verify the distinct_id is correct.

---

## Example 4: Configuration Mismatch (Single Field) ❌

**Input:**
- Segment matches ✅
- Position 1, `item_id`: expected=`coin`, actual=`gem`
- All other fields match

**Output:**
```
distinct_id: user_11111
is_difference: yes
difference_type: config
detailed_difference: Position 1: item_id: expected=coin, actual=gem
```

**Interpretation:** Segment is correct, but the user has a different item_id in position 1 than expected.

**Action Required:** Update the user's configuration or the expected configuration for this segment.

---

## Example 5: Configuration Mismatch (Multiple Fields) ❌

**Input:**
- Segment matches ✅
- Position 1:
  - `item_id`: expected=`100`, actual=`200`
  - `mission_type`: expected=`daily`, actual=`weekly`
- Position 3:
  - `target_amount`: expected=`50`, actual=`75`

**Output:**
```
distinct_id: user_22222
is_difference: yes
difference_type: config
detailed_difference: Position 1: item_id: expected=100, actual=200; mission_type: expected=daily, actual=weekly | Position 3: target_amount: expected=50, actual=75
```

**Interpretation:** Segment is correct, but multiple configuration fields don't match. The output shows each position with mismatches separated by `|`.

**Action Required:** Review and fix the configuration for this user in positions 1 and 3.

---

## Example 6: Configuration Mismatch (Missing Value) ❌

**Input:**
- Segment matches ✅
- Position 2, `item_quantity`: expected=`5`, actual=`NULL` (missing)

**Output:**
```
distinct_id: user_33333
is_difference: yes
difference_type: config
detailed_difference: Position 2: item_quantity: expected=5, actual=NULL
```

**Interpretation:** The user is missing a required configuration value in position 2.

**Action Required:** Add the missing item_quantity value for this user.

---

## Example 7: No Expected Configuration for Segment ❌

**Input:**
- Segment matches ✅
- User's segment: `test_segment_99`
- Config spreadsheet doesn't have this segment

**Output:**
```
distinct_id: user_44444
is_difference: yes
difference_type: config
detailed_difference: No expected configuration found for segment: test_segment_99
```

**Interpretation:** The user has a valid segment assignment in BigQuery, but there's no expected configuration defined for this segment in the config spreadsheet.

**Action Required:** Add the expected configuration for this segment to the config spreadsheet.

---

## Full Output Example

Here's what a complete validation run might look like in the output spreadsheet:

| distinct_id | is_difference | difference_type | detailed_difference |
|-------------|---------------|-----------------|---------------------|
| user_001 | no | | |
| user_002 | yes | segment | Segment mismatch - Expected: premium, BigQuery: basic |
| user_003 | no | | |
| user_004 | yes | config | Position 1: item_id: expected=coin, actual=gem |
| user_005 | yes | segment | User not found in BigQuery. Expected segment: premium |
| user_006 | no | | |
| user_007 | yes | config | Position 1: item_id: expected=100, actual=200; mission_type: expected=daily, actual=weekly \| Position 3: target_amount: expected=50, actual=75 |
| user_008 | no | | |
| user_009 | yes | config | Position 2: item_quantity: expected=5, actual=NULL |
| user_010 | no | | |

---

## Understanding the Output Columns

### `distinct_id`
The user identifier from the user spreadsheet.

### `is_difference`
- **`yes`**: Differences were found (segment or configuration mismatch)
- **`no`**: Everything matches perfectly

### `difference_type`
- **`segment`**: The segment in BigQuery doesn't match the expected segment, OR the user wasn't found in BigQuery
- **`config`**: The segment matches, but the configuration values don't match
- **Empty**: No differences (only when `is_difference` is `no`)

### `detailed_difference`
A human-readable description of what doesn't match. Format varies by type:

**For segment differences:**
- `Segment mismatch - Expected: {expected}, BigQuery: {actual}`
- `User not found in BigQuery. Expected segment: {expected}`

**For config differences:**
- `Position {N}: {field}: expected={expected_value}, actual={actual_value}`
- Multiple differences are separated by `; ` within a position
- Multiple positions are separated by ` | `

---

## How to Use the Output

### 1. Filter by `is_difference = yes`
Focus on rows with differences to identify issues.

### 2. Group by `difference_type`
- Handle all **segment** issues first (fix segment assignments)
- Then handle **config** issues (fix configuration values)

### 3. Parse `detailed_difference`
- Look for position numbers to identify which mission positions have issues
- Look for field names to identify what specific values need fixing
- Check for NULL values (missing data)

### 4. Take Action
Based on the difference type:
- **Segment issues**: Update BigQuery or the user spreadsheet
- **Config issues**: Update the user's configuration or the expected segment configuration

### 5. Re-run Validation
After making fixes, run the validator again to verify the issues are resolved.

---

## Tips

1. **Sort by difference_type** to batch-fix similar issues
2. **Export to CSV** for easier filtering and analysis
3. **Compare with previous runs** to track progress
4. **Search for specific fields** (e.g., "item_id") to find all issues with that field
5. **Check for patterns** - if many users have the same issue, it might be a data source problem

---

## Questions?

See the full documentation in [`MISSION_VALIDATION_README.md`](MISSION_VALIDATION_README.md).
