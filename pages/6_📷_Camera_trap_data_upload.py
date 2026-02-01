"""
📷 Camera Trap Upload
Camera Trap Image Processing & Cloud Storage
"""

import streamlit as st
import sys
import os
from pathlib import Path


# Add shared utilities for logo
current_dir = Path(__file__).parent.parent
sys.path.append(str(current_dir))
from shared.utils import add_sidebar_logo

# Add logo to sidebar at the top
add_sidebar_logo()

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
💡 **Process:**
1. Authenticate your Google Cloud access
2. Select camera trap type: **fence**, **grid**, or **waterhole**
3. Select country and site from your Google Cloud bucket access
4. Enter **Station ID** and **Camera ID**
5. upload a zipped folder (one folder per camera)
6. Images are auto renamed: `country_site_station_camera_yyyymmdd_original`

**Example structure:**
- Original: `DSC001.jpg`
- Renamed: `namibia_etosha_A1_cam01_20240805_DSC001.jpg`
- Path: `gs://country_site/camera_trap/type/station/camera/yyyymm/`

**Supported formats:** `.jpg`, `.jpeg`, `.png`, `.tiff` (inside `.zip` archives)
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
        
        # Set camera trap mode flag before executing
        globals()['CAMERA_TRAP_MODE'] = True
        
        exec(cleaned_code)
        
    finally:
        # Always restore original directory
        os.chdir(original_dir)
else:
    st.error("❌ Camera Trap Upload tool not found!")
    st.info("Please ensure the camera_trap_upload/app.py file exists.")