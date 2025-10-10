"""
Our Impact Dashboard
Aggregated metrics from multiple dashboards showing overall GCF impact
"""

import streamlit as st
import pandas as pd
import geopandas as gpd
from datetime import datetime, timedelta, date
import plotly.express as px
import plotly.graph_objects as go
import json
import os
import sys
import requests
from pathlib import Path

# Import functions from other dashboards
sys.path.append(str(Path(__file__).parent.parent))

# Try to import translocation functions
try:
    from translocation_dashboard.app import get_translocation_events, LOCATION_AREAS
    TRANSLOCATION_AVAILABLE = True
except ImportError:
    TRANSLOCATION_AVAILABLE = False

# Ecoscope imports for EarthRanger integration
try:
    from ecoscope.io.earthranger import EarthRangerIO
    ECOSCOPE_AVAILABLE = True
except ImportError:
    ECOSCOPE_AVAILABLE = False

# Custom CSS for better styling
st.markdown("""
<style>
    .impact-header {
        background: linear-gradient(90deg, #2E8B57 0%, #3CB371 100%);
        padding: 2rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .impact-title {
        font-size: 3rem;
        font-weight: bold;
        margin-bottom: 0.5rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
    }
    .impact-subtitle {
        font-size: 1.5rem;
        font-weight: 300;
        opacity: 0.9;
    }
    .metric-card {
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        padding: 1.5rem;
        border-radius: 10px;
        border: 1px solid #dee2e6;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin: 1rem 0;
    }
    .metric-value {
        font-size: 2.5rem;
        font-weight: bold;
        color: #2E8B57;
        margin-bottom: 0.5rem;
    }
    .metric-label {
        font-size: 1.1rem;
        color: #6c757d;
        font-weight: 500;
    }
    .metric-description {
        font-size: 0.9rem;
        color: #868e96;
        margin-top: 0.5rem;
    }
    .section-header {
        color: #2E8B57;
        font-size: 1.8rem;
        font-weight: bold;
        margin: 2rem 0 1rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 3px solid #2E8B57;
    }
    .placeholder-section {
        background-color: #f8f9fa;
        border: 2px dashed #6c757d;
        border-radius: 10px;
        padding: 2rem;
        text-align: center;
        color: #6c757d;
        margin: 1rem 0;
    }
    .placeholder-title {
        font-size: 1.5rem;
        font-weight: bold;
        margin-bottom: 1rem;
    }
    .placeholder-text {
        font-size: 1rem;
        font-style: italic;
    }
</style>
""", unsafe_allow_html=True)

def init_session_state():
    """Initialize session state variables"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'username' not in st.session_state:
        st.session_state.username = ""
    if 'password' not in st.session_state:
        st.session_state.password = ""
    if 'server_url' not in st.session_state:
        st.session_state.server_url = "https://twiga.pamdas.org"

def authenticate_earthranger():
    """Handle EarthRanger authentication"""
    if not ECOSCOPE_AVAILABLE:
        st.error("❌ Ecoscope package is required but not available. Please install ecoscope.")
        return
        
    st.header("🔐 EarthRanger Authentication")
    
    with st.form("auth_form"):
        st.write("Enter your EarthRanger credentials to access impact metrics:")
        
        # Fixed server URL for impact dashboard
        server_url = "https://twiga.pamdas.org"
        st.info(f"**Server:** {server_url}")
        
        # Update session state with fixed server
        st.session_state.server_url = server_url
        
        # Credentials
        username = st.text_input("Username", value=st.session_state.username)
        password = st.text_input("Password", type="password")
        
        submit_button = st.form_submit_button("🔌 Connect to EarthRanger", type="primary")
        
        if submit_button:
            if not username or not password:
                st.error("❌ Username and password are required")
                return
            
            with st.spinner(f"Authenticating with {server_url}..."):
                if test_er_connection(username, password, server_url):
                    st.session_state.authenticated = True
                    st.session_state.username = username
                    st.session_state.password = password
                    st.success(f"✅ Successfully authenticated with {server_url}!")
                    st.rerun()
                else:
                    st.error("❌ Authentication failed. Please check your credentials.")

def get_zotero_giraffe_management_plans(library_id, library_type="group", api_key=None, collection_key=None):
    """
    Count management plans with 'giraffe' tag in Zotero library
    
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
        response = requests.get(url, params=params, headers=headers)
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
                management_plans.append({
                    "title": data.get("title", "Unknown"),
                    "authors": ", ".join([creator.get("lastName", "") + ", " + creator.get("firstName", "") 
                                        for creator in data.get("creators", [])]),
                    "date": data.get("date", "Unknown"),
                    "item_type": data.get("itemType", "Unknown"),
                    "url": data.get("url", ""),
                    "tags": [tag.get("tag", "") for tag in data.get("tags", [])]
                })
        
        return len(management_plans), management_plans
        
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching Zotero data: {str(e)}")
        return 0, []
    except Exception as e:
        st.error(f"Error processing Zotero data: {str(e)}")
        return 0, []

