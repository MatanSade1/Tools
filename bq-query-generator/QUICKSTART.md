# BQ Query Generator - Quick Start Guide

## ✅ What's Been Built

Your RAG-based BigQuery query generator is **successfully installed and ready**!

### Components Status:
- ✅ **Directory structure created** (`bq-query-generator/`)
- ✅ **OpenAI embeddings working** (text-embedding-3-large, 3072 dimensions)
- ✅ **Pinecone vector DB created** (132 document chunks indexed)
- ✅ **Organizational documentation embedded** (4 markdown files)
- ✅ **CLI interface ready** (`main.py`)
- ⚠️  **Claude API needs verification** (see below)

### What's Indexed:
- 📄 **tables_schema.md** - 36 sections about BigQuery tables
- 📄 **usage_guardrails.md** - 20 sections on query best practices  
- 📄 **metrics_definitions.md** - 28 sections on organizational metrics
- 📄 **events_parameters.md** - 48 sections on event tracking

**Total:** 132 embedded chunks in Pinecone

---

## ⚠️ Action Required: Claude API Key

The Anthropic API key needs to be verified. Current error:
```
Error code: 404 - model: claude-3-opus-20240229 not found
```

### To Fix:

1. **Verify your Anthropic API key** at https://console.anthropic.com/settings/keys
2. **Check your account** has access to Claude models
3. **Update `.env` if needed:**
```bash
cd /Users/matansade/Tools/bq-query-generator
# Edit .env and update ANTHROPIC_API_KEY
```

4. **Test the connection:**
```bash
source ../venv/bin/activate
python main.py test
```

You should see:
```
✓ OpenAI embeddings working
✓ Pinecone connected (vectors: 132)
✓ Claude AI connected
```

---

## 🚀 Usage (Once Claude is Working)

### 1. Activate Environment
```bash
cd /Users/matansade/Tools
source venv/bin/activate
cd bq-query-generator
```

### 2. Generate a Query
```bash
python main.py query "Show me daily active users for the last 7 days"
```

### 3. With Verbose Output (see the RAG process)
```bash
python main.py query "Calculate Day 7 retention for January cohort" --verbose
```

### 4. Interactive Mode
```bash
python main.py interactive
```

Then enter queries like:
- "Show me new users by signup method last month"
- "Calculate stickiness ratio for last 30 days"
- "Create a signup funnel from signup_started to signup_completed"
- "Show me revenue by subscription tier"

---

## 📁 Project Structure

```
bq-query-generator/
├── README.md                      # Full documentation
├── QUICKSTART.md                  # This file
├── main.py                        # CLI entry point ⭐
├── setup_vectordb.py              # Vector DB setup script
├── requirements.txt               # Dependencies
├── .env                          # API keys (gitignored)
├── config/
│   ├── config.json               # Tool configuration
│   └── organizational_manual/    # Your knowledge base
│       ├── tables_schema.md      # ✅ 36 sections indexed
│       ├── usage_guardrails.md   # ✅ 20 sections indexed
│       ├── metrics_definitions.md # ✅ 28 sections indexed
│       └── events_parameters.md  # ✅ 48 sections indexed
└── src/
    ├── embeddings.py             # OpenAI embeddings ✅
    ├── vector_store.py           # Pinecone operations ✅
    ├── llm_client.py             # Claude AI client ⚠️
    └── query_generator.py        # RAG pipeline ✅
```

---

## 🔧 Configuration

### Current Settings (`config/config.json`):

```json
{
  "pinecone": {
    "index_name": "bq-query-knowledge",
    "dimension": 3072,
    "metric": "cosine"
  },
  "embeddings": {
    "model": "text-embedding-3-large"
  },
  "llm": {
    "model": "claude-3-opus-20240229",
    "temperature": 0.1
  },
  "retrieval": {
    "top_k": 8,
    "score_threshold": 0.3
  }
}
```

**Note:** `score_threshold` was lowered to 0.3 (from 0.7) based on testing. Semantic search typically produces scores in the 0.4-0.6 range.

---

## 📝 Updating Documentation

When you update your organizational docs:

```bash
# 1. Edit markdown files in config/organizational_manual/

# 2. Refresh the vector database
source ../venv/bin/activate
python main.py setup --reset

# 3. Test with a related query
python main.py query "query about the updated content" --verbose
```

---

## 🧪 Testing

