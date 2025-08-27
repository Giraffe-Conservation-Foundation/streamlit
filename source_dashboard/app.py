import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
import json
import os

# Import ecoscope for events functionality
try:
    import ecoscope
    ECOSCOPE_AVAILABLE = True
except ImportError:
    ECOSCOPE_AVAILABLE = False
    st.warning("⚠️ ecoscope library not available. Events functionality will be limited.")

# Make main available at module level for import
def main():
    """Main application entry point - delegates to _main_implementation"""
    return _main_implementation()

# Page configuration - handled by main Twiga Tools app
# st.set_page_config(
#     page_title="Source Dashboard",
#     page_icon="🌍",
#     layout="wide",
#     initial_sidebar_state="expanded"
# )

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
    if 'password' not in st.session_state:
        st.session_state.password = None

def authenticate_earthranger():
    """Handle EarthRanger authentication"""
    st.header("🔐 EarthRanger Authentication")
    
    st.write("Enter your EarthRanger API token to access the source dashboard:")
    
    # Fixed server URL
    st.info("**Server:** https://twiga.pamdas.org")
    
    # API Token (required)
    api_token = st.text_input(
        "API Token",
        type="password",
        help="Your EarthRanger API token from https://twiga.pamdas.org"
    )
    
    if st.button("🔌 Connect to EarthRanger", type="primary"):
        if not api_token:
            st.error("❌ API token is required")
            return
        
        try:
            with st.spinner("Connecting to EarthRanger..."):
                st.session_state.api_token = api_token
                st.session_state.base_url = "https://twiga.pamdas.org/api/v1.0"
                headers = {"Authorization": f"Bearer {api_token}"}
                
                # Test the API token
                test_url = f"{st.session_state.base_url}/sources/?page_size=1"
                response = requests.get(test_url, headers=headers)
                response.raise_for_status()
                
                st.success("✅ Successfully authenticated with EarthRanger!")
                st.session_state.authenticated = True
                st.session_state.headers = headers
                
                st.rerun()
                
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                st.error("❌ Authentication failed: Invalid API token")
            else:
                st.error(f"❌ HTTP Error: {e}")
        except Exception as e:
            st.error(f"❌ Connection failed: {str(e)}")
            st.info("💡 Please check your API token")

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

def get_latest_location(source_id):
    """Fetch latest location for a source"""
    if not st.session_state.get('api_token'):
        return None
        
    url = f"{st.session_state.base_url}/observations/?source_id={source_id}&page_size=1&ordering=-recorded_at"
    resp = requests.get(url, headers=st.session_state.headers)
    resp.raise_for_status()
    data = resp.json()
    
    if data['data']['results']:
        result = data['data']['results'][0]
        return {
            'datetime': result['recorded_at'],
            'latitude': result['location']['latitude'],
            'longitude': result['location']['longitude']
        }
    
    return None

