"""
6-Month Post-Tagging Dashboard
Monitor tagged giraffe subjects 6 months after deployment start date

This dashboard allows users to:
1. Filter subjects by deployment start date range and country
2. View a table of last location information for filtered subjects
3. Generate movement maps from deployment start to 6 months post-deployment
"""

import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta, date
import plotly.express as px
import plotly.graph_objects as go
import json
import os
from dateutil.relativedelta import relativedelta
import numpy as np

# Ecoscope imports for EarthRanger integration
try:
    from ecoscope.io.earthranger import EarthRangerIO
    ECOSCOPE_AVAILABLE = True
except ImportError:
    ECOSCOPE_AVAILABLE = False
    st.warning("⚠️ Ecoscope package not available. Please install ecoscope to use this dashboard.")

# Organization color palette for consistency
ORG_COLORS = ['#DB580F', '#3E0000', '#CCCCCC', '#999999', '#8B4513', '#D2691E', '#CD853F', '#F4A460']

# Custom CSS for better styling with organization branding
st.markdown("""
<style>
    .logo-title {
        color: #DB580F;
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 0.5rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
    }
    .logo-subtitle {
        color: #3E0000;
        font-size: 1.3rem;
        font-weight: 300;
        margin-top: 0;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #DB580F;
        margin: 0.5rem 0;
    }
    .filter-section {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 0.5rem 0;
        border-left: 4px solid #3E0000;
    }
    .stButton > button {
        background-color: #DB580F;
        color: white;
        border: none;
        border-radius: 0.5rem;
        padding: 0.5rem 1rem;
    }
    .stButton > button:hover {
        background-color: #3E0000;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

def init_session_state():
    """Initialize session state variables for authentication and data caching"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'username' not in st.session_state:
        st.session_state.username = ""
    if 'password' not in st.session_state:
        st.session_state.password = ""
    if 'server_url' not in st.session_state:
        st.session_state.server_url = "https://twiga.pamdas.org"
    if 'er_io' not in st.session_state:
        st.session_state.er_io = None
    if 'subjects_data' not in st.session_state:
        st.session_state.subjects_data = None
    if 'map_data_loaded' not in st.session_state:
        st.session_state.map_data_loaded = False
    if 'movement_data' not in st.session_state:
        st.session_state.movement_data = {}

def authenticate_earthranger():
    """Handle EarthRanger authentication using ecoscope"""
    if not ECOSCOPE_AVAILABLE:
        st.error("❌ Ecoscope package is required but not available. Please install ecoscope.")
        return
        
    st.header("🔐 EarthRanger Authentication")
    
    st.write("Enter your EarthRanger credentials to access the 6-month post-tagging dashboard:")
    
    # Fixed server URL
    st.info("**Server:** https://twiga.pamdas.org")
    
    # Username and password inputs
    username = st.text_input(
        "Username",
        value=st.session_state.username,
        help="Your EarthRanger username"
    )
    
    password = st.text_input(
        "Password",
        type="password",
        value=st.session_state.password,
        help="Your EarthRanger password"
    )
    
    if st.button("🔌 Connect to EarthRanger", type="primary"):
        if not username or not password:
            st.error("❌ Both username and password are required")
            return
        
        try:
            with st.spinner("Authenticating with EarthRanger..."):
                # Initialize EarthRanger connection using ecoscope
                er_io = EarthRangerIO(
                    server=st.session_state.server_url,
                    username=username,
                    password=password
                )
                
                # Test connection by fetching a small amount of data
                test_subjects = er_io.get_subjects(max_results=1)
                
                st.success("✅ Successfully authenticated with EarthRanger!")
                
                # Store credentials and connection in session state
                st.session_state.authenticated = True
                st.session_state.username = username
                st.session_state.password = password
                st.session_state.er_io = er_io
                
                st.rerun()
                
        except Exception as e:
            st.error(f"❌ Authentication failed: {str(e)}")
            st.info("💡 Please check your username and password")

@st.cache_data(ttl=1800)  # Cache for 30 minutes
def get_all_subjects(_er_io):
    """
    Fetch all subjects from EarthRanger with deployment information
    
    Args:
        _er_io: EarthRanger IO object (prefixed with _ to avoid hashing)
    
    Returns:
        pd.DataFrame: DataFrame containing subject information
    """
    try:
        with st.spinner("Loading subjects data from EarthRanger..."):
            # Get all subjects
            subjects_gdf = _er_io.get_subjects(include_tracks=False)
            
            if subjects_gdf.empty:
                st.warning("No subjects found in EarthRanger.")
                return pd.DataFrame()
            
            # Convert to DataFrame, dropping geometry column if present
            subjects_df = pd.DataFrame(subjects_gdf.drop(columns='geometry', errors='ignore'))
            
            # DEBUG: Show column information
            st.write("**Debug: Subject DataFrame Info**")
            st.write(f"Total columns: {list(subjects_df.columns)}")
            
            if 'subject_type' in subjects_df.columns:
                unique_types = subjects_df['subject_type'].value_counts()
                st.write("**Subject Types Found:**")
                st.write(unique_types)
            
            if 'subject_groups' in subjects_df.columns:
                st.write("**Sample subject_groups (first 5):**")
                sample_groups = subjects_df['subject_groups'].head().tolist()
                for i, group in enumerate(sample_groups):
                    st.write(f"  {i+1}: {group} (type: {type(group)})")
            
            # FILTER TO KEEP ONLY RELEVANT SUBJECTS
            # 1. Keep only subjects with type='wildlife'
            if 'subject_type' in subjects_df.columns:
                subjects_df = subjects_df[subjects_df['subject_type'] == 'wildlife']
                st.info(f"Filtered to keep only wildlife subjects. Remaining: {len(subjects_df)}")
            
            # 2. Keep only subjects with subject_subtype='giraffe'
            if 'subject_subtype' in subjects_df.columns:
                # Debug: Show subject subtypes before filtering
                if len(subjects_df) > 0:
                    subtype_counts = subjects_df['subject_subtype'].value_counts()
                    st.write("**Subject Subtypes Found:**")
                    st.write(subtype_counts)
                
                subjects_df = subjects_df[subjects_df['subject_subtype'] == 'giraffe']
                st.info(f"Filtered to keep only giraffe subjects. Remaining: {len(subjects_df)}")
            
            # 3. Filter out subjects belonging to 'NAN_NANW_giraffe' group (if column exists)
            if 'subject_groups' in subjects_df.columns:
                def is_valid_subject(subject_groups):
                    """Check if subject should be included (not in NAN_NANW_giraffe group)"""
                    if pd.isna(subject_groups) or not subject_groups:
                        return True
                    
                    # Handle different formats of subject_groups
                    if isinstance(subject_groups, list):
                        group_names = [str(group).lower() for group in subject_groups]
                    elif isinstance(subject_groups, str):
                        group_names = [subject_groups.lower()]
                    else:
                        group_names = [str(subject_groups).lower()]
                    
                    # Check if any group contains 'nan_nanw_giraffe'
                    return not any('nan_nanw_giraffe' in name for name in group_names)
                
                subjects_df = subjects_df[subjects_df['subject_groups'].apply(is_valid_subject)]
                st.info(f"Filtered out NAN_NANW_giraffe group subjects. Remaining: {len(subjects_df)}")
            
            if subjects_df.empty:
                st.warning("No valid subjects found after filtering.")
                return pd.DataFrame()
            
            # Add country extraction from subject_subtype (second section after _)
            subjects_df['country'] = subjects_df['subject_subtype'].apply(extract_country_from_subtype)
            
            # Get deployment information for each subject using available data
            deployments_list = []
            
            progress_bar = st.progress(0)
            total_subjects = len(subjects_df)
            
            st.write(f"**Debug: Attempting to get deployment info for {total_subjects} subjects...**")
            
            # First check if subjects have tracks_available flag and last_position_date
            if 'tracks_available' in subjects_df.columns:
                tracks_available_count = subjects_df['tracks_available'].sum()
                st.write(f"**Subjects with tracks_available=True: {tracks_available_count}**")
            
            if 'last_position_date' in subjects_df.columns:
                subjects_with_positions = subjects_df['last_position_date'].notna().sum()
                st.write(f"**Subjects with last_position_date: {subjects_with_positions}**")
                
                # Show sample of last position dates
                sample_positions = subjects_df[subjects_df['last_position_date'].notna()]['last_position_date'].head(5)
                st.write(f"**Sample last position dates:**")
                for pos in sample_positions:
                    st.write(f"  - {pos}")
            
            # Try to use available subject data instead of calling additional APIs
            for i, (_, subject) in enumerate(subjects_df.iterrows()):
                try:
                    subject_id = subject['id']
                    subject_name = subject.get('name', f'Subject-{subject_id[:8]}')
                    
                    # Check if subject has tracking data available
                    has_tracks = subject.get('tracks_available', False)
                    last_position_date = subject.get('last_position_date')
                    
                    if has_tracks or pd.notna(last_position_date):
                        # Use available data to create deployment record
                        deployment_start = None
                        deployment_end = None
                        
                        # Try to parse last_position_date
                        if pd.notna(last_position_date):
                            try:
                                deployment_end = pd.to_datetime(last_position_date)
                                # Estimate deployment start (assume max 2 years ago)
                                deployment_start = deployment_end - pd.Timedelta(days=730)
                            except:
                                pass
                        
                        # If we still don't have dates, use created_at as deployment start
                        if deployment_start is None and 'created_at' in subject:
                            try:
                                deployment_start = pd.to_datetime(subject['created_at'])
                                if deployment_end is None:
                                    deployment_end = deployment_start + pd.Timedelta(days=180)  # Assume 6 months
                            except:
                                pass
                        
                        # Only add if we have at least a deployment start date
                        if deployment_start is not None:
                            deployments_list.append({
                                'subject_id': subject_id,
                                'subject_name': subject_name,
                                'subject_subtype': subject.get('subject_subtype', 'Unknown'),
                                'country': subject.get('country', 'Unknown'),
                                'deployment_start': deployment_start,
                                'deployment_end': deployment_end,
                                'device_id': 'Unknown',
                                'collar_model': 'Unknown',
                                'tracks_available': has_tracks,
                                'last_position_date': last_position_date
                            })
                            
                            if i < 5:  # Debug first 5 subjects
                                st.write(f"**Debug Subject {i+1}: {subject_name}**")
                                st.write(f"  - ID: {subject_id}")
                                st.write(f"  - Tracks available: {has_tracks}")
                                st.write(f"  - Last position: {last_position_date}")
                                st.write(f"  - Deployment start: {deployment_start}")
                        
                except Exception as e:
                    if i < 5:  # Only show errors for first 5
                        st.write(f"  - Error processing subject: {str(e)}")
                    continue
                
                # Update progress
                progress_bar.progress((i + 1) / total_subjects)
            
            progress_bar.empty()
            
            st.write(f"**Debug: Found {len(deployments_list)} subjects with valid deployment information**")
            
            if not deployments_list:
                st.warning("No subjects with deployment/tracking information found.")
                return pd.DataFrame()
            
            deployments_df = pd.DataFrame(deployments_list)
            
            # Filter to only include subjects with valid deployment dates
            deployments_df = deployments_df.dropna(subset=['deployment_start'])
            
            st.success(f"Successfully loaded {len(deployments_df)} subjects with deployment information.")
            
            return deployments_df
            
    except Exception as e:
        st.error(f"Error fetching subjects data: {str(e)}")
        return pd.DataFrame()

def extract_country_from_subtype(subject_subtype):
    """
    Extract country code from subject_subtype (second section after underscore)
    
    Args:
        subject_subtype (str): Subject subtype string (e.g., "giraffe_nam_adult")
    
    Returns:
        str: Country code in uppercase (e.g., "NAM") or "Unknown"
    """
    if pd.isna(subject_subtype) or not isinstance(subject_subtype, str):
        return "Unknown"
    
    parts = subject_subtype.split('_')
    if len(parts) >= 2:
        return parts[1].upper()
    else:
        return "Unknown"

@st.cache_data(ttl=1800)  # Cache for 30 minutes
def get_subject_last_locations(_er_io, subject_ids):
    """
    Get the last known location for each subject using available subject data
    
    Args:
        _er_io: EarthRanger IO object
        subject_ids: List of subject IDs
    
    Returns:
        pd.DataFrame: DataFrame with last location information
    """
    try:
        # Get fresh subject data to get last positions
        subjects_gdf = _er_io.get_subjects()
        subjects_df = pd.DataFrame(subjects_gdf.drop(columns='geometry', errors='ignore'))
        
        # Filter for our subject IDs
        filtered_subjects = subjects_df[subjects_df['id'].isin(subject_ids)]
        
        last_locations = []
        
        for _, subject in filtered_subjects.iterrows():
            subject_id = subject['id']
            
            # Extract last position data from subject record
            last_position = subject.get('last_position')
            last_position_date = subject.get('last_position_date')
            
            last_longitude = None
            last_latitude = None
            
            # Parse last_position if available (usually contains coordinates)
            if pd.notna(last_position) and last_position:
                try:
                    if isinstance(last_position, dict):
                        last_longitude = last_position.get('longitude')
                        last_latitude = last_position.get('latitude')
                    elif isinstance(last_position, str):
                        # Try to parse if it's a string representation
                        import json
                        pos_data = json.loads(last_position)
                        last_longitude = pos_data.get('longitude')
                        last_latitude = pos_data.get('latitude')
                except:
                    pass
            
            last_locations.append({
                'subject_id': subject_id,
                'last_longitude': last_longitude,
                'last_latitude': last_latitude,
                'last_recorded_at': pd.to_datetime(last_position_date) if pd.notna(last_position_date) else None,
                'last_fix_type': 'Subject Record'
            })
        
        return pd.DataFrame(last_locations)
        
    except Exception as e:
        st.error(f"Error fetching location data: {str(e)}")
        return pd.DataFrame()

def load_movement_data_for_subject(er_io, subject_id, deployment_start):
    """
    Load 6 months of movement data for a specific subject
    
    Args:
        er_io: EarthRanger IO object
        subject_id: Subject ID
        deployment_start: Deployment start datetime
    
    Returns:
        pd.DataFrame: Movement data for the subject
    """
    try:
        # Calculate 6 months from deployment start
        end_time = deployment_start + relativedelta(months=6)
        
        st.write(f"⚠️ Note: Movement data loading not yet implemented due to API method limitations.")
        st.write(f"Available EarthRangerIO methods need to be explored for subject tracking data.")
        
        # For now, return empty DataFrame
        # TODO: Implement proper movement data retrieval once correct API method is identified
        return pd.DataFrame()
            
    except Exception as e:
        st.warning(f"Could not load movement data for subject {subject_id}: {str(e)}")
        return pd.DataFrame()

def create_movement_map(movement_data, subjects_info):
    """
    Create an interactive map showing 6-month movement tracks for subjects
    
    Args:
        movement_data (dict): Dictionary with subject_id as keys and movement DataFrames as values
        subjects_info (pd.DataFrame): DataFrame with subject information
    
    Returns:
        plotly.graph_objects.Figure: Interactive map figure
    """
    fig = go.Figure()
    
    # Color palette for different subjects
    colors = ORG_COLORS * (len(movement_data) // len(ORG_COLORS) + 1)
    
    for i, (subject_id, movement_df) in enumerate(movement_data.items()):
        if movement_df.empty:
            continue
        
        # Get subject info
        subject_info = subjects_info[subjects_info['subject_id'] == subject_id].iloc[0]
        subject_name = subject_info['subject_name']
        country = subject_info['country']
        
        # Create trace for movement track
        fig.add_trace(go.Scattermapbox(
            lat=movement_df['location_lat'],
            lon=movement_df['location_long'],
            mode='lines+markers',
            marker=dict(
                size=4,
                color=colors[i],
                opacity=0.7
            ),
            line=dict(
                width=2,
                color=colors[i]
            ),
            name=f"{subject_name} ({country})",
            hovertemplate="<b>%{text}</b><br>" +
                         "Date: %{customdata}<br>" +
                         "Lat: %{lat:.4f}<br>" +
                         "Lon: %{lon:.4f}<br>" +
                         "<extra></extra>",
            text=[f"{subject_name}"] * len(movement_df),
            customdata=movement_df['recorded_at'].dt.strftime('%Y-%m-%d %H:%M')
        ))
        
        # Add start point marker
        if not movement_df.empty:
            first_point = movement_df.iloc[0]
            fig.add_trace(go.Scattermapbox(
                lat=[first_point['location_lat']],
                lon=[first_point['location_long']],
                mode='markers',
                marker=dict(
                    size=12,
                    color='green',
                    symbol='circle'
                ),
                name=f"{subject_name} - Start",
                hovertemplate="<b>%{text} - START</b><br>" +
                             "Deployment: %{customdata}<br>" +
                             "Lat: %{lat:.4f}<br>" +
                             "Lon: %{lon:.4f}<br>" +
                             "<extra></extra>",
                text=[f"{subject_name}"],
                customdata=[first_point['recorded_at'].strftime('%Y-%m-%d %H:%M')]
            ))
            
            # Add end point marker (or last known position)
            last_point = movement_df.iloc[-1]
            fig.add_trace(go.Scattermapbox(
                lat=[last_point['location_lat']],
                lon=[last_point['location_long']],
                mode='markers',
                marker=dict(
                    size=12,
                    color='red',
                    symbol='square'
                ),
                name=f"{subject_name} - End/Last",
                hovertemplate="<b>%{text} - END/LAST</b><br>" +
                             "Last Fix: %{customdata}<br>" +
                             "Lat: %{lat:.4f}<br>" +
                             "Lon: %{lon:.4f}<br>" +
                             "<extra></extra>",
                text=[f"{subject_name}"],
                customdata=[last_point['recorded_at'].strftime('%Y-%m-%d %H:%M')]
            ))
    
    # Calculate center and zoom based on all data points
    if movement_data:
        all_lats = []
        all_lons = []
        for movement_df in movement_data.values():
            if not movement_df.empty:
                all_lats.extend(movement_df['location_lat'].dropna().tolist())
                all_lons.extend(movement_df['location_long'].dropna().tolist())
        
        if all_lats and all_lons:
            center_lat = np.mean(all_lats)
            center_lon = np.mean(all_lons)
            
            # Calculate zoom level based on data spread
            lat_range = max(all_lats) - min(all_lats)
            lon_range = max(all_lons) - min(all_lons)
            zoom = max(1, min(10, 8 - np.log10(max(lat_range, lon_range) + 0.01)))
        else:
            center_lat, center_lon, zoom = -20, 20, 3  # Default to Africa
    else:
        center_lat, center_lon, zoom = -20, 20, 3  # Default to Africa
    
    # Update layout
    fig.update_layout(
        mapbox=dict(
            style="open-street-map",
            center=dict(lat=center_lat, lon=center_lon),
            zoom=zoom
        ),
        height=600,
        title={
            'text': "6-Month Movement Tracks (Green: Start, Red: End/Last Position)",
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 16, 'color': '#3E0000'}
        },
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.02
        ),
        margin=dict(l=0, r=150, t=50, b=0)
    )
    
    return fig

