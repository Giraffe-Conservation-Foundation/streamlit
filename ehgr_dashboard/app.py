import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from ecoscope.io.earthranger import EarthRangerIO
from pandas import json_normalize, to_datetime
import requests
import os
from pathlib import Path
import geopandas as gpd
from shapely.geometry import LineString

def main():
    """Main function for the EHGR Dashboard"""
    
    # Try to load environment variables from .env file
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        st.sidebar.warning("⚠️ python-dotenv not installed. Using default settings.")
        
    # Force deployment update - timestamp: Sep 26, 2025 - EHGR DASHBOARD IMPLEMENTATION
    # EHGR Dashboard - Complete implementation with satellite mapping - NAMIBIA DATA

    # Configuration - can be overridden by environment variables
    EARTHRANGER_SERVER = os.getenv('EARTHRANGER_SERVER', 'https://twiga.pamdas.org')
    MAPBOX_TOKEN = os.getenv('MAPBOX_TOKEN', '')  # Add your Mapbox token here or in .env file

    #### ER AUTHENTICATION ###############################################
    def er_login(username, password):
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
        
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
    if "username" not in st.session_state:
        st.session_state["username"] = ""
    if "password" not in st.session_state:
        st.session_state["password"] = ""

    if not st.session_state["authenticated"]:
        st.title("🦒 Login to EHGR EarthRanger Dashboard")
        username = st.text_input("EarthRanger Username")
        password = st.text_input("EarthRanger Password", type="password")
        if st.button("Login"):
            if er_login(username, password):
                st.session_state["authenticated"] = True
                st.session_state["username"] = username
                st.session_state["password"] = password
                st.success("Login successful!")
                st.rerun()  # Updated from deprecated st.experimental_rerun()
            else:
                st.error("Invalid credentials. Please try again.")
        st.stop()

    # After this point, only the dashboard is shown!
    username = st.session_state["username"]
    password = st.session_state["password"]

    # Header with logo
    current_dir = Path(__file__).parent.parent
    logo_path = current_dir / "shared" / "logo.png"

    if logo_path.exists():
        try:
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.image(str(logo_path), width=300)
                st.markdown('<div style="text-align: center;"><h1>🦒 EHGR Giraffe Monitoring Dashboard</h1></div>', unsafe_allow_html=True)
                #st.markdown('<div style="text-align: center;"><h3>🇳🇦 Namibia Conservation Tracking</h3></div>', unsafe_allow_html=True)
        except Exception:
            st.title("🦒 EHGR Giraffe Monitoring Dashboard")
    else:
        st.title("🦒 EHGR Giraffe Monitoring Dashboard")

    # Initialise session state flags for on-demand sections
    for _key in ("ehgr_patrols_loaded", "ehgr_camera_loaded", "ehgr_weather_loaded"):
        if _key not in st.session_state:
            st.session_state[_key] = False

    @st.cache_data(ttl=3600)
    def load_monitoring_events(er_username, er_password):
        """Fetch monitoring_nam events once and split into giraffe + priority species dataframes."""
        er = EarthRangerIO(
            server="https://twiga.pamdas.org",
            username=er_username,
            password=er_password
        )
        since = "2024-07-01T00:00:00Z"
        until = datetime.now().strftime("%Y-%m-%dT23:59:59Z")
        try:
            events = er.get_events(
                event_category="monitoring_nam",
                since=since,
                until=until,
                include_details=True,
                include_notes=False
            )
            if events.empty:
                return pd.DataFrame(), pd.DataFrame()
            flat = json_normalize(events.to_dict(orient="records"))
        except Exception as e:
            st.error(f"❌ Error loading monitoring data: {str(e)}")
            return pd.DataFrame(), pd.DataFrame()

        giraffe_df = flat[flat["event_type"] == "giraffe_survey_encounter_nam"].copy()

        priority_types = {
            "Rhino": "rhino_encounter_nam",
            "Lion": "lion_encounter_nam",
            "Cheetah": "cheetah_encounter_nam",
            "Leopard": "leopard_encounter_nam",
        }
        priority_parts = []
        for species_name, etype in priority_types.items():
            subset = flat[flat["event_type"] == etype].copy()
            if not subset.empty:
                subset["species"] = species_name
                priority_parts.append(subset)
        priority_df = pd.concat(priority_parts, ignore_index=True) if priority_parts else pd.DataFrame()

        return giraffe_df, priority_df

    with st.spinner("Loading monitoring data..."):
        df, priority_species_df = load_monitoring_events(username, password)

    if df.empty:
        st.warning("⚠️ No giraffe sighting data available to display")
        st.info("""
        **Possible issues:**
        1. Event category 'monitoring_nam' may not exist
        2. Event type 'giraffe_survey_encounter_nam' may not exist
        3. No data in the specified date range
        """)
        st.stop()

    # Rename columns (similar to NANW but adapted for EHGR structure)
    rename_map = {
        "reported_by.id": "user_id",
        "reported_by.name": "user_name",
        "id": "event_id",
        "event_type": "evt_type",
        "event_category": "evt_category",
        "serial_number": "evt_serial",
        "url": "evt_url",
        "time": "evt_dttm",
        "location.latitude": "lat",
        "location.longitude": "lon",
        "event_details.image_prefix": "evt_imagePrefix",
        "event_details.herd_dire": "evt_herd_dir",
        "event_details.herd_dist": "evt_herd_dist",
        "event_details.herd_size": "evt_herdSize",
        "event_details.herd_notes": "evt_herdNotes",
        "giraffe_id": "evt_girID",
        "giraffe_age": "evt_girAge",
        "giraffe_gsd": "evt_girGSD",
        "giraffe_sex": "evt_girSex",
        "giraffe_dire": "evt_girDire",
        "giraffe_dist": "evt_girDist",
        "giraffe_snar": "evt_girSnare",
        "giraffe_notes": "evt_girNotes",
        "giraffe_right": "evt_girRight",
        "giraffe_left": "evt_gifLeft",
        "giraffe_gsd_loc": "evt_girGSD_loc",
        "giraffe_gsd_sev": "evt_girGSD_sev",
        "event_details.river_system": "evt_riverSystem"
    }

    df = df.rename(columns=rename_map)
    df["evt_dttm"] = pd.to_datetime(df["evt_dttm"])
    df = df.dropna(subset=["evt_dttm"])

    #### DASHBOARD LAYOUT ###############################################

    # Top row: Date filter - separate start and end dates
    st.subheader("Filter Date Range")
    # Clean evt_dttm and drop NaT values
    df["evt_dttm"] = pd.to_datetime(df["evt_dttm"], errors="coerce")
    df = df.dropna(subset=["evt_dttm"])
    
    # Calculate default dates: system date minus 1 month for start, system date for end
    from datetime import timedelta
    default_end_date = datetime.today().date()
    default_start_date = (datetime.today() - timedelta(days=30)).date()
    
    # Get min/max from data if available
    if df["evt_dttm"].notna().any():
        data_min_date = df["evt_dttm"].min().date()
        data_max_date = df["evt_dttm"].max().date()
    else:
        data_min_date = default_start_date
        data_max_date = default_end_date

    col_date1, col_date2 = st.columns(2)
    with col_date1:
        start_date = st.date_input("Start date", value=default_start_date, help="Beginning of date range")
    with col_date2:
        end_date = st.date_input("End date", value=default_end_date, help="End of date range")

    filtered_df = df[(df["evt_dttm"].dt.date >= start_date) & (df["evt_dttm"].dt.date <= end_date)]
    
    # Filter for specific users
    target_users = ["Martina Kusters", "Katie Ahl", "Emma Wells", "Etosha Heights"]
    if "user_name" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["user_name"].isin(target_users)].copy()
        if filtered_df.empty:
            st.warning(f"⚠️ No giraffe sightings found for {', '.join(target_users)} in the selected date range")
    else:
        st.info("ℹ️ user_name column not found in data")

    st.markdown("---")

    #### heading metrics
    st.subheader("🦒 Giraffe Sightings")
    # Simplified metrics without subject group dependencies

    # Calculate basic metrics from filtered data
    individuals_seen = filtered_df["evt_herdSize"].sum() if "evt_herdSize" in filtered_df.columns else 0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Individuals seen", individuals_seen)
    with col2:
        # Count unique encounters/herds (each row represents one herd encounter)
        herd_count = len(filtered_df) if not filtered_df.empty else 0
        st.metric("Herds seen", herd_count)
    with col3:
        if "evt_herdSize" in filtered_df.columns:
            avg_herd_size = filtered_df["evt_herdSize"].mean()
            st.metric("Average herd size", f"{avg_herd_size:.1f}" if not pd.isna(avg_herd_size) else "N/A")
        else:
            st.metric("Average herd size", "N/A")
    with col4:
        st.metric("Date range", f"{(end_date - start_date).days} days")

    #### Sighting map
    st.subheader("📍 Sightings map")
    map_df = filtered_df.dropna(subset=["lat", "lon"])
    if not map_df.empty:
        # Calculate appropriate zoom level based on data extent
        lat_range = map_df["lat"].max() - map_df["lat"].min()
        lon_range = map_df["lon"].max() - map_df["lon"].min()
        max_range = max(lat_range, lon_range)
        
        # Estimate zoom level (approximate formula)
        if max_range > 10:
            zoom_level = 6
        elif max_range > 5:
            zoom_level = 7
        elif max_range > 2:
            zoom_level = 8
        elif max_range > 1:
            zoom_level = 9
        elif max_range > 0.5:
            zoom_level = 10
        else:
            zoom_level = 11
        
        # Create plotly map with dark satellite style and park boundaries
        fig_map = px.scatter_mapbox(
            map_df, 
            lat="lat", 
            lon="lon",
            hover_data=["evt_dttm", "evt_herdSize"] if "evt_herdSize" in map_df.columns else ["evt_dttm"],
            zoom=zoom_level,
            height=500,
            title="Giraffe Sightings"
        )
        
        # Set map style based on token availability
        if MAPBOX_TOKEN:
            # Use satellite-streets for Google Maps-like experience with boundaries
            map_style = "satellite-streets"
            px.set_mapbox_access_token(MAPBOX_TOKEN)
        else:
            # Fallback to open street map (free, no token required)
            map_style = "open-street-map"
        
        # Update layout for dark satellite style with boundaries
        fig_map.update_layout(
            mapbox_style=map_style,
            mapbox=dict(
                center=dict(
                    lat=map_df["lat"].mean(),
                    lon=map_df["lon"].mean()
                ),
                zoom=zoom_level
            ),
            margin={"r":0,"t":50,"l":0,"b":0},
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)"
        )
        
        # Update marker style for better visibility
        if map_style == "satellite-streets":
            # Yellow markers for satellite view
            marker_color = "yellow"
        else:
            # Red markers for street map
            marker_color = "red"
        
        fig_map.update_traces(
            marker=dict(
                size=12,
                color=marker_color,
                opacity=0.8
            )
        )
        
        st.plotly_chart(fig_map, use_container_width=True)
    else:
        st.info("No location data available for mapping")

    # Display giraffe sightings data table
    st.subheader("🦒 Giraffe sightings details")
    if not filtered_df.empty:
        # Check if we need to explode herd data for individual giraffes
        if "event_details.Herd" in filtered_df.columns:
            # Explode herd data to show individual giraffes
            display_sightings_df = filtered_df.explode("event_details.Herd").reset_index(drop=True)
            
            # Normalize the herd details if they exist
            if not display_sightings_df["event_details.Herd"].isna().all():
                herd_details = json_normalize(display_sightings_df["event_details.Herd"])
                display_sightings_df = pd.concat([display_sightings_df.drop(columns="event_details.Herd"), herd_details], axis=1)
                
                # Comprehensive column mapping including all event details
                column_mapping = {
                    'evt_dttm': 'Date/Time',
                    'user_name': 'Observer',
                    'evt_serial': 'Serial Number',
                    'event_id': 'Event ID',
                    'evt_imagePrefix': 'Image Prefix',
                    'evt_herdSize': 'Herd Size',
                    'evt_riverSystem': 'River System',
                    'evt_herd_dir': 'Herd Direction',
                    'evt_herd_dist': 'Herd Distance (m)',
                    'evt_herdNotes': 'Herd Notes',
                    'giraffe_id': 'Giraffe ID',
                    'giraffe_sex': 'Sex',
                    'giraffe_age': 'Age',
                    'giraffe_notes': 'Giraffe Notes',
                    'giraffe_right': 'Right Photo',
                    'giraffe_left': 'Left Photo',
                    'lat': 'Latitude',
                    'lon': 'Longitude',
                    'evt_url': 'Event URL'
                }
            else:
                # Fallback if herd details are empty
                column_mapping = {
                    'evt_dttm': 'Date/Time',
                    'user_name': 'Observer',
                    'evt_serial': 'Serial Number',
                    'event_id': 'Event ID',
                    'evt_imagePrefix': 'Image Prefix',
                    'evt_herdSize': 'Herd Size',
                    'evt_riverSystem': 'River System',
                    'evt_herd_dir': 'Herd Direction',
                    'evt_herd_dist': 'Herd Distance',
                    'evt_herdNotes': 'Notes',
                    'lat': 'Latitude',
                    'lon': 'Longitude',
                    'evt_url': 'Event URL'
                }
        else:
            # No herd data to explode, use event-level columns
            display_sightings_df = filtered_df.copy()
            column_mapping = {
                'evt_dttm': 'Date/Time',
                'user_name': 'Observer',
                'evt_serial': 'Serial Number',
                'event_id': 'Event ID',
                'evt_imagePrefix': 'Image Prefix',
                'evt_herdSize': 'Herd Size',
                'evt_riverSystem': 'River System',
                'evt_herd_dir': 'Herd Direction',
                'evt_herd_dist': 'Herd Distance',
                'evt_herdNotes': 'Herd Notes',
                'evt_girID': 'Giraffe ID',
                'evt_girSex': 'Sex',
                'evt_girAge': 'Age',
                'evt_girNotes': 'Giraffe Notes',
                'evt_girRight': 'Right Photo',
                'evt_gifLeft': 'Left Photo',
                'lat': 'Latitude',
                'lon': 'Longitude',
                'evt_url': 'Event URL'
            }
        
        # Build display dataframe with available columns
        available_cols = [col for col in column_mapping.keys() if col in display_sightings_df.columns]
        display_sightings_df = display_sightings_df[available_cols]
        
        # Rename columns to friendly names
        display_sightings_df = display_sightings_df.rename(columns={k: v for k, v in column_mapping.items() if k in available_cols})
        
        # Format datetime if present
        if 'Date/Time' in display_sightings_df.columns:
            display_sightings_df['Date/Time'] = display_sightings_df['Date/Time'].dt.strftime('%Y-%m-%d %H:%M')
        
        # Format photo numbers to be at least 4 digits with leading zeros
        def format_photo_number(x):
            if pd.isna(x):
                return x
            try:
                # Try to convert to int and then format with leading zeros
                return str(int(float(x))).zfill(4)
            except (ValueError, TypeError):
                return x
        
        for photo_col in ['Right Photo', 'Left Photo']:
            if photo_col in display_sightings_df.columns:
                display_sightings_df[photo_col] = display_sightings_df[photo_col].apply(format_photo_number)
        
        # Sort by date descending
        if 'Date/Time' in display_sightings_df.columns:
            display_sightings_df = display_sightings_df.sort_values('Date/Time', ascending=False)
        
        st.dataframe(display_sightings_df, use_container_width=True, hide_index=True)
    else:
        st.info("No giraffe sightings to display")

    #### Age/sex breakdown bar chart
    st.subheader("🧬 Age / sex breakdown")

    # For age/sex breakdown, we need individual giraffe data
    # So we'll explode the herd data here if needed
    if not filtered_df.empty and "event_details.Herd" in df.columns:
        # Explode herd data for individual analysis
        individual_df = filtered_df.explode("event_details.Herd").reset_index(drop=True)
        if not individual_df["event_details.Herd"].isna().all():
            herd_details = json_normalize(individual_df["event_details.Herd"])
            individual_df = pd.concat([individual_df.drop(columns="event_details.Herd"), herd_details], axis=1)
            
            # Map the individual giraffe columns
            if "giraffe_sex" in individual_df.columns and "giraffe_age" in individual_df.columns:
                breakdown = (
                    individual_df.groupby(["giraffe_sex", "giraffe_age"])
                    .size()
                    .reset_index(name="Count")
                )
                fig2 = px.bar(breakdown, x="giraffe_age", y="Count", color="giraffe_sex", barmode="group",
                              category_orders={"giraffe_age": ["ad", "sa", "ju", "ca"]})
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("No individual giraffe age/sex data available in herd details")
        else:
            st.info("No herd detail data available for age/sex breakdown")
    elif not filtered_df.empty and "evt_girSex" in filtered_df.columns and "evt_girAge" in filtered_df.columns:
        # Use direct event-level age/sex data if available
        breakdown = (
            filtered_df.groupby(["evt_girSex", "evt_girAge"])
            .size()
            .reset_index(name="Count")
        )
        fig2 = px.bar(breakdown, x="evt_girAge", y="Count", color="evt_girSex", barmode="group",
                      category_orders={"evt_girAge": ["ad", "sa", "ju", "ca"]})
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No age/sex data available for breakdown chart")

    #### OTHER PRIORITY SPECIES SECTION ###############################################
    st.markdown("---")
    st.subheader("🦁 Other Priority Species Sightings")
    st.markdown("*Includes: Rhino, Lion, Cheetah, Leopard*")

    if not priority_species_df.empty:
        # Rename columns for priority species
        priority_rename_map = {
            "reported_by.id": "user_id",
            "reported_by.name": "user_name",
            "id": "event_id",
            "event_type": "evt_type",
            "event_category": "evt_category",
            "serial_number": "evt_serial",
            "url": "evt_url",
            "time": "evt_dttm",
            "location.latitude": "lat",
            "location.longitude": "lon"
        }
        
        priority_species_df = priority_species_df.rename(columns=priority_rename_map)
        priority_species_df["evt_dttm"] = pd.to_datetime(priority_species_df["evt_dttm"])
        priority_species_df = priority_species_df.dropna(subset=["evt_dttm"])
        
        # Filter by date range (using same dates as giraffe section)
        filtered_priority_df = priority_species_df[
            (priority_species_df["evt_dttm"].dt.date >= start_date) & 
            (priority_species_df["evt_dttm"].dt.date <= end_date)
        ]
        
        # Filter for specific users (same as giraffe section)
        if "user_name" in filtered_priority_df.columns:
            filtered_priority_df = filtered_priority_df[filtered_priority_df["user_name"].isin(target_users)].copy()
        
        if not filtered_priority_df.empty:
            # Metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total sightings", len(filtered_priority_df))
            with col2:
                species_count = filtered_priority_df["species"].nunique() if "species" in filtered_priority_df.columns else 0
                st.metric("Species observed", species_count)
            with col3:
                if "species" in filtered_priority_df.columns:
                    most_common = filtered_priority_df["species"].value_counts().index[0]
                    st.metric("Most common", most_common)
                else:
                    st.metric("Most common", "N/A")
            with col4:
                st.metric("Date range", f"{(end_date - start_date).days} days")
            
            # Sightings map
            st.subheader("📍 Priority species sightings map")
            map_priority_df = filtered_priority_df.dropna(subset=["lat", "lon"])
            if not map_priority_df.empty:
                # Calculate appropriate zoom level
                lat_range = map_priority_df["lat"].max() - map_priority_df["lat"].min()
                lon_range = map_priority_df["lon"].max() - map_priority_df["lon"].min()
                max_range = max(lat_range, lon_range)
                
                if max_range > 10:
                    zoom_level = 6
                elif max_range > 5:
                    zoom_level = 7
                elif max_range > 2:
                    zoom_level = 8
                elif max_range > 1:
                    zoom_level = 9
                elif max_range > 0.5:
                    zoom_level = 10
                else:
                    zoom_level = 11
                
                # Create plotly map with species color coding
                fig_priority = px.scatter_mapbox(
                    map_priority_df, 
                    lat="lat", 
                    lon="lon",
                    color="species" if "species" in map_priority_df.columns else None,
                    hover_data=["evt_dttm", "species"] if "species" in map_priority_df.columns else ["evt_dttm"],
                    zoom=zoom_level,
                    height=500,
                    title="Priority Species Sightings"
                )
                
                # Set map style based on token availability
                if MAPBOX_TOKEN:
                    map_style = "satellite-streets"
                    px.set_mapbox_access_token(MAPBOX_TOKEN)
                else:
                    map_style = "open-street-map"
                
                # Update layout
                fig_priority.update_layout(
                    mapbox_style=map_style,
                    mapbox=dict(
                        center=dict(
                            lat=map_priority_df["lat"].mean(),
                            lon=map_priority_df["lon"].mean()
                        ),
                        zoom=zoom_level
                    ),
                    margin={"r":0,"t":50,"l":0,"b":0},
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)"
                )
                
                # Update marker style
                fig_priority.update_traces(
                    marker=dict(
                        size=12,
                        opacity=0.8
                    )
                )
                
                st.plotly_chart(fig_priority, use_container_width=True)
            else:
                st.info("No location data available for mapping")
            
            # Display priority species sightings data table
            st.subheader("🦁 Priority species sightings details")
            
            # Check if we need to explode Group data for individual animals (like giraffe's Herd)
            if "event_details.Group" in filtered_priority_df.columns:
                # Explode Group data to show individual animals
                display_priority_df = filtered_priority_df.explode("event_details.Group").reset_index(drop=True)
                
                # Normalize the group details if they exist
                if not display_priority_df["event_details.Group"].isna().all():
                    group_details = json_normalize(display_priority_df["event_details.Group"])
                    display_priority_df = pd.concat([display_priority_df.drop(columns="event_details.Group"), group_details], axis=1)
                    
                    # Build comprehensive column mapping including individual animal details
                    priority_column_mapping = {
                        'evt_dttm': 'Date/Time',
                        'species': 'Species',
                        'user_name': 'Observer',
                        'evt_serial': 'Serial Number',
                        'event_id': 'Event ID',
                        'event_details.image_prefix': 'Image Prefix',
                        'event_details.group_size': 'Group Size',
                        'event_details.herd_notes': 'Group Notes',
                        'event_details.notes': 'Notes',
                        # Rhino individual details
                        'rhino_id': 'Rhino ID',
                        'rhino_age': 'Rhino Age',
                        'rhino_sex': 'Rhino Sex',
                        'rhino_notes': 'Rhino Notes',
                        'rhino_photo_left': 'Rhino Photo Left',
                        'rhino_photo_right': 'Rhino Photo Right',
                        'rhino_whisker_left': 'Rhino Whisker Left',
                        'rhino_whisker_right': 'Rhino Whisker Right',
                        'rhino_ear_left': 'Rhino Ear Left',
                        'rhino_ear_right': 'Rhino Ear Right',
                        # Lion individual details
                        'lion_id': 'Lion ID',
                        'lion_age': 'Lion Age',
                        'lion_sex': 'Lion Sex',
                        'lion_notes': 'Lion Notes',
                        'lion_photo_left': 'Lion Photo Left',
                        'lion_photo_right': 'Lion Photo Right',
                        'lion_whisker_left': 'Lion Whisker Left',
                        'lion_whisker_right': 'Lion Whisker Right',
                        'lion_ear_left': 'Lion Ear Left',
                        'lion_ear_right': 'Lion Ear Right',
                        # Cheetah individual details
                        'cheetah_id': 'Cheetah ID',
                        'cheetah_age': 'Cheetah Age',
                        'cheetah_sex': 'Cheetah Sex',
                        'cheetah_notes': 'Cheetah Notes',
                        'cheetah_photo_left': 'Cheetah Photo Left',
                        'cheetah_photo_right': 'Cheetah Photo Right',
                        'cheetah_whisker_left': 'Cheetah Whisker Left',
                        'cheetah_whisker_right': 'Cheetah Whisker Right',
                        # Leopard individual details
                        'leopard_id': 'Leopard ID',
                        'leopard_age': 'Leopard Age',
                        'leopard_sex': 'Leopard Sex',
                        'leopard_notes': 'Leopard Notes',
                        'leopard_photo_left': 'Leopard Photo Left',
                        'leopard_photo_right': 'Leopard Photo Right',
                        'leopard_whisker_left': 'Leopard Whisker Left',
                        'leopard_whisker_right': 'Leopard Whisker Right',
                        'lat': 'Latitude',
                        'lon': 'Longitude',
                        'evt_url': 'Event URL'
                    }
                else:
                    # Fallback if group details are empty
                    display_priority_df = filtered_priority_df.copy()
                    priority_column_mapping = {
                        'evt_dttm': 'Date/Time',
                        'species': 'Species',
                        'user_name': 'Observer',
                        'evt_serial': 'Serial Number',
                        'event_id': 'Event ID',
                        'event_details.image_prefix': 'Image Prefix',
                        'event_details.group_size': 'Group Size',
                        'event_details.notes': 'Notes',
                        'lat': 'Latitude',
                        'lon': 'Longitude',
                        'evt_url': 'Event URL'
                    }
            else:
                # No Group data to explode
                display_priority_df = filtered_priority_df.copy()
                priority_column_mapping = {
                    'evt_dttm': 'Date/Time',
                    'species': 'Species',
                    'user_name': 'Observer',
                    'evt_serial': 'Serial Number',
                    'event_id': 'Event ID',
                    'event_details.image_prefix': 'Image Prefix',
                    'event_details.group_size': 'Group Size',
                    'event_details.notes': 'Notes',
                    'lat': 'Latitude',
                    'lon': 'Longitude',
                    'evt_url': 'Event URL'
                }
            
            # Build display dataframe with available columns
            available_cols = [col for col in priority_column_mapping.keys() if col in display_priority_df.columns]
            display_priority_df = display_priority_df[available_cols]
            
            # Rename columns to friendly names
            display_priority_df = display_priority_df.rename(columns={k: v for k, v in priority_column_mapping.items() if k in available_cols})
            
            # Format datetime
            if 'Date/Time' in display_priority_df.columns:
                display_priority_df['Date/Time'] = display_priority_df['Date/Time'].dt.strftime('%Y-%m-%d %H:%M')
            
            # Format photo numbers to be at least 4 digits with leading zeros
            def format_photo_number(x):
                if pd.isna(x):
                    return x
                try:
                    # Try to convert to int and then format with leading zeros
                    return str(int(float(x))).zfill(4)
                except (ValueError, TypeError):
                    return x
            
            # Apply photo number formatting to all photo columns
            photo_columns = [col for col in display_priority_df.columns if 'Photo' in col or 'Whisker' in col or 'Ear' in col]
            for photo_col in photo_columns:
                if photo_col in display_priority_df.columns:
                    display_priority_df[photo_col] = display_priority_df[photo_col].apply(format_photo_number)
            
            # Sort by date descending
            if 'Date/Time' in display_priority_df.columns:
                display_priority_df = display_priority_df.sort_values('Date/Time', ascending=False)
            
            st.dataframe(display_priority_df, use_container_width=True, hide_index=True)
            
            # Species breakdown bar chart
            st.subheader("📊 Species breakdown")
            if "species" in filtered_priority_df.columns:
                species_counts = filtered_priority_df["species"].value_counts().reset_index()
                species_counts.columns = ["Species", "Count"]
                
                fig_species = px.bar(
                    species_counts, 
                    x="Species", 
                    y="Count",
                    title="Sightings by Species",
                    color="Species"
                )
                st.plotly_chart(fig_species, use_container_width=True)
            else:
                st.info("No species data available for breakdown")
        else:
            st.info(f"No priority species sightings found for {', '.join(target_users)} in the selected date range")
    else:
        st.info("No priority species data available")

    #### PATROL MAP ###############################################
    st.markdown("---")
    st.subheader("🚶 Patrol Tracks")
    
    # Allow user to edit patrol leader names
    patrol_names_input = st.text_area(
        "Patrol leader usernames (one per line)",
        value="Martina Kusters\nKatie Ahl\nEmma Wells\nEtosha Heights",
        height=80,
        help="Enter patrol leader names to filter. From debug info, available leaders are shown."
    )
    patrol_usernames = [name.strip() for name in patrol_names_input.split('\n') if name.strip()]

    @st.cache_data(ttl=3600, show_spinner=False)
    def load_patrol_data(start_date_input, end_date_input, patrol_usernames_list, er_username, er_password, _debug=True):
        """Load patrol data filtered by specified usernames"""
        debug_info = []
        try:
            er = EarthRangerIO(
                server="https://twiga.pamdas.org",
                username=er_username,
                password=er_password
            )
            
            # Get patrols - fetch broader range and filter manually
            # EarthRanger API filters by scheduled dates, but Emma Wells' patrols use actual start dates
            debug_info.append(f"📅 Requested date range: {start_date_input} to {end_date_input}")
            debug_info.append(f"👤 Looking for patrols by: {', '.join(patrol_usernames_list)}")
            
            # Fetch last 150 days of patrols (broader range) to catch patrols with missing scheduled dates
            # Using 150 days to ensure we capture all recent patrols
            broader_since = (datetime.now() - timedelta(days=150)).strftime("%Y-%m-%dT%H:%M:%SZ")
            broader_until = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")  # Add 7 days buffer to future
            
            debug_info.append(f"🔍 Fetching patrols from {broader_since} to {broader_until}")
            
            # Get patrols
            try:
                patrols_df = er.get_patrols(
                    since=broader_since,
                    until=broader_until
                )
            except Exception as patrol_err:
                if 'timeout' in str(patrol_err).lower():
                    debug_info.append(f"⏱️ Request timed out - try a shorter date range")
                    return None, f"Request timed out. Please try a shorter date range (currently {(end_date_input - start_date_input).days} days)", debug_info
                else:
                    raise
            
            debug_info.append(f"📊 Total patrols retrieved: {len(patrols_df)}")
            
            if patrols_df.empty:
                return None, "No patrols found for the specified date range", debug_info
            
            # Debug: Show highest serial numbers to check if we're getting recent patrols
            if 'serial_number' in patrols_df.columns:
                max_serial = patrols_df['serial_number'].max()
                min_serial = patrols_df['serial_number'].min()
                debug_info.append(f"🔢 Serial number range: {min_serial} to {max_serial}")
            
            # Debug: Show raw patrol data structure for first few AND last few patrols
            debug_info.append(f"🔍 Examining patrol data structure (first 3 and last 3):")
            display_patrols = pd.concat([patrols_df.head(3), patrols_df.tail(3)])
            for idx, row in display_patrols.iterrows():
                patrol_id = row.get('id', 'unknown')
                title = row.get('title', 'No title')
                serial = row.get('serial_number', 'No serial')
                debug_info.append(f"  Patrol: {title} (ID: {patrol_id}, Serial: {serial})")
                
                # Check multiple possible fields for patrol leader
                if 'patrol_segments' in row:
                    debug_info.append(f"    patrol_segments: {type(row['patrol_segments'])}")
                    if isinstance(row['patrol_segments'], list) and len(row['patrol_segments']) > 0:
                        segment = row['patrol_segments'][0]
                        debug_info.append(f"    First segment keys: {segment.keys() if isinstance(segment, dict) else 'Not a dict'}")
                        if isinstance(segment, dict):
                            if 'leader' in segment:
                                debug_info.append(f"    leader: {segment['leader']}")
                            if 'tracked_subject' in segment:
                                debug_info.append(f"    tracked_subject: {segment['tracked_subject']}")
                
                # Check other possible leader fields
                if 'owner' in row:
                    debug_info.append(f"    owner: {row['owner']}")
                if 'created_by' in row:
                    debug_info.append(f"    created_by: {row['created_by']}")
            
            # Extract patrol leader/subject from patrol_segments
            def get_patrol_subject(row):
                # Try multiple possible fields
                # 1. Check patrol_segments -> leader
                if 'patrol_segments' in row and isinstance(row['patrol_segments'], list) and len(row['patrol_segments']) > 0:
                    segment = row['patrol_segments'][0]
                    if isinstance(segment, dict):
                        if 'leader' in segment:
                            leader = segment['leader']
                            if isinstance(leader, dict):
                                return leader.get('name', leader.get('username', leader.get('content_type', '')))
                            return str(leader) if leader else ''
                        # Try tracked_subject as alternative
                        if 'tracked_subject' in segment:
                            subject = segment['tracked_subject']
                            if isinstance(subject, dict):
                                return subject.get('name', subject.get('username', ''))
                            return str(subject) if subject else ''
                
                # 2. Check owner field
                if 'owner' in row:
                    owner = row['owner']
                    if isinstance(owner, dict):
                        return owner.get('username', owner.get('name', ''))
                    return str(owner) if owner else ''
                
                # 3. Check created_by field
                if 'created_by' in row:
                    creator = row['created_by']
                    if isinstance(creator, dict):
                        return creator.get('username', creator.get('name', ''))
                    return str(creator) if creator else ''
                
                return ''
            
            patrols_df['patrol_leader'] = patrols_df.apply(get_patrol_subject, axis=1)
            
            # Get unique leaders for debugging
            unique_leaders = patrols_df['patrol_leader'].unique().tolist()
            unique_leaders_clean = [l for l in unique_leaders if l]
            debug_info.append(f"👥 Found {len(unique_leaders_clean)} unique patrol leaders in last 90 days:")
            for leader in sorted(unique_leaders_clean):
                count = len(patrols_df[patrols_df['patrol_leader'] == leader])
                debug_info.append(f"   - '{leader}': {count} patrol(s)")
            
            # Filter for specified username patrols only
            patrols_df = patrols_df[patrols_df['patrol_leader'].isin(patrol_usernames_list)].copy()
            
            debug_info.append(f"✅ Patrols for target users (before date filter): {len(patrols_df)}")
            
            if patrols_df.empty:
                return None, f"No patrols found for {', '.join(patrol_usernames_list)}", debug_info
            
            # NOW filter by actual start date from time_range (not scheduled dates)
            def get_actual_start_date(row):
                """Extract actual start date from patrol segments"""
                if 'patrol_segments' in row and isinstance(row['patrol_segments'], list) and len(row['patrol_segments']) > 0:
                    segment = row['patrol_segments'][0]
                    if isinstance(segment, dict):
                        time_range = segment.get('time_range', {})
                        if isinstance(time_range, dict):
                            start_time = time_range.get('start_time')
                            if start_time:
                                try:
                                    return pd.to_datetime(start_time).date()
                                except:
                                    pass
                return None
            
            patrols_df['actual_start_date'] = patrols_df.apply(get_actual_start_date, axis=1)
            
            # Show all patrol dates for debugging
            debug_info.append(f"📅 Patrol dates found:")
            for idx, row in patrols_df.iterrows():
                patrol_leader = row.get('patrol_leader', 'Unknown')
                serial = row.get('serial_number', 'N/A')
                actual_date = row.get('actual_start_date', 'No date')
                debug_info.append(f"   - Serial {serial} ({patrol_leader}): {actual_date}")
            
            # Filter by user's requested date range using actual dates
            patrols_df = patrols_df[
                (patrols_df['actual_start_date'] >= start_date_input) & 
                (patrols_df['actual_start_date'] <= end_date_input)
            ].copy()
            
            debug_info.append(f"✅ Patrols after date filtering ({start_date_input} to {end_date_input}): {len(patrols_df)}")
            
            if patrols_df.empty:
                return None, f"No patrols found for {', '.join(patrol_usernames_list)} in the specified date range", debug_info
            
            # Get patrol observations
            debug_info.append(f"🔄 Fetching patrol observations...")
            patrol_observations = er.get_patrol_observations(
                patrols_df=patrols_df,
                include_patrol_details=True
            )
            
            # Handle both Relocations object and GeoDataFrame
            if hasattr(patrol_observations, 'gdf'):
                points_gdf = patrol_observations.gdf
            else:
                points_gdf = patrol_observations
            
            debug_info.append(f"📍 Total observation points: {len(points_gdf)}")
            
            if points_gdf.empty:
                return None, "No patrol tracks found", debug_info
            
            # Find time column for sorting
            time_col = None
            for col in ['extra__recorded_at', 'recorded_at', 'fixtime', 'time', 'timestamp']:
                if col in points_gdf.columns:
                    time_col = col
                    break
            
            debug_info.append(f"⏰ Time column used: {time_col if time_col else 'None found'}")
            
            # Convert points to LineStrings grouped by patrol_id
            lines = []
            group_col = 'patrol_id'
            
            unique_patrol_ids = points_gdf[group_col].unique()
            debug_info.append(f"🆔 Unique patrol IDs: {len(unique_patrol_ids)}")
            
            for group_id in unique_patrol_ids:
                patrol_points = points_gdf[points_gdf[group_col] == group_id].copy()
                
                # Sort by time
                if time_col and time_col in patrol_points.columns:
                    patrol_points = patrol_points.sort_values(time_col, ascending=True)
                
                if len(patrol_points) < 2:
                    debug_info.append(f"⚠️ Patrol {group_id}: Only {len(patrol_points)} point(s), skipping")
                    continue
                
                # Create LineString from points
                coords = [(point.x, point.y) for point in patrol_points.geometry]
                line = LineString(coords)
                
                # Get patrol metadata
                first_point = patrol_points.iloc[0]
                
                # Get actual patrol leader name
                patrol_leader_name = ''
                if 'patrol_leader' in patrols_df.columns:
                    patrol_info = patrols_df[patrols_df['id'] == first_point.get('patrol_id')]
                    if not patrol_info.empty:
                        patrol_leader_name = patrol_info.iloc[0]['patrol_leader']
                
                line_data = {
                    'geometry': line,
                    'patrol_id': first_point['patrol_id'] if 'patrol_id' in first_point.index else group_id,
                    'patrol_title': first_point.get('patrol_title', ''),
                    'patrol_sn': first_point.get('patrol_serial_number', ''),
                    'patrol_type': first_point.get('patrol_type__display', first_point.get('patrol_type__value', '')),
                    'subject_name': patrol_leader_name,
                    'num_points': len(patrol_points),
                    'distance_km': line.length * 111
                }
                
                # Add time columns if available
                if time_col:
                    line_data['start_time'] = str(patrol_points[time_col].min())
                    line_data['end_time'] = str(patrol_points[time_col].max())
                
                lines.append(line_data)
            
            debug_info.append(f"✅ Successfully created {len(lines)} patrol track(s)")
            
            if not lines:
                return None, "No patrols with multiple points found (need at least 2 points per patrol)", debug_info
            
            # Create GeoDataFrame from lines
            lines_gdf = gpd.GeoDataFrame(lines, crs=4326)
            return lines_gdf, None, debug_info
            
        except Exception as e:
            import traceback
            debug_info.append(f"❌ ERROR: {str(e)}")
            debug_info.append(f"📋 Traceback: {traceback.format_exc()}")
            return None, f"Error loading patrol data: {str(e)}", debug_info

    col_load_p, _ = st.columns([1, 3])
    with col_load_p:
        if st.button("Load patrol data", key="load_patrols_btn"):
            st.session_state["ehgr_patrols_loaded"] = True

    if not st.session_state["ehgr_patrols_loaded"]:
        st.info("Click **Load patrol data** to fetch patrol tracks.")
        patrol_gdf = None
        patrol_error = None
    else:
        with st.spinner(f"Loading patrol data for {', '.join(patrol_usernames)}... This may take a moment."):
            patrol_result = load_patrol_data(start_date, end_date, patrol_usernames, username, password)

        # Unpack result (could be 2 or 3 items)
        if len(patrol_result) == 3:
            patrol_gdf, patrol_error, debug_info = patrol_result
            with st.expander("🔍 Debug Information", expanded=False):
                for info in debug_info:
                    st.write(info)
        else:
            patrol_gdf, patrol_error = patrol_result
            patrol_gdf = None

    if patrol_error:
        st.warning(f"⚠️ {patrol_error}")
    elif patrol_gdf is not None and not patrol_gdf.empty:
        st.success(f"✅ Loaded {len(patrol_gdf)} patrol track(s)")
        
        # Display patrol summary metrics
        col_p1, col_p2, col_p3 = st.columns(3)
        with col_p1:
            st.metric("Total patrols", len(patrol_gdf))
        with col_p2:
            st.metric("Total distance (km)", f"{patrol_gdf['distance_km'].sum():.2f}")
        with col_p3:
            st.metric("Total points", patrol_gdf['num_points'].sum())
        
        # Patrol type breakdown
        st.subheader("📋 Distance by patrol type")
        if 'patrol_type' in patrol_gdf.columns:
            patrol_type_summary = patrol_gdf.groupby('patrol_type')['distance_km'].agg(['sum', 'count']).reset_index()
            patrol_type_summary.columns = ['Patrol Type', 'Total Distance (km)', 'Number of Patrols']
            patrol_type_summary['Total Distance (km)'] = patrol_type_summary['Total Distance (km)'].round(2)
            patrol_type_summary = patrol_type_summary.sort_values('Total Distance (km)', ascending=False)
            st.dataframe(patrol_type_summary, use_container_width=True, hide_index=True)
        else:
            st.info("No patrol type data available")
        
        # Create patrol map
        st.subheader("📍 Patrol tracks map")
        
        # Extract coordinates from LineStrings for plotting
        patrol_plot_data = []
        for idx, row in patrol_gdf.iterrows():
            coords = list(row.geometry.coords)
            for i, (lon, lat) in enumerate(coords):
                patrol_plot_data.append({
                    'lat': lat,
                    'lon': lon,
                    'patrol_id': row['patrol_id'],
                    'patrol_title': row.get('patrol_title', f"Patrol {idx+1}"),
                    'patrol_type': row.get('patrol_type', 'N/A'),
                    'order': i
                })
        
        patrol_plot_df = pd.DataFrame(patrol_plot_data)
        
        if not patrol_plot_df.empty:
            # Calculate appropriate zoom level for patrol tracks
            lat_range = patrol_plot_df["lat"].max() - patrol_plot_df["lat"].min()
            lon_range = patrol_plot_df["lon"].max() - patrol_plot_df["lon"].min()
            max_range = max(lat_range, lon_range)
            
            if max_range > 10:
                patrol_zoom = 6
            elif max_range > 5:
                patrol_zoom = 7
            elif max_range > 2:
                patrol_zoom = 8
            elif max_range > 1:
                patrol_zoom = 9
            elif max_range > 0.5:
                patrol_zoom = 10
            else:
                patrol_zoom = 11
            
            # Create plotly line map
            fig_patrol = px.line_mapbox(
                patrol_plot_df,
                lat="lat",
                lon="lon",
                color="patrol_title",
                hover_data=["patrol_type"],
                zoom=patrol_zoom,
                height=500,
                title="Patrol Tracks"
            )
            
            # Set map style
            if MAPBOX_TOKEN:
                map_style = "satellite-streets"
                px.set_mapbox_access_token(MAPBOX_TOKEN)
            else:
                map_style = "open-street-map"
            
            fig_patrol.update_layout(
                mapbox_style=map_style,
                mapbox=dict(
                    center=dict(
                        lat=patrol_plot_df["lat"].mean(),
                        lon=patrol_plot_df["lon"].mean()
                    ),
                    zoom=patrol_zoom
                ),
                margin={"r":0,"t":50,"l":0,"b":0},
                showlegend=True
            )
            
            st.plotly_chart(fig_patrol, use_container_width=True)
            
            # Display patrol data table
            st.subheader("Patrol details")
            display_patrol_df = patrol_gdf.drop(columns=['geometry']).copy()
            st.dataframe(display_patrol_df)
        else:
            st.info("No patrol track data to display")
    else:
        st.info("No patrol data available for the selected date range")

    #### CAMERA TRAP CHECK ###############################################
    st.markdown("---")
    st.subheader("📷 Camera Trap Check")
    st.markdown("*Last check event per camera trap station*")

    @st.cache_data(ttl=3600)
    def load_camera_trap_events(er_username, er_password):
        er = EarthRangerIO(
            server="https://twiga.pamdas.org",
            username=er_username,
            password=er_password
        )
        since = "2024-01-01T00:00:00Z"
        until = datetime.now().strftime("%Y-%m-%dT23:59:59Z")
        try:
            events = er.get_events(
                event_type="64ffa5d9-6fec-4ed7-bdbd-54e761c767a0",
                since=since,
                until=until,
                include_details=True,
                include_notes=True
            )
            if events.empty:
                return pd.DataFrame()
            flat = json_normalize(events.to_dict(orient="records"))
            if "event_type" in flat.columns:
                flat = flat[flat["event_type"] == "camera_trap_2"]
            return flat
        except Exception as e:
            st.error(f"❌ Error loading camera trap check data: {str(e)}")
            return pd.DataFrame()

    col_load_c, _ = st.columns([1, 3])
    with col_load_c:
        if st.button("Load camera trap data", key="load_camera_btn"):
            st.session_state["ehgr_camera_loaded"] = True

    if not st.session_state["ehgr_camera_loaded"]:
        st.info("Click **Load camera trap data** to fetch check records.")
    else:
        camera_df = load_camera_trap_events(username, password)

    if st.session_state["ehgr_camera_loaded"] and not camera_df.empty:
        camera_df["time"] = pd.to_datetime(camera_df.get("time", pd.Series(dtype="object")), errors="coerce")
        camera_df = camera_df.dropna(subset=["time"])

        # Camtrap site code → display name lookup
        CAMTRAP_SITE_NAMES = {
            "S001": "Gruisgat",
            "S002": "Middlepos",
            "S003": "Mopaniepos",
            "S004": "Boesmanspoel",
            "S005": "Mountain Lodge",
            "S006": "Bergpos",
            "S007": "Boma Rooipos",
            "S008": "Nuwepos",
            "S009": "Grootrante",
            "S010": "Madala",
            "S011": "Bergwater",
            "S012": "Tankpos",
            "S013": "Grenswag",
            "S014": "Olifantspos",
            "S015": "Witgat",
            "S016": "Safarihoek",
            "S017": "Flamingo Pan",
            "S018": "Uitspuit Southern Boundary",
            "S019": "Mopaniepan Corner",
            "S020": "CT64",
            "S021": "CT75",
            "S022": "CT86",
            "S023": "CT97",
            "S024": "CT108",
            "S025": "CT119",
            "S026": "Oupos",
            "S027": "Vlakwater",
            "S028": "Leeuslootdam",
            "S029": "Gronddam",
            "S030": "Leeurante",
            "S031": "Moesoemoeroep",
            "S032": "Dadelpos",
        }

        # Identify columns
        detail_cols = [c for c in camera_df.columns if c.startswith("event_details.")]
        # Prefer the explicit camtrap_site field for grouping/display
        site_col = "event_details.camtrap_site" if "event_details.camtrap_site" in camera_df.columns else None
        # Fallback: detect station column from hints (excluding "camera" which picks up camera-ID fields)
        station_col = site_col
        if not station_col:
            for hint in ["trap", "station", "site", "id"]:
                matches = [c for c in detail_cols if hint.lower() in c.lower()]
                if matches:
                    station_col = matches[0]
                    break

        # Deduplicate to most recent event per station
        camera_df_sorted = camera_df.sort_values("time", ascending=False)
        if station_col:
            summary_camera = camera_df_sorted.groupby(station_col, sort=False).first().reset_index()
        else:
            summary_camera = camera_df_sorted.copy()

        # Add site name column from hardcoded lookup
        if station_col and station_col in summary_camera.columns:
            summary_camera["_camtrap_site_name"] = summary_camera[station_col].map(CAMTRAP_SITE_NAMES)

        # Build display table
        cam_display_cols = {}
        if station_col:
            cam_display_cols[station_col] = "Camtrap Site"
        if "_camtrap_site_name" in summary_camera.columns:
            cam_display_cols["_camtrap_site_name"] = "Camtrap Site Name"
        cam_display_cols["time"] = "Last Checked"
        if "reported_by.name" in summary_camera.columns:
            cam_display_cols["reported_by.name"] = "Checked By"
        if "serial_number" in summary_camera.columns:
            cam_display_cols["serial_number"] = "Serial #"
        for c in detail_cols:
            if c == station_col:
                continue
            cam_display_cols[c] = c.replace("event_details.", "").replace("_", " ").title()
        for notes_col in ["notes", "event_details.notes"]:
            if notes_col in summary_camera.columns and notes_col not in cam_display_cols:
                cam_display_cols[notes_col] = "Notes"

        # Deduplicate display names — keep first occurrence only
        seen_labels = set()
        avail_cam = []
        for c in cam_display_cols:
            if c in summary_camera.columns and cam_display_cols[c] not in seen_labels:
                avail_cam.append(c)
                seen_labels.add(cam_display_cols[c])
        out_cam = summary_camera[avail_cam].rename(columns={c: cam_display_cols[c] for c in avail_cam})
        out_cam["Last Checked"] = pd.to_datetime(out_cam["Last Checked"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
        station_label = cam_display_cols.get(station_col) if station_col else None
        sort_col = station_label if station_label and station_label in out_cam.columns else "Last Checked"
        out_cam = out_cam.sort_values(sort_col, ascending=True)

        st.metric("Camera traps with check records", len(out_cam))
        st.dataframe(out_cam, use_container_width=True, hide_index=True)
    elif st.session_state["ehgr_camera_loaded"]:
        st.info("No camera trap check events found.")

    #### WEATHER STATION CHECK ###############################################
    st.markdown("---")
    st.subheader("🌦️ Weather Station Check")
    st.markdown("*Last check event per weather station*")

    @st.cache_data(ttl=3600)
    def load_weather_station_events(er_username, er_password):
        er = EarthRangerIO(
            server="https://twiga.pamdas.org",
            username=er_username,
            password=er_password
        )
        since = "2024-01-01T00:00:00Z"
        until = datetime.now().strftime("%Y-%m-%dT23:59:59Z")
        try:
            events = er.get_events(
                event_type="f3fbb844-3749-40c9-8bc5-82878c37169a",
                since=since,
                until=until,
                include_details=True,
                include_notes=True
            )
            if events.empty:
                return pd.DataFrame()
            flat = json_normalize(events.to_dict(orient="records"))
            if "event_type" in flat.columns:
                flat = flat[flat["event_type"] == "weather_station"]
            return flat
        except Exception as e:
            st.error(f"❌ Error loading weather station check data: {str(e)}")
            return pd.DataFrame()

    col_load_w, _ = st.columns([1, 3])
    with col_load_w:
        if st.button("Load weather station data", key="load_weather_btn"):
            st.session_state["ehgr_weather_loaded"] = True

    if not st.session_state["ehgr_weather_loaded"]:
        st.info("Click **Load weather station data** to fetch check records.")
    else:
        weather_df = load_weather_station_events(username, password)

    if st.session_state["ehgr_weather_loaded"] and not weather_df.empty:
        weather_df["time"] = pd.to_datetime(weather_df.get("time", pd.Series(dtype="object")), errors="coerce")
        weather_df = weather_df.dropna(subset=["time"])

        # Identify station column from event_details fields
        detail_cols_ws = [c for c in weather_df.columns if c.startswith("event_details.")]
        station_col_ws = None
        for hint in ["name", "station", "weather", "id"]:
            matches = [c for c in detail_cols_ws if hint.lower() in c.lower()]
            if matches:
                station_col_ws = matches[0]
                break

        # Deduplicate to most recent event per station
        weather_df_sorted = weather_df.sort_values("time", ascending=False)
        if station_col_ws:
            summary_weather = weather_df_sorted.groupby(station_col_ws, sort=False).first().reset_index()
        else:
            summary_weather = weather_df_sorted.copy()

        # Build display table
        ws_display_cols = {}
        if station_col_ws:
            ws_display_cols[station_col_ws] = station_col_ws.replace("event_details.", "").replace("_", " ").title()
        ws_display_cols["time"] = "Last Checked"
        if "reported_by.name" in summary_weather.columns:
            ws_display_cols["reported_by.name"] = "Checked By"
        if "serial_number" in summary_weather.columns:
            ws_display_cols["serial_number"] = "Serial #"
        for c in detail_cols_ws:
            if c == station_col_ws:
                continue
            ws_display_cols[c] = c.replace("event_details.", "").replace("_", " ").title()
        for notes_col in ["notes", "event_details.notes"]:
            if notes_col in summary_weather.columns and notes_col not in ws_display_cols:
                ws_display_cols[notes_col] = "Notes"

        # Deduplicate display names — keep first occurrence only
        seen_labels_ws = set()
        avail_ws = []
        for c in ws_display_cols:
            if c in summary_weather.columns and ws_display_cols[c] not in seen_labels_ws:
                avail_ws.append(c)
                seen_labels_ws.add(ws_display_cols[c])
        out_ws = summary_weather[avail_ws].rename(columns={c: ws_display_cols[c] for c in avail_ws})
        out_ws["Last Checked"] = pd.to_datetime(out_ws["Last Checked"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
        station_label_ws = ws_display_cols.get(station_col_ws) if station_col_ws else None
        sort_col_ws = station_label_ws if station_label_ws and station_label_ws in out_ws.columns else "Last Checked"
        out_ws = out_ws.sort_values(sort_col_ws, ascending=True)

        st.metric("Weather stations with check records", len(out_ws))
        st.dataframe(out_ws, use_container_width=True, hide_index=True)
    elif st.session_state["ehgr_weather_loaded"]:
        st.info("No weather station check events found.")

    #### Simplified - AAG section removed as not applicable for EHGR

    # Logout button
    if st.sidebar.button("🔓 Logout"):
        for key in ['authenticated', 'username', 'password']:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

if __name__ == "__main__":
    main()