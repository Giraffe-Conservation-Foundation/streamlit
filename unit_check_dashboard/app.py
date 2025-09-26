import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from ecoscope.io.earthranger import EarthRangerIO

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
    if 'username' not in st.session_state:
        st.session_state.username = ""
    if 'password' not in st.session_state:
        st.session_state.password = ""

def er_login(username, password):
    """Test EarthRanger login credentials"""
    try:
        er = EarthRangerIO(
            server="https://twiga.pamdas.org",
            username=username,
            password=password
        )
        # Try a simple call to check credentials
        er.get_sources(limit=1)
        return True
    except Exception:
        return False

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
        
        if er_login(username, password):
            st.session_state.authenticated = True
            st.session_state.username = username
            st.session_state.password = password
            st.success("✅ Successfully logged in to EarthRanger!")
            st.rerun()
        else:
            st.error("❌ Invalid credentials. Please try again.")

# --- Data fetching functions ---
@st.cache_data(ttl=3600)
def get_all_sources(_username, _password):
    """Fetch all sources using ecoscope (cached for 1 hour)"""
    er = EarthRangerIO(
        server="https://twiga.pamdas.org",
        username=_username,
        password=_password
    )
    sources_df = er.get_sources()
    return sources_df

def get_last_7_days(source_id, username, password):
    """Fetch last 7 days of locations for a source using ecoscope"""
    er = EarthRangerIO(
        server="https://twiga.pamdas.org",
        username=username,
        password=password
    )
    
    since = (datetime.utcnow() - timedelta(days=7)).isoformat()
    
    try:
        # Use EarthRangerIO get_source_observations method with correct parameters
        relocations = er.get_source_observations(
            source_ids=[source_id],  # This method expects source_ids (plural) as a list
            since=since,
            include_details=True,
            relocations=False  # Get raw DataFrame instead of Relocations object
        )
        

        
        if relocations.empty:
            return pd.DataFrame()
        
        # Convert to the format we need
        points = []
        for _, row in relocations.iterrows():
            # Extract coordinates from geometry (Point object)
            latitude, longitude = None, None
            if 'geometry' in row and pd.notna(row['geometry']):
                try:
                    geom = row['geometry']
                    if hasattr(geom, 'y') and hasattr(geom, 'x'):
                        latitude = geom.y
                        longitude = geom.x
                except:
                    # Fallback to location dict if available
                    if 'location' in row and isinstance(row['location'], dict):
                        latitude = row['location'].get('latitude')
                        longitude = row['location'].get('longitude')
            
            point = {
                'datetime': row['recorded_at'],
                'latitude': latitude,
                'longitude': longitude
            }
            
            # Extract battery data - check multiple sources
            battery_found = False
            
            # First check observation_details (most direct)
            if 'observation_details' in row and pd.notna(row['observation_details']):
                obs_details = row['observation_details']
                if isinstance(obs_details, dict):
                    battery_fields = ['voltage', 'battery', 'batt', 'batt_perc', 'bat_soc']
                    for field in battery_fields:
                        if field in obs_details:
                            point['battery'] = obs_details[field]
                            battery_found = True
                            break
            
            # If not found, check device_status_properties
            if not battery_found and 'device_status_properties' in row and pd.notna(row['device_status_properties']):
                device_status = row['device_status_properties']
                if isinstance(device_status, list):
                    for item in device_status:
                        if isinstance(item, dict) and 'label' in item and 'value' in item:
                            label = item['label'].lower()
                            # Look for voltage, battery, batt, or bat_soc
                            if any(battery_term in label for battery_term in ['voltage', 'battery', 'batt', 'bat_soc']):
                                point['battery'] = item['value']
                                battery_found = True
                                break
            
            points.append(point)
        
        return pd.DataFrame(points)
        
    except Exception as e:
        st.error(f"Error fetching observations: {e}")
        import traceback
        st.code(traceback.format_exc())
        return pd.DataFrame()

