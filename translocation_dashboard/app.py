import streamlit as st
import pandas as pd
import geopandas as gpd
from datetime import datetime, timedelta, date
import plotly.express as px
import plotly.graph_objects as go
import json
import os

# Ecoscope imports for EarthRanger integration
try:
    from ecoscope.io.earthranger import EarthRangerIO
    ECOSCOPE_AVAILABLE = True
except ImportError:
    ECOSCOPE_AVAILABLE = False
    st.warning("⚠️ Ecoscope package not available. Please install ecoscope to use this dashboard.")

# Location area data for range calculations (in km²)
LOCATION_AREAS = {
    'Iona National Park': 15200,
    'Cuatir': 400,
    'Majete Wildlife Reserve': 700,
    'Gadabedji': 760,
    'Murchison Falls National Park (South)': 3893,
    'Pian Upe Wildlife Reserve': 2275,
    'Ongongo': 501,
    'Mnjoli Game Reserve': 4,
    # Add more locations and their areas as needed
}

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
    .translocation-event {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 0.5rem 0;
        border-left: 4px solid #007bff;
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

def authenticate_earthranger():
    """Handle EarthRanger authentication using ecoscope"""
    if not ECOSCOPE_AVAILABLE:
        st.error("❌ Ecoscope package is required but not available. Please install ecoscope.")
        return
        
    st.header("🔐 EarthRanger Authentication")
    
    st.write("Enter your EarthRanger credentials to access the translocation dashboard:")
    
    # Fixed server URL
    st.info("**Server:** https://twiga.pamdas.org")
    
    # Username and password inputs
    username = st.text_input(
        "Username",
        help="Your EarthRanger username"
    )
    
    password = st.text_input(
        "Password",
        type="password",
        help="Your EarthRanger password"
    )
    
    if st.button("🔌 Connect to EarthRanger", type="primary"):
        if not username or not password:
            st.error("❌ Both username and password are required")
            return
        
        try:
            with st.spinner("🔐 Authenticating with EarthRanger..."):
                # Test the connection by creating EarthRangerIO - this validates credentials
                er_io = EarthRangerIO(
                    server=st.session_state.server_url,
                    username=username,
                    password=password
                )
                
                # Just test the connection without fetching data for faster authentication
                # The EarthRangerIO initialization already validates the connection
                
                st.success("✅ Successfully authenticated with EarthRanger!")
                st.session_state.authenticated = True
                st.session_state.username = username
                st.session_state.password = password
                
                st.rerun()
                
        except Exception as e:
            st.error(f"❌ Authentication failed: {str(e)}")
            st.info("💡 Please check your username and password")

@st.cache_data(ttl=1800, show_spinner=False)  # Cache for 30 minutes
def get_translocation_events(start_date=None, end_date=None, _debug=False):
    """Fetch translocation events from EarthRanger using ecoscope"""
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
            'max_results': 1000,
            'drop_null_geometry': False  # Keep events without geometry for now
        }
        
        # Add date filters if provided - convert date objects to ISO format strings
        if start_date:
            # Ensure start_date is a date object and convert to string
            if isinstance(start_date, date):
                since_str = start_date.strftime('%Y-%m-%dT00:00:00Z')
            else:
                since_str = str(start_date)
            kwargs['since'] = since_str
            if _debug:
                st.write(f"Debug: since = {since_str}")
                
        if end_date:
            # Ensure end_date is a date object and convert to string
            if isinstance(end_date, date):
                until_str = end_date.strftime('%Y-%m-%dT23:59:59Z')
            else:
                until_str = str(end_date)
            kwargs['until'] = until_str
            if _debug:
                st.write(f"Debug: until = {until_str}")
        
        # Get events using ecoscope (all veterinary events)
        gdf_events = er_io.get_events(**kwargs)
        
        if gdf_events.empty:
            return pd.DataFrame()
        
        # Convert GeoDataFrame to regular DataFrame for easier handling in Streamlit
        df = pd.DataFrame(gdf_events.drop(columns='geometry', errors='ignore'))
        
        # Filter by event_type after getting the data (avoiding UUID requirement)
        # Only include giraffe_translocation_3 (exclude giraffe_translocation_2 and other variants)
        if 'event_type' in df.columns:
            df = df[df['event_type'] == 'giraffe_translocation_3']
        
        if df.empty:
            return pd.DataFrame()
        
        # Process the data
        if 'time' in df.columns:
            df['time'] = pd.to_datetime(df['time'])
            df['date'] = df['time'].dt.date
            df['year'] = df['time'].dt.year
            df['month'] = df['time'].dt.month
            df['month_name'] = df['time'].dt.strftime('%B')
            
            # Apply client-side date filtering as backup (in case API filter didn't work)
            if start_date is not None:
                df = df[df['date'] >= start_date]
            if end_date is not None:
                df = df[df['date'] <= end_date]
            
            if _debug and not df.empty:
                st.write(f"Debug: After date filtering, {len(df)} events remain")
                st.write(f"Debug: Date range in data: {df['date'].min()} to {df['date'].max()}")
        
        # Add location information if geometry was available
        if not gdf_events.empty and 'geometry' in gdf_events.columns:
            # Extract coordinates from geometry
            gdf_events['latitude'] = gdf_events.geometry.apply(lambda x: x.y if x and hasattr(x, 'y') else None)
            gdf_events['longitude'] = gdf_events.geometry.apply(lambda x: x.x if x and hasattr(x, 'x') else None)
            df['latitude'] = gdf_events['latitude']
            df['longitude'] = gdf_events['longitude']
        
        return df
        
    except Exception as e:
        st.error(f"Error fetching translocation events: {str(e)}")
        return pd.DataFrame()

