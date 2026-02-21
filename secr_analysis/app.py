"""
SECR Analysis Dashboard
=======================

Spatially-Explicit Capture-Recapture analysis for population estimation.
Demonstrates the complete workflow from EarthRanger field data → Wildbook photo-ID → SECR analysis.

Author: Giraffe Conservation Foundation
Date: February 2026
"""

import streamlit as st
import pandas as pd
import numpy as np
import sys
import os
from pathlib import Path
import io
import re
from datetime import datetime

try:
    import folium
    from streamlit_folium import st_folium
    FOLIUM_AVAILABLE = True
except ImportError:
    FOLIUM_AVAILABLE = False

# Add parent directory to path for shared utilities
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.append(str(parent_dir))

# Try to import SECR workflow components
try:
    # Force reload of bailey_analysis module to get latest changes
    import importlib
    if 'secr_analysis.bailey_analysis' in sys.modules:
        del sys.modules['secr_analysis.bailey_analysis']
    
    from secr_analysis.secr_workflow import (
        SECRAnalysis, 
        EarthRangerDataExtractor, 
        load_wildbook_export,
        prepare_secr_data,
        generate_example_data
    )
    from secr_analysis.bailey_analysis import (
        BaileyAnalysis,
        GiraffeSpotterClient,
        prepare_bailey_data
    )
    SECR_AVAILABLE = True
except ImportError as e:
    SECR_AVAILABLE = False
    IMPORT_ERROR = str(e)

# Try to import patrol download functionality
try:
    from ecoscope.io import EarthRangerIO
    import geopandas as gpd
    PATROL_DOWNLOAD_AVAILABLE = True
except ImportError:
    PATROL_DOWNLOAD_AVAILABLE = False