def get_unit_events(source_ids, since_days=7, dashboard_df=None):
    """Fetch events for selected unit IDs using ecoscope get_events function"""
    if not ECOSCOPE_AVAILABLE or not st.session_state.get('api_token'):
        return pd.DataFrame()
    
    try:
        # Initialize EarthRanger connection using ecoscope
        er_client = ecoscope.io.EarthRangerIO(
            server="https://twiga.pamdas.org",
            token=st.session_state.api_token
        )
        
        # Calculate date range
        since_date = (datetime.now() - timedelta(days=since_days)).isoformat()
        until_date = datetime.now().isoformat()
        
        # Get events for monitoring category and unit_update type
        events_gdf = er_client.get_events(
            event_category="monitoring",
            since=since_date,
            until=until_date,
            include_details=True
        )
        
        if events_gdf.empty:
            return pd.DataFrame()
        
        # Filter events for unit_update type
        unit_events = events_gdf[
            (events_gdf.get('event_type', pd.Series(dtype='object')).str.contains('unit_update', na=False)) |
            (events_gdf.get('title', pd.Series(dtype='object')).str.contains('unit_update', case=False, na=False))
        ]
        
        # Filter events by EarthRanger source UUID in unitupdate_unitid
        if not unit_events.empty:
            matching_events = []
            
            for _, event in unit_events.iterrows():
                event_details = event.get('event_details', {})
                if isinstance(event_details, dict):
                    # Get the stored EarthRanger source UUID
                    stored_source_uuid = event_details.get('unitupdate_unitid', '')
                    
                    # Check if this UUID matches any of our selected source IDs
                    if stored_source_uuid in source_ids:
                        matching_events.append(event)
            
            if matching_events:
                return pd.DataFrame(matching_events)
            else:
                return pd.DataFrame()
        
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"Error fetching events: {str(e)}")
        return pd.DataFrame()

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
        
        # Debug: Store the raw result structure for inspection
        point['raw_keys'] = list(result.keys())
        
        # Add additional data if available (check both locations)
        battery_found = False
        
        # First check 'additional' field (some manufacturers use this)
        if 'additional' in result:
            additional = result['additional']
            # Store all additional field names for debugging
            point['additional_fields'] = list(additional.keys())
            
            # Try different battery field names used by different manufacturers
            battery_fields = [
                'battery_voltage', 'battery_level', 'battery', 'voltage', 'bat_voltage', 'batteryvoltage', 
                'v', 'battery_volts',  # SpoorTrack
                'battery_percentage',  # Mapipedia
            ]
            for field in battery_fields:
                if field in additional:
                    point['battery'] = additional[field]
                    point['battery_field_name'] = field  # Track which field was used
                    point['battery_source'] = 'additional'
                    battery_found = True
                    break
            
            # Add other potentially useful fields
            if 'temperature' in additional:
                point['temperature'] = additional['temperature']
            if 'activity' in additional:
                point['activity'] = additional['activity']
        else:
            # No additional data found
            point['additional_fields'] = ['NO_ADDITIONAL_FIELD']
        
        # Check 'device_status_properties' field (SpoorTrack and others use this)
        if 'device_status_properties' in result and not battery_found:
            device_status_list = result['device_status_properties']
            
            # Handle list structure: each item has 'label' and 'value'
            if device_status_list and isinstance(device_status_list, list):
                # Extract all labels for debugging
                device_labels = [item.get('label', 'UNKNOWN') for item in device_status_list if isinstance(item, dict)]
                point['device_status_fields'] = device_labels
                
                # Look for battery-related labels and extract their values
                battery_labels = ['battery', 'voltage', 'battery_voltage', 'battery_level', 'battery_percentage', 'v', 'bat_voltage']
                
                for item in device_status_list:
                    if isinstance(item, dict) and 'label' in item and 'value' in item:
                        label = item['label'].lower()  # Convert to lowercase for matching
                        if any(battery_label in label for battery_label in battery_labels):
                            point['battery'] = item['value']
                            point['battery_field_name'] = item['label']  # Store original label
                            point['battery_source'] = 'device_status_properties'
                            battery_found = True
                            break
                
                # Add other potentially useful fields from device status
                for item in device_status_list:
                    if isinstance(item, dict) and 'label' in item and 'value' in item:
                        label = item['label'].lower()
                        if 'temperature' in label and 'temperature' not in point:
                            point['temperature'] = item['value']
                        elif 'activity' in label and 'activity' not in point:
                            point['activity'] = item['value']
            else:
                point['device_status_fields'] = ['NO_DEVICE_STATUS_FIELDS']
        else:
            point['device_status_fields'] = ['NO_DEVICE_STATUS_FIELD']
        
        points.append(point)
    
    return pd.DataFrame(points)