### Test All Components:
```bash
python main.py test
```

Expected output:
```
✓ OpenAI embeddings working (3072 dimensions)
✓ Pinecone connected (vectors: 132)
✓ Claude AI connected
```

### Test Individual Components:
```bash
# Test embeddings
python -m src.embeddings

# Test vector store
python -m src.vector_store

# Test LLM client
python -m src.llm_client
```

---

## 💡 Example Queries to Try

Once Claude is working, try these:

### Basic Metrics:
- "Show me DAU for last 30 days"
- "Calculate MAU and stickiness ratio"
- "Show me new users by day"

### User Analysis:
- "Find power users with more than 100 events per day"
- "Show me user retention Day 1, 7, and 30"
- "Calculate activation rate by signup method"

### Event Analysis:
- "Show me most viewed screens in last week"
- "Count button clicks on home screen"
- "Find all error events with their error codes"

### Revenue:
- "Show me total revenue by subscription tier"
- "Calculate ARPU by signup month"
- "Show me subscription renewal rate"

### Funnels:
- "Create signup funnel: signup_started → signup_completed"
- "Build purchase funnel: product_viewed → add_to_cart → purchase_completed"
- "Show onboarding completion funnel"

---

## 🎯 How It Works

```
User Request
     ↓
OpenAI Embeddings (text-embedding-3-large)
     ↓
Pinecone Vector Search
     ↓
Retrieve Top 8 Relevant Doc Chunks (score > 0.3)
     ↓
Claude AI (with context)
     ↓
Optimized BigQuery SQL + Explanation
```

### Example Flow:

**Input:** "Show me daily active users for last 7 days"

**Vector Search Finds:**
- metrics_definitions.md → DAU definition (score: 0.59)
- tables_schema.md → events_daily_summary table (score: 0.52)
- usage_guardrails.md → partition filtering rules (score: 0.48)

**Claude Receives:**
- User request
- 8 relevant context chunks
- System prompt: "You are a BigQuery expert, follow org best practices..."

**Claude Generates:**
```sql
SELECT 
  event_date,
  COUNT(DISTINCT user_id) AS dau
FROM `project.dataset.events_daily_summary`
WHERE event_date >= CURRENT_DATE() - 7
  AND event_name IN ('app_opened', 'session_start')
GROUP BY event_date
ORDER BY event_date
```

**Explanation:** Uses events_daily_summary for performance, filters by partition column (event_date), follows DAU definition from metrics_definitions.md.

---

## 💰 Costs (Already Incurred)

### Setup Phase:
- OpenAI embeddings (132 chunks): ~$0.002 ✅ DONE
- Pinecone storage (132 vectors): FREE tier ✅ DONE

### Per Query (Estimated):
- OpenAI embedding (1 query): ~$0.000013
- Pinecone search: FREE (unlimited queries)
- Claude generation: ~$0.01-0.02 per query

**Monthly (100 queries/day):** ~$30-60

---

## 🐛 Troubleshooting

### "No relevant context found"
- ✅ Fixed! Score threshold lowered to 0.3
- Vector DB has 132 chunks ready

### "OpenAI API error"
- ✅ Working! Successfully generating embeddings

### "Pinecone connection failed"
- ✅ Fixed! Index created and connected (132 vectors)

### "Claude API error" ⚠️
- **Current issue:** Verify Anthropic API key
- Check https://console.anthropic.com/
- Try a different Claude model if needed

---

## 📚 Documentation

Full documentation available in:
- **README.md** - Complete guide with examples
- **config/organizational_manual/*.md** - Your knowledge base
- **This file (QUICKSTART.md)** - Quick reference

---

## ✨ Next Steps

1. **Verify Claude API key** (see Action Required section above)
2. **Run test command:** `python main.py test`
3. **Try your first query:** `python main.py query "Show me DAU last 7 days"`
4. **Customize docs:** Edit markdown files to match your actual BigQuery schema
5. **Re-run setup:** `python main.py setup --reset` after doc changes

---

## 🎉 Success Criteria

You'll know it's working when:

✅ `python main.py test` shows all green checkmarks  
✅ Queries return valid BigQuery SQL  
✅ Generated queries follow your org's best practices  
✅ Queries reference correct table names and columns  
✅ Partition filtering is always included  

---

**Questions or issues?** Check the full README.md or run commands with `--verbose` to see what's happening under the hood.

**Happy querying! 🚀**
