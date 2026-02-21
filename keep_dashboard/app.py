"""
KEEP Dashboard
Embedded ArcGIS Dashboard for KEEP project
"""

import streamlit as st
import sys
from pathlib import Path
import base64

# Add shared utilities for logo
current_dir = Path(__file__).parent.parent
sys.path.append(str(current_dir))

try:
    from shared.utils import add_sidebar_logo
except ImportError:
    def add_sidebar_logo():
        pass

# Get ArcGIS credentials from secrets
try:
    ARCGIS_USERNAME = st.secrets.get("arcgis", {}).get("username", None)
    ARCGIS_PASSWORD = st.secrets.get("arcgis", {}).get("password", None)
    PORTAL_URL = st.secrets.get("arcgis", {}).get("portal_url", "https://giraffecf.maps.arcgis.com")
except Exception:
    ARCGIS_USERNAME = None
    ARCGIS_PASSWORD = None
    PORTAL_URL = "https://giraffecf.maps.arcgis.com"

# Custom CSS for full-page iframe
st.markdown("""
<style>
    /* Remove padding and margins for full-page display */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 0rem;
        padding-left: 1rem;
        padding-right: 1rem;
        max-width: 100%;
    }
    
    iframe {
        border: none;
    }
</style>
""", unsafe_allow_html=True)

# ======== Authentication Functions ========

def check_password():
    """Returns `True` if the user had the correct password."""
    def password_entered():
        """Checks whether a password entered by the user is correct."""
        try:
            # Try to get password from secrets (same as publications)
            if st.session_state["password"] == st.secrets["passwords"]["publications_password"]:
                st.session_state["password_correct"] = True
                del st.session_state["password"]  # don't store password
            else:
                st.session_state["password_correct"] = False
        except Exception as e:
            # For local development without secrets.toml, use a default password
            if st.session_state["password"] == "admin":
                st.session_state["password_correct"] = True
                del st.session_state["password"]
            else:
                st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # First run, show input for password
        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        st.write("*Please enter password to access the KEEP Dashboard.*")
        return False
    elif not st.session_state["password_correct"]:
        # Password incorrect, show input + error
        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        st.error("😕 Password incorrect")
        return False
    else:
        # Password correct
        return True

def main():
    """Main application function"""
    
    # Add logo to sidebar
    add_sidebar_logo()
    
    # Check password
    if not check_password():
        return
    
    # Page title
    st.title("🎓 KEEP Dashboard")
    st.markdown("---")
    
    # ArcGIS Dashboard URL
    dashboard_url = "https://giraffecf.maps.arcgis.com/apps/dashboards/572591b7353b4c1db3a4e85d200ed2de"
    
    # Check if we have credentials
    if not ARCGIS_USERNAME or not ARCGIS_PASSWORD:
        st.error("❌ ArcGIS credentials not configured in secrets.")
        st.info("Add arcgis.username and arcgis.password to Streamlit secrets.")
        return
    
    # Create auto-login HTML page
    # Encode credentials for JavaScript
    username_b64 = base64.b64encode(ARCGIS_USERNAME.encode()).decode()
    password_b64 = base64.b64encode(ARCGIS_PASSWORD.encode()).decode()
    
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body, html {{
                margin: 0;
                padding: 0;
                height: 100%;
                overflow: hidden;
            }}
            #dashboardFrame {{
                width: 100%;
                height: 100vh;
                border: none;
            }}
            .loading {{
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                font-family: Arial, sans-serif;
                background-color: #f5f5f5;
            }}
            .spinner {{
                border: 4px solid #f3f3f3;
                border-top: 4px solid #0079c1;
                border-radius: 50%;
                width: 40px;
                height: 40px;
                animation: spin 1s linear infinite;
                margin-right: 15px;
            }}
            @keyframes spin {{
                0% {{ transform: rotate(0deg); }}
                100% {{ transform: rotate(360deg); }}
            }}
        </style>
    </head>
    <body>
        <div id="loadingDiv" class="loading">
            <div class="spinner"></div>
            <div>
                <h3>Authenticating with ArcGIS...</h3>
                <p>Please wait while we load your dashboard</p>
            </div>
        </div>
        <iframe id="dashboardFrame" style="display:none;"></iframe>
        
        <script>
            // Decode credentials
            const username = atob('{username_b64}');
            const password = atob('{password_b64}');
            const portalUrl = '{PORTAL_URL}';
            const dashboardUrl = '{dashboard_url}';
            
            // Function to authenticate and get token
            async function authenticate() {{
                try {{
                    const tokenUrl = portalUrl + '/sharing/rest/generateToken';
                    
                    const params = new URLSearchParams();
                    params.append('username', username);
                    params.append('password', password);
                    params.append('referer', portalUrl);
                    params.append('f', 'json');
                    
                    const response = await fetch(tokenUrl, {{
                        method: 'POST',
                        body: params
                    }});
                    
                    const data = await response.json();
                    
                    if (data.token) {{
                        // Successfully authenticated, load dashboard with token
                        loadDashboard(data.token);
                    }} else {{
                        showError('Authentication failed: ' + (data.error?.message || 'Unknown error'));
                    }}
                }} catch (error) {{
                    showError('Error authenticating: ' + error.message);
                }}
            }}
            
            function loadDashboard(token) {{
                const iframe = document.getElementById('dashboardFrame');
                const urlWithToken = dashboardUrl + '?token=' + token;
                
                iframe.onload = function() {{
                    document.getElementById('loadingDiv').style.display = 'none';
                    iframe.style.display = 'block';
                }};
                
                iframe.src = urlWithToken;
            }}
            
            function showError(message) {{
                const loadingDiv = document.getElementById('loadingDiv');
                loadingDiv.innerHTML = '<div style="color: red;"><h3>❌ Error</h3><p>' + message + '</p></div>';
            }}
            
            // Start authentication on page load
            authenticate();
        </script>
    </body>
    </html>
    """
    
    # Display the auto-login page
    st.components.v1.html(html_code, height=1000, scrolling=False)

if __name__ == "__main__":
    main()
