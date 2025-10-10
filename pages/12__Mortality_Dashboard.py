"""
Mortality Dashboard Page
Track and analyze giraffe mortality events from EarthRanger
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

# Add the mortality_dashboard directory to Python path
current_dir = Path(__file__).parent.parent
mortality_dir = current_dir / "mortality_dashboard"
app_file = mortality_dir / "app.py"

# Import the specific app.py file from mortality_dashboard
spec = importlib.util.spec_from_file_location("mortality_app", app_file)
mortality_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mortality_app)

# Get the main function
main = mortality_app.main

# Run the Mortality dashboard
if __name__ == "__main__":
    main()