def test_er_connection(username, password, server_url):
    """Test EarthRanger connection"""
    try:
        er = EarthRangerIO(
            server=server_url,
            username=username,
            password=password
        )
        # Test with a simple query
        er.get_subjects(limit=1)
        return True
    except Exception:
        return False

def get_range_expansion_metrics(start_date, end_date):
    """Calculate range expansion metrics from translocation data - FOUNDER POPULATIONS ONLY"""
    if not TRANSLOCATION_AVAILABLE:
        return 0, 0, []
    
    try:
        # Get translocation events
        events_df = get_translocation_events(start_date, end_date)
        
        if events_df.empty:
            return 0, 0, []
        
        total_founder_translocations = 0
        total_range_secured = 0
        range_details = []
        processed_locations = set()  # Track unique locations to avoid double counting
        
        for idx, event in events_df.iterrows():
            event_details = event.get('event_details', {})
            if isinstance(event_details, dict):
                trans_type = event_details.get('trans_type')
                
                # Only count FOUNDER translocations
                if trans_type and trans_type.lower() == 'founder':
                    total_founder_translocations += 1
                    
                    # Extract species information
                    species = event_details.get('species') or event_details.get('animal_species') or 'Unknown'
                    if isinstance(species, dict):
                        species = species.get('name') or species.get('species') or 'Unknown'
                    elif not isinstance(species, str):
                        species = str(species) if species else 'Unknown'
                    
                    # Get destination location using same priority as translocation dashboard
                    dest_location = (event_details.get('destination_site') or
                                   event_details.get('destination_location') or 
                                   event_details.get('dest_location') or 
                                   event_details.get('to_location') or
                                   event_details.get('Destination Location') or
                                   event_details.get('destination_location_name') or
                                   event_details.get('dest_location_name'))
                    
                    # Ensure dest_location is a string, not a dict or other type
                    if dest_location:
                        if isinstance(dest_location, dict):
                            # If it's a dict, try to extract a meaningful location name
                            dest_location = (dest_location.get('name') or 
                                           dest_location.get('location') or 
                                           dest_location.get('place') or
                                           str(dest_location))
                        elif not isinstance(dest_location, str):
                            dest_location = str(dest_location)
                        
                        # Create unique key for location to avoid double counting
                        location_key = dest_location.lower().strip()
                        
                        if location_key not in processed_locations:
                            processed_locations.add(location_key)
                            
                            # Calculate area using same logic as translocation dashboard
                            area_km2 = 0
                            if dest_location and 'iona' in dest_location.lower():
                                area_km2 = 15200
                                dest_location = "Iona National Park"  # Standardize the name
                            elif dest_location and 'cuatir' in dest_location.lower():
                                area_km2 = 400
                                dest_location = "Cuatir"  # Standardize the name
                            else:
                                # Look up the area for this location in the dictionary
                                area_km2 = LOCATION_AREAS.get(dest_location, 0)
                            
                            if area_km2 > 0:
                                total_range_secured += area_km2
                                range_details.append({
                                    'location': dest_location,
                                    'area_km2': area_km2,
                                    'species': species,
                                    'date': event['time'].strftime('%Y-%m-%d') if 'time' in event else 'Unknown'
                                })
        
        return total_founder_translocations, total_range_secured, range_details
        
    except Exception as e:
        st.error(f"Error calculating range expansion metrics: {str(e)}")
        # Add debug information
        st.error(f"Debug info: Exception type: {type(e).__name__}")
        if 'event_details' in locals():
            st.error(f"Sample event_details keys: {list(event_details.keys()) if isinstance(event_details, dict) else 'Not a dict'}")
            if 'trans_type' in locals():
                st.error(f"Sample trans_type: {trans_type}")
            if 'dest_location' in locals():
                st.error(f"Sample dest_location: {dest_location} (type: {type(dest_location)})")
        return 0, 0, []

def create_metric_card(value, label, description="", icon="📊"):
    """Create a styled metric card"""
    return f"""
    <div class="metric-card">
        <div style="display: flex; align-items: center; margin-bottom: 1rem;">
            <span style="font-size: 2rem; margin-right: 1rem;">{icon}</span>
            <div>
                <div class="metric-value">{value}</div>
                <div class="metric-label">{label}</div>
            </div>
        </div>
        {f'<div class="metric-description">{description}</div>' if description else ''}
    </div>
    """

def create_placeholder_section(title, description):
    """Create a placeholder section for future metrics"""
    return f"""
    <div class="placeholder-section">
        <div class="placeholder-title">🚧 {title}</div>
        <div class="placeholder-text">{description}</div>
    </div>
    """

