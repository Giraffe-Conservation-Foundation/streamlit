"""
Unit Performance Report Page
Generate the quarterly GPS unit performance report from live EarthRanger data
"""

import streamlit as st
import sys
from pathlib import Path
import importlib.util

# Add shared utilities for logo
current_dir = Path(__file__).parent.parent
sys.path.append(str(current_dir))
from shared.utils import add_sidebar_logo

# Add logo to sidebar at the top
add_sidebar_logo()

# Add the unit_performance_dashboard directory to Python path
unit_perf_dir = current_dir / "unit_performance_dashboard"
app_file = unit_perf_dir / "app.py"

try:
    if not app_file.exists():
        st.error(f"Unit Performance Report app.py not found at: {app_file}")
        st.info("Expected file structure: unit_performance_dashboard/app.py")
        st.stop()

    spec = importlib.util.spec_from_file_location("unit_performance_app", app_file)
    if spec is None:
        st.error(f"Could not create module spec for: {app_file}")
        st.stop()

    unit_performance_app = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        st.error(f"Could not get loader for: {app_file}")
        st.stop()

    spec.loader.exec_module(unit_performance_app)

    if hasattr(unit_performance_app, 'main'):
        main = unit_performance_app.main
    else:
        st.error("Unit Performance Report app.py does not have a 'main' function")
        st.stop()

    main()

except Exception as e:
    st.error(f"Error loading Unit Performance Report: {str(e)}")
    st.info(f"File path: {app_file}")
    st.info(f"File exists: {app_file.exists() if 'app_file' in locals() else 'Unknown'}")
    import traceback
    st.code(traceback.format_exc())
