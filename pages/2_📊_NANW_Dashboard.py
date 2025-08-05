"""
📊 NANW Event Dashboard
Northern Africa/Namibia West Conservation Monitoring
"""

import streamlit as st
import sys
import os
from pathlib import Path

# Add the nanw_dashboard directory to Python path
current_dir = Path(__file__).parent.parent
nanw_dir = current_dir / "nanw_dashboard"
sys.path.insert(0, str(nanw_dir))

st.title("📊 NANW Event Dashboard")
st.markdown("*Northern Africa/Namibia West Conservation Monitoring*")

if nanw_dir.exists() and (nanw_dir / "app.py").exists():
    # Store original working directory
    original_dir = os.getcwd()
    
    try:
        # Change to the app directory
        os.chdir(nanw_dir)
        
        # Load environment variables if available
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            st.warning("⚠️ python-dotenv not installed. Environment variables from .env file won't be loaded.")
        
        # Read and execute the app code
        with open(nanw_dir / "app.py", "r", encoding="utf-8") as f:
            app_code = f.read()
            
        # Remove any set_page_config calls since this is a page
        import re
        cleaned_code = re.sub(
            r'st\.set_page_config\s*\([^)]*\)',
            '',
            app_code,
            flags=re.MULTILINE | re.DOTALL
        )
        
        exec(cleaned_code)
        
    finally:
        # Always restore original directory
        os.chdir(original_dir)
else:
    st.error("❌ NANW Dashboard not found!")
    st.info("Please ensure the nanw_dashboard/app.py file exists.")
