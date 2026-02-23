"""
Multi-Model SECR Analysis Dashboard
====================================

Spatially-Explicit Capture-Recapture analysis with multiple model comparison.
Uses Murray Efford's 'secr' CRAN package to fit and compare detection function models
(HN, HR, EX) crossed with density and behavioural-response structures.

REQUIRED R PACKAGE: secr  (CRAN — no GitHub compilation needed)
Installation: R -e "install.packages(c('secr','jsonlite'))"

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


# ─────────────────────────────────────────────────────────────────────────────
# R PACKAGE AUTO-INSTALLER
# Runs once per deployment/session (cached). Works locally and on Streamlit Cloud.
# Streamlit Cloud provides R via packages.txt (r-base); this installs secr/jsonlite.
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def ensure_r_packages():
    """Install secr and jsonlite into the current R installation if missing."""
    import subprocess
    import shutil
    import glob

    # Locate Rscript
    rscript = shutil.which('Rscript')
    if not rscript:
        candidates = sorted(
            glob.glob(r'C:\Program Files\R\R-*\bin\Rscript.exe'), reverse=True
        ) + sorted(
            glob.glob(r'C:\Program Files (x86)\R\R-*\bin\Rscript.exe'), reverse=True
        )
        for c in candidates:
            if Path(c).exists():
                rscript = c
                break

    if not rscript:
        return {
            'ok': False,
            'rscript': None,
            'message': 'Rscript not found. Install R from https://www.r-project.org/'
        }

    # Check if both packages are already present (fast path)
    check = subprocess.run(
        [rscript, '--vanilla', '-e',
         "missing <- setdiff(c('secr','jsonlite'), rownames(installed.packages())); "
         "cat(if(length(missing)==0) 'OK' else paste('MISSING', paste(missing, collapse=',')))"],
        capture_output=True, text=True, timeout=30
    )
    if 'OK' in check.stdout:
        return {'ok': True, 'rscript': rscript, 'message': 'R packages already installed'}

    # Install missing packages
    install = subprocess.run(
        [rscript, '--vanilla', '-e',
         "options(repos=c(CRAN='https://cloud.r-project.org'), timeout=600); "
         "pkgs <- setdiff(c('secr','jsonlite'), rownames(installed.packages())); "
         "if(length(pkgs)>0){ cat('Installing:', paste(pkgs,collapse=', '),'\\n'); "
         "install.packages(pkgs, quiet=FALSE) }; "
         "ok <- all(c('secr','jsonlite') %in% rownames(installed.packages())); "
         "cat(if(ok) 'INSTALL_OK' else 'INSTALL_FAILED', '\\n')"],
        capture_output=True, text=True, timeout=600
    )

    success = 'INSTALL_OK' in install.stdout
    msg = install.stdout.strip() + ('\n' + install.stderr.strip() if install.stderr.strip() else '')
    return {'ok': success, 'rscript': rscript, 'message': msg}


def main():
    """Main Streamlit app"""
    
    # Page title
    st.title("📊 Multi-Model SECR Analysis")
    st.caption("Build: 2026-02-21-MULTI-MODEL-v1")
    st.markdown("*Spatially-Explicit Capture-Recapture with Detection Function Comparison*")
    st.markdown("---")
    
    # Introduction
    st.markdown("""
    ### 🦒 Multiple SECR Models Comparison
    
    **Compare detection function models to find the best fit**
    
    This analysis:
    1. Downloads patrol tracks from EarthRanger (survey effort)
    2. Downloads encounter data from GiraffeSpotter
    3. Matches encounters to patrol occasions (spatial-temporal)
    4. Fits multiple SECR models — detection function × g0 structure:
       - **HN** (Half-normal) × null / time / behavioural response
       - **HR** (Hazard-rate) × null / time / behavioural response
       - **EX** (Exponential) × null / time / behavioural response
    5. Compares **9+ models by AICc** and computes Akaike weights
    6. Reports model-averaged population estimate + best-model CIs
    
    **Package:** Murray Efford's `secr` (CRAN) — installs in seconds, no GitHub required
    """)
    
    # ── R environment check (runs once, cached) ─────────────────────────────────
    with st.spinner("🔧 Checking R environment — first run installs secr (~2 min on cold start)..."):
        r_env = ensure_r_packages()

    if not r_env['ok']:
        st.error(f"❌ R not ready: {r_env['message']}")
        st.markdown("""
        **Install R** from https://www.r-project.org/ then open R and run:
        ```r
        install.packages(c('secr', 'jsonlite'))
        ```
        Then refresh this page.
        """)
        return
    else:
        label = '✅ R ready' if 'already' in r_env['message'] else '✅ secr installed'
        st.success(f"{label} — `{Path(r_env['rscript']).parent.parent.name}`")

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
    
    # Initialize session state for multi-model SECR analysis
    if 'secr_results' not in st.session_state:
        st.session_state.secr_results = None
    if 'secr_data' not in st.session_state:
        st.session_state.secr_data = None
    if 'secr_patrols' not in st.session_state:
        st.session_state.secr_patrols = None
    if 'all_patrols' not in st.session_state:
        st.session_state.all_patrols = None
    if 'patrol_leaders_list' not in st.session_state:
        st.session_state.patrol_leaders_list = []
    
    # ===== MULTI-MODEL SECR ANALYSIS =====
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
            st.session_state.secr_patrols = filtered_patrols
            
            st.info(f"Using {len(filtered_patrols)} patrols from {len(selected_leaders)} leader(s)")
        else:
            st.warning("⚠️ Please select at least one patrol leader")
            st.session_state.secr_patrols = None
    
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
                                secr_data = prepare_bailey_data(encounters, include_unidentified=include_unidentified)
                                
                                if secr_data is not None and not secr_data.empty:
                                    # --- Project lat/lon → metric x/y for SECR ---
                                    has_latlon = ('latitude' in secr_data.columns and
                                                  'longitude' in secr_data.columns and
                                                  secr_data['latitude'].notna().any())
                                    if has_latlon:
                                        try:
                                            import math
                                            # Equirectangular projection — accurate to <1% over survey areas up to ~200 km
                                            valid = secr_data['latitude'].notna() & secr_data['longitude'].notna()
                                            lat_ref = float(secr_data.loc[valid, 'latitude'].mean())
                                            lon_ref = float(secr_data.loc[valid, 'longitude'].mean())
                                            M = 111319.9  # metres per degree latitude
                                            cos_lat = math.cos(math.radians(lat_ref))
                                            secr_data['x'] = np.where(
                                                valid,
                                                (secr_data['longitude'] - lon_ref) * cos_lat * M,
                                                np.nan
                                            )
                                            secr_data['y'] = np.where(
                                                valid,
                                                (secr_data['latitude'] - lat_ref) * M,
                                                np.nan
                                            )
                                            st.info(f"📍 Coordinates projected to metres (ref: {lat_ref:.4f}°, {lon_ref:.4f}°)")
                                        except Exception as proj_err:
                                            st.warning(f"⚠️ Could not project coordinates: {proj_err}. Using raw lat/lon (density unreliable).")
                                            secr_data['x'] = secr_data['longitude']
                                            secr_data['y'] = secr_data['latitude']
                                    
                                    st.session_state.secr_data = secr_data
                                    st.success(f"✅ Downloaded {len(secr_data)} encounters with identified individuals")
                                    
                                    # Show date breakdown
                                    date_counts = secr_data['date'].dt.date.value_counts().sort_index()
                                    st.info("📅 **Encounter Distribution by Date:**")
                                    for date, count in date_counts.items():
                                        st.text(f"  • {date}: {count} encounters")
                                    
                                    if date_counts.min() < 3:
                                        st.warning("⚠️ Some dates have very few encounters. SECR analysis works best with 5+ encounters per occasion.")
                                    
                                    with st.expander("📋 Data Preview"):
                                        st.dataframe(secr_data.head(10))
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
    st.markdown("# " + "="*50)
    st.markdown("# 📍 STEP 3: SPATIAL MATCHING (REQUIRED)")
    st.markdown("# " + "="*50)
    
    # Check if we have both data sources
    has_encounter_data = 'secr_data' in st.session_state and st.session_state.secr_data is not None
    has_patrol_data = 'secr_patrols' in st.session_state and st.session_state.secr_patrols is not None
    
    if not has_encounter_data:
        st.error("❌ No encounter data. Complete Step 2 first.")
    elif not has_patrol_data:
        st.error("❌ No patrol data. Complete Step 1 first.")
    elif not PATROL_DOWNLOAD_AVAILABLE:
        st.error("❌ Spatial matching requires geopandas. Install: pip install geopandas ecoscope-release")
    else:
        secr_data = st.session_state.secr_data
        patrols_df = st.session_state.secr_patrols
        
        # Check if already matched
        if 'occasion' in secr_data.columns:
            n_matched = secr_data['occasion'].notna().sum()
            n_occasions = secr_data['occasion'].nunique()
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
                            secr_data_with_occasions = secr_data.copy()
                            
                            # Drop existing occasion column if present
                            if 'occasion' in secr_data_with_occasions.columns:
                                secr_data_with_occasions = secr_data_with_occasions.drop(columns=['occasion'])
                            
                            secr_data_with_occasions['date'] = pd.to_datetime(secr_data_with_occasions['date'])
                            secr_data_with_occasions['enc_date'] = secr_data_with_occasions['date'].dt.date
                            
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
                            secr_data_with_occasions['occasion'] = secr_data_with_occasions['enc_date'].map(date_to_occasion)
                            
                            # Debug: Show encounter date distribution with occasion assignments
                            st.info("🔍 **Encounter Date Distribution with Occasion Assignment:**")
                            enc_dist = secr_data_with_occasions.groupby(['enc_date', 'occasion']).size().reset_index()
                            enc_dist.columns = ['date', 'occasion', 'count']
                            for _, row in enc_dist.iterrows():
                                occ_str = f"Occasion {row['occasion']}" if pd.notna(row['occasion']) else "NO OCCASION"
                                st.text(f"  • {row['date']} → {occ_str}: {row['count']} encounters")
                            
                            matched = secr_data_with_occasions[secr_data_with_occasions['occasion'].notna()].copy()
                            
                            if not matched.empty:
                                st.session_state.secr_data = matched
                                st.session_state.secr_patrols = patrols_gdf
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
                                    
                                    if n_occasions < 2:
                                        st.error(f"⚠️ Only {n_occasions} occasions found. Need at least 2!")
                                        st.info("Check that encounters span multiple patrol dates")
                                    else:
                                        st.success(f"✅ {n_occasions} occasions - sufficient for SECR analysis!")
                                
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
                                                for _, enc in secr_data_with_occasions.iterrows():
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
                                                num_encounters = len(secr_data_with_occasions)
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
                                                
                                                st.info(f"📍 Map shows {len(patrols_viz)} patrol lines and {len(secr_data_with_occasions)} encounters with identified individuals")
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
                                st.info(f"Encounter dates: {sorted(secr_data_with_occasions['enc_date'].unique())}")
                    
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
                        st.exception(e)
        else:
            st.error("⚠️ Patrol data missing 'title' column")
            st.write("Available columns:", list(patrols_df.columns))
    
    st.markdown("---")
    st.markdown("# " + "="*50)
    
    # Step 4: Run SECR Multi-Model Analysis
    if 'secr_data' in st.session_state and st.session_state.secr_data is not None:
        st.markdown("# 📊 STEP 4: RUN SECR MULTI-MODEL ANALYSIS")
        st.markdown("# " + "="*50)
        
        secr_data = st.session_state.secr_data
        
        # Check if occasion matching was completed
        has_occasions = 'occasion' in secr_data.columns
        has_patrol_data = 'secr_patrols' in st.session_state and st.session_state.secr_patrols is not None
        
        if has_patrol_data and not has_occasions:
            st.error("❌ **BLOCKED: Complete Step 3 first!**")
            st.warning("""
            ⚠️ You have patrol data, so you MUST complete Step 3 spatial matching before running SECR analysis.
            
            **Why?** The system uses patrol track names to define occasions (e.g., Line1 = Occasion 1).
            Without spatial matching, it would use encounter timestamps as occasions (creating many occasions instead of few).
            
            **Solution:** Scroll up to Step 3 and click "🔗 Match Encounters to Patrol Occasions"
            """)
            return
        
        occasion_col = 'occasion' if has_occasions else 'date'
        occasion_label = "Occasions" if has_occasions else "Survey Dates"
        
        # Summary
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Captures", len(secr_data), help="Number of individual detections")
        with col2:
            st.metric("Unique Individuals", secr_data['individual_id'].nunique(), help="Number of identified subjects")
        with col3:
            st.metric(occasion_label, secr_data[occasion_col].nunique(), help="Number of survey occasions")
        with col4:
            if 'x' in secr_data.columns and 'y' in secr_data.columns:
                n_locations = len(secr_data[['x', 'y']].drop_duplicates())
                st.metric("Detector Locations", n_locations, help="Number of unique capture locations")
        
        if has_occasions:
            st.success(f"✅ Using patrol-based occasions from Step 3 spatial matching")
        else:
            st.info(f"ℹ️ Using survey dates as occasions (no patrol data)")
        
        # Check if we have enough occasions
        unique_occasions = secr_data[occasion_col].nunique()
        if unique_occasions < 2:
            st.error(f"❌ Need at least 2 {occasion_label.lower()} for SECR analysis. Found: {unique_occasions}")
            st.info("💡 Download data covering at least 2 separate survey occasions")
        else:
            # Show occasions distribution
            st.markdown(f"### {occasion_label} Distribution:")
            occasion_counts = secr_data.groupby(occasion_col).size().reset_index(name='captures')
            occasion_counts = occasion_counts.sort_values(occasion_col)
            
            # Create capture history summary
            ch_summary = secr_data.groupby([occasion_col, 'individual_id']).size().unstack(fill_value=0)
            st.dataframe(occasion_counts, use_container_width=True)
            
            st.markdown("**Models to Fit:**")
            st.info("""
            Will compare up to **9 models** (detection function × g0 structure):
            
            | Detection function | Null | Time-varying | Behavioural response |
            |---|---|---|---|
            | **HN** Half-normal: g(d) = g₀·exp(−d²/2σ²) | ✓ | ✓ | ✓ |
            | **HR** Hazard-rate: 1−exp(−(d/σ)−z) | ✓ | ✓ | ✓ |
            | **EX** Exponential: g(d) = g₀·exp(−d/σ) | ✓ | ✓ | ✓ |
            
            Models ranked by **AICc** with Akaike weights. Model-averaged N̂ also reported.
            """)
            
            # Run models button
            r_env = ensure_r_packages()  # guaranteed cached — instant
            if not r_env['ok']:
                st.error("❌ R is not available — see banner at top of page")
            elif st.button("🚀 Fit SECR Models (Compare Detection Functions)", type="primary", use_container_width=True, key="run_oscr"):
                with st.spinner("Fitting SECR models (this may take 1–3 minutes)..."):
                    try:
                        import tempfile
                        import json
                        import subprocess
                        
                        # Prepare data for R (secr format)
                        with tempfile.TemporaryDirectory() as tmpdir:
                            tmpdir = Path(tmpdir)
                            
                            individuals = sorted(secr_data['individual_id'].unique())
                            occasions   = sorted(secr_data[occasion_col].unique())
                            occ_map     = {o: i + 1 for i, o in enumerate(occasions)}  # 1-indexed
                            
                            # Build trap lookup: unique (x,y) → trap_id
                            has_xy = 'x' in secr_data.columns and 'y' in secr_data.columns
                            if has_xy:
                                traps_xy = secr_data[['x', 'y']].drop_duplicates().reset_index(drop=True)
                                traps_xy.index = traps_xy.index + 1  # 1-indexed trap IDs
                                trap_key = {(r.x, r.y): idx for idx, r in traps_xy.iterrows()}

                                # captures.csv: Session, ID, Occasion, Detector
                                cap_rows = []
                                for _, row in secr_data.iterrows():
                                    det_id = trap_key.get((row['x'], row['y']), 1)
                                    cap_rows.append({
                                        'Session':  'S1',
                                        'ID':       str(row['individual_id']),
                                        'Occasion': occ_map[row[occasion_col]],
                                        'Detector': det_id
                                    })
                                pd.DataFrame(cap_rows).to_csv(tmpdir / 'captures.csv', index=False)

                                # traps.csv: Detector, x, y
                                traps_out = traps_xy.copy()
                                traps_out.index.name = 'Detector'
                                traps_out.reset_index().to_csv(tmpdir / 'traps.csv', index=False)
                            else:
                                # No x/y — stop and tell user to re-download
                                st.error("❌ No coordinate data found in encounter records.")
                                st.warning("""
                                **Action required:** Your GiraffeSpotter encounters are missing GPS coordinates,
                                or the data was downloaded before the coordinate fix was applied.

                                **Please go back to Step 2 and re-download the encounters.**
                                SECR requires real spatial coordinates — a dummy grid cannot produce
                                meaningful density or abundance estimates.
                                """)
                                st.stop()

                            # Call R script
                            r_script = Path(__file__).parent / "secr_multi_model.R"
                            
                            if not r_script.exists():
                                st.error(f"❌ R script not found: {r_script}")
                                st.info("Make sure secr_multi_model.R is in the secr_analysis directory")
                                st.info(f"**Expected location:** {r_script}")
                            else:
                                # Run R script
                                output_dir = tmpdir / "results"
                                output_dir.mkdir()
                                
                                # Use the already-verified Rscript path from ensure_r_packages()
                                rscript_cmd = r_env['rscript']
                                cmd = [rscript_cmd, str(r_script), str(tmpdir), str(output_dir)]
                                
                                st.info(f"🔧 Running R SECR analysis (may take 1–5 minutes)...")
                                st.code(f"Command: {rscript_cmd} secr_multi_model.R")
                                
                                # Write stdout/stderr to temp files to avoid Windows pipe-buffer deadlock
                                stdout_file = tmpdir / "r_stdout.txt"
                                stderr_file = tmpdir / "r_stderr.txt"
                                with open(stdout_file, 'w') as fout, open(stderr_file, 'w') as ferr:
                                    proc = subprocess.run(cmd, stdout=fout, stderr=ferr, timeout=600)
                                stdout_txt = stdout_file.read_text(errors='replace')
                                stderr_txt = stderr_file.read_text(errors='replace')
                                
                                class _result:
                                    returncode = proc.returncode
                                    stdout = stdout_txt
                                    stderr = stderr_txt
                                result = _result()
                                
                                if result.returncode != 0:
                                    st.error("❌ R script failed")
                                    st.warning("**R stderr:**")
                                    st.code(result.stderr)
                                    st.warning("**R stdout:**")
                                    st.code(result.stdout)
                                    st.info(f"**Full command:** {' '.join(cmd)}")
                                    # The auto-installer should have caught this, but just in case:
                                    if "there is no package called 'secr'" in result.stderr:
                                        st.error("⚠️ secr package missing from R library. "
                                                 "Clear the Streamlit cache and reload to re-run the installer.")
                                else:
                                    # Load results
                                    results_file = output_dir / "secr_results.json"
                                    aic_file = output_dir / "aic_table.csv"
                                        
                                    if results_file.exists() and aic_file.exists():
                                        with open(results_file) as f:
                                            results_dict = json.load(f)
                                        
                                        aic_df = pd.read_csv(aic_file)
                                        
                                        # Store results
                                        st.session_state.secr_results = {
                                            'results_dict': results_dict,
                                            'aic_table': aic_df
                                        }
                                        
                                        st.success("✅ Model fitting complete!")
                                        st.balloons()
                                        
                                    else:
                                        st.error("❌ Could not load results from R")
                                        st.info(f"Expected files not found in {output_dir}")
                                    
                    except Exception as e:
                        st.error(f"❌ Analysis failed: {str(e)}")
                        st.exception(e)

    else:
        st.info("👆 Please download and prepare GiraffeSpotter encounter data to continue")
    
    # Display results if available
    if 'secr_results' in st.session_state and st.session_state.secr_results is not None:
        display_oscr_results(st.session_state.secr_results)


def display_oscr_results(results):
    """Display oSCR multi-model analysis results"""
    
    results_dict = results.get('results_dict', {})
    aic_table = results.get('aic_table')
    
    if aic_table is None:
        st.error("No results available")
        return
    
    # Import visualization functions
    from secr_analysis.oscr_visualization import (
        display_model_comparison_table,
        plot_model_aic_comparison,
        plot_delta_aicc,
        display_best_model_summary,
        display_model_uncertainty,
        display_analysis_summary,
        export_results_buttons
    )
    
    st.markdown("---")
    st.markdown("# 📊 SECR Multi-Model Results")
    st.markdown("Spatially Explicit Capture-Recapture Analysis (Efford `secr` package)")
    
    # Summary statistics
    display_analysis_summary(results_dict)

    # ── Population estimate (top of page) ──────────────────────────────────
    pop = results_dict.get('population_estimate', {})
    n_hat = pop.get('N_hat')
    n_lcl = pop.get('N_lcl')
    n_ucl = pop.get('N_ucl')
    ma_n  = results_dict.get('model_averaged_N')
    g0    = pop.get('g0')
    sigma = pop.get('sigma')

    st.markdown("---")
    st.markdown("### 🦒 Population Estimate")
    pe1, pe2, pe3, pe4 = st.columns(4)
    with pe1:
        st.metric("N̂ (best model)",
                  f"{n_hat:,.0f}" if n_hat and not str(n_hat) == 'nan' else "—")
    with pe2:
        if n_lcl and n_ucl and str(n_lcl) != 'nan':
            st.metric("95% CI", f"{n_lcl:,.0f} – {n_ucl:,.0f}")
        else:
            st.metric("95% CI", "—")
    with pe3:
        st.metric("Model-averaged N̂",
                  f"{ma_n:,.0f}" if ma_n and str(ma_n) != 'nan' else "—")
    with pe4:
        st.metric("Best model", results_dict.get('best_model', '—'))

    dp1, dp2 = st.columns(2)
    with dp1:
        st.metric("g₀ (baseline detection)",
                  f"{g0:.4f}" if g0 and str(g0) != 'nan' else "—")
    with dp2:
        st.metric("σ (detection range, m)",
                  f"{sigma:.1f}" if sigma and str(sigma) != 'nan' else "—")

    st.markdown("---")
    
    # Model comparison table
    display_model_comparison_table(aic_table)
    
    st.markdown("---")
    
    # Visualizations
    st.markdown("### 📈 Model Comparison Visualizations")
    plot_model_aic_comparison(aic_table)
    
    st.markdown("---")
    
    plot_delta_aicc(aic_table)
    
    st.markdown("---")
    
    # Best model details
    display_best_model_summary(results_dict)
    
    st.markdown("---")
    
    # Model uncertainty
    display_model_uncertainty(aic_table)
    
    st.markdown("---")
    
    # Download results
    export_results_buttons(results_dict, aic_table)
    
    # Additional information
    st.markdown("---")
    st.markdown("### 📚 About SECR & Model Comparison")
    
    with st.expander("What is SECR?", expanded=False):
        st.markdown("""
        **Spatially-Explicit Capture-Recapture (SECR)**
        
        SECR is a statistical method for estimating animal population densities using 
        captures/detections at known locations (e.g., camera traps, photo-ID, mark-recapture).
        
        Key features:
        - Uses spatial information (location of detections)
        - Estimates density (individuals per unit area)
        - Accounts for detection probability declining with distance
        - Flexible to different detection function shapes
        
        **Advantages over traditional CR:**
        - Better population estimates in open populations
        - Estimates population density directly
        - Uses spatial information for better inference
        - Can incorporate covariates on density and detection
        """)
    
    with st.expander("Why compare models?", expanded=False):
        st.markdown("""
        **Model Selection & Comparison**
        
        Different detection functions (HN, EX, UF, HZ) may fit the data differently:
        
        1. **Half-normal (HN)** - Standard, gaussian shape, most commonly used
        2. **Exponential (EX)** - More gradual decline with distance
        3. **Uniform hazard (UF)** - Good for live trapping, cumulative hazard
        4. **Hazard-rate (HZ)** - More flexible with shape parameter
        
        **Why AICc?**
        - AIC: Balances fit vs complexity
        - AICc: AIC corrected for small sample sizes (preferred)
        - AICc weight: Probability model is best given the data
        
        **Model averaging:**
        - If multiple models have similar support (ΔAICc < 2)
        - Can average predictions across models
        - Accounts for model uncertainty in final estimates
        """)
    
    with st.expander("Next steps", expanded=False):
        st.markdown("""
        **After selecting the best model:**
        
        1. **Check diagnostics**
           - Fit plots (observed vs predicted captures)
           - Residual analysis
        
        2. **Extract estimates**
           - Density (individuals per unit area)
           - Detection parameters (g0, sigma)
           - Confidence intervals
        
        3. **Make predictions**
           - Population size for whole area
           - Uncertainty bounds
        
        4. **Validate assumptions**
           - Equal catchability within class
           - Closed population
           - Accurate coordinate recording
        
        **For more info:**
        - Royle et al. (2014) "Spatial Capture-Recapture"
        - Efford et al. SECR package documentation
        - GitHub: jaroyle/oSCR
        """)

