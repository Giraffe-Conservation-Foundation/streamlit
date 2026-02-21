# KEEP Dashboard

This dashboard embeds the ArcGIS Dashboard for the KEEP (Key Elephant & Environmental Pressures) project.

## Features

- **Password Protection**: Secure access using the same password as the Publications dashboard
- **Full-Page Display**: Dashboard fills the available space for optimal viewing
- **ArcGIS Integration**: Direct embedding of the ArcGIS Dashboard

## Dashboard URL

https://giraffecf.maps.arcgis.com/apps/dashboards/572591b7353b4c1db3a4e85d200ed2de

## ArcGIS Authentication

The dashboard uses the same ArcGIS token as the GAD dashboard for authentication.

### Setup

The token is automatically loaded from Streamlit secrets (same configuration as GAD):

```toml
[arcgis]
token = "your-arcgis-token-here"
```

The app will automatically append the token to the dashboard URL for seamless viewing without sign-in prompts.

### For Streamlit Cloud

1. Go to your app settings on Streamlit Cloud
2. Navigate to "Secrets"
3. Ensure the arcgis.token is configured (should already be set for GAD dashboard)
4. Save and redeploy

**Note:** This uses the same token configuration as the GAD dashboard, so if GAD works, KEEP should work automatically.

## Password

Uses the same password configuration as the Publications dashboard (stored in `st.secrets["passwords"]["publications_password"]`).

## Usage

The dashboard is automatically accessible from the main Twigatools app sidebar as "🎓 KEEP".