def get_inactive_sources():
    """Get sources with no location in >90 days and attached to a subject"""
    st.info("🔍 Analyzing sources attached to subjects for recent activity...")
    
    # Get all sources and check their last transmission
    all_sources = get_all_sources()
    if all_sources.empty:
        return pd.DataFrame()
    
    # Filter to tracking devices only
    tracking_sources = all_sources[all_sources['source_type'] == 'tracking-device']
    
    # Create timezone-aware cutoff date to match the data
    cutoff_date = datetime.now().replace(tzinfo=None) - timedelta(days=90)
    results = []
    
    # Get subject-source relationships first (filter to active subjects only)
    try:
        # Get active subjects first
        subjects_url = f"{st.session_state.base_url}/subjects/?page_size=1000&is_active=true"
        subjects_resp = requests.get(subjects_url, headers=st.session_state.headers)
        subjects_resp.raise_for_status()
        subjects_data = subjects_resp.json()
        
        # Check if we have valid data structure
        if not subjects_data or 'data' not in subjects_data:
            raise ValueError("Invalid subjects response structure")
        
        data_section = subjects_data.get('data', {})
        if not data_section or 'results' not in data_section:
            raise ValueError("No results found in subjects response")
        
        subjects_list = data_section.get('results', [])
        if subjects_list is None:
            raise ValueError("Subjects results is None")
        
        active_subjects_count = len(subjects_list)
        st.info(f"Found {active_subjects_count} active subjects in EarthRanger")
        
        # Now get subjectsources to find the subject-source relationships
        # This is the key endpoint that connects subjects to sources
        subjectsources_url = f"{st.session_state.base_url}/subjectsources/?page_size=1000"
        all_subjectsources = []
        
        # Paginate through all subjectsources
        while subjectsources_url:
            subjectsources_resp = requests.get(subjectsources_url, headers=st.session_state.headers)
            subjectsources_resp.raise_for_status()
            subjectsources_data = subjectsources_resp.json()
            
            if subjectsources_data and 'data' in subjectsources_data and 'results' in subjectsources_data['data']:
                batch_results = subjectsources_data['data']['results']
                all_subjectsources.extend(batch_results)
                # Get next page URL
                subjectsources_url = subjectsources_data['data'].get('next')
            else:
                break
        
        st.info(f"Found {len(all_subjectsources)} total subjectsource relationships (after pagination)")
        
        # Extract active subject IDs and names for filtering and later display
        active_subject_ids = {subject['id'] for subject in subjects_list}
        active_subjects_dict = {subject['id']: subject['name'] for subject in subjects_list}
        
        # Extract source IDs that are attached to active subjects AND have active deployments
        attached_source_ids = set()
        source_to_subject_mapping = {}  # Map source_id to subject info
        subjectsources_count = 0
        active_deployments_count = 0
        
        # Current year for deployment filtering
        current_year = datetime.now().year
        
        # Process all subjectsources
        for subjectsource in all_subjectsources:
            subjectsources_count += 1
            
            # Handle different possible data types
            if isinstance(subjectsource, dict):
                # The source and subject fields are direct string IDs, not nested objects
                subject_id = subjectsource.get('subject')  # This is a string ID
                source_id = subjectsource.get('source')    # This is a string ID
                
                if subject_id in active_subject_ids and source_id:
                    # Check deployment status - look for assigned_range
                    deployment_active = True
                    assigned_range = subjectsource.get('assigned_range', {})
                    
                    if assigned_range and isinstance(assigned_range, dict):
                        # Check if there's an upper bound (deployment end date)
                        upper_bound = assigned_range.get('upper')
                        if upper_bound:
                            try:
                                # Parse the deployment end date
                                end_date = pd.to_datetime(upper_bound)
                                end_year = end_date.year
                                
                                # Only include if deployment ends in the future or this year
                                if end_year <= current_year - 1:  # Ended before this year
                                    deployment_active = False
                                    
                            except Exception:
                                # If we can't parse the date, assume it's active
                                pass
                    
                    # Only add sources with active deployments
                    if deployment_active:
                        attached_source_ids.add(source_id)
                        active_deployments_count += 1
                        # Store the mapping for later display
                        source_to_subject_mapping[source_id] = {
                            'subject_id': subject_id,
                            'subject_name': active_subjects_dict.get(subject_id, 'Unknown'),
                            'deployment_end': assigned_range.get('upper', 'Open') if assigned_range else 'Open'
                        }
        
        st.info(f"Found {subjectsources_count} total subjectsource relationships processed")
        st.info(f"Found {active_deployments_count} sources with active deployments attached to active subjects")
        st.info(f"Found {len(attached_source_ids)} unique source IDs with active deployments")
        
        if attached_source_ids:
            # Show a sample of the source IDs we found
            sample_ids = list(attached_source_ids)[:5]  # Show fewer for cleaner output
            st.write(f"Sample source IDs found: {sample_ids}")
        
        if not attached_source_ids:
            st.warning("No sources found with active deployments attached to active subjects using subjectsources endpoint.")
            # Fallback: check all tracking sources (less targeted)
            attached_source_ids = set(tracking_sources['id'].tolist())
            st.info("Checking all tracking device sources instead.")
    
    except Exception as e:
        st.warning(f"Could not retrieve subject-source relationships: {str(e)}")
        st.info("Checking all tracking device sources instead.")
        attached_source_ids = set(tracking_sources['id'].tolist())
    
    # Filter to only sources that are attached to subjects
    sources_to_check = tracking_sources[tracking_sources['id'].isin(attached_source_ids)]
    
    # Debug: Check if a specific source exists in the data (for troubleshooting)
    # You can change this source_id to debug any specific source
    debug_source_id = None  # Set to a source ID like "581346e9-a69a-4109-92fc-36b51e1ba03d" if needed
    
    if debug_source_id:
        debug_in_tracking = tracking_sources[tracking_sources['id'] == debug_source_id]
        if not debug_in_tracking.empty:
            row = debug_in_tracking.iloc[0]
            st.write(f"DEBUG - Found source {debug_source_id} in tracking sources:")
            st.write(f"  - Provider: {row.get('provider', 'Unknown')}")
            st.write(f"  - Source Type: {row.get('source_type', 'Unknown')}")
            st.write(f"  - In attached_source_ids: {row['id'] in attached_source_ids}")
            st.write(f"  - In sources_to_check: {row['id'] in sources_to_check['id'].values}")
        else:
            st.write(f"DEBUG - Source {debug_source_id} NOT found in tracking sources")
            # Check if it exists in all sources
            all_debug = get_all_sources()[get_all_sources()['id'] == debug_source_id]
            if not all_debug.empty:
                row = all_debug.iloc[0]
                st.write(f"DEBUG - Found source {debug_source_id} in all sources (non-tracking):")
                st.write(f"  - Source Type: {row.get('source_type', 'Unknown')}")
                st.write(f"  - Provider: {row.get('provider', 'Unknown')}")
    
    # Debug: Show why the numbers differ
    st.info(f"**Breakdown of filtering:**")
    st.info(f"- Total tracking sources in system: {len(tracking_sources)}")
    st.info(f"- Source IDs found in subjectsources with active deployments: {len(attached_source_ids)}")
    st.info(f"- Sources that exist in both tracking sources AND subjectsources: {len(sources_to_check)}")
    
    # Show which sources are missing
    missing_from_tracking = attached_source_ids - set(tracking_sources['id'].tolist())
    if missing_from_tracking:
        st.warning(f"Found {len(missing_from_tracking)} source IDs in subjectsources that are not in tracking sources list")
        st.write(f"Sample missing IDs: {list(missing_from_tracking)[:5]}")
    
    st.info(f"Found {len(sources_to_check)} sources attached to subjects. Checking all sources for recent activity...")
    
    # Create progress bar for large numbers of sources
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    with st.spinner(f"Checking last transmission for {len(sources_to_check)} sources..."):
        for idx, (_, source) in enumerate(sources_to_check.iterrows()):
            # Update progress
            progress = (idx + 1) / len(sources_to_check)
            progress_bar.progress(progress)
            status_text.text(f"Checking source {idx + 1} of {len(sources_to_check)}: {source.get('collar_key', source['id'])}")
            
            sid = source['id']
            
            try:
                url = f"{st.session_state.base_url}/observations/?source_id={sid}&page_size=1&ordering=-recorded_at"
                resp = requests.get(url, headers=st.session_state.headers)
                resp.raise_for_status()
                data = resp.json()
                
                # Get the last location datetime
                if data['data']['results']:
                    last_dt = data['data']['results'][0]['recorded_at']
                else:
                    last_dt = None
                
                # Get subject information for this source
                subject_info = source_to_subject_mapping.get(sid, {
                    'subject_name': 'Unknown', 
                    'subject_id': 'Unknown',
                    'deployment_end': 'Unknown'
                })
                
                results.append({
                    'source_id': sid,
                    'collar_key': source.get('collar_key', 'Unknown'),
                    'provider': source.get('provider', 'Unknown'),
                    'subject_name': subject_info['subject_name'],
                    'subject_id': subject_info['subject_id'],
                    'deployment_end': subject_info['deployment_end'],
                    'last_location': last_dt
                })
            except Exception as e:
                # Log the error but continue processing
                subject_info = source_to_subject_mapping.get(sid, {
                    'subject_name': 'Unknown', 
                    'subject_id': 'Unknown',
                    'deployment_end': 'Unknown'
                })
                results.append({
                    'source_id': sid,
                    'collar_key': source.get('collar_key', 'Unknown'), 
                    'provider': source.get('provider', 'Unknown'),
                    'subject_name': subject_info['subject_name'],
                    'subject_id': subject_info['subject_id'],
                    'deployment_end': subject_info['deployment_end'],
                    'last_location': None,
                    'error': str(e)
                })
    
    # Clear progress indicators
    progress_bar.empty()
    status_text.empty()
    
    if not results:
        return pd.DataFrame()
    
    df_results = pd.DataFrame(results)
    
    # Convert last_location to datetime and make timezone-naive for comparison
    df_results['last_location'] = pd.to_datetime(df_results['last_location'], errors='coerce')
    if df_results['last_location'].dt.tz is not None:
        df_results['last_location'] = df_results['last_location'].dt.tz_convert(None)
    
    # Find inactive sources
    inactive = df_results[
        (df_results['last_location'].isna()) | 
        (df_results['last_location'] < cutoff_date)
    ]
    
    st.info(f"**Analysis Results:**")
    st.info(f"- Total sources checked: {len(df_results)}")
    st.info(f"- Sources with no data: {df_results['last_location'].isna().sum()}")
    st.info(f"- Sources older than {cutoff_date.strftime('%Y-%m-%d')}: {(df_results['last_location'] < cutoff_date).sum()}")
    st.info(f"- Total inactive sources: {len(inactive)}")
    
    return inactive

