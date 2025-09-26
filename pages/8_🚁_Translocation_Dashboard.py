"""
Translocation Dashboard Page
Monitor and analyze giraffe translocation events from EarthRanger
"""

import streamlit as st
import sys
from pathlib import Path
import importlib.util

# Add the translocation_dashboard directory to Python path
current_dir = Path(__file__).parent.parent
translocation_dir = current_dir / "translocation_dashboard"
app_file = translocation_dir / "app.py"

# Import the specific app.py file from translocation_dashboard
spec = importlib.util.spec_from_file_location("translocation_app", app_file)
translocation_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(translocation_app)

# Get the main function
main = translocation_app.main

# Run the Translocation dashboard
if __name__ == "__main__":
    main()