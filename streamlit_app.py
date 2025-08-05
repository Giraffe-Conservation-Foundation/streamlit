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
    page_icon="🦒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Main page content
current_dir = Path(__file__).parent

# Sidebar with logo
if (current_dir / "shared" / "logo.png").exists():
    st.sidebar.image(str(current_dir / "shared" / "logo.png"), width=200)

st.sidebar.markdown("---")
st.sidebar.markdown("**Giraffe Conservation Foundation**")
st.sidebar.markdown("[GitHub Repository](https://github.com/Giraffe-Conservation-Foundation/streamlit)")

# Main content
st.title("🦒 Twiga Tools")
st.markdown("*Conservation Technology Platform*")

st.markdown("""
## Welcome to Twiga Tools

This integrated platform provides essential tools for giraffe conservation research and data management.

### 📊 Available Tools

Navigate using the sidebar to access:

- **📖 Create ID Book** - Generate unique identifiers for giraffes
- **📊 NANW Dashboard** - Event tracking and monitoring  
- **📷 Camera Trap Upload** - Process camera trap images
- **🔍 Survey Upload** - Process survey images

### 🚀 Getting Started

1. Use the sidebar navigation to select a tool
2. Follow the authentication steps for each tool
3. Upload your data and follow the guided process

### 🔒 Security

All tools use secure authentication and encrypted data transmission.
""")

# Footer
st.markdown("---")
st.markdown("© 2025 Giraffe Conservation Foundation. All rights reserved.")
