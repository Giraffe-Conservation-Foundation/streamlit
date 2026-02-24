"""
Twiga Dash — GPS Subject Tracking Summary
Page wrapper for the multi-page Twiga Tools app.
"""

import streamlit as st
import sys
import importlib.util
from pathlib import Path

# Add shared utilities for logo
current_dir = Path(__file__).parent.parent
sys.path.append(str(current_dir))
from shared.utils import add_sidebar_logo

# Add logo to sidebar at the top
add_sidebar_logo()

# Load twiga_dash/app.py
app_file = current_dir / "twiga_dash" / "app.py"

try:
    if not app_file.exists():
        st.error(f"Twiga Dash app.py not found at: {app_file}")
        st.info("Expected file structure: twiga_dash/app.py")
        st.stop()

    spec = importlib.util.spec_from_file_location("twiga_dash_app", app_file)
    if spec is None:
        st.error(f"Could not create module spec for: {app_file}")
        st.stop()

    twiga_dash_app = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        st.error(f"Could not get loader for: {app_file}")
        st.stop()

    spec.loader.exec_module(twiga_dash_app)

    if hasattr(twiga_dash_app, "main"):
        twiga_dash_app.main()
    else:
        st.error("twiga_dash/app.py does not have a 'main' function.")
        st.stop()

except Exception as e:
    st.error(f"Error loading Twiga Dash: {e}")
    import traceback
    st.code(traceback.format_exc())
