import streamlit as st
import pandas as pd
import geopandas as gpd
from datetime import datetime, timedelta, date
import plotly.express as px
import plotly.graph_objects as go
import json
import os
from pandas import json_normalize

# Handle NumPy 2.x compatibility warnings
import warnings
warnings.filterwarnings("ignore", message=".*copy keyword.*")
warnings.filterwarnings("ignore", message=".*np.array.*")

# Ecoscope imports for EarthRanger integration
try:
    from ecoscope.io.earthranger import EarthRangerIO
    ECOSCOPE_AVAILABLE = True
except ImportError:
    ECOSCOPE_AVAILABLE = False
    st.warning("⚠️ Ecoscope package not available. Please install ecoscope to use this dashboard.")

def _main_implementation():
    """Main application logic"""
    init_session_state()
    
    # Note: set_page_config is handled by the main Twiga Tools app when running as a page
    
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
                    st.markdown('<div class="logo-title" style="text-align: center;">Genetic Dashboard</div>', unsafe_allow_html=True)
                    st.markdown('<div class="logo-subtitle" style="text-align: center;">Biological Sample Event Monitoring</div>', unsafe_allow_html=True)
                    logo_displayed = True
            except Exception as e:
                st.error(f"Error loading logo: {str(e)}")
        
        # Fallback header without logo
        if not logo_displayed:
            st.title("🧬 Genetic Dashboard")
            st.markdown("Biological sample inventory and status")
    
    # Landing page (only shown if not authenticated yet)
    if not st.session_state.authenticated:
        # Show authentication directly on landing page
        authenticate_earthranger()
        return

    # After authentication, set up global variables like NANW dashboard
    username = st.session_state.username
    password = st.session_state.password
    
    # Sidebar navigation
    st.sidebar.title("Navigation")
    
    # Authentication status
    st.sidebar.markdown("### 🔐 Authentication ✅")
    if st.session_state.get('username'):
        st.sidebar.write(f"**User:** {st.session_state.username}")
    
    # Show dashboard
    genetic_dashboard()
    
    # Sidebar options
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔧 Options")
    
    if st.sidebar.button("🔄 Refresh Data"):
        # Clear cached data
        get_biological_sample_events.clear()
        st.rerun()
    
    if st.sidebar.button("🔓 Logout"):
        # Clear authentication
        for key in ['authenticated', 'username', 'password']:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

# Make main available at module level for import
def main():
    """Main application entry point - delegates to _main_implementation"""
    return _main_implementation()

