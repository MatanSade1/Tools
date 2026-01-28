"""
Query Generator Module

Uses Claude Opus 4.5 to generate SQL queries from natural language questions
about the UA cohort data.
"""

import logging
from typing import Tuple, Optional
from datetime import datetime

import anthropic

logger = logging.getLogger(__name__)

# UA Cohort table schema for Claude context
UA_COHORT_SCHEMA = """
Table: yotam-395120.peerplay.ua_cohort

This table contains User Acquisition (UA) cohort data for marketing analytics.

DIMENSIONS (use for filtering and grouping):
- install_date: DATE - The date users installed the app
- week: DATE - The week of installation (use for weekly aggregations)
- month: DATE - The month of installation (use for monthly aggregations)  
- year: INT64 - The year of installation
- platform: STRING - 'Android' or 'Apple' (iOS)
- country: STRING - Two-letter country code (e.g., 'US', 'GB')
- mediasource: STRING - Media source / ad network (e.g., 'applovin_int', 'googleadwords_int', 'Facebook Ads', 'unityads_int', 'ironsource_int')
- campaign_name: STRING - Campaign name
- media_type: STRING - Type of media ('Offerwalls', 'Non-Offerwalls', 'Organic', etc.)
- is_test_campaign: BOOLEAN - Whether this is a test campaign

CORE METRICS:
- installs: INT64 - Number of installs
- cost: FLOAT64 - Marketing cost (USD)
- rt_cost: FLOAT64 - Retargeting cost (USD)

ROAS METRICS (Return on Ad Spend):
For each cohort day D, there are columns for net revenue and ROAS:
- d0_total_net_revenue, d1_total_net_revenue, d3_total_net_revenue, d7_total_net_revenue, 
  d14_total_net_revenue, d21_total_net_revenue, d30_total_net_revenue, d45_total_net_revenue,
  d60_total_net_revenue, d75_total_net_revenue, d90_total_net_revenue, d120_total_net_revenue,
  d150_total_net_revenue, d180_total_net_revenue, d210_total_net_revenue, d240_total_net_revenue,
  d270_total_net_revenue, d300_total_net_revenue, d330_total_net_revenue, d360_total_net_revenue
- ltv_total_net_revenue: FLOAT64 - Lifetime net revenue

To calculate ROAS: SUM(d{X}_total_net_revenue) / NULLIF(SUM(cost), 0)
Example: D7 ROAS = SUM(d7_total_net_revenue) / NULLIF(SUM(cost), 0)

FTD METRICS (First Time Depositors / Payers):
- d0_ftds, d1_ftds, d3_ftds, d7_ftds, d14_ftds, d21_ftds, d30_ftds, d45_ftds, d60_ftds, 
  d75_ftds, d90_ftds, d120_ftds, d150_ftds, d180_ftds, d210_ftds, d240_ftds, d270_ftds, 
  d300_ftds, d330_ftds, d360_ftds
- ltv_ftds: INT64 - Lifetime first time depositors

To calculate FTD rate: SUM(d{X}_ftds) / NULLIF(SUM(installs), 0) * 100

RETENTION METRICS:
- d0_retention, d1_retention, d3_retention, d7_retention, d14_retention, d21_retention,
  d30_retention, d45_retention, d60_retention, d75_retention, d90_retention, d120_retention,
  d150_retention, d180_retention, d210_retention, d240_retention, d270_retention, d300_retention,
  d330_retention, d360_retention

To calculate Retention rate: SUM(d{X}_retention) / NULLIF(SUM(installs), 0) * 100

PAYER RETENTION METRICS:
- d0_payers_retention, d1_payers_retention, d3_payers_retention, d7_payers_retention, etc.

To calculate Payer Retention rate: SUM(d{X}_payers_retention) / NULLIF(SUM(ltv_ftds), 0) * 100

ADDITIONAL COLUMNS:
- net_share: STRING - Net share type ('fixed_15', 'actual')
- d{X}_total_net_revenue_15_pct: FLOAT64 - Net revenue with 15% fixed net share

IMPORTANT NOTES:
1. Always use NULLIF to prevent division by zero
2. For cost calculations, typically use just 'cost' column (not rt_cost)
3. When calculating averages across time periods, use SUM() / NULLIF(COUNT(DISTINCT), 0)
4. ROAS is typically expressed as a decimal (e.g., 0.5 for 50% ROAS)
5. Use install_date < CURRENT_DATE() to exclude incomplete current day data
6. For monthly data, group by 'month' column
7. For weekly data, group by 'week' column
"""

