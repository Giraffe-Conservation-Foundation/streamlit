"""
KEEP Dashboard
Embedded ArcGIS Dashboard for KEEP project
"""

import streamlit as st
import sys
from pathlib import Path

# Add shared utilities for logo
current_dir = Path(__file__).parent.parent
sys.path.append(str(current_dir))

try:
    from shared.utils import add_sidebar_logo
except ImportError:
    def add_sidebar_logo():
        pass

# Custom CSS for full-page iframe
st.markdown("""
<style>
    /* Remove padding and margins for full-page display */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 0rem;
        padding-left: 1rem;
        padding-right: 1rem;
        max-width: 100%;
    }
    
    iframe {
        border: none;
    }
</style>
""", unsafe_allow_html=True)

# ======== Authentication Functions ========

def check_password():
    """Returns `True` if the user had the correct password."""
    def password_entered():
        """Checks whether a password entered by the user is correct."""
        try:
            # Try to get password from secrets (same as publications)
            if st.session_state["password"] == st.secrets["passwords"]["publications_password"]:
                st.session_state["password_correct"] = True
                del st.session_state["password"]  # don't store password
            else:
                st.session_state["password_correct"] = False
        except Exception as e:
            # For local development without secrets.toml, use a default password
            if st.session_state["password"] == "admin":
                st.session_state["password_correct"] = True
                del st.session_state["password"]
            else:
                st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # First run, show input for password
        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        st.write("*Please enter password to access the KEEP Dashboard.*")
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

def main():
    """Main application function"""
    
    # Add logo to sidebar
    add_sidebar_logo()
    
    # Check password
    if not check_password():
        return
    
    # Page title
    st.title("🔑 KEEP Dashboard")
    st.markdown("Key Elephant & Environmental Pressures")
    st.markdown("---")
    
    # ArcGIS Dashboard URL
    dashboard_url = "https://giraffecf.maps.arcgis.com/apps/dashboards/572591b7353b4c1db3a4e85d200ed2de"
    
    # Embed the dashboard
    st.components.v1.iframe(
        dashboard_url,
        height=800,
        scrolling=True
    )

if __name__ == "__main__":
    main()
