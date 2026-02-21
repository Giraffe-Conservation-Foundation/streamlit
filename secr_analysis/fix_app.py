#!/usr/bin/env python3
"""Script to fix app.py by replacing lines 127-330"""

# Read the original file
with open(r"g:\My Drive\Data management\streamlit\secr_analysis\app.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

# Lines 1-126 (keep as is - indices 0-125)
part1 = lines[0:126]

# New clean code to replace lines 127-330
new_code = '''    if st.button("📡 Download Patrol Data", key="download_patrols_bailey", type="primary"):
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
                        
                        # Show preview
                        with st.expander("📋 Patrol Preview"):
                            display_df = patrols_df[['id', 'patrol_leader', 'serial_number']].head(10) if 'serial_number' in patrols_df.columns else patrols_df[['id', 'patrol_leader']].head(10)
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
    
    # Step 2: GiraffeSpotter Connection (file upload only)
    st.markdown("## 🦒 Step 2: GiraffeSpotter Encounter Data")
    
    st.info("""Upload the GiraffeSpotter encounter export file for the same survey period.
    
**How to export from GiraffeSpotter:**
1. Go to https://giraffespotter.org → Search → Encounter Search
2. Set your filters (location, date range)
3. Click Export → Encounter Annotation Export
4. Upload the file below
    """)
    
    # Hardcode GiraffeSpotter URL (no API access, file upload only)
    wildbook_url = "https://giraffespotter.org"
    
    # Location ID filter
    location_id = st.text_input(
        "Location ID (optional)",
        placeholder="e.g., EHGR, Central Tuli",
        help="Filter encounters by location. Leave empty for all locations.",
        key="location_id_bailey"
    )
    
    bailey_data = None
    
    uploaded_file = st.file_uploader(
        "Upload GiraffeSpotter Encounter Export (.xlsx or .csv)",
        type=['xlsx', 'xls', 'csv'],
        key="bailey_wb_upload"
    )
    
    if uploaded_file:
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as tmp:
                tmp.write(uploaded_file.getvalue())
                tmp_path = tmp.name
            
            wildbook_df = load_wildbook_export(tmp_path)
            os.unlink(tmp_path)
            
            if wildbook_df is not None:
                # Filter by location if specified
                if location_id.strip() and 'Encounter.locationID' in wildbook_df.columns:
                    wildbook_df = wildbook_df[wildbook_df['Encounter.locationID'] == location_id.strip()]
                    if wildbook_df.empty:
                        st.warning(f"No encounters found for location: {location_id}")
                    else:
                        st.info(f"Filtered to {len(wildbook_df)} encounters at location: {location_id}")
                
                # Filter by date range (same as patrols)
                if 'Encounter.verbatimEventDate' in wildbook_df.columns:
                    wildbook_df['date_parsed'] = pd.to_datetime(wildbook_df['Encounter.verbatimEventDate'], errors='coerce')
                    wildbook_df = wildbook_df[wildbook_df['date_parsed'].notna()]
                    
                    start_dt = pd.Timestamp(start_date)
                    end_dt = pd.Timestamp(end_date)
                    
                    wildbook_df = wildbook_df[
                        (wildbook_df['date_parsed'] >= start_dt) &
                        (wildbook_df['date_parsed'] <= end_dt)
                    ]
                    
                    if wildbook_df.empty:
                        st.warning(f"No encounters found in date range: {start_date} to {end_date}")
                    else:
                        st.info(f"Filtered to {len(wildbook_df)} encounters in date range")
                
                if not wildbook_df.empty:
                    bailey_data = prepare_bailey_data(wildbook_df)
                    if bailey_data is not None:
                        st.session_state.bailey_data = bailey_data
                        st.success(f"✅ Loaded {len(bailey_data)} encounters")
                        
                        with st.expander("📋 Data Preview"):
                            st.dataframe(bailey_data.head())
                        
        except Exception as e:
            st.error(f"❌ Error loading file: {str(e)}")
            st.exception(e)

    st.markdown("---")
'''

# Lines 330-641 (keep as is - indices 329-640)
part3 = lines[329:]

# Combine all parts (split new_code into lines with newlines)
new_code_lines = [line + '\n' for line in new_code.split('\n')]
combined = part1 + new_code_lines + part3

# Write the corrected file
with open(r"g:\My Drive\Data management\streamlit\secr_analysis\app.py", "w", encoding="utf-8") as f:
    f.writelines(combined)

print("File corrected successfully!")
