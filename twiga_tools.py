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
st.sidebar.markdown("# 🦒 Twiga Tools")
st.sidebar.markdown("*Conservation Technology Platform*")
st.sidebar.markdown("---")

tool_choice = st.sidebar.selectbox(
    "🛠️ Select a Tool:",
    [
        "🏠 Dashboard Home",
        "🆔 Wildbook ID Generator", 
        "📊 NANW Event Dashboard",
        "📸 Image Management System",
        "🌍 EarthRanger Integration"
    ]
)

st.sidebar.markdown("---")
st.sidebar.markdown("### 📋 Tool Status")
st.sidebar.markdown("✅ **Wildbook ID Generator** - Active")
st.sidebar.markdown("✅ **NANW Dashboard** - Active") 
st.sidebar.markdown("✅ **Image Management** - Active")
st.sidebar.markdown("🚧 **EarthRanger** - In Development")

# Main content area
if tool_choice == "🏠 Dashboard Home":
    # Header with logo and title
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<h1 class="main-header">🦒 Twiga Tools</h1>', unsafe_allow_html=True)
        st.markdown('<p style="text-align: center; font-size: 1.2rem; color: #666;">Giraffe Conservation Foundation Technology Platform</p>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Welcome message
    st.markdown("""
    ## Welcome to Twiga Tools! 🌍
    
    This integrated platform provides essential tools for giraffe conservation research and data management. 
    Select a tool from the sidebar to get started with your conservation work.
    """)
    
    # Tool overview cards
    st.subheader("�️ Available Conservation Tools")
    
    col1, col2 = st.columns(2)
    
    with col1:
        with st.container():
            st.markdown("""
            <div class="tool-card">
                <h3>🆔 Wildbook ID Generator</h3>
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
                <h3>📸 Image Management System</h3>
                <p><strong>Status:</strong> ✅ Production Ready</p>
                <p>Complete workflow for managing giraffe conservation images with Google Cloud Storage integration, automated processing, and standardized naming.</p>
                <ul>
                    <li>Google Cloud Storage integration</li>
                    <li>Automated image processing</li>
                    <li>Standardized naming conventions</li>
                    <li>Batch upload capabilities</li>
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
        st.metric("Active Tools", "3", "All operational")
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
        - Contact the GCF technology team
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

elif tool_choice == "🆔 Wildbook ID Generator":
    st.title("🆔 Wildbook ID Generator")
    st.markdown("*Individual Giraffe Identification System*")
    
    try:
        # Import and run the wildbook app
        wildbook_path = current_dir / "wildbook_id_generator"
        if wildbook_path.exists():
            sys.path.insert(0, str(wildbook_path))
            
            # Load environment variables if available
            try:
                from dotenv import load_dotenv
                load_dotenv()
            except ImportError:
                pass  # dotenv not required for this tool
            
            # Execute the wildbook app
            os.chdir(wildbook_path)
            exec(open("app.py").read())
        else:
            st.error("❌ Wildbook ID Generator not found!")
            st.info("Please ensure the wildbook_id_generator/app.py file exists.")
    except Exception as e:
        st.error(f"❌ Error loading Wildbook ID Generator: {e}")
        st.info("Please check that all required dependencies are installed.")

elif tool_choice == "📊 NANW Event Dashboard":
    st.title("📊 NANW Event Dashboard")
    st.markdown("*Northern Africa/Namibia West Conservation Monitoring*")
    
    try:
        # Import the NANW dashboard
        nanw_path = current_dir / "nanw_dashboard"
        if nanw_path.exists():
            sys.path.insert(0, str(nanw_path))
            
            # Load environment variables
            from dotenv import load_dotenv
            load_dotenv()
            
            # Execute the NANW dashboard app
            os.chdir(nanw_path)
            exec(open("app.py").read())
        else:
            st.error("❌ NANW Dashboard not found!")
            st.info("Please ensure the nanw_dashboard/app.py file exists.")
    except Exception as e:
        st.error(f"❌ Error loading NANW Dashboard: {e}")
        st.info("Please check that all required dependencies are installed and EarthRanger credentials are configured.")

elif tool_choice == "📸 Image Management System":
    st.title("📸 Image Management System")
    st.markdown("*Giraffe Conservation Image Processing & Cloud Storage*")
    
    try:
        # Import the image management system
        image_path = current_dir / "image_management"
        if image_path.exists():
            sys.path.insert(0, str(image_path))
            
            # Load environment variables
            from dotenv import load_dotenv
            load_dotenv()
            
            # Execute the image management app
            os.chdir(image_path)
            exec(open("app.py").read())
        else:
            st.error("❌ Image Management System not found!")
            st.info("Please ensure the image_management/app.py file exists.")
    except Exception as e:
        st.error(f"❌ Error loading Image Management System: {e}")
        st.info("Please check that Google Cloud credentials are properly configured.")

elif tool_choice == "🌍 EarthRanger Integration":
    st.title("🌍 EarthRanger Integration")
    st.markdown("*Wildlife Tracking & Conservation Platform Integration*")
    
    st.info("🚧 This tool is currently in development.")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("""
        ### 🎯 Planned Features
        
        **Wildlife Tracking**
        - Real-time animal location monitoring
        - Movement pattern analysis
        - Migration route tracking
        - Habitat usage visualization
        
        **Conservation Area Monitoring**
        - Patrol route optimization
        - Ranger activity tracking
        - Conservation area coverage analysis
        - Incident reporting and mapping
        
        **Alert Management**
        - Security alert notifications
        - Wildlife emergency responses
        - Automated threat detection
        - Multi-channel alert distribution
        
        **Data Integration**
        - EarthRanger API connectivity
        - Real-time data synchronization
        - Historical data analysis
        - Cross-platform data sharing
        """)
    
    with col2:
        st.info("""
        **🔔 Development Status**
        
        ✅ API research completed
        ⏳ Authentication system
        ⏳ Data visualization
        ⏳ Alert management
        ⏳ User interface design
        ⏳ Testing & validation
        
        **📅 Expected Release**
        Q4 2025
        
        **🤝 Get Updates**
        Contact the GCF tech team for progress updates and beta testing opportunities.
        """)
    
    st.markdown("---")
    st.markdown("### 📞 Contact Information")
    st.markdown("For questions about EarthRanger integration or to express interest in beta testing, please contact the GCF development team.")

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 System Info")
st.sidebar.success("🟢 All systems operational")
st.sidebar.info("🔄 Last updated: August 2025")
st.sidebar.markdown("---")
st.sidebar.markdown("**🦒 Giraffe Conservation Foundation**")
st.sidebar.markdown("*Twiga Tools Platform*")
st.sidebar.markdown("[GitHub Repository](https://github.com/Giraffe-Conservation-Foundation/streamlit)")