def main():
    """Main application function"""
    st.markdown('<h1 class="logo-title">🏷️ 6-Month Post-Tagging Dashboard</h1>', unsafe_allow_html=True)
    st.markdown('<p class="logo-subtitle">Monitor tagged giraffe subjects 6 months after deployment</p>', unsafe_allow_html=True)
    
    # Initialize session state
    init_session_state()
    
    # Check authentication
    if not st.session_state.authenticated:
        authenticate_earthranger()
        return
    
    # Main dashboard content
    st.success(f"✅ Connected to EarthRanger as: {st.session_state.username}")
    
    # Sidebar filters
    st.sidebar.markdown('<div class="filter-section">', unsafe_allow_html=True)
    st.sidebar.header("📊 Filters")
    
    # Date range filter for deployment start
    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_date = st.date_input(
            "Deployment Start - From",
            value=date.today() - timedelta(days=1095),  # 3 years back to include older deployments
            help="Filter subjects by deployment start date"
        )
    with col2:
        end_date = st.date_input(
            "Deployment Start - To",
            value=date.today(),
            help="Filter subjects by deployment start date"
        )
    
    # Load subjects data if not already loaded
    if st.session_state.subjects_data is None:
        st.session_state.subjects_data = get_all_subjects(st.session_state.er_io)
    
    subjects_data = st.session_state.subjects_data
    
    # Add debug exploration section
    with st.expander("🔍 Debug Data Exploration", expanded=False):
        if st.button("🔬 Explore Raw Subject Data"):
            if st.session_state.er_io:
                try:
                    raw_subjects = st.session_state.er_io.get_subjects()
                    if not raw_subjects.empty:
                        st.write("**Raw subjects sample (first 3):**")
                        sample_df = pd.DataFrame(raw_subjects.head(3).drop(columns='geometry', errors='ignore'))
                        st.dataframe(sample_df)
                        
                        st.write("**Available columns:**")
                        st.write(list(raw_subjects.columns))
                        
                        if 'subject_type' in raw_subjects.columns:
                            st.write("**All subject types:**")
                            st.write(raw_subjects['subject_type'].value_counts())
                        
                        if 'subject_subtype' in raw_subjects.columns:
                            st.write("**Sample subject subtypes (first 10):**")
                            st.write(raw_subjects['subject_subtype'].value_counts().head(10))
                    else:
                        st.warning("No raw subjects found")
                except Exception as e:
                    st.error(f"Error exploring raw data: {e}")
        
        if st.button("🎯 Test Single Subject Tracks"):
            if st.session_state.er_io and not subjects_data.empty:
                try:
                    # Test with the first subject
                    test_subject_id = subjects_data.iloc[0]['subject_id']
                    st.write(f"Testing tracks for subject: {test_subject_id}")
                    
                    tracks = st.session_state.er_io.get_subjecttracks(subject_ids=[test_subject_id])
                    st.write(f"Tracks found: {len(tracks) if not tracks.empty else 0}")
                    
                    if not tracks.empty:
                        tracks_df = pd.DataFrame(tracks.drop(columns='geometry', errors='ignore'))
                        st.write("**Track columns:**")
                        st.write(list(tracks_df.columns))
                        st.write("**Sample track data:**")
                        st.dataframe(tracks_df.head())
                    else:
                        st.warning("No tracks found for test subject")
                        
                except Exception as e:
                    st.error(f"Error testing single subject tracks: {e}")
    
    if subjects_data.empty:
        st.error("No subjects data available.")
        return
    
    # Country filter
    available_countries = sorted(subjects_data['country'].unique())
    selected_countries = st.sidebar.multiselect(
        "Select Countries",
        options=available_countries,
        default=available_countries,
        help="Filter subjects by country"
    )
    
    st.sidebar.markdown('</div>', unsafe_allow_html=True)
    
    # Debug: Show deployment date ranges in the data
    if not subjects_data.empty:
        min_deployment = subjects_data['deployment_start'].min()
        max_deployment = subjects_data['deployment_start'].max()
        st.sidebar.write(f"**Data Range:**")
        st.sidebar.write(f"Earliest deployment: {min_deployment.strftime('%Y-%m-%d') if pd.notna(min_deployment) else 'Unknown'}")
        st.sidebar.write(f"Latest deployment: {max_deployment.strftime('%Y-%m-%d') if pd.notna(max_deployment) else 'Unknown'}")
        st.sidebar.write(f"Total subjects available: {len(subjects_data)}")
    
    # Apply filters
    filtered_data = subjects_data[
        (subjects_data['deployment_start'].dt.date >= start_date) &
        (subjects_data['deployment_start'].dt.date <= end_date) &
        (subjects_data['country'].isin(selected_countries))
    ].copy()
    
    # Debug: Show filtering results
    st.write(f"**Filter Debug:**")
    st.write(f"Date range: {start_date} to {end_date}")
    st.write(f"Countries selected: {len(selected_countries)}")
    st.write(f"Subjects after date filter: {len(subjects_data[(subjects_data['deployment_start'].dt.date >= start_date) & (subjects_data['deployment_start'].dt.date <= end_date)])}")
    st.write(f"Subjects after all filters: {len(filtered_data)}")
    
    # Display summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(
            f'<div class="metric-card"><h3 style="color: #DB580F; margin: 0;">{len(filtered_data)}</h3><p style="margin: 0;">Subjects in Range</p></div>',
            unsafe_allow_html=True
        )
    
    with col2:
        unique_countries = len(filtered_data['country'].unique()) if not filtered_data.empty else 0
        st.markdown(
            f'<div class="metric-card"><h3 style="color: #DB580F; margin: 0;">{unique_countries}</h3><p style="margin: 0;">Countries</p></div>',
            unsafe_allow_html=True
        )
    
    with col3:
        if not filtered_data.empty:
            latest_deployment = filtered_data['deployment_start'].max().strftime('%Y-%m-%d')
        else:
            latest_deployment = "N/A"
        st.markdown(
            f'<div class="metric-card"><h3 style="color: #DB580F; margin: 0;">{latest_deployment}</h3><p style="margin: 0;">Latest Deployment</p></div>',
            unsafe_allow_html=True
        )
    
    with col4:
        if not filtered_data.empty:
            earliest_deployment = filtered_data['deployment_start'].min().strftime('%Y-%m-%d')
        else:
            earliest_deployment = "N/A"
        st.markdown(
            f'<div class="metric-card"><h3 style="color: #DB580F; margin: 0;">{earliest_deployment}</h3><p style="margin: 0;">Earliest Deployment</p></div>',
            unsafe_allow_html=True
        )
    
    if filtered_data.empty:
        st.warning("No subjects found matching the selected filters.")
        return
    
    # Get last location information for filtered subjects
    st.header("📍 Last Location Information")
    
    with st.spinner("Loading last location data..."):
        last_locations = get_subject_last_locations(st.session_state.er_io, filtered_data['subject_id'].tolist())
    
    # Merge subjects data with last locations
    display_data = filtered_data.merge(last_locations, on='subject_id', how='left')
    
    # Format the display table
    display_table = display_data[[
        'subject_name', 'country', 'deployment_start', 'device_id', 
        'last_latitude', 'last_longitude', 'last_recorded_at', 'last_fix_type'
    ]].copy()
    
    display_table['deployment_start'] = display_table['deployment_start'].dt.strftime('%Y-%m-%d %H:%M')
    display_table['last_recorded_at'] = display_table['last_recorded_at'].apply(
        lambda x: x.strftime('%Y-%m-%d %H:%M') if pd.notna(x) else 'No data'
    )
    display_table['last_latitude'] = display_table['last_latitude'].apply(
        lambda x: f"{x:.6f}" if pd.notna(x) else 'No data'
    )
    display_table['last_longitude'] = display_table['last_longitude'].apply(
        lambda x: f"{x:.6f}" if pd.notna(x) else 'No data'
    )
    
    # Rename columns for better display
    display_table.columns = [
        'Subject Name', 'Country', 'Deployment Start', 'Device ID',
        'Last Latitude', 'Last Longitude', 'Last Fix Time', 'Fix Type'
    ]
    
    # Display the table
    st.dataframe(
        display_table,
        use_container_width=True,
        height=400
    )
    
    # Map generation section
    st.header("🗺️ 6-Month Movement Tracking")
    
    st.info("""
    **Note:** Loading movement data for multiple subjects over 6 months may take several minutes. 
    Click the button below to generate the movement map for all filtered subjects.
    """)
    
    # Button to generate map
    if st.button("🗺️ Generate 6-Month Movement Map", type="primary"):
        
        if len(filtered_data) > 10:
            st.warning(f"You have selected {len(filtered_data)} subjects. This may take a long time to load. Consider filtering to fewer subjects.")
            if not st.button("Continue with All Subjects"):
                st.stop()
        
        # Load movement data for all filtered subjects
        movement_data = {}
        
        progress_container = st.container()
        with progress_container:
            st.write("Loading movement data...")
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            total_subjects = len(filtered_data)
            
            for i, (_, subject_row) in enumerate(filtered_data.iterrows()):
                subject_id = subject_row['subject_id']
                subject_name = subject_row['subject_name']
                deployment_start = subject_row['deployment_start']
                
                status_text.text(f"Loading data for {subject_name} ({i+1}/{total_subjects})...")
                
                # Load movement data for this subject
                subject_movement = load_movement_data_for_subject(
                    st.session_state.er_io, 
                    subject_id, 
                    deployment_start
                )
                
                if not subject_movement.empty:
                    movement_data[subject_id] = subject_movement
                
                progress_bar.progress((i + 1) / total_subjects)
            
            progress_container.empty()
        
        # Create and display map
        if movement_data:
            st.success(f"Successfully loaded movement data for {len(movement_data)} subjects.")
            
            # Create movement map
            movement_map = create_movement_map(movement_data, filtered_data)
            st.plotly_chart(movement_map, use_container_width=True)
            
            # Display summary statistics
            st.subheader("📊 Movement Summary")
            
            summary_stats = []
            for subject_id, movement_df in movement_data.items():
                subject_info = filtered_data[filtered_data['subject_id'] == subject_id].iloc[0]
                
                if not movement_df.empty:
                    total_fixes = len(movement_df)
                    date_range = (movement_df['recorded_at'].max() - movement_df['recorded_at'].min()).days
                    
                    summary_stats.append({
                        'Subject': subject_info['subject_name'],
                        'Country': subject_info['country'],
                        'Total Fixes': total_fixes,
                        'Tracking Days': date_range,
                        'First Fix': movement_df['recorded_at'].min().strftime('%Y-%m-%d'),
                        'Last Fix': movement_df['recorded_at'].max().strftime('%Y-%m-%d')
                    })
            
            if summary_stats:
                summary_df = pd.DataFrame(summary_stats)
                st.dataframe(summary_df, use_container_width=True)
        else:
            st.warning("No movement data found for the selected subjects and date range.")

if __name__ == "__main__":
    main()