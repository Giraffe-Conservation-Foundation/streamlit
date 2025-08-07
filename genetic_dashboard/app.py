import streamlit as st
import pandas as pd
import geopandas as gpd
from datetime import datetime, timedelta, date
import plotly.express as px
import plotly.graph_objects as go
import json
import os
from pandas import json_normalize
import requests
import time

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

# Reverse geocoding function using Nominatim (free service)
@st.cache_data(ttl=86400)  # Cache for 24 hours
def get_country_from_coordinates(lat, lon):
    """Get country name from latitude and longitude using Nominatim reverse geocoding"""
    if pd.isna(lat) or pd.isna(lon):
        return "Unknown"
    
    try:
        # Ensure lat and lon are converted to float/string properly
        lat_str = str(float(lat))
        lon_str = str(float(lon))
        
        # Use Nominatim (OpenStreetMap) reverse geocoding service
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat_str}&lon={lon_str}&format=json&addressdetails=1"
        headers = {'User-Agent': 'GCF-TwigaTools/1.0 (conservation research)'}
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'address' in data and 'country' in data['address']:
                return data['address']['country']
        
        return "Unknown"
    except Exception as e:
        return "Unknown"

def add_country_column(df):
    """Add country column to dataframe based on coordinates"""
    if df.empty or 'latitude' not in df.columns or 'longitude' not in df.columns:
        df['country'] = "Unknown"
        return df
    
    # Show progress for country lookup
    countries = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Use df.index to ensure we iterate through all rows properly
    for idx, (row_idx, row) in enumerate(df.iterrows()):
        try:
            lat = row['latitude']
            lon = row['longitude']
            
            # Check if coordinates are valid
            if pd.notna(lat) and pd.notna(lon) and lat != '' and lon != '':
                # Convert to float to ensure proper data type
                lat_float = float(lat)
                lon_float = float(lon)
                
                # Basic validation of coordinate ranges
                if -90 <= lat_float <= 90 and -180 <= lon_float <= 180:
                    country = get_country_from_coordinates(lat_float, lon_float)
                    countries.append(country)
                else:
                    countries.append("Unknown")
            else:
                countries.append("Unknown")
            
            # Update progress
            progress = (idx + 1) / len(df)
            progress_bar.progress(progress)
            status_text.text(f"Looking up countries... {idx+1}/{len(df)}")
            
            # Small delay to be respectful to the geocoding service
            time.sleep(0.1)
            
        except (ValueError, TypeError) as e:
            # Handle conversion errors
            countries.append("Unknown")
            continue
    
    # Clear progress indicators
    progress_bar.empty()
    status_text.empty()
    
    # Ensure the countries list has exactly the same length as the DataFrame
    if len(countries) != len(df):
        st.warning(f"Country lookup mismatch: {len(countries)} countries for {len(df)} events. Using 'Unknown' for all.")
        df['country'] = "Unknown"
    else:
        df['country'] = countries
    
    return df

# Make main available at module level for import
def main():
    """Main application entry point - delegates to _main_implementation"""
    return _main_implementation()