EXAMPLE_QUERIES = """
EXAMPLE QUERIES:

1. "Give me the total cost per month from Jan 2024 till today"
SELECT 
    month,
    SUM(cost) as total_cost
FROM `yotam-395120.peerplay.ua_cohort`
WHERE install_date >= '2024-01-01' 
    AND install_date < CURRENT_DATE()
GROUP BY month
ORDER BY month

2. "Give the cost split per platform for the last month"
SELECT 
    platform,
    SUM(cost) as total_cost
FROM `yotam-395120.peerplay.ua_cohort`
WHERE install_date >= DATE_SUB(DATE_TRUNC(CURRENT_DATE(), MONTH), INTERVAL 1 MONTH)
    AND install_date < DATE_TRUNC(CURRENT_DATE(), MONTH)
GROUP BY platform
ORDER BY total_cost DESC

3. "Give me the spent we will have till the end of the month according the avg daily spent we had so far"
WITH daily_avg AS (
    SELECT 
        SUM(cost) / NULLIF(COUNT(DISTINCT install_date), 0) as avg_daily_cost
    FROM `yotam-395120.peerplay.ua_cohort`
    WHERE install_date >= DATE_TRUNC(CURRENT_DATE(), MONTH)
        AND install_date < CURRENT_DATE()
),
days_info AS (
    SELECT 
        DATE_DIFF(LAST_DAY(CURRENT_DATE()), DATE_TRUNC(CURRENT_DATE(), MONTH), DAY) + 1 as days_in_month,
        DATE_DIFF(CURRENT_DATE(), DATE_TRUNC(CURRENT_DATE(), MONTH), DAY) as days_passed
)
SELECT 
    ROUND(avg_daily_cost * days_in_month, 2) as projected_monthly_cost
FROM daily_avg, days_info

4. "Give me the avg roas for offerwalls per every week in the last 7 weeks"
SELECT 
    week,
    SUM(d7_total_net_revenue) / NULLIF(SUM(cost), 0) as avg_d7_roas
FROM `yotam-395120.peerplay.ua_cohort`
WHERE media_type = 'Offerwalls'
    AND install_date >= DATE_SUB(DATE_TRUNC(CURRENT_DATE(), WEEK), INTERVAL 7 WEEK)
    AND install_date < CURRENT_DATE()
GROUP BY week
ORDER BY week

5. "Give me the ltv roas for september month"
SELECT 
    SUM(ltv_total_net_revenue) / NULLIF(SUM(cost), 0) as ltv_roas
FROM `yotam-395120.peerplay.ua_cohort`
WHERE month = '2024-09-01'

6. "Give the avg D7 Retention in the last 10 weeks"
SELECT 
    week,
    SUM(d7_retention) / NULLIF(SUM(installs), 0) * 100 as d7_retention_pct
FROM `yotam-395120.peerplay.ua_cohort`
WHERE install_date >= DATE_SUB(DATE_TRUNC(CURRENT_DATE(), WEEK), INTERVAL 10 WEEK)
    AND install_date < CURRENT_DATE()
GROUP BY week
ORDER BY week
"""


class QueryGenerator:
    """Generates SQL queries from natural language using Claude Opus 4.5."""
    
    def __init__(self, api_key: str):
        """Initialize with Anthropic API key."""
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-20250514"  # Using Claude Sonnet 4 (latest)
    
    def generate_query(self, question: str) -> Tuple[Optional[str], str]:
        """
        Generate a SQL query from a natural language question.
        
        Args:
            question: Natural language question about UA cohort data
            
        Returns:
            Tuple of (sql_query, explanation)
            If generation fails, sql_query will be None and explanation will contain the error
        """
        try:
            current_date = datetime.now().strftime("%Y-%m-%d")
            
            system_prompt = f"""You are a SQL expert that generates BigQuery SQL queries for UA (User Acquisition) cohort data analysis.

{UA_COHORT_SCHEMA}

{EXAMPLE_QUERIES}

CURRENT DATE: {current_date}

RULES:
1. ONLY generate SELECT statements - no INSERT, UPDATE, DELETE, DROP, or any DDL/DML
2. ONLY query the table: yotam-395120.peerplay.ua_cohort
3. Always use backticks around the full table name: `yotam-395120.peerplay.ua_cohort`
4. Use clear column aliases for calculated fields
5. Handle division by zero with NULLIF
6. For date filtering, consider the current date context
7. Always ORDER BY results appropriately
8. Keep queries efficient - avoid unnecessary complexity
9. If the question is unclear or cannot be answered with this table, explain why

RESPONSE FORMAT:
Always respond with a JSON object containing:
- "sql": The SQL query (or null if cannot generate)
- "explanation": Brief explanation of what the query does or why it couldn't be generated"""

            user_message = f"""Generate a SQL query to answer this question:

"{question}"

Remember: Only SELECT queries on the ua_cohort table are allowed."""

            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_message}
                ]
            )
            
            # Parse response
            response_text = response.content[0].text
            
            # Try to extract JSON from response
            import json
            import re
            
            # Look for JSON in the response
            json_match = re.search(r'\{[^{}]*"sql"[^{}]*\}', response_text, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group())
                    sql = result.get("sql")
                    explanation = result.get("explanation", "Query generated successfully")
                    return sql, explanation
                except json.JSONDecodeError:
                    pass
            
            # Fallback: try to extract SQL directly
            sql_match = re.search(r'```sql\s*(.*?)\s*```', response_text, re.DOTALL | re.IGNORECASE)
            if sql_match:
                sql = sql_match.group(1).strip()
                return sql, "Query extracted from response"
            
            # Another fallback: look for SELECT statement
            select_match = re.search(r'(SELECT\s+.*?(?:;|$))', response_text, re.DOTALL | re.IGNORECASE)
            if select_match:
                sql = select_match.group(1).strip().rstrip(';')
                return sql, "Query extracted from response"
            
            # If nothing found, return error
            logger.warning(f"Could not extract SQL from response: {response_text[:500]}")
            return None, f"Could not generate a valid SQL query. Claude response: {response_text[:200]}"
        
        except anthropic.APIError as e:
            logger.error(f"Anthropic API error: {e}")
            return None, f"API error: {str(e)}"
        
        except Exception as e:
            logger.exception(f"Error generating query: {e}")
            return None, f"Error generating query: {str(e)}"



