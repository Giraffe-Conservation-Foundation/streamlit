"""
Post-Tagging Dashboard
Monitor giraffe locations during first 2 days after deployment/tagging
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from ecoscope.io.earthranger import EarthRangerIO

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
    """Test EarthRanger login credentials"""
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
    """Handle EarthRanger authentication"""
    st.header("🔐 EarthRanger Authentication")
    
    with st.form("auth_form"):
        st.write("Enter your EarthRanger credentials:")
        
        # Server URL (fixed)
        st.info("**Server:** https://twiga.pamdas.org")
        
        # Credentials
        username = st.text_input("Username", value=st.session_state.username)
        password = st.text_input("Password", type="password")
        
        submit_button = st.form_submit_button("🔌 Connect to EarthRanger", type="primary")
        
        if submit_button:
            if not username or not password:
                st.error("❌ Username and password are required")
                return
            
            with st.spinner("Authenticating..."):
                if er_login(username, password):
                    st.session_state.authenticated = True
                    st.session_state.username = username
                    st.session_state.password = password
                    st.success("✅ Successfully authenticated!")
                    st.rerun()
                else:
                    st.error("❌ Authentication failed. Please check your credentials.")

@st.cache_data(ttl=3600)
def get_subjects_with_deployments(_er, start_date, end_date):
    """Get subjects with collar deployments within date range"""
    try:
        # Get all subjects
        subjects_df = _er.get_subjects()
        
        if subjects_df.empty:
            return pd.DataFrame()
        
        # Filter for subjects with deployments in the date range
        subjects_with_deployments = []
        
        for _, subject in subjects_df.iterrows():
            # Check if subject has assigned_range within our date range
            if pd.notna(subject.get('assigned_range')):
                assigned_range = subject['assigned_range']
                if isinstance(assigned_range, dict):
                    start_time = assigned_range.get('start_time')
                    if start_time:
                        deployment_date = pd.to_datetime(start_time).date()
                        if start_date <= deployment_date <= end_date:
                            subjects_with_deployments.append({
                                'id': subject['id'],
                                'name': subject['name'],
                                'deployment_date': deployment_date,
                                'deployment_datetime': pd.to_datetime(start_time),
                                'subject_subtype': subject.get('subject_subtype', ''),
                                'additional': subject.get('additional', {})
                            })
        
        return pd.DataFrame(subjects_with_deployments)
        
    except Exception as e:
        st.error(f"Error fetching subjects: {str(e)}")
        return pd.DataFrame()

@st.cache_data(ttl=1800)
def get_subject_locations(_er, subject_id, start_datetime, end_datetime):
    """Get locations for a subject within specific datetime range"""
    try:
        locations_df = _er.get_subject_observations(
            subject_id=subject_id,
            include_details=True,
            since=start_datetime,
            until=end_datetime
        )
        
        if not locations_df.empty:
            # Ensure we have the required columns
            required_cols = ['recorded_at', 'location_lat', 'location_long']
            if all(col in locations_df.columns for col in required_cols):
                # Convert recorded_at to datetime if it's not already
                locations_df['recorded_at'] = pd.to_datetime(locations_df['recorded_at'])
                # Filter out any records with null coordinates
                locations_df = locations_df.dropna(subset=['location_lat', 'location_long'])
                return locations_df
        
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"Error fetching locations for subject {subject_id}: {str(e)}")
        return pd.DataFrame()

def create_deployment_map(subjects_df, locations_data):
    """Create interactive map showing deployment locations and tracks"""
    fig = go.Figure()
    
    # Define colors for different subjects
    colors = px.colors.qualitative.Set3
    color_map = {}
    
    for i, (_, subject) in enumerate(subjects_df.iterrows()):
        subject_id = subject['id']
        subject_name = subject['name']
        color = colors[i % len(colors)]
        color_map[subject_id] = color
        
        # Add deployment start marker
        if subject_id in locations_data and not locations_data[subject_id].empty:
            first_location = locations_data[subject_id].iloc[0]
            fig.add_trace(go.Scattermapbox(
                lat=[first_location['location_lat']],
                lon=[first_location['location_long']],
                mode='markers',
                marker=dict(
                    size=15,
                    color=color,
                    symbol='star'
                ),
                name=f"{subject_name} - Deployment",
                text=f"<b>{subject_name}</b><br>Deployment: {subject['deployment_date']}<br>Time: {first_location['recorded_at'].strftime('%Y-%m-%d %H:%M')}",
                hovertemplate='%{text}<extra></extra>'
            ))
            
            # Add location track
            df = locations_data[subject_id].sort_values('recorded_at')
            fig.add_trace(go.Scattermapbox(
                lat=df['location_lat'],
                lon=df['location_long'],
                mode='lines+markers',
                line=dict(width=2, color=color),
                marker=dict(size=6, color=color, opacity=0.7),
                name=f"{subject_name} - Track",
                text=[f"<b>{subject_name}</b><br>Time: {dt.strftime('%Y-%m-%d %H:%M')}<br>Lat: {lat:.5f}<br>Lon: {lon:.5f}" 
                      for dt, lat, lon in zip(df['recorded_at'], df['location_lat'], df['location_long'])],
                hovertemplate='%{text}<extra></extra>'
            ))
    
    # Calculate center point
    all_lats = []
    all_lons = []
    for df in locations_data.values():
        if not df.empty:
            all_lats.extend(df['location_lat'].tolist())
            all_lons.extend(df['location_long'].tolist())
    
    if all_lats and all_lons:
        center_lat = np.mean(all_lats)
        center_lon = np.mean(all_lons)
        zoom = 10
    else:
        center_lat, center_lon = -2.0, 37.0  # Default to Kenya
        zoom = 6
    
    fig.update_layout(
        mapbox=dict(
            style="open-street-map",
            center=dict(lat=center_lat, lon=center_lon),
            zoom=zoom
        ),
        height=600,
        margin=dict(l=0, r=0, t=30, b=0),
        title="Giraffe Deployment Locations and 2-Day Movement Tracks",
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01,
            bgcolor="rgba(255, 255, 255, 0.8)"
        )
    )
    
    return fig

def create_timeline_chart(subjects_df, locations_data):
    """Create timeline showing data collection over 48 hours"""
    fig = go.Figure()
    
    colors = px.colors.qualitative.Set3
    
    for i, (_, subject) in enumerate(subjects_df.iterrows()):
        subject_id = subject['id']
        subject_name = subject['name']
        color = colors[i % len(colors)]
        
        if subject_id in locations_data and not locations_data[subject_id].empty:
            df = locations_data[subject_id].sort_values('recorded_at')
            
            # Calculate hours since deployment
            deployment_time = subject['deployment_datetime']
            df['hours_since_deployment'] = (df['recorded_at'] - deployment_time).dt.total_seconds() / 3600
            
            fig.add_trace(go.Scatter(
                x=df['hours_since_deployment'],
                y=[subject_name] * len(df),
                mode='markers',
                marker=dict(
                    color=color,
                    size=8,
                    line=dict(width=1, color='white')
                ),
                name=subject_name,
                text=[f"Time: {dt.strftime('%Y-%m-%d %H:%M')}<br>Hours since deployment: {hours:.1f}" 
                      for dt, hours in zip(df['recorded_at'], df['hours_since_deployment'])],
                hovertemplate='<b>%{y}</b><br>%{text}<extra></extra>'
            ))
    
    fig.update_layout(
        title="Data Collection Timeline (48 Hours Post-Deployment)",
        xaxis_title="Hours Since Deployment",
        yaxis_title="Subject",
        height=400,
        showlegend=False,
        xaxis=dict(range=[0, 48], dtick=6),
        margin=dict(l=0, r=0, t=40, b=0)
    )
    
    # Add vertical lines for day boundaries
    fig.add_vline(x=24, line_dash="dash", line_color="gray", annotation_text="24 hours")
    fig.add_vline(x=48, line_dash="dash", line_color="red", annotation_text="48 hours")
    
    return fig

def create_movement_summary(subjects_df, locations_data):
    """Create summary statistics for movement during first 48 hours"""
    summary_data = []
    
    for _, subject in subjects_df.iterrows():
        subject_id = subject['id']
        subject_name = subject['name']
        
        if subject_id in locations_data and not locations_data[subject_id].empty:
            df = locations_data[subject_id].sort_values('recorded_at')
            
            # Calculate basic stats
            num_locations = len(df)
            time_span = (df['recorded_at'].max() - df['recorded_at'].min()).total_seconds() / 3600
            
            # Calculate approximate distance traveled
            if len(df) > 1:
                # Simple distance calculation (not accounting for earth curvature, but good enough for short distances)
                lat_diff = df['location_lat'].diff()
                lon_diff = df['location_long'].diff()
                distances = np.sqrt(lat_diff**2 + lon_diff**2) * 111  # Rough conversion to km
                total_distance = distances.sum()
            else:
                total_distance = 0
                
            # Calculate area of movement (convex hull approximation)
            if len(df) >= 3:
                lat_range = df['location_lat'].max() - df['location_lat'].min()
                lon_range = df['location_long'].max() - df['location_long'].min() 
                area_approx = lat_range * lon_range * (111**2)  # Very rough area in km²
            else:
                area_approx = 0
            
            summary_data.append({
                'Subject': subject_name,
                'Deployment Date': subject['deployment_date'],
                'Locations Recorded': num_locations,
                'Time Span (hours)': round(time_span, 1),
                'Approx Distance (km)': round(total_distance, 2),
                'Movement Area (km²)': round(area_approx, 4)
            })
    
    return pd.DataFrame(summary_data)

def main():
    """Main dashboard function"""
    st.set_page_config(
        page_title="Post-Tagging Dashboard",
        page_icon="📡",
        layout="wide"
    )
    
    st.title("📡 Post-Tagging Dashboard")
    st.markdown("Monitor giraffe locations during the first 2 days after collar deployment/tagging")
    
    # Initialize session state
    init_session_state()
    
    # Authentication
    if not st.session_state.authenticated:
        authenticate_earthranger()
        return
    
    # Create EarthRanger connection
    try:
        er = EarthRangerIO(
            server=st.session_state.server_url,
            username=st.session_state.username,
            password=st.session_state.password
        )
    except Exception as e:
        st.error(f"Failed to connect to EarthRanger: {str(e)}")
        st.session_state.authenticated = False
        st.rerun()
        return
    
    # Sidebar filters
    st.sidebar.header("📅 Deployment Date Range")
    st.sidebar.write("Select the period when collars were deployed:")
    
    # Date range selection
    default_end = datetime.now().date()
    default_start = default_end - timedelta(days=30)
    
    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=default_start)
    with col2:
        end_date = st.date_input("End Date", value=default_end)
    
    if start_date > end_date:
        st.sidebar.error("Start date must be before end date")
        return
    
    # Get subjects with deployments
    with st.spinner("Loading deployment data..."):
        subjects_df = get_subjects_with_deployments(er, start_date, end_date)
    
    if subjects_df.empty:
        st.info(f"No collar deployments found between {start_date} and {end_date}")
        st.write("Try adjusting the date range or check if deployments are properly recorded in EarthRanger.")
        return
    
    st.success(f"Found {len(subjects_df)} collar deployments in selected period")
    
    # Display deployments summary
    st.subheader("🏷️ Deployments Summary")
    
    summary_cols = ['name', 'deployment_date', 'subject_subtype']
    display_df = subjects_df[summary_cols].copy()
    display_df.columns = ['Subject Name', 'Deployment Date', 'Subject Type']
    st.dataframe(display_df, use_container_width=True)
    
    # Collect location data for each subject (48 hours post-deployment)
    st.subheader("📍 2-Day Location Tracking")
    
    locations_data = {}
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, (_, subject) in enumerate(subjects_df.iterrows()):
        subject_id = subject['id']
        subject_name = subject['name']
        deployment_datetime = subject['deployment_datetime']
        
        status_text.text(f"Loading locations for {subject_name}...")
        
        # Get locations for 48 hours after deployment
        end_datetime = deployment_datetime + timedelta(hours=48)
        locations_df = get_subject_locations(er, subject_id, deployment_datetime, end_datetime)
        
        if not locations_df.empty:
            locations_data[subject_id] = locations_df
        
        progress_bar.progress((i + 1) / len(subjects_df))
    
    progress_bar.empty()
    status_text.empty()
    
    # Check if we have any location data
    subjects_with_data = [sid for sid, df in locations_data.items() if not df.empty]
    
    if not subjects_with_data:
        st.warning("No location data found for any subjects in the 48 hours following deployment.")
        st.write("This could mean:")
        st.write("- Collars haven't started transmitting yet")
        st.write("- Data transmission issues")
        st.write("- Deployments are too recent (data may not be synced yet)")
        return
    
    st.success(f"Location data found for {len(subjects_with_data)} out of {len(subjects_df)} deployed subjects")
    
    # Create and display map
    st.subheader("🗺️ Deployment Locations & Movement Tracks")
    map_fig = create_deployment_map(subjects_df, locations_data)
    st.plotly_chart(map_fig, use_container_width=True)
    
    # Create and display timeline
    st.subheader("⏱️ Data Collection Timeline")
    timeline_fig = create_timeline_chart(subjects_df, locations_data)
    st.plotly_chart(timeline_fig, use_container_width=True)
    
    # Movement summary statistics
    st.subheader("📊 Movement Summary")
    summary_df = create_movement_summary(subjects_df, locations_data)
    if not summary_df.empty:
        st.dataframe(summary_df, use_container_width=True)
    
    # Data details
    with st.expander("📋 Detailed Location Data"):
        for subject_id, df in locations_data.items():
            if not df.empty:
                subject_name = subjects_df[subjects_df['id'] == subject_id]['name'].iloc[0]
                st.write(f"**{subject_name}** ({len(df)} locations)")
                
                # Show subset of columns for display
                display_cols = ['recorded_at', 'location_lat', 'location_long']
                available_cols = [col for col in display_cols if col in df.columns]
                
                if available_cols:
                    display_data = df[available_cols].copy()
                    display_data['recorded_at'] = display_data['recorded_at'].dt.strftime('%Y-%m-%d %H:%M:%S')
                    st.dataframe(display_data.head(10), use_container_width=True)
                    
                    if len(df) > 10:
                        st.write(f"... and {len(df) - 10} more locations")
                
                st.write("---")

if __name__ == "__main__":
    main()