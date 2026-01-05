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

def get_zotero_giraffe_management_plans(library_id, library_type="group", api_key=None, collection_key=None):
    """
    Count management plans with 'giraffe' tag in Zotero library
    Adapted from impact_dashboard
    
    Args:
        library_id (str): Zotero library ID 
        library_type (str): 'group' or 'user' library
        api_key (str): Zotero API key (optional for public libraries)
        collection_key (str): Specific collection/subfolder key (optional)
    
    Returns:
        int: Number of items with 'giraffe' tag
        list: List of items with details
    """
    try:
        # Base URL for Zotero API
        base_url = f"https://api.zotero.org/{library_type}s/{library_id}"
        
        # Build URL
        if collection_key:
            url = f"{base_url}/collections/{collection_key}/items"
        else:
            url = f"{base_url}/items"
        
        # Parameters
        params = {
            "format": "json",
            "tag": "giraffe",  # Filter by giraffe tag
            "itemType": "-attachment",  # Exclude attachments
            "limit": 100  # Adjust as needed
        }
        
        # Headers
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        # Make request
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        
        items = response.json()
        
        # Filter for management plans (by title keywords or item type)
        management_plan_keywords = [
            "management plan", "conservation plan", "action plan", 
            "strategy", "management strategy", "conservation strategy"
        ]
        
        management_plans = []
        for item in items:
            data = item.get("data", {})
            title = data.get("title", "").lower()
            item_type = data.get("itemType", "")
            
            # Check if it's likely a management plan
            is_management_plan = any(keyword in title for keyword in management_plan_keywords)
            
            if is_management_plan or item_type in ["report", "document"]:
                # Extract location/country from tags or title
                tags = [tag.get("tag", "") for tag in data.get("tags", [])]
                
                management_plans.append({
                    "title": data.get("title", "Unknown"),
                    "authors": ", ".join([creator.get("lastName", "") + ", " + creator.get("firstName", "") 
                                        for creator in data.get("creators", [])]),
                    "date": data.get("date", "Unknown"),
                    "item_type": data.get("itemType", "Unknown"),
                    "url": data.get("url", ""),
                    "tags": tags,
                    "country": extract_country_from_tags_or_title(tags, data.get("title", ""))
                })
        
        return len(management_plans), management_plans
        
    except requests.exceptions.RequestException as e:
        # Silent fail - status will be shown in Data Source Status section
        return 0, []
    except Exception as e:
        # Silent fail - status will be shown in Data Source Status section
        return 0, []

def extract_country_from_tags_or_title(tags, title):
    """Extract country name from tags or title"""
    # Common African countries where giraffe occur
    giraffe_countries = [
        'Angola', 'Benin', 'Botswana', 'Burkina Faso', 'Cameroon', 'CAR', 'Central African Republic',
        'Chad', 'DRC', 'Democratic Republic of Congo', 'Ethiopia', 'Kenya', 'Malawi', 
        'Mozambique', 'Namibia', 'Niger', 'Nigeria', 'Rwanda', 'Somalia', 'South Africa', 
        'South Sudan', 'Sudan', 'Tanzania', 'Uganda', 'Zambia', 'Zimbabwe'
    ]
    
    # Check tags first
    for tag in tags:
        for country in giraffe_countries:
            if country.lower() in tag.lower():
                return country
    
    # Check title
    title_lower = title.lower()
    for country in giraffe_countries:
        if country.lower() in title_lower:
            return country
    
    return "Unknown"

@st.cache_data(ttl=86400)  # Cache for 24 hours
def load_wdpa_data_from_gee():
    """
    Load WDPA Africa data from Google Earth Engine
    Returns pandas DataFrame with protected areas and debug info
    """
    success, debug_info = initialize_gee()
    
    if not GEE_AVAILABLE or not success:
        return None, debug_info
    
    try:
        debug_info.append("🔄 Loading WDPA from GEE...")
        # Load WDPA feature collection from GEE
        wdpa = ee.FeatureCollection(WDPA_GEE_ASSET)
        debug_info.append(f"✅ WDPA asset loaded: {WDPA_GEE_ASSET}")
        
        # Filter for African countries - use ISO3 field instead of PARENT_ISO3
        wdpa_africa = wdpa.filter(ee.Filter.inList('ISO3', AFRICAN_COUNTRIES_ISO3))
        debug_info.append(f"✅ Filtered for {len(AFRICAN_COUNTRIES_ISO3)} African countries")
        
        # Count features first
        count = wdpa_africa.size().getInfo()
        debug_info.append(f"📊 Total matching features: {count}")
        
        if count == 0:
            debug_info.append("⚠️ No features found - trying PARENT_ISO3 field...")
            wdpa_africa = wdpa.filter(ee.Filter.inList('PARENT_ISO3', AFRICAN_COUNTRIES_ISO3))
            count = wdpa_africa.size().getInfo()
            debug_info.append(f"📊 Total with PARENT_ISO3: {count}")
        
        # Get feature info (limit to reasonable number for UI)
        debug_info.append("🔄 Fetching features (limit 2000)...")
        features = wdpa_africa.limit(2000).getInfo()['features']
        debug_info.append(f"✅ Retrieved {len(features)} features")
        
        # Extract properties and geometry
        data = []
        for feature in features:
            props = feature.get('properties', {})
            geom = feature.get('geometry', None)
            if props:  # Only add if properties exist
                props['geometry'] = geom  # Keep geometry for spatial operations
                data.append(props)
        
        # Convert to DataFrame
        df = pd.DataFrame(data) if data else pd.DataFrame()
        debug_info.append(f"✅ Created DataFrame with {len(df)} rows")
        
        return df, debug_info
            
    except Exception as e:
        debug_info.append(f"❌ Error loading WDPA: {str(e)}")
        import traceback
        debug_info.append(f"📜 Traceback: {traceback.format_exc()[:300]}")
        return None, debug_info

def get_wdpa_list(wdpa_df, countries=None, min_area=0):
    """
    Get list of protected areas from WDPA DataFrame
    
    Args:
        wdpa_df: DataFrame with WDPA data from GEE
        countries: List of ISO3 country codes to filter (optional)
        min_area: Minimum area in km² (optional)
    
    Returns:
        Filtered DataFrame
    """
    if wdpa_df is None or len(wdpa_df) == 0:
        return None
    
    filtered = wdpa_df.copy()
    
    # Filter by country
    if countries:
        # Check which ISO3 columns exist
        iso3_cols = []
        if 'ISO3' in filtered.columns:
            iso3_cols.append('ISO3')
        if 'PARENT_ISO3' in filtered.columns:
            iso3_cols.append('PARENT_ISO3')
        
        if iso3_cols:
            # Build filter condition
            mask = filtered[iso3_cols[0]].isin(countries)
            for col in iso3_cols[1:]:
                mask = mask | filtered[col].isin(countries)
            filtered = filtered[mask]
    
    # Filter by minimum area
    if min_area > 0:
        if 'REP_AREA' in filtered.columns:
            filtered = filtered[filtered['REP_AREA'] >= min_area]
        elif 'GIS_AREA' in filtered.columns:
            filtered = filtered[filtered['GIS_AREA'] >= min_area]
    
    return filtered

