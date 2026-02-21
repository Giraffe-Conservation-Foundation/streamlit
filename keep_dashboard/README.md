# KEEP Dashboard

This dashboard embeds the ArcGIS Dashboard for the KEEP (Key Elephant & Environmental Pressures) project.

## Features

- **Password Protection**: Secure access using the same password as the Publications dashboard
- **Full-Page Display**: Dashboard fills the available space for optimal viewing
- **ArcGIS Integration**: Direct embedding of the ArcGIS Dashboard

## Dashboard URL

https://giraffecf.maps.arcgis.com/apps/dashboards/572591b7353b4c1db3a4e85d200ed2de

## Dashboard Access

The KEEP Dashboard automatically opens in a new browser tab when you access this page.

### How It Works

1. When you navigate to the KEEP Dashboard page, it automatically opens the ArcGIS dashboard in a new tab
2. You'll authenticate with ArcGIS in that new tab (if not already signed in)
3. Once authenticated, your session persists in that tab
4. You can return to the dashboard anytime by keeping the tab open

### Manual Access

If the automatic opening is blocked by your browser, a button is provided to manually open the dashboard.

**Dashboard URL:** https://giraffecf.maps.arcgis.com/apps/dashboards/572591b7353b4c1db3a4e85d200ed2de

### Note

This approach opens the dashboard in a full browser context where ArcGIS authentication works properly, avoiding the limitations of iframe embedding.

## Password

Uses the same password configuration as the Publications dashboard (stored in `st.secrets["passwords"]["publications_password"]`).

## Usage

The dashboard is automatically accessible from the main Twigatools app sidebar as "🎓 KEEP".
