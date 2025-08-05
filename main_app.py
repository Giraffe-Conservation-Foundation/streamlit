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
    page_title="GCF Streamlit Applications",
    page_icon="🦒",
    layout="wide"
)

# Sidebar for app selection
st.sidebar.title("🦒 GCF Applications")
st.sidebar.markdown("---")

app_choice = st.sidebar.selectbox(
    "Choose an Application:",
    [
        "🏠 Home",
        "🆔 Wildbook ID Generator", 
        "📊 NANW Dashboard",
        "📸 Image Management",
        "🌍 EarthRanger Dashboard"
    ]
)

# Main content area
if app_choice == "🏠 Home":
    st.title("🦒 Giraffe Conservation Foundation")
    st.header("Streamlit Applications Dashboard")
    
    st.markdown("""
    Welcome to the GCF Streamlit Applications suite! Choose an application from the sidebar to get started.
    
    ## 📱 Available Applications
    
    ### 🆔 Wildbook ID Generator
    Generate unique IDs for giraffe individuals in the Wildbook database with validation and batch processing capabilities.
    
    ### 📊 NANW Dashboard  
    Event tracking and subject history visualization for Northern Africa/Namibia West conservation areas.
    
    ### 📸 Image Management
    Complete workflow for managing giraffe conservation images with Google Cloud Storage integration.
    
    ### 🌍 EarthRanger Dashboard
    Integration with EarthRanger conservation platform for wildlife tracking (coming soon).
    
    ---
    
    **🔒 Security Note**: All applications use secure authentication and environment variables for sensitive data.
    """)
    
    # Show project status
    st.subheader("📋 Project Status")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Wildbook ID Generator", "✅ Active", "Production Ready")
    with col2:
        st.metric("NANW Dashboard", "✅ Active", "Production Ready")
    with col3:
        st.metric("Image Management", "✅ Active", "Production Ready")
    with col4:
        st.metric("EarthRanger Dashboard", "🚧 Development", "Coming Soon")

elif app_choice == "🆔 Wildbook ID Generator":
    st.title("🆔 Wildbook ID Generator")
    
    # Import and run the wildbook app
    try:
        # Add the wildbook directory to path and import
        wildbook_path = current_dir / "wildbook_id_generator"
        if wildbook_path.exists():
            sys.path.insert(0, str(wildbook_path))
            
            # You'll need to modify the wildbook app to be importable
            st.info("🔧 Loading Wildbook ID Generator...")
            st.markdown("**Note**: This would load the Wildbook ID Generator app here.")
            st.markdown("The app needs to be refactored to work as an imported module.")
        else:
            st.error("Wildbook ID Generator not found!")
    except Exception as e:
        st.error(f"Error loading Wildbook ID Generator: {e}")

elif app_choice == "📊 NANW Dashboard":
    st.title("📊 NANW Dashboard")
    
    try:
        nanw_path = current_dir / "nanw_dashboard"
        if nanw_path.exists():
            sys.path.insert(0, str(nanw_path))
            st.info("🔧 Loading NANW Dashboard...")
            st.markdown("**Note**: This would load the NANW Dashboard app here.")
            st.markdown("The app needs to be refactored to work as an imported module.")
        else:
            st.error("NANW Dashboard not found!")
    except Exception as e:
        st.error(f"Error loading NANW Dashboard: {e}")

elif app_choice == "📸 Image Management":
    st.title("📸 Image Management System")
    
    try:
        image_path = current_dir / "image_management"
        if image_path.exists():
            sys.path.insert(0, str(image_path))
            st.info("🔧 Loading Image Management System...")
            st.markdown("**Note**: This would load the Image Management app here.")
            st.markdown("The app needs to be refactored to work as an imported module.")
        else:
            st.error("Image Management System not found!")
    except Exception as e:
        st.error(f"Error loading Image Management System: {e}")

elif app_choice == "🌍 EarthRanger Dashboard":
    st.title("🌍 EarthRanger Dashboard")
    st.info("🚧 This application is currently in development.")
    st.markdown("""
    **Planned Features:**
    - Wildlife tracking integration
    - Conservation area monitoring  
    - Alert management
    - Data visualization
    
    Check back soon for updates!
    """)

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("**🦒 Giraffe Conservation Foundation**")
st.sidebar.markdown("*Supporting conservation through technology*")