@st.cache_data(ttl=1800)  # Cache for 30 minutes
def get_subject_details(subject_ids):
    """Fetch subject details from EarthRanger using ecoscope"""
    if not ECOSCOPE_AVAILABLE or not subject_ids:
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
        
        # Get subjects data
        subjects_gdf = er_io.get_subjects()
        
        if subjects_gdf.empty:
            return pd.DataFrame()
        
        # Convert to DataFrame and filter for our subject IDs
        subjects_df = pd.DataFrame(subjects_gdf.drop(columns='geometry', errors='ignore'))
        
        # Filter for the subjects we're interested in
        if 'id' in subjects_df.columns:
            filtered_subjects = subjects_df[subjects_df['id'].isin(subject_ids)]
        else:
            return pd.DataFrame()
        
        # Get subject tracks/deployments for deployment dates
        subject_details = []
        
        for subject_id in subject_ids:
            subject_info = filtered_subjects[filtered_subjects['id'] == subject_id]
            if not subject_info.empty:
                subject_row = subject_info.iloc[0]
                
                # Try to get deployment information
                try:
                    # Get subject tracks to find deployment dates
                    tracks_gdf = er_io.get_subjecttracks(subject_ids=[subject_id])
                    
                    deployment_start = None
                    deployment_end = None
                    
                    if not tracks_gdf.empty:
                        tracks_df = pd.DataFrame(tracks_gdf.drop(columns='geometry', errors='ignore'))
                        if 'recorded_at' in tracks_df.columns:
                            tracks_df['recorded_at'] = pd.to_datetime(tracks_df['recorded_at'])
                            deployment_start = tracks_df['recorded_at'].min()
                            deployment_end = tracks_df['recorded_at'].max()
                    
                    # Determine status based on last location time
                    status = "Unknown"
                    if deployment_end:
                        days_since_last = (pd.Timestamp.now() - deployment_end).days
                        if days_since_last <= 7:
                            status = "Active"
                        elif days_since_last <= 30:
                            status = "Recent"
                        else:
                            status = "Inactive"
                    
                    subject_details.append({
                        'subject_id': subject_id,
                        'name': subject_row.get('name', 'Unknown'),
                        'subject_type': subject_row.get('subject_type', 'Unknown'),
                        'sex': subject_row.get('sex', 'Unknown'),
                        'deployment_start': deployment_start.strftime('%Y-%m-%d') if deployment_start else 'Unknown',
                        'deployment_end': deployment_end.strftime('%Y-%m-%d') if deployment_end else 'Unknown',
                        'last_location_days': (pd.Timestamp.now() - deployment_end).days if deployment_end else None,
                        'status': status
                    })
                    
                except Exception as e:
                    # If we can't get deployment info, just add basic subject info
                    subject_details.append({
                        'subject_id': subject_id,
                        'name': subject_row.get('name', 'Unknown'),
                        'subject_type': subject_row.get('subject_type', 'Unknown'),
                        'sex': subject_row.get('sex', 'Unknown'),
                        'deployment_start': 'Unknown',
                        'deployment_end': 'Unknown',
                        'last_location_days': None,
                        'status': 'Unknown'
                    })
        
        return pd.DataFrame(subject_details)
        
    except Exception as e:
        st.error(f"Error fetching subject details: {str(e)}")
        return pd.DataFrame()

