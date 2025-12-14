# =============================================================================
# AUTHENTICATION CODE - DO NOT MODIFY
# =============================================================================
import streamlit as st

# Must be the first Streamlit command
st.set_page_config(
    page_title="UA Analytics Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

import os
import requests
from google_auth_oauthlib.flow import Flow

ALLOWED_DOMAINS = ['peerplay.com', 'peerplay.io']

def get_secret(key):
    try:
        if hasattr(st, 'secrets') and key in st.secrets:
            return st.secrets[key]
    except:
        pass
    return os.environ.get(key)

def check_authorization(email):
    if not email:
        return False
    domain = email.split('@')[-1].lower() if '@' in email else ''
    return domain in [d.lower() for d in ALLOWED_DOMAINS]

def get_google_oauth_url():
    client_id = get_secret('GOOGLE_OAUTH_CLIENT_ID')
    client_secret = get_secret('GOOGLE_OAUTH_CLIENT_SECRET')
    redirect_uri = get_secret('STREAMLIT_REDIRECT_URI') or "http://localhost:8501/"
    if not client_id or not client_secret:
        return None
    flow = Flow.from_client_config(
        {"web": {"client_id": client_id, "client_secret": client_secret,
                 "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                 "token_uri": "https://oauth2.googleapis.com/token",
                 "redirect_uris": [redirect_uri]}},
        scopes=["openid", "https://www.googleapis.com/auth/userinfo.email",
                "https://www.googleapis.com/auth/userinfo.profile"],
        redirect_uri=redirect_uri)
    authorization_url, _ = flow.authorization_url(access_type='offline', prompt='consent')
    return authorization_url

def authenticate_user():
    if st.session_state.get('authenticated'):
        return st.session_state.get('user_email')
    code = st.query_params.get('code')
    if code:
        try:
            client_id = get_secret('GOOGLE_OAUTH_CLIENT_ID')
            client_secret = get_secret('GOOGLE_OAUTH_CLIENT_SECRET')
            redirect_uri = get_secret('STREAMLIT_REDIRECT_URI') or "http://localhost:8501/"
            flow = Flow.from_client_config(
                {"web": {"client_id": client_id, "client_secret": client_secret,
                         "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                         "token_uri": "https://oauth2.googleapis.com/token",
                         "redirect_uris": [redirect_uri]}},
                scopes=["openid", "https://www.googleapis.com/auth/userinfo.email",
                        "https://www.googleapis.com/auth/userinfo.profile"],
                redirect_uri=redirect_uri)
            flow.fetch_token(code=code)
            user_info = requests.get('https://www.googleapis.com/oauth2/v2/userinfo',
                                     headers={'Authorization': f'Bearer {flow.credentials.token}'}).json()
            if check_authorization(user_info.get('email', '')):
                st.session_state.authenticated = True
                st.session_state.user_email = user_info.get('email', '')
                st.session_state.user_name = user_info.get('name', '')
                st.query_params.clear()
                st.rerun()
            else:
                st.error("❌ Access Denied - Peerplay employees only")
                st.stop()
        except Exception as e:
            st.error(f"Auth error: {e}")
            st.stop()
    auth_url = get_google_oauth_url()
    if auth_url:
        st.markdown(f'''<div style="text-align:center;padding:100px;">
            <h1>🔒 Login Required</h1>
            <p>Restricted to Peerplay employees</p><br>
            <a href="{auth_url}" style="background:#4285f4;color:white;padding:15px 30px;
               border-radius:10px;text-decoration:none;font-weight:bold;">Sign in with Google</a>
        </div>''', unsafe_allow_html=True)
        st.stop()
    return None

def is_oauth_configured():
    return get_secret('GOOGLE_OAUTH_CLIENT_ID') is not None

def show_user_sidebar():
    if st.session_state.get('authenticated'):
        st.sidebar.markdown(f"**👤 {st.session_state.get('user_name', 'User')}**")
        if st.sidebar.button("🚪 Logout"):
            st.session_state.clear()
            st.rerun()
        st.sidebar.markdown("---")
# =============================================================================
# END AUTHENTICATION CODE
# =============================================================================

import pandas as pd
from google.cloud import bigquery
from datetime import datetime, date

# BigQuery configuration
PROJECT_ID = 'yotam-395120'
DATASET_ID = 'peerplay'
TABLE_ID = 'ua_cohort'
TABLE_FULL = f'{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}'

# Initialize BigQuery client
@st.cache_resource
def get_bigquery_client():
    return bigquery.Client(project=PROJECT_ID)

# Available dimensions
# Note: install_week, install_month, install_year may need to be derived from install_date
# If they don't exist as separate columns, we'll derive them in the query
AVAILABLE_DIMENSIONS = {
    'platform': 'platform',
    'country': 'country',
    'mediasource': 'mediasource',
    'campaign': 'campaign_name',
    'install_date': 'install_date',
    'install_week': 'week',
    'install_month': 'month',
    'install_year': 'year'
}

# Day columns (d0, d1, d3, d7, d14, d21, d30, d45, d60, d75, d90, d120, d150, d180, d210, d240, d270, d300, d330, d360)
DAY_COLUMNS = [0, 1, 3, 7, 14, 21, 30, 45, 60, 75, 90, 120, 150, 180, 210, 240, 270, 300, 330, 360]

def build_where_clause(filters):
    """Build WHERE clause from filters"""
    conditions = []
    
    if filters.get('install_date_start') and filters.get('install_date_end'):
        conditions.append(f"install_date BETWEEN '{filters['install_date_start']}' AND '{filters['install_date_end']}'")
    
    if filters.get('platform'):
        platforms_str = "', '".join(map(str, filters['platform']))
        conditions.append(f"platform IN ('{platforms_str}')")
    
    if filters.get('country'):
        countries_str = "', '".join(map(str, filters['country']))
        conditions.append(f"country IN ('{countries_str}')")
    
    if filters.get('media_source'):
        sources_str = "', '".join(map(str, filters['media_source']))
        conditions.append(f"mediasource IN ('{sources_str}')")
    
    if filters.get('campaign_name'):
        campaigns_str = "', '".join(map(str, filters['campaign_name']))
        conditions.append(f"campaign_name IN ('{campaigns_str}')")
    
    if filters.get('media_type'):
        types_str = "', '".join(map(str, filters['media_type']))
        conditions.append(f"media_type IN ('{types_str}')")
    
    if filters.get('is_test_campaign') is not None and filters.get('is_test_campaign') != 'All':
        is_test_val = 'true' if filters['is_test_campaign'] else 'false'
        conditions.append(f"is_test_campaign = {is_test_val}")
    
    return " AND ".join(conditions) if conditions else "1=1"

def get_filter_options(client, column, filters):
    """Get distinct values for a column under current filters."""
    where_clause = build_where_clause(filters)
    query = f"""
    SELECT DISTINCT {column} as value
    FROM `{TABLE_FULL}`
    WHERE {where_clause} AND {column} IS NOT NULL
    ORDER BY value ASC
    """
    df = client.query(query).to_dataframe()
    return df['value'].tolist() if not df.empty else []

def build_cost_expression(add_rt_cost):
    """Build cost expression based on RT cost toggle"""
    if add_rt_cost:
        return "COALESCE(cost, 0) + COALESCE(rt_cost, 0)"
    else:
        return "COALESCE(cost, 0)"

def build_group_by_clause(selected_dimensions):
    """Build GROUP BY clause from selected dimensions"""
    if not selected_dimensions:
        return ""
    dimension_cols = [AVAILABLE_DIMENSIONS[dim] for dim in selected_dimensions]
    return ", ".join(dimension_cols)

def build_order_by_clause(selected_dimensions):
    """Build ORDER BY clause from selected dimensions (DESC)"""
    if not selected_dimensions:
        return ""
    dimension_cols = [AVAILABLE_DIMENSIONS[dim] for dim in selected_dimensions]
    return ", ".join([f"{col} DESC" for col in dimension_cols])

@st.cache_data(ttl=60)
def query_roas_table(_client, filters_tuple, selected_dimensions_tuple, add_rt_cost):
    """Query ROAS table data"""
    filters = dict(filters_tuple)
    selected_dimensions = list(selected_dimensions_tuple)
    where_clause = build_where_clause(filters)
    group_by_clause = build_group_by_clause(selected_dimensions)
    order_by_clause = build_order_by_clause(selected_dimensions)
    cost_expr = build_cost_expression(add_rt_cost)
    
    # Build dimension selects
    dimension_selects = []
    if selected_dimensions:
        for dim in selected_dimensions:
            dimension_selects.append(f"{AVAILABLE_DIMENSIONS[dim]} as {dim}")
    
    dimensions_str = ", ".join(dimension_selects) if dimension_selects else ""
    dimensions_comma = ", " if dimensions_str else ""
    
    # Build metric selects
    metric_selects = [
        f"SUM({cost_expr}) as cost",
        "SUM(installs) as installs",
        f"SUM({cost_expr}) / NULLIF(SUM(installs), 0) as cpi",
        "MIN(DATE_DIFF(CURRENT_DATE(), install_date, DAY)) as diff_from_today",
        f"SUM({cost_expr}) / NULLIF(COUNT(DISTINCT install_date), 0) as avg_daily_cost",
        "SUM(installs) / NULLIF(COUNT(DISTINCT install_date), 0) as avg_daily_installs"
    ]
    
    # Add ROAS metrics
    for day in DAY_COLUMNS:
        metric_selects.append(f"SUM(d{day}_total_net_revenue) / NULLIF(SUM({cost_expr}), 0) as d{day}_roas")
        metric_selects.append(f"SUM(d{day}_total_net_revenue) as d{day}_total_net_revenue")
    
    metric_selects.append(f"SUM(ltv_total_net_revenue) / NULLIF(SUM({cost_expr}), 0) as ltv_roas")
    metric_selects.append("SUM(ltv_total_net_revenue) as ltv_total_net_revenue")
    
    metrics_str = ", ".join(metric_selects)
    
    group_by_sql = f"GROUP BY {group_by_clause}" if group_by_clause else ""
    order_by_sql = f"ORDER BY {order_by_clause}" if order_by_clause else ""
    
    query = f"""
    SELECT 
        {dimensions_str}{dimensions_comma}{metrics_str}
    FROM `{TABLE_FULL}`
    WHERE {where_clause}
    {group_by_sql}
    {order_by_sql}
    """
    
    return _client.query(query).to_dataframe()

@st.cache_data(ttl=60)
def query_ftds_table(_client, filters_tuple, selected_dimensions_tuple, add_rt_cost):
    """Query FTDs table data"""
    filters = dict(filters_tuple)
    selected_dimensions = list(selected_dimensions_tuple)
    """Query FTDs table data"""
    where_clause = build_where_clause(filters)
    group_by_clause = build_group_by_clause(selected_dimensions)
    order_by_clause = build_order_by_clause(selected_dimensions)
    cost_expr = build_cost_expression(add_rt_cost)
    
    # Build dimension selects
    dimension_selects = []
    if selected_dimensions:
        for dim in selected_dimensions:
            dimension_selects.append(f"{AVAILABLE_DIMENSIONS[dim]} as {dim}")
    
    dimensions_str = ", ".join(dimension_selects) if dimension_selects else ""
    dimensions_comma = ", " if dimensions_str else ""
    
    # Build metric selects
    metric_selects = [
        f"SUM({cost_expr}) as cost",
        "SUM(installs) as installs",
        f"SUM({cost_expr}) / NULLIF(SUM(installs), 0) as cpi",
        "MIN(DATE_DIFF(CURRENT_DATE(), install_date, DAY)) as diff_from_today",
        f"SUM({cost_expr}) / NULLIF(COUNT(DISTINCT install_date), 0) as avg_daily_cost",
        "SUM(installs) / NULLIF(COUNT(DISTINCT install_date), 0) as avg_daily_installs"
    ]
    
    # Add FTD metrics
    for day in DAY_COLUMNS:
        metric_selects.append(f"SUM(d{day}_ftds) / NULLIF(SUM(installs), 0) * 100 as d{day}_ftd_pct")
        metric_selects.append(f"SUM(d{day}_ftds) as d{day}_ftds")
    
    metric_selects.append("SUM(ltv_ftds) / NULLIF(SUM(installs), 0) * 100 as ltv_ftd_pct")
    metric_selects.append("SUM(ltv_ftds) as ltv_ftds")
    
    metrics_str = ", ".join(metric_selects)
    
    group_by_sql = f"GROUP BY {group_by_clause}" if group_by_clause else ""
    order_by_sql = f"ORDER BY {order_by_clause}" if order_by_clause else ""
    
    query = f"""
    SELECT 
        {dimensions_str}{dimensions_comma}{metrics_str}
    FROM `{TABLE_FULL}`
    WHERE {where_clause}
    {group_by_sql}
    {order_by_sql}
    """
    
    return _client.query(query).to_dataframe()

@st.cache_data(ttl=60)
def query_retention_table(_client, filters_tuple, selected_dimensions_tuple, add_rt_cost):
    """Query Retention table data"""
    filters = dict(filters_tuple)
    selected_dimensions = list(selected_dimensions_tuple)
    """Query Retention table data"""
    where_clause = build_where_clause(filters)
    group_by_clause = build_group_by_clause(selected_dimensions)
    order_by_clause = build_order_by_clause(selected_dimensions)
    cost_expr = build_cost_expression(add_rt_cost)
    
    # Build dimension selects
    dimension_selects = []
    if selected_dimensions:
        for dim in selected_dimensions:
            dimension_selects.append(f"{AVAILABLE_DIMENSIONS[dim]} as {dim}")
    
    dimensions_str = ", ".join(dimension_selects) if dimension_selects else ""
    dimensions_comma = ", " if dimensions_str else ""
    
    # Build metric selects
    metric_selects = [
        f"SUM({cost_expr}) as cost",
        "SUM(installs) as installs",
        f"SUM({cost_expr}) / NULLIF(SUM(installs), 0) as cpi",
        "MIN(DATE_DIFF(CURRENT_DATE(), install_date, DAY)) as diff_from_today",
        f"SUM({cost_expr}) / NULLIF(COUNT(DISTINCT install_date), 0) as avg_daily_cost",
        "SUM(installs) / NULLIF(COUNT(DISTINCT install_date), 0) as avg_daily_installs"
    ]
    
    # Add Retention metrics
    for day in DAY_COLUMNS:
        metric_selects.append(f"SUM(d{day}_retention) / NULLIF(SUM(installs), 0) * 100 as d{day}_ret_pct")
        metric_selects.append(f"SUM(d{day}_retention) as d{day}_ret")
    
    metrics_str = ", ".join(metric_selects)
    
    group_by_sql = f"GROUP BY {group_by_clause}" if group_by_clause else ""
    order_by_sql = f"ORDER BY {order_by_clause}" if order_by_clause else ""
    
    query = f"""
    SELECT 
        {dimensions_str}{dimensions_comma}{metrics_str}
    FROM `{TABLE_FULL}`
    WHERE {where_clause}
    {group_by_sql}
    {order_by_sql}
    """
    
    return _client.query(query).to_dataframe()

@st.cache_data(ttl=60)
def query_payer_retention_table(_client, filters_tuple, selected_dimensions_tuple, add_rt_cost):
    """Query Payer Retention table data"""
    filters = dict(filters_tuple)
    selected_dimensions = list(selected_dimensions_tuple)
    where_clause = build_where_clause(filters)
    group_by_clause = build_group_by_clause(selected_dimensions)
    order_by_clause = build_order_by_clause(selected_dimensions)
    cost_expr = build_cost_expression(add_rt_cost)
    
    # Build dimension selects
    dimension_selects = []
    if selected_dimensions:
        for dim in selected_dimensions:
            dimension_selects.append(f"{AVAILABLE_DIMENSIONS[dim]} as {dim}")
    
    dimensions_str = ", ".join(dimension_selects) if dimension_selects else ""
    dimensions_comma = ", " if dimensions_str else ""
    
    # Build metric selects
    metric_selects = [
        f"SUM({cost_expr}) as cost",
        "SUM(installs) as installs",
        f"SUM({cost_expr}) / NULLIF(SUM(installs), 0) as cpi",
        "MIN(DATE_DIFF(CURRENT_DATE(), install_date, DAY)) as diff_from_today",
        f"SUM({cost_expr}) / NULLIF(COUNT(DISTINCT install_date), 0) as avg_daily_cost",
        "SUM(installs) / NULLIF(COUNT(DISTINCT install_date), 0) as avg_daily_installs",
        "SUM(ltv_ftds) as payers"
    ]
    
    # Add Payer Retention metrics
    for day in DAY_COLUMNS:
        metric_selects.append(f"SUM(d{day}_payers_retention) / NULLIF(SUM(ltv_ftds), 0) * 100 as d{day}_payers_ret_pct")
        metric_selects.append(f"SUM(d{day}_payers_retention) as d{day}_payers_retention")
    
    metrics_str = ", ".join(metric_selects)
    
    group_by_sql = f"GROUP BY {group_by_clause}" if group_by_clause else ""
    order_by_sql = f"ORDER BY {order_by_clause}" if order_by_clause else ""
    
    query = f"""
    SELECT 
        {dimensions_str}{dimensions_comma}{metrics_str}
    FROM `{TABLE_FULL}`
    WHERE {where_clause}
    {group_by_sql}
    {order_by_sql}
    """
    
    return _client.query(query).to_dataframe()

@st.cache_data(ttl=60)
def query_cpa_table(_client, filters_tuple, selected_dimensions_tuple, add_rt_cost):
    """Query CPA table data"""
    filters = dict(filters_tuple)
    selected_dimensions = list(selected_dimensions_tuple)
    """Query CPA table data"""
    where_clause = build_where_clause(filters)
    group_by_clause = build_group_by_clause(selected_dimensions)
    order_by_clause = build_order_by_clause(selected_dimensions)
    cost_expr = build_cost_expression(add_rt_cost)
    
    # Build dimension selects
    dimension_selects = []
    if selected_dimensions:
        for dim in selected_dimensions:
            dimension_selects.append(f"{AVAILABLE_DIMENSIONS[dim]} as {dim}")
    
    dimensions_str = ", ".join(dimension_selects) if dimension_selects else ""
    dimensions_comma = ", " if dimensions_str else ""
    
    # Build metric selects
    metric_selects = [
        f"SUM({cost_expr}) as cost",
        "SUM(installs) as installs",
        f"SUM({cost_expr}) / NULLIF(SUM(installs), 0) as cpi",
        "MIN(DATE_DIFF(CURRENT_DATE(), install_date, DAY)) as diff_from_today",
        f"SUM({cost_expr}) / NULLIF(COUNT(DISTINCT install_date), 0) as avg_daily_cost",
        "SUM(installs) / NULLIF(COUNT(DISTINCT install_date), 0) as avg_daily_installs"
    ]
    
    # Add CPA metrics (also include ftds for summary calculation)
    for day in DAY_COLUMNS:
        metric_selects.append(f"SUM({cost_expr}) / NULLIF(SUM(d{day}_ftds), 0) as d{day}_cpa")
        metric_selects.append(f"SUM(d{day}_ftds) as d{day}_ftds")  # Include for summary calculation
    
    metrics_str = ", ".join(metric_selects)
    
    group_by_sql = f"GROUP BY {group_by_clause}" if group_by_clause else ""
    order_by_sql = f"ORDER BY {order_by_clause}" if order_by_clause else ""
    
    query = f"""
    SELECT 
        {dimensions_str}{dimensions_comma}{metrics_str}
    FROM `{TABLE_FULL}`
    WHERE {where_clause}
    {group_by_sql}
    {order_by_sql}
    """
    
    return _client.query(query).to_dataframe()

def filters_to_tuple(filters):
    """Convert filters dict to a hashable tuple for caching."""
    items = []
    for k, v in sorted(filters.items()):
        if v is None:
            items.append((k, None))
        elif isinstance(v, list):
            items.append((k, tuple(v)))
        else:
            items.append((k, v))
    return tuple(items)

def add_summary_row(df, table_type, selected_dimensions):
    """Add a summary row that applies the same formulas to all rows"""
    if df.empty:
        return df
    
    summary_row = {}
    
    # For dimension columns, use "Total"
    for dim in selected_dimensions:
        if dim in df.columns:
            summary_row[dim] = "Total"
    
    # Common metrics - sum them
    if 'cost' in df.columns:
        summary_row['cost'] = df['cost'].sum()
    if 'installs' in df.columns:
        summary_row['installs'] = df['installs'].sum()
    if 'cpi' in df.columns:
        # Recalculate: sum(cost) / sum(installs)
        total_cost = df['cost'].sum()
        total_installs = df['installs'].sum()
        summary_row['cpi'] = total_cost / total_installs if total_installs > 0 else 0
    if 'avg_daily_cost' in df.columns:
        # Recalculate: sum(cost) / count(distinct install_date)
        total_cost = df['cost'].sum()
        # Check if install_date is in selected dimensions, otherwise use a default
        if 'install_date' in df.columns:
            distinct_dates = df['install_date'].nunique()
        else:
            # If install_date not in dimensions, we need to estimate - use number of rows as proxy
            distinct_dates = len(df)
        summary_row['avg_daily_cost'] = total_cost / distinct_dates if distinct_dates > 0 else 0
    if 'avg_daily_installs' in df.columns:
        # Recalculate: sum(installs) / count(distinct install_date)
        total_installs = df['installs'].sum()
        if 'install_date' in df.columns:
            distinct_dates = df['install_date'].nunique()
        else:
            distinct_dates = len(df)
        summary_row['avg_daily_installs'] = total_installs / distinct_dates if distinct_dates > 0 else 0
    
    # Table-specific metrics
    if table_type == 'roas':
        total_cost = df['cost'].sum()
        for day in DAY_COLUMNS:
            if f'd{day}_total_net_revenue' in df.columns:
                total_revenue = df[f'd{day}_total_net_revenue'].sum()
                summary_row[f'd{day}_roas'] = total_revenue / total_cost if total_cost > 0 else 0
                summary_row[f'd{day}_total_net_revenue'] = total_revenue
        if 'ltv_total_net_revenue' in df.columns:
            total_ltv_revenue = df['ltv_total_net_revenue'].sum()
            summary_row['ltv_roas'] = total_ltv_revenue / total_cost if total_cost > 0 else 0
            summary_row['ltv_total_net_revenue'] = total_ltv_revenue
    
    elif table_type == 'ftds':
        total_installs = df['installs'].sum()
        for day in DAY_COLUMNS:
            if f'd{day}_ftds' in df.columns:
                total_ftds = df[f'd{day}_ftds'].sum()
                summary_row[f'd{day}_ftd_pct'] = (total_ftds / total_installs * 100) if total_installs > 0 else 0
                summary_row[f'd{day}_ftds'] = total_ftds
        if 'ltv_ftds' in df.columns:
            total_ltv_ftds = df['ltv_ftds'].sum()
            summary_row['ltv_ftd_pct'] = (total_ltv_ftds / total_installs * 100) if total_installs > 0 else 0
            summary_row['ltv_ftds'] = total_ltv_ftds
    
    elif table_type == 'retention':
        total_installs = df['installs'].sum()
        for day in DAY_COLUMNS:
            if f'd{day}_ret' in df.columns:
                total_ret = df[f'd{day}_ret'].sum()
                summary_row[f'd{day}_ret_pct'] = (total_ret / total_installs * 100) if total_installs > 0 else 0
                summary_row[f'd{day}_ret'] = total_ret
    
    elif table_type == 'payer_retention':
        if 'payers' in df.columns:
            summary_row['payers'] = df['payers'].sum()
        total_payers = df['payers'].sum() if 'payers' in df.columns else 0
        for day in DAY_COLUMNS:
            if f'd{day}_payers_retention' in df.columns:
                total_payers_ret = df[f'd{day}_payers_retention'].sum()
                summary_row[f'd{day}_payers_ret_pct'] = (total_payers_ret / total_payers * 100) if total_payers > 0 else 0
                summary_row[f'd{day}_payers_retention'] = total_payers_ret
    
    elif table_type == 'cpa':
        total_cost = df['cost'].sum()
        for day in DAY_COLUMNS:
            if f'd{day}_ftds' in df.columns:
                total_ftds = df[f'd{day}_ftds'].sum()
                summary_row[f'd{day}_cpa'] = total_cost / total_ftds if total_ftds > 0 else 0
                # Don't include ftds in summary row display (it's just for calculation)
    
    # diff_from_today - use min
    if 'diff_from_today' in df.columns:
        summary_row['diff_from_today'] = df['diff_from_today'].min()
    
    # Fill missing columns with None, but exclude dX_ftds from CPA table
    for col in df.columns:
        if col not in summary_row:
            # For CPA table, don't include dX_ftds in summary row (they're calculation-only)
            if table_type == 'cpa' and col.endswith('_ftds') and col.startswith('d'):
                continue
            summary_row[col] = None
    
    # Create summary dataframe row
    summary_df = pd.DataFrame([summary_row])
    
    # Concatenate with original dataframe
    result_df = pd.concat([df, summary_df], ignore_index=True)
    return result_df

def reorder_columns(df, table_type, selected_dimensions):
    """Reorder columns according to specification"""
    if df.empty:
        return df
    
    # For CPA table, exclude dX_ftds columns (they're only for calculation)
    if table_type == 'cpa':
        df = df.drop(columns=[col for col in df.columns if col.endswith('_ftds') and col.startswith('d')], errors='ignore')
    
    # Start with selected dimensions
    ordered_cols = [dim for dim in selected_dimensions if dim in df.columns]
    
    # Common columns
    common_cols = ['cost', 'installs', 'cpi', 'avg_daily_cost', 'avg_daily_installs']
    for col in common_cols:
        if col in df.columns:
            ordered_cols.append(col)
    
    # Get remaining columns (dx metrics)
    remaining_cols = [col for col in df.columns if col not in ordered_cols and col != 'diff_from_today']
    
    # Separate into percentage columns and value columns
    pct_cols = []
    value_cols = []
    
    for col in remaining_cols:
        if any(x in col for x in ['_pct', '_roas']) and 'total' not in col:
            pct_cols.append(col)
        else:
            value_cols.append(col)
    
    # Sort percentage columns by day
    def get_day_number(col_name):
        for day in DAY_COLUMNS:
            if f'd{day}_' in col_name:
                return day
        if 'ltv_' in col_name:
            return 9999  # LTV comes last
        return 0
    
    pct_cols.sort(key=get_day_number)
    value_cols.sort(key=get_day_number)
    
    # Add percentage columns, then value columns
    ordered_cols.extend(pct_cols)
    ordered_cols.extend(value_cols)
    
    # Add diff_from_today at the end
    if 'diff_from_today' in df.columns:
        ordered_cols.append('diff_from_today')
    
    # Reorder dataframe
    return df[[col for col in ordered_cols if col in df.columns]]

def format_dataframe(df, table_type):
    """Format dataframe for display"""
    if df.empty:
        return df
    
    display_df = df.copy()
    
    # Format common metrics
    if 'cost' in display_df.columns:
        display_df['cost'] = display_df['cost'].apply(lambda x: f"{x:,.2f}" if pd.notna(x) else "")
    if 'installs' in display_df.columns:
        display_df['installs'] = display_df['installs'].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "")
    if 'cpi' in display_df.columns:
        display_df['cpi'] = display_df['cpi'].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "")
    if 'avg_daily_cost' in display_df.columns:
        display_df['avg_daily_cost'] = display_df['avg_daily_cost'].apply(lambda x: f"{x:,.2f}" if pd.notna(x) else "")
    if 'avg_daily_installs' in display_df.columns:
        display_df['avg_daily_installs'] = display_df['avg_daily_installs'].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "")
    
    # Format table-specific metrics
    if table_type == 'roas':
        for day in DAY_COLUMNS:
            if f'd{day}_roas' in display_df.columns:
                # Format ROAS as percentage with 2 decimals
                display_df[f'd{day}_roas'] = display_df[f'd{day}_roas'].apply(lambda x: f"{x*100:.2f}%" if pd.notna(x) else "")
            if f'd{day}_total_net_revenue' in display_df.columns:
                display_df[f'd{day}_total_net_revenue'] = display_df[f'd{day}_total_net_revenue'].apply(lambda x: f"{x:,.2f}" if pd.notna(x) else "")
        if 'ltv_roas' in display_df.columns:
            # Format LTV ROAS as percentage with 2 decimals
            display_df['ltv_roas'] = display_df['ltv_roas'].apply(lambda x: f"{x*100:.2f}%" if pd.notna(x) else "")
        if 'ltv_total_net_revenue' in display_df.columns:
            display_df['ltv_total_net_revenue'] = display_df['ltv_total_net_revenue'].apply(lambda x: f"{x:,.2f}" if pd.notna(x) else "")
    
    elif table_type == 'ftds':
        for day in DAY_COLUMNS:
            if f'd{day}_ftd_pct' in display_df.columns:
                display_df[f'd{day}_ftd_pct'] = display_df[f'd{day}_ftd_pct'].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "")
            if f'd{day}_ftds' in display_df.columns:
                display_df[f'd{day}_ftds'] = display_df[f'd{day}_ftds'].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "")
        if 'ltv_ftd_pct' in display_df.columns:
            display_df['ltv_ftd_pct'] = display_df['ltv_ftd_pct'].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "")
        if 'ltv_ftds' in display_df.columns:
            display_df['ltv_ftds'] = display_df['ltv_ftds'].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "")
    
    elif table_type == 'retention':
        for day in DAY_COLUMNS:
            if f'd{day}_ret_pct' in display_df.columns:
                display_df[f'd{day}_ret_pct'] = display_df[f'd{day}_ret_pct'].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "")
            if f'd{day}_ret' in display_df.columns:
                display_df[f'd{day}_ret'] = display_df[f'd{day}_ret'].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "")
    
    elif table_type == 'payer_retention':
        if 'payers' in display_df.columns:
            display_df['payers'] = display_df['payers'].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "")
        for day in DAY_COLUMNS:
            if f'd{day}_payers_ret_pct' in display_df.columns:
                display_df[f'd{day}_payers_ret_pct'] = display_df[f'd{day}_payers_ret_pct'].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "")
            if f'd{day}_payers_retention' in display_df.columns:
                display_df[f'd{day}_payers_retention'] = display_df[f'd{day}_payers_retention'].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "")
    
    elif table_type == 'cpa':
        for day in DAY_COLUMNS:
            if f'd{day}_cpa' in display_df.columns:
                display_df[f'd{day}_cpa'] = display_df[f'd{day}_cpa'].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "")
    
    return display_df

