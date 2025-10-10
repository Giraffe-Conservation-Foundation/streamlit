"""
ER2WB: EarthRanger to GiraffeSpotter Formatting Tool
Navigation page for Streamlit multipage app
"""

import sys
import os
from pathlib import Path
import streamlit as st


# Add shared utilities for logo
current_dir = Path(__file__).parent.parent
sys.path.append(str(current_dir))
from shared.utils import add_sidebar_logo

# Add logo to sidebar at the top
add_sidebar_logo()

# Add the er2wb_dashboard directory to Python path
current_dir = Path(__file__).parent.parent
dashboard_path = current_dir / "er2wb_dashboard"

if str(dashboard_path) not in sys.path:
    sys.path.insert(0, str(dashboard_path))

# Import and run the main application
try:
    # Import the main function from the app module
    import importlib.util
    spec = importlib.util.spec_from_file_location("er2wb_app", dashboard_path / "app.py")
    er2wb_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(er2wb_module)
    
    # Run the main function
    er2wb_module.main()
    
except Exception as e:
    st.error(f"Failed to load ER2WB module: {e}")
    st.info("""
    **ER2WB Module Requirements:**
    
    Please ensure all required packages are installed:
    
    ```bash
    pip install ecoscope pillow geopy pytz openpyxl
    ```
    
    **About ER2WB:**
    
    The ER2WB (EarthRanger to WildBook) converter helps you:
    - Convert giraffe encounter data from EarthRanger to GiraffeSpotter format
    - Process and rename survey images with standardized filenames
    - Apply coordinate reprojection for Zambia sites using GPS directions
    - Generate bulk import packages for GiraffeSpotter
    
    **Features:**
    - Multi-country support (CMR, KEN, NAM, NANW, TZA, UGA, ZAF, ZMB, RWA)
    - Automated timezone conversions
    - EXIF data extraction from images
    - Coordinate reprojection using manual or GPS directions
    - Excel output compatible with GiraffeSpotter bulk import
    
    If you continue to have issues, please contact: courtney@giraffeconservation.org
    """)