def display_event_details(event):
    """Display detailed information for a single translocation event"""
    with st.expander(f"📅 {event['time'].strftime('%Y-%m-%d %H:%M')} - Event ID: {event.get('id', 'Unknown')}", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            st.write(f"**Serial Number:** {event.get('serial_number', 'N/A')}")
            st.write(f"**Event Type:** {event.get('event_type', 'N/A')}")
            st.write(f"**Event Category:** {event.get('event_category', 'N/A')}")
            st.write(f"**Priority:** {event.get('priority', 'N/A')}")
            st.write(f"**State:** {event.get('state', 'N/A')}")
            
        with col2:
            st.write(f"**Created At:** {pd.to_datetime(event.get('created_at', '')).strftime('%Y-%m-%d %H:%M') if event.get('created_at') else 'N/A'}")
            st.write(f"**Updated At:** {pd.to_datetime(event.get('updated_at', '')).strftime('%Y-%m-%d %H:%M') if event.get('updated_at') else 'N/A'}")
            
            # Location information
            if event.get('latitude') and event.get('longitude'):
                st.write(f"**Location:** {event['latitude']:.6f}, {event['longitude']:.6f}")
            else:
                st.write("**Location:** Not available")
        
        # Event details
        if event.get('event_details'):
            st.write("**Event Details:**")
            details = event['event_details']
            if isinstance(details, dict):
                for key, value in details.items():
                    if value:  # Only show non-empty values
                        st.write(f"  - **{key.replace('_', ' ').title()}:** {value}")
            else:
                st.write(f"  {details}")
        
        # Notes
        if event.get('notes'):
            st.write("**Notes:**")
            notes = event['notes']
            if isinstance(notes, list):
                for note in notes:
                    if isinstance(note, dict):
                        note_time = pd.to_datetime(note.get('created_at', '')).strftime('%Y-%m-%d %H:%M') if note.get('created_at') else 'Unknown time'
                        st.write(f"  - **{note_time}:** {note.get('text', '')}")
                    else:
                        st.write(f"  - {note}")
            else:
                st.write(f"  {notes}")

def translocation_dashboard():
    """Main translocation dashboard interface"""
    
    # Date filter controls
    st.subheader("📅 Filters")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        start_date = st.date_input(
            "Start Date",
            value=date.today() - timedelta(days=365),  # Default to last year
            help="Select the earliest date for translocation events"
        )
    
    with col2:
        end_date = st.date_input(
            "End Date", 
            value=date.today(),
            help="Select the latest date for translocation events"
        )
    
    # First fetch all events to get available countries
    with st.spinner("🔄 Loading available countries..."):
        all_events = get_translocation_events(start_date, end_date)
    
    # Extract unique destination countries
    all_countries = ['All Countries']
    if not all_events.empty:
        for idx, event in all_events.iterrows():
            event_details = event.get('event_details', {})
            if isinstance(event_details, dict):
                # New format uses country codes like 'bwa', 'ken'
                dest_country = event_details.get('destination_country')
                
                # Handle both new format (country codes) and old format (dict/string)
                if dest_country:
                    if isinstance(dest_country, dict):
                        dest_country = (dest_country.get('name') or 
                                      dest_country.get('country') or 
                                      dest_country.get('code'))
                    elif not isinstance(dest_country, str):
                        dest_country = str(dest_country)
                    
                    if dest_country and dest_country not in all_countries:
                        all_countries.append(dest_country.upper())  # Uppercase for consistency
    
    with col3:
        selected_country = st.selectbox(
            "Destination Country",
            options=all_countries,
            index=0,
            help="Filter by destination country"
        )
    
    with col4:
        if st.button("🔄 Refresh Data", type="primary"):
            # Clear cache to force refresh
            get_translocation_events.clear()
            st.rerun()
    
    # Additional filters row
    col1, col2, col3, col4 = st.columns(4)
    
    # Extract unique values for filters from all events
    all_species = ['All Species']
    all_ranges = ['All Ranges']
    all_trans_types = ['All Types']
    all_origin_countries = ['All Countries']
    
    if not all_events.empty:
        for idx, event in all_events.iterrows():
            event_details = event.get('event_details', {})
            if isinstance(event_details, dict):
                # Species
                species = event_details.get('species')
                if species:
                    if isinstance(species, dict):
                        species = species.get('name') or species.get('species')
                    if species:
                        species_title = str(species).title()
                        if species_title not in all_species:
                            all_species.append(species_title)
                
                # Range
                range_val = event_details.get('range')
                if range_val:
                    range_title = str(range_val).title()
                    if range_title not in all_ranges:
                        all_ranges.append(range_title)
                
                # Translocation type
                trans_type = event_details.get('translocation_type') or event_details.get('trans_type')
                if trans_type:
                    if isinstance(trans_type, dict):
                        trans_type = trans_type.get('name') or trans_type.get('type')
                    if trans_type:
                        trans_type_title = str(trans_type).title()
                        if trans_type_title not in all_trans_types:
                            all_trans_types.append(trans_type_title)
                
                # Origin country
                origin_country = event_details.get('origin_country')
                if origin_country:
                    if isinstance(origin_country, dict):
                        origin_country = (origin_country.get('name') or 
                                        origin_country.get('country') or 
                                        origin_country.get('code'))
                    if origin_country:
                        origin_country_upper = origin_country.upper()
                        if origin_country_upper not in all_origin_countries:
                            all_origin_countries.append(origin_country_upper)
    
    with col1:
        selected_species = st.selectbox(
            "Species",
            options=all_species,
            index=0,
            help="Filter by species"
        )
    
    with col2:
        selected_range = st.selectbox(
            "Range Type",
            options=all_ranges,
            index=0,
            help="Filter by range classification"
        )
    
    with col3:
        selected_trans_type = st.selectbox(
            "Translocation Type",
            options=all_trans_types,
            index=0,
            help="Filter by translocation type"
        )
    
    with col4:
        selected_origin_country = st.selectbox(
            "Origin Country",
            options=all_origin_countries,
            index=0,
            help="Filter by origin country"
        )
    
    # GCF filter on separate row for better visibility
    show_all_events = st.checkbox(
        "Show all events including non-GCF",
        value=False,
        help="By default, only GCF events are shown. Check this to include all events."
    )
    
    # Validate date range
    if start_date > end_date:
        st.error("❌ Start date cannot be after end date")
        return
    
    # Fetch translocation events
    with st.spinner("🔄 Fetching translocation events from EarthRanger..."):
        df_events = get_translocation_events(start_date, end_date)
    
    # Apply GCF organization filter (by default show only GCF, unless show_all_events is checked)
    if not show_all_events and not df_events.empty:
        filtered_events = []
        for idx, event in df_events.iterrows():
            event_details = event.get('event_details', {})
            if isinstance(event_details, dict):
                # Check if GCF is in any of the 3 organization fields
                org1 = event_details.get('organisation_1', '')
                org2 = event_details.get('organisation_2', '')
                org3 = event_details.get('organisation_3', '')
                
                # Case-insensitive check for GCF
                if any('giraffe conservation foundation' in str(org).lower() 
                       for org in [org1, org2, org3] if org):
                    filtered_events.append(event)
        
        if filtered_events:
            df_events = pd.DataFrame(filtered_events)
        else:
            df_events = pd.DataFrame()
    
    # Apply destination country filter if not "All Countries"
    if selected_country != 'All Countries' and not df_events.empty:
        filtered_events = []
        for idx, event in df_events.iterrows():
            event_details = event.get('event_details', {})
            if isinstance(event_details, dict):
                dest_country = event_details.get('destination_country')
                
                # Handle both new format (country codes) and old format
                if dest_country:
                    if isinstance(dest_country, dict):
                        dest_country = (dest_country.get('name') or 
                                      dest_country.get('country') or 
                                      dest_country.get('code'))
                    elif not isinstance(dest_country, str):
                        dest_country = str(dest_country)
                    
                    # Case-insensitive comparison
                    if dest_country and dest_country.upper() == selected_country.upper():
                        filtered_events.append(event)
        
        if filtered_events:
            df_events = pd.DataFrame(filtered_events)
        else:
            df_events = pd.DataFrame()
    
    # Apply species filter
    if selected_species != 'All Species' and not df_events.empty:
        filtered_events = []
        for idx, event in df_events.iterrows():
            event_details = event.get('event_details', {})
            if isinstance(event_details, dict):
                species = event_details.get('species')
                if isinstance(species, dict):
                    species = species.get('name') or species.get('species')
                if species and str(species).title() == selected_species:
                    filtered_events.append(event)
        
        if filtered_events:
            df_events = pd.DataFrame(filtered_events)
        else:
            df_events = pd.DataFrame()
    
    # Apply range filter
    if selected_range != 'All Ranges' and not df_events.empty:
        filtered_events = []
        for idx, event in df_events.iterrows():
            event_details = event.get('event_details', {})
            if isinstance(event_details, dict):
                range_val = event_details.get('range')
                if range_val and str(range_val).title() == selected_range:
                    filtered_events.append(event)
        
        if filtered_events:
            df_events = pd.DataFrame(filtered_events)
        else:
            df_events = pd.DataFrame()
    
    # Apply translocation type filter
    if selected_trans_type != 'All Types' and not df_events.empty:
        filtered_events = []
        for idx, event in df_events.iterrows():
            event_details = event.get('event_details', {})
            if isinstance(event_details, dict):
                trans_type = event_details.get('translocation_type') or event_details.get('trans_type')
                if isinstance(trans_type, dict):
                    trans_type = trans_type.get('name') or trans_type.get('type')
                if trans_type and str(trans_type).title() == selected_trans_type:
                    filtered_events.append(event)
        
        if filtered_events:
            df_events = pd.DataFrame(filtered_events)
        else:
            df_events = pd.DataFrame()
    
    # Apply origin country filter
    if selected_origin_country != 'All Countries' and not df_events.empty:
        filtered_events = []
        for idx, event in df_events.iterrows():
            event_details = event.get('event_details', {})
            if isinstance(event_details, dict):
                origin_country = event_details.get('origin_country')
                if isinstance(origin_country, dict):
                    origin_country = (origin_country.get('name') or 
                                    origin_country.get('country') or 
                                    origin_country.get('code'))
                if origin_country and origin_country.upper() == selected_origin_country.upper():
                    filtered_events.append(event)
        
        if filtered_events:
            df_events = pd.DataFrame(filtered_events)
        else:
            df_events = pd.DataFrame()
    
    if df_events.empty:
        st.warning("No translocation events found for the selected date range.")
        
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
                            if available_cols:
                                st.dataframe(debug_df[available_cols].head(10))
                        else:
                            st.write("No 'event_type' column found in veterinary events")
                    else:
                        st.write("No veterinary events found in the selected date range")
                        
                except Exception as e:
                    st.error(f"Debug error: {str(e)}")
        
        st.info("""
        **Possible reasons:**
        - No giraffe translocation events occurred in the selected date range
        - Events may be categorized differently in EarthRanger
        - Access permissions may not include veterinary events
        - Event type might be named differently (use debug option above to check)
        
        **Event criteria:** event_category='veterinary' AND event_type='giraffe_translocation'
        """)
        return
    
    # Summary metrics
    st.subheader("📊 Summary Statistics")
    
    # Calculate all metrics first
    total_individuals = 0
    species_counts = {}
    range_counts = {}
    trans_type_counts = {}
    
    for idx, event in df_events.iterrows():
        event_details = event.get('event_details', {})
        if isinstance(event_details, dict):
            # Extract species information
            species = event_details.get('species') or 'Unknown'
            if isinstance(species, dict):
                species = species.get('name') or species.get('species') or 'Unknown'
            elif isinstance(species, str):
                species = species.title() if species else 'Unknown'
            else:
                species = str(species) if species else 'Unknown'
            
            # Count individuals
            individuals = event_details.get('total_individuals')
            if individuals is not None:
                try:
                    count = int(individuals)
                    total_individuals += count
                    species_counts[species] = species_counts.get(species, 0) + count
                except (ValueError, TypeError):
                    total_individuals += 1
                    species_counts[species] = species_counts.get(species, 0) + 1
            else:
                total_individuals += 1
                species_counts[species] = species_counts.get(species, 0) + 1
            
            # Range classification
            range_type = event_details.get('range', 'Unknown')
            if isinstance(range_type, str):
                range_type = range_type.title()
            else:
                range_type = str(range_type) if range_type else 'Unknown'
            range_counts[range_type] = range_counts.get(range_type, 0) + 1
            
            # Translocation type
            trans_type = event_details.get('translocation_type') or event_details.get('trans_type') or 'Unknown'
            if isinstance(trans_type, dict):
                trans_type = trans_type.get('name') or trans_type.get('type') or 'Unknown'
            elif isinstance(trans_type, str):
                trans_type = trans_type.title()
            else:
                trans_type = str(trans_type) if trans_type else 'Unknown'
            trans_type_counts[trans_type] = trans_type_counts.get(trans_type, 0) + 1
    
    # Top row: Key metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Events", len(df_events))
    with col2:
        st.metric("Total Individuals", total_individuals)
    with col3:
        st.metric("Species Types", len(species_counts))
    
    st.markdown("---")
    
    # Visualizations in columns
    col1, col2, col3 = st.columns(3)
    
    # Custom color palette
    org_colors = ['#DB580F', '#3E0000', '#CCCCCC', '#999999', '#FF7F3F', '#5D1010', '#E6E6E6', '#B8860B', '#8B4513', '#A0522D']
    
    with col1:
        if species_counts:
            species_df = pd.DataFrame(list(species_counts.items()), columns=['Species', 'Individuals'])
            species_df = species_df.sort_values('Individuals', ascending=False)
            fig_species = px.pie(
                species_df,
                values='Individuals',
                names='Species',
                title="Species Distribution",
                color_discrete_sequence=org_colors,
                height=350
            )
            fig_species.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_species, use_container_width=True)
    
    with col2:
        if range_counts:
            range_df = pd.DataFrame(list(range_counts.items()), columns=['Range Type', 'Count'])
            fig_range = px.pie(
                range_df,
                values='Count',
                names='Range Type',
                title="Range Classification",
                color_discrete_map={'In Range': '#2E8B57', 'Extralimital': '#FF6B35', 'Unknown': '#999999'},
                height=350
            )
            fig_range.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_range, use_container_width=True)
    
    with col3:
        if trans_type_counts:
            type_df = pd.DataFrame(list(trans_type_counts.items()), columns=['Type', 'Count'])
            color_map = {'Founder': '#DB580F', 'Augmentation': '#3E0000', 'Relocation': '#999999'}
            colors = [color_map.get(t, '#1f77b4') for t in type_df['Type']]
            fig_types = px.pie(
                type_df,
                values='Count',
                names='Type',
                title="Translocation Type",
                color_discrete_sequence=colors,
                height=350
            )
            fig_types.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_types, use_container_width=True)
    
    st.markdown("---")
    
    # Organization involvement
    st.subheader("🏢 Organizations Involved")
    org_counts = {}
    for idx, event in df_events.iterrows():
        event_details = event.get('event_details', {})
        if isinstance(event_details, dict):
            for org_field in ['organisation_1', 'organisation_2', 'organisation_3']:
                org = event_details.get(org_field)
                if org and isinstance(org, str) and org.strip():
                    org_counts[org] = org_counts.get(org, 0) + 1
    
    if org_counts:
        # Sort by count and get top organizations
        sorted_orgs = sorted(org_counts.items(), key=lambda x: x[1], reverse=True)
        
        # Bar chart for top 10 organizations
        top_orgs_df = pd.DataFrame(sorted_orgs[:10], columns=['Organization', 'Event Count'])
        fig_orgs = px.bar(
            top_orgs_df,
            x='Event Count',
            y='Organization',
            orientation='h',
            title="Top 10 Organizations by Event Participation",
            color='Event Count',
            color_continuous_scale=['#DB580F', '#3E0000'],
            height=400
        )
        fig_orgs.update_layout(yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig_orgs, use_container_width=True)
    else:
        st.info("No organization data available")
    
    # Create two columns for Giraffe Range Secured and Translocation Routes Map
    col_left, col_right = st.columns(2)
    
    with col_left:
        # Calculate range secured for founder translocations
        st.subheader("🌍 Giraffe Range Secured")
        
        total_range_secured = 0
        founder_locations = []
        species_range_secured = {}
        
        for idx, event in df_events.iterrows():
            event_details = event.get('event_details', {})
            if isinstance(event_details, dict):
                # New format uses 'translocation_type' instead of 'trans_type'
                trans_type = event_details.get('translocation_type') or event_details.get('trans_type')
                
                if trans_type and trans_type.lower() == 'founder':
                    # Extract species information
                    species = event_details.get('species') or event_details.get('animal_species') or 'Unknown'
                    if isinstance(species, dict):
                        species = species.get('name') or species.get('species') or 'Unknown'
                    elif not isinstance(species, str):
                        species = str(species) if species else 'Unknown'
                    
                    # Get destination location - ensure it's a string
                    dest_location = (event_details.get('destination_site') or
                                   event_details.get('destination_location') or 
                                   event_details.get('dest_location') or 
                                   event_details.get('to_location') or
                                   event_details.get('Destination Location') or
                                   event_details.get('destination_location_name') or
                                   event_details.get('dest_location_name'))
                    
                    # Ensure dest_location is a string, not a dict or other type
                    if dest_location:
                        if isinstance(dest_location, dict):
                            # If it's a dict, try to extract a meaningful location name
                            dest_location = (dest_location.get('name') or 
                                           dest_location.get('location') or 
                                           dest_location.get('place') or
                                           str(dest_location))  # Fallback to string representation
                        elif not isinstance(dest_location, str):
                            dest_location = str(dest_location)  # Convert to string
                        
                        # Hard-code Iona National Park and Cuatir detection
                        area_km2 = 0
                        if dest_location and 'iona' in dest_location.lower():
                            area_km2 = 15200
                            dest_location = "Iona National Park"  # Standardize the name
                        elif dest_location and 'cuatir' in dest_location.lower():
                            area_km2 = 400
                            dest_location = "Cuatir"  # Standardize the name
                        else:
                            # Look up the area for this location in the dictionary
                            area_km2 = LOCATION_AREAS.get(dest_location, 0)
                        
                        if area_km2 > 0:
                            total_range_secured += area_km2
                            # Track range by species
                            if species not in species_range_secured:
                                species_range_secured[species] = set()
                            species_range_secured[species].add((dest_location, area_km2))
                            
                            founder_locations.append({
                                'location': dest_location,
                                'area_km2': area_km2,
                                'species': species,
                                'date': event['time'].strftime('%Y-%m-%d')
                            })
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Total Range Secured (km²)", f"{total_range_secured:,}")
        
        with col2:
            founder_count = len([event for event in df_events.iterrows() 
                               if isinstance(event[1].get('event_details', {}), dict) and 
                               (event[1].get('event_details', {}).get('translocation_type', '').lower() == 'founder' or
                                event[1].get('event_details', {}).get('trans_type', '').lower() == 'founder')])
            st.metric("Founder Translocations", founder_count)
        
        # Show breakdown of founder locations if any exist
        if founder_locations:
            st.write("**Founder Translocation Locations:**")
            founder_df = pd.DataFrame(founder_locations)
            # Group by location to avoid duplicates
            location_summary = founder_df.groupby(['location', 'species']).agg({
                'area_km2': 'first',  # Take first value (should be same for all)
                'date': 'count'  # Count number of events
            }).reset_index()
            location_summary.columns = ['Location', 'Species', 'Area (km²)', 'Number of Events']
            
            st.dataframe(
                location_summary,
                use_container_width=True,
                column_config={
                    'Location': 'Destination Location',
                    'Species': 'Species',
                    'Area (km²)': st.column_config.NumberColumn(
                        'Area (km²)',
                        format="%d"
                    ),
                    'Number of Events': 'Founder Events'
                }
            )
            
            # Show range secured by species
            if species_range_secured:
                st.write("**Range Secured by Species:**")
                # Show as summary metrics instead of table
                for species, locations in species_range_secured.items():
                    total_species_range = sum(area for _, area in locations)
                    locations_list = list(set(loc for loc, _ in locations))
                    st.metric(
                        f"{species} Range Secured",
                        f"{total_species_range:,} km²",
                        delta=f"{len(locations_list)} location(s): {', '.join(locations_list)}"
                    )
    
    with col_right:
        # Map visualization if location data is available
        st.subheader("🗺️ Translocation Routes Map")
        
        # Check if any events have location data in event_details
        events_with_location = []
        for idx, event in df_events.iterrows():
            event_details = event.get('event_details', {})
            if isinstance(event_details, dict):
                origin_loc = event_details.get('origin_location')
                dest_loc = event_details.get('destination_location')
                # Check if we have at least one location with coordinates
                if (isinstance(origin_loc, dict) and origin_loc.get('latitude') and origin_loc.get('longitude')) or \
                   (isinstance(dest_loc, dict) and dest_loc.get('latitude') and dest_loc.get('longitude')):
                    events_with_location.append(event)
        
        if len(events_with_location) > 0:
            # Create map with origin and destination points
            fig_map = go.Figure()
            
            for event_idx, event in enumerate(events_with_location):
                event_details = event.get('event_details', {})
                if isinstance(event_details, dict):
                    # Extract origin and destination coordinates - handle nested location objects
                    origin_location_obj = event_details.get('origin_location')
                    dest_location_obj = event_details.get('destination_location')
                    
                    # Extract origin coordinates from nested object or direct fields
                    if isinstance(origin_location_obj, dict):
                        origin_lat = origin_location_obj.get('latitude')
                        origin_lon = origin_location_obj.get('longitude')
                    else:
                        origin_lat = origin_lon = None
                    
                    # Extract destination coordinates from nested object or direct fields
                    if isinstance(dest_location_obj, dict):
                        dest_lat = dest_location_obj.get('latitude')
                        dest_lon = dest_location_obj.get('longitude')
                    else:
                        dest_lat = dest_lon = None
                    
                    # Location names - extract from nested objects or use default names
                    origin_location_name = 'Unknown Origin'
                    if isinstance(origin_location_obj, dict):
                        origin_location_name = (origin_location_obj.get('name') or 
                                              origin_location_obj.get('location_name') or
                                              event_details.get('origin_location_name') or
                                              'Unknown Origin')
                    
                    destination_location_name = 'Unknown Destination'
                    if isinstance(dest_location_obj, dict):
                        destination_location_name = (dest_location_obj.get('name') or 
                                                   dest_location_obj.get('location_name') or
                                                   event_details.get('destination_location_name') or
                                                   'Unknown Destination')
                    
                    # Only draw the route if we have both origin and destination
                    if all([origin_lat, origin_lon, dest_lat, dest_lon]):
                        try:
                            import numpy as np
                            origin_lat_float, origin_lon_float = float(origin_lat), float(origin_lon)
                            dest_lat_float, dest_lon_float = float(dest_lat), float(dest_lon)
                            
                            # Calculate midpoint and add curvature
                            mid_lat = (origin_lat_float + dest_lat_float) / 2
                            mid_lon = (origin_lon_float + dest_lon_float) / 2
                            
                            # Add curvature offset (perpendicular to the line)
                            dx = dest_lon_float - origin_lon_float
                            dy = dest_lat_float - origin_lat_float
                            curve_offset = 0.1  # Curve intensity
                            
                            # Perpendicular offset for curve
                            perp_x = -dy * curve_offset
                            perp_y = dx * curve_offset
                            
                            # Create curved path with multiple segments for gradient effect
                            num_segments = 10
                            t = np.linspace(0, 1, num_segments + 1)
                            
                            # Color gradient from dark gray to orange
                            colors = ['#333333', '#4D4D4D', '#666666', '#805533', '#996633', 
                                     '#B37722', '#CC8811', '#E69900', '#FF9933', '#DB580F']
                            
                            # Draw each segment with a different color
                            for i in range(num_segments):
                                t_start = t[i]
                                t_end = t[i + 1]
                                
                                # Calculate segment endpoints using Bezier curve
                                lat_start = (1-t_start)**2 * origin_lat_float + 2*(1-t_start)*t_start * (mid_lat + perp_y) + t_start**2 * dest_lat_float
                                lon_start = (1-t_start)**2 * origin_lon_float + 2*(1-t_start)*t_start * (mid_lon + perp_x) + t_start**2 * dest_lon_float
                                
                                lat_end = (1-t_end)**2 * origin_lat_float + 2*(1-t_end)*t_end * (mid_lat + perp_y) + t_end**2 * dest_lat_float
                                lon_end = (1-t_end)**2 * origin_lon_float + 2*(1-t_end)*t_end * (mid_lon + perp_x) + t_end**2 * dest_lon_float
                                
                                # Draw line segment
                                fig_map.add_trace(go.Scattermapbox(
                                    lat=[lat_start, lat_end],
                                    lon=[lon_start, lon_end],
                                    mode='lines',
                                    line=dict(width=3, color=colors[i]),
                                    name='Translocation Route' if i == 0 else '',
                                    showlegend=(i == 0 and event_idx == 0),
                                    hovertemplate=f"<b>Route:</b> {origin_location_name} → {destination_location_name}<br>" +
                                                f"<b>Date:</b> {event['time'].strftime('%Y-%m-%d')}<br>" +
                                                f"<b>Species:</b> {event_details.get('species', 'Unknown')}<extra></extra>"
                                ))
                            
                            # Add small endpoint markers for clarity
                            # Origin marker (dark)
                            fig_map.add_trace(go.Scattermapbox(
                                lat=[origin_lat_float],
                                lon=[origin_lon_float],
                                mode='markers',
                                marker=dict(size=10, color='#333333', symbol='circle'),
                                name='Origin' if event_idx == 0 else '',
                                showlegend=(event_idx == 0),
                                hovertemplate=f"<b>Origin:</b> {origin_location_name}<extra></extra>"
                            ))
                            
                            # Destination marker (orange)
                            fig_map.add_trace(go.Scattermapbox(
                                lat=[dest_lat_float],
                                lon=[dest_lon_float],
                                mode='markers',
                                marker=dict(size=10, color='#DB580F', symbol='circle'),
                                name='Destination' if event_idx == 0 else '',
                                showlegend=(event_idx == 0),
                                hovertemplate=f"<b>Destination:</b> {destination_location_name}<extra></extra>"
                            ))
                        except (ValueError, TypeError):
                            pass  # Skip if coordinates can't be converted to float
            
            # Update map layout
            fig_map.update_layout(
                mapbox=dict(
                    style="open-street-map",
                    zoom=2.5,  # Africa-wide zoom level
                    center=dict(
                        lat=0,   # Center on equator for Africa-wide view
                        lon=20   # Center on Africa longitude
                    )
                ),
                height=600,
                title="Translocation Routes (Dark to Orange gradient shows direction)",
                showlegend=True
            )
            
            st.plotly_chart(fig_map, use_container_width=True)
        else:
            st.info("No location data available for the current events.")
    
    # Detailed event list
    st.subheader("📋 Detailed Event List")
    
    # Create comprehensive table with all event data for export
    export_data = []
    
    for idx, event in df_events.iterrows():
        event_details = event.get('event_details', {})
        
        # Initialize row with specific columns in the exact order requested
        row = {
            'Date & Time': event['time'].strftime('%Y-%m-%d %H:%M') if 'time' in event else 'N/A',
            'Serial Number': event.get('serial_number', 'N/A'),
            'Event Type': event.get('event_type', 'N/A'),
            'Event Category': event.get('event_category', 'N/A'),
            'organisation_1': '',
            'organisation_2': '',
            'organisation_3': '',
            'range': '',
            'translocation_type': '',
            'species': '',
            'origin_country': '',
            'origin_location_name': '',
            'origin_location_latitude': '',
            'origin_location_longitude': '',
            'destination_country': '',
            'destination_location_name': '',
            'destination_location_latitude': '',
            'destination_location_longitude': '',
            'total_individuals': '',
            'males': '',
            'females': '',
            'notes': ''
        }
        
        # Populate event details if available
        if isinstance(event_details, dict):
            # Direct field mappings
            row['organisation_1'] = event_details.get('organisation_1', '')
            row['organisation_2'] = event_details.get('organisation_2', '')
            row['organisation_3'] = event_details.get('organisation_3', '')
            row['range'] = event_details.get('range', '')
            row['translocation_type'] = event_details.get('translocation_type') or event_details.get('trans_type', '')
            row['species'] = event_details.get('species', '')
            row['origin_country'] = event_details.get('origin_country', '')
            row['destination_country'] = event_details.get('destination_country', '')
            row['total_individuals'] = event_details.get('total_individuals', '')
            row['males'] = event_details.get('males', '')
            row['females'] = event_details.get('females', '')
            
            # Extract origin location details
            origin_location = event_details.get('origin_location')
            if isinstance(origin_location, dict):
                row['origin_location_name'] = origin_location.get('name', '')
                row['origin_location_latitude'] = origin_location.get('latitude', '')
                row['origin_location_longitude'] = origin_location.get('longitude', '')
            
            # Extract destination location details
            destination_location = event_details.get('destination_location')
            if isinstance(destination_location, dict):
                row['destination_location_name'] = destination_location.get('name', '')
                row['destination_location_latitude'] = destination_location.get('latitude', '')
                row['destination_location_longitude'] = destination_location.get('longitude', '')
        
        # Add notes if available
        if event.get('notes'):
            notes_list = event['notes']
            if isinstance(notes_list, list) and notes_list:
                # Combine all note texts
                note_texts = []
                for note in notes_list:
                    if isinstance(note, dict):
                        text = note.get('text', '')
                        if text:
                            note_texts.append(text)
                row['notes'] = ' | '.join(note_texts) if note_texts else ''
            else:
                row['notes'] = str(notes_list) if notes_list else ''
        
        export_data.append(row)
    
    # Create DataFrame for export
    export_df = pd.DataFrame(export_data)
    
    # Show the comprehensive table
    st.write("**Comprehensive Event Data Table (Exportable):**")
    st.dataframe(export_df, use_container_width=True)

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
                    st.markdown('<div class="logo-title" style="text-align: center;">Translocation Dashboard</div>', unsafe_allow_html=True)
                    st.markdown('<div class="logo-subtitle" style="text-align: center;">Giraffe Translocation Event Monitoring</div>', unsafe_allow_html=True)
                    logo_displayed = True
            except Exception as e:
                st.error(f"Error loading logo: {str(e)}")
        
        # Fallback header without logo
        if not logo_displayed:
            st.title("🚁 Translocation Dashboard")
            st.markdown("Giraffe translocation event monitoring and analytics")
    
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
    translocation_dashboard()
    
    # Sidebar options
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔧 Options")
    
    if st.sidebar.button("🔄 Refresh Data"):
        # Clear cached data
        get_translocation_events.clear()
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
