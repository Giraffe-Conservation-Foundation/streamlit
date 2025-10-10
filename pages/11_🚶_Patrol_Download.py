"""
Patrol Download Page
Download patrol tracks as shapefiles from EarthRanger
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

# Add the patrol_download directory to Python path
current_dir = Path(__file__).parent.parent
patrol_dir = current_dir / "patrol_download"
app_file = patrol_dir / "app.py"

# Import the specific app.py file from patrol_download
spec = importlib.util.spec_from_file_location("patrol_app", app_file)
patrol_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patrol_app)

# Get the main function
main = patrol_app.main

# Run the Patrol Download dashboard
if __name__ == "__main__":
    main()