def get_protected_area_info(pa_name, wdpa_df):
    """
    Get protected area information by name from WDPA DataFrame
    
    Args:
        pa_name: Name of the protected area
        wdpa_df: DataFrame with WDPA data from GEE
    
    Returns:
        dict: Protected area information or None
    """
    if wdpa_df is None or len(wdpa_df) == 0:
        return None
    
    try:
        # Find PA by name
        pa_data = wdpa_df[wdpa_df['NAME'] == pa_name]
        
        if pa_data.empty:
            return None
        
        pa = pa_data.iloc[0]
        
        # Calculate centroid from geometry if available
        lat, lon = None, None
        if 'geometry' in pa and pa['geometry'] is not None:
            try:
                geom = pa['geometry']
                if isinstance(geom, dict):
                    if geom['type'] == 'Polygon':
                        coords = geom['coordinates'][0]
                        lons = [c[0] for c in coords]
                        lats = [c[1] for c in coords]
                        lon = sum(lons) / len(lons)
                        lat = sum(lats) / len(lats)
                    elif geom['type'] == 'Point':
                        lon = geom['coordinates'][0]
                        lat = geom['coordinates'][1]
            except:
                pass
        
        return {
            'name': pa.get('NAME', pa.get('ORIG_NAME', 'Unknown')),
            'country': pa.get('ISO3', pa.get('PARENT_ISO3', 'Unknown')),
            'iucn_cat': pa.get('IUCN_CAT', 'Unknown'),
            'status': pa.get('STATUS', 'Unknown'),
            'area_km2': pa.get('REP_AREA', pa.get('GIS_AREA', 0)),
            'gov_type': pa.get('GOV_TYPE', 'Unknown'),
            'mgmt_auth': pa.get('MANG_AUTH', 'Unknown'),
            'designation': pa.get('DESIG', pa.get('DESIG_ENG', 'Unknown')),
            'desig_type': pa.get('DESIG_TYPE', 'Unknown'),
            'lat': lat,
            'lon': lon
        }
        
    except Exception as e:
        st.warning(f"Error querying WDPA data: {str(e)}")
        return None

def initialize_gee():
    """
    Initialize Google Earth Engine with authentication
    Tries service account first (for deployment), then user credentials
    Returns True if successful, False otherwise
    """
    global GEE_INITIALIZED
    
    debug_info = []
    
    if not GEE_AVAILABLE:
        debug_info.append("❌ GEE module not available")
        return False, debug_info
    
    debug_info.append("✅ GEE module imported")
    
    # Check if already initialized
    try:
        ee.Number(1).getInfo()  # Test if already initialized
        GEE_INITIALIZED = True
        debug_info.append("✅ GEE already initialized")
        return True, debug_info
    except Exception as e:
        debug_info.append(f"ℹ️ Not yet initialized: {str(e)[:50]}")
    
    try:
        # Debug: Show what's in secrets
        debug_info.append(f"📋 Available secrets sections: {list(st.secrets.keys())}")
        
        # Try service account authentication from secrets (for deployment)
        if "gee_service_account" in st.secrets:
            debug_info.append("✅ Found gee_service_account in secrets")
            service_account = st.secrets["gee_service_account"]["client_email"]
            debug_info.append(f"📧 Service account: {service_account}")
            
            # Check if we have full credentials
            if "private_key" in st.secrets["gee_service_account"]:
                debug_info.append("🔑 Private key found in credentials")
                try:
                    # Create credentials using google-auth library directly
                    import json
                    from google.oauth2 import service_account
                    
                    # Convert streamlit secrets to dict
                    credentials_dict = dict(st.secrets["gee_service_account"])
                    debug_info.append("✅ Converted secrets to dict")
                    
                    # Create Google credentials object
                    credentials = service_account.Credentials.from_service_account_info(
                        credentials_dict,
                        scopes=['https://www.googleapis.com/auth/earthengine']
                    )
                    debug_info.append("✅ Google service account credentials created")
                    
                    # Initialize Earth Engine with credentials
                    ee.Initialize(credentials)
                    debug_info.append("✅ ee.Initialize() called with service account")
                    
                    # Verify it worked
                    ee.Number(1).getInfo()
                    debug_info.append("✅ GEE test query successful!")
                    GEE_INITIALIZED = True
                    return True, debug_info
                except Exception as e:
                    debug_info.append(f"❌ Service account init failed: {str(e)}")
                    import traceback
                    debug_info.append(f"📋 Traceback: {traceback.format_exc()[:200]}")
            else:
                debug_info.append("❌ Private key not found in credentials")
        else:
            debug_info.append("⚠️ gee_service_account not in secrets")
    except Exception as e:
        debug_info.append(f"❌ Service account error: {str(e)}")
    
    try:
        # Try to initialize with existing user credentials (local development)
        debug_info.append("🔄 Trying user credentials...")
        ee.Initialize()
        debug_info.append("✅ ee.Initialize() called with user credentials")
        # Verify it worked
        ee.Number(1).getInfo()
        debug_info.append("✅ GEE test query successful with user auth!")
        GEE_INITIALIZED = True
        return True, debug_info
    except Exception as e:
        debug_info.append(f"❌ User credentials failed: {str(e)}")
        GEE_INITIALIZED = False
        return False, debug_info

@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_bii_from_gee(lat, lon, resolution='8km'):
    """
    Extract BII (Biodiversity Intactness Index) value from Google Earth Engine
    
    Args:
        lat (float): Latitude
        lon (float): Longitude
        resolution (str): '1km' or '8km' resolution
    
    Returns:
        dict: Dictionary with BII values or None if error
    """
    if not GEE_AVAILABLE:
        return None
    
    gee_status, _ = initialize_gee()
    if not gee_status:
        return None
    
    try:
        # Define point
        point = ee.Geometry.Point([lon, lat])
        
        # Load BII dataset based on resolution
        if resolution == '1km':
            bii_collection = ee.ImageCollection("projects/earthengine-legacy/assets/projects/sat-io/open-datasets/BII/BII_1km")
            bands = ['Land Use', 'Land Use Intensity', 'BII All',
                    'BII Amphibians', 'BII Birds', 'BII Forbs', 'BII Graminoids',
                    'BII Mammals', 'BII All Plants', 'BII Reptiles', 'BII Trees',
                    'BII All Vertebrates']
        else:  # 8km
            bii_collection = ee.ImageCollection("projects/earthengine-legacy/assets/projects/sat-io/open-datasets/BII/BII_8km")
            bands = ['BII All', 'BII Amphibians', 'BII Birds', 'BII Forbs', 'BII Graminoids',
                    'BII Mammals', 'BII All Plants', 'BII Reptiles', 'BII Trees',
                    'BII All Vertebrates', 'Land Use', 'Land Use Intensity']
        
        # Load mask
        mask = ee.Image("projects/earthengine-legacy/assets/projects/sat-io/open-datasets/BII/BII_Mask")
        
        # Process the dataset
        bii_image = bii_collection.toBands().rename(bands)
        bii_processed = bii_image.select('^BII.*').selfMask()
        
        # Apply land use mask
        lcMask = bii_image.select('Land Use').neq(2).And(bii_image.select('Land Use').neq(5))
        LUI = bii_image.select('Land Use Intensity').updateMask(lcMask)
        bii_final = bii_processed.addBands([bii_image.select('Land Use'), LUI]).updateMask(mask)
        
        # Sample at the point
        sample = bii_final.sample(
            region=point,
            scale=1000 if resolution == '1km' else 8000,
            geometries=True
        ).first()
        
        # Extract values
        if sample:
            properties = sample.getInfo()['properties']
            
            # Return key BII metrics
            return {
                'bii_all': properties.get('BII All'),
                'bii_mammals': properties.get('BII Mammals'),
                'bii_birds': properties.get('BII Birds'),
                'bii_reptiles': properties.get('BII Reptiles'),
                'bii_plants': properties.get('BII All Plants'),
                'land_use': properties.get('Land Use'),
                'land_use_intensity': properties.get('Land Use Intensity'),
                'resolution': resolution
            }
        
        return None
        
    except Exception as e:
        st.warning(f"Error extracting BII from GEE: {str(e)}")
        return None

