"""
📷 Camera Trap Upload
Camera Trap Image Processing & Cloud Storage
"""

import streamlit as st
import sys
import os
from pathlib import Path

# Add the image_management directory to Python path
current_dir = Path(__file__).parent.parent
image_dir = current_dir / "image_management"
sys.path.insert(0, str(image_dir))

st.title("📷 Camera Trap Upload")
st.markdown("*Camera Trap Image Processing & Cloud Storage*")
st.markdown("**Naming Format:** `country_site_station_camera_yyyymmdd_originalname`")
st.markdown("**Storage Path:** `country_site/camera_trap/camera_[fence|grid|water]/yyyymm/station/camera/`")

# Camera trap type selector
st.subheader("📋 Camera Trap Configuration")
camera_type = st.selectbox(
    "Select Camera Trap Type:",
    ["camera_fence", "camera_grid", "camera_water"],
    help="Choose the type of camera trap deployment"
)

st.success(f"✅ Selected: **{camera_type.replace('_', ' ').title()}**")
st.info(f"Images will be uploaded to: `country_site/camera_trap/{camera_type}/yyyymm/station/camera/`")

st.info("""
💡 **Camera Trap Process:**
1. Select camera trap type: **Fence**, **Grid**, or **Water**
2. Select country and site from your bucket access
3. Enter **Station ID** and **Camera ID** (no year/month/initials needed)
4. Images automatically organized by station and camera subfolders
5. Images renamed: `country_site_station_camera_yyyymmdd_original`

**Folder Structure Examples:**
- Fence camera: `namibia_etosha/camera_trap/camera_fence/202508/ST01/CAM02/`
- Water camera: `kenya_samburu/camera_trap/camera_water/202508/W03/A/`

**File Examples:**
- `namibia_etosha_ST01_CAM02_20250805_IMG001.jpg`
- `kenya_samburu_W03_A_20250805_DSC123.jpg`
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
        
        # Add camera trap mode flag and type to the app
        camera_mode_code = f"CAMERA_TRAP_MODE = True\nCAMERA_TYPE = '{camera_type}'\n" + cleaned_code
        exec(camera_mode_code)
        
    finally:
        # Always restore original directory
        os.chdir(original_dir)
else:
    st.error("❌ Camera Trap Upload tool not found!")
    st.info("Please ensure the image_management/app.py file exists.")
