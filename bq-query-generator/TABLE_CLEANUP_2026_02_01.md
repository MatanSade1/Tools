# Query Gen Tables Cleanup - February 1, 2026

## Summary

Cleaned up and improved `query_gen_tables` by updating descriptions, removing obsolete tables, and clarifying usage instructions.

---

## Updated Tables (6)

### 1. googleplay_sales
**Change:** Updated table description  
**New Description:** "Google Play transaction and refunds records."  
**Impact:** Clearer understanding of what data this table contains

### 2. vmp_master_event_normalized
**Change:** Enhanced description  
**Addition:** "This is the main raw events level table, also known as the client BI events table."  
**Impact:** Query generator now knows this is the primary client events table

### 3. levelplay_revenue_data
**Change:** Added deprecation notice to usage description  
**Addition:** "Note: Since version 0.37422 we no longer use LevelPlay as our ad mediation (we use MAX instead)."  
**Impact:** Query generator will warn users about deprecated data source

### 4. agg_player_chapter_daily
**Change:** Added filtering instruction to usage description  
**Addition:** "Important: Ignore records with chapter = 0 (they are used only for aggregation of attribution data)."  
**Impact:** Queries will automatically filter out chapter 0 records

### 5. singular.singular_events
**Change:** Complete rewrite of description and usage  
**New Description:** "Data reported directly from Singular. Use this table when you want to know that Singular received a postback (event)."  
**New Usage:** "Use custom_user_id (matches our distinct_id) and name (event_name) columns for queries."  
**Impact:** Much clearer explanation of how to use Singular data

### 6. launch_funnel_analysis_dashboard
**Change:** Added additional usage note  
**Addition:** "This is also the table we use for the launch dashboard."  
**Impact:** Query generator knows this table powers the launch dashboard

---

## Removed Tables (2)

### 1. active_versions ❌
**Reason:** Barely used, would confuse the tool  
**Action Taken:**
- Removed from `query_gen_tables`
- Deleted all related columns from `query_gen_columns`
- Removed all vectors from Pinecone

### 2. sentry_mapping ❌
**Reason:** Barely used, would confuse the tool  
**Action Taken:**
- Removed from `query_gen_tables`
- Deleted all related columns from `query_gen_columns`
- Removed all vectors from Pinecone

---

## Impact Metrics

### Before Cleanup
- **Tables:** 24
- **Columns:** 1,654
- **Pinecone Vectors:** 1,702

### After Cleanup
- **Tables:** 22 (-2)
- **Columns:** 1,628 (-26)
- **Pinecone Vectors:** 1,671 (-31)

### Improvements
- **Cleaner knowledge base:** Removed 31 obsolete vectors
- **Better accuracy:** Updated 6 table descriptions for clarity
- **Less confusion:** Eliminated rarely-used tables that could mislead the AI
- **Specific instructions:** Added usage guardrails for special cases

---

## Query Generator Improvements

The query generator now:
1. ✅ **Won't suggest obsolete tables** (`active_versions`, `sentry_mapping`)
2. ✅ **Understands Google Play data** (transactions & refunds)
3. ✅ **Knows the main events table** (`vmp_master_event_normalized`)
4. ✅ **Warns about deprecated data** (LevelPlay after v0.37422)
5. ✅ **Filters chapter correctly** (chapter != 0 in aggregations)
6. ✅ **Uses Singular properly** (`custom_user_id`, `name` columns)
7. ✅ **Recognizes dashboard tables** (launch dashboard)

---

## Next Steps

### Recommended Actions
1. Monitor query generation for accuracy improvements
2. Add column descriptions for newly documented tables
3. Consider similar cleanup for other rarely-used tables
4. Document any new tables with clear descriptions from the start

### Maintenance
- This cleanup reduced the knowledge base by ~2%
- Future additions should include clear descriptions and usage instructions
- Regularly review table usage and remove unused tables

---

## Verification

All changes verified:
- ✅ 6 tables updated in BigQuery
- ✅ 2 tables removed from BigQuery
- ✅ 26 columns removed from `query_gen_columns`
- ✅ All changes synced to Pinecone
- ✅ Vector count reduced to 1,671

**Status:** Complete and operational ✅
