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
from datetime import datetime

# Add parent directory to path for shared utilities
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.append(str(parent_dir))

# Try to import SECR workflow components
try:
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
    st.caption("Build: 2026-02-18-STEP3-FIX-v5-PWSH")
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
                                bailey_data = prepare_bailey_data(encounters)
                                
                                if bailey_data is not None and not bailey_data.empty:
                                    st.session_state.bailey_data = bailey_data
                                    st.success(f"✅ Downloaded {len(bailey_data)} encounters")
                                    
                                    with st.expander("📋 Data Preview"):
                                        st.dataframe(bailey_data.head(10))
                                else:
                                    st.warning("No valid encounters found after filtering")
                            else:
                                st.warning("No encounters found matching the filters")
                    else:
                        st.error("❌ Authentication failed. Please check your credentials.")
                        
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
                    st.exception(e)
    
    st.markdown("---")
    
    # Step 3: Run Bailey's Analysis
    if 'bailey_data' in st.session_state and st.session_state.bailey_data is not None:
        st.markdown("## 📊 Step 3: Run Bailey's Analysis")
        
        bailey_data = st.session_state.bailey_data
        
        # Summary
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Encounters", len(bailey_data))
        with col2:
            st.metric("Unique Individuals", bailey_data['individual_id'].nunique())
        with col3:
            st.metric("Survey Dates", bailey_data['date'].nunique())
        
        # Check if we have enough data
        unique_dates = bailey_data['date'].nunique()
        if unique_dates < 3:
            st.warning(f"⚠️ Need at least 3 survey dates for Bailey's Triple Catch. Found: {unique_dates}")
            st.info("Please download data covering at least 3 separate survey days")
        else:
            # Show survey dates
            st.markdown("### Survey Dates:")
            date_counts = bailey_data.groupby('date').size().reset_index(name='encounters')
            date_counts = date_counts.sort_values('date')
            st.dataframe(date_counts)
            
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
                        # Initialize Bailey analysis
                        bailey = BaileyAnalysis(bailey_data)
                        
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

