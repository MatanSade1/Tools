"""
Claude LLM client for generating BigQuery SQL queries from natural language.
"""

import os
from typing import List, Dict, Optional
from anthropic import Anthropic
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class LLMClient:
    """Client for interacting with Claude AI to generate SQL queries."""
    
    def __init__(self, model: str = "claude-3-opus-20240229", 
                 temperature: float = 0.1, max_tokens: int = 2000):
        """
        Initialize Claude client.
        
        Args:
            model: Claude model name
            temperature: Sampling temperature (0-1, lower is more deterministic)
            max_tokens: Maximum tokens in response
        """
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
        
        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
    
    def generate_query(self, user_request: str, context_chunks: List[Dict],
                      verbose: bool = False) -> Dict[str, str]:
        """
        Generate a BigQuery SQL query from user request and context.
        
        Args:
            user_request: Natural language query request
            context_chunks: Retrieved context from vector DB
            verbose: Whether to print detailed info
            
        Returns:
            Dict with 'query' and 'explanation' keys
        """
        # Build context string from chunks
        context_parts = []
        for i, chunk in enumerate(context_chunks, 1):
            metadata = chunk.get('metadata', {})
            content = metadata.get('content', '')
            source = metadata.get('source', 'Unknown')
            title = metadata.get('title', 'Untitled')
            score = chunk.get('score', 0)
            
            context_parts.append(
                f"[Context {i} - Source: {source}, Section: {title}, Relevance: {score:.2f}]\n{content}\n"
            )
        
        context_str = "\n---\n".join(context_parts)
        
        # Build system prompt
        system_prompt = """You are an expert BigQuery SQL developer for an analytics organization. Your job is to convert natural language requests into correct, optimized BigQuery SQL queries.

You have access to organizational documentation that describes:
- Table schemas and their proper usage
- Query guardrails and best practices (partitioning, clustering)
- Organizational metric definitions
- Event names and parameter meanings

CRITICAL RULES:
1. ALWAYS use partition columns in WHERE clauses (typically event_date or signup_date)
2. ALWAYS follow clustering order in WHERE clauses for performance
3. Use the correct table for the task (raw vs aggregated vs dimensional)
4. Follow organizational naming conventions and metric definitions
5. Include appropriate date range filters
6. Write valid BigQuery SQL syntax (not standard SQL)
7. Add comments explaining complex logic
8. Consider query cost and performance

OUTPUT FORMAT:
Return a JSON object with two keys:
{
  "query": "SELECT ... -- your SQL query here",
  "explanation": "Brief explanation of what the query does and why you made specific choices"
}"""

        # Build user message
        user_message = f"""Based on the following organizational context, generate a BigQuery SQL query for this request:

USER REQUEST:
{user_request}

ORGANIZATIONAL CONTEXT:
{context_str}

Generate a complete, executable BigQuery SQL query that follows all organizational best practices and guardrails mentioned in the context. Include explanatory comments in the SQL."""

        if verbose:
            print("\n=== System Prompt ===")
            print(system_prompt)
            print("\n=== User Message ===")
            print(user_message)
        
        # Call Claude API
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_message}
            ]
        )
        
        # Parse response
        response_text = response.content[0].text.strip()
        
        # Try to extract JSON if present
        if "```json" in response_text:
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            response_text = response_text[json_start:json_end].strip()
        
        # Try to parse as JSON
        try:
            import json
            result = json.loads(response_text)
            return {
                'query': result.get('query', ''),
                'explanation': result.get('explanation', '')
            }
        except json.JSONDecodeError:
            # If not JSON, treat entire response as query
            return {
                'query': response_text,
                'explanation': 'Generated query based on organizational context'
            }
    
    def test_connection(self) -> bool:
        """Test if Claude API connection works."""
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=100,
                messages=[
                    {"role": "user", "content": "Say 'Connection successful' if you can read this."}
                ]
            )
            return "successful" in response.content[0].text.lower()
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False


if __name__ == "__main__":
    # Test LLM client
    client = LLMClient()
    
    # Test connection
    if client.test_connection():
        print("✓ Claude API connection successful")
    else:
        print("✗ Claude API connection failed")
    
    # Test query generation with mock context
    mock_context = [
        {
            'score': 0.85,
            'metadata': {
                'source': 'tables_schema.md',
                'title': 'events_daily_summary',
                'content': 'Table for daily aggregated events. Partitioned by event_date.'
            }
        }
    ]
    
    result = client.generate_query(
        "Show me daily active users for last 7 days",
        mock_context
    )
    
    print("\n=== Generated Query ===")
    print(result['query'])
    print("\n=== Explanation ===")
    print(result['explanation'])
