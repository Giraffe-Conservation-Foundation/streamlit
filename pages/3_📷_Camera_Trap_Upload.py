"""
📷 Camera Trap Upload
Camera Trap Image Processing & Cloud Storage
"""

import streamlit as st
import sys
import os
from pathlib import Path

# Add the camera_trap_upload directory to Python path
current_dir = Path(__file__).parent.parent
image_dir = current_dir / "camera_trap_upload"
shared_dir = current_dir / "shared"
sys.path.insert(0, str(image_dir))
sys.path.insert(0, str(shared_dir))

st.title("📷 Camera Trap Upload")
st.markdown("*Camera trap image processing and cloud storage*")

# Only show the process overview if user hasn't authenticated yet
# This ensures it's only visible on the landing page (Step 1)
if 'authenticated' not in st.session_state or not st.session_state.authenticated:
    st.markdown("""
💡 **Camera Trap Process:**
1. Authenticate your Google Cloud access
2. Select camera trap type: **Fence**, **Grid**, or **Water**
3. Select country and site from your Google Cloud bucket access
4. Enter **Station ID** and **Camera ID** (one folder upload per camera)
5. Images are auto renamed: `country_site_station_camera_yyyymmdd_original`
6. Images are auto sorted into correct Google Cloud bucket
""")

if image_dir.exists() and (image_dir / "app.py").exists():
    # Store original working directory
    original_dir = os.getcwd()
    
    try:
        # Change to the app directory
        os.chdir(image_dir)
        
        # Load environment variables if available
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            st.warning("⚠️ python-dotenv not installed. Environment variables from .env file won't be loaded.")
        
        # Read and execute the app code
        with open(image_dir / "app.py", "r", encoding="utf-8") as f:
            app_code = f.read()
            
        # Remove any set_page_config calls since this is a page
        import re
        cleaned_code = re.sub(
            r'st\.set_page_config\s*\([^)]*\)',
            '',
            app_code,
            flags=re.MULTILINE | re.DOTALL
        )
        
        # Add camera trap mode flag to the app (type will be selected within the app)
        camera_mode_code = f"CAMERA_TRAP_MODE = True\n" + cleaned_code
        exec(camera_mode_code)
        
    finally:
        # Always restore original directory
        os.chdir(original_dir)
else:
    st.error("❌ Camera Trap Upload tool not found!")
    st.info("Please ensure the camera_trap_upload/app.py file exists.")
