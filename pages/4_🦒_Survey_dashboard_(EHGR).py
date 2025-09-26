# -*- coding: utf-8 -*-
"""
EHGR Dashboard Page Launcher
Launches the Namibia giraffe monitoring dashboard
"""

import streamlit as st
import sys
from pathlib import Path
import importlib

def main():
    """Main function to launch EHGR Dashboard"""
    # Add the ehgr_dashboard directory to Python path
    current_dir = Path(__file__).parent.parent
    ehgr_dashboard_dir = current_dir / "ehgr_dashboard"
    
    if ehgr_dashboard_dir not in sys.path:
        sys.path.insert(0, str(ehgr_dashboard_dir))
    
    try:
        # Import and run the EHGR dashboard app
        ehgr_app = importlib.import_module("app")
        ehgr_app.main()
    except ImportError as e:
        st.error(f"❌ Error loading EHGR Dashboard: {str(e)}")
        st.info("Please ensure the ehgr_dashboard module is properly installed.")
    except Exception as e:
        st.error(f"❌ Error running EHGR Dashboard: {str(e)}")

if __name__ == "__main__":
    main()