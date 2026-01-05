import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster
from arcgis.gis import GIS
from arcgis.features import FeatureLayer
import os
from pathlib import Path

# DEBUG: Check secrets at module load time
if hasattr(st, 'secrets'):
    print(f"[DEBUG] Secrets available at import: {list(st.secrets.keys())}")
else:
    print("[DEBUG] st.secrets not available at import")

# Note: GEE, World Bank API, and advanced geospatial libraries removed
# GAD only uses AGOL data for summary table and folium map

# Configuration
AGOL_URL = "https://services1.arcgis.com/uMBFfFIXcCOpjlID/arcgis/rest/services/GAD_20250624/FeatureServer/0"
TOKEN = st.secrets.get("arcgis", {}).get("token", None)

# ======== Authentication Functions ========

def check_password():
    """Returns `True` if the user had the correct password."""
    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["password"] == st.secrets["passwords"]["admin_password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # don't store password
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # First run, show input for password
        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        st.write("*Please enter password to access the GAD.*")
        return False
    elif not st.session_state["password_correct"]:
        # Password incorrect, show input + error
        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        st.error("😕 Password incorrect")
        return False
    else:
        # Password correct
        return True

# ======== Data Loading Functions ========

@st.cache_data(ttl=3600)
def load_gad_data():
    """Load data from ArcGIS Online using ArcGIS Python API"""
    # Connect to ArcGIS Online with token (if available, otherwise anonymous)
    if TOKEN:
        gis = GIS("https://www.arcgis.com", token=TOKEN)
    else:
        gis = GIS()  # Anonymous connection
    
    # Use ArcGIS FeatureLayer to get all data at once
    feature_layer = FeatureLayer(AGOL_URL, gis=gis)
    
    # Query all features - this automatically handles pagination
    feature_set = feature_layer.query(where='1=1', out_fields='*', return_all_records=True)
    
    # Convert to DataFrame - this is the equivalent of arc.select() in R
    df = feature_set.sdf
    
    # Filter exactly as in R code:
    # filter(!is.na(Estimate)) %>%
    # filter(SCALE != "ISO") %>%
    # filter(SCALE != "GOV")
    df = df[df['Estimate'].notna()]
    df = df[df['SCALE'] != 'ISO']
    df = df[df['SCALE'] != 'GOV']
    
    # Convert numeric columns
    numeric_cols = ['Year', 'Estimate', 'Std_Err', 'CI_lower', 'CI_upper', 'x', 'y']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    return df

# ======== Data Processing Functions ========

def calculate_scale_rank(scale):
    """Calculate scale ranking"""
    scale_map = {'ISO': 1, 'REGION': 2, 'SUBREGION': 3, 'SITE': 4}
    return scale_map.get(scale, 5)

def calculate_iqi_rank(method, std_err, ci_upper):
    """Calculate IQI ranking based on method and precision"""
    # Handle NA values from arcgis
    method_str = str(method) if pd.notna(method) else ""
    
    if method_str == "Observation":
        return 1
    elif method_str == "Ground sample" and (pd.notna(std_err) or pd.notna(ci_upper)):
        return 1
    elif method_str == "Ground sample" and (pd.isna(std_err) and pd.isna(ci_upper)):
        return 2
    elif method_str == "Aerial sample" and (pd.notna(std_err) or pd.notna(ci_upper)):
        return 2
    elif method_str == "Aerial sample" and (pd.isna(std_err) and pd.isna(ci_upper)):
        return 3
    elif method_str in ["Ground total", "Aerial total"]:
        return 3
    elif method_str == "Guesstimate":
        return 4
    else:
        return 5

def calculate_bounds(row):
    """Calculate lower and upper bounds for estimates"""
    estimate = row['Estimate']
    std_err = row['Std_Err']
    ci_lower = row['CI_lower']
    ci_upper = row['CI_upper']
    method = str(row['Methods__field']) if pd.notna(row['Methods__field']) else ""
    
    # Lower bound
    if pd.notna(ci_lower):
        lower = ci_lower
    elif pd.notna(std_err):
        lower = estimate - std_err
    elif method in ["Aerial total", "Ground total"]:
        lower = estimate
    elif method == "Guesstimate":
        lower = estimate * 0.5
    elif method == "Ground sample" and pd.isna(ci_lower) and pd.isna(std_err):
        lower = estimate * 0.8
    else:
        lower = estimate
    
    # Upper bound
    if pd.notna(ci_upper):
        upper = ci_upper
    elif pd.notna(std_err):
        upper = estimate + std_err
    elif method == "Aerial total":
        upper = estimate * 1.6
    elif method == "Ground total":
        upper = estimate * 1.2
    elif method == "Guesstimate":
        upper = estimate * 1.5
    elif method == "Ground sample" and pd.isna(ci_upper) and pd.isna(std_err):
        upper = estimate * 1.2
    else:
        upper = estimate
    
    return pd.Series({'Lower': lower, 'Upper': upper})

def process_data(df, species_filter=None, subspecies_filter=None, country_filter=None, region0_filter=None):
    """Process and summarize GAD data"""
    # Apply filters
    filtered = df.copy()
    if species_filter:
        filtered = filtered[filtered['Species'].isin(species_filter)]
    if subspecies_filter:
        filtered = filtered[filtered['Subspecies'].isin(subspecies_filter)]
    if country_filter:
        filtered = filtered[filtered['Country'].isin(country_filter)]
    if region0_filter:
        filtered = filtered[filtered['Region0'].isin(region0_filter)]
    
    # Calculate rankings
    filtered['SCALE_RANK'] = filtered['SCALE'].apply(calculate_scale_rank)
    filtered['IQI_RANK'] = filtered.apply(lambda x: calculate_iqi_rank(x['Methods__field'], x['Std_Err'], x['CI_upper']), axis=1)
    filtered['TIME'] = datetime.now().year - filtered['Year']
    filtered['RANK'] = (filtered['SCALE_RANK'] * 2) + (filtered['IQI_RANK'] * 3) + (filtered['TIME'] * 1)
    
    # Calculate bounds
    filtered[['Lower', 'Upper']] = filtered.apply(calculate_bounds, axis=1)
    
    # Fill NA values in location columns with empty string for proper grouping
    filtered['Region0'] = filtered['Region0'].fillna('')
    filtered['Region1'] = filtered['Region1'].fillna('')
    filtered['Site'] = filtered['Site'].fillna('')
    
    # Get latest data per location
    latest_data = (filtered
                   .sort_values(['SCALE_RANK', 'TIME'])
                   .groupby(['Species', 'Subspecies', 'Country', 'Region0', 'Region1', 'Site'])
                   .first()
                   .reset_index())
    
    # Summarize at site level
    site_data = (latest_data[latest_data['Site'].notna() & (latest_data['Site'] != '')]
                 .groupby(['Country', 'Species', 'Subspecies', 'Region0', 'Region1', 'Site'])
                 .agg({
                     'Estimate': 'sum',
                     'Lower': 'sum',
                     'Upper': 'sum',
                     'Year': 'max',
                     'IQI_RANK': 'mean',
                     'Reference': 'first',
                     'ref_url': 'first',
                     'x': 'first',
                     'y': 'first'
                 })
                 .reset_index())
    
    # Summarize at region1 level (R: filter(is.na(Site)))
    # Must have Region1 not null to be included here
    region1_data = (latest_data[(latest_data['Site'].isna() | (latest_data['Site'] == '')) &
                                (latest_data['Region1'].notna() & (latest_data['Region1'] != ''))]
                    .groupby(['Country', 'Species', 'Subspecies', 'Region0', 'Region1'])
                    .agg({
                        'Estimate': 'sum',
                        'Lower': 'sum',
                        'Upper': 'sum',
                        'Year': 'max',
                        'IQI_RANK': 'mean',
                        'Reference': 'first',
                        'ref_url': 'first',
                        'x': 'first',
                        'y': 'first'
                    })
                    .reset_index())
    
    # Summarize at region0 level (R: filter(is.na(Site) & is.na(Region1)))
    # Must have Region0 not null to be included here
    region0_data = (latest_data[(latest_data['Site'].isna() | (latest_data['Site'] == '')) & 
                                (latest_data['Region1'].isna() | (latest_data['Region1'] == '')) &
                                (latest_data['Region0'].notna() & (latest_data['Region0'] != ''))]
                    .groupby(['Country', 'Species', 'Subspecies', 'Region0'])
                    .agg({
                        'Estimate': 'sum',
                        'Lower': 'sum',
                        'Upper': 'sum',
                        'Year': 'max',
                        'IQI_RANK': 'mean',
                        'Reference': 'first',
                        'ref_url': 'first',
                        'x': 'first',
                        'y': 'first'
                    })
                    .reset_index())
    
    # Add missing columns to region0_data so structure matches for combining
    region0_data['Region1'] = ''
    region0_data['Site'] = ''
    
    # Add Site column to region1_data so structure matches for combining
    region1_data['Site'] = ''
    
    # R anti_join logic: Use most aggregated data available
    # If a region0 summary exists, don't include any region1 or site data for that region0
    # If a region1 summary exists (but no region0), don't include site data for that region1
    
    # First: Remove site_data where we have a region1 summary for the same location
    if len(region1_data) > 0:
        site_data = site_data.merge(
            region1_data[['Country', 'Species', 'Subspecies', 'Region0', 'Region1']],
            on=['Country', 'Species', 'Subspecies', 'Region0', 'Region1'],
            how='left',
            indicator=True
        )
        site_data = site_data[site_data['_merge'] == 'left_only'].drop('_merge', axis=1)
    
    # Second: Remove site_data where we have a region0 summary for the same location
    if len(region0_data) > 0:
        site_data = site_data.merge(
            region0_data[['Country', 'Species', 'Subspecies', 'Region0']],
            on=['Country', 'Species', 'Subspecies', 'Region0'],
            how='left',
            indicator=True
        )
        site_data = site_data[site_data['_merge'] == 'left_only'].drop('_merge', axis=1)
    
    # Third: Remove region1_data where we have a region0 summary for the same location
    if len(region0_data) > 0:
        region1_data = region1_data.merge(
            region0_data[['Country', 'Species', 'Subspecies', 'Region0']],
            on=['Country', 'Species', 'Subspecies', 'Region0'],
            how='left',
            indicator=True
        )
        region1_data = region1_data[region1_data['_merge'] == 'left_only'].drop('_merge', axis=1)
    
    # Combine all data (R: bind_rows)
    combined = pd.concat([site_data, region1_data, region0_data], ignore_index=True)
    
    # Calculate years since survey
    combined['YearsSince'] = datetime.now().year - combined['Year']
    
    # Add total row
    if len(combined) > 0:
        # Create total row with same structure as combined
        total_data = {
            'Country': 'Total',
            'Region0': 'Total',
            'Region1': '',
            'Site': '',
            'Species': '',
            'Subspecies': '',
            'Year': df['Year'].max(),
            'Estimate': combined['Estimate'].sum(),
            'Lower': combined['Lower'].sum(),
            'Upper': combined['Upper'].sum(),
            'IQI_RANK': combined['IQI_RANK'].mean(),
            'YearsSince': combined['YearsSince'].mean(),
            'Reference': ''
        }
        # Add other columns that might exist
        for col in combined.columns:
            if col not in total_data:
                total_data[col] = None
        
        total_row = pd.DataFrame([total_data])
        # Ensure matching dtypes
        for col in combined.columns:
            if col in total_row.columns:
                try:
                    total_row[col] = total_row[col].astype(combined[col].dtype)
                except:
                    pass
        combined = pd.concat([total_row, combined], ignore_index=True)
    
    return combined

# ======== Visualization Functions ========

def get_subspecies_color(subspecies):
    """Get color for subspecies"""
    color_map = {
        'peralta': '#DB0F0F',
        'antiquorum': '#9A392B',
        'camelopardalis': '#E6751A',
        'reticulata': '#C41697',
        'tippelskirchi': '#216DCC',
        'thornicrofti': '#5BAED9',
        'giraffa': '#4D9C2C',
        'angolensis': '#457132'
    }
    return color_map.get(subspecies, '#E5E4D8')

def get_time_color(years_since):
    """Get color based on years since survey (for highlighting populations needing review)"""
    if years_since >= 8:
        return '#FF6347'  # Red - urgent review needed
    elif years_since >= 4:
        return '#FFE866'  # Yellow - review needed soon
    else:
        return '#90EE90'  # Green - recent data

def create_map(data, color_by='subspecies'):
    """Create folium map with giraffe populations
    
    Args:
        data: DataFrame with giraffe population data
        color_by: 'subspecies' for subspecies colors or 'time' for time-based colors
    """
    # Create base map centered on Africa
    m = folium.Map(location=[0, 20], zoom_start=4, tiles='OpenStreetMap')
    
    # Filter out total row and rows without coordinates
    map_data = data[(data['Country'] != 'Total') & 
                    (data['x'].notna()) & 
                    (data['y'].notna()) &
                    (data['Estimate'] > 0)]
    
    # Add markers
    for _, row in map_data.iterrows():
        location_name = row['Site'] if pd.notna(row['Site']) and row['Site'] != '' else \
                       row['Region1'] if pd.notna(row['Region1']) and row['Region1'] != '' else \
                       row['Region0']
        
        popup_text = f"""
        <b>{location_name}</b><br>
        Country: {row['Country']}<br>
        Species: {row['Species']}<br>
        Subspecies: {row['Subspecies']}<br>
        Population: {int(row['Estimate']):,}<br>
        Range: {int(row['Lower']):,} - {int(row['Upper']):,}<br>
        Survey Year: {int(row['Year'])}<br>
        Years Since: {int(row['YearsSince'])}<br>
        Reference: {row['Reference']}
        """
        
        # Choose color based on parameter
        if color_by == 'time':
            marker_color = get_time_color(row['YearsSince'])
        else:
            marker_color = get_subspecies_color(row['Subspecies'])
        
        folium.CircleMarker(
            location=[row['y'], row['x']],
            radius=max(5, min(25, (row['Estimate'] ** 0.5) / 10)),
            popup=folium.Popup(popup_text, max_width=300),
            tooltip=f"{location_name}: {int(row['Estimate']):,} giraffe",
            color=marker_color,
            fill=True,
            fillColor=marker_color,
            fillOpacity=0.7,
            weight=2
        ).add_to(m)
    
    return m

# ======== Main Application ========

def main():
    """Main application function"""
    # Set pandas display options to show all rows
    pd.set_option('display.max_rows', None)

    st.title("🦒 Giraffe Africa Database (GAD v1.1)")

    # Check password before showing content
    if not check_password():
        st.stop()

    # Load data
    with st.spinner("Loading GAD data..."):
        try:
            df = load_gad_data()
        except Exception as e:
            st.error(f"Error loading data: {e}")
            st.stop()

    # Filters
    st.subheader("Filters")

    # Create columns for filters
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        # Year filter - dropdown for year selection
        year_options = sorted(df['Year'].dropna().unique().tolist(), reverse=True)
        selected_year = st.selectbox(
            "Maximum Survey Year",
            options=year_options,
            index=0,
            help="Only include surveys up to this year"
        )

    # Apply year filter to dataframe
    df = df[df['Year'] <= selected_year]

    with col2:
        species_options = sorted(df['Species'].dropna().unique().tolist())
        species_filter = st.multiselect("Species", species_options, max_selections=None)

    with col3:
        # Filter subspecies based on species
        if species_filter:
            subspecies_options = sorted(df[df['Species'].isin(species_filter)]['Subspecies'].dropna().unique().tolist())
        else:
            subspecies_options = sorted(df['Subspecies'].dropna().unique().tolist())
        subspecies_filter = st.multiselect("Subspecies", subspecies_options, max_selections=None)

    with col4:
        # Filter countries based on subspecies
        if subspecies_filter:
            country_options = sorted(df[df['Subspecies'].isin(subspecies_filter)]['Country'].dropna().unique().tolist())
        else:
            country_options = sorted(df['Country'].dropna().unique().tolist())
        country_filter = st.multiselect("Country", country_options, max_selections=None)

    with col5:
        # Filter regions based on country
        if country_filter:
            region0_options = sorted(df[df['Country'].isin(country_filter)]['Region0'].dropna().unique().tolist())
        else:
            region0_options = sorted(df['Region0'].dropna().unique().tolist())
        region0_filter = st.multiselect("Region", region0_options, max_selections=None)

    st.markdown("---")

    # Process data
    summary = process_data(df, species_filter, subspecies_filter, country_filter, region0_filter)

    # Create tabs
    tab1, tab2, tab3 = st.tabs(["📊 Summary Table", "🗺️ Map; population", "⏰ Map; time"])

    with tab1:
        st.header("Population Summary")
        
        # Format the dataframe for display
        display_df = summary.copy()
        display_df['Estimate'] = display_df['Estimate'].apply(lambda x: f"{int(x):,}")
        display_df['Lower'] = display_df['Lower'].apply(lambda x: f"{int(x):,}")
        display_df['Upper'] = display_df['Upper'].apply(lambda x: f"{int(x):,}")
        display_df['IQI'] = display_df['IQI_RANK'].apply(lambda x: int(round(x)) if pd.notna(x) else '')
        display_df['Year'] = display_df['Year'].apply(lambda x: int(x) if pd.notna(x) else '')
        display_df['YearsSince'] = display_df['YearsSince'].apply(lambda x: int(x) if pd.notna(x) else '')
        
        # Color code years since
        def color_years(val):
            if val == '' or pd.isna(val):
                return ''
            try:
                val_int = int(val)
                if val_int >= 8:
                    return 'background-color: #FF6347; color: white'
                elif val_int >= 4:
                    return 'background-color: #FFE866; color: black'
                else:
                    return 'background-color: #90EE90; color: black'
            except:
                return ''
        
        # Select columns for display
        display_cols = ['Country', 'Region0', 'Region1', 'Site', 'Species', 'Subspecies', 
                       'Year', 'Estimate', 'Lower', 'Upper', 'IQI', 'YearsSince', 'Reference']
        
        # Fill NaN values with empty string for display
        for col in ['Region1', 'Site', 'Reference']:
            if col in display_df.columns:
                display_df[col] = display_df[col].fillna('')
        
        display_df = display_df[display_cols]
        
        # Show row count
        st.write(f"**Showing {len(display_df)} records**")
        
        # Color code the YearsSince column for display
        def highlight_years(row):
            years = row['YearsSince']
            color = ''
            if years != '' and pd.notna(years):
                try:
                    years_int = int(years)
                    if years_int >= 8:
                        color = 'background-color: #FF6347; color: white'
                    elif years_int >= 4:
                        color = 'background-color: #FFE866; color: black'
                    else:
                        color = 'background-color: #90EE90; color: black'
                except:
                    pass
            return [color if col == 'YearsSince' else '' for col in row.index]
        
        # Style and display all rows
        styled_df = display_df.style.apply(highlight_years, axis=1)
        st.dataframe(styled_df, use_container_width=True)
        
        # Summary statistics
        st.subheader("Summary Statistics")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_estimate = summary[summary['Country'] != 'Total']['Estimate'].sum()
            st.metric("Total Population", f"{int(total_estimate):,}")
        
        with col2:
            num_countries = summary[summary['Country'] != 'Total']['Country'].nunique()
            st.metric("Countries", num_countries)
        
        with col3:
            num_subspecies = summary[summary['Country'] != 'Total']['Subspecies'].nunique()
            st.metric("Subspecies", num_subspecies)
        
        with col4:
            avg_years = summary[summary['Country'] != 'Total']['YearsSince'].mean()
            st.metric("Avg Years Since Survey", f"{avg_years:.1f}")

    with tab2:
        st.header("Giraffe Distribution by Population")
        
        # Create and display map using HTML export
        try:
            giraffe_map = create_map(summary, color_by='subspecies')
            # Export to HTML and display
            map_html = giraffe_map._repr_html_()
            st.components.v1.html(map_html, height=600, scrolling=True)
        except Exception as e:
            st.error(f"Error displaying map: {e}")
            st.info("Map display is temporarily unavailable. Please view data in the Summary Table tab.")
        
        st.markdown("""
        **Map Information:**
        - Bubble size represents population estimate
        - Colors represent different giraffe subspecies
        - Click bubbles for detailed information
        
        **Legend:**
        - 🔴 *G. c. peralta* (West African)
        - 🟤 *G. c. antiquorum* (Kordofan)
        - 🟠 *G. c. camelopardalis* (Nubian)
        - 🟣 *G. reticulata* (Reticulated)
        - 🔵 *G. t. tippelskirchi* (Masai)
        - 🔷 *G. t. thornicrofti* (Luangwa)
        - 🟢 *G. g. giraffa* (South African)
        - 🟩 *G. g. angolensis* (Angolan)
        """)
    
    with tab3:
        st.header("Survey Age Analysis")
        
        # Create and display map using HTML export with time-based colors
        try:
            giraffe_map = create_map(summary, color_by='time')
            # Export to HTML and display
            map_html = giraffe_map._repr_html_()
            st.components.v1.html(map_html, height=600, scrolling=True)
        except Exception as e:
            st.error(f"Error displaying map: {e}")
            st.info("Map display is temporarily unavailable. Please view data in the Summary Table tab.")
        
        st.markdown("""
        **Map Information:**
        - Bubble size represents population estimate
        - **Colors indicate years since last survey** (populations needing review)
        - Click bubbles for detailed information
        
        **Legend:**
        - 🟢 **Green**: Recent surveys (< 4 years)
        - 🟡 **Yellow**: Review needed soon (4-7 years)
        - 🔴 **Red**: Urgent review needed (≥ 8 years)
        
        *This map highlights populations that require updated surveys to ensure accurate conservation data.*
        """)

if __name__ == "__main__":
    main()


