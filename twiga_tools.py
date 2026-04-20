"""
Streamlit Multipage App Structure
Entry point using st.navigation() for grouped sidebar sections.
Requires streamlit >= 1.36.0
"""

import streamlit as st
from pathlib import Path

# ── Page config (must be first Streamlit command) ─────────────────────────────
st.set_page_config(
    page_title="Twiga Tools - GCF Conservation Platform",
    layout="wide",
    initial_sidebar_state="expanded",
)

current_dir = Path(__file__).parent

# ── Sidebar header (logo) ─────────────────────────────────────────────────────
with st.sidebar:
    if (current_dir / "shared" / "logo.png").exists():
        st.image(str(current_dir / "shared" / "logo.png"), width=200)
    st.markdown("---")


# ── Welcome / landing page ────────────────────────────────────────────────────
def _welcome_page():
    if (current_dir / "shared" / "logo.png").exists():
        st.image(str(current_dir / "shared" / "logo.png"), width=300)

    st.title("Twiga Tools")
    st.markdown("*Conservation Technology Platform*")
    st.markdown("---")

    st.markdown("""
This integrated platform provides essential tools for giraffe conservation research, monitoring, and data management.

### 📊 Available tools

Use the grouped sidebar to access:

- **Home** — overview dashboards: Our Impact, Twiga Dash, Life History, Publications, Preferred Suppliers
- **Survey dashboards** — country-level survey encounter dashboards (EHGR, NANW, ZAF, ZMB) and Patrol shapefile download
- **Technical** — GPS unit health and deployment tools
- **Data upload** — survey and camera trap image ingestion
- **GiraffeSpotter** — converters and ID book generator for Wildbook
- **GAD** — Giraffe Africa Database, mortality, and genetic sample tracking
- **Translocations** — translocation events and priority assessment
- **Other** — CITES trade data and SECR population analysis

### 🚀 Getting started

1. Pick a tool from the sidebar
2. Follow the authentication/log in steps
3. Follow the guided process
4. Contact courtney@giraffeconservation.org for help or new tool requests

### 🔒 Security

All tools use secure authentication and encrypted data transmission.
""")

    st.markdown("---")
    st.markdown("© 2025 Giraffe Conservation Foundation.")


# ── Page registry ─────────────────────────────────────────────────────────────
pages = {
    "Home": [
        st.Page(_welcome_page, title="Welcome", icon="🦒", default=True, url_path="welcome"),
        st.Page("pages/0_🌍_Our_Impact.py",            title="Our Impact",          icon="🌍"),
        st.Page("pages/17_🦒_Twiga_Dash.py",           title="Twiga Dash",          icon="🦒"),
        st.Page("pages/16_📜_Life_History.py",         title="Life History",        icon="📜"),
        st.Page("pages/15_📚_Publications.py",         title="Publications",        icon="📚"),
        st.Page("pages/2_🔧_Preferred_Suppliers.py",   title="Preferred Suppliers", icon="🔧"),
    ],
    "Survey dashboards": [
        st.Page("pages/4_🦒_Survey_dashboard_(EHGR).py", title="Survey dashboard (EHGR)", icon="🦒"),
        st.Page("pages/2_🦒_Survey_dashboard_(NANW).py", title="Survey dashboard (NANW)", icon="🦒"),
        st.Page("pages/3_🦒_Survey_dashboard_(ZAF).py",  title="Survey dashboard (ZAF)",  icon="🦒"),
        st.Page("pages/20_🦒_Survey_dashboard_ZMB.py",   title="Survey dashboard (ZMB)",  icon="🦒"),
        st.Page("pages/11_🗺️_Patrol_shp_download.py",   title="Patrol shp download",     icon="🗺️"),
    ],
    "Technical": [
        st.Page("pages/1_🔋_GPS_unit_check.py",         title="GPS unit check",        icon="🔋"),
        st.Page("pages/2_🛰️_GPS_Data_Availability.py",  title="GPS Data Availability", icon="🛰️"),
        st.Page("pages/7_📍_Post-Tagging_Dashboard.py", title="Post-Tagging Dashboard", icon="📍"),
    ],
    "Data upload": [
        st.Page("pages/5_🚗_Survey_data_backup.py",      title="Survey data backup",      icon="🚗"),
        st.Page("pages/6_📷_Camera_trap_data_upload.py", title="Camera trap data upload", icon="📷"),
    ],
    "GiraffeSpotter": [
        st.Page("pages/18_🦒_ER2WB_Converter.py",                        title="ER2WB Converter",   icon="🦒"),
        st.Page("pages/19_📋_SMART2WB_Converter.py",                     title="SMART2WB Converter", icon="📋"),
        st.Page("pages/10_📖_Create_an_ID_book_(GiraffeSpotter).py",     title="Create ID Book",    icon="📖"),
    ],
    "GAD": [
        st.Page("pages/7_🦒_GAD.py",                title="GAD",                 icon="🦒"),
        st.Page("pages/13_☠️_Mortality_Dashboard.py", title="Mortality Dashboard", icon="☠️"),
        st.Page("pages/9_🧬_Genetic_Dashboard.py",  title="Genetic dashboard",   icon="🧬"),
    ],
    "Translocations": [
        st.Page("pages/8_🚁_Translocation_Dashboard.py",  title="Translocation Dashboard",  icon="🦒"),
        st.Page("pages/12_🌍_Translocation_Assessment.py", title="Translocation Assessment", icon="🌍"),
    ],
    "Other": [
        st.Page("pages/12_📋_CITES_Trade_Database.py",      title="CITES Trade Database",      icon="📋"),
        st.Page("pages/14_📊_SECR_Population_Analysis.py", title="SECR Population Analysis", icon="📊"),
    ],
}

# ── Run selected page ─────────────────────────────────────────────────────────
pg = st.navigation(pages)
pg.run()

# ── Sidebar footer (renders on every page) ────────────────────────────────────
st.sidebar.markdown("---")
st.sidebar.markdown("**Giraffe Conservation Foundation**")
st.sidebar.markdown("[GitHub Repository](https://github.com/Giraffe-Conservation-Foundation/streamlit)")
