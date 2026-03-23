"""
GPS Data Availability Page
Quick summary of GPS tracking data available by subject group.
"""

import streamlit as st
import sys
from pathlib import Path
import importlib.util

current_dir = Path(__file__).parent.parent
sys.path.append(str(current_dir))
from shared.utils import add_sidebar_logo

add_sidebar_logo()

dashboard_dir = current_dir / "gps_availability_dashboard"
app_file = dashboard_dir / "app.py"

try:
    if not app_file.exists():
        st.error(f"GPS Availability dashboard not found at: {app_file}")
        st.stop()

    spec = importlib.util.spec_from_file_location("gps_availability_app", app_file)
    if spec is None or spec.loader is None:
        st.error(f"Could not load module from: {app_file}")
        st.stop()

    gps_avail_app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gps_avail_app)

    if not hasattr(gps_avail_app, 'main'):
        st.error("GPS Availability app.py does not have a 'main' function.")
        st.stop()

    gps_avail_app.main()

except Exception as e:
    st.error(f"Error loading GPS Data Availability Dashboard: {e}")
    import traceback
    st.code(traceback.format_exc())
