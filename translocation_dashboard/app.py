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

@st.cache_data(ttl=1800)  # Cache for 30 minutes
def get_translocation_events(start_date=None, end_date=None):
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
        
        # Add date filters if provided
        if start_date:
            kwargs['since'] = start_date.strftime('%Y-%m-%dT00:00:00Z')
        if end_date:
            kwargs['until'] = end_date.strftime('%Y-%m-%dT23:59:59Z')
        
        # Get events using ecoscope (all veterinary events)
        gdf_events = er_io.get_events(**kwargs)
        
        if gdf_events.empty:
            return pd.DataFrame()
        
        # Convert GeoDataFrame to regular DataFrame for easier handling in Streamlit
        df = pd.DataFrame(gdf_events.drop(columns='geometry', errors='ignore'))
        
        # Filter by event_type after getting the data (avoiding UUID requirement)
        if 'event_type' in df.columns:
            df = df[df['event_type'] == 'giraffe_translocation_2']
        
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
                dest_country = event_details.get('destination_country') or event_details.get('country')
                
                # Ensure dest_country is a string, not a dict or other type
                if dest_country:
                    if isinstance(dest_country, dict):
                        # If it's a dict, try to extract a meaningful country name
                        dest_country = (dest_country.get('name') or 
                                      dest_country.get('country') or 
                                      dest_country.get('code'))
                    elif not isinstance(dest_country, str):
                        dest_country = str(dest_country)
                    
                    if dest_country and dest_country not in all_countries:
                        all_countries.append(dest_country)
    
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
    
    # Validate date range
    if start_date > end_date:
        st.error("❌ Start date cannot be after end date")
        return
    
    # Fetch translocation events
    with st.spinner("🔄 Fetching translocation events from EarthRanger..."):
        df_events = get_translocation_events(start_date, end_date)
    
    # Apply country filter if not "All Countries"
    if selected_country != 'All Countries' and not df_events.empty:
        filtered_events = []
        for idx, event in df_events.iterrows():
            event_details = event.get('event_details', {})
            if isinstance(event_details, dict):
                dest_country = event_details.get('destination_country') or event_details.get('country')
                
                # Ensure dest_country is a string for comparison
                if dest_country:
                    if isinstance(dest_country, dict):
                        dest_country = (dest_country.get('name') or 
                                      dest_country.get('country') or 
                                      dest_country.get('code'))
                    elif not isinstance(dest_country, str):
                        dest_country = str(dest_country)
                    
                    if dest_country == selected_country:
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
    
    # Calculate total individuals translocated and species breakdown
    total_individuals = 0
    species_counts = {}
    
    for idx, event in df_events.iterrows():
        event_details = event.get('event_details', {})
        if isinstance(event_details, dict):
            # Extract species information
            species = event_details.get('species') or event_details.get('animal_species') or 'Unknown'
            if isinstance(species, dict):
                species = species.get('name') or species.get('species') or 'Unknown'
            elif not isinstance(species, str):
                species = str(species) if species else 'Unknown'
            
            # Count individuals for this species
            individuals = event_details.get('total_individuals')
            if individuals is not None:
                try:
                    count = int(individuals)
                    total_individuals += count
                    species_counts[species] = species_counts.get(species, 0) + count
                except (ValueError, TypeError):
                    total_individuals += 1  # Default to 1 if can't parse
                    species_counts[species] = species_counts.get(species, 0) + 1
            else:
                # Fallback to other possible field names if total_individuals is not available
                individuals = (event_details.get('number_of_individuals') or 
                             event_details.get('individuals_count') or 
                             event_details.get('animal_count'))
                if individuals is not None:
                    try:
                        count = int(individuals)
                        total_individuals += count
                        species_counts[species] = species_counts.get(species, 0) + count
                    except (ValueError, TypeError):
                        total_individuals += 1
                        species_counts[species] = species_counts.get(species, 0) + 1
                else:
                    total_individuals += 1  # Default to 1 if no count field found
                    species_counts[species] = species_counts.get(species, 0) + 1
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Translocation Events", len(df_events))
    
    with col2:
        st.metric("Total Individuals Translocated", total_individuals)
    
    with col3:
        st.metric("Species Types", len(species_counts))
    
    # Show species breakdown
    if species_counts:
        st.write("**Species Breakdown:**")
        species_df = pd.DataFrame(list(species_counts.items()), columns=['Species', 'Individuals'])
        species_df = species_df.sort_values('Individuals', ascending=False)
        
        # Show pie chart only (table removed)
        if len(species_df) > 0:
            fig_species = px.pie(
                species_df,
                values='Individuals',
                names='Species',
                title="Individuals by Species"
            )
            st.plotly_chart(fig_species, use_container_width=True)
    
    # Calculate range secured for founder translocations
    st.subheader("🌍 Giraffe Range Secured")
    
    total_range_secured = 0
    founder_locations = []
    species_range_secured = {}
    
    for idx, event in df_events.iterrows():
        event_details = event.get('event_details', {})
        if isinstance(event_details, dict):
            trans_type = event_details.get('trans_type')
            
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
                           event[1].get('event_details', {}).get('trans_type', '').lower() == 'founder'])
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
    
    # Analytics sections
    st.subheader("🌍 Breakdown Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        destination_countries = []
        
        for idx, event in df_events.iterrows():
            event_details = event.get('event_details', {})
            if isinstance(event_details, dict):
                # Extract destination country - ensure it's a string
                dest_country = event_details.get('destination_country') or event_details.get('country') or 'Unknown'
                
                # Ensure dest_country is a string, not a dict or other type
                if isinstance(dest_country, dict):
                    # If it's a dict, try to extract a meaningful country name
                    dest_country = (dest_country.get('name') or 
                                  dest_country.get('country') or 
                                  dest_country.get('code') or
                                  'Unknown')
                elif not isinstance(dest_country, str):
                    dest_country = str(dest_country) if dest_country else 'Unknown'
                
                destination_countries.append(dest_country)
        
        if destination_countries:
            country_counts = pd.Series(destination_countries).value_counts().reset_index()
            country_counts.columns = ['country', 'count']
            
            if len(country_counts) > 0:
                # Custom color palette based on organization colors
                org_colors = [
                    '#DB580F',  # Primary orange
                    '#3E0000',  # Primary dark red
                    '#CCCCCC',  # Light gray
                    '#999999',  # Medium gray
                    '#FF7F3F',  # Lighter orange variant
                    '#5D1010',  # Lighter dark red variant
                    '#E6E6E6',  # Very light gray
                    '#B8860B',  # Golden brown (complementary)
                    '#8B4513',  # Saddle brown (earth tone)
                    '#A0522D'   # Sienna (earth tone)
                ]
                
                fig_countries = px.pie(
                    country_counts,
                    values='count',
                    names='country',
                    title="Events by Destination Country",
                    color_discrete_sequence=org_colors,
                    height=400  # Set consistent height
                )
                st.plotly_chart(fig_countries, use_container_width=True)
    
    with col2:
        trans_types = []
        
        for idx, event in df_events.iterrows():
            event_details = event.get('event_details', {})
            if isinstance(event_details, dict):
                # Extract trans_type
                trans_type = event_details.get('trans_type') or 'Unknown'
                
                # Ensure trans_type is a string
                if isinstance(trans_type, dict):
                    trans_type = (trans_type.get('name') or 
                                trans_type.get('type') or 
                                'Unknown')
                elif not isinstance(trans_type, str):
                    trans_type = str(trans_type) if trans_type else 'Unknown'
                
                trans_types.append(trans_type)
        
        if trans_types:
            type_counts = pd.Series(trans_types).value_counts().reset_index()
            type_counts.columns = ['type', 'count']
            
            if len(type_counts) > 0:
                # Custom colors for translocation types
                color_map = {
                    'founder': '#DB580F',
                    'augmentation': '#3E0000'
                }
                colors = [color_map.get(t.lower(), '#1f77b4') for t in type_counts['type']]
                
                fig_types = px.pie(
                    type_counts,
                    values='count',
                    names='type',
                    title="Events by Translocation Type",
                    color_discrete_sequence=colors,
                    height=400  # Set consistent height
                )
                st.plotly_chart(fig_types, use_container_width=True)
    
    # Map visualization if location data is available
    if 'latitude' in df_events.columns and 'longitude' in df_events.columns:
        events_with_location = df_events[
            df_events['latitude'].notna() & df_events['longitude'].notna()
        ].copy()
        
        if len(events_with_location) > 0:
            st.subheader("🗺️ Translocation Routes")
            
            # Create map with origin and destination points
            fig_map = go.Figure()
            
            for idx, event in events_with_location.iterrows():
                event_details = event.get('event_details', {})
                if isinstance(event_details, dict):
                    # Extract origin and destination coordinates - handle nested location objects
                    origin_location_obj = event_details.get('Origin Location') or event_details.get('origin_location')
                    dest_location_obj = event_details.get('Destination Location') or event_details.get('destination_location')
                    
                    # Initialize coordinates
                    origin_lat = origin_lon = dest_lat = dest_lon = None
                    
                    # Extract origin coordinates from nested object or direct fields
                    if isinstance(origin_location_obj, dict):
                        origin_lat = origin_location_obj.get('latitude')
                        origin_lon = origin_location_obj.get('longitude')
                    else:
                        # Fallback to direct coordinate fields
                        origin_lat = (event_details.get('origin_latitude') or 
                                    event_details.get('origin_lat') or 
                                    event_details.get('source_latitude') or 
                                    event_details.get('source_lat'))
                        origin_lon = (event_details.get('origin_longitude') or 
                                    event_details.get('origin_lon') or 
                                    event_details.get('source_longitude') or 
                                    event_details.get('source_lon'))
                    
                    # Extract destination coordinates from nested object or direct fields
                    if isinstance(dest_location_obj, dict):
                        dest_lat = dest_location_obj.get('latitude')
                        dest_lon = dest_location_obj.get('longitude')
                    else:
                        # Fallback to main event coordinates or direct fields
                        dest_lat = (event.get('latitude') or 
                                  event_details.get('destination_latitude') or 
                                  event_details.get('destination_lat') or
                                  event_details.get('dest_latitude') or
                                  event_details.get('dest_lat'))
                        dest_lon = (event.get('longitude') or 
                                  event_details.get('destination_longitude') or 
                                  event_details.get('destination_lon') or
                                  event_details.get('dest_longitude') or
                                  event_details.get('dest_lon'))
                    
                    # Location names
                    origin_location_name = (event_details.get('origin_location_name') or 
                                          event_details.get('source_location') or 
                                          event_details.get('from_location') or 
                                          'Unknown Origin')
                    destination_location_name = (event_details.get('destination_location_name') or 
                                               event_details.get('dest_location') or 
                                               event_details.get('to_location') or 
                                               'Unknown Destination')
                    
                    # Add origin point if coordinates available
                    if origin_lat and origin_lon:
                        try:
                            origin_lat_float = float(origin_lat)
                            origin_lon_float = float(origin_lon)
                            fig_map.add_trace(go.Scattermapbox(
                                lat=[origin_lat_float],
                                lon=[origin_lon_float],
                                mode='markers',
                                marker=dict(size=15, color='#3E0000', symbol='circle'),  # Dark red for origin (augmentation color)
                                text=f"Origin: {origin_location_name}",
                                name='Origin',
                                showlegend=(idx == events_with_location.index[0]),  # Only show legend for first item
                                hovertemplate="<b>Origin:</b> %{text}<br>" +
                                            "<b>Date:</b> " + event['time'].strftime('%Y-%m-%d') + "<br>" +
                                            "<b>Coordinates:</b> %{lat:.4f}, %{lon:.4f}<extra></extra>"
                            ))
                        except (ValueError, TypeError):
                            pass  # Skip if coordinates can't be converted to float
                    
                    # Add destination point if coordinates available
                    if dest_lat and dest_lon:
                        try:
                            dest_lat_float = float(dest_lat)
                            dest_lon_float = float(dest_lon)
                            fig_map.add_trace(go.Scattermapbox(
                                lat=[dest_lat_float],
                                lon=[dest_lon_float],
                                mode='markers',
                                marker=dict(size=15, color='#DB580F', symbol='circle'),  # Orange for destination
                                text=f"Destination: {destination_location_name}",
                                name='Destination',
                                showlegend=(idx == events_with_location.index[0]),  # Only show legend for first item
                                hovertemplate="<b>Destination:</b> %{text}<br>" +
                                            "<b>Date:</b> " + event['time'].strftime('%Y-%m-%d') + "<br>" +
                                            "<b>Coordinates:</b> %{lat:.4f}, %{lon:.4f}<extra></extra>"
                            ))
                        except (ValueError, TypeError):
                            pass  # Skip if coordinates can't be converted to float
                    
                    # Add curved arrow/line between origin and destination
                    if all([origin_lat, origin_lon, dest_lat, dest_lon]):
                        try:
                            # Create curved path points
                            import numpy as np
                            origin_lat_float, origin_lon_float = float(origin_lat), float(origin_lon)
                            dest_lat_float, dest_lon_float = float(dest_lat), float(dest_lon)
                            
                            # Calculate midpoint and add curvature
                            mid_lat = (origin_lat_float + dest_lat_float) / 2
                            mid_lon = (origin_lon_float + dest_lon_float) / 2
                            
                            # Add curvature offset (perpendicular to the line)
                            dx = dest_lon_float - origin_lon_float
                            dy = dest_lat_float - origin_lat_float
                            curve_offset = 0.1  # Adjust curve intensity
                            
                            # Perpendicular offset for curve
                            perp_x = -dy * curve_offset
                            perp_y = dx * curve_offset
                            
                            # Create curved path with multiple points
                            t = np.linspace(0, 1, 20)
                            curve_lats = []
                            curve_lons = []
                            
                            for point in t:
                                # Quadratic Bezier curve
                                lat = (1-point)**2 * origin_lat_float + 2*(1-point)*point * (mid_lat + perp_y) + point**2 * dest_lat_float
                                lon = (1-point)**2 * origin_lon_float + 2*(1-point)*point * (mid_lon + perp_x) + point**2 * dest_lon_float
                                curve_lats.append(lat)
                                curve_lons.append(lon)
                            
                            # Add curved line
                            fig_map.add_trace(go.Scattermapbox(
                                lat=curve_lats,
                                lon=curve_lons,
                                mode='lines',
                                line=dict(width=4, color='#666666'),  # Solid gray line, slightly thicker
                                name='Route',
                                showlegend=(idx == events_with_location.index[0]),  # Only show legend for first item
                                hovertemplate=f"<b>Route:</b> {origin_location_name} → {destination_location_name}<br>" +
                                            f"<b>Date:</b> {event['time'].strftime('%Y-%m-%d')}<extra></extra>"
                            ))
                            
                            # Add arrow at destination
                            arrow_size = 0.02
                            # Calculate arrow direction
                            arrow_lat = dest_lat_float - arrow_size * np.cos(np.arctan2(dy, dx))
                            arrow_lon = dest_lon_float - arrow_size * np.sin(np.arctan2(dy, dx))
                            
                            fig_map.add_trace(go.Scattermapbox(
                                lat=[arrow_lat, dest_lat_float],
                                lon=[arrow_lon, dest_lon_float],
                                mode='lines',
                                line=dict(width=5, color='#2a2a2a'),
                                name='Direction',
                                showlegend=False,
                                hoverinfo='skip'
                            ))
                        except (ValueError, TypeError):
                            pass  # Skip if coordinates can't be converted to float
            
            # Update map layout
            fig_map.update_layout(
                mapbox=dict(
                    style="open-street-map",
                    zoom=3,  # Africa-wide zoom level
                    center=dict(
                        lat=0,   # Center on equator for Africa-wide view
                        lon=20   # Center on Africa longitude
                    )
                ),
                height=600,
                title="Translocation Routes (Dark Red=Origin, Orange=Destination, Gray=Route)",
                showlegend=True
            )
            
            st.plotly_chart(fig_map, use_container_width=True)
        else:
            st.info("No location data available for the current events.")
    
    # Associated Subjects Section
    st.subheader("🦒 Associated Subjects")
    
    # Collect all subject IDs from events
    all_subject_ids = set()
    event_subject_mapping = {}
    
    for idx, event in df_events.iterrows():
        event_details = event.get('event_details', {})
        if isinstance(event_details, dict):
            subject_names = event_details.get('Subject Names', [])
            if isinstance(subject_names, list):
                event_subjects = []
                for subject_entry in subject_names:
                    if isinstance(subject_entry, dict):
                        subject_id = subject_entry.get('giraffe_er_id')
                        if subject_id:
                            all_subject_ids.add(subject_id)
                            event_subjects.append(subject_id)
                
                if event_subjects:
                    event_subject_mapping[event['time'].strftime('%Y-%m-%d')] = event_subjects
    
    if all_subject_ids:
        with st.spinner("🔄 Fetching subject details..."):
            subjects_df = get_subject_details(list(all_subject_ids))
        
        if not subjects_df.empty:
            # Add status styling
            def style_status(status):
                if status == "Active":
                    return "🟢 Active"
                elif status == "Recent":
                    return "🟡 Recent"
                elif status == "Inactive":
                    return "🔴 Inactive"
                else:
                    return "⚪ Unknown"
            
            # Create display dataframe
            display_df = subjects_df.copy()
            display_df['status_display'] = display_df['status'].apply(style_status)
            
            # Format the table for display
            st.dataframe(
                display_df[['name', 'subject_type', 'sex', 'deployment_start', 'deployment_end', 'last_location_days', 'status_display']],
                use_container_width=True,
                column_config={
                    'name': 'Subject Name',
                    'subject_type': 'Type',
                    'sex': 'Sex',
                    'deployment_start': 'Deployment Start',
                    'deployment_end': 'Last Location',
                    'last_location_days': st.column_config.NumberColumn(
                        'Days Since Last Location',
                        format="%d"
                    ),
                    'status_display': 'Status'
                }
            )
            
            # Summary statistics for subjects
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total Subjects", len(subjects_df))
            
            with col2:
                active_count = len(subjects_df[subjects_df['status'] == 'Active'])
                st.metric("Currently Active", active_count)
            
            with col3:
                inactive_count = len(subjects_df[subjects_df['status'] == 'Inactive'])
                st.metric("Inactive", inactive_count)
            
            # Show which subjects were involved in which events
            st.write("**Subject-Event Associations:**")
            for event_date, subject_ids in event_subject_mapping.items():
                subject_names = []
                for sid in subject_ids:
                    subject_info = subjects_df[subjects_df['subject_id'] == sid]
                    if not subject_info.empty:
                        subject_names.append(subject_info.iloc[0]['name'])
                    else:
                        subject_names.append(f"ID: {sid}")
                
                st.write(f"**{event_date}:** {', '.join(subject_names)}")
            
            st.info("""
            **Status Definitions:**
            - 🟢 **Active**: Last location within 7 days
            - 🟡 **Recent**: Last location within 30 days  
            - 🔴 **Inactive**: Last location over 30 days ago
            - ⚪ **Unknown**: No location data available
            """)
        else:
            st.warning("Could not retrieve subject details from EarthRanger.")
    else:
        st.info("No subjects found in the current translocation events.")
    
    # Detailed event list
    st.subheader("📋 Detailed Event List")
    
    # Sort events by date (most recent first)
    df_sorted = df_events.sort_values('time', ascending=False)
    
    # Show summary table first
    display_columns = ['time', 'serial_number', 'state', 'priority']
    available_columns = [col for col in display_columns if col in df_sorted.columns]
    
    if available_columns:
        st.write("**Event Summary Table:**")
        summary_df = df_sorted[available_columns].copy()
        if 'time' in summary_df.columns:
            summary_df['time'] = summary_df['time'].dt.strftime('%Y-%m-%d %H:%M')
        
        st.dataframe(
            summary_df,
            use_container_width=True,
            column_config={
                'time': 'Date & Time',
                'serial_number': 'Serial Number',
                'state': 'Status',
                'priority': 'Priority'
            }
        )
    
    # Detailed expandable view
    st.write("**Detailed Event Information:**")
    for idx, event in df_sorted.iterrows():
        display_event_details(event)

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
