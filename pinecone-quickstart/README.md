# Pinecone Quick Test

A quick demonstration of Pinecone's semantic search capabilities with integrated embeddings and reranking.

## What This Demo Does

1. **Connects to Pinecone** - Uses your API key to connect to a Pinecone index
2. **Uploads Sample Data** - 12 documents covering history, science, art, literature, and more
3. **Performs Semantic Search** - Searches for "Famous historical structures and monuments"
4. **Shows Reranking** - Demonstrates how reranking improves result accuracy

## Key Results

### Without Reranking
The initial search found relevant results, but some non-historical items appeared (Shakespeare's plays, Mona Lisa).

### With Reranking
After reranking, the top 5 results were ALL historical structures and monuments:
1. The Eiffel Tower
2. The Taj Mahal
3. The Great Wall of China
4. The Statue of Liberty
5. The Pyramids of Giza

**This is the power of semantic search + reranking!** 🎯

## Project Structure

```
pinecone-quickstart/
├── .env              # Your API key (keep this secret!)
├── .env.example      # Template for API key
├── quickstart.py     # The demo script
└── README.md         # This file
```

## Running the Script

```bash
# Activate virtual environment
source ../venv/bin/activate

# Run the script
python quickstart.py
```

## Key Concepts Demonstrated

✅ **Index Creation** - Created index with integrated embeddings using CLI  
✅ **Namespace Usage** - Used `quickstart` namespace for data isolation  
✅ **Semantic Search** - Finds meaning, not just keywords  
✅ **Reranking** - Improves result accuracy significantly  

## What You Learned

1. **Semantic Search** understands meaning - even though "Eiffel Tower" doesn't contain the words "structures" or "monuments", it knows it's relevant
2. **Reranking** improves accuracy - notice how the reranked results are all historical structures
3. **Namespaces** provide data isolation - critical for multi-tenant applications
4. **Integrated Embeddings** make it easy - no need to generate embeddings yourself

## Next Steps

### Try Different Queries

Edit `quickstart.py` and change the query on line 110:

```python
query = "Scientific discoveries about plants"  # Try this!
# Expected: Should return the photosynthesis document
```

### Explore Metadata Filtering

Add a filter to only search specific categories:

```python
results = index.search(
    namespace="quickstart",
    query={
        "top_k": 10,
        "inputs": {"text": query},
        "filter": {"category": {"$eq": "history"}}  # Only history!
    }
)
```

### Build Something Real

Now that you understand the basics, you can build:
- **Search System** - Semantic search over your knowledge base
- **RAG System** - Retrieve context and feed to an LLM for answers
- **Recommendation Engine** - Suggest similar items based on semantic similarity

See the Pinecone documentation in `.agents/` for detailed guides on these use cases.

## Clean Up

When you're done experimenting:

```bash
# Delete the index to avoid charges
pc index delete --name quickstart-test
```

## Resources

- **Pinecone Docs**: https://docs.pinecone.io/
- **Agent Guides**: See `.agents/` directory in the parent folder
- **API Key**: https://app.pinecone.io/

## Summary

🎉 You successfully:
- Installed Pinecone CLI and Python SDK
- Created a Pinecone index with integrated embeddings
- Uploaded 12 sample documents
- Performed semantic search with reranking
- Saw reranking improve accuracy from mixed results to 100% relevant results

**Pinecone makes vector search easy!** 🚀
