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

# Main page content
current_dir = Path(__file__).parent

# Sidebar content
st.sidebar.markdown("**Giraffe Conservation Foundation**")
st.sidebar.markdown("[GitHub Repository](https://github.com/Giraffe-Conservation-Foundation/streamlit)")
st.sidebar.markdown("---")

# Quick access to dashboards
st.sidebar.markdown("### 🚀 Quick Access")
st.sidebar.markdown("- [🧬 Genetic Dashboard](8_🧬_Genetic_Dashboard)")
st.sidebar.markdown("- [🚁 Translocation Dashboard](7_🚁_Translocation_Dashboard)")
st.sidebar.markdown("- [📊 NANW Dashboard](2_📊_NANW_Dashboard)")
st.sidebar.markdown("---")

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

- **Create ID Book** - generate an ID book using GiraffeSpotter (Wildbook) data
- **NANW Dashboard** - monitor Northwest Namibia giraffe population  
- **Camera Trap Upload** - process and upload camera trap images to Google Cloud
- **Survey Upload** - process and upload survey images to Google Cloud
- **Source Dashboard** - monitor tracking device sources and location data
- **Tagging Dashboard** - monitor newly tagged giraffes by month and country
- **Translocation Dashboard** - monitor and analyze giraffe translocation events
- **Genetic Dashboard** - monitor and analyze biological sample events

### 🚧 Coming soon
            
- **Life history** - see all events linked with a giraffe (sightings, immobilisations, etc)
- **Impact reports**
- Please send any other tool/dashboard requests to courtney

### 🚀 Getting started

1. Use the sidebar navigation to select a tool
2. Follow the authentication/log in steps
3. Upload your data and follow the guided process
4. If you need further help, please contact courtney@giraffeconservation.org             

### 🔒 Security

All tools use secure authentication and encrypted data transmission.
""")

# Footer
st.markdown("---")
st.markdown("© 2025 Giraffe Conservation Foundation.")
