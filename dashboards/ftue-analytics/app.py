# =============================================================================
# AUTHENTICATION CODE - DO NOT MODIFY
# =============================================================================
import streamlit as st

# Must be the first Streamlit command
st.set_page_config(
    page_title="FTUE Analytics Dashboard",
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
import plotly.express as px
import plotly.graph_objects as go

# BigQuery configuration
PROJECT_ID = 'yotam-395120'
DATASET_ID = 'peerplay'
TABLE_ID = 'ftue_dashboard'
TABLE_FULL = f'{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}'

# Initialize BigQuery client
@st.cache_resource
def get_bigquery_client():
    return bigquery.Client(project=PROJECT_ID)

# Get actual pct and ratio column names from table schema
@st.cache_data
def get_pct_columns(_client):
    """Get all pct column names from the table schema.
    Leading underscore avoids hashing the client object.
    """
    table_ref = _client.dataset(DATASET_ID).table(TABLE_ID)
    table = _client.get_table(table_ref)
    pct_columns = [col.name for col in table.schema if col.name.startswith('pct_')]
    pct_columns.sort()  # Sort to ensure consistent ordering
    return pct_columns

@st.cache_data
def get_ratio_columns(_client):
    """Get all ratio column names from the table schema."""
    table_ref = _client.dataset(DATASET_ID).table(TABLE_ID)
    table = _client.get_table(table_ref)
    ratio_columns = [col.name for col in table.schema if col.name.startswith('ratio_')]
    ratio_columns.sort()
    return ratio_columns

def build_where_clause(filters):
    """Build WHERE clause from filters"""
    conditions = []
    
    if filters.get('install_date_start') and filters.get('install_date_end'):
        conditions.append(f"install_date BETWEEN '{filters['install_date_start']}' AND '{filters['install_date_end']}'")
    
    if filters.get('install_week'):
        weeks_str = "', '".join(map(str, filters['install_week']))
        conditions.append(f"install_week IN ('{weeks_str}')")
    
    if filters.get('install_month'):
        months_str = "', '".join(map(str, filters['install_month']))
        conditions.append(f"install_month IN ('{months_str}')")
    
    if filters.get('version'):
        # version is FLOAT type in BigQuery, so no quotes needed
        versions_str = ", ".join(map(str, filters['version']))
        conditions.append(f"install_version IN ({versions_str})")
    
    if filters.get('platform'):
        platforms_str = "', '".join(map(str, filters['platform']))
        conditions.append(f"platform IN ('{platforms_str}')")
    
    if filters.get('mediasource'):
        sources_str = "', '".join(map(str, filters['mediasource']))
        conditions.append(f"mediasource IN ('{sources_str}')")
    
    if filters.get('mediatype'):
        types_str = "', '".join(map(str, filters['mediatype']))
        conditions.append(f"media_type IN ('{types_str}')")
    
    if filters.get('country'):
        countries_str = "', '".join(map(str, filters['country']))
        conditions.append(f"country IN ('{countries_str}')")
    
    # is_low_payers_country filter - only apply when explicitly set (not 'All')
    if filters.get('is_low_payers') is not None and filters.get('is_low_payers') != 'All':
        # is_low_payers_country is a boolean
        is_low_payers_val = 'true' if filters['is_low_payers'] else 'false'
        conditions.append(f"is_low_payers_country = {is_low_payers_val}")

    # Always filter out platform 'none'
    conditions.append("LOWER(platform) != 'none'")
    
    return " AND ".join(conditions) if conditions else "1=1"

def get_filter_options(client, column, filters, order="asc"):
    """Get distinct values with user counts for a column under current filters."""
    where_clause = build_where_clause(filters)
    order_clause = "DESC" if order.lower() == "desc" else "ASC"
    query = f"""
    SELECT {column} as value, SUM(total_users) as users
    FROM `{TABLE_FULL}`
    WHERE {where_clause}
    GROUP BY value
    HAVING value IS NOT NULL
    ORDER BY value {order_clause}
    """
    df = client.query(query).to_dataframe()
    values = df['value'].tolist()
    counts = dict(zip(df['value'], df['users']))
    return values, counts

@st.cache_data(ttl=60)
def query_table_data(_client, filters_tuple, selected_metrics_tuple):
    """Query data for the main table. Uses tuples for caching."""
    filters = dict(filters_tuple)
    selected_metrics = list(selected_metrics_tuple)
    where_clause = build_where_clause(filters)
    
    # Build SELECT clause for metrics - using weighted averages
    metric_selects = []
    for metric in selected_metrics:
        if metric == 'users':
            metric_selects.append("SUM(total_users) as users")
        else:
            metric_selects.append(f"SUM({metric} * total_users) / SUM(total_users) as {metric}")
    
    metrics_str = ", ".join(metric_selects)
    
    query = f"""
    SELECT 
        install_date,
        install_week,
        install_month,
        install_version as version,
        platform,
        mediasource,
        media_type as mediatype,
        {metrics_str}
    FROM `{TABLE_FULL}`
    WHERE {where_clause}
    GROUP BY install_date, install_week, install_month, install_version, platform, mediasource, media_type
    ORDER BY install_date DESC, install_week DESC, install_month DESC, install_version DESC
    """
    
    return _client.query(query).to_dataframe()

@st.cache_data(ttl=60)
def query_bar_chart_media_type(_client, filters_tuple, selected_metrics_tuple):
    """Query data for media_type bar chart - using weighted averages"""
    filters = dict(filters_tuple)
    selected_metrics = list(selected_metrics_tuple)
    where_clause = build_where_clause(filters)

    metric_selects = []
    for metric in selected_metrics:
        if metric == 'users':
            metric_selects.append("SUM(total_users) as users")
        else:
            metric_selects.append(f"SUM({metric} * total_users) / SUM(total_users) as {metric}")
    
    metrics_str = ", ".join(metric_selects)
    
    query = f"""
    SELECT 
        media_type,
        {metrics_str}
    FROM `{TABLE_FULL}`
    WHERE {where_clause}
    GROUP BY media_type
    ORDER BY media_type
    """
    
    return _client.query(query).to_dataframe()

@st.cache_data(ttl=60)
def query_bar_chart_version(_client, filters_tuple, selected_metrics_tuple):
    """Query data for version bar chart - using weighted averages"""
    filters = dict(filters_tuple)
    selected_metrics = list(selected_metrics_tuple)
    where_clause = build_where_clause(filters)

    metric_selects = []
    for metric in selected_metrics:
        if metric == 'users':
            metric_selects.append("SUM(total_users) as users")
        else:
            metric_selects.append(f"SUM({metric} * total_users) / SUM(total_users) as {metric}")
    
    metrics_str = ", ".join(metric_selects)
    
    query = f"""
    SELECT 
        CAST(install_version AS FLOAT64) as version,
        {metrics_str}
    FROM `{TABLE_FULL}`
    WHERE {where_clause}
    GROUP BY install_version
    ORDER BY version ASC
    """
    
    return _client.query(query).to_dataframe()

@st.cache_data(ttl=60)
def query_time_series(_client, filters_tuple, selected_metrics_tuple, time_granularity):
    """Query data for time series chart"""
    filters = dict(filters_tuple)
    selected_metrics = list(selected_metrics_tuple)
    
    # Determine time column based on granularity
    if time_granularity == 'Daily':
        time_col = 'install_date'
    elif time_granularity == 'Weekly':
        time_col = 'install_week'
    else:  # Monthly
        time_col = 'install_month'
    
    # Remove the time dimension from filters for this query
    time_filters = filters.copy()
    if time_granularity == 'Daily':
        time_filters.pop('install_week', None)
        time_filters.pop('install_month', None)
    elif time_granularity == 'Weekly':
        time_filters.pop('install_date', None)
        time_filters.pop('install_month', None)
    else:
        time_filters.pop('install_date', None)
        time_filters.pop('install_week', None)
    
    where_clause = build_where_clause(time_filters)
    
    # Using weighted averages for metrics
    metric_selects = []
    for metric in selected_metrics:
        if metric == 'users':
            metric_selects.append("SUM(total_users) as users")
        else:
            metric_selects.append(f"SUM({metric} * total_users) / SUM(total_users) as {metric}")
    
    metrics_str = ", ".join(metric_selects)
    
    query = f"""
    SELECT 
        {time_col} as time_period,
        {metrics_str}
    FROM `{TABLE_FULL}`
    WHERE {where_clause}
    GROUP BY {time_col}
    ORDER BY time_period
    """
    
    return _client.query(query).to_dataframe()


@st.cache_data(ttl=60)
def query_average_metrics(_client, filters_tuple, columns_tuple):
    """Return a single-row dataframe with weighted AVG for each column."""
    filters = dict(filters_tuple)
    columns = list(columns_tuple)
    if not columns:
        return pd.DataFrame()
    where_clause = build_where_clause(filters)
    # Using weighted averages: SUM(metric * total_users) / SUM(total_users)
    metric_selects = [f"SUM({col} * total_users) / SUM(total_users) as {col}" for col in columns]
    metrics_str = ", ".join(metric_selects)
    query = f"""
    SELECT {metrics_str}
    FROM `{TABLE_FULL}`
    WHERE {where_clause}
    """
    return _client.query(query).to_dataframe()


@st.cache_data(ttl=60)
def query_version_summary(_client, filters_tuple, columns_tuple):
    """Return version summary with total users and weighted avg for each metric."""
    filters = dict(filters_tuple)
    columns = list(columns_tuple)
    if not columns:
        return pd.DataFrame()
    where_clause = build_where_clause(filters)
    
    # Build weighted average expressions: SUM(metric * total_users) / SUM(total_users)
    metric_selects = []
    for col in columns:
        metric_selects.append(f"SUM({col} * total_users) / SUM(total_users) as {col}")
    
    metrics_str = ", ".join(metric_selects)
    
    query = f"""
    SELECT 
        install_version,
        SUM(total_users) as total_users,
        {metrics_str}
    FROM `{TABLE_FULL}`
    WHERE {where_clause}
    GROUP BY install_version
    ORDER BY install_version DESC
    """
    return _client.query(query).to_dataframe()


def format_step_labels(columns, prefix_len=4):
    """Format column names to readable step labels."""
    labels = []
    for col in columns:
        parts = col.split('_', 2)
        if len(parts) >= 3 and parts[0] == 'pct':
            labels.append(f"{parts[1]}: {parts[2]}")
        elif len(parts) >= 3 and parts[0] == 'ratio':
            labels.append(f"{parts[1]} to {parts[2]}")
        else:
            labels.append(col)
    return labels


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

def main():
    # Authentication check
    if is_oauth_configured():
        user = authenticate_user()
        if not user:
            return
        show_user_sidebar()
    
    st.title("📊 FTUE Analytics Dashboard")
    st.markdown("---")
    
    client = get_bigquery_client()
    
    # Get actual pct and ratio column names from table (needed for defaults)
    try:
        pct_columns = get_pct_columns(client)
        ratio_columns = get_ratio_columns(client)
        all_metrics = ['users'] + pct_columns + ratio_columns
        default_metrics = pct_columns + ratio_columns  # show all by default (without filters)
    except Exception as e:
        st.error(f"Error loading metrics: {e}")
        st.stop()
    
    # Get filter options (cache these so they don't re-query on every interaction)
    @st.cache_data(ttl=300)
    def load_filter_options():
        week_values, week_counts = get_filter_options(client, 'install_week', filters={}, order="desc")
        month_values, month_counts = get_filter_options(client, 'install_month', filters={}, order="desc")
        version_values, version_counts = get_filter_options(client, 'install_version', filters={}, order="desc")
        platform_values, platform_counts = get_filter_options(client, 'platform', filters={}, order="asc")
        source_values, source_counts = get_filter_options(client, 'mediasource', filters={}, order="asc")
        type_values, type_counts = get_filter_options(client, 'media_type', filters={}, order="asc")
        country_values, country_counts = get_filter_options(client, 'country', filters={}, order="asc")
        return {
            'week': (week_values, week_counts),
            'month': (month_values, month_counts),
            'version': (version_values, version_counts),
            'platform': (platform_values, platform_counts),
            'source': (source_values, source_counts),
            'type': (type_values, type_counts),
            'country': (country_values, country_counts)
        }
    
    filter_opts = load_filter_options()
    week_values, week_counts = filter_opts['week']
    month_values, month_counts = filter_opts['month']
    version_values, version_counts = filter_opts['version']
    platform_values, platform_counts = filter_opts['platform']
    source_values, source_counts = filter_opts['source']
    type_values, type_counts = filter_opts['type']
    country_values, country_counts = filter_opts['country']
    
    # Default dates
    default_start = (pd.Timestamp.today() - pd.DateOffset(months=3)).date()
    default_end = date.today()
    
    # Find highest version with > 10K users for default selection
    default_version_list = None
    for v in version_values:  # Already sorted descending
        if version_counts.get(v, 0) > 10000:
            default_version_list = [v]
            break
    
    # Initialize session state for run filters (only on first load)
    if 'run_filters' not in st.session_state:
        st.session_state.run_filters = {
            'install_date_start': str(default_start),
            'install_date_end': str(default_end),
            'install_week': None,
            'install_month': None,
            'version': default_version_list,
            'platform': None,
            'mediasource': None,
            'mediatype': None,
            'country': ['US'],  # Default to US only
            'is_low_payers': False,  # Default to False (non-low payers)
        }
        st.session_state.run_metrics = default_metrics
        st.session_state.dashboard_initialized = True
    
    # Sidebar with form to prevent auto-updates
    with st.sidebar:
        # Run button at the very top
        st.markdown("### 🚀 Run Analytics")
        run_button = st.button("Run Dashboard", type="primary", use_container_width=True)
        
        st.markdown("---")
        st.header("🔍 Filters")
        
        # Date range filter
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
        
        # Other filters
        st.subheader("Additional Filters")
        
        selected_weeks = st.multiselect(
            "Install Week",
            week_values,
            format_func=lambda v: f"{v} ({week_counts.get(v,0):,})",
            key="filter_week"
        )
        selected_months = st.multiselect(
            "Install Month",
            month_values,
            format_func=lambda v: f"{v} ({month_counts.get(v,0):,})",
            key="filter_month"
        )
        selected_versions = st.multiselect(
            "Version",
            version_values,
            default=default_version_list if default_version_list else [],
            format_func=lambda v: f"{v} ({version_counts.get(v,0):,})",
            key="filter_version"
        )
        selected_platforms = st.multiselect(
            "Platform",
            platform_values,
            format_func=lambda v: f"{v} ({platform_counts.get(v,0):,})",
            key="filter_platform"
        )
        selected_sources = st.multiselect(
            "Media Source",
            source_values,
            format_func=lambda v: f"{v} ({source_counts.get(v,0):,})",
            key="filter_source"
        )
        selected_types = st.multiselect(
            "Media Type",
            type_values,
            format_func=lambda v: f"{v} ({type_counts.get(v,0):,})",
            key="filter_type"
        )
        selected_countries = st.multiselect(
            "Country",
            country_values,
            default=['US'] if 'US' in country_values else [],
            format_func=lambda v: f"{v} ({country_counts.get(v,0):,})",
            key="filter_country"
        )
        selected_is_low_payers = st.selectbox(
            "Is Low Payers",
            options=['All', False, True],
            index=1,  # Default to False (non-low payers)
            format_func=lambda v: "All" if v == 'All' else ("Yes" if v else "No"),
            key="filter_is_low_payers"
        )

        st.caption("Note: values in brackets show total users for each option.")
        
        # Metrics selection
        st.markdown("---")
        st.subheader("📈 Metrics")
        
        selected_metrics = st.multiselect(
            "Select Metrics",
            all_metrics,
            default=default_metrics,
            key="metrics_select"
        )
    
    # Only update filters when Run button is clicked
    if run_button:
        st.session_state.run_filters = {
            'install_date_start': str(date_start),
            'install_date_end': str(date_end),
            'install_week': selected_weeks if selected_weeks else None,
            'install_month': selected_months if selected_months else None,
            'version': selected_versions if selected_versions else None,
            'platform': selected_platforms if selected_platforms else None,
            'mediasource': selected_sources if selected_sources else None,
            'mediatype': selected_types if selected_types else None,
            'country': selected_countries if selected_countries else None,
            'is_low_payers': selected_is_low_payers,
        }
        st.session_state.run_metrics = selected_metrics
        st.rerun()  # Force rerun with new filters
    
    # Use stored filters (not current widget values)
    filters = st.session_state.run_filters
    active_metrics = st.session_state.run_metrics
    
    if not active_metrics:
        st.warning("⚠️ Please select at least one metric and click 'Run Dashboard'.")
        st.stop()
    
    # Convert filters to tuple for caching
    filters_tuple = filters_to_tuple(filters)
    
    # Main content area
    try:
        # Charts section
        st.header("📊 Charts")

        # 1. PCT steps chart (conversion vs step 1)
        st.subheader("FTUE Steps - Conversion vs Step 1")
        with st.spinner("Loading step conversions..."):
            pct_df = query_average_metrics(client, filters_tuple, tuple(pct_columns))
        if not pct_df.empty:
            values = pct_df.iloc[0].tolist()
            labels = format_step_labels(pct_columns)
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=labels,
                y=values,
                text=[f"{v*100:.1f}%" if v is not None else None for v in values],
                textposition='inside',
                textangle=-90,
                textfont=dict(size=10, color='white'),
                marker_color='steelblue',
                name="Step Conversion"
            ))
            fig.update_layout(
                xaxis_title="FTUE Steps",
                yaxis_title="Conversion (vs step 1)",
                height=500,
                showlegend=False,
                yaxis=dict(range=[0, max(values) * 1.05 if values else 1]),
                margin=dict(t=40, l=60, r=40, b=120)
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data for step conversion chart.")

        # 2. Ratio chart (conversion vs previous step)
        st.subheader("FTUE Steps - Conversion vs Previous Step")
        with st.spinner("Loading step ratios..."):
            ratio_df = query_average_metrics(client, filters_tuple, tuple(ratio_columns))
        if not ratio_df.empty:
            values = ratio_df.iloc[0].tolist()
            labels = format_step_labels(ratio_columns)
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=labels,
                y=values,
                text=[f"{v*100:.1f}%" if v is not None else None for v in values],
                textposition='inside',
                textangle=-90,
                textfont=dict(size=10, color='white'),
                marker_color='seagreen',
                name="Step Ratio"
            ))
            fig.update_layout(
                xaxis_title="FTUE Steps (vs previous step)",
                yaxis_title="Conversion (vs prev step)",
                height=500,
                showlegend=False,
                yaxis=dict(range=[0, max(values) * 1.05 if values else 1]),
                margin=dict(t=40, l=60, r=40, b=120)
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data for step ratio chart.")

        # 3. Bar Chart: Media Type with metric set toggle
        # X-axis = metrics (steps), bars grouped by media_type
        st.subheader("Bar Chart: Media Type")
        media_metric_mode = st.selectbox(
            "Metric set",
            ["Conversion vs Step 1", "Conversion vs Previous Step"],
            key="media_metric_mode"
        )
        media_metrics = pct_columns if media_metric_mode == "Conversion vs Step 1" else ratio_columns
        with st.spinner("Loading media type chart..."):
            media_df = query_bar_chart_media_type(client, filters_tuple, tuple(media_metrics))
        
        if not media_df.empty:
            fig = go.Figure()
            # Pivot: X-axis = metrics, bars = media_types
            metric_labels = format_step_labels(media_metrics)
            for _, row in media_df.iterrows():
                media_type = row['media_type']
                values = [row[m] for m in media_metrics]
                fig.add_trace(go.Bar(
                    x=metric_labels,
                    y=values,
                    name=str(media_type),
                    text=[f"{v:.1%}" if v is not None else None for v in values],
                    textposition='inside',
                    textangle=-90,
                    textfont=dict(size=9, color='white'),
                    insidetextanchor='middle'
                ))
            fig.update_layout(
                barmode='group',
                xaxis_title="FTUE Steps",
                yaxis_title="Value",
                height=550,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                xaxis_tickangle=-45,
                margin=dict(t=60, l=60, r=40, b=120)
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data for media type chart.")
        
        # 4. Bar Chart: Version with metric set toggle
        # X-axis = metrics (steps), bars grouped by version
        st.subheader("Bar Chart: Version")
        version_metric_mode = st.selectbox(
            "Metric set ",
            ["Conversion vs Step 1", "Conversion vs Previous Step"],
            key="version_metric_mode"
        )
        version_metrics = pct_columns if version_metric_mode == "Conversion vs Step 1" else ratio_columns
        with st.spinner("Loading version chart..."):
            version_df = query_bar_chart_version(client, filters_tuple, tuple(version_metrics))
        
        if not version_df.empty:
            fig = go.Figure()
            # Pivot: X-axis = metrics, bars = versions
            metric_labels = format_step_labels(version_metrics)
            for _, row in version_df.iterrows():
                version = row['version']
                values = [row[m] for m in version_metrics]
                fig.add_trace(go.Bar(
                    x=metric_labels,
                    y=values,
                    name=str(version),
                    text=[f"{v:.1%}" if v is not None else None for v in values],
                    textposition='inside',
                    textangle=-90,
                    textfont=dict(size=9, color='white'),
                    insidetextanchor='middle'
                ))
            fig.update_layout(
                barmode='group',
                xaxis_title="FTUE Steps",
                yaxis_title="Value",
                height=550,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                xaxis_tickangle=-45,
                margin=dict(t=60, l=60, r=40, b=120)
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data for version chart.")

        # 5. Time Series Chart
        st.subheader("Time Series Chart")
        time_metric_mode = st.selectbox(
            "Metric set  ",
            ["Conversion vs Step 1", "Conversion vs Previous Step"],
            key="time_metric_mode"
        )
        time_metrics = pct_columns if time_metric_mode == "Conversion vs Step 1" else ratio_columns
        time_granularity = st.radio(
            "Time Granularity",
            ["Daily", "Weekly", "Monthly"],
            horizontal=True,
            key="time_gran"
        )
        
        with st.spinner(f"Loading {time_granularity.lower()} time series..."):
            time_df = query_time_series(client, filters_tuple, tuple(time_metrics), time_granularity)
        
        if not time_df.empty:
            fig = go.Figure()
            for metric in time_metrics:
                if metric in time_df.columns:
                    fig.add_trace(go.Scatter(
                        x=time_df['time_period'],
                        y=time_df[metric],
                        mode='lines+markers',
                        name=metric,
                        line=dict(width=2)
                    ))
            
            # Get actual data range for x-axis (remove empty space)
            x_min = time_df['time_period'].min()
            x_max = time_df['time_period'].max()
            
            fig.update_layout(
                xaxis_title=time_granularity,
                yaxis_title="Value",
                height=500,
                hovermode='x unified',
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(t=60, l=60, r=40, b=80),
                xaxis=dict(
                    range=[x_min, x_max],
                    autorange=False
                )
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data for time series chart.")

        st.markdown("---")

        # 6. Version Summary Table
        st.header("📊 Version Summary Table")
        version_summary_mode = st.selectbox(
            "Metric set",
            ["Conversion vs Step 1", "Conversion vs Previous Step"],
            key="version_summary_mode"
        )
        version_summary_metrics = pct_columns if version_summary_mode == "Conversion vs Step 1" else ratio_columns
        
        with st.spinner("Loading version summary..."):
            version_summary_df = query_version_summary(client, filters_tuple, tuple(version_summary_metrics))
        
        if not version_summary_df.empty:
            # Format the dataframe for display
            display_df = version_summary_df.copy()
            
            # Format total_users with commas
            display_df['total_users'] = display_df['total_users'].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "")
            
            # Format metric columns as percentages
            for col in version_summary_metrics:
                if col in display_df.columns:
                    display_df[col] = display_df[col].apply(lambda x: f"{x*100:.1f}%" if pd.notna(x) else "")
            
            # Rename columns for better display
            display_df = display_df.rename(columns={
                'install_version': 'Version',
                'total_users': 'Total Users'
            })
            
            # Dynamic height based on number of rows (35px per row + header)
            dynamic_height = min(len(display_df) * 35 + 40, 600)
            st.dataframe(display_df, use_container_width=True, height=dynamic_height, hide_index=True)
        else:
            st.info("No version summary data available.")

        st.markdown("---")

        # 7. Data Table (moved to bottom)
        st.header("📋 Data Table")
        with st.spinner("Loading data table..."):
            table_df = query_table_data(client, filters_tuple, tuple(active_metrics))
        
        if table_df.empty:
            st.info("No data found for the selected filters.")
        else:
            # Add weighted average summary row using 'users' as weights when present
            if 'users' in table_df.columns and table_df['users'].sum() > 0:
                total_users = table_df['users'].sum()
                summary = {col: "" for col in table_df.columns}
                summary[list(table_df.columns)[0]] = "Weighted Avg"
                for col in table_df.columns:
                    if col == 'users':
                        summary[col] = total_users
                    elif col not in ['install_date', 'install_week', 'install_month', 'version', 'platform', 'mediasource', 'mediatype']:
                        try:
                            summary[col] = (table_df[col] * table_df['users']).sum() / total_users
                        except Exception:
                            summary[col] = None
                styled = pd.concat([table_df, pd.DataFrame([summary])], ignore_index=True)
                def highlight_summary(row):
                    return ['font-weight: bold' if row.name == len(styled)-1 else '' for _ in row]
                st.dataframe(styled.style.apply(highlight_summary, axis=1), use_container_width=True)
            else:
                st.dataframe(table_df, use_container_width=True)
    
    except Exception as e:
        st.error(f"Error loading data: {e}")
        st.exception(e)

if __name__ == "__main__":
    main()

