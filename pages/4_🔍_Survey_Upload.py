"""
🔍 Survey Upload
Process and upload giraffe survey images to Google Cloud storage
"""

import streamlit as st
import sys
import os
from pathlib import Path

# Add the image_management directory to Python path
current_dir = Path(__file__).parent.parent
image_dir = current_dir / "image_management"
sys.path.insert(0, str(image_dir))

st.title("🔍 Survey Upload")
st.markdown("*Process and upload giraffe survey images to Google Cloud storage*")

# Survey type selector
st.subheader("📋 Survey Configuration")
survey_type = st.selectbox(
    "Select Survey Type:",
    ["survey_vehicle", "survey_aerial"],
    help="Choose whether this is a vehicle-based or aerial survey"
)

st.success(f"✅ Selected: **{survey_type.replace('_', ' ').title()}**")
st.info(f"Images will be uploaded to: `country_site/survey/{survey_type}/yyyymm/`")

st.info("""
💡 **Survey Process:**
1. Select survey type: **Vehicle** or **Aerial**
2. Select country and site from your bucket access
3. Enter researcher initials for tracking
4. Images automatically organized by month
5. Images renamed: `country_site_initials_yyyymmdd_original`

**Folder Structure Examples:**
- Vehicle survey: `namibia_etosha/survey/survey_vehicle/202508/`
- Aerial survey: `kenya_samburu/survey/survey_aerial/202508/`

**File Examples:**
- `namibia_etosha_CM_20250805_IMG001.jpg`
- `kenya_samburu_JD_20250805_DSC123.jpg`
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
        
        # Add survey mode flag and type to the app
        survey_mode_code = f"SURVEY_MODE = True\nSURVEY_TYPE = '{survey_type}'\n" + cleaned_code
        exec(survey_mode_code)
        
    finally:
        # Always restore original directory
        os.chdir(original_dir)
else:
    st.error("❌ Survey Upload tool not found!")
    st.info("Please ensure the image_management/app.py file exists.")
