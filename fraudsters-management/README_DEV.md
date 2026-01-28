# Fraudsters Management DEV/LOCAL Version

This is the development/local version of the fraudsters management process. It writes to staging tables and Mixpanel staging properties to allow testing without affecting production data.

## Differences from Production

### BigQuery Tables
- **Production**: `potential_fraudsters`, `fraudsters`, `fraudsters_temp`
- **Staging**: `potential_fraudsters_stage`, `fraudsters_stage`, `fraudsters_stage_temp`

### Mixpanel Properties
- **Production**: `fraudster_cohort_active_v7`
- **Staging**: `fraudster_cohort_active_stage`

### Mixpanel Cohorts
- **Production**: `known_fraudsters`
- **Staging**: `known_fraudsters_stage`

### Important Notes
- The staging version **reads from production `fraudsters` table** to get manual fraud identifications (this is intentional - manual flags should be preserved)
- All writes go to staging tables
- Mixpanel updates use staging property names

## Setup

1. **Create staging tables in BigQuery**:
   ```bash
   # Run the SQL in create_staging_tables.sql in BigQuery console
   ```

2. **Install dependencies**:
   ```bash
   cd fraudsters-management
   pip install -r requirements.txt
   ```

3. **Set up authentication**:
   ```bash
   gcloud auth application-default login
   ```

## Running Locally

```bash
python main_dev.py
```

The script will:
1. Calculate `potential_fraudsters_stage` table
2. Calculate `offer_wall_progression_cheaters` table (using staging data)
3. Update `fraudsters_stage` table
4. Update Mixpanel profiles with `fraudster_cohort_active_stage` property
5. Create/update `known_fraudsters_stage` cohort in Mixpanel

## Output

The script prints a JSON summary with:
- `run_id`: Unique identifier for this run
- `mode`: "DEV/STAGING"
- `steps`: Array of step results
- `success`: Overall success status
- `start_time` / `end_time`: Execution timestamps

## Comparing Results

After running, you can compare staging vs production:

```sql
-- Compare counts
SELECT 
  'production' as source,
  COUNT(*) as count
FROM `yotam-395120.peerplay.fraudsters`
UNION ALL
SELECT 
  'staging' as source,
  COUNT(*) as count
FROM `yotam-395120.peerplay.fraudsters_stage`;

-- Compare specific users
SELECT 
  f.distinct_id,
  f.manual_identification_fraud_purchase_flag as prod_manual,
  fs.manual_identification_fraud_purchase_flag as stage_manual,
  f.fast_progression_flag as prod_fast,
  fs.fast_progression_flag as stage_fast
FROM `yotam-395120.peerplay.fraudsters` f
FULL OUTER JOIN `yotam-395120.peerplay.fraudsters_stage` fs
  ON f.distinct_id = fs.distinct_id
WHERE f.distinct_id IS NULL OR fs.distinct_id IS NULL
  OR f.manual_identification_fraud_purchase_flag != fs.manual_identification_fraud_purchase_flag
LIMIT 100;
```