# Custom CSS for better styling and widescreen layout
st.markdown("""
<style>
    /* Widescreen layout - reduce margins and padding */
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 0rem;
        padding-left: 1rem;
        padding-right: 1rem;
        max-width: none;
    }
    
    /* Remove default Streamlit margins */
    .main > div {
        padding-top: 0rem;
    }
    
    /* Full width content */
    .stApp > div:first-child {
        margin: 0;
        padding: 0;
    }
    
    /* Logo and header styling */
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
    
    /* Card styling */
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #2E8B57;
        margin: 0.5rem 0;
    }
    .sample-event {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 0.5rem 0;
        border-left: 4px solid #28a745;
    }
    
    /* Make dataframes use full width */
    .stDataFrame {
        width: 100%;
    }
    
    /* Sidebar adjustments for widescreen */
    .css-1d391kg {
        padding-top: 1rem;
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
    if 'server_url' not in st.session_state:
        st.session_state.server_url = "https://twiga.pamdas.org"

def er_login(username, password):
    """Simple login function like NANW dashboard with enhanced cloud compatibility"""
    try:
        # Try with explicit SSL settings for cloud compatibility
        import ssl
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        er = EarthRangerIO(
            server=st.session_state.server_url,
            username=username,
            password=password,
            verify_ssl=True  # Ensure SSL verification is explicit
        )
        # Try a simple call to check credentials - use events instead of subjects
        er.get_events(limit=1)  # This might work better than get_subjects
        return True
    except Exception as e:
        # Write detailed error info to Desktop for debugging
        try:
            desktop_path = os.path.expanduser(r"C:\Users\court\Desktop\er_login_error.txt")
            with open(desktop_path, "a") as f:
                f.write(f"[{datetime.now()}] Username: {username}\n")
                f.write(f"Server: {st.session_state.server_url}\n")
                f.write(f"Environment: {'DEPLOYED' if 'STREAMLIT_SHARING' in os.environ or 'STREAMLIT_CLOUD' in os.environ else 'LOCAL'}\n")
                f.write(f"Error Type: {type(e).__name__}\n")
                f.write(f"Error Message: {str(e)}\n")
                if hasattr(e, 'response') and e.response is not None:
                    f.write(f"HTTP Status: {e.response.status_code}\n")
                    f.write(f"Response Text: {e.response.text}\n")
                f.write("="*50 + "\n\n")
        except Exception as file_error:
            print(f"Failed to write error log: {file_error}")
        
        # Display error in UI for better debugging
        st.error(f"🚫 Authentication Failed: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            st.error(f"📊 HTTP Status: {e.response.status_code}")
            st.error(f"📝 Response: {e.response.text[:200]}...")
        
        return False

def authenticate_earthranger():
    """Handle EarthRanger authentication using ecoscope - simplified like NANW dashboard"""
    if not ECOSCOPE_AVAILABLE:
        st.error("❌ Ecoscope package is required but not available. Please install ecoscope.")
        return
        
    st.title("Login to Genetic Dashboard")
    st.info("**Server:** https://twiga.pamdas.org")
    
    # Show environment info for debugging
    env_type = "DEPLOYED" if ('STREAMLIT_SHARING' in os.environ or 'STREAMLIT_CLOUD' in os.environ) else "LOCAL"
    st.write(f"🔧 **Environment:** {env_type}")
    if env_type == "DEPLOYED":
        st.write("🌐 **Running on Streamlit Cloud/Sharing**")
    
    username = st.text_input("EarthRanger Username")
    password = st.text_input("EarthRanger Password", type="password")
    
    if st.button("Login"):
        if er_login(username, password):
            st.session_state.authenticated = True
            st.session_state.username = username
            st.session_state.password = password
            st.success("Login successful!")
            st.rerun()
        else:
            st.error("Invalid credentials. Please try again.")
    st.stop()

# @st.cache_data(ttl=3600)  # Cache disabled to ensure fresh data
def get_biological_sample_events(start_date=None, end_date=None, max_results=200):
    """Fetch biological sample events from EarthRanger using ecoscope"""
    if not ECOSCOPE_AVAILABLE:
        st.error("❌ Ecoscope package is required but not available.")
        return pd.DataFrame()
        
    if not st.session_state.get('username') or not st.session_state.get('password'):
        return pd.DataFrame()
    
    try:
        # Create EarthRanger connection using stored credentials
        er_io = EarthRangerIO(
            server=st.session_state.server_url,
            username=st.session_state.username,
            password=st.session_state.password
        )
        
        # Build parameters for ecoscope get_events
        # Note: Don't pass event_type to get_events as it expects UUIDs, 
        # we'll filter by event_type string after getting the data
        kwargs = {
            'event_category': 'veterinary',
            'include_details': True,
            'include_notes': True,
            'max_results': max_results,  # Use the parameter
            'drop_null_geometry': False  # Keep events without geometry for now
        }
        
        # Add date filters if provided
        if start_date:
            kwargs['since'] = start_date.strftime('%Y-%m-%dT00:00:00Z')
        if end_date:
            kwargs['until'] = end_date.strftime('%Y-%m-%dT23:59:59Z')
        
        # Get events using ecoscope (all veterinary events)
        # Handle NumPy 2.x compatibility issue
        import warnings
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=".*copy keyword.*")
            warnings.filterwarnings("ignore", message=".*np.array.*")
            gdf_events = er_io.get_events(**kwargs)
        
        if gdf_events.empty:
            return pd.DataFrame()
        
        # Convert GeoDataFrame to regular DataFrame for easier handling in Streamlit
        # Handle potential NumPy compatibility issues during conversion
        try:
            df = pd.DataFrame(gdf_events.drop(columns='geometry', errors='ignore'))
        except Exception as conversion_error:
            st.warning(f"Geometry conversion warning: {str(conversion_error)}")
            # Fallback: convert without geometry handling
            df = pd.DataFrame(gdf_events)
            if 'geometry' in df.columns:
                df = df.drop(columns='geometry', errors='ignore')
        
        # Filter by event_type after getting the data (avoiding UUID requirement)
        if 'event_type' in df.columns:
            df = df[df['event_type'] == 'biological_sample']
        
        if df.empty:
            return pd.DataFrame()
        
        # Process the data
        if 'time' in df.columns:
            df['time'] = pd.to_datetime(df['time'])
            df['date'] = df['time'].dt.date
            df['year'] = df['time'].dt.year
            df['month'] = df['time'].dt.month
            df['month_name'] = df['time'].dt.strftime('%B')
        
        # Add location information if geometry was available, but preserve CSV coordinates if they exist
        if not gdf_events.empty and 'geometry' in gdf_events.columns:
            # Extract coordinates from geometry with error handling
            try:
                geo_latitude = gdf_events.geometry.apply(lambda x: x.y if x and hasattr(x, 'y') else None)
                geo_longitude = gdf_events.geometry.apply(lambda x: x.x if x and hasattr(x, 'x') else None)
                

                
                # Only use geometry coordinates where CSV coordinates are missing/zero
                if 'latitude' not in df.columns:
                    df['latitude'] = geo_latitude
                else:
                    # Fill missing or zero values with geometry coordinates
                    df['latitude'] = df['latitude'].fillna(geo_latitude)
                    df.loc[(df['latitude'] == 0) & (geo_latitude.notna()), 'latitude'] = geo_latitude
                
                if 'longitude' not in df.columns:
                    df['longitude'] = geo_longitude
                else:
                    # Fill missing or zero values with geometry coordinates
                    df['longitude'] = df['longitude'].fillna(geo_longitude)
                    df.loc[(df['longitude'] == 0) & (geo_longitude.notna()), 'longitude'] = geo_longitude
                    
            except Exception as geo_error:
                st.warning(f"Geometry processing warning: {str(geo_error)}")
                # Continue without geometry data
                pass
        
        # Extract country and site information from event_details and check for coordinate data
        if 'event_details' in df.columns:
            countries = []
            sites = []
            csv_latitudes = []
            csv_longitudes = []
            
            for _, row in df.iterrows():
                event_details = row.get('event_details', {})
                serial_number = row.get('serial_number', 'Unknown')
                
                # Extract country (iso) and site from event_details
                country = None
                site = None
                csv_lat = None
                csv_lng = None
                
                if isinstance(event_details, dict):
                    # Direct access to country and site fields - check girsam_ prefixed fields first
                    country = event_details.get('girsam_iso') or event_details.get('country') or event_details.get('iso')
                    site = event_details.get('girsam_site') or event_details.get('site')
                    
                    # Check for coordinate data from the original CSV upload
                    if 'latitude' in event_details:
                        try:
                            csv_lat = float(event_details['latitude'])
                        except (ValueError, TypeError):
                            csv_lat = None
                    if 'longitude' in event_details:
                        try:
                            csv_lng = float(event_details['longitude'])
                        except (ValueError, TypeError):
                            csv_lng = None
                
                # CRITICAL: Also check the 'location' field for correct coordinates
                if csv_lat is None or csv_lng is None:
                    location = row.get('location', {})
                    if isinstance(location, dict):
                        if csv_lat is None and 'latitude' in location:
                            try:
                                csv_lat = float(location['latitude'])
                            except (ValueError, TypeError):
                                pass
                        if csv_lng is None and 'longitude' in location:
                            try:
                                csv_lng = float(location['longitude'])
                            except (ValueError, TypeError):
                                pass
                    
                    # Also check nested structures (girsam) as fallback - prioritize iso field
                    if not country and 'girsam' in event_details:
                        girsam_data = event_details.get('girsam', {})
                        if isinstance(girsam_data, dict):
                            # Try iso first, then country as fallback
                            country = girsam_data.get('iso') or girsam_data.get('country')
                    if not site and 'girsam' in event_details:
                        girsam_data = event_details.get('girsam', {})
                        if isinstance(girsam_data, dict):
                            site = girsam_data.get('site')
                            
                elif isinstance(event_details, str):
                    # Try to parse JSON string
                    try:
                        parsed_details = json.loads(event_details)
                        if isinstance(parsed_details, dict):
                            country = parsed_details.get('girsam_iso') or parsed_details.get('country') or parsed_details.get('iso')
                            site = parsed_details.get('girsam_site') or parsed_details.get('site')
                            
                            # Check for coordinate data
                            if 'latitude' in parsed_details:
                                try:
                                    csv_lat = float(parsed_details['latitude'])
                                except (ValueError, TypeError):
                                    csv_lat = None
                            if 'longitude' in parsed_details:
                                try:
                                    csv_lng = float(parsed_details['longitude'])
                                except (ValueError, TypeError):
                                    csv_lng = None
                            
                            # Check nested structures - prioritize iso field
                            if not country and 'girsam' in parsed_details:
                                girsam_data = parsed_details.get('girsam', {})
                                if isinstance(girsam_data, dict):
                                    country = girsam_data.get('iso') or girsam_data.get('country')
                            if not site and 'girsam' in parsed_details:
                                girsam_data = parsed_details.get('girsam', {})
                                if isinstance(girsam_data, dict):
                                    site = girsam_data.get('site')
                    except json.JSONDecodeError:
                        pass
                
                # Clean and append values
                countries.append(str(country).strip() if country and str(country).strip() not in ['None', 'null', '', 'nan'] else "Unknown")
                sites.append(str(site).strip() if site and str(site).strip() not in ['None', 'null', '', 'nan'] else "Unknown")
                csv_latitudes.append(csv_lat)
                csv_longitudes.append(csv_lng)
            
            df['country'] = countries
            df['site'] = sites
            
            # Prioritize CSV coordinates from event_details over any other source
            csv_coords_found = any(lat is not None for lat in csv_latitudes)
            if csv_coords_found:
                
                # Initialize coordinate columns if they don't exist
                if 'latitude' not in df.columns:
                    df['latitude'] = [None] * len(df)
                if 'longitude' not in df.columns:
                    df['longitude'] = [None] * len(df)
                
                # Set coordinates from CSV data, OVERRIDING any geometry coordinates
                for i, (lat, lng) in enumerate(zip(csv_latitudes, csv_longitudes)):
                    if lat is not None and lng is not None:
                        # Force CSV coordinates to override any existing coordinates (including geometry)
                        df.iloc[i, df.columns.get_loc('latitude')] = lat
                        df.iloc[i, df.columns.get_loc('longitude')] = lng
                    elif 'latitude' in df.columns and 'longitude' in df.columns:
                        # If CSV coordinates are missing, but we have columns, ensure they're not left as zero
                        if pd.isna(df.iloc[i, df.columns.get_loc('latitude')]) or df.iloc[i, df.columns.get_loc('latitude')] == 0:
                            df.iloc[i, df.columns.get_loc('latitude')] = None
                        if pd.isna(df.iloc[i, df.columns.get_loc('longitude')]) or df.iloc[i, df.columns.get_loc('longitude')] == 0:
                            df.iloc[i, df.columns.get_loc('longitude')] = None
            else:
                pass
        else:
            df['country'] = "Unknown"
            df['site'] = "Unknown"
        
        # Also create flattened detail fields for display (this ensures both approaches work)
        try:
            if 'event_details' in df.columns:
                # Quick flattening for key fields to ensure we have the flattened columns too
                girsam_iso_values = []
                girsam_site_values = []
                
                for _, row in df.iterrows():
                    event_details = row.get('event_details', {})
                    iso_val = None
                    site_val = None
                    
                    if isinstance(event_details, dict):
                        # Check girsam_ prefixed fields first (root level)
                        iso_val = event_details.get('girsam_iso')
                        site_val = event_details.get('girsam_site')
                        
                        # Fallback: Check girsam nested structure - prioritize iso field
                        if not iso_val and 'girsam' in event_details:
                            girsam_data = event_details.get('girsam', {})
                            if isinstance(girsam_data, dict):
                                iso_val = girsam_data.get('iso') or girsam_data.get('country')
                        if not site_val and 'girsam' in event_details:
                            girsam_data = event_details.get('girsam', {})
                            if isinstance(girsam_data, dict):
                                site_val = girsam_data.get('site')
                    elif isinstance(event_details, str):
                        try:
                            parsed_details = json.loads(event_details)
                            if isinstance(parsed_details, dict):
                                # Check girsam_ prefixed fields first
                                iso_val = parsed_details.get('girsam_iso')
                                site_val = parsed_details.get('girsam_site')
                                
                                # Fallback: check nested girsam structure
                                if not iso_val and 'girsam' in parsed_details:
                                    girsam_data = parsed_details.get('girsam', {})
                                    if isinstance(girsam_data, dict):
                                        iso_val = girsam_data.get('iso') or girsam_data.get('country')
                                if not site_val and 'girsam' in parsed_details:
                                    girsam_data = parsed_details.get('girsam', {})
                                    if isinstance(girsam_data, dict):
                                        site_val = girsam_data.get('site')
                        except json.JSONDecodeError:
                            pass
                    
                    girsam_iso_values.append(str(iso_val).strip() if iso_val and str(iso_val).strip() not in ['None', 'null', '', 'nan'] else "Unknown")
                    girsam_site_values.append(str(site_val).strip() if site_val and str(site_val).strip() not in ['None', 'null', '', 'nan'] else "Unknown")
                
                # Add the flattened columns
                df['details_girsam_iso'] = girsam_iso_values
                df['details_girsam_site'] = girsam_site_values
        except Exception as flatten_error:
            st.warning(f"Field flattening warning: {str(flatten_error)}")
            # Continue without flattened fields
            pass
        
        # Debug: Check coordinate sources
        if 'latitude' in df.columns and 'longitude' in df.columns:
            # Check for mismatched coordinates (Namibian sites with non-Namibian coordinates)
            namibian_events = df[df['country'].str.upper() == 'NAM'] if 'country' in df.columns else df
            if not namibian_events.empty:
                # Namibia longitude should be roughly 12°E to 25°E
                suspicious_coords = namibian_events[
                    (namibian_events['longitude'] < 10) | (namibian_events['longitude'] > 26)
                ]
                if not suspicious_coords.empty:
                    pass
        
        return df
        
    except Exception as e:
        st.error(f"Error fetching biological sample events: {str(e)}")
        return pd.DataFrame()

def display_event_details_table(df_events):
    """Display biological sample events in a comprehensive table format"""
    if df_events.empty:
        st.warning("No biological sample events found.")
        return df_events
    
    st.subheader("📋 Biological Sample Events Table")
    
    # Prepare the data for display
    display_df = df_events.copy()
    
    # Format datetime columns
    if 'time' in display_df.columns:
        display_df['event_datetime'] = pd.to_datetime(display_df['time']).dt.strftime('%Y-%m-%d %H:%M:%S')
    
    if 'created_at' in display_df.columns:
        display_df['created_datetime'] = pd.to_datetime(display_df['created_at'], errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S')
    
    if 'updated_at' in display_df.columns:
        display_df['updated_datetime'] = pd.to_datetime(display_df['updated_at'], errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S')
    
    # Flatten event_details if it exists
    if 'event_details' in display_df.columns:
        # Try to normalize event_details with better handling
        details_expanded = []
        for idx, row in display_df.iterrows():
            details = row.get('event_details', {})
            flattened = {}
            
            if isinstance(details, dict):
                # Recursively flatten nested dictionaries
                def flatten_dict(d, parent_key='', sep='_'):
                    items = []
                    for k, v in d.items():
                        new_key = f'details_{parent_key}{sep}{k}' if parent_key else f'details_{k}'
                        if isinstance(v, dict):
                            items.extend(flatten_dict(v, new_key, sep=sep).items())
                        elif isinstance(v, list):
                            # Convert lists to strings but also create individual columns if short
                            flattened[new_key] = str(v)
                            if len(v) <= 5:  # For short lists, also create indexed columns
                                for i, item in enumerate(v):
                                    flattened[f'{new_key}_{i}'] = str(item)
                        else:
                            flattened[new_key] = v
                    return dict(items)
                
                flattened.update(flatten_dict(details))
            elif isinstance(details, str):
                # Try to parse JSON string
                try:
                    parsed_details = json.loads(details)
                    if isinstance(parsed_details, dict):
                        def flatten_dict(d, parent_key='', sep='_'):
                            items = []
                            for k, v in d.items():
                                new_key = f'details_{parent_key}{sep}{k}' if parent_key else f'details_{k}'
                                if isinstance(v, dict):
                                    items.extend(flatten_dict(v, new_key, sep=sep).items())
                                elif isinstance(v, list):
                                    flattened[new_key] = str(v)
                                    if len(v) <= 5:
                                        for i, item in enumerate(v):
                                            flattened[f'{new_key}_{i}'] = str(item)
                                else:
                                    flattened[new_key] = v
                            return dict(items)
                        flattened.update(flatten_dict(parsed_details))
                    else:
                        flattened['details_parsed'] = str(parsed_details)
                except json.JSONDecodeError:
                    flattened['details_raw'] = str(details)
            else:
                flattened['details_raw'] = str(details)
            
            details_expanded.append(flattened)
        
        # Convert to DataFrame and merge (avoid creating duplicates)
        if details_expanded:
            details_df = pd.DataFrame(details_expanded)
            
            # Reset index to ensure proper alignment when merging
            details_df.reset_index(drop=True, inplace=True)
            display_df.reset_index(drop=True, inplace=True)
            
            # Add the details columns to the main dataframe, but skip if they already exist
            for col in details_df.columns:
                if col not in display_df.columns:
                    display_df[col] = details_df[col]
    
    # Ensure alias columns exist for filtering (if not already created in fetch function)
    if 'country' not in display_df.columns:
        if 'details_girsam_iso' in display_df.columns:
            display_df['country'] = display_df['details_girsam_iso']
        else:
            display_df['country'] = "Unknown"
        
    if 'site' not in display_df.columns:
        if 'details_girsam_site' in display_df.columns:
            display_df['site'] = display_df['details_girsam_site']
        else:
            display_df['site'] = "Unknown"
    
    # Define preferred column order - cleaned up to only essential columns
    preferred_columns = [
        'id',                    # Event ID
        'serial_number',         # Serial Number
        'event_datetime',        # Event Date/Time
        'details_girsam_iso',    # Country (ISO) - from flattened event_details
        'details_girsam_site',   # Site Name - from flattened event_details
        'details_girsam_origin', # Origin - from flattened event_details
        'latitude',              # Latitude
        'longitude'              # Longitude
    ]
    
    # Add all event_details columns (these are the exploded details) except excluded ones
    excluded_columns = ['details_updates', 'event_type']
    details_columns = [col for col in display_df.columns 
                      if col.startswith('details_') and col not in excluded_columns and col not in preferred_columns]
    preferred_columns.extend(details_columns)
    
    # Select only existing columns from our preferred list and remove duplicates
    available_columns = []
    seen_columns = set()
    for col in preferred_columns:
        if col in display_df.columns and col not in seen_columns:
            available_columns.append(col)
            seen_columns.add(col)
    
    # Create custom column configuration with renamed headers
    column_config = {
        'id': 'Event ID',
        'serial_number': 'Serial Number',
        'event_datetime': 'Event Date/Time',
        'country': 'Country (ISO)',
        'site': 'Site Name',
        'details_girsam_iso': 'Country (ISO)',  # Map flattened field to country
        'details_girsam_site': 'Site Name',     # Map flattened field to site
        'latitude': st.column_config.NumberColumn('Latitude', format="%.6f"),
        'longitude': st.column_config.NumberColumn('Longitude', format="%.6f"),
        'details_girsam_age': 'Giraffe Age',
        'details_girsam_sex': 'Giraffe Sex',
        'details_girsam_proc': 'Sample Processed',
        'details_girsam_ship': 'Sample Shipped',
        'details_girsam_type': 'Sample Type',
        'details_girsam_notes': 'Notes',
        'details_girsam_smpid': 'Sample ID',
        'details_girsam_smpid2': 'Secondary Sample ID',
        'details_girsam_subid': 'Giraffe ER ID',
        'details_girsam_species': 'Species',
        'details_girsam_status': 'Sample Status',
        'details_girsam_origin': 'Origin'
    }
    
    # Display the table with comprehensive deduplication
    # First, ensure the DataFrame itself has no duplicate columns
    if len(display_df.columns) != len(set(display_df.columns)):
        # Remove duplicates keeping first occurrence
        display_df = display_df.loc[:, ~display_df.columns.duplicated(keep='first')]
        
    # Then ensure available_columns has no duplicates and all columns exist
    final_columns = []
    seen = set()
    for col in available_columns:
        if col in display_df.columns and col not in seen:
            final_columns.append(col)
            seen.add(col)
    
    st.dataframe(
        display_df[final_columns],
        use_container_width=True,
        column_config=column_config
    )
    
    # Return the exploded dataframe for use in mapping and other functions
    return display_df

def display_events_map(df_events):
    """Display biological sample events on an interactive map colored by processing status"""
    if df_events.empty:
        return
    
    # Check if we have location data
    if 'latitude' not in df_events.columns or 'longitude' not in df_events.columns:
        st.warning("No location data available for mapping.")
        return
    
    # Filter events with valid coordinates
    df_map = df_events[
        (df_events['latitude'].notna()) & 
        (df_events['longitude'].notna()) &
        (df_events['latitude'] != 0) &
        (df_events['longitude'] != 0)
    ].copy()
    
    if df_map.empty:
        st.warning("No events with valid coordinates found for mapping.")
        return
    
    st.subheader("🗺️ Biological Sample Events Map")
    
    # Create hover text with event details including sample status
    df_map['hover_text'] = df_map.apply(lambda row: 
        f"<b>Event ID:</b> {row.get('id', 'N/A')}<br>" +
        f"<b>Serial:</b> {row.get('serial_number', 'N/A')}<br>" +
        f"<b>Date:</b> {row.get('time', 'N/A')}<br>" +
        f"<b>Sample ID:</b> {row.get('details_girsam_smpid', 'N/A')}<br>" +
        f"<b>Species:</b> {row.get('details_girsam_species', 'N/A')}<br>" +
        f"<b>Sample Status:</b> {row.get('details_girsam_status', 'N/A')}", axis=1)
    
    # Use sample status for coloring
    color_column = 'details_girsam_status'
    if color_column in df_map.columns:
        # Clean up sample status values (handle NaN and empty values)
        df_map[color_column] = df_map[color_column].fillna('Unknown')
        df_map[color_column] = df_map[color_column].replace('', 'Unknown')
        
        # Create custom color mapping for specific statuses
        status_color_map = {
            'analysed': '#DB580F',  # Orange
            'office': '#6C757D',    # Grey
            'shipped': '#28A745',    # Green
            'collected': '#4683B7' # blue 
        }
        
        # Get unique statuses and create color mapping
        unique_statuses = df_map[color_column].unique()
        color_discrete_map = {}
        for status in unique_statuses:
            color_discrete_map[status] = status_color_map.get(status.lower(), '#FFC107')  # Default yellow for unknown
        
        # Create the map with sample status coloring using custom color mapping
        fig = px.scatter_mapbox(
            df_map,
            lat='latitude',
            lon='longitude',
            hover_name='serial_number',
            hover_data={
                'latitude': ':.6f',
                'longitude': ':.6f',
                'time': True,
                'details_girsam_smpid': True,
                'details_girsam_species': True,
                'details_girsam_status': True
            },
            color=color_column,
            color_discrete_map=color_discrete_map,
            size_max=15,
            zoom=4,  # Zoom level for Southern Africa region
            center={"lat": -25.0, "lon": 25.0},  # Center on Southern Africa
            height=600,
            title=f"Biological Sample Events by Sample Status ({len(df_map)} events with coordinates)",
            labels={color_column: 'Sample Status'}
        )
    else:
        # Fallback if processing status column doesn't exist
        fig = px.scatter_mapbox(
            df_map,
            lat='latitude',
            lon='longitude',
            hover_name='serial_number',
            hover_data={
                'latitude': ':.6f',
                'longitude': ':.6f',
                'time': True,
                'details_girsam_smpid': True,
                'details_girsam_species': True,
                'details_girsam_status': True
            },
            size_max=15,
            zoom=4,  # Zoom level for Southern Africa region
            center={"lat": -25.0, "lon": 25.0},  # Center on Southern Africa
            height=600,
            title=f"Biological Sample Events Map ({len(df_map)} events with coordinates)"
        )
    
    # Update map layout
    fig.update_layout(
        mapbox_style="open-street-map",
        margin={"r": 0, "t": 50, "l": 0, "b": 0},
        showlegend=True
    )
    
    # Make dots larger and more visible
    fig.update_traces(marker=dict(size=12, opacity=0.8))
    
    # Display the map
    st.plotly_chart(fig, use_container_width=True)
    
    # Show sample status summary
    if color_column in df_map.columns:
        st.subheader("📊 Sample Status Summary")
        status_counts = df_map[color_column].value_counts()
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.write("**Sample Status Breakdown:**")
            for status, count in status_counts.items():
                percentage = (count / len(df_map) * 100)
                st.write(f"• {status}: {count} samples ({percentage:.1f}%)")
        
        with col2:
            # Create a simple bar chart of sample status with custom color mapping
            if len(status_counts) > 0:
                # Create custom color mapping for specific statuses
                status_color_map = {
                    'analysed': '#DB580F',  # Orange
                    'office': '#6C757D',    # Grey
                    'shipped': '#28A745'    # Green
                }
                
                # Map colors to the actual status values in the data
                colors = [status_color_map.get(status.lower(), '#FFC107') for status in status_counts.index]
                
                fig_bar = px.bar(
                    x=status_counts.index,
                    y=status_counts.values,
                    labels={'x': 'Sample Status', 'y': 'Number of Samples'},
                    title="Sample Status Distribution",
                    color=status_counts.index,
                    color_discrete_map={status: color for status, color in zip(status_counts.index, colors)}
                )
                fig_bar.update_layout(height=300, showlegend=False)
                fig_bar.update_xaxes(title_text="Sample Status")
                st.plotly_chart(fig_bar, use_container_width=True)
        
        with col3:
            # Create a pie chart of sample status with custom color mapping
            if len(status_counts) > 0:
                # Create custom color mapping for specific statuses
                status_color_map = {
                    'analysed': '#DB580F',  # Orange
                    'office': '#6C757D',    # Grey
                    'shipped': '#28A745'    # Green
                }
                
                # Map colors to the actual status values in the data
                colors = [status_color_map.get(status.lower(), '#FFC107') for status in status_counts.index]
                
                fig_pie = px.pie(
                    values=status_counts.values,
                    names=status_counts.index,
                    title="Sample Status Distribution",
                    color=status_counts.index,
                    color_discrete_map={status: color for status, color in zip(status_counts.index, colors)}
                )
                fig_pie.update_layout(height=300, showlegend=True)
                st.plotly_chart(fig_pie, use_container_width=True)

def genetic_dashboard():
    """Main genetic dashboard interface"""
    #st.header("🧬 Genetic Dashboard")
    #st.markdown("Monitor and analyze biological sample events from EarthRanger")
    
    # Dashboard controls - use wider layout for max results only
    col1, col2, col3 = st.columns([6, 2, 1])

    with col1:
        st.write("")  # Spacer

    with col2:
        st.write("")  # Spacer

    with col3:
        # Add max results control
        max_results = st.selectbox(
            "Max Results",
            options=[50, 100, 200, 500],
            index=2,  # Default to 200
            help="Limit the number of events to fetch (higher numbers may be slower)"
        )

    # Default date values for initial data fetch - cover 2024 data
    start_date_temp = date(2024, 1, 1)  # Start of 2024
    end_date_temp = date(2024, 12, 31)  # End of 2024

    # Fetch biological sample events with the selected max_results for initial display
    with st.spinner("Fetching biological sample events..."):
        df_events = get_biological_sample_events(start_date_temp, end_date_temp, max_results)

    if df_events.empty:
        st.warning("No biological sample events found for the initial date range (2024). Try adjusting the date filters below.")
        # Don't return here - still show the filters so user can adjust dates
        df_events = pd.DataFrame()  # Continue with empty dataframe    # Filter section - always show, even if initial data is empty
    st.subheader("🔍 Filters")
    
    # Get unique countries from the data (if any)
    if not df_events.empty and 'country' in df_events.columns:
        available_countries = sorted([c for c in df_events['country'].unique() if c not in ['Unknown', 'Other', None] and str(c).strip() != ''])
        if 'Other' in df_events['country'].values:
            available_countries.append('Other')
        if 'Unknown' in df_events['country'].values:
            available_countries.append('Unknown')
    else:
        available_countries = []
    
    # Get unique sites from the data (if any)
    if not df_events.empty and 'site' in df_events.columns:
        available_sites = sorted([s for s in df_events['site'].unique() if s not in ['Unknown', 'Other', None] and str(s).strip() != ''])
        if 'Other' in df_events['site'].values:
            available_sites.append('Other')
        if 'Unknown' in df_events['site'].values:
            available_sites.append('Unknown')
    else:
        available_sites = []
    
    # Get unique sample types from the data - need to extract from event_details
    available_sample_types = []
    
    if not df_events.empty and 'event_details' in df_events.columns:
        # Extract sample types from the nested event_details structure
        sample_types_found = []
        
        for _, row in df_events.iterrows():
            event_details = row.get('event_details', {})
            
            # Handle different data structures
            sample_type = None
            if isinstance(event_details, dict):
                # Direct access
                sample_type = event_details.get('girsam_type')
                # Also check nested structures
                if not sample_type and 'girsam' in event_details:
                    girsam_data = event_details.get('girsam', {})
                    if isinstance(girsam_data, dict):
                        sample_type = girsam_data.get('type')
            elif isinstance(event_details, str):
                # Try to parse JSON string
                try:
                    parsed_details = json.loads(event_details)
                    if isinstance(parsed_details, dict):
                        sample_type = parsed_details.get('girsam_type')
                        if not sample_type and 'girsam' in parsed_details:
                            girsam_data = parsed_details.get('girsam', {})
                            if isinstance(girsam_data, dict):
                                sample_type = girsam_data.get('type')
                except json.JSONDecodeError:
                    pass
            
            # Clean and add the sample type if found
            if sample_type:
                str_value = str(sample_type).strip()
                if str_value and str_value.lower() not in ['none', 'null', '', 'nan']:
                    sample_types_found.append(str_value)
        
        # Get unique values and sort
        available_sample_types = sorted(list(set(sample_types_found)))
    
    # Get unique species from the data - need to extract from event_details
    available_species = []
    
    if not df_events.empty and 'event_details' in df_events.columns:
        # Extract species from the nested event_details structure
        species_found = []
        
        for _, row in df_events.iterrows():
            event_details = row.get('event_details', {})
            
            # Handle different data structures
            species = None
            if isinstance(event_details, dict):
                # Direct access
                species = event_details.get('girsam_species')
                # Also check nested structures
                if not species and 'girsam' in event_details:
                    girsam_data = event_details.get('girsam', {})
                    if isinstance(girsam_data, dict):
                        species = girsam_data.get('species')
            elif isinstance(event_details, str):
                # Try to parse JSON string
                try:
                    parsed_details = json.loads(event_details)
                    if isinstance(parsed_details, dict):
                        species = parsed_details.get('girsam_species')
                        if not species and 'girsam' in parsed_details:
                            girsam_data = parsed_details.get('girsam', {})
                            if isinstance(girsam_data, dict):
                                species = girsam_data.get('species')
                except json.JSONDecodeError:
                    pass
            
            # Clean and add the species if found
            if species:
                str_value = str(species).strip()
                if str_value and str_value.lower() not in ['none', 'null', '', 'nan']:
                    species_found.append(str_value)
        
        # Get unique values and sort
        available_species = sorted(list(set(species_found)))
    
    # Summary metrics above filters - horizontal layout
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Countries", 
            len([c for c in available_countries if c not in ['Unknown', 'Other']]) if available_countries else 0,
            help="Number of countries with identified events"
        )
    
    with col2:
        st.metric(
            "Sites", 
            len([s for s in available_sites if s not in ['Unknown', 'Other']]) if available_sites else 0,
            help="Number of sites with identified events"
        )
    
    with col3:
        st.metric(
            "Species", 
            len(available_species) if available_species else 0,
            help="Number of species with events"
        )
    
    # Filter selection interface - now with 4 columns for country, site, sample type, and species
    col1, col2, col3, col4 = st.columns([3, 3, 3, 3])
    
    with col1:
        country_options = ["All Countries"] + available_countries if available_countries else ["All Countries", "No data available"]
        selected_country = st.selectbox(
            "🌍 Country",
            options=country_options,
            index=0,
            help="Filter biological sample events by country"
        )
    
    with col2:
        site_options = ["All Sites"] + available_sites if available_sites else ["All Sites", "No data available"]
        selected_site = st.selectbox(
            "📍 Site",
            options=site_options,
            index=0,
            help="Filter biological sample events by site"
        )
    
    with col3:
        if available_sample_types:
            selected_sample_type = st.selectbox(
                "🧪 Sample Type",
                options=["All Sample Types"] + available_sample_types,
                index=0,
                help="Filter biological sample events by sample type"
            )
        else:
            selected_sample_type = st.selectbox(
                "🧪 Sample Type",
                options=["All Sample Types", "No sample types found"],
                index=0,
                help="No sample type information available in the data"
            )
    
    with col4:
        if available_species:
            selected_species = st.selectbox(
                "🦒 Species",
                options=["All Species"] + available_species,
                index=0,
                help="Filter biological sample events by species"
            )
        else:
            selected_species = st.selectbox(
                "🦒 Species",
                options=["All Species", "No species found"],
                index=0,
                help="No species information available in the data"
            )
    
    # Date filters under the main filters section
    st.write("")  # Small spacer
    col1, col2, col3, col4 = st.columns([3, 3, 3, 3])
    
    with col1:
        start_date = st.date_input(
            "📅 Start Date",
            value=date.today().replace(year=date.today().year - 1),  # Default to 1 year ago
            help="Select the earliest date for biological sample events"
        )
    
    with col2:
        end_date = st.date_input(
            "📅 End Date", 
            value=date.today(),  # Default to today's date
            help="Select the latest date for biological sample events"
        )
    
    with col3:
        st.write("")  # Spacer
    
    with col4:
        if st.button("🔄 Refresh Data", type="primary"):
            # Clear cache to force refresh
            get_biological_sample_events.clear()
            st.rerun()
    
    # Validate date range and refetch data if dates are different
    if start_date > end_date:
        st.error("❌ Start date cannot be after end date")
        return
    
    # Refetch data if date range has changed or if initial data was empty
    if start_date != start_date_temp or end_date != end_date_temp or df_events.empty:
        with st.spinner("Updating data for selected date range..."):
            df_events = get_biological_sample_events(start_date, end_date, max_results)
        
        if df_events.empty:
            st.warning("No biological sample events found for the selected date range.")
            # Still continue to show empty dashboard with filters available
    
    # Apply filters (only if we have data)
    df_filtered = df_events.copy()
    filter_info = []
    
    # Apply country filter
    if selected_country != "All Countries":
        df_filtered = df_filtered[df_filtered['country'] == selected_country]
        filter_info.append(f"Country: {selected_country}")
    
    # Apply site filter
    if selected_site != "All Sites":
        df_filtered = df_filtered[df_filtered['site'] == selected_site]
        filter_info.append(f"Site: {selected_site}")
    
    # Apply sample type filter
    if selected_sample_type != "All Sample Types" and selected_sample_type != "No sample types found":
        # Filter based on event_details structure
        filtered_indices = []
        for idx, row in df_filtered.iterrows():
            event_details = row.get('event_details', {})
            
            # Extract sample type from event_details
            sample_type = None
            if isinstance(event_details, dict):
                sample_type = event_details.get('girsam_type')
                if not sample_type and 'girsam' in event_details:
                    girsam_data = event_details.get('girsam', {})
                    if isinstance(girsam_data, dict):
                        sample_type = girsam_data.get('type')
            elif isinstance(event_details, str):
                try:
                    parsed_details = json.loads(event_details)
                    if isinstance(parsed_details, dict):
                        sample_type = parsed_details.get('girsam_type')
                        if not sample_type and 'girsam' in parsed_details:
                            girsam_data = parsed_details.get('girsam', {})
                            if isinstance(girsam_data, dict):
                                sample_type = girsam_data.get('type')
                except json.JSONDecodeError:
                    pass
            
            # Check if this row matches the selected sample type
            if sample_type and str(sample_type).strip() == selected_sample_type:
                filtered_indices.append(idx)
        
        # Apply the filter
        if filtered_indices:
            df_filtered = df_filtered.loc[filtered_indices]
        else:
            df_filtered = df_filtered.iloc[0:0]  # Empty dataframe with same structure
        
        filter_info.append(f"Sample Type: {selected_sample_type}")
    
    # Apply species filter
    if selected_species != "All Species" and selected_species != "No species found":
        # Filter based on event_details structure
        filtered_indices = []
        for idx, row in df_filtered.iterrows():
            event_details = row.get('event_details', {})
            
            # Extract species from event_details
            species = None
            if isinstance(event_details, dict):
                species = event_details.get('girsam_species')
                if not species and 'girsam' in event_details:
                    girsam_data = event_details.get('girsam', {})
                    if isinstance(girsam_data, dict):
                        species = girsam_data.get('species')
            elif isinstance(event_details, str):
                try:
                    parsed_details = json.loads(event_details)
                    if isinstance(parsed_details, dict):
                        species = parsed_details.get('girsam_species')
                        if not species and 'girsam' in parsed_details:
                            girsam_data = parsed_details.get('girsam', {})
                            if isinstance(girsam_data, dict):
                                species = girsam_data.get('species')
                except json.JSONDecodeError:
                    pass
            
            # Check if this row matches the selected species
            if species and str(species).strip() == selected_species:
                filtered_indices.append(idx)
        
        # Apply the filter
        if filtered_indices:
            df_filtered = df_filtered.loc[filtered_indices]
        else:
            df_filtered = df_filtered.iloc[0:0]  # Empty dataframe with same structure
        
        filter_info.append(f"Species: {selected_species}")
    
    # Display filter status
    if filter_info:
        st.info(f"📊 Filtered by: **{' | '.join(filter_info)}** ({len(df_filtered)} events)")
    else:
        st.info(f"📊 Showing **all events** ({len(df_filtered)} events)")
    
    # Check if filtered data is empty
    if df_filtered.empty:
        if filter_info:
            filter_desc = ' and '.join(filter_info)
            st.warning(f"No biological sample events found for {filter_desc} in the selected date range.")
        else:
            st.warning("No biological sample events found in the selected date range. Try adjusting the date filters or check if you have data for this period.")
        return
    
    # Display the events table and get exploded data
    df_exploded = display_event_details_table(df_filtered)
    
    # Add some spacing
    st.markdown("---")
    
    # Display the map with exploded data for processing status coloring
    display_events_map(df_exploded)

# Make main() available for import while still allowing direct execution
if __name__ == "__main__":
    main()
