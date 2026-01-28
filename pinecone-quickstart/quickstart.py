#!/usr/bin/env python3
"""
Pinecone Quick Test - Semantic Search Demo

This script demonstrates:
1. Connecting to Pinecone
2. Upserting sample data with metadata
3. Performing semantic search
4. Reranking results for better accuracy
"""

import os
import time
from dotenv import load_dotenv
from pinecone import Pinecone

# Load environment variables
load_dotenv()

# Initialize Pinecone
pc = Pinecone(api_key=os.environ.get("PINECONE_API_KEY"))

# Connect to index
INDEX_NAME = "quickstart-test"
index = pc.Index(INDEX_NAME)

print(f"✅ Connected to index: {INDEX_NAME}\n")

# Sample data - documents from different domains
sample_data = [
    {
        "_id": "rec1",
        "content": "The Eiffel Tower was completed in 1889 and stands in Paris, France.",
        "category": "history"
    },
    {
        "_id": "rec2",
        "content": "Photosynthesis allows plants to convert sunlight into energy.",
        "category": "science"
    },
    {
        "_id": "rec5",
        "content": "Shakespeare wrote many famous plays, including Hamlet and Macbeth.",
        "category": "literature"
    },
    {
        "_id": "rec7",
        "content": "The Great Wall of China was built to protect against invasions.",
        "category": "history"
    },
    {
        "_id": "rec15",
        "content": "Leonardo da Vinci painted the Mona Lisa.",
        "category": "art"
    },
    {
        "_id": "rec17",
        "content": "The Pyramids of Giza are among the Seven Wonders of the Ancient World.",
        "category": "history"
    },
    {
        "_id": "rec21",
        "content": "The Statue of Liberty was a gift from France to the United States.",
        "category": "history"
    },
    {
        "_id": "rec26",
        "content": "Rome was once the center of a vast empire.",
        "category": "history"
    },
    {
        "_id": "rec33",
        "content": "The violin is a string instrument commonly used in orchestras.",
        "category": "music"
    },
    {
        "_id": "rec38",
        "content": "The Taj Mahal is a mausoleum built by Emperor Shah Jahan.",
        "category": "history"
    },
    {
        "_id": "rec48",
        "content": "Vincent van Gogh painted Starry Night.",
        "category": "art"
    },
    {
        "_id": "rec50",
        "content": "Renewable energy sources include wind, solar, and hydroelectric power.",
        "category": "energy"
    }
]

print("📤 Upserting sample data to Pinecone...")
print(f"   Total records: {len(sample_data)}\n")

# Upsert data using the records namespace (for data isolation)
# Note: Using namespace is MANDATORY for production use
index.upsert_records(
    namespace="quickstart",
    records=sample_data
)

print("✅ Data uploaded successfully!\n")

# Wait for data to be indexed (eventually consistent)
print("⏳ Waiting 10 seconds for indexing to complete...")
time.sleep(10)
print("✅ Ready to search!\n")

# Perform semantic search
query = "Famous historical structures and monuments"
print(f"🔍 Searching for: '{query}'\n")
print("=" * 80)

# Search with semantic search API
# Note: We'll compare results without and with reranking
results = index.search(
    namespace="quickstart",
    query={
        "top_k": 10,
        "inputs": {
            "text": query
        }
    }
)

print(f"\n📊 SEARCH RESULTS (without reranking):")
print(f"   Found {len(results['result']['hits'])} results\n")

for i, hit in enumerate(results['result']['hits'][:5], 1):
    print(f"{i}. [Score: {hit['_score']:.4f}] {hit['fields']['content']}")
    print(f"   Category: {hit['fields']['category']}")
    print()

# Now let's rerank the results for better accuracy
print("=" * 80)
print("\n🎯 RERANKING RESULTS for better accuracy...\n")

reranked_results = index.search(
    namespace="quickstart",
    query={
        "top_k": 10,
        "inputs": {
            "text": query
        }
    },
    rerank={
        "model": "bge-reranker-v2-m3",
        "top_n": 5,
        "rank_fields": ["content"]
    }
)

print(f"📊 RERANKED RESULTS:")
print(f"   Showing top {len(reranked_results['result']['hits'])} results\n")

for i, hit in enumerate(reranked_results['result']['hits'], 1):
    print(f"{i}. [Score: {hit['_score']:.4f}] {hit['fields']['content']}")
    print(f"   Category: {hit['fields']['category']}")
    print()

print("=" * 80)
print("\n✅ Quick test completed successfully!")
print("\n💡 Key concepts demonstrated:")
print("   • Index creation with integrated embeddings")
print("   • Namespace usage for data isolation")
print("   • Semantic search (finds meaning, not just keywords)")
print("   • Reranking for improved result accuracy")
print("\n📚 Next steps:")
print("   • Try different search queries")
print("   • Explore metadata filtering")
print("   • Build a RAG system or recommendation engine")
print(f"\n🗑️  Clean up: pc index delete --name {INDEX_NAME}")