def unit_dashboard():
    """Main unit check dashboard interface"""
    #st.header("🔍 Unit Check Dashboard")
    
    username = st.session_state.username
    password = st.session_state.password
    
    with st.spinner("Loading all sources..."):
        df_sources = get_all_sources(username, password)
    
    if df_sources.empty:
        st.warning("No sources found.")
        return
    
    # Filter to only tracking-device sources
    df_sources = df_sources[df_sources['source_type'] == 'tracking-device']
    
    if df_sources.empty:
        st.warning("No tracking device sources found.")
        return
    
    # First filter by manufacturer - default to SpoorTrack (case insensitive)
    manufacturers = ['All'] + sorted(df_sources['provider'].dropna().unique().tolist())
    
    # Find SpoorTrack with case-insensitive search
    spoortrack_match = None
    for manufacturer in manufacturers:
        if manufacturer.lower() == "spoortrack":
            spoortrack_match = manufacturer
            break
    
    # Set SpoorTrack as default if it exists (using the actual case from data)
    default_manufacturer = spoortrack_match if spoortrack_match else "All"
    default_index = manufacturers.index(default_manufacturer)
    
    selected_manufacturer = st.selectbox("Select a manufacturer", manufacturers, 
                                       index=default_index)
    
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
    
    # Separator between filter and activity sections
    st.markdown("---")
    
    # Last 7 days combined chart
    st.subheader("📊 Activity (last 7 days)")
    
    all_7_day_data = []
    all_battery_data = []
    
    with st.spinner("Fetching 7-day location data..."):
        for i, source_id in enumerate(selected_source_ids):
            source_label = selected_labels[i]
            df_7 = get_last_7_days(source_id, username, password)
            
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
                title="Daily location counts",
                barmode='group'
            )
            
            # Determine manufacturer type based on selected manufacturer
            # Add reference lines for expected daily location counts
            if selected_manufacturer.lower() in ['spoortrack', 'savannah tracking', 'savannah_tracking_provider']:
                # SpoorTrack and Savannah: good activity at 24 locations/day
                fig.add_hline(
                    y=24, 
                    line_dash="dash", 
                    line_color="green",
                    annotation_text="Good (24/day)",
                    annotation_position="top right",
                    annotation_font_color="green"
                )
            elif selected_manufacturer.lower() in ['gsatsolar', 'ceres']:
                # GSatSolar and Ceres: good activity at 3 locations/day
                fig.add_hline(
                    y=3, 
                    line_dash="dash", 
                    line_color="green",
                    annotation_text="Good (3/day)",
                    annotation_position="top right",
                    annotation_font_color="green"
                )
            elif selected_manufacturer == 'All':
                # When "All" is selected, check the actual sources in the data
                sources_in_data = combined_df['source'].unique()
                # Get the manufacturer for each source from the original data
                source_manufacturers = df_sources[df_sources['label'].isin(selected_labels)]['provider'].unique()
                
                # If all sources are voltage-type manufacturers, use 24
                voltage_manufacturers = ['spoortrack', 'savannah tracking', 'savannah_tracking_provider']
                percentage_manufacturers = ['gsatsolar', 'ceres']
                
                if all(mfg.lower() in voltage_manufacturers for mfg in source_manufacturers):
                    fig.add_hline(y=24, line_dash="dash", line_color="green", 
                                annotation_text="Good (24/day)", annotation_position="top right",
                                annotation_font_color="green")
                elif all(mfg.lower() in percentage_manufacturers for mfg in source_manufacturers):
                    fig.add_hline(y=3, line_dash="dash", line_color="green", 
                                annotation_text="Good (3/day)", annotation_position="top right",
                                annotation_font_color="green")
                # For mixed manufacturers, don't add a reference line
            
            fig.update_layout(
                xaxis_title="Date", 
                yaxis_title="Number of locations",
                xaxis=dict(tickformat='%Y-%m-%d')
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No locations in the last 7 days for any selected sources.")
    
    with col2:
        if all_battery_data:
            battery_df = pd.concat(all_battery_data, ignore_index=True)
            
            # Determine battery type based on values (voltage vs percentage)
            max_battery = battery_df['battery'].max()
            min_battery = battery_df['battery'].min()
            
            # If values are in range 3-5, it's voltage; if 6-100, it's percentage
            is_voltage = max_battery <= 5.0 and min_battery >= 3.0
            is_percentage = max_battery > 10 and max_battery <= 100
            
            # Create battery level chart
            fig_battery = px.line(
                battery_df,
                x='date',
                y='battery',
                color='source',
                title="Average daily battery",
                markers=True
            )
            
            # Add reference line for "good" battery level and set y-axis limits
            if is_voltage:
                # For voltage (SpoorTrack, Savannah): good level at 3.9V
                fig_battery.add_hline(
                    y=3.9, 
                    line_dash="dash", 
                    line_color="green",
                    annotation_text="Good (3.9V)",
                    annotation_position="bottom right",
                    annotation_font_color="green"
                )
                y_title = "Battery voltage (V)"
                y_range = [3.2, 4.2]
            elif is_percentage:
                # For percentage (GSatSolar, Ceres): good level at 80%
                fig_battery.add_hline(
                    y=80, 
                    line_dash="dash", 
                    line_color="green",
                    annotation_text="Good (80%)",
                    annotation_position="bottom right",
                    annotation_font_color="green"
                )
                y_title = "Battery level (%)"
                y_range = [0, 100]
            else:
                # Unknown type, use generic label and auto-range
                y_title = "Battery Level"
                y_range = None
            
            fig_battery.update_layout(
                xaxis_title="Date",
                yaxis_title=y_title,
                xaxis=dict(tickformat='%Y-%m-%d'),
                yaxis=dict(range=y_range) if y_range else {}
            )
            st.plotly_chart(fig_battery, use_container_width=True)
        else:
            st.info("No battery data available for selected sources.")
    
    # Separator between activity and last location sections
    st.markdown("---")
    
    # Last location map for all selected sources
    st.subheader("🗺️ Last location")
    
    last_locations = []
    
    with st.spinner("Getting last locations..."):
        for i, source_id in enumerate(selected_source_ids):
            source_label = selected_labels[i]
            df_7 = get_last_7_days(source_id, username, password)
            
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
        
        # Prepare hover data - only include battery if it exists
        hover_data = {'datetime': True, 'latitude': ':.6f', 'longitude': ':.6f'}
        if 'battery' in last_locations_df.columns:
            hover_data['battery'] = True
        
        # Create map with last locations only
        fig_map = px.scatter_mapbox(
            last_locations_df,
            lat='latitude',
            lon='longitude',
            color='source',
            hover_data=hover_data,
            title="Last known locations",
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
        st.subheader("📍 Last location details")
        display_columns = ['source', 'datetime', 'latitude', 'longitude']
        display_df = last_locations_df[display_columns].copy()
        
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
            st.metric("Total locations (7 days)", total_locations)
        with col2:
            st.metric("Average daily locations", f"{avg_daily.mean():.1f}")
        with col3:
            st.metric("Sources reporting", len(selected_labels))

def _main_implementation():
    """Main application logic"""
    init_session_state()
    
    # Header with logo
    with st.container():
        st.title("🔍 Unit Check Dashboard")
        st.markdown("Monitor GPS tracking units (7 day activity/battery, and last location)")
    
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
        st.sidebar.write("**Server:** https://twiga.pamdas.org")
    
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
        for key in ['authenticated', 'username', 'password']:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

# Make main() available for import while still allowing direct execution
if __name__ == "__main__":
    main()