def main():
    # Authentication check
    if is_oauth_configured():
        user = authenticate_user()
        if not user:
            return
        show_user_sidebar()
    
    st.title("📊 UA Analytics Dashboard")
    st.markdown("---")
    
    client = get_bigquery_client()
    
    # Default dates (beginning of current year)
    current_year = date.today().year
    default_start = date(current_year, 1, 1)
    default_end = date.today()
    
    # Initialize session state
    if 'run_filters' not in st.session_state:
        st.session_state.run_filters = {
            'install_date_start': str(default_start),
            'install_date_end': str(default_end),
            'platform': None,
            'country': None,
            'media_source': None,
            'campaign_name': None,
            'media_type': None,
            'is_test_campaign': False,  # Default: not test campaigns
        }
        st.session_state.add_rt_cost = False  # Default: false (will be managed by widget)
        st.session_state.selected_dimensions = ['install_week']  # Default: install_week
        st.session_state.selected_table = 'roas'
        st.session_state.dashboard_initialized = True
        st.session_state.run_clicked = False  # Track if Run button has been clicked
        st.session_state.run_add_rt_cost = False  # Store the value when Run is clicked
    
    # Sidebar with filters
    with st.sidebar:
        st.markdown("### 🚀 Run Analytics")
        run_button = st.button("Run Dashboard", type="primary", use_container_width=True)
        
        st.markdown("---")
        st.header("🔍 Filters")
        
        # Install date range
        st.subheader("Install Date Range")
        date_start = st.date_input(
            "Start Date",
            value=default_start,
            key="date_start"
        )
        date_end = st.date_input(
            "End Date",
            value=default_end,
            key="date_end"
        )
        
        # Get filter options (with basic filters to avoid circular dependency)
        basic_filters = {'install_date_start': str(date_start), 'install_date_end': str(date_end)}
        
        # Platform filter
        st.subheader("Platform")
        platform_options = get_filter_options(client, 'platform', basic_filters)
        selected_platforms = st.multiselect(
            "Select Platforms",
            platform_options,
            key="filter_platform"
        )
        
        # Country filter
        st.subheader("Country")
        country_options = get_filter_options(client, 'country', basic_filters)
        selected_countries = st.multiselect(
            "Select Countries",
            country_options,
            key="filter_country"
        )
        
        # Media Source filter
        st.subheader("Media Source")
        media_source_options = get_filter_options(client, 'mediasource', basic_filters)
        selected_media_sources = st.multiselect(
            "Select Media Sources",
            media_source_options,
            key="filter_media_source"
        )
        
        # Campaign Name filter
        st.subheader("Campaign Name")
        campaign_options = get_filter_options(client, 'campaign_name', basic_filters)
        selected_campaigns = st.multiselect(
            "Select Campaigns",
            campaign_options,
            key="filter_campaign"
        )
        
        # Media Type filter
        st.subheader("Media Type")
        media_type_options = get_filter_options(client, 'media_type', basic_filters)
        selected_media_types = st.multiselect(
            "Select Media Types",
            media_type_options,
            key="filter_media_type"
        )
        
        # With Test Campaigns filter
        st.subheader("With Test Campaigns")
        is_test_options = ['All', True, False]
        # Default to False (index 2) - not test campaigns
        current_value = st.session_state.run_filters.get('is_test_campaign', False)
        if current_value == False:
            default_index = 2
        elif current_value == 'All':
            default_index = 0
        else:  # True
            default_index = 1
        selected_is_test = st.selectbox(
            "Select Option",
            is_test_options,
            index=default_index,
            format_func=lambda x: "All" if x == 'All' else ("Yes" if x else "No"),
            key="filter_is_test"
        )
        
        # Add RT Cost toggle
        st.markdown("---")
        st.subheader("Cost Settings")
        add_rt_cost = st.checkbox(
            "Add RT Cost",
            value=st.session_state.add_rt_cost,
            key="add_rt_cost",
            help="Add the RT campaigns cost to the UA cost"
        )
        
        # Dimension selection
        st.markdown("---")
        st.markdown("### Dimensions")
        st.caption("Select dimensions to aggregate by")
        selected_dimensions = st.multiselect(
            "Select Dimensions",
            list(AVAILABLE_DIMENSIONS.keys()),
            default=st.session_state.selected_dimensions if st.session_state.selected_dimensions else ['install_week'],
            key="dimensions_select"
        )
    
    # Update filters when Run button is clicked
    if run_button:
        st.session_state.run_filters = {
            'install_date_start': str(date_start),
            'install_date_end': str(date_end),
            'platform': selected_platforms if selected_platforms else None,
            'country': selected_countries if selected_countries else None,
            'media_source': selected_media_sources if selected_media_sources else None,
            'campaign_name': selected_campaigns if selected_campaigns else None,
            'media_type': selected_media_types if selected_media_types else None,
            'is_test_campaign': selected_is_test,
        }
        # Store the checkbox value (read from widget's session_state)
        st.session_state.run_add_rt_cost = st.session_state.add_rt_cost
        st.session_state.selected_dimensions = selected_dimensions
        st.session_state.run_clicked = True  # Mark that Run has been clicked
        st.rerun()
    
    # Only show tables if Run button has been clicked
    if not st.session_state.get('run_clicked', False):
        st.info("👆 Click 'Run Dashboard' in the sidebar to load data.")
        return
    
    # Use stored filters
    filters = st.session_state.run_filters
    add_rt_cost = st.session_state.run_add_rt_cost  # Use the stored value from Run button
    selected_dimensions = st.session_state.selected_dimensions
    
    # Table options
    table_options = {
        'roas': 'ROAS',
        'ftds': 'FTDs',
        'retention': 'Retention',
        'payer_retention': 'Payer Retention',
        'cpa': 'CPA'
    }
    
    # Convert to tuples for caching
    filters_tuple = filters_to_tuple(filters)
    selected_dimensions_tuple = tuple(selected_dimensions)
    
    # Main content area - Display all tables
    for table_key, table_name in table_options.items():
        try:
            st.header(f"📊 {table_name} Table")
            
            with st.spinner(f"Loading {table_name} data..."):
                if table_key == 'roas':
                    df = query_roas_table(client, filters_tuple, selected_dimensions_tuple, add_rt_cost)
                elif table_key == 'ftds':
                    df = query_ftds_table(client, filters_tuple, selected_dimensions_tuple, add_rt_cost)
                elif table_key == 'retention':
                    df = query_retention_table(client, filters_tuple, selected_dimensions_tuple, add_rt_cost)
                elif table_key == 'payer_retention':
                    df = query_payer_retention_table(client, filters_tuple, selected_dimensions_tuple, add_rt_cost)
                elif table_key == 'cpa':
                    df = query_cpa_table(client, filters_tuple, selected_dimensions_tuple, add_rt_cost)
                else:
                    df = pd.DataFrame()
            
            if df.empty:
                st.info("No data found for the selected filters.")
            else:
                # Add summary row (before formatting)
                df_with_summary = add_summary_row(df.copy(), table_key, selected_dimensions)
                
                # Reorder columns
                df_reordered = reorder_columns(df_with_summary, table_key, selected_dimensions)
                
                # Format dataframe
                display_df = format_dataframe(df_reordered, table_key)
                
                # Mark summary row (last row) as bold
                # Calculate height: 10 data rows + 1 header + 1 summary = 12 rows total
                # Each row ~35px, header ~40px, so total ~460px
                table_height = 460  # Fixed height for 10 rows + header + summary
                
                # Identify frozen columns
                frozen_cols = []
                for dim in selected_dimensions:
                    if dim in display_df.columns:
                        frozen_cols.append(dim)
                frozen_cols.extend(['cost', 'installs', 'cpi', 'avg_daily_cost', 'avg_daily_installs'])
                frozen_cols = [col for col in frozen_cols if col in display_df.columns]
                
                # Display table with fixed height for 10 rows
                st.dataframe(
                    display_df, 
                    use_container_width=True, 
                    height=table_height, 
                    hide_index=True,
                    column_config={
                        col: st.column_config.Column(
                            col,
                            help=None
                        ) for col in display_df.columns
                    }
                )
                
                # Add CSS for frozen columns and summary row styling
                summary_row_idx = len(display_df) - 1
                st.markdown(f"""
                <style>
                /* Style summary row (last row) */
                div[data-testid="stDataFrame"] table tbody tr:nth-child({summary_row_idx + 1}) {{
                    font-weight: bold !important;
                    background-color: #f0f2f6 !important;
                    position: sticky !important;
                    bottom: 0 !important;
                    z-index: 10 !important;
                }}
                div[data-testid="stDataFrame"] table thead tr th {{
                    position: sticky !important;
                    top: 0 !important;
                    z-index: 20 !important;
                    background-color: white !important;
                }}
                </style>
                """, unsafe_allow_html=True)
                
                # Download button (use original df without summary for CSV)
                csv = df.to_csv(index=False)
                st.download_button(
                    label=f"📥 Download {table_name} CSV",
                    data=csv,
                    file_name=f"{table_key}_table_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    key=f"download_{table_key}"
                )
            
            # Add spacing between tables
            st.markdown("---")
        
        except Exception as e:
            st.error(f"Error loading {table_name} data: {e}")
            st.exception(e)
            st.markdown("---")

if __name__ == "__main__":
    main()

