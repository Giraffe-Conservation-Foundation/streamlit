# KEEP Dashboard

This dashboard embeds the ArcGIS Dashboard for the KEEP (Key Elephant & Environmental Pressures) project.

## Features

- **Password Protection**: Secure access using the same password as the Publications dashboard
- **Full-Page Display**: Dashboard fills the available space for optimal viewing
- **ArcGIS Integration**: Direct embedding of the ArcGIS Dashboard

## Dashboard URL

https://giraffecf.maps.arcgis.com/apps/dashboards/572591b7353b4c1db3a4e85d200ed2de

## ArcGIS Authentication

The dashboard may show a "Please sign in to ArcGIS Online" prompt. Users can simply click "OK" or "Cancel" and the dashboard will load.

### To Permanently Remove the Sign-In Prompt:

**Make the Dashboard Public (Strongly Recommended):**
1. Log in to ArcGIS Online at https://www.arcgis.com
2. Go to "Content" and find your KEEP Dashboard
3. Click on the dashboard, then click "Share"
4. Select "Everyone (public)" 
5. Click "Save"

After making the dashboard public, the sign-in prompt will no longer appear for any users.

### Alternative: Token Authentication (Private Dashboards Only)
If you must keep the dashboard private, add an ArcGIS token to your Streamlit secrets:

```toml
[arcgis]
token = "your-arcgis-token-here"
```

**Note:** Making the dashboard public is the recommended solution as it provides the best user experience.

## Password

Uses the same password configuration as the Publications dashboard (stored in `st.secrets["passwords"]["publications_password"]`).

## Usage

The dashboard is automatically accessible from the main Twigatools app sidebar as "🎓 KEEP".
