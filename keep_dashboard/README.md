# KEEP Dashboard

This dashboard embeds the ArcGIS Dashboard for the KEEP (Key Elephant & Environmental Pressures) project.

## Features

- **Password Protection**: Secure access using the same password as the Publications dashboard
- **Full-Page Display**: Dashboard fills the available space for optimal viewing
- **ArcGIS Integration**: Direct embedding of the ArcGIS Dashboard

## Dashboard URL

https://giraffecf.maps.arcgis.com/apps/dashboards/572591b7353b4c1db3a4e85d200ed2de

## ArcGIS Authentication

The dashboard automatically authenticates using ArcGIS credentials stored in Streamlit secrets.

### Setup

Add your ArcGIS credentials to Streamlit secrets:

```toml
[arcgis]
username = "your-arcgis-username"
password = "your-arcgis-password"
portal_url = "https://giraffecf.maps.arcgis.com"  # Optional, defaults to this value
```

The app will:
1. Automatically authenticate with ArcGIS using the provided credentials
2. Get an access token
3. Load the dashboard with the token - no user interaction required

### For Streamlit Cloud

1. Go to your app settings on Streamlit Cloud
2. Navigate to "Secrets"
3. Add the arcgis credentials as shown above
4. Save and redeploy

**Note:** Users will not see any authentication prompts. The dashboard loads automatically.

## Password

Uses the same password configuration as the Publications dashboard (stored in `st.secrets["passwords"]["publications_password"]`).

## Usage

The dashboard is automatically accessible from the main Twigatools app sidebar as "🎓 KEEP".
