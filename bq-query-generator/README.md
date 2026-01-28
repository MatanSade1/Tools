# BQ Query Generator

A RAG (Retrieval-Augmented Generation) based tool that converts natural language requests into optimized BigQuery SQL queries using your organizational knowledge base.

## Features

✨ **Natural Language to SQL** - Describe what you want in plain English, get production-ready SQL  
🎯 **Context-Aware** - Leverages your organizational documentation (tables, metrics, guardrails)  
🚀 **Optimized Queries** - Follows best practices (partitioning, clustering, cost optimization)  
🔍 **Semantic Search** - Uses vector embeddings to find relevant context  
🤖 **Claude AI** - Powered by Claude Sonnet for intelligent query generation  
📚 **Transparent** - Shows which documentation informed the query  
🛠️ **Easy to Maintain** - Update markdown docs and re-run setup

## Architecture

```
User Request → Embedding → Vector Search → Context Retrieval → Claude AI → SQL Query
                  ↓                              ↓
              OpenAI                         Pinecone
          text-embedding-3-large         Vector Database
```

**Components:**
- **OpenAI** (`text-embedding-3-large`): Generates semantic embeddings
- **Pinecone**: Stores and retrieves document embeddings
- **Claude AI** (Sonnet 3.5): Generates SQL from context + request
- **Organizational Docs**: Your knowledge base in markdown format

## Quick Start

### 1. Installation

```bash
cd bq-query-generator

# Install dependencies (using your existing venv)
source ../venv/bin/activate
pip install -r requirements.txt
```

### 2. Configuration

API keys are already configured in `.env` file:
- ✅ OpenAI API Key
- ✅ Pinecone API Key
- ✅ Anthropic API Key

### 3. Setup Vector Database

This one-time step reads your organizational docs, generates embeddings, and uploads them to Pinecone:

```bash
python main.py setup
```

This will:
1. Read all markdown files from `config/organizational_manual/`
2. Chunk documents by sections
3. Generate embeddings using OpenAI
4. Upload vectors to Pinecone

**Expected time:** 2-5 minutes depending on documentation size

### 4. Generate Queries

#### Single Query

```bash
python main.py query "Show me daily active users for the last 7 days"
```

#### With Verbose Output

```bash
python main.py query "Show me daily active users for the last 7 days" --verbose
```

Shows:
- Embedding generation
- Vector search results
- Retrieved context
- LLM generation process

#### Interactive Mode

```bash
python main.py interactive
```

Enter multiple queries in a conversation-style interface.

## Usage Examples

### Example 1: Basic Metrics Query

```bash
python main.py query "Calculate DAU for last 30 days"
```

**Output:**
```sql
-- Daily Active Users for last 30 days
SELECT 
  event_date,
  COUNT(DISTINCT user_id) AS dau
FROM `project.dataset.events_daily_summary`
WHERE event_date >= CURRENT_DATE() - 30
  AND event_name IN ('app_opened', 'session_start')
GROUP BY event_date
ORDER BY event_date
```

### Example 2: User Cohort Analysis

```bash
python main.py query "Show me retention rate for users who signed up in January 2024"
```

### Example 3: Revenue Analysis

```bash
python main.py query "What's the total revenue by subscription tier for last month"
```

### Example 4: Funnel Analysis

```bash
python main.py query "Create a signup funnel from signup_started to signup_completed for last week"
```

### Example 5: Event Analysis

```bash
python main.py query "Show me the most common button clicks on the home screen in the last 7 days"
```

## Project Structure

```
bq-query-generator/
├── README.md                          # This file
├── requirements.txt                   # Python dependencies
├── main.py                           # CLI entry point
├── setup_vectordb.py                 # Vector DB setup script
├── .env                              # API keys (gitignored)
├── .env.example                      # Environment template
├── .gitignore                        # Git ignore rules
├── config/
│   ├── config.json                   # Tool configuration
│   └── organizational_manual/
│       ├── tables_schema.md          # Table schemas & usage
│       ├── usage_guardrails.md       # Query best practices
│       ├── metrics_definitions.md    # Standard metrics
│       └── events_parameters.md      # Event dictionary
└── src/
    ├── __init__.py
    ├── embeddings.py                 # OpenAI embedding generation
    ├── vector_store.py               # Pinecone operations
    ├── llm_client.py                 # Claude AI client
    └── query_generator.py            # Main RAG pipeline
```

## CLI Commands

### `python main.py query <REQUEST>`

Generate a single SQL query.

**Options:**
- `--verbose, -v`: Show detailed generation process
- `--copy, -c`: Copy query to clipboard (requires pyperclip)

