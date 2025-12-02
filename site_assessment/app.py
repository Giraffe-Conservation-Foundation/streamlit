"""
Site Assessment Dashboard
Evaluate potential giraffe translocation sites using satellite imagery and environmental data
"""

import streamlit as st
import sys
from pathlib import Path
import pandas as pd
import geopandas as gpd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np
from shapely.geometry import Polygon, mapping
import folium
from streamlit_folium import st_folium
import json

# Add shared utilities
current_dir = Path(__file__).parent.parent
sys.path.append(str(current_dir))

def main():
    st.set_page_config(
        page_title="Site Assessment - GCF",
        page_icon="🌍",
        layout="wide"
    )
    
    st.title("🌍 Site Assessment for Giraffe Translocation")
    st.markdown("*Evaluate habitat suitability using satellite imagery and environmental data*")
    
    # NDVI thresholds for giraffe habitat
    NDVI_THRESHOLDS = {
        'Poor': (0.0, 0.2, '❌', '#d32f2f'),
        'Marginal': (0.2, 0.3, '⚠️', '#f57c00'),
        'Suitable': (0.3, 0.5, '✔️', '#388e3c'),
        'Optimal': (0.5, 1.0, '✅', '#1b5e20')
    }
    
    def assess_habitat_suitability(mean_ndvi):
        """Assess habitat suitability based on NDVI"""
        for category, (low, high, emoji, color) in NDVI_THRESHOLDS.items():
            if low <= mean_ndvi < high:
                return category, emoji, color
        return 'Unknown', '❓', '#757575'
    
    def get_sentinel2_ndvi_mock(polygon, start_date, end_date):
        """
        Mock function for Sentinel-2 NDVI data
        Replace with actual Microsoft Planetary Computer integration when API keys are configured
        """
        # Calculate center of polygon for mock data variation
        centroid = polygon.centroid
        lat_factor = (centroid.y + 90) / 180  # Normalize latitude
        
        # Generate realistic mock NDVI based on location
        base_ndvi = 0.25 + (lat_factor * 0.3)  # Varies by latitude
        mean_ndvi = base_ndvi + np.random.uniform(-0.05, 0.05)
        std_ndvi = np.random.uniform(0.05, 0.15)
        
        # Mock NDVI array for heatmap
        ndvi_array = np.random.normal(mean_ndvi, std_ndvi, (100, 100))
        ndvi_array = np.clip(ndvi_array, -0.2, 1.0)
        
        return {
            'ndvi_array': ndvi_array,
            'mean_ndvi': float(mean_ndvi),
            'std_ndvi': float(std_ndvi),
            'min_ndvi': float(np.min(ndvi_array)),
            'max_ndvi': float(np.max(ndvi_array)),
            'date': end_date,
            'cloud_cover': np.random.uniform(5, 15),
            'is_mock': True
        }
    
    # Sidebar configuration
    st.sidebar.header("⚙️ Assessment Settings")
    
    # Date range selection
    st.sidebar.subheader("📅 Time Period")
    end_date = st.sidebar.date_input(
        "End Date",
        value=datetime.now(),
        max_value=datetime.now()
    )
    
    start_date = st.sidebar.date_input(
        "Start Date",
        value=end_date - timedelta(days=90),
        max_value=end_date
    )
    
    # NDVI threshold customization
    st.sidebar.subheader("🌱 NDVI Thresholds")
    with st.sidebar.expander("Customize Thresholds"):
        st.markdown("""
        **Default thresholds for giraffe habitat:**
        - Optimal: 0.5 - 1.0
        - Suitable: 0.3 - 0.5
        - Marginal: 0.2 - 0.3
        - Poor: 0.0 - 0.2
        """)
    
    # Main content tabs
    tab1, tab2, tab3 = st.tabs(["📍 Define Site", "📊 Analysis Results", "📚 Guide"])
    
    with tab1:
        st.subheader("Define Assessment Area")
        
        # Method selection
        input_method = st.radio(
            "How would you like to define the site?",
            ["🗺️ Draw on Map", "📁 Upload Shapefile", "📝 Enter Coordinates"],
            horizontal=True
        )
        
        polygon = None
        site_name = st.text_input("Site Name (optional)", placeholder="e.g., Iona National Park - North Sector")
        
        if input_method == "🗺️ Draw on Map":
            st.info("👇 Click on the map to draw a polygon. Double-click to complete.")
            
            # Create a map centered on Africa
            m = folium.Map(
                location=[-2.0, 20.0],  # Center of Africa
                zoom_start=4,
                tiles='OpenStreetMap'
            )
            
            # Add drawing tools
            draw = folium.plugins.Draw(
                export=False,
                draw_options={
                    'polyline': False,
                    'rectangle': True,
                    'circle': False,
                    'marker': False,
                    'circlemarker': False,
                    'polygon': True
                }
            )
            draw.add_to(m)
            
            # Display map
            map_data = st_folium(m, width=700, height=500, key="site_map")
            
            # Extract drawn polygon
            if map_data and map_data.get('all_drawings'):
                drawings = map_data['all_drawings']
                if drawings:
                    last_drawing = drawings[-1]
                    
                    if last_drawing['geometry']['type'] == 'Polygon':
                        coords = last_drawing['geometry']['coordinates'][0]
                        # Convert to shapely polygon (swap lat/lon)
                        polygon = Polygon([(lon, lat) for lon, lat in coords])
                        
                        area_km2 = polygon.area * 111 * 111  # Rough conversion to km²
                        st.success(f"✅ Polygon created: ~{area_km2:.2f} km² area")
                    
                    elif last_drawing['geometry']['type'] == 'Rectangle':
                        coords = last_drawing['geometry']['coordinates'][0]
                        polygon = Polygon([(lon, lat) for lon, lat in coords])
                        
                        area_km2 = polygon.area * 111 * 111
                        st.success(f"✅ Rectangle created: ~{area_km2:.2f} km² area")
        
        elif input_method == "📁 Upload Shapefile":
            st.markdown("**Upload a zipped shapefile (.zip containing .shp, .shx, .dbf)**")
            uploaded_file = st.file_uploader("Choose file", type=['zip'])
            
            if uploaded_file:
                try:
                    import zipfile
                    import tempfile
                    
                    with tempfile.TemporaryDirectory() as tmpdir:
                        with zipfile.ZipFile(uploaded_file, 'r') as zip_ref:
                            zip_ref.extractall(tmpdir)
                        
                        # Find .shp file
                        shp_files = list(Path(tmpdir).glob('*.shp'))
                        if shp_files:
                            shp_file = shp_files[0]
                            gdf = gpd.read_file(shp_file)
                            
                            # Convert to WGS84 if needed
                            if gdf.crs and gdf.crs.to_string() != 'EPSG:4326':
                                gdf = gdf.to_crs('EPSG:4326')
                            
                            polygon = gdf.geometry.iloc[0]
                            
                            area_km2 = polygon.area * 111 * 111
                            st.success(f"✅ Shapefile loaded: ~{area_km2:.2f} km² area")
                        else:
                            st.error("❌ No .shp file found in the uploaded zip")
                
                except Exception as e:
                    st.error(f"❌ Error reading shapefile: {str(e)}")
        
        elif input_method == "📝 Enter Coordinates":
            st.markdown("**Enter polygon coordinates (one per line: latitude, longitude)**")
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                coords_text = st.text_area(
                    "Coordinates",
                    value="-19.5, 13.5\n-19.5, 14.0\n-20.0, 14.0\n-20.0, 13.5",
                    height=200,
                    help="Format: latitude, longitude (one pair per line)"
                )
            
            with col2:
                st.markdown("**Example locations:**")
                if st.button("🇦🇴 Iona NP (Angola)"):
                    coords_text = "-17.0, 12.5\n-17.0, 13.0\n-17.5, 13.0\n-17.5, 12.5"
                if st.button("🇰🇪 Nairobi NP (Kenya)"):
                    coords_text = "-1.4, 36.85\n-1.4, 36.95\n-1.5, 36.95\n-1.5, 36.85"
                if st.button("🇿🇦 Kruger NP (SA)"):
                    coords_text = "-24.0, 31.5\n-24.0, 32.0\n-24.5, 32.0\n-24.5, 31.5"
            
            if st.button("Create Polygon", type="primary"):
                try:
                    coords = []
                    for line in coords_text.strip().split('\n'):
                        if line.strip():
                            lat, lon = map(float, line.split(','))
                            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                                raise ValueError(f"Invalid coordinates: {lat}, {lon}")
                            coords.append((lon, lat))  # Shapely uses (lon, lat)
                    
                    if len(coords) < 3:
                        st.error("❌ Need at least 3 points to create a polygon")
                    else:
                        polygon = Polygon(coords)
                        area_km2 = polygon.area * 111 * 111
                        st.success(f"✅ Polygon created with {len(coords)} vertices (~{area_km2:.2f} km²)")
                        
                except Exception as e:
                    st.error(f"❌ Error parsing coordinates: {str(e)}")
                    st.info("Ensure format is: latitude, longitude (e.g., -19.5, 13.5)")
        
        # Store polygon in session state
        if polygon:
            st.session_state['assessment_polygon'] = polygon
            st.session_state['site_name'] = site_name
            
            # Show polygon info
            with st.expander("📐 Polygon Details"):
                bounds = polygon.bounds
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Min Longitude", f"{bounds[0]:.4f}°")
                    st.metric("Min Latitude", f"{bounds[1]:.4f}°")
                with col2:
                    st.metric("Max Longitude", f"{bounds[2]:.4f}°")
                    st.metric("Max Latitude", f"{bounds[3]:.4f}°")
    
    with tab2:
        st.subheader("📊 Habitat Suitability Analysis")
        
        if 'assessment_polygon' not in st.session_state:
            st.info("👈 Please define a site in the 'Define Site' tab first")
        else:
            polygon = st.session_state['assessment_polygon']
            site_name = st.session_state.get('site_name', 'Unnamed Site')
            
            if st.button("🔍 Run Assessment", type="primary", use_container_width=True):
                with st.spinner("🛰️ Fetching satellite data and analyzing habitat..."):
                    try:
                        # Fetch NDVI data
                        result = get_sentinel2_ndvi_mock(polygon, start_date, end_date)
                        
                        # Store in session state
                        st.session_state['assessment_result'] = result
                        st.rerun()
                    
                    except Exception as e:
                        st.error(f"❌ Error during analysis: {str(e)}")
            
            # Display results if available
            if 'assessment_result' in st.session_state:
                result = st.session_state['assessment_result']
                
                # Mock data warning
                if result.get('is_mock'):
                    st.warning("⚠️ **Demo Mode**: Using simulated data. Configure Microsoft Planetary Computer API for real satellite imagery.")
                
                st.success("✅ Analysis complete!")
                
                # Key metrics
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Mean NDVI", f"{result['mean_ndvi']:.3f}")
                
                with col2:
                    suitability, emoji, color = assess_habitat_suitability(result['mean_ndvi'])
                    st.metric("Suitability", f"{emoji} {suitability}")
                
                with col3:
                    st.metric("NDVI Range", f"{result['min_ndvi']:.2f} - {result['max_ndvi']:.2f}")
                
                with col4:
                    st.metric("Cloud Cover", f"{result['cloud_cover']:.1f}%")
                
                # Detailed assessment
                st.markdown("---")
                
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    st.subheader("🎯 Assessment Summary")
                    
                    suitability, emoji, color = assess_habitat_suitability(result['mean_ndvi'])
                    
                    if suitability == 'Optimal':
                        st.success(f"{emoji} **Excellent habitat** for giraffe translocation")
                        st.markdown("""
                        **Recommendation:** ✅ Highly suitable
                        
                        This site shows dense vegetation cover optimal for giraffe. 
                        Proceed with field verification and additional assessments.
                        """)
                    elif suitability == 'Suitable':
                        st.info(f"{emoji} **Good habitat** - suitable for translocation")
                        st.markdown("""
                        **Recommendation:** ✔️ Suitable
                        
                        This site has moderate vegetation suitable for giraffe.
                        Recommend field surveys to verify browse availability.
                        """)
                    elif suitability == 'Marginal':
                        st.warning(f"{emoji} **Marginal habitat** - further assessment needed")
                        st.markdown("""
                        **Recommendation:** ⚠️ Requires careful evaluation
                        
                        Vegetation is sparse. Consider seasonal variations and
                        water availability before proceeding.
                        """)
                    else:
                        st.error(f"{emoji} **Poor habitat** - not recommended")
                        st.markdown("""
                        **Recommendation:** ❌ Not recommended
                        
                        Insufficient vegetation for giraffe. Consider alternative sites
                        or habitat restoration before translocation.
                        """)
                    
                    # Site details
                    st.markdown("---")
                    st.markdown("**Site Information:**")
                    st.markdown(f"- **Name:** {site_name or 'Not specified'}")
                    st.markdown(f"- **Analysis Date:** {result['date'].strftime('%Y-%m-%d')}")
                    st.markdown(f"- **Period:** {start_date} to {end_date}")
                
                with col2:
                    st.subheader("📈 NDVI Distribution")
                    
                    # Create histogram
                    ndvi_flat = result['ndvi_array'].flatten()
                    ndvi_flat = ndvi_flat[~np.isnan(ndvi_flat)]
                    
                    fig = go.Figure()
                    
                    fig.add_trace(go.Histogram(
                        x=ndvi_flat,
                        nbinsx=50,
                        name='NDVI',
                        marker_color='#388e3c'
                    ))
                    
                    # Add threshold lines
                    for category, (low, high, emoji, color) in NDVI_THRESHOLDS.items():
                        fig.add_vline(
                            x=low,
                            line_dash="dash",
                            line_color=color,
                            annotation_text=category,
                            annotation_position="top"
                        )
                    
                    fig.update_layout(
                        title="NDVI Value Distribution",
                        xaxis_title="NDVI",
                        yaxis_title="Frequency",
                        showlegend=False,
                        height=300
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Statistics table
                    stats_df = pd.DataFrame({
                        'Metric': ['Mean', 'Std Dev', 'Min', 'Max', '25th %ile', '75th %ile'],
                        'Value': [
                            f"{result['mean_ndvi']:.3f}",
                            f"{result['std_ndvi']:.3f}",
                            f"{result['min_ndvi']:.3f}",
                            f"{result['max_ndvi']:.3f}",
                            f"{np.percentile(ndvi_flat, 25):.3f}",
                            f"{np.percentile(ndvi_flat, 75):.3f}"
                        ]
                    })
                    st.dataframe(stats_df, hide_index=True, use_container_width=True)
                
                # NDVI Heatmap
                st.markdown("---")
                st.subheader("🗺️ NDVI Spatial Distribution")
                
                fig_heatmap = px.imshow(
                    result['ndvi_array'],
                    color_continuous_scale='RdYlGn',
                    aspect='auto',
                    labels={'color': 'NDVI'},
                    zmin=-0.2,
                    zmax=1.0
                )
                
                fig_heatmap.update_layout(
                    title="NDVI Heatmap (Green = High Vegetation, Red = Low Vegetation)",
                    height=400
                )
                
                st.plotly_chart(fig_heatmap, use_container_width=True)
                
                # Additional considerations
                st.markdown("---")
                st.subheader("💡 Additional Factors to Consider")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("""
                    **Environmental Factors:**
                    - 🌧️ Annual rainfall patterns (>400mm preferred)
                    - 🌡️ Temperature ranges (15-35°C optimal)
                    - 💧 Permanent water sources
                    - 🌳 Browse species diversity
                    - 🏔️ Terrain and accessibility
                    """)
                
                with col2:
                    st.markdown("""
                    **Management Factors:**
                    - 🦁 Predator populations
                    - 👥 Human-wildlife conflict history
                    - 🏞️ Protected area status
                    - 📊 Carrying capacity estimates
                    - 🚁 Monitoring infrastructure
                    """)
                
                # Export results
                st.markdown("---")
                st.subheader("📥 Export Results")
                
                # Prepare export data
                export_data = {
                    'site_name': site_name,
                    'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'period_start': start_date.strftime('%Y-%m-%d'),
                    'period_end': end_date.strftime('%Y-%m-%d'),
                    'mean_ndvi': result['mean_ndvi'],
                    'std_ndvi': result['std_ndvi'],
                    'min_ndvi': result['min_ndvi'],
                    'max_ndvi': result['max_ndvi'],
                    'suitability': suitability,
                    'cloud_cover': result['cloud_cover'],
                    'polygon_bounds': list(polygon.bounds)
                }
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.download_button(
                        label="📄 Download Report (JSON)",
                        data=json.dumps(export_data, indent=2),
                        file_name=f"site_assessment_{site_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.json",
                        mime="application/json"
                    )
                
                with col2:
                    # CSV export
                    export_df = pd.DataFrame([export_data])
                    st.download_button(
                        label="📊 Download Data (CSV)",
                        data=export_df.to_csv(index=False),
                        file_name=f"site_assessment_{site_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )
    
    with tab3:
        st.subheader("📚 User Guide")
        
        st.markdown("""
        ## How to Use This Tool
        
        ### 1️⃣ Define Your Site
        Choose one of three methods to specify the area you want to assess:
        
        - **🗺️ Draw on Map**: Interactive drawing tool for quick site selection
        - **📁 Upload Shapefile**: Use existing GIS data (must be zipped)
        - **📝 Enter Coordinates**: Manually input polygon vertices
        
        ### 2️⃣ Configure Settings
        Use the sidebar to:
        - Set the analysis time period (default: last 90 days)
        - Adjust NDVI thresholds if needed
        
        ### 3️⃣ Run Analysis
        Click "Run Assessment" to fetch satellite data and analyze habitat suitability.
        
        ### 4️⃣ Review Results
        Examine the:
        - Overall suitability rating
        - NDVI statistics and distribution
        - Spatial heatmap showing vegetation patterns
        - Recommendations and considerations
        
        ### 5️⃣ Export Report
        Download results as JSON or CSV for documentation and further analysis.
        
        ---
        
        ## Understanding NDVI
        
        **NDVI (Normalized Difference Vegetation Index)** measures vegetation health and density:
        
        | NDVI Range | Interpretation | Giraffe Habitat |
        |------------|----------------|-----------------|
        | 0.5 - 1.0  | Dense vegetation | ✅ Optimal |
        | 0.3 - 0.5  | Moderate vegetation | ✔️ Suitable |
        | 0.2 - 0.3  | Sparse vegetation | ⚠️ Marginal |
        | 0.0 - 0.2  | Little/no vegetation | ❌ Poor |
        
        ### Giraffe Habitat Requirements
        
        Giraffe thrive in:
        - **Savanna woodlands** with mixed tree/shrub species
        - **NDVI range**: Typically 0.3 - 0.6
        - **Browse availability**: Acacia, Combretum, Terminalia species
        - **Open areas** for movement and predator detection
        
        ---
        
        ## Data Sources
        
        This tool uses:
        - **Satellite Imagery**: Sentinel-2 (10m resolution, ESA)
        - **Platform**: Microsoft Planetary Computer
        - **Update Frequency**: Every 5 days
        - **Coverage**: Global
        
        ---
        
        ## Limitations & Best Practices
        
        ⚠️ **This is a preliminary assessment tool**
        
        **Limitations:**
        - NDVI only measures vegetation presence, not species composition
        - Cloud cover may affect data quality
        - Single-point-in-time snapshot (consider seasonal variations)
        - Does not assess water, predators, or human factors
        
        **Best Practices:**
        - Run assessments for multiple time periods (wet/dry seasons)
        - Compare with existing giraffe habitat
        - Combine with field surveys and local knowledge
        - Consider landscape connectivity
        - Consult with local wildlife authorities
        
        **For comprehensive translocation decisions, include:**
        - Field ecological surveys
        - Browse species assessment
        - Water availability mapping
        - Predator and prey surveys
        - Community consultations
        - Legal/protected area status
        - Carrying capacity analysis
        
        ---
        
        ## Troubleshooting
        
        **No satellite data found:**
        - Try a different date range
        - Check if coordinates are valid
        - Area might have persistent cloud cover
        
        **Polygon won't create:**
        - Ensure at least 3 coordinate points
        - Check coordinate format (latitude, longitude)
        - Verify values are within valid ranges
        
        **Need help?**
        Contact GCF data team for assistance with complex assessments.
        """)
        
        # Contact info
        st.info("""
        📧 **Questions or feedback?**  
        This tool is part of the GCF Twiga Tools suite for giraffe conservation data management.
        """)
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666;'>
    <small>
    Site Assessment Tool | Giraffe Conservation Foundation<br>
    Data: Microsoft Planetary Computer • Sentinel-2 ESA<br>
    Version 1.0 | November 2025
    </small>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
