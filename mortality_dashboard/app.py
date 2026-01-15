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

# Custom CSS for better styling
st.markdown("""
<style>
    .logo-title {
        color: #DC143C;
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
        border-left: 4px solid #DC143C;
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
    if 'server_url' not in st.session_state:
        st.session_state.server_url = "https://twiga.pamdas.org"

def authenticate_earthranger():
    """Handle EarthRanger authentication using ecoscope"""
    if not ECOSCOPE_AVAILABLE:
        st.error("❌ Ecoscope package is required but not available. Please install ecoscope.")
        return
        
    st.header("🔐 EarthRanger Authentication")
    
    st.write("Enter your EarthRanger credentials to access the mortality dashboard:")
    
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
                er_io = EarthRangerIO(
                    server=st.session_state.server_url,
                    username=username,
                    password=password
                )
                
                st.success("✅ Successfully authenticated with EarthRanger!")
                st.session_state.authenticated = True
                st.session_state.username = username
                st.session_state.password = password
                
                st.rerun()
                
        except Exception as e:
            st.error(f"❌ Authentication failed: {str(e)}")
            st.info("💡 Please check your username and password")

@st.cache_data(ttl=1800, show_spinner=False)  # Cache for 30 minutes
def get_mortality_events(start_date=None, end_date=None, _debug=False):
    """Fetch mortality events from EarthRanger using ecoscope"""
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
        kwargs = {
            'event_category': 'veterinary',
            'include_details': True,
            'include_notes': True,
            'max_results': 1000,
            'drop_null_geometry': False
        }
        
        # Add date filters if provided
        if start_date:
            if isinstance(start_date, date):
                since_str = start_date.strftime('%Y-%m-%dT00:00:00Z')
            else:
                since_str = str(start_date)
            kwargs['since'] = since_str
            if _debug:
                st.write(f"Debug: since = {since_str}")
                
        if end_date:
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
        
        # Convert GeoDataFrame to regular DataFrame
        df = pd.DataFrame(gdf_events.drop(columns='geometry', errors='ignore'))
        
        # Filter by event_type for mortality events
        if 'event_type' in df.columns:
            df = df[df['event_type'] == 'giraffe_mortality']
        
        if df.empty:
            return pd.DataFrame()
        
        # Process the data
        if 'time' in df.columns:
            df['time'] = pd.to_datetime(df['time'])
            df['date'] = df['time'].dt.date
            df['year'] = df['time'].dt.year
            df['month'] = df['time'].dt.month
            df['month_name'] = df['time'].dt.strftime('%B')
            
            # Apply client-side date filtering
            if start_date is not None:
                df = df[df['date'] >= start_date]
            if end_date is not None:
                df = df[df['date'] <= end_date]
            
            if _debug and not df.empty:
                st.write(f"Debug: After date filtering, {len(df)} events remain")
                st.write(f"Debug: Date range in data: {df['date'].min()} to {df['date'].max()}")
        
        # Add location information if geometry was available
        if not gdf_events.empty and 'geometry' in gdf_events.columns:
            gdf_events['latitude'] = gdf_events.geometry.apply(lambda x: x.y if x and hasattr(x, 'y') else None)
            gdf_events['longitude'] = gdf_events.geometry.apply(lambda x: x.x if x and hasattr(x, 'x') else None)
            df['latitude'] = gdf_events['latitude']
            df['longitude'] = gdf_events['longitude']
        
        return df
        
    except Exception as e:
        st.error(f"Error fetching mortality events: {str(e)}")
        return pd.DataFrame()

def parse_mortality_cause(mortality_cause):
    """Parse giraffe_mortality_cause field into type (natural/unnatural) and cause
    
    Args:
        mortality_cause: String like 'natural_predation' or 'unnatural_immobilisation'
    
    Returns:
        tuple: (type, cause) e.g. ('Natural', 'Predation')
    """
    if not mortality_cause or mortality_cause == 'Unknown':
        return 'Unknown', 'Unknown'
    
    mortality_str = str(mortality_cause).lower()
    
    # Split by underscore
    if '_' in mortality_str:
        parts = mortality_str.split('_', 1)  # Split only on first underscore
        mortality_type = parts[0].title()  # Natural or Unnatural
        cause = parts[1].replace('_', ' ').title()  # Predation, Immobilisation, etc.
        return mortality_type, cause
    
    # If no underscore, treat whole thing as cause with unknown type
    return 'Unknown', mortality_str.title()

def mortality_dashboard():
    """Main mortality dashboard interface"""
    
    # Date filter controls
    st.subheader("📅 Filters")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        start_date = st.date_input(
            "Start Date",
            value=date.today() - timedelta(days=365),
            help="Select the earliest date for mortality events"
        )
    
    with col2:
        end_date = st.date_input(
            "End Date", 
            value=date.today(),
            help="Select the latest date for mortality events"
        )
    
    # Fetch all events to get available filters
    with st.spinner("🔄 Loading mortality data..."):
        all_events = get_mortality_events(start_date, end_date)
    
    # Extract unique countries and mortality types
    all_countries = ['All Countries']
    all_species = ['All Species']
    all_types = ['All Types', 'Natural', 'Unnatural', 'Unknown']  # Mortality types
    
    if not all_events.empty:
        for idx, event in all_events.iterrows():
            event_details = event.get('event_details', {})
            if isinstance(event_details, dict):
                # Country
                country = event_details.get('country')
                if country:
                    if isinstance(country, dict):
                        country = country.get('name') or country.get('country') or country.get('code')
                    if country:
                        country_upper = str(country).upper()
                        if country_upper not in all_countries:
                            all_countries.append(country_upper)
                
                # Species (coded as gir_species)
                species = event_details.get('gir_species') or event_details.get('species')
                if species:
                    if isinstance(species, dict):
                        species = species.get('name') or species.get('species')
                    if species:
                        species_title = str(species).title()
                        if species_title not in all_species:
                            all_species.append(species_title)
    
    with col3:
        selected_country = st.selectbox(
            "Country",
            options=all_countries,
            index=0,
            help="Filter by country"
        )
    
    with col4:
        if st.button("🔄 Refresh Data", type="primary"):
            get_mortality_events.clear()
            st.rerun()
    
    # Additional filters
    col1, col2 = st.columns(2)
    
    with col1:
        selected_type = st.selectbox(
            "Mortality Type",
            options=all_types,
            index=0,
            help="Filter by natural or unnatural mortality"
        )
    
    with col2:
        selected_species = st.selectbox(
            "Species",
            options=all_species,
            index=0,
            help="Filter by species"
        )
    
    # Validate date range
    if start_date > end_date:
        st.error("❌ Start date cannot be after end date")
        return
    
    # Apply filters
    df_events = all_events.copy()
    
    # Mortality type filter (Natural/Unnatural)
    if selected_type != 'All Types' and not df_events.empty:
        filtered_events = []
        for idx, event in df_events.iterrows():
            event_details = event.get('event_details', {})
            if isinstance(event_details, dict):
                # Check both new and old field names for backward compatibility
                mortality_cause = event_details.get('giraffe_mortality_cause') or event_details.get('mortality_cause')
                if mortality_cause:
                    mortality_type, cause = parse_mortality_cause(mortality_cause)
                    if mortality_type == selected_type:
                        filtered_events.append(event)
        df_events = pd.DataFrame(filtered_events) if filtered_events else pd.DataFrame()
    
    # Country filter
    if selected_country != 'All Countries' and not df_events.empty:
        filtered_events = []
        for idx, event in df_events.iterrows():
            event_details = event.get('event_details', {})
            if isinstance(event_details, dict):
                country = event_details.get('country')
                if isinstance(country, dict):
                    country = country.get('name') or country.get('country') or country.get('code')
                if country and str(country).upper() == selected_country.upper():
                    filtered_events.append(event)
        df_events = pd.DataFrame(filtered_events) if filtered_events else pd.DataFrame()
    
    # Species filter
    if selected_species != 'All Species' and not df_events.empty:
        filtered_events = []
        for idx, event in df_events.iterrows():
            event_details = event.get('event_details', {})
            if isinstance(event_details, dict):
                species = event_details.get('gir_species') or event_details.get('species')
                if isinstance(species, dict):
                    species = species.get('name') or species.get('species')
                if species and str(species).title() == selected_species:
                    filtered_events.append(event)
        df_events = pd.DataFrame(filtered_events) if filtered_events else pd.DataFrame()
    
    if df_events.empty:
        st.warning("No mortality events found for the selected filters.")
        
        # Debug option
        if st.checkbox("🔍 Debug: Show available veterinary event types", value=False):
            with st.spinner("Fetching all veterinary events for debugging..."):
                try:
                    er_io = EarthRangerIO(
                        server=st.session_state.server_url,
                        username=st.session_state.username,
                        password=st.session_state.password
                    )
                    
                    debug_kwargs = {
                        'event_category': 'veterinary',
                        'max_results': 100,
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
                        else:
                            st.write("No 'event_type' column found in veterinary events")
                    else:
                        st.write("No veterinary events found in the selected date range")
                        
                except Exception as e:
                    st.error(f"Debug error: {str(e)}")
        
        st.info("""
        **Looking for mortality events with:**
        - event_category='veterinary'
        - event_type='giraffe_mortality'
        
        If no events are found, please verify the event type exists in EarthRanger.
        """)
        return
    
    # Summary metrics
    st.subheader("📊 Summary Statistics")
    
    # Custom color palette (more diverse colors)
    org_colors = ['#DC143C', '#FF8C00', '#32CD32', '#1E90FF', '#9370DB', '#FFD700', '#20B2AA', '#FF69B4', '#8B4513', '#708090']
    
    # Calculate metrics
    total_mortalities = len(df_events)
    country_counts = {}
    cause_counts = {}
    species_counts = {}
    sex_counts = {'Male': 0, 'Female': 0, 'Unknown': 0}
    classification_counts = {'Natural': 0, 'Unnatural': 0, 'Unknown': 0}
    
    for idx, event in df_events.iterrows():
        event_details = event.get('event_details', {})
        if isinstance(event_details, dict):
            # Country
            country = event_details.get('country')
            if country:
                if isinstance(country, dict):
                    country = country.get('name') or country.get('country') or country.get('code')
                country_str = str(country).upper() if country else 'Unknown'
                country_counts[country_str] = country_counts.get(country_str, 0) + 1
            else:
                country_counts['Unknown'] = country_counts.get('Unknown', 0) + 1
            
            # Cause (from giraffe_mortality_cause field)
            mortality_cause = event_details.get('giraffe_mortality_cause') or event_details.get('mortality_cause') or 'Unknown'
            mortality_type, cause = parse_mortality_cause(mortality_cause)
            cause_counts[cause] = cause_counts.get(cause, 0) + 1
            
            # Classification (natural/unnatural)
            classification_counts[mortality_type] = classification_counts.get(mortality_type, 0) + 1
            
            # Species (gir_species field)
            species = event_details.get('gir_species') or event_details.get('species') or 'Unknown'
            if isinstance(species, dict):
                species = species.get('name') or species.get('species') or 'Unknown'
            species_str = str(species).title() if species else 'Unknown'
            species_counts[species_str] = species_counts.get(species_str, 0) + 1
            
            # Sex (gir_sex field)
            sex = event_details.get('gir_sex') or event_details.get('sex', 'Unknown')
            if sex and str(sex).lower() in ['male', 'm']:
                sex_counts['Male'] += 1
            elif sex and str(sex).lower() in ['female', 'f']:
                sex_counts['Female'] += 1
            else:
                sex_counts['Unknown'] += 1
    
    # Key metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Mortalities", total_mortalities)
    with col2:
        st.metric("Natural", classification_counts.get('Natural', 0))
    with col3:
        st.metric("Unnatural", classification_counts.get('Unnatural', 0))
    with col4:
        st.metric("Countries", len([k for k in country_counts.keys() if k != 'Unknown']))
    with col5:
        st.metric("Causes", len([k for k in cause_counts.keys() if k != 'Unknown']))
    
    st.markdown("---")
    
    # Natural vs Unnatural split
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Natural/Unnatural classification
        classification_df = pd.DataFrame(
            [(k, v) for k, v in classification_counts.items() if v > 0],
            columns=['Classification', 'Count']
        )
        if not classification_df.empty:
            fig_class = px.pie(
                classification_df,
                values='Count',
                names='Classification',
                title="Natural vs Unnatural",
                color='Classification',
                color_discrete_map={'Natural': '#2E8B57', 'Unnatural': '#DC143C', 'Unknown': '#999999'},
                height=350
            )
            fig_class.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_class, use_container_width=True)
    
    with col2:
        if species_counts:
            species_df = pd.DataFrame(list(species_counts.items()), columns=['Species', 'Count'])
            species_df = species_df.sort_values('Count', ascending=False)
            fig_species = px.pie(
                species_df,
                values='Count',
                names='Species',
                title="Species Distribution",
                color_discrete_sequence=org_colors,
                height=350
            )
            fig_species.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_species, use_container_width=True)
    
    with col3:
        sex_df = pd.DataFrame(list(sex_counts.items()), columns=['Sex', 'Count'])
        sex_df = sex_df[sex_df['Count'] > 0]  # Only show non-zero
        if not sex_df.empty:
            fig_sex = px.pie(
                sex_df,
                values='Count',
                names='Sex',
                title="Sex Distribution",
                color_discrete_map={'Male': '#8B0000', 'Female': '#DC143C', 'Unknown': '#999999'},
                height=350
            )
            fig_sex.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_sex, use_container_width=True)
    
    st.markdown("---")
    
    # Temporal trends - Line chart for causes over time
    st.subheader("📈 Mortality Trends Over Time")
    
    # Check if we have multiple months or years of data
    if 'time' in df_events.columns and len(df_events) > 0:
        # Create temporal data
        temporal_data = []
        for idx, event in df_events.iterrows():
            event_details = event.get('event_details', {})
            if isinstance(event_details, dict):
                # Check both new and old field names for backward compatibility
                mortality_cause = event_details.get('giraffe_mortality_cause') or event_details.get('mortality_cause')
                if mortality_cause:
                    mortality_type, cause = parse_mortality_cause(mortality_cause)
                    temporal_data.append({
                        'date': event['time'],
                        'year': event['time'].year,
                        'month': event['time'].strftime('%Y-%m'),
                        'cause': cause,
                        'type': mortality_type
                    })
        
        if temporal_data:
            temp_df = pd.DataFrame(temporal_data)
            
            # Determine aggregation level based on date range
            unique_years = temp_df['year'].nunique()
            unique_months = temp_df['month'].nunique()
            
            if unique_years > 1 or unique_months > 6:
                # Use monthly aggregation
                temp_summary = temp_df.groupby(['month', 'cause']).size().reset_index(name='count')
                temp_summary = temp_summary.sort_values('month')
                x_label = 'Month'
                x_col = 'month'
                
                fig_temporal = px.line(
                    temp_summary,
                    x=x_col,
                    y='count',
                    color='cause',
                    markers=True,
                    title=f"Mortality Causes Over Time ({temp_df['month'].min()} to {temp_df['month'].max()})",
                    labels={'count': 'Number of Events', 'month': 'Month', 'cause': 'Cause'},
                    color_discrete_sequence=org_colors,
                    height=400
                )
                fig_temporal.update_xaxes(tickangle=-45)
                st.plotly_chart(fig_temporal, use_container_width=True)
            else:
                # For shorter periods, show a simple bar chart
                temp_summary = temp_df.groupby(['month', 'cause']).size().reset_index(name='count')
                fig_temporal = px.bar(
                    temp_summary,
                    x='month',
                    y='count',
                    color='cause',
                    title="Mortality Causes Distribution",
                    labels={'count': 'Number of Events', 'month': 'Period', 'cause': 'Cause'},
                    color_discrete_sequence=org_colors,
                    height=400
                )
                st.plotly_chart(fig_temporal, use_container_width=True)
    
    st.markdown("---")
    
    # Country and Cause visualizations
    col1, col2 = st.columns(2)
    
    org_colors = ['#DC143C', '#FF8C00', '#32CD32', '#1E90FF', '#9370DB', '#FFD700', '#20B2AA', '#FF69B4', '#8B4513', '#708090']
    
    with col1:
        if country_counts:
            country_df = pd.DataFrame(list(country_counts.items()), columns=['Country', 'Count'])
            country_df = country_df.sort_values('Count', ascending=False)
            fig_country = px.bar(
                country_df,
                x='Count',
                y='Country',
                orientation='h',
                title="Mortalities by Country",
                color='Count',
                color_continuous_scale=['#DC143C', '#8B0000'],
                height=400
            )
            fig_country.update_layout(yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig_country, use_container_width=True)
    
    with col2:
        if cause_counts:
            cause_df = pd.DataFrame(list(cause_counts.items()), columns=['Cause', 'Count'])
            cause_df = cause_df.sort_values('Count', ascending=False)
            fig_cause = px.pie(
                cause_df,
                values='Count',
                names='Cause',
                title="Mortality Causes",
                color_discrete_sequence=org_colors,
                height=400
            )
            fig_cause.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_cause, use_container_width=True)
    
    # Map visualization
    st.subheader("🗺️ Mortality Locations Map")
    
    events_with_location = []
    for idx, event in df_events.iterrows():
        event_details = event.get('event_details', {})
        if isinstance(event_details, dict):
            # Check for location in event_details
            location = event_details.get('location')
            if isinstance(location, dict) and location.get('latitude') and location.get('longitude'):
                events_with_location.append(event)
            # Also check for direct lat/lon fields
            elif event.get('latitude') and event.get('longitude'):
                events_with_location.append(event)
    
    if events_with_location:
        fig_map = go.Figure()
        
        # Simple color map for mortality types (not causes)
        type_color_map = {
            'Natural': '#DB580F',      # Orange (GCF brand color)
            'Unnatural': '#5D4037',    # Dark brown
            'Unknown': '#808080'       # Grey
        }
        
        # Track which types we've added to legend
        legend_items = set()
        
        for event_idx, event in enumerate(events_with_location):
            event_details = event.get('event_details', {})
            
            # Get coordinates
            location = event_details.get('location') if isinstance(event_details, dict) else {}
            if isinstance(location, dict):
                lat = location.get('latitude')
                lon = location.get('longitude')
                location_name = location.get('name', 'Unknown')
            else:
                lat = event.get('latitude')
                lon = event.get('longitude')
                location_name = event_details.get('location_name', 'Unknown') if isinstance(event_details, dict) else 'Unknown'
            
            if lat and lon:
                try:
                    lat_float, lon_float = float(lat), float(lon)
                    
                    # Get event info for hover
                    country = 'Unknown'
                    mortality_type = 'Unknown'
                    cause = 'Unknown'
                    species = 'Unknown'
                    
                    if isinstance(event_details, dict):
                        country_val = event_details.get('country')
                        if isinstance(country_val, dict):
                            country = country_val.get('name') or country_val.get('code') or 'Unknown'
                        elif country_val:
                            country = str(country_val)
                        
                        # Parse giraffe_mortality_cause (check both new and old field names)
                        mortality_cause = event_details.get('giraffe_mortality_cause') or event_details.get('mortality_cause')
                        if mortality_cause:
                            mortality_type, cause = parse_mortality_cause(mortality_cause)
                        
                        # Species (gir_species)
                        species_val = event_details.get('gir_species') or event_details.get('species')
                        if isinstance(species_val, dict):
                            species = species_val.get('name') or 'Unknown'
                        elif species_val:
                            species = str(species_val)
                    
                    # Get color for this mortality type
                    marker_color = type_color_map.get(mortality_type, '#808080')
                    
                    # Show in legend only once per type
                    show_in_legend = mortality_type not in legend_items
                    
                    fig_map.add_trace(go.Scattermapbox(
                        lat=[lat_float],
                        lon=[lon_float],
                        mode='markers',
                        marker=dict(
                            size=12,
                            color=marker_color,
                            opacity=0.7
                        ),
                        name=mortality_type,
                        showlegend=show_in_legend,
                        hovertemplate=f"<b>Location:</b> {location_name}<br>" +
                                    f"<b>Country:</b> {country}<br>" +
                                    f"<b>Species:</b> {species}<br>" +
                                    f"<b>Type:</b> {mortality_type}<br>" +
                                    f"<b>Cause:</b> {cause}<br>" +
                                    f"<b>Date:</b> {event['time'].strftime('%Y-%m-%d')}<extra></extra>"
                    ))
                    
                    # Mark this type as added to legend
                    legend_items.add(mortality_type)
                except (ValueError, TypeError):
                    pass
        
        fig_map.update_layout(
            mapbox=dict(
                style="open-street-map",
                zoom=2.5,
                center=dict(lat=0, lon=20)
            ),
            height=600,
            showlegend=True
        )
        
        st.plotly_chart(fig_map, use_container_width=True)
    else:
        st.info("No location data available for mortality events.")
    
    # Detailed event list
    st.subheader("📋 Detailed Event List")
    
    export_data = []
    for idx, event in df_events.iterrows():
        event_details = event.get('event_details', {})
        
        row = {
            'Date & Time': event['time'].strftime('%Y-%m-%d %H:%M') if 'time' in event else 'N/A',
            'Serial Number': event.get('serial_number', 'N/A'),
            'Country': '',
            'Location': '',
            'Species': '',
            'Mortality Type': '',
            'Mortality Cause': '',
            'Sex': '',
            'Age Class': '',
            'Subject ID': '',
            'Latitude': '',
            'Longitude': '',
            'Notes': ''
        }
        
        if isinstance(event_details, dict):
            # Country
            country = event_details.get('country')
            if isinstance(country, dict):
                row['Country'] = country.get('name') or country.get('code') or ''
            elif country:
                row['Country'] = str(country)
            
            # Location
            location = event_details.get('location')
            if isinstance(location, dict):
                row['Location'] = location.get('name', '')
                row['Latitude'] = location.get('latitude', '')
                row['Longitude'] = location.get('longitude', '')
            else:
                row['Location'] = event_details.get('location_name', '')
            
            # Species (gir_species)
            species = event_details.get('gir_species') or event_details.get('species')
            if isinstance(species, dict):
                row['Species'] = species.get('name') or ''
            elif species:
                row['Species'] = str(species)
            
            # Parse giraffe_mortality_cause into separate fields (check both new and old field names)
            mortality_cause = event_details.get('giraffe_mortality_cause') or event_details.get('mortality_cause')
            if mortality_cause:
                mortality_type, cause = parse_mortality_cause(mortality_cause)
                row['Mortality Type'] = mortality_type
                row['Mortality Cause'] = cause
            else:
                row['Mortality Type'] = ''
                row['Mortality Cause'] = ''
            
            row['Sex'] = event_details.get('gir_sex') or event_details.get('sex', '')
            row['Age Class'] = event_details.get('gir_age') or event_details.get('age_class', '')
            row['Subject ID'] = event_details.get('subject_id', '')
            
            # Notes from event_details
            notes = event_details.get('notes', '')
            if notes:
                row['Notes'] = str(notes)
        
        # Also check for direct lat/lon on event
        if not row['Latitude'] and event.get('latitude'):
            row['Latitude'] = event.get('latitude')
        if not row['Longitude'] and event.get('longitude'):
            row['Longitude'] = event.get('longitude')
        
        export_data.append(row)
    
    export_df = pd.DataFrame(export_data)
    st.dataframe(export_df, use_container_width=True)

def main():
    """Main application entry point"""
    init_session_state()
    
    # Header with logo
    with st.container():
        logo_displayed = False
        
        # Get the absolute path to the logo file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(current_dir, '..', 'logo.png')
        
        if os.path.exists(logo_path):
            try:
                col1, col2, col3 = st.columns([1, 2, 1])
                with col2:
                    st.image(logo_path, width=300)
                    st.markdown('<div class="logo-title" style="text-align: center;">Mortality Dashboard</div>', unsafe_allow_html=True)
                    st.markdown('<div class="logo-subtitle" style="text-align: center;">Wildlife Mortality Event Monitoring</div>', unsafe_allow_html=True)
                    logo_displayed = True
            except Exception as e:
                st.error(f"Error loading logo: {str(e)}")
        
        # Fallback header without logo
        if not logo_displayed:
            st.title("☠️ Mortality Dashboard")
            st.markdown("Wildlife mortality event monitoring and analytics")
    
    # Authentication check
    if not st.session_state.authenticated:
        authenticate_earthranger()
        return
    
    # Sidebar
    st.sidebar.title("Navigation")
    
    # Authentication status
    st.sidebar.markdown("### 🔐 Authentication ✅")
    if st.session_state.get('username'):
        st.sidebar.write(f"**User:** {st.session_state.username}")
    
    # Show dashboard
    mortality_dashboard()
    
    # Sidebar options
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔧 Options")
    
    if st.sidebar.button("🔄 Refresh Data"):
        get_mortality_events.clear()
        st.rerun()
    
    if st.sidebar.button("🔓 Logout"):
        for key in ['authenticated', 'username', 'password']:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

if __name__ == "__main__":
    main()
