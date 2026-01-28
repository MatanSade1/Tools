"""
Query Validator Module

Validates SQL queries to ensure they are:
1. SELECT statements only (no DDL/DML)
2. Only query the allowed ua_cohort table
3. Safe from SQL injection
"""

import re
import logging
from typing import Tuple

import sqlparse
from sqlparse.sql import IdentifierList, Identifier, Where, Parenthesis
from sqlparse.tokens import Keyword, DML

logger = logging.getLogger(__name__)

# Allowed table (fully qualified)
ALLOWED_TABLE = "yotam-395120.peerplay.ua_cohort"

# Blocked SQL keywords (anything that modifies data or schema)
BLOCKED_KEYWORDS = {
    'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER', 'TRUNCATE',
    'REPLACE', 'MERGE', 'GRANT', 'REVOKE', 'EXEC', 'EXECUTE', 'CALL',
    'SET', 'COMMIT', 'ROLLBACK', 'SAVEPOINT', 'LOCK', 'UNLOCK',
    'LOAD', 'COPY', 'EXPORT', 'INTO'  # INTO can be used for INSERT INTO
}

# Blocked patterns (prevent various injection attempts)
BLOCKED_PATTERNS = [
    r';\s*(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE)',  # Multiple statements with DDL/DML
    r'--',  # SQL comments (potential injection)
    r'/\*',  # Block comments
    r'INFORMATION_SCHEMA',  # Metadata queries
    r'__TABLES__',  # BigQuery internal tables
    r'SYSTEM\.',  # System tables
]


