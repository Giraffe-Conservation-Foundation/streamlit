# KEEP Dashboard

This dashboard embeds the ArcGIS Dashboard for the KEEP (Key Elephant & Environmental Pressures) project.

## Features

- **Password Protection**: Secure access using the same password as the Publications dashboard
- **Full-Page Display**: Dashboard fills the available space for optimal viewing
- **ArcGIS Integration**: Direct embedding of the ArcGIS Dashboard

## Dashboard URL

https://giraffecf.maps.arcgis.com/apps/dashboards/572591b7353b4c1db3a4e85d200ed2de

## ArcGIS Authentication

To avoid the "Please sign in to ArcGIS Online" prompt, you have two options:

### Option 1: Make Dashboard Public (Recommended)
1. Go to your ArcGIS Dashboard
2. Click "Share" 
3. Select "Everyone (public)" or "Organization"
4. Save the sharing settings

### Option 2: Use Token Authentication
If you need to keep the dashboard private, add an ArcGIS token to your Streamlit secrets:

```toml
[arcgis]
token = "your-arcgis-token-here"
```

The app will automatically append the token to the dashboard URL for authentication.

## Password

Uses the same password configuration as the Publications dashboard (stored in `st.secrets["passwords"]["publications_password"]`).

## Usage

The dashboard is automatically accessible from the main Twigatools app sidebar as "🎓 KEEP".