def source_dashboard():
    """Main source dashboard interface"""
    st.header("🌍 Source Dashboard")
    
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
    
    # First filter by manufacturer
    manufacturers = ['All'] + sorted(df_sources['provider'].dropna().unique().tolist())
    selected_manufacturer = st.selectbox("Select a manufacturer", manufacturers)
    
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
    
    # Create a mapping for debugging and show ALL sources that match selected labels
    source_mapping = df_sources[df_sources['label'].isin(selected_labels)][['label', 'id', 'collar_key']].to_dict('records')
    
    # Also check for duplicate collar keys
    for label in selected_labels:
        matching_sources = df_sources[df_sources['label'] == label]
        if len(matching_sources) > 1:
            st.warning(f"⚠️ Found {len(matching_sources)} sources with label '{label}'. Using first one.")
            for idx, (_, source) in enumerate(matching_sources.iterrows()):
                st.write(f"  {idx+1}. ID: `{source['id']}`, Collar Key: `{source.get('collar_key', 'N/A')}`")
    
    # Create a color mapping for the selected sources
    colors = px.colors.qualitative.Set1
    color_map = {label: colors[i % len(colors)] for i, label in enumerate(selected_labels)}
    
    # Latest locations for all selected sources
    st.subheader("📍 Latest Locations")
    
    latest_locations = []
    map_data = []
    
    with st.spinner("Fetching latest locations..."):
        for i, source_id in enumerate(selected_source_ids):
            # Safely get the source label - find it from the dataframe instead of assuming index alignment
            matching_source = df_sources[df_sources['id'] == source_id]
            if not matching_source.empty:
                source_label = matching_source.iloc[0]['label']
            else:
                source_label = f"Unknown Source {i+1}"
            
            latest = get_latest_location(source_id)
            
            if latest:
                latest_locations.append({
                    'source': source_label,
                    'datetime': latest['datetime'],
                    'latitude': latest['latitude'],
                    'longitude': latest['longitude']
                })
                
                map_data.append({
                    'latitude': latest['latitude'],
                    'longitude': latest['longitude'],
                    'source': source_label,
                    'color': color_map[source_label]
                })
                
                # Format datetime for display
                dt_formatted = pd.to_datetime(latest['datetime']).strftime('%Y-%m-%d %H:%M:%S UTC')
                st.write(f"**{source_label}** - {dt_formatted} - Lat: {latest['latitude']:.6f}, Lon: {latest['longitude']:.6f}")
            else:
                st.write(f"**{source_label}** - No recent locations")
    
    # Show map with colored markers for multiple sources
    if map_data:
        map_df = pd.DataFrame(map_data)
        
        # Create a plotly scatter map for better color control
        fig = px.scatter_mapbox(
            map_df, 
            lat="latitude", 
            lon="longitude", 
            color="source",
            hover_name="source",
            hover_data={"latitude": ":.6f", "longitude": ":.6f"},
            zoom=8,
            height=400,
            title="Latest Locations"
        )
        fig.update_layout(mapbox_style="open-street-map")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No recent locations for any selected sources.")
    
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
            
            # Debug: Show what fields are available
            if st.checkbox("🔍 Show available data fields (for debugging)"):
                debug_data = []
                for i, source_id in enumerate(selected_source_ids):
                    source_label = selected_labels[i]
                    df_7 = get_last_7_days(source_id)
                    
                    if not df_7.empty:
                        # Show raw API response structure
                        if 'raw_keys' in df_7.columns:
                            raw_keys = []
                            for key_list in df_7['raw_keys'].dropna():
                                raw_keys.extend(key_list)
                            unique_raw_keys = list(set(raw_keys))
                            
                        # Show additional fields
                        if 'additional_fields' in df_7.columns:
                            all_fields = []
                            for field_list in df_7['additional_fields'].dropna():
                                all_fields.extend(field_list)
                            unique_fields = list(set(all_fields))
                        else:
                            unique_fields = ['NO_ADDITIONAL_FIELD']
                        
                        # Show device status fields
                        if 'device_status_fields' in df_7.columns:
                            all_device_fields = []
                            for field_list in df_7['device_status_fields'].dropna():
                                all_device_fields.extend(field_list)
                            unique_device_fields = list(set(all_device_fields))
                        else:
                            unique_device_fields = ['NO_DEVICE_STATUS_FIELD']
                        
                        # Check if battery was found
                        battery_found = 'battery' in df_7.columns and df_7['battery'].notna().any()
                        battery_field_used = None
                        battery_source = None
                        if 'battery_field_name' in df_7.columns:
                            battery_field_used = df_7['battery_field_name'].dropna().iloc[0] if df_7['battery_field_name'].notna().any() else None
                        if 'battery_source' in df_7.columns:
                            battery_source = df_7['battery_source'].dropna().iloc[0] if df_7['battery_source'].notna().any() else None
                        
                        debug_data.append({
                            'source': source_label,
                            'raw_response_keys': ', '.join(sorted(unique_raw_keys)) if 'raw_keys' in df_7.columns else 'N/A',
                            'additional_fields': ', '.join(sorted(unique_fields)) if unique_fields != ['NO_ADDITIONAL_FIELD'] else 'NO ADDITIONAL FIELDS',
                            'device_status_fields': ', '.join(sorted(unique_device_fields)) if unique_device_fields != ['NO_DEVICE_STATUS_FIELD'] else 'NO DEVICE STATUS FIELDS',
                            'battery_found': '✅ YES' if battery_found else '❌ NO',
                            'battery_field_used': battery_field_used or 'N/A',
                            'battery_source': battery_source or 'N/A',
                            'sample_battery_values': str(df_7['battery'].dropna().head(3).tolist()) if battery_found else 'N/A'
                        })
                
                if debug_data:
                    debug_df = pd.DataFrame(debug_data)
                    st.write("**Detailed debugging information:**")
                    for _, row in debug_df.iterrows():
                        with st.expander(f"🔍 {row['source']} - Battery: {row['battery_found']}"):
                            st.write(f"**Raw API Response Keys:** {row['raw_response_keys']}")
                            st.write(f"**Additional Fields:** {row['additional_fields']}")
                            st.write(f"**Device Status Fields:** {row['device_status_fields']}")
                            st.write(f"**Battery Found:** {row['battery_found']}")
                            st.write(f"**Battery Field Used:** {row['battery_field_used']}")
                            st.write(f"**Battery Source Location:** {row['battery_source']}")
                            st.write(f"**Sample Battery Values:** {row['sample_battery_values']}")
                else:
                    st.write("No debug data available")
    
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
    
    # Unit Events Section
    st.subheader("📋 Unit Events")
    st.write("Events associated with selected units (event_category=monitoring, event_type=unit_update)")
    
    if ECOSCOPE_AVAILABLE:
        # Time range selector for events
        col1, col2 = st.columns(2)
        with col1:
            event_days = st.selectbox(
                "Event history period",
                [7, 14, 30, 60, 90],
                index=0,
                help="Number of days to look back for events"
            )
        with col2:
            if st.button("🔄 Refresh Events", help="Refresh event data"):
                st.rerun()
        # Manual fix for TAIL-ST1386 - add correct EarthRanger source ID
        manual_source_ids = selected_source_ids.copy()
        if any('TAIL-ST1386' in mapping['label'] for mapping in source_mapping):
            correct_tail_id = '68a5642d-6ddc-4693-8031-580c9eab01c3'
            if correct_tail_id not in manual_source_ids:
                manual_source_ids.append(correct_tail_id)
        
        with st.spinner(f"Fetching unit events for last {event_days} days..."):
            events_df = get_unit_events(manual_source_ids, since_days=event_days, dashboard_df=df_sources)
        
        if not events_df.empty:
            st.success(f"Found {len(events_df)} unit events in the last {event_days} days")
            
            # Prepare events display
            display_events = events_df.copy()
            
            # Extract useful fields from event_details for display
            if 'event_details' in display_events.columns:
                for idx, row in display_events.iterrows():
                    event_details = row.get('event_details', {})
                    if isinstance(event_details, dict):
                        # Extract common fields
                        for key in ['unitupdate_notes', 'unitupdate_action', 'unitupdate_country']:
                            if key in event_details:
                                display_events.loc[idx, key] = event_details[key]
                
                # Get unit names for display
                display_events['unit_name'] = display_events.apply(
                    lambda row: df_sources[df_sources['id'] == row.get('event_details', {}).get('unitupdate_unitid', '')]['label'].iloc[0] 
                    if not df_sources[df_sources['id'] == row.get('event_details', {}).get('unitupdate_unitid', '')].empty 
                    else 'Unknown Unit',
                    axis=1
                )
            
            # Format datetime columns
            time_columns = ['time', 'created_at', 'updated_at', 'event_time']
            for col in time_columns:
                if col in display_events.columns:
                    display_events[col] = pd.to_datetime(display_events[col], errors='coerce')
                    display_events[f'{col}_formatted'] = display_events[col].dt.strftime('%Y-%m-%d %H:%M:%S')
            
            # Select columns for display (avoid duplicates)
            display_cols = ['unit_name']
            
            # Add time column
            if 'time_formatted' in display_events.columns:
                display_cols.append('time_formatted')
            elif 'event_time_formatted' in display_events.columns:
                display_cols.append('event_time_formatted')
            elif 'created_at_formatted' in display_events.columns:
                display_cols.append('created_at_formatted')
            
            # Add other relevant columns (check they exist and aren't already added)
            additional_cols = ['unitupdate_action', 'unitupdate_notes', 'unitupdate_country']
            for col in additional_cols:
                if col in display_events.columns and col not in display_cols:
                    display_cols.append(col)
            
            # Display the events table
            st.subheader("📊 Unit Events Table")
            st.dataframe(
                display_events[display_cols],
                use_container_width=True,
                hide_index=True
            )
            
            base_cols = ['title', 'event_type', 'state', 'priority']
            for col in base_cols:
                if col in display_events.columns:
                    display_cols.append(col)
            
            # Add location info if available
            if 'geometry' in display_events.columns:
                # Extract coordinates from geometry
                try:
                    display_events['latitude'] = display_events['geometry'].apply(
                        lambda geom: geom.y if hasattr(geom, 'y') else None
                    )
                    display_events['longitude'] = display_events['geometry'].apply(
                        lambda geom: geom.x if hasattr(geom, 'x') else None
                    )
                    display_cols.extend(['latitude', 'longitude'])
                except:
                    pass
            
            # Add event details if available
            if 'event_details' in display_events.columns:
                display_cols.append('event_details')
            
            # Final column selection
            available_cols = [col for col in display_cols if col in display_events.columns]
            
            if available_cols:
                # Display events table
                st.dataframe(
                    display_events[available_cols],
                    use_container_width=True,
                    column_config={
                        'time_formatted': 'Event Time',
                        'event_time_formatted': 'Event Time',
                        'created_at_formatted': 'Created At',
                        'title': 'Title',
                        'event_type': 'Event Type',
                        'state': 'State',
                        'priority': 'Priority',
                        'latitude': st.column_config.NumberColumn('Latitude', format="%.6f"),
                        'longitude': st.column_config.NumberColumn('Longitude', format="%.6f"),
                        'event_details': 'Event Details'
                    }
                )
            
            # Show event summary statistics  
            st.subheader("📊 Event Summary")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if 'event_type' in display_events.columns:
                    event_types = display_events['event_type'].value_counts()
                    st.write("**Event Types:**")
                    for event_type, count in event_types.items():
                        st.write(f"• {event_type}: {count}")
            
            with col2:
                if 'unitupdate_action' in display_events.columns:
                    actions = display_events['unitupdate_action'].value_counts()
                    st.write("**Actions:**")
                    for action, count in actions.items():
                        st.write(f"• {action}: {count}")
            
            with col3:
                if 'unitupdate_country' in display_events.columns:
                    countries = display_events['unitupdate_country'].value_counts()
                    st.write("**Countries:**")
                    for country, count in countries.items():
                        st.write(f"• {country}: {count}")
                        
        else:
            st.info(f"No unit events found for selected sources in the last {event_days} days")
    
    else:
        st.warning("⚠️ ecoscope library not available. Cannot fetch events data.")
        st.info("To enable events functionality, install ecoscope: `pip install ecoscope`")
    
    # Inactive sources section
    st.header("⚠️ Inactive Source Analysis")
    st.subheader("Sources with Active Deployments but No Location in >90 Days")
    
    st.info("""
    This analysis finds sources that **should be active** but haven't transmitted in over 90 days:
    
    - ✅ **Attached to active subjects**
    - ✅ **Deployment is still supposed to be active** (end date in the future or open)
    - ❌ **Haven't transmitted in >90 days** (indicating a potential problem)
    
    These are sources you may want to manually mark as ended/inactive in EarthRanger.
    Click the button below to run the analysis.
    """)
    
    # Add trigger button
    if st.button("🔍 Analyze Inactive Sources", type="primary"):
        with st.spinner("Analyzing inactive sources..."):
            df_inactive = get_inactive_sources()
        
        if not df_inactive.empty:
            st.warning(f"Found {len(df_inactive)} sources that should be active but haven't transmitted in >90 days:")
            st.info("These sources have active deployments (not marked as ended) but appear to have stopped transmitting. You may want to manually mark them as ended/inactive.")
            
            # Format the display - include subject name and deployment end date
            display_cols = ['collar_key', 'subject_name', 'deployment_end', 'last_location', 'provider', 'source_id']
            available_cols = [col for col in display_cols if col in df_inactive.columns]
            
            # Format last_location for display with better handling
            if 'last_location' in df_inactive.columns:
                # Convert to datetime first, then format
                df_inactive_copy = df_inactive.copy()  # Work on a copy to avoid modifying original
                df_inactive_copy['last_location_dt'] = pd.to_datetime(df_inactive_copy['last_location'], errors='coerce')
                df_inactive_copy['last_location_formatted'] = df_inactive_copy['last_location_dt'].dt.strftime('%Y-%m-%d %H:%M:%S').fillna('Never')
                # Replace 'last_location' with 'last_location_formatted' in the display columns
                if 'last_location' in available_cols:
                    available_cols[available_cols.index('last_location')] = 'last_location_formatted'
            else:
                df_inactive_copy = df_inactive.copy()
            
            # Format deployment_end for display
            if 'deployment_end' in df_inactive_copy.columns:
                # Clean up deployment end dates
                def format_deployment_end(date_str):
                    if pd.isna(date_str) or date_str == 'Open' or date_str == 'Unknown':
                        return 'Open'
                    try:
                        dt = pd.to_datetime(date_str)
                        return dt.strftime('%Y-%m-%d')
                    except:
                        return str(date_str)
                
                df_inactive_copy['deployment_end_formatted'] = df_inactive_copy['deployment_end'].apply(format_deployment_end)
                # Replace deployment_end with formatted version
                if 'deployment_end' in available_cols:
                    available_cols[available_cols.index('deployment_end')] = 'deployment_end_formatted'
            
            # Show only the inactive sources (not all sources)
            st.dataframe(
                df_inactive_copy[available_cols], 
                use_container_width=True,
                column_config={
                    'collar_key': 'Collar Key',
                    'subject_name': 'Subject Name', 
                    'deployment_end_formatted': 'Deployment End',
                    'last_location_formatted': 'Last Location',
                    'provider': 'Provider',
                    'source_id': 'Source ID'
                }
            )
            
            # Show summary by provider
            if 'provider' in df_inactive.columns:
                provider_counts = df_inactive['provider'].value_counts()
                st.subheader("📊 Inactive Sources by Provider")
                fig = px.bar(
                    x=provider_counts.index, 
                    y=provider_counts.values,
                    title="Number of Inactive Sources by Provider"
                )
                fig.update_layout(xaxis_title="Provider", yaxis_title="Number of Inactive Sources")
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.success("✅ No inactive sources found! All tracked sources have reported within the last 90 days.")
    else:
        st.write("Click the button above to start the inactive source analysis.")

