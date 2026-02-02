"""
Embedding generation using OpenAI's text-embedding-3-large model.
"""

import os
from typing import List, Dict
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class EmbeddingGenerator:
    """Generates embeddings using OpenAI's text-embedding-3-large model."""
    
    def __init__(self, model: str = "text-embedding-3-large"):
        """
        Initialize the embedding generator.
        
        Args:
            model: OpenAI embedding model name
        """
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.dimension = 3072  # text-embedding-3-large produces 3072-dim vectors
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Input text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        
        response = self.client.embeddings.create(
            input=text,
            model=self.model
        )
        
        return response.data[0].embedding
    
    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in a single API call.
        
        OpenAI allows up to 2048 inputs per request. This method automatically
        batches if you provide more than 2048 texts.
        
        Args:
            texts: List of input texts to embed
            
        Returns:
            List of embedding vectors (same order as input)
        """
        if not texts:
            return []
        
        # Filter out empty texts and track indices
        valid_texts = []
        valid_indices = []
        for i, text in enumerate(texts):
            if text and text.strip():
                valid_texts.append(text)
                valid_indices.append(i)
        
        if not valid_texts:
            raise ValueError("All texts are empty")
        
        embeddings = []
        batch_size = 2048  # OpenAI's max batch size
        
        for i in range(0, len(valid_texts), batch_size):
            batch = valid_texts[i:i + batch_size]
            
            response = self.client.embeddings.create(
                input=batch,
                model=self.model
            )
            
            # Extract embeddings in order
            batch_embeddings = [item.embedding for item in response.data]
            embeddings.extend(batch_embeddings)
        
        return embeddings
    
    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in a batch.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            raise ValueError("Texts list cannot be empty")
        
        # Filter out empty texts
        valid_texts = [t for t in texts if t and t.strip()]
        if not valid_texts:
            raise ValueError("No valid texts to embed")
        
        response = self.client.embeddings.create(
            input=valid_texts,
            model=self.model
        )
        
        return [item.embedding for item in response.data]
    
    def chunk_text(self, text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[str]:
        """
        Split text into overlapping chunks for embedding.
        
        Args:
            text: Text to chunk
            chunk_size: Maximum characters per chunk
            chunk_overlap: Characters to overlap between chunks
            
        Returns:
            List of text chunks
        """
        if not text or not text.strip():
            return []
        
        chunks = []
        start = 0
        text_len = len(text)
        
        while start < text_len:
            end = start + chunk_size
            chunk = text[start:end]
            
            # Try to break at paragraph or sentence boundary
            if end < text_len:
                # Look for paragraph break
                last_para = chunk.rfind('\n\n')
                if last_para > chunk_size // 2:
                    chunk = chunk[:last_para]
                else:
                    # Look for sentence break
                    last_period = chunk.rfind('. ')
                    if last_period > chunk_size // 2:
                        chunk = chunk[:last_period + 1]
            
            chunks.append(chunk.strip())
            start = start + chunk_size - chunk_overlap
        
        return [c for c in chunks if c]  # Remove empty chunks
    
    def chunk_markdown_by_sections(self, markdown_text: str) -> List[Dict[str, str]]:
        """
        Chunk markdown text by sections (headers) to preserve context.
        
        Args:
            markdown_text: Markdown text to chunk
            
        Returns:
            List of dicts with 'content', 'title', and 'level' keys
        """
        chunks = []
        lines = markdown_text.split('\n')
        
        current_chunk = []
        current_title = "Introduction"
        current_level = 0
        
        for line in lines:
            # Check if line is a header
            if line.startswith('#'):
                # Save previous chunk
                if current_chunk:
                    chunks.append({
                        'content': '\n'.join(current_chunk).strip(),
                        'title': current_title,
                        'level': current_level
                    })
                    current_chunk = []
                
                # Parse new header
                level = len(line) - len(line.lstrip('#'))
                current_title = line.lstrip('#').strip()
                current_level = level
                current_chunk.append(line)
            else:
                current_chunk.append(line)
        
        # Save final chunk
        if current_chunk:
            chunks.append({
                'content': '\n'.join(current_chunk).strip(),
                'title': current_title,
                'level': current_level
            })
        
        return [c for c in chunks if c['content']]  # Remove empty chunks


if __name__ == "__main__":
    # Test the embedding generator
    generator = EmbeddingGenerator()
    
    # Test single embedding
    test_text = "Show me daily active users for the last 7 days"
    embedding = generator.generate_embedding(test_text)
    print(f"Generated embedding with {len(embedding)} dimensions")
    print(f"First 5 values: {embedding[:5]}")
    
    # Test chunking
    long_text = "This is a test. " * 100
    chunks = generator.chunk_text(long_text, chunk_size=100, chunk_overlap=20)
    print(f"\nChunked text into {len(chunks)} chunks")
