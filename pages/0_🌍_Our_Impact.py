"""
Our Impact Dashboard Page
Aggregated metrics from multiple dashboards showing overall GCF impact
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

# Add the impact_dashboard directory to Python path
impact_dir = current_dir / "impact_dashboard"
app_file = impact_dir / "app.py"

# Import the specific app.py file from impact_dashboard
spec = importlib.util.spec_from_file_location("impact_app", app_file)
impact_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(impact_app)

# Get the main function
main = impact_app.main

# Run the Impact Dashboard
if __name__ == "__main__":
    main()