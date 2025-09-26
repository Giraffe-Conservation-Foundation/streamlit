import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
import json
import os

# Make main available at module level for import
def main():
    """Main application entry point - delegates to _main_implementation"""
    return _main_implementation()

# Custom CSS for better styling (minimal - no forced backgrounds)
st.markdown("""
<style>
    .logo-title {
        color: #2E8B57;
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 0.5rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
    }
    .logo-subtitle {
        color: #4F4F4F;
        font-size: 1.3rem;
        font-weight: 300;
        margin-top: 0;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #2E8B57;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

def init_session_state():
    """Initialize session state variables"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'api_token' not in st.session_state:
        st.session_state.api_token = None
    if 'base_url' not in st.session_state:
        st.session_state.base_url = "https://twiga.pamdas.org/api/v1.0"
    if 'username' not in st.session_state:
        st.session_state.username = None

def authenticate_earthranger():
    """Handle EarthRanger authentication with username/password"""
    st.header("🔐 EarthRanger Authentication")
    
    st.write("Enter your EarthRanger credentials to access the unit check dashboard:")
    
    # Fixed server URL
    st.info("**Server:** https://twiga.pamdas.org")
    
    # Username and Password
    username = st.text_input("Username", help="Your EarthRanger username")
    password = st.text_input("Password", type="password", help="Your EarthRanger password")
    
    if st.button("🔌 Login to EarthRanger", type="primary"):
        if not username or not password:
            st.error("❌ Username and password are required")
            return
        
        try:
            with st.spinner("Logging in to EarthRanger..."):
                # Use EarthRanger login API
                login_url = "https://twiga.pamdas.org/api/v1.0/login"
                login_data = {"username": username, "password": password}
                
                response = requests.post(login_url, json=login_data)
                response.raise_for_status()
                
                # Get the token from response
                login_result = response.json()
                api_token = login_result.get('token')
                
                if not api_token:
                    st.error("❌ Login failed: No token received")
                    return
                
                # Test the token
                st.session_state.api_token = api_token
                st.session_state.base_url = "https://twiga.pamdas.org/api/v1.0"
                headers = {"Authorization": f"Bearer {api_token}"}
                
                test_url = f"{st.session_state.base_url}/sources/?page_size=1"
                test_response = requests.get(test_url, headers=headers)
                test_response.raise_for_status()
                
                st.success("✅ Successfully logged in to EarthRanger!")
                st.session_state.authenticated = True
                st.session_state.headers = headers
                st.session_state.username = username
                
                st.rerun()
                
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                st.error("❌ Authentication failed: Invalid username or password")
            else:
                st.error(f"❌ HTTP Error: {e}")
        except Exception as e:
            st.error(f"❌ Login failed: {str(e)}")
            st.info("💡 Please check your username and password")

# --- Data fetching functions ---
@st.cache_data(ttl=3600)
def get_all_sources():
    """Fetch all sources (cached for 1 hour)"""
    if not st.session_state.get('api_token'):
        return pd.DataFrame()
    
    # Use direct API calls
    url = f"{st.session_state.base_url}/sources/?page_size=1000"
    headers = st.session_state.headers
    sources = []
    
    while url:
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        sources.extend(data['data']['results'])
        url = data['data']['next']
    
    return pd.DataFrame(sources)

def get_last_7_days(source_id):
    """Fetch last 7 days of locations for a source"""
    if not st.session_state.get('api_token'):
        return pd.DataFrame()
        
    since = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00.000Z")
    url = f"{st.session_state.base_url}/observations/?source_id={source_id}&since={since}&page_size=1000&ordering=recorded_at"
    resp = requests.get(url, headers=st.session_state.headers)
    resp.raise_for_status()
    data = resp.json()
    
    points = []
    for result in data['data']['results']:
        # Basic location data
        point = {
            'datetime': result['recorded_at'],
            'latitude': result['location']['latitude'],
            'longitude': result['location']['longitude']
        }
        
        # Add additional data if available (check both locations)
        battery_found = False
        
        # First check 'additional' field (some manufacturers use this)
        if 'additional' in result:
            additional = result['additional']
            
            # Try different battery field names used by different manufacturers
            battery_fields = [
                'battery_voltage', 'battery_level', 'battery', 'voltage', 'bat_voltage', 'batteryvoltage', 
                'v', 'battery_volts',  # SpoorTrack
                'battery_percentage',  # Mapipedia
            ]
            for field in battery_fields:
                if field in additional:
                    point['battery'] = additional[field]
                    battery_found = True
                    break
        
        # Check 'device_status_properties' field (SpoorTrack and others use this)
        if 'device_status_properties' in result and not battery_found:
            device_status_list = result['device_status_properties']
            
            # Handle list structure: each item has 'label' and 'value'
            if device_status_list and isinstance(device_status_list, list):
                # Look for battery-related labels and extract their values
                battery_labels = ['battery', 'voltage', 'battery_voltage', 'battery_level', 'battery_percentage', 'v', 'bat_voltage']
                
                for item in device_status_list:
                    if isinstance(item, dict) and 'label' in item and 'value' in item:
                        label = item['label'].lower()  # Convert to lowercase for matching
                        if any(battery_label in label for battery_label in battery_labels):
                            point['battery'] = item['value']
                            battery_found = True
                            break
        
        points.append(point)
    
    return pd.DataFrame(points)

def unit_dashboard():
    """Main unit check dashboard interface"""
    st.header("🔍 Unit Check Dashboard")
    
    with st.spinner("Loading all sources..."):
        df_sources = get_all_sources()
    
    if df_sources.empty:
        st.warning("No sources found.")
        return
    
    # Filter to only tracking-device sources
    df_sources = df_sources[df_sources['source_type'] == 'tracking-device']
    
    if df_sources.empty:
        st.warning("No tracking device sources found.")
        return
    
    # First filter by manufacturer - default to SpoorTrack
    manufacturers = ['All'] + sorted(df_sources['provider'].dropna().unique().tolist())
    
    # Set SpoorTrack as default if it exists
    default_manufacturer = "SpoorTrack" if "SpoorTrack" in manufacturers else "All"
    selected_manufacturer = st.selectbox("Select a manufacturer", manufacturers, 
                                       index=manufacturers.index(default_manufacturer))
    
    # Filter by manufacturer if not "All"
    if selected_manufacturer != 'All':
        df_sources = df_sources[df_sources['provider'] == selected_manufacturer]
    
    # Use collar_key for the dropdown label (fallback to id if missing)
    df_sources['label'] = df_sources['collar_key'].fillna(df_sources['id']).astype(str)
    # Sort alphanumerically by label
    df_sources = df_sources.sort_values('label')
    
    # Multi-select for sources
    selected_labels = st.multiselect(
        "Select sources (you can select multiple)", 
        df_sources['label'].tolist(),
        default=[df_sources['label'].iloc[0]] if len(df_sources) > 0 else []
    )
    
    if not selected_labels:
        st.warning("Please select at least one source.")
        return
    
    selected_source_ids = df_sources[df_sources['label'].isin(selected_labels)]['id'].tolist()
    
    # Create a color mapping for the selected sources
    colors = px.colors.qualitative.Set1
    color_map = {label: colors[i % len(colors)] for i, label in enumerate(selected_labels)}
    
    # Last 7 days combined chart
    st.subheader("📊 Location Activity (Last 7 Days)")
    
    all_7_day_data = []
    all_battery_data = []
    
    with st.spinner("Fetching 7-day location data..."):
        for i, source_id in enumerate(selected_source_ids):
            source_label = selected_labels[i]
            df_7 = get_last_7_days(source_id)
            
            if not df_7.empty:
                df_7['date'] = pd.to_datetime(df_7['datetime']).dt.date
                counts = df_7.groupby('date').size().reset_index(name='count')
                counts['source'] = source_label
                all_7_day_data.append(counts)
                
                # Collect battery data if available
                if 'battery' in df_7.columns:
                    # Convert battery values to numeric, handling any non-numeric values
                    df_7['battery_numeric'] = pd.to_numeric(df_7['battery'], errors='coerce')
                    
                    # Only proceed if we have valid numeric battery values
                    if df_7['battery_numeric'].notna().any():
                        battery_data = df_7.groupby('date')['battery_numeric'].mean().reset_index()
                        battery_data = battery_data.rename(columns={'battery_numeric': 'battery'})
                        battery_data['source'] = source_label
                        all_battery_data.append(battery_data)
    
    # Create two columns for charts
    col1, col2 = st.columns(2)
    
    with col1:
        if all_7_day_data:
            combined_df = pd.concat(all_7_day_data, ignore_index=True)
            
            # Create a plotly bar chart with different colors for each source
            fig = px.bar(
                combined_df,
                x='date',
                y='count',
                color='source',
                title="Daily Location Counts (Last 7 Days)",
                barmode='group'
            )
            fig.update_layout(
                xaxis_title="Date", 
                yaxis_title="Number of Locations",
                xaxis=dict(tickformat='%Y-%m-%d')
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No locations in the last 7 days for any selected sources.")
    
    with col2:
        if all_battery_data:
            battery_df = pd.concat(all_battery_data, ignore_index=True)
            
            # Create battery level chart
            fig_battery = px.line(
                battery_df,
                x='date',
                y='battery',
                color='source',
                title="Average Daily Battery Level (Last 7 Days)",
                markers=True
            )
            fig_battery.update_layout(
                xaxis_title="Date",
                yaxis_title="Battery Level",
                xaxis=dict(tickformat='%Y-%m-%d')
            )
            st.plotly_chart(fig_battery, use_container_width=True)
        else:
            st.info("No battery data available for selected sources.")
    
    # Last location map for all selected sources
    st.subheader("🗺️ Last Known Locations")
    
    last_locations = []
    
    with st.spinner("Getting last locations..."):
        for i, source_id in enumerate(selected_source_ids):
            source_label = selected_labels[i]
            df_7 = get_last_7_days(source_id)
            
            if not df_7.empty and 'latitude' in df_7.columns and 'longitude' in df_7.columns:
                # Sort by datetime and get the most recent location
                df_sorted = df_7.sort_values('datetime', ascending=False)
                last_location = df_sorted.iloc[0]
                
                location_data = {
                    'source': source_label,
                    'latitude': last_location['latitude'],
                    'longitude': last_location['longitude'],
                    'datetime': last_location['datetime'],
                    'color': color_map[source_label]
                }
                
                # Add battery info if available
                if 'battery' in df_7.columns and pd.notna(last_location.get('battery')):
                    location_data['battery'] = last_location['battery']
                
                last_locations.append(location_data)
    
    if last_locations:
        last_locations_df = pd.DataFrame(last_locations)
        
        # Create map with last locations only
        fig_map = px.scatter_mapbox(
            last_locations_df,
            lat='latitude',
            lon='longitude',
            color='source',
            hover_data={'datetime': True, 'latitude': ':.6f', 'longitude': ':.6f', 'battery': True},
            title="Last Known Locations",
            mapbox_style='open-street-map',
            height=500,
            size_max=15
        )
        
        # Make markers larger
        fig_map.update_traces(marker=dict(size=12))
        
        # Center map on all last locations
        fig_map.update_layout(
            mapbox=dict(
                center=dict(
                    lat=last_locations_df['latitude'].mean(),
                    lon=last_locations_df['longitude'].mean()
                ),
                zoom=8
            )
        )
        
        st.plotly_chart(fig_map, use_container_width=True)
        
        # Show last location details in a table
        st.subheader("📍 Last Location Details")
        display_df = last_locations_df[['source', 'datetime', 'latitude', 'longitude']].copy()
        if 'battery' in last_locations_df.columns:
            display_df['battery'] = last_locations_df['battery']
        display_df['datetime'] = pd.to_datetime(display_df['datetime']).dt.strftime('%Y-%m-%d %H:%M:%S')
        st.dataframe(display_df, use_container_width=True)
        
    else:
        st.info("No location data available for mapping.")
    
    # Show summary statistics
    if all_7_day_data:
        combined_df = pd.concat(all_7_day_data, ignore_index=True)
        total_locations = combined_df['count'].sum()
        avg_daily = combined_df.groupby('source')['count'].mean()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Locations (7 days)", total_locations)
        with col2:
            st.metric("Average Daily", f"{avg_daily.mean():.1f}")
        with col3:
            st.metric("Sources Reporting", len(selected_labels))

def _main_implementation():
    """Main application logic"""
    init_session_state()
    
    # Header with logo
    with st.container():
        st.title("🔍 Unit Check Dashboard")
        st.markdown("Monitor tracking device units - 7-day activity, battery, and location")
    
    # Landing page (only shown if not authenticated yet)
    if not st.session_state.authenticated:
        # Show authentication directly on landing page
        authenticate_earthranger()
        return
    
    # Sidebar navigation
    st.sidebar.title("Navigation")
    
    # Authentication status
    st.sidebar.markdown("### 🔐 Authentication ✅")
    if st.session_state.get('username'):
        st.sidebar.write(f"**User:** {st.session_state.username}")
    
    # Show dashboard
    unit_dashboard()
    
    # Sidebar options
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔧 Options")
    
    if st.sidebar.button("🔄 Refresh Data"):
        # Clear cached data
        get_all_sources.clear()
        st.rerun()
    
    if st.sidebar.button("🔓 Logout"):
        # Clear authentication
        for key in ['authenticated', 'api_token', 'headers', 'username']:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

# Make main() available for import while still allowing direct execution
if __name__ == "__main__":
    main()