"""
Streamlit Multipage App Structure
This is the main entry point that uses Streamlit's built-in multipage functionality.
Much cleaner than the current complex fallback system.
"""

import streamlit as st
from pathlib import Path

# Set page config (must be first Streamlit command)
st.set_page_config(
    page_title="Twiga Tools - GCF Conservation Platform",
    #page_icon="🦒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS to force full sidebar navigation visibility
st.markdown("""
<style>
    /* Force sidebar to be full height and show all navigation items */
    .css-1d391kg, [data-testid="stSidebar"] .css-1d391kg {
        height: 100vh !important;
        max-height: 100vh !important;
        overflow-y: auto !important;
        padding-bottom: 2rem !important;
    }
    
    /* Target the navigation container specifically */
    [data-testid="stSidebar"] nav, 
    [data-testid="stSidebar"] .nav-link-container,
    [data-testid="stSidebar"] .stSelectbox > div,
    section[data-testid="stSidebar"] nav[role="navigation"] {
        max-height: none !important;
        height: auto !important;
        overflow: visible !important;
    }
    
    /* Remove any height limits on navigation lists */
    [data-testid="stSidebar"] ul,
    [data-testid="stSidebar"] .nav-wrapper,
    [data-testid="stSidebar"] .css-17lntkn {
        max-height: none !important;
        height: auto !important;
        overflow: visible !important;
    }
    
    /* Hide the expand/collapse controls */
    [data-testid="stSidebar"] .css-1avcm0n button,
    [data-testid="stSidebar"] [kind="secondary"],
    [data-testid="stSidebar"] .css-1avcm0n [data-testid="expanderToggle"] {
        display: none !important;
    }
    
    /* Force navigation items to be visible */
    [data-testid="stSidebar"] .css-1avcm0n > div,
    [data-testid="stSidebar"] .nav-item {
        display: block !important;
        opacity: 1 !important;
        visibility: visible !important;
    }
    
    /* Ensure sidebar content scrolls properly */
    [data-testid="stSidebar"] > div {
        overflow-y: auto !important;
        max-height: 100vh !important;
    }
</style>
""", unsafe_allow_html=True)

# Main page content
current_dir = Path(__file__).parent

# Add logo to sidebar
with st.sidebar:
    if (current_dir / "shared" / "logo.png").exists():
        st.image(str(current_dir / "shared" / "logo.png"), width=200)
    st.markdown("---")

# Main content with logo at top
if (current_dir / "shared" / "logo.png").exists():
    st.image(str(current_dir / "shared" / "logo.png"), width=300)

st.title("Twiga Tools")
st.markdown("*Conservation Technology Platform*")
st.markdown("---")

st.markdown("""

This integrated platform provides essential tools for giraffe conservation research, monitoring, and data management.

### 📊 Available tools

Navigate using the sidebar to access:

- **Our impact** - quick look at our conservation success
- **GPS unit check** - monitor GPS tracking device performance over 7 days
- **Survey dashboard (NANW)** - monitor Northwest Namibia giraffe population
- **Survey dashboard (ZAF)** - monitor South Africa giraffe survey encounters
- **Survey dashboard (EHGR)** - monitor Etosha Heights giraffe encounters and patrol data
- **Survey data upload** - process and upload survey images direct to Google Cloud
- **Camera trap data upload** - process and upload camera trap images direct to Google Cloud
- **Post-tagging dashboard** - monitor giraffe locations during first 7 days after collar deployment
- **GAD** - review, download, or submit giraffe population to the Giraffe Africa Database
- **Translocation dashboard** - monitor and review giraffe translocation events
- **Genetic dashboard** - monitor and review biological sample events
- **Create ID Book** - create and download an ID book using a GiraffeSpotter export

### 🚧 Coming soon
            
- **Life history** - see all events linked with an individual giraffe (sightings, immobilisations, etc)
- **Impact reports**
- **Patrol Download** - download patrol tracks as shapefiles from EarthRanger for GIS analysis
- **Mortality Dashboard** - track and analyze giraffe mortality events with timeline and location mapping
- **ER2WB Converter** - convert EarthRanger giraffe encounter data to GiraffeSpotter bulk import format
- **ER Backup** - comprehensive backup of all EarthRanger data

Please send any other tool/dashboard requests to courtney

### 🚀 Getting started

1. Use the sidebar navigation to select a tool
2. Follow the authentication/log in steps
3. Follow the guided process
4. If you need further help, please contact courtney@giraffeconservation.org             

### 🔒 Security

All tools use secure authentication and encrypted data transmission.
""")

# Footer
st.markdown("---")
st.markdown("© 2025 Giraffe Conservation Foundation.")

# Sidebar footer content
st.sidebar.markdown("---")
st.sidebar.markdown("**Giraffe Conservation Foundation**")
st.sidebar.markdown("[GitHub Repository](https://github.com/Giraffe-Conservation-Foundation/streamlit)")
