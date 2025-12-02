"""
Site Assessment Dashboard Page
Evaluate potential giraffe translocation sites using satellite imagery
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

# Add the site_assessment directory to Python path
assessment_dir = current_dir / "site_assessment"
app_file = assessment_dir / "app.py"

# Import the specific app.py file from site_assessment
spec = importlib.util.spec_from_file_location("site_assessment_app", app_file)
assessment_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assessment_app)

# Get the main function
main = assessment_app.main

# Run the Site Assessment Dashboard
if __name__ == "__main__":
    main()
