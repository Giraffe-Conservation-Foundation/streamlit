"""
KEEP Dashboard Page
Embedded ArcGIS Dashboard
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

# Add the keep_dashboard directory to Python path
keep_dir = current_dir / "keep_dashboard"
app_file = keep_dir / "app.py"

# Import the specific app.py file from keep_dashboard
spec = importlib.util.spec_from_file_location("keep_app", app_file)
keep_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(keep_app)

# Get the main function
main = keep_app.main

# Run the KEEP Dashboard
if __name__ == "__main__":
    main()