# Custom CSS for better styling
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
    .sample-event {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 0.5rem 0;
        border-left: 4px solid #28a745;
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
    """Simple login function like NANW dashboard"""
    try:
        er = EarthRangerIO(
            server=st.session_state.server_url,
            username=username,
            password=password
        )
        # Try a simple call to check credentials
        er.get_subjects(limit=1)
        return True
    except Exception:
        return False

def authenticate_earthranger():
    """Handle EarthRanger authentication using ecoscope - simplified like NANW dashboard"""
    if not ECOSCOPE_AVAILABLE:
        st.error("❌ Ecoscope package is required but not available. Please install ecoscope.")
        return
        
    st.title("Login to Genetic Dashboard")
    st.info("**Server:** https://twiga.pamdas.org")
    
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

@st.cache_data(ttl=3600)  # Cache for 1 hour like NANW dashboard
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
        
        # Add location information if geometry was available
        if not gdf_events.empty and 'geometry' in gdf_events.columns:
            # Extract coordinates from geometry with error handling
            try:
                gdf_events['latitude'] = gdf_events.geometry.apply(lambda x: x.y if x and hasattr(x, 'y') else None)
                gdf_events['longitude'] = gdf_events.geometry.apply(lambda x: x.x if x and hasattr(x, 'x') else None)
                df['latitude'] = gdf_events['latitude']
                df['longitude'] = gdf_events['longitude']
            except Exception as geo_error:
                st.warning(f"Geometry processing warning: {str(geo_error)}")
                # Continue without geometry data
                pass
        
        # Add country information based on coordinates
        if 'latitude' in df.columns and 'longitude' in df.columns:
            try:
                # Add option to skip country lookup for debugging
                if st.session_state.get('skip_country_lookup', False):
                    df['country'] = "Unknown"
                    st.info("🌍 Country lookup skipped (debug mode)")
                else:
                    with st.spinner("🌍 Looking up countries from coordinates..."):
                        df = add_country_column(df)
            except Exception as country_error:
                st.warning(f"Could not determine countries from coordinates: {str(country_error)}")
                st.info("Setting all events to 'Unknown' country and continuing...")
                df['country'] = "Unknown"
        else:
            df['country'] = "Unknown"
        
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
        
        # Convert to DataFrame and merge
        if details_expanded:
            details_df = pd.DataFrame(details_expanded)
            
            # Reset index to ensure proper alignment when merging
            details_df.reset_index(drop=True, inplace=True)
            display_df.reset_index(drop=True, inplace=True)
            
            # Add the details columns to the main dataframe with proper index alignment
            for col in details_df.columns:
                display_df[col] = details_df[col]
    
    # Define preferred column order - cleaned up to only essential columns
    preferred_columns = [
        'id',                # Event ID
        'serial_number',     # Serial Number
        'event_datetime',    # Event Date/Time
        'latitude',          # Latitude
        'longitude'          # Longitude
    ]
    
    # Add all event_details columns (these are the exploded details) except excluded ones
    excluded_columns = ['details_updates', 'event_type']
    details_columns = [col for col in display_df.columns 
                      if col.startswith('details_') and col not in excluded_columns]
    preferred_columns.extend(details_columns)
    
    # Select only existing columns from our preferred list
    available_columns = [col for col in preferred_columns if col in display_df.columns]
    
    # Create custom column configuration with renamed headers
    column_config = {
        'id': 'Event ID',
        'serial_number': 'Serial Number',
        'event_datetime': 'Event Date/Time',
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
        'details_girsam_status': 'Sample Status'
    }
    
    # Display the table
    st.dataframe(
        display_df[available_columns],
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
    df_map = df_events[(df_events['latitude'].notna()) & (df_events['longitude'].notna())].copy()
    
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
            'shipped': '#28A745'    # Green
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
            zoom=6,
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
            zoom=6,
            height=600,
            title=f"Biological Sample Events Map ({len(df_map)} events with coordinates)"
        )
    
    # Update map layout
    fig.update_layout(
        mapbox_style="open-street-map",
        margin={"r": 0, "t": 50, "l": 0, "b": 0},
        showlegend=True
    )
    
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
    
    # Show country breakdown
    if 'country' in df_map.columns:
        st.subheader("🌍 Country Breakdown")
        country_counts = df_map['country'].value_counts()
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.write("**Samples by Country:**")
            for country, count in country_counts.items():
                percentage = (count / len(df_map) * 100)
                flag = "🏴" if country == "Unknown" else "🏃"
                st.write(f"• {flag} {country}: {count} samples ({percentage:.1f}%)")
        
        with col2:
            # Country bar chart
            if len(country_counts) > 0:
                fig_country_bar = px.bar(
                    x=country_counts.values,
                    y=country_counts.index,
                    orientation='h',
                    title="Samples by Country",
                    labels={'x': 'Number of Samples', 'y': 'Country'},
                    color=country_counts.values,
                    color_continuous_scale='Viridis'
                )
                fig_country_bar.update_layout(height=300, showlegend=False)
                st.plotly_chart(fig_country_bar, use_container_width=True)
        
        with col3:
            # Country pie chart
            if len(country_counts) > 0:
                fig_country_pie = px.pie(
                    values=country_counts.values,
                    names=country_counts.index,
                    title="Country Distribution"
                )
                fig_country_pie.update_layout(height=300, showlegend=True)
                st.plotly_chart(fig_country_pie, use_container_width=True)

def genetic_dashboard():
    """Main genetic dashboard interface"""
    st.header("🧬 Genetic Dashboard")
    st.markdown("Monitor and analyze biological sample events from EarthRanger")
    
    # Dashboard controls - use wider layout
    col1, col2, col3 = st.columns([4, 2, 1])
    
    with col1:
        st.subheader("📅 Date Filters")
    
    with col2:
        # Debug option to skip country lookup
        skip_country = st.checkbox(
            "Skip Country Lookup",
            value=False,
            help="Skip reverse geocoding for faster loading (sets all countries to 'Unknown')"
        )
        if skip_country:
            st.session_state['skip_country_lookup'] = True
        else:
            st.session_state['skip_country_lookup'] = False
    
    with col3:
        # Add max results control
        max_results = st.selectbox(
            "Max Results",
            options=[50, 100, 200, 500],
            index=2,  # Default to 200
            help="Limit the number of events to fetch (higher numbers may be slower)"
        )
    
    # Date selection controls in a wider format
    col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
    # Date selection controls in a wider format
    col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
    
    with col1:
        start_date = st.date_input(
            "Start Date",
            value=date.today() - timedelta(days=365),  # Default to last year
            help="Select the earliest date for biological sample events"
        )
    
    with col2:
        end_date = st.date_input(
            "End Date", 
            value=date.today(),
            help="Select the latest date for biological sample events"
        )
    
    with col3:
        st.write("")  # Spacer for alignment
    
    with col4:
        if st.button("🔄 Refresh Data", type="primary"):
            # Clear cache to force refresh
            get_biological_sample_events.clear()
            st.rerun()
    
    # Validate date range
    if start_date > end_date:
        st.error("❌ Start date cannot be after end date")
        return
    
    # Fetch biological sample events with the selected max_results
    with st.spinner("Fetching biological sample events..."):
        df_events = get_biological_sample_events(start_date, end_date, max_results)
    
    if df_events.empty:
        st.warning("No biological sample events found for the selected date range.")
        
        # Add debugging information to help understand available event types
        if st.checkbox("🔍 Debug: Show available veterinary event types", value=False):
            with st.spinner("Fetching all veterinary events for debugging..."):
                try:
                    er_io = EarthRangerIO(
                        server=st.session_state.server_url,
                        username=st.session_state.username,
                        password=st.session_state.password
                    )
                    
                    # Get all veterinary events to see what event types are available
                    debug_kwargs = {
                        'event_category': 'veterinary',
                        'max_results': 100,  # Limit for debugging
                        'drop_null_geometry': False
                    }
                    
                    if start_date:
                        debug_kwargs['since'] = start_date.strftime('%Y-%m-%dT00:00:00Z')
                    if end_date:
                        debug_kwargs['until'] = end_date.strftime('%Y-%m-%dT23:59:59Z')
                    
                    debug_gdf = er_io.get_events(**debug_kwargs)
                    
                    if not debug_gdf.empty:
                        debug_df = pd.DataFrame(debug_gdf.drop(columns='geometry', errors='ignore'))
                        if 'event_type' in debug_df.columns:
                            event_types = debug_df['event_type'].value_counts()
                            st.write("**Available event types in 'veterinary' category:**")
                            st.dataframe(event_types.reset_index())
                            
                            st.write("**Sample events:**")
                            sample_cols = ['time', 'event_type', 'serial_number', 'state']
                            available_cols = [col for col in sample_cols if col in debug_df.columns]
                            st.dataframe(debug_df[available_cols].head())
                    else:
                        st.write("No veterinary events found in the selected date range.")
                        
                except Exception as debug_error:
                    st.error(f"Debug error: {str(debug_error)}")
        return
    
    # Country filter section
    st.subheader("🌍 Country Filter")
    
    # Get unique countries
    countries_in_data = sorted([c for c in df_events['country'].unique() if c != "Unknown"])
    if "Unknown" in df_events['country'].values:
        countries_in_data.append("Unknown")
    
    # Country selection
    col1, col2 = st.columns([3, 1])
    with col1:
        country_filter = st.selectbox(
            "Select Country",
            options=["All Countries"] + countries_in_data,
            index=0,
            help="Filter data by country (based on event coordinates)"
        )
    
    with col2:
        st.metric(
            "Total Countries", 
            len([c for c in countries_in_data if c != "Unknown"]),
            help="Number of countries with events"
        )
    
    # Apply country filter
    if country_filter != "All Countries":
        df_filtered = df_events[df_events['country'] == country_filter].copy()
        st.info(f"📊 Showing data for: **{country_filter}** ({len(df_filtered)} events)")
    else:
        df_filtered = df_events.copy()
        st.info(f"📊 Showing data for: **All Countries** ({len(df_filtered)} events)")
    
    # Update the rest of the function to use df_filtered instead of df_events
    if df_filtered.empty:
        st.warning(f"No biological sample events found for {country_filter} in the selected date range.")
        return
    
    # Display the events table and get exploded data
    df_exploded = display_event_details_table(df_filtered)
    
    # Add some spacing
    st.markdown("---")
    
    # Display the map with exploded data for processing status coloring
    display_events_map(df_exploded)

def _main_implementation():
    """Main application logic"""
    init_session_state()
    
    # Set wide layout for better dashboard display
    st.set_page_config(
        page_title="Genetic Dashboard",
        page_icon="🧬",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
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
            st.markdown("Biological sample event monitoring and analytics")
    
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

# Make main() available for import while still allowing direct execution
if __name__ == "__main__":
    main()