def convert_bii_to_connectivity_rank(bii_value):
    """
    Convert BII value (0-1) to connectivity/intactness rank (1-5)
    
    Args:
        bii_value (float): BII value between 0 and 1
    
    Returns:
        int: Rank from 1 (low connectivity) to 5 (high connectivity)
    """
    if bii_value is None or pd.isna(bii_value):
        return 3  # Default to middle
    
    # Convert BII to rank
    if bii_value >= 0.8:
        return 5  # Very high intactness
    elif bii_value >= 0.6:
        return 4  # High intactness
    elif bii_value >= 0.4:
        return 3  # Moderate intactness
    elif bii_value >= 0.2:
        return 2  # Low intactness
    else:
        return 1  # Very low intactness

def get_vegetation_suitability_from_gee(geometry):
    """
    Extract mean vegetation suitability for a protected area polygon from GEE
    
    Args:
        geometry: GEE geometry (Polygon or MultiPolygon) or GeoJSON dict
    
    Returns:
        float: Mean vegetation suitability (0-1 scale, where 0=unsuitable, 1=suitable) or None if error
    """
    if not GEE_AVAILABLE:
        return None
    
    gee_status, _ = initialize_gee()
    if not gee_status:
        return None
    
    try:
        # Convert geometry to EE geometry if needed
        if isinstance(geometry, dict):
            ee_geom = ee.Geometry(geometry)
        else:
            ee_geom = geometry
        
        # Load giraffe vegetation suitability raster from GEE Assets
        veg_suitability = ee.Image('projects/translocation-priority/assets/giraffe_veg_suitability')
        
        # Calculate mean within polygon
        stats = veg_suitability.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=ee_geom,
            scale=1000,  # 1km resolution (adjust based on your raster)
            maxPixels=1e9,
            bestEffort=True
        )
        
        # Get the mean value - your asset uses band 'b1'
        info = stats.getInfo()
        mean_value = info.get('b1')
        
        if mean_value is not None:
            # Clamp to 0-1 range just in case
            return max(0, min(1, float(mean_value)))
        else:
            return None
        
    except Exception as e:
        return None

@st.cache_data
def load_bii_raster():
    """Load Biodiversity Intactness Index raster (DEPRECATED - use GEE instead)"""
    if not RASTERIO_AVAILABLE:
        return None
    
    try:
        if os.path.exists(BII_RASTER_PATH):
            return str(BII_RASTER_PATH)
        else:
            return None
    except Exception as e:
        return None

def get_bii_value(lat, lon, raster_path=None):
    """
    Extract BII value at a given coordinate (tries GEE first, falls back to local raster)
    
    Args:
        lat (float): Latitude
        lon (float): Longitude
        raster_path (str): Path to BII raster file (optional, for fallback)
    
    Returns:
        float: BII value (0-1) or None if error
    """
    # Try Google Earth Engine first
    if GEE_AVAILABLE and initialize_gee():
        bii_data = get_bii_from_gee(lat, lon, resolution='8km')
        if bii_data and bii_data.get('bii_all') is not None:
            return bii_data['bii_all']
    
    # Fallback to local raster if available
    if RASTERIO_AVAILABLE and raster_path:
        try:
            with rasterio.open(raster_path) as src:
                # Sample the raster at the point
                vals = list(sample_gen(src, [(lon, lat)]))
                if vals and len(vals) > 0:
                    bii_value = vals[0][0]
                    # Handle nodata values
                    if bii_value != src.nodata:
                        return float(bii_value)
        except Exception as e:
            st.warning(f"Error extracting BII value from local raster: {str(e)}")
    
    return None

@st.cache_data(ttl=86400)  # Cache for 24 hours
def get_world_bank_political_stability(country_code=None, latest_year=True):
    """
    Get Political Stability and Absence of Violence/Terrorism indicator from World Bank
    Indicator: PV.EST
    
    Args:
        country_code (str): ISO3 country code (e.g., 'KEN', 'TZA'). None for all countries.
        latest_year (bool): If True, get only the most recent year
    
    Returns:
        dict or pd.DataFrame: Political stability data
    """
    indicator = "PV.EST"  # Political Stability and Absence of Violence/Terrorism
    
    try:
        if WBGAPI_AVAILABLE:
            # Using wbgapi (recommended)
            if country_code:
                data = wb.data.DataFrame(indicator, country_code, time=range(2010, 2030))
                if latest_year and not data.empty:
                    # Get most recent non-null value
                    latest = data.dropna().iloc[-1] if not data.dropna().empty else None
                    return {'country': country_code, 'value': latest, 'year': data.dropna().index[-1]} if latest is not None else None
                return data
            else:
                # Get all countries
                data = wb.data.DataFrame(indicator, wb.region.members('AFR'), time=range(2010, 2030))
                if latest_year:
                    # Get most recent year for each country
                    latest_data = []
                    for country in data.index:
                        country_data = data.loc[country].dropna()
                        if not country_data.empty:
                            latest_data.append({
                                'country': country,
                                'value': country_data.iloc[-1],
                                'year': country_data.index[-1]
                            })
                    return pd.DataFrame(latest_data)
                return data
                
        elif WBDATA_AVAILABLE:
            # Using wbdata (alternative)
            import datetime
            date_range = (datetime.datetime(2010, 1, 1), datetime.datetime.now())
            
            if country_code:
                data = wbdata.get_dataframe({indicator: "stability"}, country=country_code, date=date_range)
                if latest_year and not data.empty:
                    latest = data['stability'].dropna().iloc[-1] if not data['stability'].dropna().empty else None
                    return {'country': country_code, 'value': latest} if latest is not None else None
                return data
            else:
                # Get African countries
                countries = wbdata.get_country(incomelevel=['LIC', 'LMC', 'UMC', 'HIC'], display=False)
                african_codes = [c['id'] for c in countries if 'Africa' in c.get('region', {}).get('value', '')]
                data = wbdata.get_dataframe({indicator: "stability"}, country=african_codes, date=date_range)
                return data
        else:
            st.warning("World Bank API library not available")
            return None
            
    except Exception as e:
        st.warning(f"Error fetching World Bank data: {str(e)}")
        return None

