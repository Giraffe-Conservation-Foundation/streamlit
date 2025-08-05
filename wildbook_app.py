#!/usr/bin/env python3
"""
Wildbook ID Generator - Root Entry Point
This file allows Streamlit Cloud to deploy the Wildbook ID Generator
from the repository root while keeping the organized structure.
"""

import sys
import os
from pathlib import Path

# Add the wildbook_id_generator directory to Python path
current_dir = Path(__file__).parent
wildbook_dir = current_dir / "wildbook_id_generator"
sys.path.insert(0, str(wildbook_dir))

# Import and run the main app
if __name__ == "__main__":
    # Change working directory to the app directory
    os.chdir(wildbook_dir)
    
    # Import the main app module
    try:
        exec(open("app.py").read())
    except FileNotFoundError:
        import streamlit as st
        st.error("❌ Wildbook ID Generator app not found!")
        st.info("Please ensure the wildbook_id_generator/app.py file exists.")
