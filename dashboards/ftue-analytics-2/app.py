# =============================================================================
# FTUE Analytics Dashboard 2 - QA Version
# Uses ftue_dashboard_stage table
# =============================================================================
import streamlit as st

# Must be the first Streamlit command
st.set_page_config(
    page_title="FTUE Analytics Dashboard 2 (QA)",
    page_icon="🧪",
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
    redirect_uri = get_secret('STREAMLIT_REDIRECT_URI') or "http://localhost:8502/"
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
            redirect_uri = get_secret('STREAMLIT_REDIRECT_URI') or "http://localhost:8502/"
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

import pandas as pd
from google.cloud import bigquery
from datetime import datetime, date
import plotly.graph_objects as go

# BigQuery configuration - STAGE TABLE
PROJECT_ID = 'yotam-395120'
DATASET_ID = 'peerplay'
TABLE_ID = 'ftue_dashboard_stage'
TABLE_FULL = f'{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}'

@st.cache_resource
def get_bigquery_client():
    return bigquery.Client(project=PROJECT_ID)

@st.cache_data
def get_pct_columns(_client):
    """Get all pct column names from the table schema."""
    table_ref = _client.dataset(DATASET_ID).table(TABLE_ID)
    table = _client.get_table(table_ref)
    pct_columns = [col.name for col in table.schema if col.name.startswith('pct_')]
    pct_columns.sort()
    return pct_columns

def build_where_clause(filters):
    """Build WHERE clause from filters"""
    conditions = []
    
    if filters.get('version'):
        versions_str = ", ".join(map(str, filters['version']))
        conditions.append(f"install_version IN ({versions_str})")
    
    if filters.get('platform'):
        platforms_str = "', '".join(map(str, filters['platform']))
        conditions.append(f"platform IN ('{platforms_str}')")

    # Always filter out platform 'none'
    conditions.append("LOWER(platform) != 'none'")
    
    return " AND ".join(conditions) if conditions else "LOWER(platform) != 'none'"

def get_filter_options(client, column, filters, order="asc"):
    """Get distinct values with user counts for a column."""
    where_clause = build_where_clause({})  # No filters for options
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
def query_average_metrics(_client, filters_tuple, columns_tuple):
    """Return a single-row dataframe with weighted AVG for each column."""
    filters = dict(filters_tuple)
    columns = list(columns_tuple)
    if not columns:
        return pd.DataFrame()
    where_clause = build_where_clause(filters)
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

def format_step_labels(columns):
    """Format column names to readable step labels."""
    labels = []
    for col in columns:
        parts = col.split('_', 2)
        if len(parts) >= 3 and parts[0] == 'pct':
            labels.append(f"{parts[1]}: {parts[2]}")
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
    
    st.title("🧪 FTUE Analytics Dashboard 2 (QA)")
    st.markdown("**Using staging table: `ftue_dashboard_stage`**")
    st.markdown("---")
    
    client = get_bigquery_client()
    
    # Get pct column names from table
    try:
        pct_columns = get_pct_columns(client)
    except Exception as e:
        st.error(f"Error loading metrics: {e}")
        st.stop()
    
    # Get filter options
    @st.cache_data(ttl=300)
    def load_filter_options():
        version_values, version_counts = get_filter_options(client, 'install_version', filters={}, order="desc")
        platform_values, platform_counts = get_filter_options(client, 'platform', filters={}, order="asc")
        return {
            'version': (version_values, version_counts),
            'platform': (platform_values, platform_counts)
        }
    
    filter_opts = load_filter_options()
    version_values, version_counts = filter_opts['version']
    platform_values, platform_counts = filter_opts['platform']
    
    # Find highest version with > 10K users for default selection
    default_version_list = None
    for v in version_values:
        if version_counts.get(v, 0) > 10000:
            default_version_list = [v]
            break
    
    # Initialize session state for run filters
    if 'run_filters' not in st.session_state:
        st.session_state.run_filters = {
            'version': default_version_list,
            'platform': None,
        }
    
    # Sidebar
    with st.sidebar:
        st.markdown("### 🚀 Run Analytics")
        run_button = st.button("Run Dashboard", type="primary", use_container_width=True)
        
        st.markdown("---")
        st.header("🔍 Filters")
        
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

        st.caption("Note: values in brackets show total users for each option.")
    
    # Only update filters when Run button is clicked
    if run_button:
        st.session_state.run_filters = {
            'version': selected_versions if selected_versions else None,
            'platform': selected_platforms if selected_platforms else None,
        }
        st.rerun()
    
    filters = st.session_state.run_filters
    filters_tuple = filters_to_tuple(filters)
    
    # Main content area
    try:
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

        st.markdown("---")

        # 2. Version Summary Table
        st.header("📊 Version Summary Table")
        
        with st.spinner("Loading version summary..."):
            version_summary_df = query_version_summary(client, filters_tuple, tuple(pct_columns))
        
        if not version_summary_df.empty:
            display_df = version_summary_df.copy()
            
            # Format total_users with commas
            display_df['total_users'] = display_df['total_users'].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "")
            
            # Format metric columns as percentages
            for col in pct_columns:
                if col in display_df.columns:
                    display_df[col] = display_df[col].apply(lambda x: f"{x*100:.1f}%" if pd.notna(x) else "")
            
            # Rename columns for better display
            display_df = display_df.rename(columns={
                'install_version': 'Version',
                'total_users': 'Total Users'
            })
            
            # Dynamic height based on number of rows
            dynamic_height = min(len(display_df) * 35 + 40, 600)
            st.dataframe(display_df, use_container_width=True, height=dynamic_height, hide_index=True)
        else:
            st.info("No version summary data available.")

    except Exception as e:
        st.error(f"Error loading data: {e}")
        st.exception(e)

if __name__ == "__main__":
    main()

