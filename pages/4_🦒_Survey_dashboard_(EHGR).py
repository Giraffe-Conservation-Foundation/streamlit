# -*- coding: utf-8 -*-
"""
EHGR Dashboard Page Launcher
Launches the Namibia giraffe monitoring dashboard
"""

import streamlit as st
import sys
from pathlib import Path
# Add shared utilities for logo
current_dir = Path(__file__).parent.parent
sys.path.append(str(current_dir))
from shared.utils import add_sidebar_logo

# Add logo to sidebar at the top
add_sidebar_logo()

def main():
    """Main function to launch EHGR Dashboard"""
    # Add the ehgr_dashboard directory to Python path
    current_dir = Path(__file__).parent.parent
    ehgr_dashboard_dir = current_dir / "ehgr_dashboard"

    try:
        # Import and run the EHGR dashboard app
        # Use spec-based loading to avoid module cache collision with other "app" modules
        import importlib.util
        spec = importlib.util.spec_from_file_location("ehgr_app", ehgr_dashboard_dir / "app.py")
        ehgr_app = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ehgr_app)
        ehgr_app.main()
    except ImportError as e:
        st.error(f"❌ Error loading EHGR Dashboard: {str(e)}")
        st.info("Please ensure the ehgr_dashboard module is properly installed.")
    except Exception as e:
        st.error(f"❌ Error running EHGR Dashboard: {str(e)}")

if __name__ == "__main__":
    main()