def main():
    """Main Streamlit app"""
    
    # Page title
    st.title("📊 SECR Population Analysis")
    st.caption("Build: 2026-02-18-UNIDENT-v22")
    st.markdown("*Spatially-Explicit Capture-Recapture*")
    st.markdown("---")
    
    # Introduction
    st.markdown("""
    ### 🦒 Bailey's Triple Catch Analysis
    
    **Residents-Only Population Estimation**
    
    This method:
    1. Downloads patrol tracks from EarthRanger (survey effort)
    2. Downloads encounter data from GiraffeSpotter
    3. Classifies individuals as **residents** (2+ captures) vs **transients** (1 capture)
    4. Applies Chapman's estimator to residents only
    5. Adds transients for total population estimate
    
    **Best for:** Short-term surveys (3+ days) in areas with transient individuals
    """)
    
    st.markdown("---")
    
    # Check if SECR is available
    if not SECR_AVAILABLE:
        st.error("❌ Bailey analysis module not available")
        st.code(f"Import Error: {IMPORT_ERROR}")
        st.info("""
        **To enable Bailey's analysis, install required packages:**
        ```bash
        pip install ecoscope-release pandas numpy scipy matplotlib geopandas shapely pywildbook
        ```
        """)
        return
    
    # Initialize session state for Bailey's analysis
    if 'bailey_results' not in st.session_state:
        st.session_state.bailey_results = None
    if 'bailey_data' not in st.session_state:
        st.session_state.bailey_data = None
    if 'bailey_patrols' not in st.session_state:
        st.session_state.bailey_patrols = None
    if 'all_patrols' not in st.session_state:
        st.session_state.all_patrols = None
    if 'patrol_leaders_list' not in st.session_state:
        st.session_state.patrol_leaders_list = []
    
    # ===== BAILEY'S TRIPLE CATCH ANALYSIS =====
    st.markdown("---")
    
    # Step 1: EarthRanger Connection
    st.markdown("## 📊 Step 1: EarthRanger Patrol Data")
    
    st.info("Download patrol tracks from the survey period to document survey effort.")
    
    col1, col2 = st.columns(2)
    with col1:
        er_username = st.text_input("EarthRanger Username", key="er_username_bailey")
    with col2:
        er_password = st.text_input("EarthRanger Password", type="password", key="er_password_bailey")
    
    # Date range
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", key="start_date_bailey")
    with col2:
        end_date = st.date_input("End Date", key="end_date_bailey")
    
    if st.button("📡 Download Patrol Data", key="download_patrols_bailey", type="primary"):
        if not er_username or not er_password:
            st.error("Please enter EarthRanger credentials")
        elif not PATROL_DOWNLOAD_AVAILABLE:
            st.error("❌ ecoscope-release not installed. Please install: pip install ecoscope-release")
        else:
            with st.spinner("Connecting to EarthRanger..."):
                try:
                    er_io = EarthRangerIO(
                        server="https://twiga.pamdas.org",
                        username=er_username,
                        password=er_password
                    )
                    
                    # Get patrols
                    patrols_df = er_io.get_patrols(
                        since=start_date.strftime('%Y-%m-%d'),
                        until=end_date.strftime('%Y-%m-%d'),
                        status=['done']
                    )
                    
                    if not patrols_df.empty:
                        # Extract patrol leader from patrol_segments
                        def get_patrol_leader(row):
                            if 'patrol_segments' in row and isinstance(row['patrol_segments'], list) and len(row['patrol_segments']) > 0:
                                segment = row['patrol_segments'][0]
                                if isinstance(segment, dict) and 'leader' in segment:
                                    leader = segment['leader']
                                    if isinstance(leader, dict):
                                        return leader.get('name', leader.get('username', ''))
                                    return str(leader) if leader else ''
                            return ''
                        
                        patrols_df['patrol_leader'] = patrols_df.apply(get_patrol_leader, axis=1)
                        
                        # Store all patrols for filtering
                        st.session_state.all_patrols = patrols_df
                        
                        # Get unique patrol leaders
                        patrol_leaders_list = sorted([leader for leader in patrols_df['patrol_leader'].unique() if leader])
                        st.session_state.patrol_leaders_list = patrol_leaders_list
                        
                        st.success(f"✅ Downloaded {len(patrols_df)} patrols from {len(patrol_leaders_list)} patrol leaders")
                        
                        # Debug: Show all columns and data types
                        with st.expander("🔍 Debug: Patrol Data Structure", expanded=False):
                            st.markdown("**Available columns:**")
                            col_info = pd.DataFrame({
                                'Column': patrols_df.columns,
                                'Type': [str(patrols_df[col].dtype) for col in patrols_df.columns],
                                'Sample': [str(patrols_df[col].iloc[0]) if len(patrols_df) > 0 else 'N/A' for col in patrols_df.columns]
                            })
                            st.dataframe(col_info, use_container_width=True)
                            
                            st.markdown("**First 3 patrols (all columns):**")
                            st.dataframe(patrols_df.head(3), use_container_width=True)
                        
                        # Show preview
                        with st.expander("📋 Patrol Preview"):
                            display_df = patrols_df[['id', 'patrol_leader', 'serial_number']].head() if 'serial_number' in patrols_df.columns else patrols_df[['id', 'patrol_leader']].head()
                            st.dataframe(display_df)
                    else:
                        st.warning("No patrols found for the specified date range")
                        
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
                    st.exception(e)
    
    # Show patrol leader filter if patrols downloaded
    if st.session_state.all_patrols is not None and len(st.session_state.patrol_leaders_list) > 0:
        st.markdown("### Filter by Patrol Leader")
        
        selected_leaders = st.multiselect(
            "Select Patrol Leaders",
            options=st.session_state.patrol_leaders_list,
            default=st.session_state.patrol_leaders_list,
            help="Filter patrols by leader. Select one or more leaders.",
            key="selected_patrol_leaders"
        )
        
        if selected_leaders:
            # Filter patrols by selected leaders
            filtered_patrols = st.session_state.all_patrols[st.session_state.all_patrols['patrol_leader'].isin(selected_leaders)]
            st.session_state.bailey_patrols = filtered_patrols
            
            st.info(f"Using {len(filtered_patrols)} patrols from {len(selected_leaders)} leader(s)")
        else:
            st.warning("⚠️ Please select at least one patrol leader")
            st.session_state.bailey_patrols = None
    
    st.markdown("---")
    
    # Step 2: GiraffeSpotter Connection (API Only)
    st.markdown("## 🦒 Step 2: GiraffeSpotter Encounter Data")
    
    st.info("""Download encounter data directly from GiraffeSpotter using the API.
    
**Required:** GiraffeSpotter.org credentials (username and password)
    """)
    
    # Option to include unidentified encounters
    include_unidentified = st.checkbox(
        "Include unidentified encounters",
        value=True,
        help="""When checked, unidentified encounters will be assigned unique IDs and treated as single-capture transients.
This is valid for Bailey's analysis and matches the approach used in the R workflow.

When unchecked, only encounters with identified individuals will be used (stricter filtering).""",
        key="include_unidentified_bailey"
    )
    
    if include_unidentified:
        st.success("✅ Unidentified encounters will be included (each assigned unique ID)")
    else:
        st.warning("⚠️ Only encounters with identified individuals will be used")
    
    # GiraffeSpotter credentials
    col1, col2 = st.columns(2)
    with col1:
        gs_username = st.text_input("GiraffeSpotter Username", key="gs_username_bailey")
    with col2:
        gs_password = st.text_input("GiraffeSpotter Password", type="password", key="gs_password_bailey")
    
    # Location ID filter
    location_id = st.text_input(
        "Location ID (optional)",
        placeholder="e.g., EHGR, Central Tuli",
        help="Filter encounters by location. Leave empty for all locations.",
        key="location_id_bailey"
    )
    
    if st.button("📡 Download from GiraffeSpotter", key="download_gs_bailey", type="primary"):
        if not gs_username or not gs_password:
            st.error("Please enter GiraffeSpotter credentials")
        else:
            with st.spinner("Connecting to GiraffeSpotter..."):
                try:
                    # Initialize client
                    gs_client = GiraffeSpotterClient()
                    
                    # Login
                    if gs_client.login(gs_username, gs_password):
                        st.success("✅ Connected to GiraffeSpotter")
                        
                        # Download encounters with filters
                        with st.spinner(f"Downloading encounters from {start_date} to {end_date}..."):
                            encounters = gs_client.download_encounters(
                                location=location_id.strip() if location_id.strip() else None,
                                start_date=start_date.strftime('%Y-%m-%d'),
                                end_date=end_date.strftime('%Y-%m-%d'),
                                size=2000
                            )
                            
                            if encounters and len(encounters) > 0:
                                # Prepare data for Bailey analysis
                                bailey_data = prepare_bailey_data(encounters, include_unidentified=include_unidentified)
                                
                                if bailey_data is not None and not bailey_data.empty:
                                    st.session_state.bailey_data = bailey_data
                                    st.success(f"✅ Downloaded {len(bailey_data)} encounters with identified individuals")
                                    
                                    # Show date breakdown
                                    date_counts = bailey_data['date'].dt.date.value_counts().sort_index()
                                    st.info("📅 **Encounter Distribution by Date:**")
                                    for date, count in date_counts.items():
                                        st.text(f"  • {date}: {count} encounters")
                                    
                                    if date_counts.min() < 3:
                                        st.warning("⚠️ Some dates have very few encounters. Bailey's analysis works best with 10+ encounters per occasion.")
                                    
                                    with st.expander("📋 Data Preview"):
                                        st.dataframe(bailey_data.head(10))
                                else:
                                    st.warning("⚠️ No valid encounters found. Possible reasons:")
                                    st.write("  • No encounters with identified individuals in the date range")
                                    st.write("  • Encounters missing critical data (individual ID or date)")
                                    st.write("  • Location filter too restrictive")
                            else:
                                st.warning("No encounters found matching the filters")
                    else:
                        st.error("❌ Authentication failed. Please check your credentials.")
                        
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
                    st.exception(e)
    
    st.markdown("---")
    # ============ CRITICAL CHECKPOINT ============
    st.error("🚨 IF YOU SEE THIS, STEP 3 CODE IS LOADING 🚨")
    st.markdown("---")
    st.markdown("# " + "="*50)
    st.markdown("# 📍 STEP 3: SPATIAL MATCHING (REQUIRED)")
    st.markdown("# " + "="*50)
    
    # Check if we have both data sources
    has_encounter_data = 'bailey_data' in st.session_state and st.session_state.bailey_data is not None
    has_patrol_data = 'bailey_patrols' in st.session_state and st.session_state.bailey_patrols is not None
    
    if not has_encounter_data:
        st.error("❌ No encounter data. Complete Step 2 first.")
    elif not has_patrol_data:
        st.error("❌ No patrol data. Complete Step 1 first.")
    elif not PATROL_DOWNLOAD_AVAILABLE:
        st.error("❌ Spatial matching requires geopandas. Install: pip install geopandas ecoscope-release")
    else:
        bailey_data = st.session_state.bailey_data
        patrols_df = st.session_state.bailey_patrols
        
        # Check if already matched
        if 'occasion' in bailey_data.columns:
            n_matched = bailey_data['occasion'].notna().sum()
            n_occasions = bailey_data['occasion'].nunique()
            st.success(f"✅ Already matched! {n_matched} encounters assigned to {n_occasions} occasions")
        else:
            st.info("🗺️ Match encounters to patrol tracks to assign occasion numbers")
        
        # Show patrol lines
        if 'title' in patrols_df.columns:
            st.markdown("### Available Patrol Lines:")
            
            # Build aggregation dict based on available columns
            agg_dict = {'id': 'count'}
            if 'start_time' in patrols_df.columns:
                agg_dict['start_time'] = ['min', 'max']
            
            patrol_groups = patrols_df.groupby('title').agg(agg_dict).reset_index()
            
            # Flatten column names
            if 'start_time' in patrols_df.columns:
                patrol_groups.columns = ['line_name', 'n_patrols', 'first_patrol', 'last_patrol']
            else:
                patrol_groups.columns = ['line_name', 'n_patrols']
            
            st.dataframe(patrol_groups, use_container_width=True)
            
            buffer_meters = st.number_input(
                "Track buffer (meters)",
                min_value=0,
                value=200,
                step=50,
                help="Buffer distance around patrol tracks for spatial matching"
            )
            
            if st.button("🔗 Match Encounters to Patrol Occasions", key="match_encounters", type="primary"):
                with st.spinner("Matching encounters to patrol tracks..."):
                    try:
                        # Extract occasion from title (e.g., "bwa_ctgr_20240423_ew_success1" -> "1")
                        def extract_occasion(title_str):
                            if pd.isna(title_str):
                                return None
                            match = re.search(r'(\d+)\s*$', str(title_str).strip())
                            return match.group(1) if match else None
                        
                        # Extract patrol line geometries from patrol_segments
                        st.info("ℹ️ Extracting patrol line geometries from 'patrol_segments' field...")
                        
                        from shapely.geometry import LineString
                        
                        def extract_patrol_line(row):
                            """Extract full patrol line geometry from patrol_segments"""
                            if 'patrol_segments' not in row or pd.isna(row['patrol_segments']):
                                return None, None, None
                            
                            segments = row['patrol_segments']
                            if not isinstance(segments, list) or len(segments) == 0:
                                return None, None, None
                            
                            first_seg = segments[0]
                            
                            # Extract times
                            start_time = first_seg.get('time_range', {}).get('start_time')
                            end_time = first_seg.get('time_range', {}).get('end_time')
                            
                            # Extract geometry - LineString from start/end locations
                            start_loc = first_seg.get('start_location', {})
                            end_loc = first_seg.get('end_location', {})
                            
                            if start_loc.get('latitude') and start_loc.get('longitude') and \
                               end_loc.get('latitude') and end_loc.get('longitude'):
                                geom = LineString([
                                    (start_loc['longitude'], start_loc['latitude']),
                                    (end_loc['longitude'], end_loc['latitude'])
                                ])
                            else:
                                geom = None
                            
                            return geom, start_time, end_time
                        
                        # Apply extraction
                        patrol_geom_data = patrols_df.apply(extract_patrol_line, axis=1, result_type='expand')
                        patrol_geom_data.columns = ['geometry', 'start_time', 'end_time']
                        
                        patrols_with_geom = pd.concat([patrols_df, patrol_geom_data], axis=1)
                        patrols_with_geom['occasion'] = patrols_with_geom['title'].apply(extract_occasion)
                        
                        # Convert times to datetime
                        patrols_with_geom['start_time'] = pd.to_datetime(patrols_with_geom['start_time'])
                        patrols_with_geom['end_time'] = pd.to_datetime(patrols_with_geom['end_time'])
                        
                        # Show patrol lines info
                        st.info(f"📋 Extracted {len(patrols_with_geom)} patrol lines:")
                        for _, row in patrols_with_geom[['title', 'occasion', 'start_time', 'end_time']].iterrows():
                            st.text(f"  • {row['title'][:40]}... → Occasion {row['occasion']}")
                            st.text(f"     Time: {row['start_time']} to {row['end_time']}")
                        
                        # Create GeoDataFrame of patrol lines
                        patrols_gdf = gpd.GeoDataFrame(
                            patrols_with_geom.dropna(subset=['geometry']), 
                            geometry='geometry', 
                            crs='EPSG:4326'
                        )
                        
                        if patrols_gdf.empty:
                            st.error("❌ Could not extract geometries from patrol_segments")
                        else:
                            # Apply buffer to patrol lines
                            if buffer_meters > 0:
                                patrols_gdf = patrols_gdf.to_crs(3857)  # Convert to meters
                                patrols_gdf['geometry'] = patrols_gdf['geometry'].buffer(buffer_meters)
                                patrols_gdf = patrols_gdf.to_crs(4326)  # Back to WGS84
                                st.info(f"🔵 Applied {buffer_meters}m buffer to patrol lines")
                            
                            # Prepare encounter points
                            bailey_data_with_occasions = bailey_data.copy()
                            
                            # Drop existing occasion column if present
                            if 'occasion' in bailey_data_with_occasions.columns:
                                bailey_data_with_occasions = bailey_data_with_occasions.drop(columns=['occasion'])
                            
                            bailey_data_with_occasions['date'] = pd.to_datetime(bailey_data_with_occasions['date'])
                            bailey_data_with_occasions['enc_date'] = bailey_data_with_occasions['date'].dt.date
                            
                            # Create date-to-occasion mapping from patrol data
                            # Use the DATE from patrol titles (YYYYMMDD in name) as the primary occasion determinant
                            def extract_date_from_title(title):
                                match = re.search(r'(\d{8})', str(title))
                                if match:
                                    date_str = match.group(1)
                                    try:
                                        return pd.to_datetime(date_str, format='%Y%m%d').date()
                                    except:
                                        return None
                                return None
                            
                            patrols_gdf['patrol_date_from_title'] = patrols_gdf['title'].apply(extract_date_from_title)
                            
                            # Map date → occasion (use the most common occasion for each date)
                            date_to_occasion = patrols_gdf.groupby('patrol_date_from_title')['occasion'].agg(
                                lambda x: x.mode()[0] if len(x.mode()) > 0 else x.iloc[0]
                            ).to_dict()
                            
                            st.info("📅 **Date → Occasion Mapping (from patrol titles):**")
                            for date, occ in sorted(date_to_occasion.items()):
                                patrol_count = len(patrols_gdf[patrols_gdf['patrol_date_from_title'] == date])
                                st.text(f"  • {date} → Occasion {occ} ({patrol_count} patrol(s))")
                            
                            # Assign occasions based on date
                            bailey_data_with_occasions['occasion'] = bailey_data_with_occasions['enc_date'].map(date_to_occasion)
                            
                            # Debug: Show encounter date distribution with occasion assignments
                            st.info("🔍 **Encounter Date Distribution with Occasion Assignment:**")
                            enc_dist = bailey_data_with_occasions.groupby(['enc_date', 'occasion']).size().reset_index()
                            enc_dist.columns = ['date', 'occasion', 'count']
                            for _, row in enc_dist.iterrows():
                                occ_str = f"Occasion {row['occasion']}" if pd.notna(row['occasion']) else "NO OCCASION"
                                st.text(f"  • {row['date']} → {occ_str}: {row['count']} encounters")
                            
                            matched = bailey_data_with_occasions[bailey_data_with_occasions['occasion'].notna()].copy()
                            
                            if not matched.empty:
                                st.session_state.bailey_data = matched
                                n_occasions = matched['occasion'].nunique()
                                st.success(f"✅ Matched {len(matched)} encounters to {n_occasions} occasions by date!")
                                
                                # Show summary
                                with st.expander("📋 Occasions Summary", expanded=True):
                                    occasion_summary = matched.groupby('occasion').agg({
                                        'individual_id': ['count', 'nunique']
                                    }).reset_index()
                                    occasion_summary.columns = ['Occasion', 'Encounters', 'Unique Individuals']
                                    occasion_summary = occasion_summary.sort_values('Occasion')
                                    st.dataframe(occasion_summary, use_container_width=True)
                                    
                                    if n_occasions < 3:
                                        st.error(f"⚠️ Only {n_occasions} occasions found. Need at least 3!")
                                        st.info("Check that encounters span at least 3 patrol dates")
                                    else:
                                        st.success(f"✅ {n_occasions} occasions - sufficient for Bailey's analysis!")
                                
                                # Create visualization map
                                if FOLIUM_AVAILABLE:
                                    with st.expander("🗺️ Patrol Lines & Encounters Map", expanded=False):
                                        try:
                                            # Use original (unbuffered) geometries for visualization
                                            patrols_viz = patrols_with_geom.dropna(subset=['geometry']).copy()
                                            
                                            # Calculate center point
                                            all_coords = []
                                            for geom in patrols_viz.geometry:
                                                coords = list(geom.coords)
                                                all_coords.extend(coords)
                                            
                                            if all_coords:
                                                center_lon = sum(c[0] for c in all_coords) / len(all_coords)
                                                center_lat = sum(c[1] for c in all_coords) / len(all_coords)
                                                
                                                # Create map
                                                m = folium.Map(location=[center_lat, center_lon], zoom_start=12)
                                                
                                                # Color mapping for occasions
                                                occasion_colors = {'1': 'red', '2': 'blue', '3': 'green'}
                                                
                                                # Add patrol lines (original, not buffered)
                                                for _, patrol in patrols_viz.iterrows():
                                                    coords = [(lat, lon) for lon, lat in patrol.geometry.coords]
                                                    color = occasion_colors.get(str(patrol['occasion']), 'gray')
                                                    
                                                    folium.PolyLine(
                                                        coords,
                                                        color=color,
                                                        weight=3,
                                                        opacity=0.8,
                                                        popup=f"{patrol['title']}<br>Occasion {patrol['occasion']}"
                                                    ).add_to(m)
                                                
                                                # Add encounter points (all encounters, not just matched)
                                                for _, enc in bailey_data_with_occasions.iterrows():
                                                    if pd.notna(enc['latitude']) and pd.notna(enc['longitude']):
                                                        has_occasion = pd.notna(enc['occasion'])
                                                        color = occasion_colors.get(str(enc.get('occasion', '')), 'gray') if has_occasion else 'black'
                                                        
                                                        folium.CircleMarker(
                                                            location=[enc['latitude'], enc['longitude']],
                                                            radius=5,
                                                            color=color,
                                                            fill=True,
                                                            fillColor=color,
                                                            fillOpacity=0.7,
                                                            popup=f"ID: {enc['individual_id']}<br>Date: {enc['enc_date']}<br>Occasion: {enc.get('occasion', 'None')}"
                                                        ).add_to(m)
                                                
                                                # Add legend
                                                num_encounters = len(bailey_data_with_occasions)
                                                legend_html = f'''
                                                <div style="position: fixed; bottom: 50px; left: 50px; width: 250px; 
                                                background-color: white; border:2px solid grey; z-index:9999; font-size:14px;
                                                padding: 10px">
                                                <p><strong>Legend</strong></p>
                                                <p><span style="color:red;">━━━</span> Occasion 1 Patrols (Apr 23)</p>
                                                <p><span style="color:blue;">━━━</span> Occasion 2 Patrols (Apr 24-25)</p>
                                                <p><span style="color:green;">━━━</span> Occasion 3 Patrols (Apr 25)</p>
                                                <p><span style="color:black;">●</span> Unmatched Encounter</p>
                                                <p><span style="color:red;">●</span> Occasion 1 Encounter</p>
                                                <p><span style="color:blue;">●</span> Occasion 2 Encounter</p>
                                                <p><span style="color:green;">●</span> Occasion 3 Encounter</p>
                                                <p style="margin-top:10px; font-size:12px; color:gray;">
                                                Note: Only shows identified individuals ({num_encounters} of ~98 total)
                                                </p>
                                                </div>
                                                '''
                                                m.get_root().html.add_child(folium.Element(legend_html))
                                                
                                                st_folium(m, width=700, height=500)
                                                
                                                st.info(f"📍 Map shows {len(patrols_viz)} patrol lines and {len(bailey_data_with_occasions)} encounters with identified individuals")
                                                st.warning("⚠️ Black dots = encounters missing April 23 date. Check GiraffeSpotter for unidentified individuals.")
                                        except Exception as e:
                                            st.error(f"Could not create map: {str(e)}")
                                            import traceback
                                            st.code(traceback.format_exc())
                                else:
                                    st.info("📦 Install folium and streamlit-folium to see patrol/encounter map: pip install folium streamlit-folium")
                            else:
                                st.error("❌ No encounters matched to patrol dates")
                                st.info(f"Patrol dates: {sorted(date_to_occasion.keys())}")
                                st.info(f"Encounter dates: {sorted(bailey_data_with_occasions['enc_date'].unique())}")
                    
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
                        st.exception(e)
        else:
            st.error("⚠️ Patrol data missing 'title' column")
            st.write("Available columns:", list(patrols_df.columns))
    
    st.markdown("---")
    st.markdown("# " + "="*50)
    
    # Step 4: Run Bailey's Analysis
    if 'bailey_data' in st.session_state and st.session_state.bailey_data is not None:
        st.markdown("# 📊 STEP 4: RUN BAILEY'S ANALYSIS")
        st.markdown("# " + "="*50)
        
        bailey_data = st.session_state.bailey_data
        
        # Check if occasion matching was completed
        has_occasions = 'occasion' in bailey_data.columns
        has_patrol_data = 'bailey_patrols' in st.session_state and st.session_state.bailey_patrols is not None
        
        if has_patrol_data and not has_occasions:
            st.error("❌ **BLOCKED: Complete Step 3 first!**")
            st.warning("""
            ⚠️ You have patrol data, so you MUST complete Step 3 spatial matching before running Bailey's analysis.
            
            **Why?** The system uses patrol track names to define occasions (e.g., Line1 = Occasion 1).
            Without spatial matching, it would use encounter timestamps as occasions (creating 28+ occasions instead of 3).
            
            **Solution:** Scroll up to Step 3 and click "🔗 Match Encounters to Patrol Occasions"
            """)
            return
        
        occasion_col = 'occasion' if has_occasions else 'date'
        occasion_label = "Occasions" if has_occasions else "Survey Dates"
        
        # Summary
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Encounters", len(bailey_data))
        with col2:
            st.metric("Unique Individuals", bailey_data['individual_id'].nunique())
        with col3:
            st.metric(occasion_label, bailey_data[occasion_col].nunique())
        
        if has_occasions:
            st.success(f"✅ Using patrol-based occasions from Step 3 spatial matching")
        else:
            st.info(f"ℹ️ Using survey dates as occasions (no patrol data)")
        
        # Check if we have enough occasions
        unique_occasions = bailey_data[occasion_col].nunique()
        if unique_occasions < 3:
            st.error(f"❌ Need at least 3 {occasion_label.lower()} for Bailey's Triple Catch. Found: {unique_occasions}")
            if has_occasions:
                st.info("💡 Check that your patrol tracks have at least 3 different occasion numbers")
            else:
                st.info("💡 Download data covering at least 3 separate survey days")
        else:
            # Show occasions/dates
            st.markdown(f"### {occasion_label}:")
            occasion_counts = bailey_data.groupby(occasion_col).size().reset_index(name='encounters')
            occasion_counts = occasion_counts.sort_values(occasion_col)
            st.dataframe(occasion_counts)
            
            # Parameters
            min_captures = st.slider(
                "Minimum captures to classify as 'resident'",
                min_value=2,
                max_value=5,
                value=2,
                help="Individuals with fewer captures are classified as transients"
            )
            
            if st.button("🔬 Run Bailey's Triple Catch Analysis", type="primary", use_container_width=True, key="run_bailey"):
                with st.spinner("Running Bailey's analysis..."):
                    try:
                        # Initialize Bailey analysis with proper occasion column
                        bailey = BaileyAnalysis(bailey_data, occasion_col=occasion_col)
                        
                        # Run analysis
                        results = bailey.bailey_triple_catch(residents_only=True)
                        
                        if results:
                            st.session_state.bailey_results = results
                            st.success("✅ Analysis complete!")
                            
                            # Display results
                            display_bailey_results(results)
                        else:
                            st.error("❌ Could not complete analysis (insufficient recaptures)")
                            
                    except Exception as e:
                        st.error(f"❌ Analysis failed: {str(e)}")
                        st.exception(e)
    else:
        st.info("👆 Please download GiraffeSpotter encounter data to continue")
    
    # Display previous results if available
    if 'bailey_results' in st.session_state and st.session_state.bailey_results is not None:
        if 'bailey_data' not in st.session_state or st.session_state.bailey_data is None:
            st.markdown("---")
            st.markdown("## 📊 Previous Analysis Results")
            display_bailey_results(st.session_state.bailey_results)


