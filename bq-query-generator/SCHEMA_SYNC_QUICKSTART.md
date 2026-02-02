# Schema Sync - Quick Reference

## 🚀 Common Commands

```bash
# Sync single table
python main.py sync-columns --table "yotam-395120.peerplay.events"

# Preview changes (dry-run)
python main.py sync-columns --table "yotam-395120.peerplay.events" --dry-run

# Sync all tables
python main.py sync-columns --all

# Verbose output
python main.py sync-columns --table "yotam-395120.peerplay.events" --verbose
```

## 📋 Typical Workflow

### Adding a New Table

**1. Add table to query_gen_tables:**
```sql
INSERT INTO `yotam-395120.peerplay.query_gen_tables`
VALUES ('table_name', 'description', 'partition_col', ['cluster1', 'cluster2'], 
        'usage_notes', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP());
```

**2. Sync columns (creates records with empty descriptions):**
```bash
python main.py sync-columns --table "yotam-395120.peerplay.table_name"
```

**3. Add descriptions to important columns:**
```sql
UPDATE `yotam-395120.peerplay.query_gen_columns`
SET column_description = 'Your description here'
WHERE column_name = 'column_name' AND related_table = 'table_name';
```

**4. Re-sync to create Pinecone vectors:**
```bash
python main.py sync-columns --table "yotam-395120.peerplay.table_name"
```

## ⚡ Performance

- **Single table:** ~2-5 seconds
- **All 24 tables:** ~45 seconds
- **Cost:** ~$0.002 per full sync

## 🎯 Key Behaviors

### What Gets Synced to Pinecone?
- ✅ **Columns WITH descriptions** → Embedded and added to Pinecone
- ❌ **Columns WITHOUT descriptions** → Skipped (added to BigQuery only)

### What Happens on Re-sync?
- **Added columns** → Inserted to BigQuery, embedded if described
- **Updated columns** → Technical fields updated, **descriptions preserved**
- **Removed columns** → Deleted from BigQuery and Pinecone

### Views vs Tables
- **Tables** → Partition/cluster from table definition
- **Views** → Attempts to detect underlying table and use its partition/cluster

## 📊 Output Explanation

```bash
✓ Updated query_gen_columns:
  - Deleted: 2 rows        # Columns removed from schema
  - Updated: 1 rows        # Technical fields changed
  - Inserted: 5 rows       # New columns added

✓ Pinecone updated:
  - Deleted: 2 vectors     # Removed columns
  - Updated: 1 vectors     # Updated columns (that had descriptions)
  - Added: 2 vectors       # New columns (that have descriptions)
  - Skipped: 3 columns     # New columns without descriptions
```

## 🔧 Troubleshooting

### "No columns found for table"
- Table doesn't exist in BigQuery
- Check table name format: `project.dataset.table`

### "0 vectors added, 10 skipped"
- Columns don't have descriptions yet
- Add descriptions with SQL UPDATE, then re-sync

### Sync taking too long
- Should complete in <1 minute for all tables
- If longer, check for network issues or API rate limits

## 📝 SQL Snippets

### View all columns for a table
```sql
SELECT column_name, column_type, column_description, is_partition, is_cluster
FROM `yotam-395120.peerplay.query_gen_columns`
WHERE related_table = 'yotam-395120.peerplay.events'
ORDER BY column_name;
```

### Find columns without descriptions
```sql
SELECT related_table, column_name
FROM `yotam-395120.peerplay.query_gen_columns`
WHERE (column_description IS NULL OR column_description = '')
ORDER BY related_table, column_name;
```

### Bulk update descriptions
```sql
UPDATE `yotam-395120.peerplay.query_gen_columns`
SET column_description = 'User identifier'
WHERE column_name = 'user_id';  -- Updates across all tables
```

## 🎯 Best Practices

1. **Add table metadata first** (in query_gen_tables)
2. **Run sync to get columns** (they'll have empty descriptions)
3. **Add descriptions gradually** (focus on most-used columns)
4. **Re-sync after descriptions** (to create Pinecone vectors)
5. **Use --dry-run** before major changes
6. **Run --all periodically** to catch schema changes

## ⚠️ Important Notes

- **Descriptions are preserved** when schema changes
- **Only described columns** appear in Pinecone
- **Batch operations** make sync very fast (~1 min for all tables)
- **No downtime** during sync - incremental updates only
