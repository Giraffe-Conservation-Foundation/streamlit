import streamlit as st
import sys
import os
from pathlib import Path

# Add project directories to Python path
current_dir = Path(__file__).parent
sys.path.append(str(current_dir / "wildbook_id_generator"))
sys.path.append(str(current_dir / "nanw_dashboard"))
sys.path.append(str(current_dir / "image_management"))
sys.path.append(str(current_dir / "shared"))

st.set_page_config(
    page_title="Twiga Tools - GCF Conservation Platform",
    page_icon="🦒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        color: #D2691E;
        text-align: center;
        margin-bottom: 2rem;
    }
    .tool-card {
        padding: 1rem;
        border-radius: 10px;
        border: 1px solid #e0e0e0;
        margin: 1rem 0;
        background-color: #f9f9f9;
    }
    .sidebar .sidebar-content {
        background-color: #f0f8e8;
    }
    .metric-container {
        background-color: white;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# Sidebar for tool selection
st.sidebar.image(str(current_dir / "shared" / "logo.png") if (current_dir / "shared" / "logo.png").exists() else None, width=200)
# st.sidebar.markdown("# Twiga Tools")
# st.sidebar.markdown("*Conservation Technology Platform*")
# st.sidebar.markdown("---")

tool_choice = st.sidebar.selectbox(
    "🛠️ Select a Tool:",
    [
        "🏠 Home",
        "📖 Create an ID book", 
        "📊 NANW Event Dashboard",
        "� Upload camera trap images",
        "🔍 Upload survey images",
        "🌍 EarthRanger Integration"
    ]
)

st.sidebar.markdown("---")


# Main content area
if tool_choice == "🏠 Home":
    # Header with logo and title
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<h1 class="main-header">Twiga Tools</h1>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Welcome message
    st.markdown("""
    ## Welcome to Twiga Tools
    
    This integrated platform provides essential tools for giraffe conservation research and data management. 
    Select a tool from the sidebar to get started.
    """)
    
    # Tool overview cards
    st.subheader("�️ Available Conservation Tools")
    
    col1, col2 = st.columns(2)
    
    with col1:
        with st.container():
            st.markdown("""
            <div class="tool-card">
                <h3>📖 Create an ID book</h3>
                <p><strong>Status:</strong> ✅ Production Ready</p>
                <p>Generate unique identifiers for individual giraffes in the Wildbook database. Features include ID validation, batch processing, and export capabilities for research teams.</p>
                <ul>
                    <li>Unique ID generation</li>
                    <li>Batch processing</li>
                    <li>Data validation</li>
                    <li>Export functionality</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
        
        with st.container():
            st.markdown("""
            <div class="tool-card">
                <h3>� Upload camera trap images</h3>
                <p><strong>Status:</strong> ✅ Production Ready</p>
                <p>Upload camera trap images with automated naming and organization. Images are renamed as country_site_station_camera_yyyymmdd_originalname and organized by camera type, date, station, and camera subfolders.</p>
                <ul>
                    <li>Camera trap specific naming</li>
                    <li>Station and camera metadata</li>
                    <li>Fence/grid/water organization</li>
                    <li>Station/camera subfolder structure</li>
                    <li>Date-based folder organization</li>
                    <li>No year/month/initials selection needed</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
    
    with col2:
        with st.container():
            st.markdown("""
            <div class="tool-card">
                <h3>📊 NANW Event Dashboard</h3>
                <p><strong>Status:</strong> ✅ Production Ready</p>
                <p>Event tracking and subject history visualization for Northern Africa/Namibia West conservation areas. Monitor giraffe movements and conservation activities.</p>
                <ul>
                    <li>Real-time event tracking</li>
                    <li>Subject history visualization</li>
                    <li>Interactive dashboards</li>
                    <li>Data export tools</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
        
        with st.container():
            st.markdown("""
            <div class="tool-card">
                <h3>🔍 Upload survey images</h3>
                <p><strong>Status:</strong> ✅ Production Ready</p>
                <p>Upload survey images with standardized naming and organization. Choose between vehicle or aerial surveys. Images renamed as country_site_initials_yyyymmdd_original and stored in country_site/survey/survey_[type]/yyyymm/.</p>
                <ul>
                    <li>Survey type selection (vehicle/aerial)</li>
                    <li>Survey specific naming</li>
                    <li>Researcher initial tracking</li>
                    <li>Monthly folder organization</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
        
        with st.container():
            st.markdown("""
            <div class="tool-card">
                <h3>🌍 EarthRanger Integration</h3>
                <p><strong>Status:</strong> 🚧 In Development</p>
                <p>Integration with EarthRanger conservation platform for comprehensive wildlife tracking and conservation area monitoring.</p>
                <ul>
                    <li>Wildlife tracking integration</li>
                    <li>Conservation area monitoring</li>
                    <li>Alert management</li>
                    <li>Real-time data visualization</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
    
    # Statistics dashboard
    st.markdown("---")
    st.subheader("� Platform Statistics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown('<div class="metric-container">', unsafe_allow_html=True)
        st.metric("Active Tools", "4", "All operational")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="metric-container">', unsafe_allow_html=True)
        st.metric("In Development", "1", "EarthRanger")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        st.markdown('<div class="metric-container">', unsafe_allow_html=True)
        st.metric("Data Security", "100%", "Fully secure")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col4:
        st.markdown('<div class="metric-container">', unsafe_allow_html=True)
        st.metric("Platform Status", "Online", "All systems operational")
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Quick start guide
    st.markdown("---")
    st.subheader("🚀 Quick Start Guide")
    
    with st.expander("🔧 Getting Started"):
        st.markdown("""
        ### How to use Twiga Tools:
        
        1. **Select a Tool**: Use the sidebar to choose the conservation tool you need
        2. **Authentication**: Some tools require authentication (Google Cloud, EarthRanger)
        3. **Follow Instructions**: Each tool has step-by-step guidance
        4. **Export Data**: Most tools support data export for further analysis
        
        ### Need Help?
        - Check individual tool documentation
        - Contact Courtney
        - Report issues via the GitHub repository
        """)
    
    with st.expander("🔒 Security Information"):
        st.markdown("""
        ### Security Features:
        - ✅ Secure authentication for all platforms
        - ✅ Environment variable configuration
        - ✅ No hardcoded credentials
        - ✅ Encrypted data transmission
        
        ### Best Practices:
        - Never share your login credentials
        - Use strong, unique passwords
        - Report any suspicious activity
        - Keep your access tokens secure
        """)

elif tool_choice == "📖 Create an ID book":
    st.title("📖 Create an ID book")
    
    try:
        # Import and run the wildbook app
        wildbook_path = current_dir / "wildbook_id_generator"
        if wildbook_path.exists():
            # Store original working directory
            original_dir = os.getcwd()
            
            try:
                sys.path.insert(0, str(wildbook_path))
                
                # Load environment variables if available
                try:
                    from dotenv import load_dotenv
                    load_dotenv()
                except ImportError:
                    pass  # dotenv not required for this tool
                
                # Change to the app directory
                os.chdir(wildbook_path)
                
                # Execute the wildbook app with proper encoding
                app_file = wildbook_path / "app.py"
                if app_file.exists():
                    # Read and execute the app code
                    with open(app_file, "r", encoding="utf-8") as f:
                        app_code = f.read()
                        
                    # Remove any remaining set_page_config calls from the code
                    import re
                    # Use regex to remove set_page_config blocks more reliably
                    cleaned_code = re.sub(
                        r'st\.set_page_config\s*\([^)]*\)',
                        '',
                        app_code,
                        flags=re.MULTILINE | re.DOTALL
                    )
                    exec(cleaned_code)
                else:
                    st.error("❌ Wildbook app.py not found!")
            finally:
                # Always restore original directory
                os.chdir(original_dir)
        else:
            st.error("❌ Create an ID book not found!")
            st.info("Please ensure the wildbook_id_generator/app.py file exists.")
    except Exception as e:
        st.error(f"❌ Error loading Create an ID book: {e}")
        st.info("Please check that all required dependencies are installed.")

elif tool_choice == "📊 NANW Event Dashboard":
    st.title("📊 NANW Event Dashboard")
    st.markdown("*Northern Africa/Namibia West Conservation Monitoring*")
    
    try:
        # Import the NANW dashboard
        nanw_path = current_dir / "nanw_dashboard"
        if nanw_path.exists():
            # Store original working directory
            original_dir = os.getcwd()
            
            try:
                sys.path.insert(0, str(nanw_path))
                
                # Load environment variables if available
                try:
                    from dotenv import load_dotenv
                    load_dotenv()
                except ImportError:
                    st.warning("⚠️ python-dotenv not installed. Environment variables from .env file won't be loaded.")
                    st.info("Install with: `pip install python-dotenv`")
                
                # Change to the app directory  
                os.chdir(nanw_path)
                
                # Execute the NANW dashboard app with proper encoding
                app_file = nanw_path / "app.py"
                if app_file.exists():
                    with open(app_file, "r", encoding="utf-8") as f:
                        app_code = f.read()
                        
                    # Remove any set_page_config calls
                    import re
                    # Use regex to remove set_page_config blocks more reliably
                    cleaned_code = re.sub(
                        r'st\.set_page_config\s*\([^)]*\)',
                        '',
                        app_code,
                        flags=re.MULTILINE | re.DOTALL
                    )
                    exec(cleaned_code)
                else:
                    st.error("❌ NANW app.py not found!")
            finally:
                # Always restore original directory
                os.chdir(original_dir)
        else:
            st.error("❌ NANW Dashboard not found!")
            st.info("Please ensure the nanw_dashboard/app.py file exists.")
    except Exception as e:
        st.error(f"❌ Error loading NANW Dashboard: {e}")
        if "dotenv" in str(e):
            st.info("💡 **Solution**: Install python-dotenv with: `pip install python-dotenv`")
        else:
            st.info("Please check that all required dependencies are installed and EarthRanger credentials are configured.")

elif tool_choice == "� Upload camera trap images":
    st.title("� Upload camera trap images")
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
    
    try:
        # Import the image management system
        image_path = current_dir / "image_management"
        if image_path.exists():
            # Store original working directory
            original_dir = os.getcwd()
            
            try:
                sys.path.insert(0, str(image_path))
                
                # Load environment variables if available
                try:
                    from dotenv import load_dotenv
                    load_dotenv()
                except ImportError:
                    st.warning("⚠️ python-dotenv not installed. Environment variables from .env file won't be loaded.")
                    st.info("Install with: `pip install python-dotenv`")
                
                # Change to the app directory
                os.chdir(image_path)
                
                # Execute the image management app with proper encoding
                app_file = image_path / "app.py"
                if app_file.exists():
                    with open(app_file, "r", encoding="utf-8") as f:
                        app_code = f.read()
                        
                    # Remove any set_page_config calls
                    import re
                    # Use regex to remove set_page_config blocks more reliably
                    cleaned_code = re.sub(
                        r'st\.set_page_config\s*\([^)]*\)',
                        '',
                        app_code,
                        flags=re.MULTILINE | re.DOTALL
                    )
                    
                    # Add camera trap mode flag and type to the app
                    camera_mode_code = f"CAMERA_TRAP_MODE = True\nCAMERA_TYPE = '{camera_type}'\n" + cleaned_code
                    exec(camera_mode_code)
                else:
                    st.error("❌ Upload camera trap images app.py not found!")
            finally:
                # Always restore original directory
                os.chdir(original_dir)
        else:
            st.error("❌ Upload camera trap images tool not found!")
            st.info("Please ensure the image_management/app.py file exists.")
    except Exception as e:
        st.error(f"❌ Error loading Upload camera trap images: {e}")
        if "dotenv" in str(e):
            st.info("💡 **Solution**: Install python-dotenv with: `pip install python-dotenv`")
        else:
            st.info("Please check that Google Cloud credentials are properly configured.")

elif tool_choice == "🔍 Upload survey images":
    st.title("🔍 Upload survey images")
    st.markdown("*Process and upload giraffe survey images to Google Cloud storage*")
    
    # Survey type selector
    st.subheader("📋 Survey Configuration")
    survey_type = st.selectbox(
        "Select Survey Type:",
        ["survey_vehicle", "survey_aerial"],
        help="Choose whether this is a vehicle-based or aerial survey"
    )
    
    try:
        # Import the image management system (same backend, different UI)
        image_path = current_dir / "image_management"
        if image_path.exists():
            # Store original working directory
            original_dir = os.getcwd()
            
            try:
                sys.path.insert(0, str(image_path))
                
                # Load environment variables if available
                try:
                    from dotenv import load_dotenv
                    load_dotenv()
                except ImportError:
                    st.warning("⚠️ python-dotenv not installed. Environment variables from .env file won't be loaded.")
                    st.info("Install with: `pip install python-dotenv`")
                
                # Change to the app directory
                os.chdir(image_path)
                
                # Execute the image management app with proper encoding
                app_file = image_path / "app.py"
                if app_file.exists():
                    with open(app_file, "r", encoding="utf-8") as f:
                        app_code = f.read()
                        
                    # Remove any set_page_config calls
                    import re
                    # Use regex to remove set_page_config blocks more reliably
                    cleaned_code = re.sub(
                        r'st\.set_page_config\s*\([^)]*\)',
                        '',
                        app_code,
                        flags=re.MULTILINE | re.DOTALL
                    )
                    
                    # Add survey mode flag and type to the app
                    survey_mode_code = f"SURVEY_MODE = True\nSURVEY_TYPE = '{survey_type}'\n" + cleaned_code
                    exec(survey_mode_code)
                else:
                    st.error("❌ Upload survey images app.py not found!")
            finally:
                # Always restore original directory
                os.chdir(original_dir)
        else:
            st.error("❌ Upload survey images tool not found!")
            st.info("Please ensure the image_management/app.py file exists.")
    except Exception as e:
        st.error(f"❌ Error loading Upload survey images: {e}")
        if "dotenv" in str(e):
            st.info("💡 **Solution**: Install python-dotenv with: `pip install python-dotenv`")
        else:
            st.info("Please check that Google Cloud credentials are properly configured.")

elif tool_choice == "🌍 EarthRanger Integration":
    st.title("🌍 EarthRanger Integration")
    #st.markdown("*Wildlife Tracking & Conservation Platform Integration*")
    
    st.info("🚧 This tool is currently in development.")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("""
        ### 🎯 Planned Features
        
        **Giraffe life history**
        - all events (sightings, snares, immobilisations)
        - home range calculation
        - habitat use visualization
        
        **survey monitoring**
        - patrol route visualization
        
        **Source (unit) checks**
        - performance before deployment
                    
        """)
    
   
    
    st.markdown("---")
    st.markdown("### 📞 Contact Information")
    st.markdown("For questions about EarthRanger integration or to express interest in beta testing, please contact the GCF development team.")

# Footer
#st.sidebar.markdown("---")
#st.sidebar.markdown("### 📊 System Info")
#st.sidebar.success("🟢 All systems operational")
st.sidebar.markdown("---")
st.sidebar.markdown("Giraffe Conservation Foundation")
# st.sidebar.markdown("*Twiga Tools tech platform*")
st.sidebar.markdown("[GitHub Repository](https://github.com/Giraffe-Conservation-Foundation/streamlit)")
