import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster
from arcgis.gis import GIS
from arcgis.features import FeatureLayer
from arcgis.geometry import Point
import os
from pathlib import Path
import json

# DEBUG: Check secrets at module load time
try:
    if hasattr(st, 'secrets'):
        print(f"[DEBUG] Secrets available at import: {list(st.secrets.keys())}")
    else:
        print("[DEBUG] st.secrets not available at import")
except Exception as e:
    print(f"[DEBUG] Could not access secrets: {e}")

# Note: GEE, World Bank API, and advanced geospatial libraries removed
# GAD only uses AGOL data for summary table and folium map

# Configuration
AGOL_URL = "https://services1.arcgis.com/uMBFfFIXcCOpjlID/arcgis/rest/services/GAD_20250624/FeatureServer/0"

# Get token safely - won't crash if secrets.toml doesn't exist locally
try:
    TOKEN = st.secrets.get("arcgis", {}).get("token", None)
except Exception:
    TOKEN = None  # For local development without secrets

# ======== Authentication Functions ========

def check_password():
    """Returns `True` if the user had the correct password."""
    def password_entered():
        """Checks whether a password entered by the user is correct."""
        try:
            if st.session_state["password"] == st.secrets["passwords"]["admin_password"]:
                st.session_state["password_correct"] = True
                del st.session_state["password"]  # don't store password
            else:
                st.session_state["password_correct"] = False
        except Exception as e:
            # For local development without secrets.toml, use a default password
            if st.session_state["password"] == "admin":  # Default for local dev
                st.session_state["password_correct"] = True
                del st.session_state["password"]
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
            radius=max(5, min(40, (row['Estimate'] ** 0.5) / 10)),
            popup=folium.Popup(popup_text, max_width=300),
            tooltip=f"{location_name}: {int(row['Estimate']):,} giraffe",
            color=marker_color,
            fill=True,
            fillColor=marker_color,
            fillOpacity=0.7,
            weight=2
        ).add_to(m)
    
    return m

# ======== Data Submission Functions ========

