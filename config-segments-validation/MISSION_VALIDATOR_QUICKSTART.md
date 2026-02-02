# 🚀 Mission Validator - Quick Start Guide

## What You Need to Know

This tool validates mission configurations for users by comparing data from:
- 📊 **2 Google Spreadsheets** (user data + expected configs)
- 🗄️ **1 BigQuery Table** (segment assignments)

Results are written to → 📝 **Output Spreadsheet** (new tab each run)

---

## 🎯 How to Run

### Step 1: Test Your Setup (First Time Only)
```bash
cd /Users/matansade/Tools
python3 test_mission_validator_setup.py
```

**What it checks:**
- ✅ Python dependencies
- ✅ GCP authentication
- ✅ Spreadsheet access
- ✅ BigQuery access

### Step 2: Run the Validator
```bash
./run_mission_validator.sh
```

**OR**

```bash
python3 mission_config_validator.py
```

### Step 3: Check Results
Open the output spreadsheet and look for the new tab:
- **Tab name**: `validation_YYYYMMDD_HHMMSS`
- **URL**: https://docs.google.com/spreadsheets/d/1hph4x2MPemtTD8B8TSO8yjV2jH6XuM19CySTsujpFDw

---

## 📊 What Gets Validated

### Test 1: Segment Validation
```
User Spreadsheet (config_segment) 
    ↕ 
BigQuery (segment_name)
```
✅ Pass → Proceed to Test 2  
❌ Fail → Report segment difference

### Test 2: Configuration Validation
```
For each of 8 positions, compare 4 fields:
- item_id
- item_quantity  
- mission_type
- target_amount

User Actual Values ↔ Expected Values (from segment config)
```
✅ Pass → No difference  
❌ Fail → Report config difference

---

## 📋 Output Format

Each row in the results tab shows:

| distinct_id | is_difference | difference_type | detailed_difference |
|-------------|---------------|-----------------|---------------------|
| user_123 | **yes** | segment | Segment mismatch - Expected: premium, BigQuery: basic |
| user_456 | **yes** | config | Position 1: item_id: expected=100, actual=200 |
| user_789 | **no** | | |

---

## 🛠️ First-Time Setup

### Install Dependencies
```bash
pip3 install -r requirements.txt
```

### Configure GCP Authentication
```bash
gcloud auth application-default login
```

### Verify Setup
```bash
python3 test_mission_validator_setup.py
```

---

## 🐛 Common Issues & Fixes

### ❌ "ModuleNotFoundError: No module named 'pandas'"
```bash
pip3 install -r requirements.txt
```

### ❌ "Could not authenticate with GCP"
```bash
gcloud auth application-default login
```

### ❌ "Requested entity was not found"
- Check spreadsheet sharing permissions
- Verify you're using the correct Google account

### ❌ "BigQuery access denied"
- Verify BigQuery permissions to `yotam-395120.peerplay`
- Check with team admin if needed

---

## 📁 Files in This Tool

| File | Purpose |
|------|---------|
| `mission_config_validator.py` | Main validation script |
| `test_mission_validator_setup.py` | Setup verification |
| `run_mission_validator.sh` | Convenience run script |
| `MISSION_VALIDATION_README.md` | Full documentation |
| `MISSION_VALIDATOR_SUMMARY.md` | Build summary |
| `MISSION_VALIDATOR_QUICKSTART.md` | This file |

---

## 🎯 Data Sources

### Input Spreadsheets
1. **User Data**: `1YZ-7pqKmYb43UnSXYneZT20elkcc1UTb9hDI4tjUhio`
2. **Config Data**: `1L94yMz3iahaJdTCAE5v5NAPFfnLJ9DHVjlTWf11CIKM`

### BigQuery
- **Table**: `yotam-395120.peerplay.mission_segmentation_test`

### Output
- **Spreadsheet**: `1hph4x2MPemtTD8B8TSO8yjV2jH6XuM19CySTsujpFDw`

---

## ✨ That's It!

You're ready to validate mission configurations. Just run:

```bash
./run_mission_validator.sh
```

For detailed documentation, see [`MISSION_VALIDATION_README.md`](MISSION_VALIDATION_README.md).