def impact_dashboard():
    """Main impact dashboard interface"""
    
    # Header
    st.markdown("""
    <div class="impact-header">
        <div class="impact-title">🌍 Our Impact</div>
        <div class="impact-subtitle">GCF's Conservation Impact Dashboard</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Date range filter that applies to all sections
    st.markdown('<div class="section-header">📅 Impact Period</div>', unsafe_allow_html=True)
    st.write("Select the date range to analyze GCF's conservation impact:")
    
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "Start Date",
            value=date.today() - timedelta(days=365),  # Default to last year
            help="Select the earliest date for impact analysis"
        )
    
    with col2:
        end_date = st.date_input(
            "End Date", 
            value=date.today(),
            help="Select the latest date for impact analysis"
        )
    
    if start_date > end_date:
        st.error("Start date must be before end date")
        return
    
    # Date range summary
    days_diff = (end_date - start_date).days
    st.info(f"📊 Analyzing {days_diff} days of impact data from {start_date.strftime('%B %d, %Y')} to {end_date.strftime('%B %d, %Y')}")
    
    # Range Expansion Section
    st.markdown('<div class="section-header">🗺️ Range Expansion</div>', unsafe_allow_html=True)
    
    with st.spinner("Calculating range expansion metrics..."):
        num_founder_translocations, total_km2, range_details = get_range_expansion_metrics(start_date, end_date)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(
            create_metric_card(
                value=f"{num_founder_translocations:,}",
                label="Founder Translocations Completed",
                description=f"Number of founder population translocations from {start_date.strftime('%Y')} to {end_date.strftime('%Y')}",
                icon="🚁"
            ),
            unsafe_allow_html=True
        )
    
    with col2:
        st.markdown(
            create_metric_card(
                value=f"{total_km2:,}",
                label="km² of New Range Secured",
                description="Total area of new habitat secured through founder translocations",
                icon="🗺️"
            ),
            unsafe_allow_html=True
        )
    
    # Range details
    if range_details:
        with st.expander("📋 Range Expansion Details"):
            details_df = pd.DataFrame(range_details)
            st.dataframe(details_df, use_container_width=True)
    
    # Placeholder sections for future metrics
    st.markdown('<div class="section-header">📋 Management Plans</div>', unsafe_allow_html=True)
    
    # Hard-coded Zotero configuration for GCF Reports External library
    st.info("📚 Connected to GCF Reports External library")
    
    # Hard-coded values
    zotero_library_id = "5147973"
    library_type = "group"
    zotero_api_key = "yWn1NPGtfjZOVDyeulrhcczL"
    collection_key = "ITF8Y3QF"
    
    # Fetch and display management plans data
    with st.spinner("Fetching management plans from Zotero..."):
        num_plans, plan_details = get_zotero_giraffe_management_plans(
            library_id=zotero_library_id,
            library_type=library_type,
            api_key=zotero_api_key,
            collection_key=collection_key
        )
        
        # Display metric
        st.markdown(
            create_metric_card(
                value=f"{num_plans:,}",
                label="Management Plans with Giraffe Targets",
                description=f"Number of management plans tagged with 'giraffe' in Zotero library",
                icon="📋"
            ),
            unsafe_allow_html=True
        )
        
        # Show plan details
        if plan_details:
            with st.expander("📋 Management Plan Details"):
                plans_df = pd.DataFrame(plan_details)
                st.dataframe(plans_df, use_container_width=True)
    
    st.markdown('<div class="section-header">📈 Population Growth</div>', unsafe_allow_html=True)
    st.markdown(
        create_placeholder_section(
            "Population Growth Rates",
            "This section will display population growth rates across different giraffe populations, showing conservation success through demographic monitoring."
        ),
        unsafe_allow_html=True
    )
    
    st.markdown('<div class="section-header">🧬 Genetic Diversity</div>', unsafe_allow_html=True)
    st.markdown(
        create_placeholder_section(
            "Genetic Diversity Index",
            "This section will show genetic diversity metrics calculated from genetic sampling data, indicating the health and viability of giraffe populations."
        ),
        unsafe_allow_html=True
    )
    
    # Footer with methodology
    st.markdown('<div class="section-header">📖 Methodology</div>', unsafe_allow_html=True)
    
    with st.expander("ℹ️ How Impact Metrics are Calculated"):
        st.markdown("""
        **Range Expansion Metrics:**
        - **Translocations**: Count of completed giraffe translocation events from EarthRanger data
        - **Range Secured**: Total area (km²) of new habitat based on destination locations
        - Areas are calculated using predefined location area mappings
        
        **Data Sources:**
        - Translocation data: EarthRanger translocation events
        - Area calculations: GCF location area database
        
        **Date Filtering:**
        - All metrics are filtered by the selected date range
        - Duplicate locations are deduplicated to avoid double-counting range areas
        """)

def main():
    """Main application entry point"""
    # Remove set_page_config() as it's handled by the main Streamlit app
    
    # Initialize session state
    init_session_state()
    
    # Authentication check
    if not st.session_state.authenticated:
        authenticate_earthranger()
        return
    
    # Main dashboard
    impact_dashboard()

if __name__ == "__main__":
    main()