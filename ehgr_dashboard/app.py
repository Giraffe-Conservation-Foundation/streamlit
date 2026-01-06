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

    # Simplified EHGR dashboard without subject group dependencies

    @st.cache_data(ttl=3600)
    def get_active_sources():
        """Get active tracking sources for EHGR giraffes"""
        er = EarthRangerIO(
            server="https://twiga.pamdas.org",
            username=username,
            password=password
        )
        sources_df = er.get_sources()
        sources = sources_df.to_dict('records')
        
        # Filter for active sources (exclude dummy sources)
        active_sources = [
            s for s in sources 
            if s.get("provider") != "dummy"
            and s.get("is_active") is True
        ]
        return active_sources

    active_sources = get_active_sources()

    @st.cache_data(ttl=3600)
    def load_data():
        """Load EHGR giraffe survey encounter data"""
        er = EarthRangerIO(
            server="https://twiga.pamdas.org",
            username=username,
            password=password
        )
        
        # EHGR-specific event parameters (Namibia data)
        event_cat = "monitoring_nam"
        event_type = "giraffe_survey_encounter_nam"
        since = "2024-07-01T00:00:00Z"
        until = "2025-12-31T23:59:59Z"

        try:
            events = er.get_events(
                event_category=event_cat,
                since=since,
                until=until,
                include_details=True,
                include_notes=False
            )
            
            if events.empty:
                st.warning(f"⚠️ No events found for category '{event_cat}' and type '{event_type}'")
                st.info("💡 Please verify the event category and type names are correct for EHGR")
                return pd.DataFrame()
            
            flat = json_normalize(events.to_dict(orient="records"))
            giraffe_only = flat[flat["event_type"] == event_type]

            if giraffe_only.empty:
                st.warning(f"⚠️ No events found with event_type '{event_type}'")
                available_types = flat["event_type"].unique() if "event_type" in flat.columns else []
                if len(available_types) > 0:
                    st.info(f"💡 Available event types: {', '.join(available_types)}")
                return pd.DataFrame()

            # Process herd data if available - but keep one record per herd encounter
            if "event_details.Herd" in giraffe_only.columns:
                # For individual giraffe analysis later, we can explode
                # But for metrics, we want to keep herd-level data
                events_final = giraffe_only.copy()
            else:
                events_final = giraffe_only

            return events_final
            
        except Exception as e:
            st.error(f"❌ Error loading EHGR data: {str(e)}")
            st.info("💡 Please check the event category and type parameters")
            return pd.DataFrame()

    df = load_data()

    if df.empty:
        st.warning("⚠️ No data available to display")
        st.info("""
        **Possible issues:**
        1. Event category 'monitoring_nam' may not exist
        2. Event type 'giraffe_survey_encounter_nam' may not exist  
        3. No data in the specified date range
        4. Subject group IDs need to be updated
        
        **Next steps:**
        - Verify the correct event category and type names for EHGR
        - Update the subject group IDs in the code
        - Check if there's data in the specified date range
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
    target_users = ["Martina Kusters", "Katie Ahl", "Emma Wells"]
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
                fig2 = px.bar(breakdown, x="giraffe_age", y="Count", color="giraffe_sex", barmode="group")
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
        fig2 = px.bar(breakdown, x="evt_girAge", y="Count", color="evt_girSex", barmode="group")
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No age/sex data available for breakdown chart")

    #### PATROL MAP ###############################################
    st.markdown("---")
    st.subheader("🚶 Patrol Tracks")
    
    # Allow user to edit patrol leader names
    patrol_names_input = st.text_area(
        "Patrol leader usernames (one per line)",
        value="Martina Kusters\nKatie Ahl\nEmma Wells",
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
            
            # Convert dates to ISO format
            since = datetime.combine(start_date_input, datetime.min.time()).isoformat()
            until = datetime.combine(end_date_input, datetime.max.time()).isoformat()
            
            debug_info.append(f"📅 Date range: {since} to {until}")
            debug_info.append(f"👤 Looking for patrols by: {', '.join(patrol_usernames_list)}")
            
            # Get patrols
            try:
                patrols_df = er.get_patrols(
                    since=since,
                    until=until,
                    status=['done', 'active']
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
            
            # Extract patrol leader/subject from patrol_segments
            def get_patrol_subject(row):
                if 'patrol_segments' in row and isinstance(row['patrol_segments'], list) and len(row['patrol_segments']) > 0:
                    segment = row['patrol_segments'][0]
                    if isinstance(segment, dict):
                        if 'leader' in segment:
                            leader = segment['leader']
                            if isinstance(leader, dict):
                                return leader.get('name', leader.get('username', ''))
                            return str(leader) if leader else ''
                return ''
            
            patrols_df['patrol_leader'] = patrols_df.apply(get_patrol_subject, axis=1)
            
            # Get unique leaders for debugging
            unique_leaders = patrols_df['patrol_leader'].unique().tolist()
            unique_leaders_clean = [l for l in unique_leaders if l]
            debug_info.append(f"👥 Found {len(unique_leaders_clean)} unique patrol leaders:")
            for leader in sorted(unique_leaders_clean):
                debug_info.append(f"   - '{leader}'")
            
            # Filter for specified username patrols only
            patrols_df = patrols_df[patrols_df['patrol_leader'].isin(patrol_usernames_list)].copy()
            
            debug_info.append(f"✅ Patrols for {', '.join(patrol_usernames_list)}: {len(patrols_df)}")
            
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

    # Load patrol data automatically
    with st.spinner(f"Loading patrol data for {', '.join(patrol_usernames)}... This may take a moment."):
        patrol_result = load_patrol_data(start_date, end_date, patrol_usernames, username, password)
    
    # Unpack result (could be 2 or 3 items)
    if len(patrol_result) == 3:
        patrol_gdf, patrol_error, debug_info = patrol_result
        
        # Display debug information in an expander
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

    #### Simplified - AAG section removed as not applicable for EHGR

    # Logout button
    if st.sidebar.button("🔓 Logout"):
        for key in ['authenticated', 'username', 'password']:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

if __name__ == "__main__":
    main()