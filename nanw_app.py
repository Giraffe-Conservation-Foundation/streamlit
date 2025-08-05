#!/usr/bin/env python3
"""
NANW Dashboard - Root Entry Point
This file allows Streamlit Cloud to deploy the NANW Dashboard
from the repository root while keeping the organized structure.
"""

import sys
import os
from pathlib import Path

# Add the nanw_dashboard directory to Python path
current_dir = Path(__file__).parent
nanw_dir = current_dir / "nanw_dashboard"
sys.path.insert(0, str(nanw_dir))

# Import and run the main app
if __name__ == "__main__":
    # Change working directory to the app directory
    os.chdir(nanw_dir)
    
    # Import the main app module
    try:
        exec(open("app.py").read())
    except FileNotFoundError:
        import streamlit as st
        st.error("❌ NANW Dashboard app not found!")
        st.info("Please ensure the nanw_dashboard/app.py file exists.")