def display_bailey_results(results):
    """Display Bailey's Triple Catch analysis results"""
    
    st.markdown("---")
    st.markdown("## 📊 Bailey's Triple Catch Results")
    
    # Main estimate
    st.markdown("### 🦒 Population Estimate")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total Population (N̂)",
            f"{results['total_estimate']['N']:.0f}",
            help="Residents + transients"
        )
    
    with col2:
        st.metric(
            "Resident Estimate",
            f"{results['resident_estimate']['N']:.1f}",
            delta=f"SE: {results['resident_estimate']['SE']:.1f}"
        )
    
    with col3:
        st.metric(
            "Transients",
            f"{results['transients']}"
        )
    
    with col4:
        cv = results['resident_estimate']['CV']
        st.metric(
            "Precision (CV)",
            f"{cv:.1f}%",
            help="Coefficient of Variation - lower is better"
        )
    
    # Confidence interval
    ci_lower = results['resident_estimate']['CI_lower']
    ci_upper = results['resident_estimate']['CI_upper']
    st.info(f"**95% Confidence Interval (residents):** [{ci_lower:.1f}, {ci_upper:.1f}]")
    
    st.markdown("---")
    
    # Classification breakdown
    st.markdown("### 📋 Classification")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Individuals", results['total_individuals'])
    with col2:
        st.metric("Residents (2+ captures)", results['residents'])
    with col3:
        st.metric("Transients (1 capture)", results['transients'])
    
    # Pie chart
    try:
        import matplotlib.pyplot as plt
        
        fig, ax = plt.subplots(figsize=(8, 6))
        
        sizes = [results['residents'], results['transients']]
        labels = [f"Residents\n({results['residents']})", f"Transients\n({results['transients']})"]
        colors = ['#4CAF50', '#FFC107']
        explode = (0.05, 0)
        
        ax.pie(sizes, explode=explode, labels=labels, colors=colors, autopct='%1.1f%%',
               shadow=True, startangle=90, textprops={'fontsize': 12, 'weight': 'bold'})
        ax.axis('equal')
        ax.set_title('Residents vs Transients Classification', fontsize=14, fontweight='bold', pad=20)
        
        st.pyplot(fig)
        
    except:
        pass
    
    st.markdown("---")
    
    # Sample statistics
    st.markdown("### 📊 Sample Statistics")
    
    stats = results['sample_statistics']
    dates = results['dates']
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"**Day 1** ({dates['day1']})")
        st.metric("Individuals", stats['n1'])
    
    with col2:
        st.markdown(f"**Day 2** ({dates['day2']})")
        st.metric("Individuals", stats['n2'])
    
    with col3:
        st.markdown(f"**Day 3** ({dates['day3']})")
        st.metric("Individuals", stats['n3'])
    
    st.markdown("#### Recapture Patterns")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Days 1 & 2", stats['m12'])
    with col2:
        st.metric("Days 1 & 3", stats['m13'])
    with col3:
        st.metric("Days 2 & 3", stats['m23'])
    with col4:
        st.metric("All 3 Days", stats['m123'])
    
    st.markdown("---")
    
    # Chapman estimator details
    with st.expander("🔬 Chapman Estimator Details"):
        st.markdown("""
        ### Chapman's Estimator
        
        This is a modified Petersen estimator for closed populations:
        
        **Formula:**
        ```
        N̂ = [(M + 1)(n + 1) / (m + 1)] - 1
        ```
        
        Where:
        - **M** = Number marked by end of day 2 = n₁ + n₂ - m₁₂
        - **n** = Sample size on day 3 = n₃
        - **m** = Recaptures on day 3 from days 1 or 2 = m₂₃
        
        **Standard Error (Seber 1982):**
        ```
        SE = √[(M+1)(n+1)(M-m)(n-m) / ((m+1)²(m+2))]
        ```
        """)
        
        st.markdown(f"""
        ### This Analysis:
        
        - M (marked by day 2) = {stats['M']}
        - n (sample day 3) = {stats['n3']}
        - m (recaptures day 3) = {stats['m23']}
        - N̂ (resident estimate) = {results['resident_estimate']['N']:.1f}
        - SE = {results['resident_estimate']['SE']:.1f}
        """)
    
    # Method explanation
    with st.expander("📖 Residents-Only Approach"):
        st.markdown("""
        ### Why Residents Only?
        
        The **residents-only approach** improves population estimates when:
        
        1. **Transient individuals** pass through the study area but don't reside there
        2. **Short survey periods** (3-7 days) don't allow time for transients to be recaptured
        3. **Traditional methods** would underestimate population due to transients inflating sample size
        
        ### The Method:
        
        1. **Classify** individuals:
           - Residents: Captured 2+ times (likely live in area)
           - Transients: Captured once (likely passing through)
        
        2. **Apply Chapman's estimator** to residents only
           - This gives an unbiased estimate of the resident population
        
        3. **Add transients** to get total population
           - Assumes all transients were detected (conservative)
        
        ### Assumptions:
        
        - Population is **closed** (no births, deaths, immigration, emigration) during survey
        - All individuals have **equal capture probability** within their class
        - **Marks are not lost** (photo-ID is permanent)
        - Residents and transients are correctly classified
        
        ### When to Use:
        
        ✅ Short-term surveys (3-10 days)  
        ✅ Areas with known transient movement  
        ✅ Multiple survey occasions per day  
        ✅ Good identification success (photo-ID)  
        
        ### References:
        
        - Bailey, N.T.J. (1951). On estimating the size of mobile populations. *Biometrika* 38:293-306.
        - Chapman, D.G. (1951). Some properties of the hypergeometric distribution. *University of California Publications in Statistics* 1:131-160.
        - Seber, G.A.F. (1982). *The Estimation of Animal Abundance and Related Parameters*. 2nd ed. Charles Griffin & Company Ltd.
        """)
    
    # Download results
    st.markdown("---")
    st.markdown("### 💾 Download Results")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # JSON download
        import json
        json_str = json.dumps(results, indent=2)
        st.download_button(
            label="📥 Download Results (JSON)",
            data=json_str,
            file_name=f"bailey_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )
    
    with col2:
        # CSV summary
        summary_df = pd.DataFrame([{
            'Method': results['method'],
            'Total_Individuals': results['total_individuals'],
            'Residents': results['residents'],
            'Transients': results['transients'],
            'Resident_Estimate_N': results['resident_estimate']['N'],
            'Resident_SE': results['resident_estimate']['SE'],
            'Resident_CI_Lower': results['resident_estimate']['CI_lower'],
            'Resident_CI_Upper': results['resident_estimate']['CI_upper'],
            'Total_Estimate_N': results['total_estimate']['N'],
            'Day1': dates['day1'],
            'Day2': dates['day2'],
            'Day3': dates['day3']
        }])
        
        csv = summary_df.to_csv(index=False)
        st.download_button(
            label="📥 Download Summary (CSV)",
            data=csv,
            file_name=f"bailey_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )


if __name__ == "__main__":
    main()

