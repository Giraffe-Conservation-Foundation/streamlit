# -*- coding: utf-8 -*-
"""
ZAF Dashboard Page Launcher
Launches the South Africa giraffe monitoring dashboard
"""

import streamlit as st
import sys
from pathlib import Path
import importlib

# Add shared utilities for logo
current_dir = Path(__file__).parent.parent
sys.path.append(str(current_dir))
from shared.utils import add_sidebar_logo

# Add logo to sidebar at the top
add_sidebar_logo()

def main():
    """Main function to launch ZAF Dashboard"""
    # Add the zaf_dashboard directory to Python path
    zaf_dashboard_dir = current_dir / "zaf_dashboard"
    
    if zaf_dashboard_dir not in sys.path:
        sys.path.insert(0, str(zaf_dashboard_dir))
    
    try:
        # Import and run the ZAF dashboard app
        zaf_app = importlib.import_module("app")
        zaf_app.main()
    except ImportError as e:
        st.error(f"❌ Error loading ZAF Dashboard: {str(e)}")
        st.info("Please ensure the zaf_dashboard module is properly installed.")
    except Exception as e:
        st.error(f"❌ Error running ZAF Dashboard: {str(e)}")

if __name__ == "__main__":
    main()