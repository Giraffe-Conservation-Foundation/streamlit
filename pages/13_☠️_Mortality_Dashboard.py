"""
Mortality Dashboard Page
Redirects to the mortality_dashboard app.py
"""

import streamlit as st
import sys
from pathlib import Path

# Add the mortality_dashboard directory to the path
dashboard_dir = Path(__file__).parent.parent / "mortality_dashboard"
sys.path.insert(0, str(dashboard_dir))

# Import and run the mortality dashboard
from mortality_dashboard.app import main

if __name__ == "__main__":
    main()
