"""
Patrol Shapefile Downloader Page
Download patrol tracks from EarthRanger as shapefiles with associated events
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from ecoscope.io.earthranger import EarthRangerIO
import geopandas as gpd
import tempfile
import os
import zipfile
from shapely.geometry import LineString, shape

# Optional imports for map
try:
    import folium
    from streamlit_folium import folium_static
    HAS_FOLIUM = True
except ImportError:
    HAS_FOLIUM = False

# Note: Page configuration is handled by main Twiga Tools app

# Initialize session state for authentication
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'er_io' not in st.session_state:
    st.session_state.er_io = None

def authenticate_earthranger(server, username, password):
    """Authenticate with EarthRanger and return EarthRangerIO instance"""
    try:
        er_io = EarthRangerIO(
            server=server,
            username=username,
            password=password
        )
        return er_io, None
    except Exception as e:
        return None, str(e)

def download_patrol_tracks(er_io, patrol_type_value, since, until, subject_name=None):
    """Download patrol tracks as GeoDataFrame and convert to LineStrings"""
    try:
        # Get patrols based on filters
        patrols_df = er_io.get_patrols(
            since=since,
            until=until,
            status=['done', 'active']
        )
        
        if patrols_df.empty:
            return None, "No patrols found for the specified criteria"
        
        # Extract patrol_type from nested patrol_segments structure
        def get_patrol_type(row):
            """Extract patrol_type from patrol_segments"""
            if 'patrol_segments' in row and isinstance(row['patrol_segments'], list) and len(row['patrol_segments']) > 0:
                segment = row['patrol_segments'][0]
                if isinstance(segment, dict) and 'patrol_type' in segment:
                    return segment['patrol_type']
            return None
        
        def get_patrol_subject(row):
            """Extract patrol subject (leader name) from patrol_segments"""
            if 'patrol_segments' in row and isinstance(row['patrol_segments'], list) and len(row['patrol_segments']) > 0:
                segment = row['patrol_segments'][0]
                if isinstance(segment, dict):
                    # Try different possible subject field names
                    if 'leader' in segment:
                        leader = segment['leader']
                        if isinstance(leader, dict):
                            return leader.get('name', leader.get('username', ''))
                        return str(leader) if leader else ''
                    elif 'patrol_subject' in segment:
                        return segment['patrol_subject']
            return ''
        
        patrols_df['patrol_type_extracted'] = patrols_df.apply(get_patrol_type, axis=1)
        patrols_df['patrol_subject_extracted'] = patrols_df.apply(get_patrol_subject, axis=1)
        
        # Remove patrols with None/empty patrol types to avoid processing errors
        patrols_df = patrols_df[patrols_df['patrol_type_extracted'].notna()].copy()
        patrols_df = patrols_df[patrols_df['patrol_type_extracted'] != ''].copy()
        
        if patrols_df.empty:
            return None, "No patrols found with valid patrol types in the specified date range"
        
        # Filter by patrol_type(s)
        if patrol_type_value:
            if isinstance(patrol_type_value, list):
                # Multiple patrol types selected
                patrols_df = patrols_df[patrols_df['patrol_type_extracted'].isin(patrol_type_value)].copy()
                if patrols_df.empty:
                    return None, f"No patrols found for types: {', '.join(patrol_type_value)}"
            else:
                # Single patrol type (backwards compatibility)
                patrols_df = patrols_df[patrols_df['patrol_type_extracted'] == patrol_type_value].copy()
                if patrols_df.empty:
                    return None, f"No patrols found for type: {patrol_type_value}"
        
        # Filter by subject name(s) if specified
        if subject_name:
            if isinstance(subject_name, list):
                # Multiple leaders selected
                patrols_df = patrols_df[patrols_df['patrol_subject_extracted'].isin(subject_name)].copy()
                if patrols_df.empty:
                    return None, f"No patrols found for leaders: {', '.join(subject_name)}"
            else:
                # Single leader (backwards compatibility)
                patrols_df = patrols_df[patrols_df['patrol_subject_extracted'] == subject_name].copy()
                if patrols_df.empty:
                    return None, f"No patrols found for leader: {subject_name}"
        
        # Get the patrol IDs that match our filter
        patrol_ids = patrols_df['id'].tolist() if 'id' in patrols_df.columns else patrols_df.index.tolist()
        
        # Get patrol observations
        patrol_observations = er_io.get_patrol_observations(
            patrols_df=patrols_df,
            include_patrol_details=True
        )
        
        # Handle both Relocations object and GeoDataFrame
        if hasattr(patrol_observations, 'gdf'):
            points_gdf = patrol_observations.gdf
        else:
            points_gdf = patrol_observations
            
        if points_gdf.empty:
            return None, "No patrol tracks found"
        
        # IMPORTANT: Filter to only include observations from the patrols we queried
        # This ensures we only get the selected patrol type
        if 'patrol_id' in points_gdf.columns and len(patrol_ids) > 0:
            points_gdf = points_gdf[points_gdf['patrol_id'].isin(patrol_ids)].copy()
            if points_gdf.empty:
                return None, f"No observations found for the selected patrols"
        
        # Merge patrol subject names and titles into points data
        if 'patrol_id' in points_gdf.columns:
            if 'patrol_subject_extracted' in patrols_df.columns:
                # Create mapping of patrol_id to subject name
                patrol_subject_map = dict(zip(patrols_df['id'], patrols_df['patrol_subject_extracted']))
                points_gdf['patrol_subject_name'] = points_gdf['patrol_id'].map(patrol_subject_map)
            
            # Add patrol title/name if available
            if 'title' in patrols_df.columns:
                patrol_title_map = dict(zip(patrols_df['id'], patrols_df['title']))
                points_gdf['patrol_title'] = points_gdf['patrol_id'].map(patrol_title_map)
        
        # Find time column for sorting points chronologically
        time_col = None
        for col in ['extra__recorded_at', 'recorded_at', 'fixtime', 'time', 'timestamp']:
            if col in points_gdf.columns:
                time_col = col
                break
        
        # Filter points to patrol segment times
        points_before_filter = len(points_gdf)
        
        if time_col and 'patrol_start_time' in points_gdf.columns and 'patrol_end_time' in points_gdf.columns:
            try:
                # Ensure time column is datetime
                if not pd.api.types.is_datetime64_any_dtype(points_gdf[time_col]):
                    points_gdf[time_col] = pd.to_datetime(points_gdf[time_col], format='ISO8601', utc=True)
                
                # Convert patrol_start_time and patrol_end_time from STRING to datetime
                # These come as ISO format strings like "2025-10-25T04:59:42Z" or with microseconds
                if points_gdf['patrol_start_time'].dtype == 'object':  # strings
                    points_gdf['patrol_start_time'] = pd.to_datetime(points_gdf['patrol_start_time'], format='ISO8601', utc=True)
                if points_gdf['patrol_end_time'].dtype == 'object':  # strings
                    points_gdf['patrol_end_time'] = pd.to_datetime(points_gdf['patrol_end_time'], format='ISO8601', utc=True)
                
                # Ensure all are timezone-aware UTC
                if points_gdf[time_col].dt.tz is None:
                    points_gdf[time_col] = points_gdf[time_col].dt.tz_localize('UTC')
                if points_gdf['patrol_start_time'].dt.tz is None:
                    points_gdf['patrol_start_time'] = points_gdf['patrol_start_time'].dt.tz_localize('UTC')
                if points_gdf['patrol_end_time'].dt.tz is None:
                    points_gdf['patrol_end_time'] = points_gdf['patrol_end_time'].dt.tz_localize('UTC')
                
                # Filter: keep only points where recorded time is between patrol start and end times
                within_patrol = (points_gdf[time_col] >= points_gdf['patrol_start_time']) & \
                               (points_gdf[time_col] <= points_gdf['patrol_end_time'])
                points_gdf = points_gdf[within_patrol].copy()
            except Exception as e:
                return None, "⚠️ No valid patrol data found within the selected date range and filters. Please check:\n• The date range contains patrols\n• The selected patrol type(s) are correct\n• The selected patrol leader(s) have patrols in this period"
        
        total_removed = points_before_filter - len(points_gdf)
        
        if points_gdf.empty:
            return None, f"No points found within patrol time ranges (filtered out {total_removed} of {points_before_filter} points)"
        
        # Convert points to LineStrings grouped by patrol segment
        lines = []
        
        # Group by patrol_id - each patrol should be a separate track
        # Note: groupby_col in ecoscope contains subject_id, not patrol segment ID
        group_col = 'patrol_id'
        
        for group_id in points_gdf[group_col].unique():
            patrol_points = points_gdf[points_gdf[group_col] == group_id].copy()
            
            # CRITICAL: Sort by recorded time to maintain chronological order
            # Data comes sorted from EarthRanger, but filtering may have disrupted the order
            if time_col and time_col in patrol_points.columns:
                patrol_points = patrol_points.sort_values(time_col, ascending=True)
            
            if len(patrol_points) < 2:
                continue  # Skip patrols with only one point
            
            # Create LineString from points IN TIME ORDER
            coords = [(point.x, point.y) for point in patrol_points.geometry]
            line = LineString(coords)
            
            # Get patrol metadata from first point
            first_point = patrol_points.iloc[0]
            
            # Extract patrol leader/subject name (the person leading the patrol)
            patrol_leader = ''
            if 'patrol_subject_name' in first_point.index:
                patrol_leader = first_point['patrol_subject_name']
            elif 'leader' in first_point.index:
                leader_data = first_point['leader']
                if isinstance(leader_data, dict):
                    patrol_leader = leader_data.get('name', leader_data.get('username', ''))
                else:
                    patrol_leader = str(leader_data) if leader_data else ''
            elif 'patrol_leader' in first_point.index:
                patrol_leader = first_point['patrol_leader']
            elif 'patrol_subject' in first_point.index:
                patrol_leader = first_point['patrol_subject']
            
            # Use the actual patrol_id for metadata, not groupby_col
            patrol_id = first_point['patrol_id'] if 'patrol_id' in first_point.index else group_id
            
            line_data = {
                'geometry': line,
                'patrol_id': patrol_id,
                'patrol_title': first_point['patrol_title'] if 'patrol_title' in first_point.index else '',
                'patrol_sn': first_point['patrol_serial_number'] if 'patrol_serial_number' in first_point.index else '',
                'patrol_type': first_point['patrol_type__display'] if 'patrol_type__display' in first_point.index else (first_point['patrol_type__value'] if 'patrol_type__value' in first_point.index else ''),
                'subject_id': first_point['extra__subject_id'] if 'extra__subject_id' in first_point.index else '',
                'subject_name': patrol_leader,
                'num_points': len(patrol_points),
                'distance_km': line.length * 111
            }
            
            # Add time columns if available
            if time_col:
                line_data['start_time'] = str(patrol_points[time_col].min())
                line_data['end_time'] = str(patrol_points[time_col].max())
            
            # Add patrol start/end times from metadata if available
            if 'patrol_start_time' in first_point.index:
                line_data['patrol_start_time'] = str(first_point['patrol_start_time'])
            if 'patrol_end_time' in first_point.index:
                line_data['patrol_end_time'] = str(first_point['patrol_end_time'])
            
            # Add patrol_type__ columns if they exist
            for col in first_point.index:
                if col.startswith('patrol_type__') and col not in line_data:
                    line_data[col] = first_point[col]
            
            lines.append(line_data)
        
        if not lines:
            return None, "No patrols with multiple points found (need at least 2 points to create a line)"
        
        # Create GeoDataFrame from lines
        lines_gdf = gpd.GeoDataFrame(lines, crs=4326)
            
        return lines_gdf, None
            
    except Exception as e:
        import traceback
        return None, f"{str(e)}\n\n{traceback.format_exc()}"

# Main app
st.title("🗺️ Patrol shapefile downloader")
st.markdown("Download patrol tracks from EarthRanger as shapefiles, with optional associated events")

# Authentication section at top of main page
st.markdown("---")
st.subheader("🔐 EarthRanger login")

if not st.session_state.authenticated:
    col_auth1, col_auth2, col_auth3 = st.columns(3)
    
    with col_auth1:
        server_input = st.text_input("Instance URL", placeholder="server.pamdas.org")
    
    with col_auth2:
        username = st.text_input("Username")
    
    with col_auth3:
        password = st.text_input("Password", type="password")
    
    if st.button("Login", type="primary", use_container_width=True):
        if server_input and username and password:
            # Add https:// if not present
            server = server_input if server_input.startswith('http') else f'https://{server_input}'
            with st.spinner("Authenticating..."):
                er_io, error = authenticate_earthranger(server, username, password)
                if er_io:
                    st.session_state.er_io = er_io
                    st.session_state.authenticated = True
                    st.success("✅ Successfully authenticated!")
                    st.rerun()
                else:
                    st.error(f"❌ Authentication failed: {error}")
        else:
            st.warning("Please fill in all fields")
else:
    col_status1, col_status2 = st.columns([3, 1])
    with col_status1:
        st.success("✅ Logged in to EarthRanger")
    with col_status2:
        if st.button("Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.er_io = None
            st.rerun()

st.markdown("---")

# Main content - only show if authenticated
if st.session_state.authenticated:
    # Date range selection row - FIRST
    st.subheader("1️⃣ Select date range")
    col1, col2 = st.columns(2)
    
    with col1:
        start_date = st.date_input(
            "Start date",
            value=datetime.now() - timedelta(days=30),
            help="Beginning of date range"
        )
    
    with col2:
        end_date = st.date_input(
            "End date",
            value=datetime.now(),
            help="End of date range"
        )
    
    # Combine date with start/end of day times
    since = datetime.combine(start_date, datetime.min.time()).isoformat()
    until = datetime.combine(end_date, datetime.max.time()).isoformat()
    
    st.markdown("---")
    st.subheader("2️⃣ Select filters (optional)")
    
    # Now load patrol types and leaders from actual patrols in the date range
    col3, col4 = st.columns(2)
    
    with st.spinner("Loading available filters from patrol data..."):
        try:
            # Fetch patrols in the date range
            sample_patrols = st.session_state.er_io.get_patrols(
                since=since,
                until=until,
                status=['done', 'active']
            )
            
            if not sample_patrols.empty:
                # Extract patrol types from actual patrols
                def get_patrol_type(row):
                    if 'patrol_segments' in row and isinstance(row['patrol_segments'], list) and len(row['patrol_segments']) > 0:
                        segment = row['patrol_segments'][0]
                        if isinstance(segment, dict) and 'patrol_type' in segment:
                            return segment['patrol_type']
                    return None
                
                # Extract patrol leaders from actual patrols
                def get_patrol_subject(row):
                    if 'patrol_segments' in row and isinstance(row['patrol_segments'], list):
                        for segment in row['patrol_segments']:
                            if isinstance(segment, dict):
                                leader = segment.get('leader', {})
                                if isinstance(leader, dict):
                                    return leader.get('name', '')
                    return ''
                
                sample_patrols['patrol_type_extracted'] = sample_patrols.apply(get_patrol_type, axis=1)
                sample_patrols['leader_name'] = sample_patrols.apply(get_patrol_subject, axis=1)
                
                # Get unique patrol types (filter out None/empty)
                patrol_types = sample_patrols['patrol_type_extracted'].dropna().unique().tolist()
                patrol_types = sorted([pt for pt in patrol_types if pt and str(pt).strip()])
                
                # Get unique leader names (filter out empty)
                leader_names = sample_patrols['leader_name'].dropna().unique().tolist()
                leader_names = sorted([name for name in leader_names if name and str(name).strip()])
                
                with col3:
                    if patrol_types:
                        selected_patrol_types = st.multiselect(
                            "Filter by patrol type(s) (optional)",
                            options=patrol_types,
                            default=patrol_types,
                            help="Select one or more patrol types, or leave empty for all"
                        )
                        patrol_type = selected_patrol_types if selected_patrol_types else None
                    else:
                        st.warning("No patrol types found in date range")
                        patrol_type = None
                
                with col4:
                    if leader_names:
                        selected_leaders = st.multiselect(
                            "Filter by patrol leader(s) (optional)",
                            options=leader_names,
                            default=leader_names,
                            help="Select one or more patrol leaders, or leave empty for all"
                        )
                        subject_name_filter = selected_leaders if selected_leaders else None
                    else:
                        st.warning("No patrol leaders found in date range")
                        subject_name_filter = None
            else:
                st.info("No patrols found in the selected date range")
                patrol_type = None
                subject_name_filter = None
        except Exception as e:
            st.error(f"Error loading filters: {e}")
            patrol_type = None
            subject_name_filter = None
    
    st.markdown("---")
    
    # Download button for patrol tracks
    if st.button("🔽 Download patrol tracks", type="primary", use_container_width=True):
        with st.spinner("Downloading patrol tracks..."):
            gdf, error = download_patrol_tracks(
                st.session_state.er_io,
                patrol_type,
                since,
                until,
                subject_name=subject_name_filter if subject_name_filter else None
            )
            
            if error:
                st.error(f"❌ Error: {error}")
            elif gdf is not None:
                st.success(f"✅ Successfully downloaded {len(gdf)} patrol track(s)!")
                
                # Store the downloaded patrols in session state for events extraction
                st.session_state.downloaded_patrols_gdf = gdf
                
                # Display map preview
                st.subheader("📍 Map preview")
                if HAS_FOLIUM:
                    try:
                        # Calculate center point
                        bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
                        center_lat = (bounds[1] + bounds[3]) / 2
                        center_lon = (bounds[0] + bounds[2]) / 2
                        
                        # Create map
                        m = folium.Map(location=[center_lat, center_lon], zoom_start=12)
                        
                        # Add each track to the map
                        colors = ['blue', 'red', 'green', 'purple', 'orange', 'darkred', 'lightred', 'beige', 'darkblue', 'darkgreen']
                        for idx, row in gdf.iterrows():
                            color = colors[idx % len(colors)]
                            coords = [(coord[1], coord[0]) for coord in row.geometry.coords]  # lat, lon
                            
                            folium.PolyLine(
                                coords,
                                color=color,
                                weight=3,
                                opacity=0.8,
                                popup=f"{row.get('patrol_title', 'Patrol')}<br>Points: {row.get('num_points', 'N/A')}<br>Distance: {row.get('distance_km', 0):.2f} km"
                            ).add_to(m)
                            
                            # Add start marker
                            folium.CircleMarker(
                                coords[0],
                                radius=5,
                                color=color,
                                fill=True,
                                popup=f"Start: {row.get('patrol_title', '')}",
                            ).add_to(m)
                            
                            # Add end marker
                            folium.CircleMarker(
                                coords[-1],
                                radius=5,
                                color=color,
                                fill=True,
                                fillColor='white',
                                popup=f"End: {row.get('patrol_title', '')}",
                            ).add_to(m)
                        
                        # Fit bounds
                        m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
                        
                        # Display map
                        folium_static(m, width=800, height=500)
                        
                    except Exception as e:
                        st.warning(f"Could not create map preview: {e}")
                else:
                    st.info("💡 Install folium and streamlit-folium to see map preview:\n```pip install folium streamlit-folium```")
                
                # Display preview
                st.subheader("Data preview")
                # Create display DataFrame without geometry and some redundant columns
                cols_to_drop = ['geometry', 'start_time', 'end_time']
                display_df = gdf.drop(columns=[col for col in cols_to_drop if col in gdf.columns]).copy()
                st.dataframe(display_df)
                
                # Show summary statistics
                col5, col6, col7 = st.columns(3)
                with col5:
                    st.metric("Total tracks", len(gdf))
                with col6:
                    st.metric("Total points", gdf['num_points'].sum())
                with col7:
                    st.metric("Total distance (km)", f"{gdf['distance_km'].sum():.2f}")
                
                # Save to shapefile
                try:
                    # Format filename: patroltype_yymmdd_yymmdd
                    start_str = start_date.strftime('%y%m%d')
                    end_str = end_date.strftime('%y%m%d')
                    # Clean patrol type for filename (remove spaces, special chars)
                    if patrol_type:
                        if isinstance(patrol_type, list):
                            # Multiple patrol types - join them
                            patrol_type_clean = "_".join("".join(c if c.isalnum() else "_" for c in pt) for pt in patrol_type[:3])  # Limit to first 3 to avoid too long filename
                        else:
                            patrol_type_clean = "".join(c if c.isalnum() else "_" for c in patrol_type)
                    else:
                        patrol_type_clean = "all_patrols"
                    base_filename = f"{patrol_type_clean}_{start_str}_{end_str}"
                    
                    # Prepare shapefile-friendly column names (max 10 chars)
                    # Rename columns: patrol → ptrl to save characters
                    gdf_export = gdf.copy()
                    column_mapping = {
                        'patrol_id': 'ptrl_id',
                        'patrol_sn': 'ptrl_sn',
                        'patrol_type': 'ptrl_type',
                        'subject_id': 'subj_id',
                        'subject_name': 'subj_name',
                        'patrol_start_time': 'ptrl_start',
                        'patrol_end_time': 'ptrl_end',
                        'distance_km': 'dist_km',
                        'num_points': 'num_pts'
                    }
                    # Only rename columns that exist
                    gdf_export = gdf_export.rename(columns={k: v for k, v in column_mapping.items() if k in gdf_export.columns})
                    
                    with tempfile.TemporaryDirectory() as tmpdir:
                        shapefile_path = os.path.join(tmpdir, f"{base_filename}.shp")
                        gdf_export.to_file(shapefile_path)
                        
                        # Create a zip file with all shapefile components
                        zip_path = os.path.join(tmpdir, f"{base_filename}.zip")
                        
                        with zipfile.ZipFile(zip_path, 'w') as zipf:
                            for ext in ['.shp', '.shx', '.dbf', '.prj', '.cpg']:
                                file_path = shapefile_path.replace('.shp', ext)
                                if os.path.exists(file_path):
                                    # Add files to zip with the base filename
                                    zipf.write(file_path, f"{base_filename}{ext}")
                        
                        # Read the zip file for download
                        with open(zip_path, 'rb') as f:
                            zip_data = f.read()
                        
                        st.download_button(
                            label="📥 Download Shapefile (ZIP)",
                            data=zip_data,
                            file_name=f"{base_filename}.zip",
                            mime="application/zip",
                            use_container_width=True
                        )
                except Exception as e:
                    st.error(f"❌ Error creating shapefile: {e}")
    
    # Events extraction section
    st.markdown("---")
    st.subheader("📋 Extract patrol events")
    st.markdown("Extract events associated with downloaded patrols")
    
    # Check if patrols have been downloaded
    if 'downloaded_patrols_gdf' in st.session_state and st.session_state.downloaded_patrols_gdf is not None:
        gdf_patrols = st.session_state.downloaded_patrols_gdf
        
        # Show available patrols
        st.write(f"Found {len(gdf_patrols)} patrol(s) to extract events from")
        
        # Button to extract events
        if st.button("📥 Extract patrol events", type="primary", use_container_width=True):
            with st.spinner("Extracting events from patrols..."):
                try:
                    # Get the original patrols dataframe with patrol_segments
                    # Use patrol_type_value instead of patrol_type since we have the value, not UUID
                    patrols_df = st.session_state.er_io.get_patrols(
                        since=since,
                        until=until,
                        patrol_type_value=patrol_type,
                        status=['done', 'active']
                    )
                    
                    # Filter to only the patrol IDs we have in our downloaded tracks
                    patrol_ids = gdf_patrols['patrol_id'].unique().tolist()
                    patrols_df = patrols_df[patrols_df['id'].isin(patrol_ids)].copy()
                    
                    if patrols_df.empty:
                        st.warning("No matching patrols found")
                    else:
                        # Get events using get_events with patrol segments to include full details
                        try:
                            # Extract all patrol segment IDs from the matched patrols
                            # Also create mappings for patrol_id, patrol_name, and subject/leader name
                            patrol_segment_ids = []
                            segment_to_patrol_map = {}  # Maps segment_id -> patrol_id
                            segment_to_patrol_name_map = {}  # Maps segment_id -> patrol_name/title
                            segment_to_subject_map = {}  # Maps segment_id -> subject/leader name
                            
                            for _, patrol in patrols_df.iterrows():
                                patrol_id = patrol['id']
                                patrol_name = patrol.get('title', patrol.get('serial_number', ''))
                                
                                # Extract leader/subject name from first segment
                                leader_name = ''
                                for segment in patrol.get('patrol_segments', []):
                                    if 'id' in segment:
                                        segment_id = segment['id']
                                        patrol_segment_ids.append(segment_id)
                                        segment_to_patrol_map[segment_id] = patrol_id
                                        segment_to_patrol_name_map[segment_id] = patrol_name
                                        
                                        # Extract leader name if not already extracted
                                        if not leader_name and 'leader' in segment:
                                            leader_data = segment['leader']
                                            if isinstance(leader_data, dict):
                                                leader_name = leader_data.get('name', leader_data.get('username', ''))
                                            else:
                                                leader_name = str(leader_data) if leader_data else ''
                                        
                                        segment_to_subject_map[segment_id] = leader_name
                            
                            if not patrol_segment_ids:
                                st.warning("No patrol segments found")
                                events_combined = gpd.GeoDataFrame()
                            else:
                                # Get events for each patrol segment with full details
                                all_events = []
                                progress_bar = st.progress(0)
                                status_text = st.empty()
                                
                                for idx, segment_id in enumerate(patrol_segment_ids):
                                    status_text.text(f"Processing segment {idx + 1}/{len(patrol_segment_ids)}...")
                                    try:
                                        # Use get_patrol_segment_events which correctly filters to patrol segment
                                        events_df = st.session_state.er_io.get_patrol_segment_events(
                                            patrol_segment_id=segment_id,
                                            include_details=True,
                                            include_notes=True,
                                            include_related_events=False,
                                            include_files=False
                                        )
                                        
                                        if not events_df.empty:
                                            # Add patrol_id, patrol_name, and patrol_leader from our mappings
                                            events_df['patrol_id'] = segment_to_patrol_map.get(segment_id, '')
                                            events_df['patrol_name'] = segment_to_patrol_name_map.get(segment_id, '')
                                            events_df['patrol_leader'] = segment_to_subject_map.get(segment_id, '')
                                            
                                            # Convert to GeoDataFrame with geometry from geojson
                                            def extract_geometry(row):
                                                if 'geojson' in row and row['geojson']:
                                                    try:
                                                        if isinstance(row['geojson'], dict):
                                                            return shape(row['geojson'])
                                                    except:
                                                        pass
                                                return None
                                            
                                            events_df['geometry'] = events_df.apply(extract_geometry, axis=1)
                                            # Filter out events without geometry
                                            events_gdf = events_df[events_df['geometry'].notna()].copy()
                                            
                                            if events_gdf.empty:
                                                status_text.text(f"Segment {idx + 1}/{len(patrol_segment_ids)}: No events with valid geometry")
                                                continue
                                            
                                            events_gdf = gpd.GeoDataFrame(events_gdf, geometry='geometry', crs=4326)
                                            
                                            # Now fetch full details for each event by event ID (only if 'id' column exists)
                                            has_details = False
                                            if 'id' in events_gdf.columns and len(events_gdf) > 0:
                                                event_ids = events_gdf['id'].tolist()
                                                # Filter out any None or NaN values
                                                event_ids = [eid for eid in event_ids if eid and pd.notna(eid)]
                                                
                                                if event_ids:
                                                    status_text.text(f"Segment {idx + 1}/{len(patrol_segment_ids)}: Fetching details for {len(event_ids)} events...")
                                                    
                                                    # Batch event IDs to avoid URL length limits (414 error)
                                                    # Process in chunks of 50 event IDs at a time
                                                    batch_size = 50
                                                    detailed_events_list = []
                                                    
                                                    for batch_idx in range(0, len(event_ids), batch_size):
                                                        batch_event_ids = event_ids[batch_idx:batch_idx + batch_size]
                                                        try:
                                                            # Fetch events with details using event IDs
                                                            detailed_events_batch = st.session_state.er_io.get_events(
                                                                event_ids=batch_event_ids,
                                                                include_details=True,
                                                                include_notes=True
                                                            )
                                                            if not detailed_events_batch.empty:
                                                                detailed_events_list.append(detailed_events_batch)
                                                        except Exception as batch_err:
                                                            st.warning(f"Could not fetch details for event batch {batch_idx//batch_size + 1}: {str(batch_err)[:100]}")
                                                    
                                                    # Combine all batches
                                                    if detailed_events_list:
                                                        detailed_events = pd.concat(detailed_events_list, ignore_index=True)
                                                        
                                                        if not detailed_events.empty and 'event_details' in detailed_events.columns and 'id' in detailed_events.columns:
                                                            # Merge event_details back into events_gdf
                                                            # Reset index to use 'id' for merging
                                                            try:
                                                                detailed_events_subset = detailed_events[['id', 'event_details']].copy()
                                                                events_gdf = events_gdf.merge(detailed_events_subset, on='id', how='left')
                                                                has_details = True
                                                            except Exception as merge_err:
                                                                st.warning(f"Could not merge event details: {str(merge_err)[:100]}")
                                                                has_details = False
                                            
                                            status_text.text(f"Segment {idx + 1}/{len(patrol_segment_ids)}: Found {len(events_gdf)} events (details: {has_details})")
                                            all_events.append(events_gdf)
                                        else:
                                            status_text.text(f"Segment {idx + 1}/{len(patrol_segment_ids)}: No events")
                                    except Exception as e:
                                        status_text.text(f"Segment {idx + 1}/{len(patrol_segment_ids)}: Error - {str(e)[:50]}")
                                        st.warning(f"Could not get events for segment {segment_id}: {e}")
                                    
                                    progress_bar.progress((idx + 1) / len(patrol_segment_ids))
                                
                                progress_bar.empty()
                                status_text.empty()
                                
                                # Combine all events
                                if all_events:
                                    events_combined = gpd.GeoDataFrame(pd.concat(all_events, ignore_index=True))
                                else:
                                    events_combined = gpd.GeoDataFrame()
                            
                            if events_combined.empty:
                                st.info("No events found for these patrols")
                            else:
                                    st.success(f"✅ Successfully extracted {len(events_combined)} event(s)!")
                                    
                                    # Extract coordinates from geometry
                                    if 'geometry' in events_combined.columns:
                                        events_combined['longitude'] = events_combined.geometry.x
                                        events_combined['latitude'] = events_combined.geometry.y
                                    
                                    
                                    # Extract time from geojson.properties.datetime if time column doesn't exist
                                    if 'time' not in events_combined.columns and 'geojson' in events_combined.columns:
                                        def extract_datetime(geojson):
                                            if isinstance(geojson, dict):
                                                props = geojson.get('properties', {})
                                                if isinstance(props, dict):
                                                    dt_str = props.get('datetime')
                                                    if dt_str:
                                                        return pd.to_datetime(dt_str, utc=True)
                                            return None
                                        events_combined['time'] = events_combined['geojson'].apply(extract_datetime)
                                    
                                    # Extract reported_by name (subject_name)
                                    if 'reported_by' in events_combined.columns:
                                        events_combined['subject_name'] = events_combined['reported_by'].apply(
                                            lambda x: x.get('name', '') if isinstance(x, dict) else ''
                                        )
                                    
                                    # Unnest event_details
                                    if 'event_details' in events_combined.columns:
                                        # Extract event_details fields into separate columns
                                        event_details_df = pd.json_normalize(events_combined['event_details'])
                                        # Add prefix to avoid column name conflicts
                                        event_details_df.columns = ['detail_' + col for col in event_details_df.columns]
                                        # Combine with main dataframe - preserve geometry
                                        geometry_col = events_combined.geometry
                                        events_combined = pd.concat([events_combined.reset_index(drop=True), event_details_df], axis=1)
                                        # Restore as GeoDataFrame
                                        events_combined = gpd.GeoDataFrame(events_combined, geometry=geometry_col.reset_index(drop=True), crs=4326)
                                    
                                    # Extract coordinates from location dict if it exists
                                    if 'location' in events_combined.columns:
                                        events_combined['location_lat'] = events_combined['location'].apply(
                                            lambda x: x.get('latitude') if isinstance(x, dict) else None
                                        )
                                        events_combined['location_lon'] = events_combined['location'].apply(
                                            lambda x: x.get('longitude') if isinstance(x, dict) else None
                                        )
                                    
                                    # Display map preview with both patrols and events
                                    st.subheader("📍 Events map preview")
                                    if HAS_FOLIUM:
                                        try:
                                            # Calculate center point from events
                                            events_bounds = events_combined.total_bounds  # [minx, miny, maxx, maxy]
                                            center_lat = (events_bounds[1] + events_bounds[3]) / 2
                                            center_lon = (events_bounds[0] + events_bounds[2]) / 2
                                            
                                            # Create map
                                            m = folium.Map(location=[center_lat, center_lon], zoom_start=12)
                                            
                                            # Add patrol tracks
                                            patrol_colors = ['blue', 'darkblue', 'lightblue', 'cadetblue']
                                            for idx, row in gdf_patrols.iterrows():
                                                color = patrol_colors[idx % len(patrol_colors)]
                                                coords = [(coord[1], coord[0]) for coord in row.geometry.coords]  # lat, lon
                                                
                                                folium.PolyLine(
                                                    coords,
                                                    color=color,
                                                    weight=3,
                                                    opacity=0.6,
                                                    popup=f"Patrol: {row.get('patrol_sn', 'N/A')}",
                                                ).add_to(m)
                                            
                                            # Add event markers
                                            event_colors = {
                                                'default': 'red'
                                            }
                                            
                                            for idx, row in events_combined.iterrows():
                                                lat = row.geometry.y
                                                lon = row.geometry.x
                                                
                                                # Get event type for popup
                                                event_type = row.get('event_type', 'Event')
                                                event_time = row.get('time', 'N/A')
                                                patrol_sn = row.get('patrol_serial_number', 'N/A')
                                                
                                                popup_text = f"<b>{event_type}</b><br>Time: {event_time}<br>Patrol: {patrol_sn}"
                                                
                                                folium.CircleMarker(
                                                    location=[lat, lon],
                                                    radius=6,
                                                    color='red',
                                                    fill=True,
                                                    fillColor='red',
                                                    fillOpacity=0.7,
                                                    popup=popup_text,
                                                ).add_to(m)
                                            
                                            # Fit bounds to show both patrols and events
                                            all_bounds = [
                                                [events_bounds[1], events_bounds[0]], 
                                                [events_bounds[3], events_bounds[2]]
                                            ]
                                            m.fit_bounds(all_bounds)
                                            
                                            # Display map
                                            folium_static(m, width=800, height=500)
                                            
                                        except Exception as e:
                                            st.warning(f"Could not create map preview: {e}")
                                    else:
                                        st.info("💡 Install folium and streamlit-folium to see map preview")
                                    
                                    # Display data preview
                                    st.subheader("Events data preview")
                                    # Create display DataFrame without geometry and geojson
                                    display_cols = [col for col in events_combined.columns if col not in ['geometry', 'geojson']]
                                    display_df = events_combined[display_cols].copy()
                                    
                                    # Clean up the display
                                    # Remove unwanted columns
                                    cols_to_remove = ['level_8', 'index', 'location', 'reported_by', 'event_details', 
                                                     'geojson', 'attributes', 'notes', 'patrols', 'patrol_segments',
                                                     'is_contained_in', 'related_subjects',
                                                     'location_lat', 'location_lon', 'message', 'provenance',
                                                     'event_category', 'priority_label', 'comment', 'end_time',
                                                     'sort_at', 'icon_id', 'url', 'image_url', 'external_source']
                                    display_df = display_df.drop(columns=[col for col in cols_to_remove if col in display_df.columns])
                                    
                                    # Rename columns for better readability
                                    rename_mapping = {
                                        'id': 'event_id',
                                        'time': 'event_datetime'
                                    }
                                    # Only rename columns that exist
                                    rename_mapping = {k: v for k, v in rename_mapping.items() if k in display_df.columns}
                                    if rename_mapping:
                                        display_df = display_df.rename(columns=rename_mapping)
                                    
                                    # Reorder columns to put important ones first
                                    preferred_order = ['event_id', 'patrol_id', 'patrol_name', 'patrol_leader', 
                                                      'serial_number', 'event_type', 'subject_name', 
                                                      'longitude', 'latitude', 'event_datetime', 
                                                      'priority', 'title', 'state', 
                                                      'updated_at', 'created_at', 'is_collection']
                                    
                                    # Add all detail_ columns after the main columns
                                    detail_cols = sorted([col for col in display_df.columns if col.startswith('detail_')])
                                    preferred_order.extend(detail_cols)
                                    
                                    # Get columns in preferred order (only if they exist)
                                    ordered_cols = [col for col in preferred_order if col in display_df.columns]
                                    # Add remaining columns
                                    remaining_cols = [col for col in display_df.columns if col not in ordered_cols]
                                    display_df = display_df[ordered_cols + remaining_cols]
                                    
                                    st.dataframe(display_df)
                                    
                                    # Show summary statistics
                                    col_e1, col_e2 = st.columns(2)
                                    with col_e1:
                                        st.metric("Total events", len(events_combined))
                                    with col_e2:
                                        if 'event_type' in events_combined.columns:
                                            st.metric("Event types", events_combined['event_type'].nunique())
                                    
                                    # Save to CSV
                                    try:
                                        start_str = start_date.strftime('%y%m%d')
                                        end_str = end_date.strftime('%y%m%d')
                                        patrol_type_clean = "".join(c if c.isalnum() else "_" for c in patrol_type)
                                        base_filename = f"{patrol_type_clean}_events_{start_str}_{end_str}"
                                        
                                        # Prepare CSV export - remove geometry and geojson columns
                                        events_export = events_combined.copy()
                                        cols_to_remove_export = ['geometry', 'geojson']
                                        events_export = events_export.drop(columns=[col for col in cols_to_remove_export if col in events_export.columns])
                                        
                                        # Remove same columns as display
                                        cols_to_remove_from_export = ['level_8', 'index', 'location', 'reported_by', 'event_details', 
                                                                     'geojson', 'attributes', 'notes', 'patrols', 
                                                                     'patrol_segments', 'is_contained_in', 'related_subjects', 
                                                                     'location_lat', 'location_lon', 
                                                                     'message', 'provenance', 'event_category', 'priority_label', 
                                                                     'comment', 'end_time', 'sort_at', 'icon_id', 'url', 
                                                                     'image_url', 'external_source']
                                        events_export = events_export.drop(columns=[col for col in cols_to_remove_from_export if col in events_export.columns])
                                        
                                        # Apply same renaming as display
                                        rename_mapping = {
                                            'id': 'event_id',
                                            'time': 'event_datetime'
                                        }
                                        # Only rename columns that exist
                                        rename_mapping = {k: v for k, v in rename_mapping.items() if k in events_export.columns}
                                        if rename_mapping:
                                            events_export = events_export.rename(columns=rename_mapping)
                                        
                                        # Convert to CSV
                                        csv_data = events_export.to_csv(index=False)
                                        
                                        st.download_button(
                                            label="📥 Download Events CSV",
                                            data=csv_data,
                                            file_name=f"{base_filename}.csv",
                                            mime="text/csv",
                                            use_container_width=True
                                        )
                                    except Exception as e:
                                        st.error(f"❌ Error creating events CSV: {e}")
                        except Exception as e:
                            st.error(f"❌ Error extracting patrol events: {e}")
                            import traceback
                            st.error(traceback.format_exc())
                
                except Exception as e:
                    st.error(f"❌ Error extracting events: {e}")
                    import traceback
                    st.error(traceback.format_exc())
    else:
        st.info("👆 Download patrol tracks first to enable event extraction")
    
    # Citation section at bottom of main area
    st.markdown("""
    ---
    
    **Citation:** Marneweck, CJ (2025) EarthRanger patrol shapefile downloader (v1.0.2). Giraffe Conservation Foundation, Windhoek, Namibia. Available at: https://erpatrolexport.streamlit.app/
    
    Opensource code on GitHub: https://github.com/Giraffe-Conservation-Foundation/streamlit_ERpatrolExport
    
    Created by the Giraffe Conservation Foundation, powered by Ecoscope
    
    Made with ❤️ for wildlife conservation
    """)

else:
    st.info("Please login to your EarthRanger instance using the form above")
    
    # Show some information about the app
    st.markdown("""
    ### About this app
    
    This application allows you to download patrol track data from EarthRanger as shapefiles, as well as the patrols associated events as a csv.
    
    **Features:**
    - Secure authentication with EarthRanger
    - Filter by patrol types unique to your EarthRanger instance
    - Users will only be able to access the data for which they have permissions to view/export in your EarthRanger instance permission settings
    - Download tracks as a shapefile (ZIP format)
    - Download the associated events as a csv
    - Preview all data before downloading
    
    **How to use:**
    1. Log in with your EarthRanger credentials using the form above
    2. Select a patrol type and patrol leader from the dropdown menu
    3. Choose your date range
    4. Click "Download patrol tracks"
    5. Check the preview, and download the shapefile ZIP when ready
    6. Click "Extract patrol events" if required
    7. Check the preview, and download the csv file when ready
    """)
