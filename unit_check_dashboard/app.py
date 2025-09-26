"""
Unit Check Dashboard
Simple monitoring for tracking device units - 7-day activity, battery, and location
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import requests
import os
from ecoscope.io.earthranger import EarthRangerIO

# Organization color palette for consistency
ORG_COLORS = ['#DB580F', '#3E0000', '#CCCCCC', '#999999', '#8B4513', '#D2691E', '#CD853F', '#F4A460']

# Configuration - can be overridden by environment variables
EARTHRANGER_SERVER = os.getenv('EARTHRANGER_SERVER', 'https://twiga.pamdas.org')

#### ER AUTHENTICATION ###############################################
def er_login(username, password):
    """Test EarthRanger credentials"""
    try:
        er = EarthRangerIO(
            server=EARTHRANGER_SERVER,
            username=username,
            password=password
        )
        # Try a simple call to check credentials
        er.get_subjects(limit=1)
        return True
    except Exception:
        return False

def authenticate():
    """Handle user authentication"""
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
    if "username" not in st.session_state:
        st.session_state["username"] = ""
    if "password" not in st.session_state:
        st.session_state["password"] = ""

    if not st.session_state["authenticated"]:
        st.title("🔍 Unit Check Dashboard")
        st.markdown("*Login to monitor tracking device units*")
        
        username = st.text_input("EarthRanger Username")
        password = st.text_input("EarthRanger Password", type="password")
        
        if st.button("Login"):
            if er_login(username, password):
                st.session_state["authenticated"] = True
                st.session_state["username"] = username
                st.session_state["password"] = password
                st.success("Login successful!")
                st.rerun()
            else:
                st.error("Invalid credentials. Please try again.")
        st.stop()

#### DATA FUNCTIONS ###############################################
@st.cache_data(ttl=1800)  # Cache for 30 minutes
def get_sources_by_manufacturer():
    """Get all tracking device sources grouped by manufacturer"""
    try:
        er = EarthRangerIO(
            server=EARTHRANGER_SERVER,
            username=st.session_state["username"],
            password=st.session_state["password"]
        )
        sources_df = er.get_sources()
        
        if sources_df.empty:
            return {}
        
        # Group by manufacturer
        sources_dict = {}
        for _, source in sources_df.iterrows():
            manufacturer = source.get('manufacturer', 'Unknown')
            if manufacturer not in sources_dict:
                sources_dict[manufacturer] = []
            
            sources_dict[manufacturer].append({
                'id': source.get('id'),
                'name': source.get('name', 'Unnamed'),
                'model': source.get('model', 'Unknown Model'),
                'is_active': source.get('is_active', False)
            })
        
        return sources_dict
    except Exception as e:
        st.error(f"Error fetching sources: {str(e)}")
        return {}

@st.cache_data(ttl=900)  # Cache for 15 minutes
def get_source_observations(source_id, days=7):
    """Get observations for a source over the last N days"""
    try:
        er = EarthRangerIO(
            server=EARTHRANGER_SERVER,
            username=st.session_state["username"],
            password=st.session_state["password"]
        )
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        observations_df = er.get_observations(
            source_id=source_id,
            start=start_date,
            end=end_date
        )
        
        if observations_df.empty:
            return pd.DataFrame()
        
        # Process observations
        observations_df['recorded_at'] = pd.to_datetime(observations_df['recorded_at'])
        observations_df = observations_df.sort_values('recorded_at')
        
        return observations_df
    except Exception as e:
        st.error(f"Error fetching observations for source {source_id}: {str(e)}")
        return pd.DataFrame()

#### VISUALIZATION FUNCTIONS ###############################################
def create_activity_chart(observations_df, unit_name):
    """Create daily activity chart"""
    if observations_df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16, color="gray")
        )
        fig.update_layout(
            title=f"7-Day Activity - {unit_name}",
            xaxis_title="Date",
            yaxis_title="Number of Observations",
            template="plotly_white"
        )
        return fig
    
    # Group by date
    daily_counts = observations_df.groupby(observations_df['recorded_at'].dt.date).size().reset_index()
    daily_counts.columns = ['date', 'observations']
    
    fig = px.bar(
        daily_counts,
        x='date',
        y='observations',
        title=f"7-Day Activity - {unit_name}",
        color='observations',
        color_continuous_scale=[[0, ORG_COLORS[2]], [1, ORG_COLORS[0]]]
    )
    
    fig.update_layout(
        template="plotly_white",
        xaxis_title="Date",
        yaxis_title="Number of Observations",
        showlegend=False
    )
    
    return fig

def create_battery_chart(observations_df, unit_name):
    """Create battery level chart over time"""
    if observations_df.empty or 'additional' not in observations_df.columns:
        fig = go.Figure()
        fig.add_annotation(
            text="No battery data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16, color="gray")
        )
        fig.update_layout(
            title=f"7-Day Battery Level - {unit_name}",
            xaxis_title="Date",
            yaxis_title="Battery Level (%)",
            template="plotly_white"
        )
        return fig
    
    # Extract battery data from additional field
    battery_data = []
    for _, row in observations_df.iterrows():
        additional = row.get('additional', {})
        if isinstance(additional, dict):
            battery = additional.get('voltage') or additional.get('battery') or additional.get('battery_level')
            if battery is not None:
                try:
                    battery_value = float(battery)
                    # Convert voltage to percentage if needed (rough approximation)
                    if battery_value > 10:  # Assume it's voltage, not percentage
                        battery_value = min(100, max(0, (battery_value - 3.0) / 1.2 * 100))
                    battery_data.append({
                        'recorded_at': row['recorded_at'],
                        'battery_level': battery_value
                    })
                except (ValueError, TypeError):
                    continue
    
    if not battery_data:
        fig = go.Figure()
        fig.add_annotation(
            text="No battery data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16, color="gray")
        )
        fig.update_layout(
            title=f"7-Day Battery Level - {unit_name}",
            xaxis_title="Date",
            yaxis_title="Battery Level (%)",
            template="plotly_white"
        )
        return fig
    
    battery_df = pd.DataFrame(battery_data)
    
    fig = px.line(
        battery_df,
        x='recorded_at',
        y='battery_level',
        title=f"7-Day Battery Level - {unit_name}",
        color_discrete_sequence=[ORG_COLORS[0]]
    )
    
    fig.update_layout(
        template="plotly_white",
        xaxis_title="Date & Time",
        yaxis_title="Battery Level (%)",
        yaxis=dict(range=[0, 100])
    )
    
    # Add horizontal lines for battery thresholds
    fig.add_hline(y=20, line_dash="dash", line_color="red", annotation_text="Low Battery (20%)")
    fig.add_hline(y=50, line_dash="dot", line_color="orange", annotation_text="Medium (50%)")
    
    return fig

def create_location_map(observations_df, unit_name):
    """Create map showing unit locations over the last 7 days"""
    if observations_df.empty or 'location' not in observations_df.columns:
        fig = go.Figure()
        fig.add_annotation(
            text="No location data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16, color="gray")
        )
        fig.update_layout(
            title=f"7-Day Location Track - {unit_name}",
            template="plotly_white"
        )
        return fig
    
    # Extract coordinates
    locations = []
    for _, row in observations_df.iterrows():
        location = row.get('location')
        if location and isinstance(location, dict):
            coords = location.get('coordinates')
            if coords and len(coords) >= 2:
                locations.append({
                    'longitude': coords[0],
                    'latitude': coords[1],
                    'recorded_at': row['recorded_at'],
                    'date_str': row['recorded_at'].strftime('%Y-%m-%d %H:%M')
                })
    
    if not locations:
        fig = go.Figure()
        fig.add_annotation(
            text="No location data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16, color="gray")
        )
        fig.update_layout(
            title=f"7-Day Location Track - {unit_name}",
            template="plotly_white"
        )
        return fig
    
    locations_df = pd.DataFrame(locations)
    
    # Create map
    fig = px.scatter_mapbox(
        locations_df,
        lat='latitude',
        lon='longitude',
        hover_name='date_str',
        title=f"7-Day Location Track - {unit_name}",
        mapbox_style='open-street-map',
        color_discrete_sequence=[ORG_COLORS[0]],
        size_max=10
    )
    
    # Add line connecting points
    fig.add_trace(
        go.Scattermapbox(
            lat=locations_df['latitude'],
            lon=locations_df['longitude'],
            mode='lines',
            line=dict(color=ORG_COLORS[1], width=2),
            name='Track',
            showlegend=False
        )
    )
    
    # Center map on data
    fig.update_layout(
        mapbox=dict(
            center=dict(
                lat=locations_df['latitude'].mean(),
                lon=locations_df['longitude'].mean()
            ),
            zoom=10
        ),
        height=500
    )
    
    return fig

#### MAIN APPLICATION ###############################################
def main():
    """Main application function"""
    st.title("🔍 Unit Check Dashboard")
    st.markdown("*Monitor tracking device units - 7-day activity, battery, and location*")
    
    # Authenticate user
    authenticate()
    
    # Get sources by manufacturer
    with st.spinner("Loading tracking device sources..."):
        sources_by_manufacturer = get_sources_by_manufacturer()
    
    if not sources_by_manufacturer:
        st.warning("No tracking device sources found.")
        return
    
    # Sidebar for manufacturer and unit selection
    st.sidebar.header("Select Units")
    
    # Manufacturer selection with SpoorTrack as default
    manufacturers = list(sources_by_manufacturer.keys())
    default_manufacturer = "SpoorTrack" if "SpoorTrack" in manufacturers else manufacturers[0]
    selected_manufacturer = st.sidebar.selectbox(
        "Manufacturer",
        manufacturers,
        index=manufacturers.index(default_manufacturer) if default_manufacturer in manufacturers else 0
    )
    
    # Unit selection
    available_units = sources_by_manufacturer[selected_manufacturer]
    unit_names = [f"{unit['name']} ({unit['model']})" for unit in available_units]
    
    selected_unit_names = st.sidebar.multiselect(
        "Select Unit(s)",
        unit_names,
        default=unit_names[:1] if unit_names else []  # Select first unit by default
    )
    
    if not selected_unit_names:
        st.info("Please select at least one unit from the sidebar.")
        return
    
    # Get selected unit objects
    selected_units = []
    for unit_name in selected_unit_names:
        for unit in available_units:
            if f"{unit['name']} ({unit['model']})" == unit_name:
                selected_units.append(unit)
                break
    
    # Display information for each selected unit
    for unit in selected_units:
        st.header(f"📡 {unit['name']}")
        
        # Status indicator
        status_color = "🟢" if unit['is_active'] else "🔴"
        st.markdown(f"**Status:** {status_color} {'Active' if unit['is_active'] else 'Inactive'}")
        st.markdown(f"**Model:** {unit['model']}")
        st.markdown(f"**Manufacturer:** {selected_manufacturer}")
        
        # Get observations for this unit
        with st.spinner(f"Loading data for {unit['name']}..."):
            observations_df = get_source_observations(unit['id'], days=7)
        
        if observations_df.empty:
            st.warning(f"No data available for {unit['name']} in the last 7 days.")
            continue
        
        # Display summary stats
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "Total Observations",
                len(observations_df),
                delta=None
            )
        
        with col2:
            if not observations_df.empty:
                last_update = observations_df['recorded_at'].max()
                hours_ago = (datetime.now() - last_update.to_pydatetime()).total_seconds() / 3600
                st.metric(
                    "Last Update",
                    f"{hours_ago:.1f}h ago",
                    delta=None
                )
            else:
                st.metric("Last Update", "No data", delta=None)
        
        with col3:
            if not observations_df.empty:
                daily_avg = len(observations_df) / 7
                st.metric(
                    "Daily Average",
                    f"{daily_avg:.1f} obs",
                    delta=None
                )
            else:
                st.metric("Daily Average", "0 obs", delta=None)
        
        # Create tabs for different views
        tab1, tab2, tab3 = st.tabs(["📊 Activity", "🔋 Battery", "🗺️ Location"])
        
        with tab1:
            activity_fig = create_activity_chart(observations_df, unit['name'])
            st.plotly_chart(activity_fig, use_container_width=True)
        
        with tab2:
            battery_fig = create_battery_chart(observations_df, unit['name'])
            st.plotly_chart(battery_fig, use_container_width=True)
        
        with tab3:
            location_fig = create_location_map(observations_df, unit['name'])
            st.plotly_chart(location_fig, use_container_width=True)
        
        # Add separator between units
        if unit != selected_units[-1]:
            st.divider()

if __name__ == "__main__":
    main()