def _main_implementation():
    """Main application logic"""
    init_session_state()
    
    # Header with logo
    with st.container():
        # Try to load and display logo
        logo_displayed = False
        
        # Get the absolute path to the logo file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(current_dir, '..', 'logo.png')  # Logo is in parent directory
        
        if os.path.exists(logo_path):
            try:
                col1, col2, col3 = st.columns([1, 2, 1])
                with col2:
                    st.image(logo_path, width=300)
                    st.markdown('<div class="logo-title" style="text-align: center;">Source Dashboard</div>', unsafe_allow_html=True)
                    st.markdown('<div class="logo-subtitle" style="text-align: center;">Source Tracking & Analytics</div>', unsafe_allow_html=True)
                    logo_displayed = True
            except Exception as e:
                st.error(f"Error loading logo: {str(e)}")
        
        # Fallback header without logo
        if not logo_displayed:
            st.title("🌍 Source Dashboard")
            st.markdown("Source (GPS unit) performance analytics and stock tracking")
    
    # Landing page (only shown if not authenticated yet)
    if not st.session_state.authenticated:
        #st.header("🌍 Source Dashboard")
        #st.write("Monitor and analyze EarthRanger tracking device sources.")
        
        # Show process overview on landing page
       # st.subheader("📋 Dashboard Features")
       # st.info("""
       # **🔐 Authentication:** Secure login with EarthRanger credentials
       # **📍 Location Tracking:** View latest positions of tracking devices
       # **📊 Activity Analysis:** 7-day location transmission charts
       # **⚠️ Inactive Monitoring:** Identify sources not reporting for >90 days
       # """)
        
        # Show authentication directly on landing page
        authenticate_earthranger()
        return
    
    # Sidebar navigation
    st.sidebar.title("Navigation")
    
    # Authentication status
    st.sidebar.markdown("### 🔐 Authentication ✅")
    if st.session_state.get('api_token'):
        st.sidebar.write("**Method:** API Token")
    elif st.session_state.get('username'):
        st.sidebar.write(f"**User:** {st.session_state.username}")
    
    # Show dashboard
    source_dashboard()
    
    # Sidebar options
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔧 Options")
    
    if st.sidebar.button("🔄 Refresh Data"):
        # Clear cached data
        get_all_sources.clear()
        st.rerun()
    
    if st.sidebar.button("🔓 Logout"):
        # Clear authentication
        for key in ['authenticated', 'api_token', 'headers']:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

# Make main() available for import while still allowing direct execution
if __name__ == "__main__":
    main()