**Examples:**
```bash
python main.py query "Show me new users by day"
python main.py query "Calculate monthly retention" --verbose
python main.py query "Revenue by country" --copy
```

### `python main.py interactive`

Run in interactive mode for multiple queries.

**Commands in interactive mode:**
- Type any query request
- `verbose`: Toggle verbose mode on/off
- `quit` or `exit`: Exit interactive mode

### `python main.py setup`

Set up vector database with organizational documentation.

**Options:**
- `--reset`: Delete existing vectors before setup

**When to run:**
- First time using the tool
- After updating organizational documentation
- To refresh the knowledge base

### `python main.py test`

Test all components (OpenAI, Pinecone, Claude).

Verifies:
- ✓ OpenAI embeddings API
- ✓ Pinecone connection and vector count
- ✓ Claude AI connection

## Configuration

### `config/config.json`

```json
{
  "pinecone": {
    "index_name": "bq-query-knowledge",
    "dimension": 3072,
    "metric": "cosine"
  },
  "embeddings": {
    "model": "text-embedding-3-large",
    "chunk_size": 1000,
    "chunk_overlap": 200
  },
  "llm": {
    "model": "claude-3-5-sonnet-20241022",
    "temperature": 0.1,
    "max_tokens": 2000
  },
  "retrieval": {
    "top_k": 8,
    "score_threshold": 0.7
  }
}
```

**Key settings:**
- `top_k`: Number of context chunks to retrieve (default: 8)
- `score_threshold`: Minimum similarity score (0-1, default: 0.7)
- `temperature`: LLM creativity (0=deterministic, 1=creative, default: 0.1)

## Organizational Documentation

The tool's knowledge comes from markdown files in `config/organizational_manual/`. These files are embedded into the vector database.

### `tables_schema.md`

Documents BigQuery tables:
- Table descriptions and schemas
- Column definitions
- Granularity (row-level meaning)
- Partitioning and clustering
- When to use each table
- Example queries
- Performance tips

### `usage_guardrails.md`

Query best practices:
- Partition filtering rules
- Clustering column order
- JSON property extraction
- Aggregation strategies
- Cost optimization
- Performance expectations

### `metrics_definitions.md`

Standard organizational metrics:
- DAU/MAU/WAU calculations
- Retention metrics
- Engagement metrics
- Revenue metrics
- Conversion funnels
- Consistent definitions across org

### `events_parameters.md`

Event tracking dictionary:
- All tracked events
- Event parameters and types
- When events fire
- Usage examples
- Common event patterns

## Updating Documentation

When you update organizational documentation:

1. **Edit markdown files** in `config/organizational_manual/`
2. **Re-run setup** to refresh vector database:
   ```bash
   python main.py setup --reset
   ```
3. **Test** to ensure changes are reflected:
   ```bash
   python main.py query "test query related to your changes" --verbose
   ```

The tool will automatically pick up the new information!

## How It Works

### RAG Pipeline

1. **User Request**: "Show me daily active users for last 7 days"

2. **Embedding Generation**: 
   - Convert request to 3072-dimensional vector using OpenAI
   - Vector captures semantic meaning

3. **Vector Search**:
   - Query Pinecone for similar document chunks
   - Retrieve top-8 most relevant sections
   - Examples: DAU definition, events_daily_summary table, partition rules

4. **Context Assembly**:
   - Combine retrieved chunks with metadata
   - Format as context for LLM

5. **Query Generation**:
   - Send context + request to Claude AI
   - Claude generates optimized BigQuery SQL
   - Follows organizational best practices

6. **Output**:
   - SQL query with comments
   - Explanation of approach
   - Context sources (if verbose)

### Why RAG?

**Traditional approaches:**
- ❌ Hardcoded templates: Not flexible, high maintenance
- ❌ LLM only: No organizational context, generic queries
- ❌ Manual: Slow, requires SQL expertise

**RAG approach:**
- ✅ Flexible: Handles wide variety of requests
- ✅ Context-aware: Uses your org's best practices
- ✅ Maintainable: Update docs, not code
- ✅ Transparent: Shows what informed the query
- ✅ Optimized: Follows partitioning, clustering rules

## Costs

### OpenAI (Embeddings)

**text-embedding-3-large pricing**: $0.13 per 1M tokens

**One-time setup cost** (for ~50KB of docs):
- ~10,000 tokens = $0.0013 ≈ **free**

**Per-query cost** (~100 tokens per query):
- 1,000 queries = $0.013 ≈ **1 cent**
- 10,000 queries = $0.13 ≈ **13 cents**

### Pinecone (Vector Database)

**Free tier**: 
- 1 index
- 100,000 vectors
- Unlimited queries

