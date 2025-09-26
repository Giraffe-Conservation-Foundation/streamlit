"""
Unit Check Dashboard Page
Monitor tracking device units - 7-day activity, battery, and location
"""

import streamlit as st
import sys
from pathlib import Path
import importlib.util

# Add the unit_check_dashboard directory to Python path
current_dir = Path(__file__).parent.parent
unit_check_dir = current_dir / "unit_check_dashboard"
app_file = unit_check_dir / "app.py"

# Import the specific app.py file from unit_check_dashboard
try:
    if not app_file.exists():
        st.error(f"Unit Check dashboard app.py not found at: {app_file}")
        st.info("Expected file structure: unit_check_dashboard/app.py")
        st.stop()
    
    spec = importlib.util.spec_from_file_location("unit_check_app", app_file)
    if spec is None:
        st.error(f"Could not create module spec for: {app_file}")
        st.stop()
    
    unit_check_app = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        st.error(f"Could not get loader for: {app_file}")
        st.stop()
    
    spec.loader.exec_module(unit_check_app)

    # Get the main function
    if hasattr(unit_check_app, 'main'):
        main = unit_check_app.main
    else:
        st.error("Unit Check dashboard app.py does not have a 'main' function")
        st.stop()

    # Run the Unit Check dashboard
    main()
    
except Exception as e:
    st.error(f"Error loading Unit Check Dashboard: {str(e)}")
    st.info(f"File path: {app_file}")
    st.info(f"File exists: {app_file.exists() if 'app_file' in locals() else 'Unknown'}")
    import traceback
    st.code(traceback.format_exc())