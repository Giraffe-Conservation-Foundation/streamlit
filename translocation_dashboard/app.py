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
    st.header("🚁 Translocation Dashboard")
    st.markdown("Monitor and analyze giraffe translocation events from EarthRanger")
    
    # Date filter controls
    st.subheader("📅 Date Filters")
    col1, col2, col3 = st.columns(3)
    
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
    
    with col3:
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
    
    # Calculate total individuals translocated
    total_individuals = 0
    for idx, event in df_events.iterrows():
        event_details = event.get('event_details', {})
        if isinstance(event_details, dict):
            # Count individuals translocated (try different field names)
            individuals = (event_details.get('number_of_individuals') or 
                         event_details.get('individuals_count') or 
                         event_details.get('animal_count') or 1)  # Default to 1 if not specified
            try:
                total_individuals += int(individuals)
            except (ValueError, TypeError):
                total_individuals += 1
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Translocation Events", len(df_events))
    
    with col2:
        st.metric("Total Individuals Translocated", total_individuals)
    
    with col3:
        date_range_days = (end_date - start_date).days + 1
        st.metric("Date Range (Days)", date_range_days)
    
    # Destination country analysis
    st.subheader("🌍 Destination Country Breakdown")
    
    destination_countries = []
    
    for idx, event in df_events.iterrows():
        event_details = event.get('event_details', {})
        if isinstance(event_details, dict):
            # Extract destination country
            dest_country = event_details.get('destination_country') or event_details.get('country') or 'Unknown'
            destination_countries.append(dest_country)
    
    if destination_countries:
        country_counts = pd.Series(destination_countries).value_counts().reset_index()
        country_counts.columns = ['country', 'count']
        
        if len(country_counts) > 0:
            fig_countries = px.pie(
                country_counts,
                values='count',
                names='country',
                title="Translocation Events by Destination Country"
            )
            st.plotly_chart(fig_countries, use_container_width=True)
    
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
                    # Extract origin and destination coordinates
                    origin_lat = event_details.get('origin_latitude') or event_details.get('origin_lat')
                    origin_lon = event_details.get('origin_longitude') or event_details.get('origin_lon')
                    dest_lat = event.get('latitude') or event_details.get('destination_latitude') or event_details.get('destination_lat')
                    dest_lon = event.get('longitude') or event_details.get('destination_longitude') or event_details.get('destination_lon')
                    
                    # Origin location names
                    origin_location = event_details.get('origin_location', 'Unknown Origin')
                    destination_location = event_details.get('destination_location', 'Unknown Destination')
                    
                    # Add origin point if coordinates available
                    if origin_lat and origin_lon:
                        fig_map.add_trace(go.Scattermapbox(
                            lat=[float(origin_lat)],
                            lon=[float(origin_lon)],
                            mode='markers',
                            marker=dict(size=12, color='red', symbol='circle'),
                            text=f"Origin: {origin_location}",
                            name='Origin',
                            showlegend=idx == 0,  # Only show legend for first item
                            hovertemplate="<b>Origin:</b> %{text}<br>" +
                                        "<b>Date:</b> " + event['time'].strftime('%Y-%m-%d') + "<br>" +
                                        "<b>Coordinates:</b> %{lat:.4f}, %{lon:.4f}<extra></extra>"
                        ))
                    
                    # Add destination point if coordinates available
                    if dest_lat and dest_lon:
                        fig_map.add_trace(go.Scattermapbox(
                            lat=[float(dest_lat)],
                            lon=[float(dest_lon)],
                            mode='markers',
                            marker=dict(size=12, color='green', symbol='circle'),
                            text=f"Destination: {destination_location}",
                            name='Destination',
                            showlegend=idx == 0,  # Only show legend for first item
                            hovertemplate="<b>Destination:</b> %{text}<br>" +
                                        "<b>Date:</b> " + event['time'].strftime('%Y-%m-%d') + "<br>" +
                                        "<b>Coordinates:</b> %{lat:.4f}, %{lon:.4f}<extra></extra>"
                        ))
                    
                    # Add curved arrow/line between origin and destination
                    if all([origin_lat, origin_lon, dest_lat, dest_lon]):
                        # Create curved path points
                        import numpy as np
                        origin_lat, origin_lon = float(origin_lat), float(origin_lon)
                        dest_lat, dest_lon = float(dest_lat), float(dest_lon)
                        
                        # Calculate midpoint and add curvature
                        mid_lat = (origin_lat + dest_lat) / 2
                        mid_lon = (origin_lon + dest_lon) / 2
                        
                        # Add curvature offset (perpendicular to the line)
                        dx = dest_lon - origin_lon
                        dy = dest_lat - origin_lat
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
                            lat = (1-point)**2 * origin_lat + 2*(1-point)*point * (mid_lat + perp_y) + point**2 * dest_lat
                            lon = (1-point)**2 * origin_lon + 2*(1-point)*point * (mid_lon + perp_x) + point**2 * dest_lon
                            curve_lats.append(lat)
                            curve_lons.append(lon)
                        
                        # Add curved line
                        fig_map.add_trace(go.Scattermapbox(
                            lat=curve_lats,
                            lon=curve_lons,
                            mode='lines',
                            line=dict(width=3, color='blue'),
                            name='Route',
                            showlegend=idx == 0,  # Only show legend for first item
                            hovertemplate=f"<b>Route:</b> {origin_location} → {destination_location}<br>" +
                                        f"<b>Date:</b> {event['time'].strftime('%Y-%m-%d')}<extra></extra>"
                        ))
                        
                        # Add arrow at destination
                        arrow_size = 0.02
                        # Calculate arrow direction
                        arrow_lat = dest_lat - arrow_size * np.cos(np.arctan2(dy, dx))
                        arrow_lon = dest_lon - arrow_size * np.sin(np.arctan2(dy, dx))
                        
                        fig_map.add_trace(go.Scattermapbox(
                            lat=[arrow_lat, dest_lat],
                            lon=[arrow_lon, dest_lon],
                            mode='lines',
                            line=dict(width=5, color='darkblue'),
                            name='Direction',
                            showlegend=False,
                            hoverinfo='skip'
                        ))
            
            # Update map layout
            fig_map.update_layout(
                mapbox=dict(
                    style="open-street-map",
                    zoom=5,
                    center=dict(
                        lat=events_with_location['latitude'].mean() if 'latitude' in events_with_location else 0,
                        lon=events_with_location['longitude'].mean() if 'longitude' in events_with_location else 0
                    )
                ),
                height=600,
                title="Translocation Routes (Red=Origin, Green=Destination, Blue=Route)",
                showlegend=True
            )
            
            st.plotly_chart(fig_map, use_container_width=True)
        else:
            st.info("No location data available for the current events.")
    
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
