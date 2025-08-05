#!/usr/bin/env python3
"""
Image Management System - Root Entry Point
This file allows Streamlit Cloud to deploy the Image Management System
from the repository root while keeping the organized structure.
"""

import sys
import os
from pathlib import Path

# Add the image_management directory to Python path
current_dir = Path(__file__).parent
image_dir = current_dir / "image_management"
sys.path.insert(0, str(image_dir))

# Import and run the main app
if __name__ == "__main__":
    # Change working directory to the app directory
    os.chdir(image_dir)
    
    # Import the main app module
    try:
        exec(open("app.py").read())
    except FileNotFoundError:
        import streamlit as st
        st.error("❌ Image Management System app not found!")
        st.info("Please ensure the image_management/app.py file exists.")