class QueryValidator:
    """Validates SQL queries for safety and compliance."""
    
    def __init__(self, allowed_table: str = ALLOWED_TABLE):
        """
        Initialize the validator.
        
        Args:
            allowed_table: The only table that queries are allowed to access
        """
        self.allowed_table = allowed_table
        self.allowed_table_patterns = self._build_table_patterns(allowed_table)
    
    def _build_table_patterns(self, table: str) -> list:
        """Build regex patterns for matching the allowed table."""
        # Handle various ways the table might be referenced
        patterns = []
        
        # Full qualified name with backticks: `yotam-395120.peerplay.ua_cohort`
        escaped = re.escape(table)
        patterns.append(rf'`{escaped}`')
        
        # Full qualified name without backticks
        patterns.append(escaped)
        
        # Just the table name with optional dataset
        parts = table.split('.')
        if len(parts) == 3:
            project, dataset, table_name = parts
            # dataset.table
            patterns.append(rf'`?{re.escape(dataset)}\.{re.escape(table_name)}`?')
            # just table
            patterns.append(rf'\b{re.escape(table_name)}\b')
        
        return patterns
    
    def validate(self, sql: str) -> Tuple[bool, str]:
        """
        Validate a SQL query.
        
        Args:
            sql: The SQL query to validate
            
        Returns:
            Tuple of (is_valid, error_message)
            If valid, error_message will be empty
        """
        if not sql or not sql.strip():
            return False, "Empty query"
        
        sql = sql.strip()
        
        # Check 1: Blocked patterns
        for pattern in BLOCKED_PATTERNS:
            if re.search(pattern, sql, re.IGNORECASE):
                return False, f"Query contains blocked pattern: {pattern}"
        
        # Check 2: Parse and validate statement type
        try:
            parsed = sqlparse.parse(sql)
            if not parsed:
                return False, "Could not parse SQL query"
            
            # We only allow single statements
            if len(parsed) > 1:
                return False, "Multiple SQL statements are not allowed"
            
            statement = parsed[0]
            
            # Get statement type
            statement_type = statement.get_type()
            
            if statement_type != 'SELECT':
                return False, f"Only SELECT statements are allowed, got: {statement_type}"
            
        except Exception as e:
            logger.warning(f"SQL parse error: {e}")
            # Fall back to regex-based validation
            pass
        
        # Check 3: Verify it starts with SELECT (case-insensitive)
        sql_upper = sql.upper().strip()
        
        # Allow WITH clauses (CTEs) before SELECT
        if not sql_upper.startswith('SELECT') and not sql_upper.startswith('WITH'):
            return False, "Query must start with SELECT or WITH clause"
        
        # Check 4: Verify no blocked keywords at statement level
        # Split by whitespace and check first tokens
        tokens = sql_upper.split()
        
        for i, token in enumerate(tokens):
            # Clean token of punctuation
            clean_token = re.sub(r'[^\w]', '', token)
            
            if clean_token in BLOCKED_KEYWORDS:
                # Check if it's a legitimate keyword use
                # INTO is blocked because of INSERT INTO, but can appear in legitimate contexts
                if clean_token == 'INTO':
                    # Check if preceded by INSERT
                    for j in range(max(0, i-5), i):
                        if 'INSERT' in tokens[j].upper():
                            return False, "INSERT INTO statements are not allowed"
                else:
                    return False, f"Blocked keyword detected: {clean_token}"
        
        # Check 5: Verify table references
        table_valid, table_error = self._validate_table_references(sql)
        if not table_valid:
            return False, table_error
        
        # Check 6: Look for potential injection in string literals
        injection_valid, injection_error = self._check_injection_attempts(sql)
        if not injection_valid:
            return False, injection_error
        
        logger.info(f"Query validation passed: {sql[:100]}...")
        return True, ""
    
    def _validate_table_references(self, sql: str) -> Tuple[bool, str]:
        """Validate that only the allowed table is referenced."""
        # Extract all potential table references
        # This is a simplified approach - look for FROM and JOIN clauses
        
        sql_upper = sql.upper()
        
        # Find FROM clauses
        from_pattern = r'\bFROM\s+([`\w\-\.]+(?:\s+(?:AS\s+)?[\w]+)?)'
        join_pattern = r'\bJOIN\s+([`\w\-\.]+(?:\s+(?:AS\s+)?[\w]+)?)'
        
        tables_found = []
        
        for pattern in [from_pattern, join_pattern]:
            matches = re.findall(pattern, sql, re.IGNORECASE)
            for match in matches:
                # Extract just the table name (before AS or alias)
                table_ref = match.split()[0].strip('`')
                tables_found.append(table_ref)
        
        # Check each table reference
        for table_ref in tables_found:
            table_ref_lower = table_ref.lower()
            allowed_lower = self.allowed_table.lower()
            
            # Check if it matches the allowed table
            is_allowed = (
                table_ref_lower == allowed_lower or
                table_ref_lower == allowed_lower.replace('`', '') or
                table_ref_lower.endswith('.ua_cohort') or
                table_ref_lower == 'ua_cohort'
            )
            
            if not is_allowed:
                # It might be a CTE reference - check if it's defined in the query
                cte_pattern = rf'\bWITH\s+{re.escape(table_ref)}\s+AS\s*\('
                if not re.search(cte_pattern, sql, re.IGNORECASE):
                    return False, f"Access to table '{table_ref}' is not allowed. Only 'ua_cohort' is permitted."
        
        # Also check for subqueries referencing other tables
        subquery_tables = self._extract_subquery_tables(sql)
        for table_ref in subquery_tables:
            table_ref_lower = table_ref.lower()
            allowed_lower = self.allowed_table.lower()
            
            is_allowed = (
                table_ref_lower == allowed_lower or
                table_ref_lower == allowed_lower.replace('`', '') or
                table_ref_lower.endswith('.ua_cohort') or
                table_ref_lower == 'ua_cohort'
            )
            
            if not is_allowed:
                # Check if it's a CTE
                cte_pattern = rf'\bWITH\s+[\w\s,]*\b{re.escape(table_ref)}\b\s+AS\s*\('
                if not re.search(cte_pattern, sql, re.IGNORECASE):
                    return False, f"Subquery access to table '{table_ref}' is not allowed."
        
        return True, ""
    
    def _extract_subquery_tables(self, sql: str) -> list:
        """Extract table references from subqueries."""
        tables = []
        
        # Find all subqueries (content within parentheses that start with SELECT)
        # This is a simplified approach
        subquery_pattern = r'\(\s*SELECT[^()]*\bFROM\s+([`\w\-\.]+)'
        matches = re.findall(subquery_pattern, sql, re.IGNORECASE)
        
        for match in matches:
            tables.append(match.strip('`'))
        
        return tables
    
    def _check_injection_attempts(self, sql: str) -> Tuple[bool, str]:
        """Check for common SQL injection patterns."""
        injection_patterns = [
            r"'\s*OR\s+'1'\s*=\s*'1",  # OR '1'='1'
            r"'\s*OR\s+1\s*=\s*1",  # OR 1=1
            r";\s*DROP\s+",  # ; DROP
            r"UNION\s+SELECT\s+",  # UNION SELECT (we don't allow external data)
            r"SLEEP\s*\(",  # Time-based attacks
            r"BENCHMARK\s*\(",  # Time-based attacks
            r"WAITFOR\s+DELAY",  # Time-based attacks
            r"pg_sleep",  # PostgreSQL time-based
        ]
        
        for pattern in injection_patterns:
            if re.search(pattern, sql, re.IGNORECASE):
                return False, f"Potential SQL injection detected"
        
        return True, ""
    
    def sanitize_for_logging(self, sql: str) -> str:
        """Sanitize SQL for safe logging (remove potential sensitive data)."""
        # Remove string literals content
        sanitized = re.sub(r"'[^']*'", "'<REDACTED>'", sql)
        return sanitized


def validate_query(sql: str) -> Tuple[bool, str]:
    """
    Convenience function to validate a query.
    
    Args:
        sql: SQL query to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    validator = QueryValidator()
    return validator.validate(sql)