**Your usage**: ~500-2000 vectors for docs = **free**

### Anthropic (Claude)

**Claude 3.5 Sonnet pricing**:
- Input: $3 per 1M tokens
- Output: $15 per 1M tokens

**Per-query cost** (~1000 input + 500 output tokens):
- Input: 1000 tokens × $3/1M = $0.003
- Output: 500 tokens × $15/1M = $0.0075
- **Total per query: ~1 cent**

**Monthly estimate** (100 queries/day):
- 3,000 queries/month × $0.01 = **$30/month**

## Troubleshooting

### Setup fails with "No markdown files found"

**Solution**: Ensure markdown files exist in `config/organizational_manual/`:
```bash
ls -la config/organizational_manual/
```

Should show:
- `tables_schema.md`
- `usage_guardrails.md`
- `metrics_definitions.md`
- `events_parameters.md`

### "No relevant context found"

**Causes:**
1. Vector database not set up
2. Query too different from documentation
3. Similarity threshold too high

**Solutions:**
```bash
# Re-run setup
python main.py setup --reset

# Test connection
python main.py test

# Try with verbose to see scores
python main.py query "your query" --verbose
```

### API errors

**OpenAI errors:**
- Check API key in `.env`
- Verify billing enabled at platform.openai.com
- Check rate limits

**Pinecone errors:**
- Verify API key in `.env`
- Check index exists: login to app.pinecone.io
- Ensure index dimension is 3072

**Claude errors:**
- Check API key in `.env`
- Verify credits available at console.anthropic.com
- Check API rate limits

### Queries don't follow best practices

**Solution**: Update `usage_guardrails.md` with specific rules:

```markdown
## CRITICAL: Always filter by partition column

When querying events_raw or events_daily_summary, you MUST include:
WHERE event_date >= <start_date> AND event_date <= <end_date>
```

Then re-run setup:
```bash
python main.py setup --reset
```

## Development

### Running Tests

```bash
# Test individual components
python -m src.embeddings
python -m src.vector_store
python -m src.llm_client
python -m src.query_generator

# Test full system
python main.py test
```

### Adding New Documentation

1. Create new `.md` file in `config/organizational_manual/`
2. Follow markdown structure (headers, sections)
3. Run setup to index:
   ```bash
   python main.py setup --reset
   ```

### Debugging

Enable verbose mode to see:
- Embedding generation
- Vector search results and scores
- Retrieved context chunks
- LLM prompt and response

```bash
python main.py query "your query" --verbose
```

## Best Practices

### Writing Good Queries

✅ **Be specific:**
- "Show me DAU for last 7 days" ✓
- "Show me users" ✗

✅ **Use organizational terms:**
- "Calculate stickiness ratio" ✓
- "Show me DAU/MAU" ✓

✅ **Mention timeframes:**
- "Last 7 days", "January 2024", "Last month" ✓

✅ **Reference known metrics:**
- "Day 7 retention for January cohort" ✓
- "Activation rate by signup method" ✓

### Maintaining Documentation

✅ **Keep docs current:**
- Update when schema changes
- Add new events/metrics promptly
- Document new tables immediately

✅ **Include examples:**
- SQL query examples help the LLM
- Real-world use cases improve accuracy

✅ **Be explicit:**
- State rules clearly (ALWAYS, NEVER, MUST)
- Explain why, not just what
- Include edge cases

## Limitations

1. **Query complexity**: Extremely complex multi-CTE queries may need manual review
2. **Custom logic**: Business-specific calculations not in docs require manual adjustment
3. **Real-time data**: Tool doesn't know current state (table sizes, latest dates)
4. **Validation**: Always review generated queries before running on production data

## Security

- ✅ API keys stored in `.env` (gitignored)
- ✅ Markdown docs can contain sensitive schema info (keep repo private)
- ✅ Query content not stored by OpenAI/Anthropic (as per their policies)
- ⚠️ Don't commit `.env` file
- ⚠️ Rotate API keys periodically

## Contributing

To improve the tool:

1. **Enhance documentation**: Add more examples, edge cases, use cases
2. **Refine prompts**: Improve system prompt in `src/llm_client.py`
3. **Adjust parameters**: Tune `top_k`, `score_threshold`, `temperature` in `config/config.json`
4. **Add validation**: Implement SQL syntax validation before output

## Support

If you encounter issues:

1. Run `python main.py test` to verify setup
2. Check with `--verbose` to see what's happening
3. Review API key configuration in `.env`
4. Ensure organizational docs are complete

## License

Internal tool for organizational use.

---

**Happy querying! 🚀**

For questions or improvements, please reach out to the data team.
