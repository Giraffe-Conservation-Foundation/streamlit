"""
Source Dashboard Page
Monitor and analyze EarthRanger tracking device sources
"""

import streamlit as st
import sys
from pathlib import Path
import importlib.util

# Add the source_dashboard directory to Python path
current_dir = Path(__file__).parent.parent
source_dir = current_dir / "source_dashboard"
app_file = source_dir / "app.py"

# Import the specific app.py file from source_dashboard
spec = importlib.util.spec_from_file_location("source_app", app_file)
source_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source_app)

# Get the main function
main = source_app.main

# Run the Source dashboard
if __name__ == "__main__":
    main()