def convert_stability_to_rank(value):
    """
    Convert World Bank Political Stability score to 1-5 rank
    World Bank scale: approximately -2.5 (weak) to +2.5 (strong)
    
    Returns:
        int: Rank from 1 (unstable) to 5 (very stable)
    """
    if value is None or pd.isna(value):
        return 3  # Default to middle
    
    # Convert to 1-5 scale
    if value >= 1.0:
        return 5
    elif value >= 0.5:
        return 4
    elif value >= -0.5:
        return 3
    elif value >= -1.0:
        return 2
    else:
        return 1

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

def create_map(data):
    """Create folium map with giraffe populations"""
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
        
        folium.CircleMarker(
            location=[row['y'], row['x']],
            radius=max(5, min(25, (row['Estimate'] ** 0.5) / 10)),
            popup=folium.Popup(popup_text, max_width=300),
            tooltip=f"{location_name}: {int(row['Estimate']):,} giraffe",
            color=get_subspecies_color(row['Subspecies']),
            fill=True,
            fillColor=get_subspecies_color(row['Subspecies']),
            fillOpacity=0.7,
            weight=2
        ).add_to(m)
    
    return m

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
    tab1, tab2 = st.tabs(["📊 Summary Table", "🗺️ Africa Map"])

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
        st.header("Giraffe Distribution Map")
        
        # Create and display map using HTML export
        try:
            giraffe_map = create_map(summary)
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
        
        # Three-column framework explanation
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("### 🌿 Ecological Criteria")
            st.markdown("""
            - No current giraffe population
            - Adequate area size
            - Vegetation suitability
            - Landscape connectivity (BII)
            """)
        
        with col2:
            st.markdown("### 🏛️ Governance Criteria")
            st.markdown("""
            - Political stability
            - Management structure
            - Existing management plan
            - Wildlife monitoring program
            """)
        
        with col3:
            st.markdown("### 🚁 Implementation Criteria")
            st.markdown("""
            - Threat assessment
            - Permit accessibility
            - Transport logistics
            - Stakeholder willingness
            """)
        
        st.markdown("---")
        
        # Data source selection
        st.subheader("1️⃣ Data Configuration")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Target Species/Subspecies**")
            target_species = st.selectbox(
                "Select target species for reintroduction",
                options=sorted(df['Species'].dropna().unique().tolist())
            )
            
            target_subspecies_options = sorted(
                df[df['Species'] == target_species]['Subspecies'].dropna().unique().tolist()
            )
            target_subspecies = st.selectbox(
                "Select target subspecies",
                options=target_subspecies_options
            )
        
        with col2:
            st.markdown("**Geographic Scope**")
            assessment_countries = st.multiselect(
                "Countries to assess (leave empty for all)",
                options=sorted(df['Country'].dropna().unique().tolist())
            )
            
            min_area_size = st.number_input(
                "Minimum protected area size (km²)",
                min_value=0,
                value=100,
                step=10,
                help="Filter out areas below this threshold"
            )
        
        st.markdown("---")
        
        # Load external data sources
        st.subheader("2️⃣ Data Sources & Integration")
        
        with st.expander("📊 View Data Source Status", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Geospatial Data**")
                # Load WDPA data from Google Earth Engine
                with st.spinner("Loading WDPA Africa from Google Earth Engine..."):
                    wdpa_df, wdpa_debug = load_wdpa_data_from_gee()
                
                if wdpa_df is not None and len(wdpa_df) > 0:
                    st.success(f"✅ WDPA Africa (GEE): {len(wdpa_df):,} protected areas")
                else:
                    st.warning("⚠️ Could not load WDPA from GEE. See debug info below.")
                    # Show debug info inline
                    st.markdown("**🔍 Debug Information:**")
                    for msg in wdpa_debug:
                        st.caption(msg)
                
                # Check GEE availability
                if GEE_AVAILABLE:
                    gee_status, gee_debug = initialize_gee()
                    if gee_status:
                        st.success("✅ Google Earth Engine (BII) - Connected")
                        st.caption("Using GEE for on-demand BII extraction")
                    else:
                        st.info("ℹ️ GEE: Not authenticated. Run `earthengine authenticate` to enable.")
                        st.markdown("**🔍 Authentication Details:**")
                        for msg in gee_debug:
                            st.caption(msg)
                else:
                    st.info("ℹ️ GEE: Install with `pip install earthengine-api`")
            
            with col2:
                st.markdown("**API Data**")
                # Test World Bank API
                if WBGAPI_AVAILABLE or WBDATA_AVAILABLE:
                    st.success("✅ World Bank API available")
                else:
                    st.info("ℹ️ World Bank: Install with `pip install wbgapi`")
                
                # Test Zotero API
                try:
                    # Use GCF library settings from secrets or defaults
                    zotero_lib = st.secrets.get("zotero", {}).get("library_id", "5485373")
                    zotero_key = st.secrets.get("zotero", {}).get("api_key", None)
                    
                    count, plans = get_zotero_giraffe_management_plans(zotero_lib, api_key=zotero_key)
                    if count > 0:
                        st.success(f"✅ Zotero API: {count} management plans found")
                    else:
                        st.info("ℹ️ Zotero: Connected, no giraffe management plans found")
                except Exception as e:
                    st.info("ℹ️ Zotero: Not configured or library not accessible")
        
        st.markdown("---")
        
        # Site identification
        st.subheader("3️⃣ Candidate Site Identification")
        
        st.info("🔍 Identifying protected areas with no current giraffe populations...")
        
        # Filter GAD data for sites with no/zero giraffe
        candidate_sites_df = summary.copy()
        
        # Remove Total row
        candidate_sites_df = candidate_sites_df[candidate_sites_df['Country'] != 'Total']
        
        # Filter for sites with zero or missing population
        sites_with_giraffe = candidate_sites_df[
            (candidate_sites_df['Estimate'] > 0) & 
            (candidate_sites_df['Species'] == target_species) &
            (candidate_sites_df['Subspecies'] == target_subspecies)
        ]['Site'].unique()
        
        st.write(f"Found **{len(sites_with_giraffe)}** sites with existing {target_species} ({target_subspecies}) populations")
        
        # Load WDPA data for candidate identification
        if 'wdpa_df' not in st.session_state:
            with st.spinner("Loading WDPA Africa data from GEE..."):
                result = load_wdpa_data_from_gee()
                # Handle tuple return (df, debug_info)
                if isinstance(result, tuple):
                    st.session_state['wdpa_df'] = result[0]
                else:
                    st.session_state['wdpa_df'] = result
        
        wdpa_df = st.session_state.get('wdpa_df')
        
        # If WDPA data is available, show candidate protected areas
        if wdpa_df is not None and len(wdpa_df) > 0:
            st.success("🎯 Using WDPA database from Google Earth Engine to identify candidate protected areas")
            
            # Convert country names to ISO3 codes for filtering
            country_iso_map = {
                'Kenya': 'KEN', 'Tanzania': 'TZA', 'Uganda': 'UGA', 
                'South Africa': 'ZAF', 'Namibia': 'NAM', 'Botswana': 'BWA',
                'Zimbabwe': 'ZWE', 'Zambia': 'ZMB', 'Angola': 'AGO',
                'Niger': 'NER', 'Chad': 'TCD', 'Cameroon': 'CMR',
                'Nigeria': 'NGA', 'Benin': 'BEN', 'Ethiopia': 'ETH',
                'Somalia': 'SOM', 'South Sudan': 'SSD', 'Sudan': 'SDN',
                'Mozambique': 'MOZ', 'Malawi': 'MWI', 'Rwanda': 'RWA',
                'Burkina Faso': 'BFA', 'DRC': 'COD', 'CAR': 'CAF'
            }
            
            iso3_countries = [country_iso_map.get(c, c) for c in assessment_countries] if assessment_countries else []
            
            wdpa_filtered = get_wdpa_list(wdpa_df, countries=iso3_countries, min_area=min_area_size)
            
            if wdpa_filtered is not None and len(wdpa_filtered) > 0:
                # Identify PAs with 0 giraffes by cross-referencing with GAD data
                # Get list of PAs that HAVE giraffes
                pas_with_giraffes = set()
                if 'Protected_Area' in df.columns:
                    pas_with_giraffes = set(df['Protected_Area'].dropna().unique())
                elif 'Location' in df.columns:
                    pas_with_giraffes = set(df['Location'].dropna().unique())
                
                # Filter to PAs with 0 giraffes (not in GAD dataset)
                wdpa_filtered['has_giraffes'] = wdpa_filtered['NAME'].isin(pas_with_giraffes)
                wdpa_zero_giraffes = wdpa_filtered[~wdpa_filtered['has_giraffes']].copy()
                
                st.write(f"📍 **{len(wdpa_filtered):,}** total protected areas meet criteria")
                st.write(f"🦒 **{len(wdpa_zero_giraffes):,}** protected areas with **0 giraffes** (translocation candidates)")
                
                # Show sample of PAs with 0 giraffes
                display_cols = ['NAME', 'ISO3', 'IUCN_CAT', 'REP_AREA', 'GOV_TYPE']
                available_cols = [col for col in display_cols if col in wdpa_zero_giraffes.columns]
                
                if len(available_cols) > 0:
                    sample_display = wdpa_zero_giraffes[available_cols].head(20)
                    st.dataframe(sample_display, use_container_width=True)
                    
                # Store filtered list (0 giraffes only) for assessment
                st.session_state['wdpa_filtered'] = wdpa_zero_giraffes
            else:
                st.info("No protected areas found matching the criteria")
        else:
            st.warning("⚠️ Could not load WDPA data from ArcGIS Online")
        
        st.markdown("---")
        
        # Show all 0-giraffe PAs with auto-fetched data
        st.subheader("3️⃣ All Protected Areas with 0 Giraffes - Data Overview")
        
        wdpa_zero_gir = st.session_state.get('wdpa_filtered')
        
        if wdpa_zero_gir is not None and len(wdpa_zero_gir) > 0:
            st.info(f"Showing ecological and governance data for all **{len(wdpa_zero_gir)}** PAs with 0 giraffes")
            
            # Create summary table with auto-fetched data
            summary_data = []
            
            # Initialize GEE once
            gee_initialized = False
            if GEE_AVAILABLE:
                gee_initialized, _ = initialize_gee()
            
            # Cache World Bank data by country to avoid repeated API calls
            country_stability_cache = {}
            
            # Track errors to show summary instead of spamming
            error_counts = {'geometry': 0, 'bii': 0, 'vegetation': 0, 'stability': 0}
            
            with st.spinner("Auto-fetching BII, vegetation suitability, and political stability data..."):
                progress = st.progress(0)
                total_pas = min(len(wdpa_zero_gir), 30)
                
                for idx, (_, row) in enumerate(wdpa_zero_gir.head(30).iterrows()):
                    progress.progress((idx + 1) / total_pas)
                    
                    pa_name = row.get('NAME', 'Unknown')
                    country_iso = row.get('ISO3', row.get('PARENT_ISO3', ''))
                    area = row.get('REP_AREA', row.get('GIS_AREA', 0))
                    iucn_cat = row.get('IUCN_CAT', 'N/A')
                    
                    # Extract geometry from GeoJSON dict and convert to centroid
                    geom_dict = row.get('geometry')
                    lat, lon = None, None
                    
                    try:
                        if geom_dict and isinstance(geom_dict, dict):
                            geom_type = geom_dict.get('type')
                            coords = geom_dict.get('coordinates')
                            
                            if geom_type == 'Polygon' and coords:
                                # Calculate centroid from polygon coordinates
                                outer_ring = coords[0]
                                lons = [c[0] for c in outer_ring]
                                lats = [c[1] for c in outer_ring]
                                lon = sum(lons) / len(lons)
                                lat = sum(lats) / len(lats)
                            elif geom_type == 'MultiPolygon' and coords:
                                # Use first polygon for centroid
                                outer_ring = coords[0][0]
                                lons = [c[0] for c in outer_ring]
                                lats = [c[1] for c in outer_ring]
                                lon = sum(lons) / len(lons)
                                lat = sum(lats) / len(lats)
                            elif geom_type == 'Point' and coords:
                                lon, lat = coords[0], coords[1]
                    except Exception:
                        error_counts['geometry'] += 1
                    
                    # Get BII at centroid
                    bii_value = None
                    bii_rank = None
                    if gee_initialized and lat and lon:
                        try:
                            bii_data = get_bii_from_gee(lat, lon, resolution='8km')
                            if bii_data and bii_data.get('bii_all') is not None:
                                bii_value = bii_data['bii_all']
                                bii_rank = convert_bii_to_connectivity_rank(bii_value)
                        except Exception:
                            error_counts['bii'] += 1
                    
                    # Get vegetation suitability from your GEE raster using polygon
                    veg_value = None
                    if gee_initialized and geom_dict:
                        try:
                            veg_value = get_vegetation_suitability_from_gee(geom_dict)
                        except Exception:
                            error_counts['vegetation'] += 1
                    
                    # Get political stability (cached by country)
                    stability_value = None
                    stability_rank = None
                    if (WBGAPI_AVAILABLE or WBDATA_AVAILABLE) and country_iso:
                        try:
                            if country_iso not in country_stability_cache:
                                stability = get_world_bank_political_stability(country_iso, latest_year=True)
                                if stability:
                                    country_stability_cache[country_iso] = stability
                            
                            if country_iso in country_stability_cache:
                                stability_value = country_stability_cache[country_iso].get('value')
                                stability_rank = convert_stability_to_rank(stability_value)
                        except Exception:
                            error_counts['stability'] += 1
                    
                    summary_data.append({
                        'PA Name': pa_name,
                        'Country': country_iso,
                        'Area (km²)': round(area, 1) if area else 0,
                        'IUCN': iucn_cat,
                        'BII Value': round(bii_value, 3) if bii_value is not None else 'N/A',
                        'BII Rank': f"{bii_rank}/5" if bii_rank else 'N/A',
                        'Veg Suitability': round(veg_value, 3) if veg_value is not None else 'N/A',
                        'Pol. Stability': round(stability_value, 2) if stability_value is not None else 'N/A',
                        'Stability Rank': f"{stability_rank}/5" if stability_rank else 'N/A'
                    })
                
                progress.empty()
                
                # Show error summary if any failures occurred
                if any(error_counts.values()):
                    st.caption(f"⚠️ Data extraction issues: {error_counts['geometry']} geometry, {error_counts['bii']} BII, {error_counts['vegetation']} vegetation, {error_counts['stability']} stability")
            
            if summary_data:
                summary_df = pd.DataFrame(summary_data)
                st.dataframe(summary_df, use_container_width=True, height=500)
                
                # Download button for complete list
                st.download_button(
                    "📥 Download Complete PA List with Data",
                    summary_df.to_csv(index=False),
                    "zero_giraffe_pas_data.csv",
                    "text/csv"
                )
        else:
            st.info("No PAs with 0 giraffes found. Adjust filters in Section 1.")
        
        st.markdown("---")
        
        # Batch Site Assessment with CSV
        st.subheader("4️⃣ Priority Shortlist - Ranking from CSV")
        
        st.markdown("""
        Rankings for **priority shortlist** from `translocation_assessment_guide.csv`
        
        **Process:**
        1. Section 2 identifies all PAs with **0 giraffes** in selected countries
        2. App scores only PAs listed in your CSV (your priority shortlist)
        3. Auto-fetches: Area (WDPA), BII (GEE), Stability (World Bank), Plans (Zotero)
        4. Combines with your manual CSV scores: threat_level, permit_ease, logistics_ease, stakeholder_willingness
        
        **CSV File**: `gad_dashboard/translocation_assessment_guide.csv`
        
        💡 Only PAs in your CSV will be scored and ranked. Update CSV to change priorities.
        """)
        
        # Auto-load CSV from folder
        csv_path = os.path.join(os.path.dirname(__file__), 'translocation_assessment_guide.csv')
        
        if os.path.exists(csv_path):
            try:
                manual_df = pd.read_csv(csv_path)
                
                # Filter out comment lines and empty rows
                manual_df = manual_df[~manual_df['protected_area_name'].astype(str).str.startswith('#')]
                manual_df = manual_df.dropna(subset=['protected_area_name'])
                
                st.info(f"📥 Loaded {len(manual_df)} sites with manual assessments. Now auto-fetching ecological and governance data...")
                
                # Initialize results list
                results = []
                
                # Process each site
                progress_bar = st.progress(0)
                for idx, row in manual_df.iterrows():
                    progress_bar.progress((idx + 1) / len(manual_df))
                    
                    pa_name = row['protected_area_name']
                    country_iso = row['country']
                    
                    # Get PA from WDPA
                    pa_match = wdpa_filtered[wdpa_filtered['NAME'] == pa_name] if wdpa_filtered is not None else None
                    
                    if pa_match is not None and len(pa_match) > 0:
                        pa = pa_match.iloc[0]
                        area = pa.get('REP_AREA', pa.get('GIS_AREA', 0))
                        
                        # Get centroid for BII extraction
                        lat, lon = 0, 0
                        if hasattr(pa, 'geometry') and pa.geometry is not None:
                            try:
                                centroid = pa.geometry.centroid
                                lat, lon = centroid.y, centroid.x
                            except:
                                pass
                        
                        # Calculate ecological score (50 points)
                        area_score = min(15, (area / 1000) * 1.5)
                        veg_score = 9  # Default moderate if no GEE data
                        connectivity_score = 9  # Default moderate
                        threat_score = row['threat_level'] * 1  # Manual input
                        
                        # Try to get BII if coordinates available
                        if GEE_AVAILABLE and lat != 0 and lon != 0:
                            try:
                                gee_status, _ = initialize_gee()
                                if gee_status:
                                    bii_data = get_bii_from_gee(lat, lon, resolution='8km')
                                    if bii_data and bii_data.get('bii_all') is not None:
                                        bii_rank = convert_bii_to_connectivity_rank(bii_data['bii_all'])
                                        connectivity_score = bii_rank * 3
                            except:
                                pass
                        
                        ecological_score = area_score + veg_score + connectivity_score + threat_score
                        
                        # Calculate governance score (40 points) 
                        stability_score = 9  # Default moderate
                        
                        # Try to get World Bank data
                        if (WBGAPI_AVAILABLE or WBDATA_AVAILABLE) and country_iso:
                            try:
                                stability = get_world_bank_political_stability(country_iso, latest_year=True)
                                if stability:
                                    stability_rank = convert_stability_to_rank(stability.get('value'))
                                    stability_score = stability_rank * 3
                            except:
                                pass
                        
                        mgmt_score = 8  # Default government management
                        plan_score = 0  # Default no plan
                        
                        # Try to check Zotero
                        try:
                            zotero_lib = st.secrets.get("zotero", {}).get("library_id", "5485373")
                            zotero_key = st.secrets.get("zotero", {}).get("api_key", None)
                            count, plans = get_zotero_giraffe_management_plans(zotero_lib, api_key=zotero_key)
                            if count > 0:
                                country_plans = [p for p in plans if country_iso in p['country'].upper()]
                                if country_plans:
                                    plan_score = 10
                        except:
                            pass
                        
                        monitoring_score = 0  # Assume no monitoring unless known
                        governance_score = stability_score + mgmt_score + plan_score + monitoring_score
                        
                        # Calculate logistics score (10 points) from manual inputs
                        permit_score = row['permit_ease'] * 0.8
                        transport_score = row['logistics_ease'] * 0.6
                        stakeholder_score = row['stakeholder_willingness'] * 0.6
                        logistics_score = permit_score + transport_score + stakeholder_score
                        
                        # Total score
                        total_score = ecological_score + governance_score + logistics_score
                        
                        results.append({
                            'protected_area_name': pa_name,
                            'country': country_iso,
                            'area_km2': area,
                            'ecological_score': round(ecological_score, 1),
                            'governance_score': round(governance_score, 1),
                            'logistics_score': round(logistics_score, 1),
                            'total_score': round(total_score, 1)
                        })
                    else:
                        st.warning(f"⚠️ Could not find '{pa_name}' in WDPA data")
                
                progress_bar.empty()
                
                if results:
                    # Create results dataframe
                    scores_df = pd.DataFrame(results)
                    scores_df['rank'] = scores_df['total_score'].rank(ascending=False, method='min').astype(int)
                    scores_df = scores_df.sort_values('rank')
                    
                    st.success(f"✅ Completed assessment for {len(scores_df)} sites from your CSV")
                    
                    # Display ranked results
                    st.markdown("### 📊 Ranked Sites (CSV Priority List)")
                    
                    display_df = scores_df[[
                        'rank', 'protected_area_name', 'country', 'area_km2',
                        'total_score', 'ecological_score', 'governance_score', 'logistics_score'
                    ]].copy()
                    
                    # Color code scores
                    st.dataframe(
                        display_df.style.background_gradient(subset=['total_score'], cmap='RdYlGn'),
                        use_container_width=True,
                        height=400
                    )
                    
                    # Export option
                    col1, col2 = st.columns(2)
                    with col1:
                        csv_export = scores_df.to_csv(index=False)
                        st.download_button(
                            "📥 Download Ranked Results",
                            csv_export,
                            "translocation_rankings.csv",
                            "text/csv",
                            key='download-rankings'
                        )
                    
                    with col2:
                        st.metric("Top Ranked Site", scores_df.iloc[0]['protected_area_name'])
                    
                    # Store for individual analysis
                    st.session_state['scores_df'] = scores_df
                else:
                    st.warning("⚠️ No matching PAs found. CSV names must match WDPA names exactly.")
                
            except Exception as e:
                st.error(f"Error loading CSV: {str(e)}")
                st.info("Make sure your CSV has the required columns: protected_area_name, country, threat_level, permit_ease, logistics_ease, stakeholder_willingness")
        else:
            st.error(f"❌ CSV file not found: `translocation_assessment_guide.csv`")
            st.info("💡 Create this file in the `gad_dashboard` folder with your manual assessments.")
            
            # Show example CSV structure
            with st.expander("📋 Example CSV Template"):
                example_df = pd.DataFrame({
                    'protected_area_name': ['Serengeti National Park', 'Kruger National Park', 'Etosha National Park'],
                    'country': ['TZA', 'ZAF', 'NAM'],
                    'threat_level': [3, 4, 4],
                    'permit_ease': [3, 5, 4],
                    'logistics_ease': [2, 5, 3],
                    'stakeholder_willingness': [4, 5, 4]
                })
                st.dataframe(example_df, use_container_width=True)
                st.download_button(
                    "📥 Download Template",
                    example_df.to_csv(index=False),
                    "translocation_manual_assessment_template.csv",
                    "text/csv"
                )
            

        
        st.markdown("---")
        
        # Individual Site Analysis
        st.subheader("5️⃣ Individual Site Analysis - Deep Dive")
        
        st.markdown("Select a protected area for detailed analysis with interactive map and environmental data:")
        
        # Get filtered WDPA list
        wdpa_filtered = st.session_state.get('wdpa_filtered')
        
        if wdpa_filtered is not None and len(wdpa_filtered) > 0:
            # Create dropdown of protected areas
            pa_names = sorted(wdpa_filtered['NAME'].dropna().unique().tolist())
            selected_pa_name = st.selectbox(
                "Select Protected Area for Analysis",
                options=['-- Select --'] + pa_names,
                help="Choose a protected area to view detailed analysis"
            )
            
            if selected_pa_name != '-- Select --':
                # Get selected PA details
                selected_pa = wdpa_filtered[wdpa_filtered['NAME'] == selected_pa_name].iloc[0]
                
                # Auto-populate fields from WDPA
                st.session_state['auto_site_name'] = selected_pa.get('NAME', '')
                st.session_state['auto_site_area'] = selected_pa.get('REP_AREA', selected_pa.get('GIS_AREA', 0))
                st.session_state['auto_country'] = selected_pa.get('ISO3', selected_pa.get('PARENT_ISO3', ''))
                st.session_state['auto_gov_type'] = selected_pa.get('GOV_TYPE', '')
                st.session_state['auto_iucn_cat'] = selected_pa.get('IUCN_CAT', '')
                st.session_state['auto_designation'] = selected_pa.get('DESIG_ENG', selected_pa.get('DESIG', ''))
                
                # Get centroid for coordinates
                centroid = None
                if hasattr(selected_pa, 'geometry') and selected_pa.geometry is not None:
                    try:
                        if hasattr(selected_pa.geometry, 'centroid'):
                            centroid = selected_pa.geometry.centroid
                            st.session_state['auto_lat'] = centroid.y
                            st.session_state['auto_lon'] = centroid.x
                    except Exception as e:
                        st.warning(f"Could not calculate centroid: {str(e)}")
                
                # === INTERACTIVE MAP VISUALIZATION ===
                st.markdown("### 🗺️ Protected Area Map")
                
                if centroid:
                    # Create base map centered on protected area
                    m = folium.Map(
                        location=[centroid.y, centroid.x],
                        zoom_start=9,
                        tiles='OpenStreetMap'
                    )
                    
                    # Add PA polygon boundary
                    if hasattr(selected_pa, 'geometry') and selected_pa.geometry is not None:
                        try:
                            # Convert geometry to GeoJSON
                            geojson_data = selected_pa.geometry.__geo_interface__
                            
                            folium.GeoJson(
                                geojson_data,
                                name=selected_pa_name,
                                style_function=lambda x: {
                                    'fillColor': '#3388ff',
                                    'color': '#0066cc',
                                    'weight': 3,
                                    'fillOpacity': 0.2
                                },
                                tooltip=folium.Tooltip(
                                    f"<b>{selected_pa_name}</b><br>"
                                    f"Area: {selected_pa.get('REP_AREA', 0):.1f} km²<br>"
                                    f"IUCN: {selected_pa.get('IUCN_CAT', 'N/A')}"
                                )
                            ).add_to(m)
                            
                        except Exception as e:
                            st.warning(f"Could not display PA boundary: {str(e)}")
                    
                    # Add centroid marker
                    folium.Marker(
                        [centroid.y, centroid.x],
                        popup=f"<b>{selected_pa_name}</b><br>Centroid",
                        tooltip=selected_pa_name,
                        icon=folium.Icon(color='blue', icon='info-sign')
                    ).add_to(m)
                    
                    # Layer control options
                    st.markdown("**Map Layers:**")
                    layer_cols = st.columns(4)
                    
                    with layer_cols[0]:
                        show_gad = st.checkbox("Show GAD Points", value=False, help="Display giraffe observation points from main GAD dataset")
                    with layer_cols[1]:
                        show_bii = st.checkbox("Show BII Heatmap", value=False, help="Biodiversity Intactness Index overlay (requires GEE)")
                    with layer_cols[2]:
                        show_veg = st.checkbox("Show Vegetation", value=False, help="Vegetation suitability overlay (requires GEE)")
                    with layer_cols[3]:
                        show_boundary = st.checkbox("Highlight Boundary", value=True, help="PA polygon boundary")
                    
                    # Add GAD giraffe points if requested
                    if show_gad:
                        try:
                            # Filter GAD points near this PA (within ~50km buffer)
                            buffer_deg = 0.5  # ~50km at equator
                            nearby_giraffes = df[
                                (df['Latitude'].between(centroid.y - buffer_deg, centroid.y + buffer_deg)) &
                                (df['Longitude'].between(centroid.x - buffer_deg, centroid.x + buffer_deg))
                            ]
                            
                            if len(nearby_giraffes) > 0:
                                # Add markers with clustering
                                marker_cluster = MarkerCluster(name="Giraffe Observations").add_to(m)
                                
                                for idx, row in nearby_giraffes.head(100).iterrows():  # Limit to 100 points
                                    folium.CircleMarker(
                                        location=[row['Latitude'], row['Longitude']],
                                        radius=4,
                                        popup=f"{row.get('Species', 'Giraffe')} - {row.get('Subspecies', 'Unknown')}",
                                        color='orange',
                                        fill=True,
                                        fillOpacity=0.7
                                    ).add_to(marker_cluster)
                                
                                st.caption(f"📍 Showing {min(len(nearby_giraffes), 100)} nearby giraffe observations")
                        except Exception as e:
                            st.warning(f"Could not load GAD points: {str(e)}")
                    
                    # Add layer control
                    folium.LayerControl().add_to(m)
                    
                    # Display map
                    st_folium(m, width=900, height=500)
                    
                    # Show GEE raster info if layers selected
                    if show_bii or show_veg:
                        st.info("🔄 Note: BII and Vegetation rasters require Google Earth Engine. Use 'Fetch All Data' button below to extract values.")
                
                else:
                    st.warning("Could not determine protected area location for map display")
                
                st.markdown("---")
                
                # Auto-fetch BII, World Bank, Zotero data
                if st.button("🔄 Fetch All Data for Selected Area"):
                    with st.spinner("Fetching ecological and governance data..."):
                        lat = st.session_state.get('auto_lat', 0)
                        lon = st.session_state.get('auto_lon', 0)
                        country_iso = st.session_state.get('auto_country', '')
                        
                        # Get BII value from Google Earth Engine
                        if GEE_AVAILABLE and initialize_gee() and lat != 0 and lon != 0:
                            bii_data = get_bii_from_gee(lat, lon, resolution='8km')
                            if bii_data and bii_data.get('bii_all') is not None:
                                bii_val = bii_data['bii_all']
                                bii_rank = convert_bii_to_connectivity_rank(bii_val)
                                st.session_state['auto_connectivity'] = bii_rank
                                st.session_state['auto_bii_data'] = bii_data
                                
                                st.success(f"✅ BII All: {bii_val:.3f} → Connectivity Rank: {bii_rank}/5")
                                
                                # Show detailed BII breakdown
                                with st.expander("🔬 Detailed BII Metrics", expanded=False):
                                    bii_cols = st.columns(3)
                                    with bii_cols[0]:
                                        st.metric("Mammals", f"{bii_data.get('bii_mammals', 0):.3f}")
                                        st.metric("Birds", f"{bii_data.get('bii_birds', 0):.3f}")
                                    with bii_cols[1]:
                                        st.metric("Reptiles", f"{bii_data.get('bii_reptiles', 0):.3f}")
                                        st.metric("Plants", f"{bii_data.get('bii_plants', 0):.3f}")
                                    with bii_cols[2]:
                                        land_use_labels = {1: 'Primary', 2: 'Secondary', 3: 'Plantation', 
                                                         4: 'Cropland', 5: 'Pasture', 6: 'Urban', 
                                                         7: 'Primary Minimal', 8: 'Primary Light', 9: 'Primary Intense'}
                                        st.metric("Land Use", land_use_labels.get(bii_data.get('land_use', 0), 'Unknown'))
                                        if bii_data.get('land_use_intensity'):
                                            st.metric("Intensity", f"{bii_data.get('land_use_intensity', 0):.2f}")
                        
                        # Get political stability
                        if (WBGAPI_AVAILABLE or WBDATA_AVAILABLE) and country_iso:
                            stability = get_world_bank_political_stability(country_iso, latest_year=True)
                            if stability:
                                stability_rank = convert_stability_to_rank(stability.get('value'))
                                st.session_state['auto_stability'] = stability_rank
                                st.success(f"✅ Political Stability: {stability.get('value', 'N/A'):.2f} → Rank: {stability_rank}/5")
                        
                        # Check for management plans
                        try:
                            zotero_lib = st.secrets.get("zotero", {}).get("library_id", "5485373")
                            zotero_key = st.secrets.get("zotero", {}).get("api_key", None)
                            count, plans = get_zotero_giraffe_management_plans(zotero_lib, api_key=zotero_key)
                            
                            # Check if any plans match this country
                            if count > 0:
                                country_plans = [p for p in plans if country_iso in p['country'].upper()]
                                if country_plans:
                                    st.session_state['auto_has_mgmt_plan'] = True
                                    st.session_state['auto_mgmt_plan_url'] = country_plans[0].get('url', '')
                                    st.success(f"✅ Found {len(country_plans)} management plan(s)")
                                    for plan in country_plans[:3]:
                                        st.info(f"📄 {plan['title']}")
                        except:
                            pass
                        
                        st.rerun()
                else:
                    st.info("ℹ️ Please select a protected area from the list above")
            else:
                st.info("ℹ️ No candidate protected areas found. Adjust filters in Data Configuration section.")
            
            st.markdown("---")
            
            # Display auto-populated summary
            if 'auto_site_name' in st.session_state and st.session_state.get('auto_site_name'):
                st.markdown("#### 📋 Auto-Populated Information")
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.metric("Protected Area", st.session_state.get('auto_site_name', 'N/A'))
                    st.metric("Area (km²)", f"{st.session_state.get('auto_site_area', 0):.1f}")
                with col_b:
                    st.metric("Country", st.session_state.get('auto_country', 'N/A'))
                    st.metric("IUCN Category", st.session_state.get('auto_iucn_cat', 'N/A'))
                with col_c:
                    st.metric("BII Connectivity", f"{st.session_state.get('auto_connectivity', 3)}/5")
                    st.metric("Political Stability", f"{st.session_state.get('auto_stability', 3)}/5")
            
            st.markdown("---")
            # Manual assessments are now in CSV file (translocation_assessment_guide.csv)
        
        st.markdown("---")
        
        # Results section
        st.subheader("6️⃣ Summary & Export")
        
        st.info("""
        **Scoring Algorithm**: Sites are ranked using a weighted composite score (0-100 points):
        - **Ecological Score** (50%): Area size (15) + vegetation (15) + connectivity (15) + threat level (5)
        - **Governance Score** (40%): Political stability (15) + management type (10) + plans (10) + monitoring (5)
        - **Logistics Score** (10%): Permit ease (4) + transport (3) + stakeholder support (3)
        
        🟢 **High Priority** (70-100) | 🟡 **Medium Priority** (50-69) | 🔴 **Low Priority** (<50)
        
        **Next Development Steps**:
        - ✅ CSV batch upload with weighted scoring
        - ✅ Interactive map with PA boundary visualization
        - ✅ Auto-fetch BII, World Bank, Zotero data
        - 🔄 GEE raster overlays for BII and vegetation
        - 🔄 Export comprehensive reports to PDF/Excel
        - 🔄 Multi-criteria decision analysis (MCDA) visualization
        """)
        
        # Results will appear here after CSV upload in Section 3
        if 'scores_df' in st.session_state and st.session_state.get('scores_df') is not None:
            st.markdown("#### 📊 Latest Rankings")
            st.info("Results from most recent CSV upload are displayed in Section 3 above.")
        else:
            st.info("💡 Upload a CSV with manual assessments in Section 3 to see ranked results here.")
        
        st.markdown("---")
        
        st.info("""
        ### 📊 Development Roadmap
        
        **Phase 1** (Current): Automated data integration ✅
        - WDPA from ArcGIS Online ✅
        - Google Earth Engine BII ✅
        - World Bank political stability ✅
        - Zotero management plans ✅
        
        **Phase 2** (To implement):
        - Vegetation suitability rasters
        - Batch assessment workflow
        - Data persistence (CSV/database)
        
        **Phase 3** (Future):
        - Interactive map with site selection
        - Report generation and export
        - Multi-species comparison
        """)