def submit_data_to_agol(feature_data):
    """Submit new feature to ArcGIS Online feature layer
    
    Args:
        feature_data: Dictionary containing all required fields for the new feature
        
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        # Check if token is available
        if not TOKEN:
            return False, "No AGOL token available. Write access is required."
        
        # Connect to ArcGIS Online with token
        gis = GIS("https://www.arcgis.com", token=TOKEN)
        
        # Get the feature layer
        feature_layer = FeatureLayer(AGOL_URL, gis=gis)
        
        # Create geometry
        geometry = {
            "x": feature_data['x'],
            "y": feature_data['y'],
            "spatialReference": {"wkid": 4326}  # WGS84
        }
        
        # Create attributes dictionary - only include fields that have values
        attributes = {}
        for key, value in feature_data.items():
            if key not in ['x', 'y'] and value is not None and value != '':
                attributes[key] = value
        
        # Create the feature
        new_feature = {
            "geometry": geometry,
            "attributes": attributes
        }
        
        # Add the feature to the layer
        result = feature_layer.edit_features(adds=[new_feature])
        
        # Check if addition was successful
        if result['addResults'] and len(result['addResults']) > 0:
            if result['addResults'][0]['success']:
                return True, f"Successfully added record with ObjectID: {result['addResults'][0]['objectId']}"
            else:
                error_msg = result['addResults'][0].get('error', {}).get('description', 'Unknown error')
                return False, f"Failed to add record: {error_msg}"
        else:
            return False, "No results returned from AGOL"
            
    except Exception as e:
        return False, f"Error submitting data: {str(e)}"

def validate_coordinates(lat, lon):
    """Validate latitude and longitude values
    
    Returns:
        tuple: (valid: bool, message: str)
    """
    try:
        lat_float = float(lat)
        lon_float = float(lon)
        
        if lat_float < -90 or lat_float > 90:
            return False, "Latitude must be between -90 and 90"
        if lon_float < -180 or lon_float > 180:
            return False, "Longitude must be between -180 and 180"
        
        # Check if coordinates are within Africa bounds (rough approximation)
        if lat_float < -35 or lat_float > 38:
            return False, "Warning: Latitude appears to be outside Africa's typical range (-35 to 38)"
        if lon_float < -18 or lon_float > 52:
            return False, "Warning: Longitude appears to be outside Africa's typical range (-18 to 52)"
        
        return True, "Coordinates valid"
    except ValueError:
        return False, "Coordinates must be valid numbers"

# ======== Main Application ========

def main():
    """Main application function"""
    # Set pandas display options to show all rows
    pd.set_option('display.max_rows', None)

    st.title("🦒 Giraffe Africa Database (GAD v1.2)")

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
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Summary Table", "🗺️ Map; population", "⏰ Map; time", "➕ Submit Data"])

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
        st.header("Giraffe distribution (by species, population)")
        
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
        
        **Legend (Subspecies Colors):**
        """, unsafe_allow_html=True)
        
        st.markdown("""
        - <span style="color:#DB0F0F">●</span> *G. c. peralta* (West African)
        - <span style="color:#9A392B">●</span> *G. c. antiquorum* (Kordofan)
        - <span style="color:#E6751A">●</span> *G. c. camelopardalis* (Nubian)
        - <span style="color:#C41697">●</span> *G. reticulata* (Reticulated)
        - <span style="color:#216DCC">●</span> *G. t. tippelskirchi* (Masai)
        - <span style="color:#5BAED9">●</span> *G. t. thornicrofti* (Luangwa)
        - <span style="color:#4D9C2C">●</span> *G. g. giraffa* (South African)
        - <span style="color:#457132">●</span> *G. g. angolensis* (Angolan)
        """, unsafe_allow_html=True)
    
    with tab3:
        st.header("Giraffe distribution (by survey year, population)")
        
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
    
    with tab4:
        st.header("Submit New Giraffe Population Data")
        
        st.warning("⚠️ **Important:** This form submits data directly to the GAD database. Please ensure all information is accurate before submitting.")
        
        # Submission Guidelines at top
        with st.expander("📋 Submission Guidelines"):
            st.markdown("""
            **Survey Method:** Choose the method that best describes how the data was collected.
            - **Observation** = high level ground monitoring with an ID book, i.e., the population is known
            - **Ground sample** = a road based survey with transects covering only a sample of the area, population extrapolated
            - **Aerial sample** = an aerial survey with transects covering a sample of the area, population extrapolated
            - **Ground total** = a road based survey of the entire area, entire population counted
            - **Aerial total** = an aerial survey of the entire area, entire population counted
            - **Guesstimate** = a best guess / rough estimation
            
            **Data error rates:** Standard Error (SE) measures the variability of sample mean. A Confidence Interval (CI) is a range calculated usually using the SE.
            Check your report for an SE or a range (upper and lower). All ground sample and aerial sample estimates should have an SE or a CI range reported.
            
            **Reference:** Include the author (year) for display purposes. Include the Zotero URL if possible.
            
            **After Submission:**
            - Data are immediately added to the AGOL feature layer
            - Refresh the page to see your submission reflected in the Summary Table and maps
            - Contact Courtney if you need to edit or remove data submitted in error
            """)
        
        # Check if token has write access
        if not TOKEN:
            st.error("No AGOL token available. Data submission requires authentication with write permissions.")
            st.stop()
        
        # Pre-form selections for cascading dropdowns (outside form to allow dynamic updates)
        st.markdown("**Step 1: Select Scale and Country**")
        col_pre1, col_pre2 = st.columns(2)
        
        with col_pre1:
            scale_options = ["SITE", "SUBREGION", "REGION"]
            submit_scale = st.selectbox(
                "Scale",
                options=scale_options,
                help="Geographic scale of survey",
                key="scale_select"
            )
        
        with col_pre2:
            country_list = sorted(df['Country'].dropna().unique().tolist())
            submit_country = st.selectbox(
                "Country",
                options=["Select a country"] + country_list,
                help="Select the country where the population is located",
                key="country_select"
            )
        
        st.markdown("---")
        
        # Step 2: Location selection based on Scale and Coordinates
        st.markdown("**Step 2: Select Location and Coordinates**")
        
        if submit_country != "Select a country":
            country_data = df[df['Country'] == submit_country]
            
            if submit_scale == "SITE":
                # For SITE scale: Select site first, then auto-populate regions
                site_list = sorted(country_data['Site'].dropna().unique().tolist())
                site_options = ["Select a site"] + site_list if site_list else ["No sites available"]
                
                submit_site = st.selectbox(
                    "Site",
                    options=site_options,
                    help="Select the specific site name",
                    key="site_select"
                )
                
                # Auto-populate Region0, Region1, and Coordinates based on selected site
                if submit_site and submit_site != "Select a site" and submit_site != "No sites available":
                    site_data = country_data[country_data['Site'] == submit_site].iloc[0]
                    submit_region0 = site_data['Region0'] if pd.notna(site_data['Region0']) else None
                    submit_region1 = site_data['Region1'] if pd.notna(site_data['Region1']) else None
                    submit_latitude = float(site_data['y']) if pd.notna(site_data['y']) else 0.0
                    submit_longitude = float(site_data['x']) if pd.notna(site_data['x']) else 0.0
                    
                    # Display the auto-populated regions
                    col_info1, col_info2 = st.columns(2)
                    with col_info1:
                        st.info(f"**Region 0:** {submit_region0}")
                    with col_info2:
                        if submit_region1:
                            st.info(f"**Region 1:** {submit_region1}")
                        else:
                            st.info("**Region 1:** None")
                    
                    # Display auto-populated coordinates
                    col_coord1, col_coord2 = st.columns(2)
                    with col_coord1:
                        st.info(f"**Latitude:** {submit_latitude}")
                    with col_coord2:
                        st.info(f"**Longitude:** {submit_longitude}")
                else:
                    submit_region0 = None
                    submit_region1 = None
                    submit_latitude = 0.0
                    submit_longitude = 0.0
                    
            elif submit_scale == "SUBREGION":
                # For SUBREGION scale: Select Region0, then Region1
                region0_list = sorted(country_data['Region0'].dropna().unique().tolist())
                region0_options = ["Select a region"] + region0_list if region0_list else ["No regions available"]
                
                col2a, col2b = st.columns(2)
                with col2a:
                    submit_region0 = st.selectbox(
                        "Region (Level 0)",
                        options=region0_options,
                        help="Primary administrative region",
                        key="region0_select"
                    )
                
                with col2b:
                    if submit_region0 and submit_region0 != "Select a region" and submit_region0 != "No regions available":
                        region1_data = country_data[country_data['Region0'] == submit_region0]
                        region1_list = sorted(region1_data['Region1'].dropna().unique().tolist())
                        region1_options = ["Select a subregion"] + region1_list if region1_list else ["No subregions available"]
                    else:
                        region1_options = ["Select a subregion"]
                    
                    submit_region1 = st.selectbox(
                        "Region (Level 1)",
                        options=region1_options,
                        help="Secondary administrative region",
                        key="region1_select"
                    )
                
                submit_site = None
                submit_latitude = 0.0
                submit_longitude = 0.0
                
            else:  # REGION scale
                # For REGION scale: Only select Region0
                region0_list = sorted(country_data['Region0'].dropna().unique().tolist())
                region0_options = ["Select a region"] + region0_list if region0_list else ["No regions available"]
                
                submit_region0 = st.selectbox(
                    "Region (Level 0)",
                    options=region0_options,
                    help="Primary administrative region",
                    key="region0_only_select"
                )
                
                submit_region1 = None
                submit_site = None
                submit_latitude = 0.0
                submit_longitude = 0.0
        else:
            st.info("Please select a country to see location options")
            submit_region0 = None
            submit_region1 = None
            submit_site = None
            submit_latitude = 0.0
            submit_longitude = 0.0
        
        st.markdown("---")
        
        # Step 3: Species Information
        st.markdown("**Step 3: Species Information**")
        
        col4a, col4b = st.columns(2)
        with col4a:
            if submit_country != "Select a country":
                country_species = sorted(country_data['Species'].dropna().unique().tolist())
                species_options = ["Select a species"] + country_species
            else:
                species_options = ["Select a species"] + sorted(df['Species'].dropna().unique().tolist())
            
            submit_species = st.selectbox(
                "Species",
                options=species_options,
                help="Scientific species name",
                key="species_select"
            )
        
        with col4b:
            if submit_country != "Select a country" and submit_species != "Select a species":
                country_subspecies = sorted(
                    country_data[country_data['Species'] == submit_species]['Subspecies'].dropna().unique().tolist()
                )
                subspecies_options = ["Select a subspecies"] + country_subspecies
            elif submit_country != "Select a country":
                country_subspecies = sorted(country_data['Subspecies'].dropna().unique().tolist())
                subspecies_options = ["Select a subspecies"] + country_subspecies
            else:
                subspecies_options = ["Select a subspecies"] + sorted(df['Subspecies'].dropna().unique().tolist())
            
            submit_subspecies = st.selectbox(
                "Subspecies",
                options=subspecies_options,
                help="Subspecies designation",
                key="subspecies_select"
            )
        
        st.markdown("---")
        
        # Step 4: Survey Data
        st.markdown("**Step 4: Survey Data**")
        
        col5a, col5b, col5c, col5d = st.columns(4)
        with col5a:
            submit_year = st.number_input(
                "Survey Year",
                min_value=1900,
                max_value=datetime.now().year,
                value=datetime.now().year,
                step=1,
                help="Year survey was conducted",
                key="year_input"
            )
        
        with col5b:
            submit_month = st.number_input(
                "Survey Month",
                min_value=1,
                max_value=12,
                value=1,
                step=1,
                help="Month survey was conducted (1-12)",
                key="month_input"
            )
        
        with col5c:
            submit_estimate = st.number_input(
                "Population Estimate",
                min_value=0,
                value=0,
                step=1,
                help="Best estimate of population",
                key="estimate_input"
            )
        
        with col5d:
            methods_list = [
                "Select a method",
                "Observation",
                "Ground sample",
                "Aerial sample",
                "Ground total",
                "Aerial total",
                "Guesstimate"
            ]
            submit_method = st.selectbox(
                "Survey Method",
                options=methods_list,
                help="Method for population estimation",
                key="method_select"
            )
        
        st.markdown("---")
        
        # Step 5: Data Error Rates (conditional)
        if submit_method in ["Observation", "Ground sample", "Aerial sample"]:
            st.markdown("**Step 5: Data Error Rates**")
            st.info("Enter EITHER Standard Error OR Confidence Intervals (Upper and Lower)")
            
            # Standard Error on first row
            submit_std_err = st.number_input(
                "Standard Error",
                min_value=0.0,
                value=0.0,
                step=0.1,
                help="Standard error of the estimate (leave as 0 if not applicable)",
                key="std_err_input"
            )
            
            # CI on second row
            col6b, col6c = st.columns(2)
            with col6b:
                submit_ci_lower = st.number_input(
                    "CI Lower",
                    min_value=0.0,
                    value=0.0,
                    step=0.1,
                    help="Lower confidence interval (leave as 0 if not applicable)",
                    key="ci_lower_input"
                )
            
            with col6c:
                submit_ci_upper = st.number_input(
                    "CI Upper",
                    min_value=0.0,
                    value=0.0,
                    step=0.1,
                    help="Upper confidence interval (leave as 0 if not applicable)",
                    key="ci_upper_input"
                )
            
            st.markdown("---")
        else:
            # Set to None for methods that don't use SE/CI
            submit_std_err = None
            submit_ci_lower = None
            submit_ci_upper = None
        
        # Step 6: Reference Information
        st.markdown("**Step 6: Reference Information**")
        
        col_ref1, col_ref2 = st.columns([1, 1])
        with col_ref1:
            submit_reference = st.text_input(
                "Reference",
                placeholder="e.g., Fennessy et al (2025)",
                help="Citation for the survey data",
                key="reference_input"
            )
        
        with col_ref2:
            submit_ref_url = st.text_input(
                "Zotero URL",
                help="Zotero URL (if available)",
                key="ref_url_input"
            )
        
        st.markdown("---")
        
        with st.form("data_submission_form"):
            
            st.markdown("---")
            
            # Submit button
            submit_button = st.form_submit_button("Submit Data", use_container_width=True)
            
            if submit_button:
                # Validation
                errors = []
                
                if submit_country == "Select a country":
                    errors.append("Please select a country")
                
                # Validate based on scale
                if submit_scale == "SITE":
                    if not submit_site or submit_site == "Select a site" or submit_site == "No sites available":
                        errors.append("Site is required for SITE scale")
                    # Region0 can be NA for some sites, so we don't validate it for SITE scale
                elif submit_scale == "SUBREGION":
                    if not submit_region0 or submit_region0 == "Select a region" or submit_region0 == "No regions available":
                        errors.append("Region (Level 0) is required for SUBREGION scale")
                    if not submit_region1 or submit_region1 == "Select a subregion" or submit_region1 == "No subregions available":
                        errors.append("Region (Level 1) is required for SUBREGION scale")
                elif submit_scale == "REGION":
                    if not submit_region0 or submit_region0 == "Select a region" or submit_region0 == "No regions available":
                        errors.append("Region (Level 0) is required for REGION scale")
                
                if submit_species == "Select a species":
                    errors.append("Please select a species")
                if submit_subspecies == "Select a subspecies":
                    errors.append("Please select a subspecies")
                if submit_method == "Select a method":
                    errors.append("Please select a survey method")
                if submit_estimate < 0:
                    errors.append("Population estimate cannot be negative")
                if not submit_reference:
                    errors.append("Reference is required")
                
                # Validate coordinates
                coord_valid, coord_msg = validate_coordinates(submit_latitude, submit_longitude)
                if not coord_valid:
                    errors.append(coord_msg)
                
                # Check if coordinates are at default (0, 0)
                if submit_latitude == 0.0 and submit_longitude == 0.0:
                    errors.append("Please provide valid coordinates (not 0, 0)")
                
                if errors:
                    st.error("**Please fix the following errors:**")
                    for error in errors:
                        st.error(f"- {error}")
                else:
                    # Prepare data for submission
                    feature_data = {
                        'Country': submit_country,
                        'Region0': submit_region0 if submit_region0 else None,
                        'Region1': submit_region1 if submit_region1 else None,
                        'Site': submit_site if submit_site else None,
                        'Species': submit_species,
                        'Subspecies': submit_subspecies,
                        'SCALE': submit_scale,
                        'Year': submit_year,
                        'Month': submit_month,
                        'Estimate': submit_estimate,
                        'Std_Err': submit_std_err if submit_std_err and submit_std_err > 0 else None,
                        'CI_lower': submit_ci_lower if submit_ci_lower and submit_ci_lower > 0 else None,
                        'CI_upper': submit_ci_upper if submit_ci_upper and submit_ci_upper > 0 else None,
                        'Methods__field': submit_method,
                        'Reference': submit_reference,
                        'ref_url': submit_ref_url if submit_ref_url else None,
                        'x': submit_longitude,
                        'y': submit_latitude
                    }
                    
                    # Show preview
                    with st.spinner("Submitting data to AGOL..."):
                        success, message = submit_data_to_agol(feature_data)
                    
                    if success:
                        st.success(f"✅ {message}")
                        st.balloons()
                        
                        # Clear the cache so new data will be loaded
                        st.cache_data.clear()
                        
                        st.info("Data has been submitted successfully! Refresh the page to see the new record in the Summary Table and maps.")
                        
                        # Show submitted data
                        with st.expander("View Submitted Data"):
                            st.json(feature_data)
                    else:
                        st.error(f"❌ {message}")
                        st.info("Please check your AGOL token has write permissions and try again.")

if __name__ == "__main__":
    main()


