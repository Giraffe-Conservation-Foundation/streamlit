import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from ecoscope.io.earthranger import EarthRangerIO
from pandas import json_normalize, to_datetime
import requests
import os
from pathlib import Path

def main():
    """Main function for the EHGR Dashboard"""
    
    # Try to load environment variables from .env file
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        st.sidebar.warning("⚠️ python-dotenv not installed. Using default settings.")
        
    # Force deployment update - timestamp: Sep 26, 2025 - EHGR DASHBOARD IMPLEMENTATION
    # EHGR Dashboard - Complete implementation with satellite mapping - NAMIBIA DATA

    # Configuration - can be overridden by environment variables
    EARTHRANGER_SERVER = os.getenv('EARTHRANGER_SERVER', 'https://twiga.pamdas.org')
    MAPBOX_TOKEN = os.getenv('MAPBOX_TOKEN', '')  # Add your Mapbox token here or in .env file

    #### ER AUTHENTICATION ###############################################
    def er_login(username, password):
        try:
            er = EarthRangerIO(
                server=EARTHRANGER_SERVER,
                username=username,
                password=password
            )
            # Try a simple call to check credentials
            er.get_subjects(limit=1)
            return True
        except Exception:
            return False
        
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
    if "username" not in st.session_state:
        st.session_state["username"] = ""
    if "password" not in st.session_state:
        st.session_state["password"] = ""

    if not st.session_state["authenticated"]:
        st.title("🦒 Login to EHGR EarthRanger Dashboard")
        username = st.text_input("EarthRanger Username")
        password = st.text_input("EarthRanger Password", type="password")
        if st.button("Login"):
            if er_login(username, password):
                st.session_state["authenticated"] = True
                st.session_state["username"] = username
                st.session_state["password"] = password
                st.success("Login successful!")
                st.rerun()  # Updated from deprecated st.experimental_rerun()
            else:
                st.error("Invalid credentials. Please try again.")
        st.stop()

    # After this point, only the dashboard is shown!
    username = st.session_state["username"]
    password = st.session_state["password"]

    # Header with logo
    current_dir = Path(__file__).parent.parent
    logo_path = current_dir / "shared" / "logo.png"

    if logo_path.exists():
        try:
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.image(str(logo_path), width=300)
                st.markdown('<div style="text-align: center;"><h1>🦒 EHGR Giraffe Monitoring Dashboard</h1></div>', unsafe_allow_html=True)
                #st.markdown('<div style="text-align: center;"><h3>🇳🇦 Namibia Conservation Tracking</h3></div>', unsafe_allow_html=True)
        except Exception:
            st.title("🦒 EHGR Giraffe Monitoring Dashboard")
    else:
        st.title("🦒 EHGR Giraffe Monitoring Dashboard")

    # Simplified EHGR dashboard without subject group dependencies

    @st.cache_data(ttl=3600)
    def get_active_sources():
        """Get active tracking sources for EHGR giraffes"""
        er = EarthRangerIO(
            server="https://twiga.pamdas.org",
            username=username,
            password=password
        )
        sources_df = er.get_sources()
        sources = sources_df.to_dict('records')
        
        # Filter for active sources (exclude dummy sources)
        active_sources = [
            s for s in sources 
            if s.get("provider") != "dummy"
            and s.get("is_active") is True
        ]
        return active_sources

    active_sources = get_active_sources()

    @st.cache_data(ttl=3600)
    def load_data():
        """Load EHGR giraffe survey encounter data"""
        er = EarthRangerIO(
            server="https://twiga.pamdas.org",
            username=username,
            password=password
        )
        
        # EHGR-specific event parameters (Namibia data)
        event_cat = "monitoring_nam"
        event_type = "giraffe_survey_encounter_nam"
        since = "2024-07-01T00:00:00Z"
        until = "2025-12-31T23:59:59Z"

        try:
            events = er.get_events(
                event_category=event_cat,
                since=since,
                until=until,
                include_details=True,
                include_notes=False
            )
            
            if events.empty:
                st.warning(f"⚠️ No events found for category '{event_cat}' and type '{event_type}'")
                st.info("💡 Please verify the event category and type names are correct for EHGR")
                return pd.DataFrame()
            
            flat = json_normalize(events.to_dict(orient="records"))
            giraffe_only = flat[flat["event_type"] == event_type]

            if giraffe_only.empty:
                st.warning(f"⚠️ No events found with event_type '{event_type}'")
                available_types = flat["event_type"].unique() if "event_type" in flat.columns else []
                if len(available_types) > 0:
                    st.info(f"💡 Available event types: {', '.join(available_types)}")
                return pd.DataFrame()

            # Process herd data if available - but keep one record per herd encounter
            if "event_details.Herd" in giraffe_only.columns:
                # For individual giraffe analysis later, we can explode
                # But for metrics, we want to keep herd-level data
                events_final = giraffe_only.copy()
            else:
                events_final = giraffe_only

            return events_final
            
        except Exception as e:
            st.error(f"❌ Error loading EHGR data: {str(e)}")
            st.info("💡 Please check the event category and type parameters")
            return pd.DataFrame()

    df = load_data()

    if df.empty:
        st.warning("⚠️ No data available to display")
        st.info("""
        **Possible issues:**
        1. Event category 'monitoring_nam' may not exist
        2. Event type 'giraffe_survey_encounter_nam' may not exist  
        3. No data in the specified date range
        4. Subject group IDs need to be updated
        
        **Next steps:**
        - Verify the correct event category and type names for EHGR
        - Update the subject group IDs in the code
        - Check if there's data in the specified date range
        """)
        st.stop()

    # Rename columns (similar to NANW but adapted for EHGR structure)
    rename_map = {
        "reported_by.id": "user_id",
        "reported_by.name": "user_name",
        "id": "event_id",
        "event_type": "evt_type",
        "event_category": "evt_category",
        "serial_number": "evt_serial",
        "url": "evt_url",
        "time": "evt_dttm",
        "location.latitude": "lat",
        "location.longitude": "lon",
        "event_details.image_prefix": "evt_imagePrefix",
        "event_details.herd_dire": "evt_herd_dir",
        "event_details.herd_dist": "evt_herd_dist",
        "event_details.herd_size": "evt_herdSize",
        "event_details.herd_notes": "evt_herdNotes",
        "giraffe_id": "evt_girID",
        "giraffe_age": "evt_girAge",
        "giraffe_gsd": "evt_girGSD",
        "giraffe_sex": "evt_girSex",
        "giraffe_dire": "evt_girDire",
        "giraffe_dist": "evt_girDist",
        "giraffe_snar": "evt_girSnare",
        "giraffe_notes": "evt_girNotes",
        "giraffe_right": "evt_girRight",
        "giraffe_left": "evt_gifLeft",
        "giraffe_gsd_loc": "evt_girGSD_loc",
        "giraffe_gsd_sev": "evt_girGSD_sev",
        "event_details.river_system": "evt_riverSystem"
    }

    df = df.rename(columns=rename_map)
    df["evt_dttm"] = pd.to_datetime(df["evt_dttm"])
    df = df.dropna(subset=["evt_dttm"])

    # Sidebar filters
    st.sidebar.header("Filter Date Range")
    # Clean evt_dttm and drop NaT values
    df["evt_dttm"] = pd.to_datetime(df["evt_dttm"], errors="coerce")
    df = df.dropna(subset=["evt_dttm"])
    if df["evt_dttm"].notna().any():
        min_date = df["evt_dttm"].min().date()
        max_date = df["evt_dttm"].max().date()
    else:
        min_date = datetime.today().date()
        max_date = datetime.today().date()

    date_range = st.sidebar.date_input("Select date range", [min_date, max_date])

    if len(date_range) == 2:
        filtered_df = df[(df["evt_dttm"].dt.date >= date_range[0]) & (df["evt_dttm"].dt.date <= date_range[1])]
    else:
        filtered_df = df

    #### DASHBOARD LAYOUT ###############################################

    #### heading metrics
    # Simplified metrics without subject group dependencies

    # Calculate basic metrics from filtered data
    individuals_seen = filtered_df["evt_herdSize"].sum() if "evt_herdSize" in filtered_df.columns else 0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Individuals seen", individuals_seen)
    with col2:
        st.metric("", "")  # Empty placeholder
    with col3:
        # Count unique encounters/herds (each row represents one herd encounter)
        herd_count = len(filtered_df) if not filtered_df.empty else 0
        st.metric("Herds seen", herd_count)
    with col4:
        if "evt_herdSize" in filtered_df.columns:
            avg_herd_size = filtered_df["evt_herdSize"].mean()
            st.metric("Average herd size", f"{avg_herd_size:.1f}" if not pd.isna(avg_herd_size) else "N/A")
        else:
            st.metric("Average herd size", "N/A")

    #### Sighting map
    st.subheader("📍 Sightings map")
    map_df = filtered_df.dropna(subset=["lat", "lon"])
    if not map_df.empty:
        # Create plotly map with dark satellite style and park boundaries
        fig_map = px.scatter_mapbox(
            map_df, 
            lat="lat", 
            lon="lon",
            hover_data=["evt_dttm", "evt_herdSize"] if "evt_herdSize" in map_df.columns else ["evt_dttm"],
            zoom=8,
            height=500,
            title="Giraffe Sightings"
        )
        
        # Set map style based on token availability
        if MAPBOX_TOKEN:
            # Use satellite-streets for Google Maps-like experience with boundaries
            map_style = "satellite-streets"
            px.set_mapbox_access_token(MAPBOX_TOKEN)
        else:
            # Fallback to open street map (free, no token required)
            map_style = "open-street-map"
        
        # Update layout for dark satellite style with boundaries
        fig_map.update_layout(
            mapbox_style=map_style,
            mapbox=dict(
                center=dict(
                    lat=map_df["lat"].mean(),
                    lon=map_df["lon"].mean()
                ),
                zoom=8
            ),
            margin={"r":0,"t":50,"l":0,"b":0},
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)"
        )
        
        # Update marker style for better visibility
        if map_style == "satellite-streets":
            # Yellow markers for satellite view
            marker_color = "yellow"
        else:
            # Red markers for street map
            marker_color = "red"
        
        fig_map.update_traces(
            marker=dict(
                size=12,
                color=marker_color,
                opacity=0.8
            )
        )
        
        st.plotly_chart(fig_map, use_container_width=True)
    else:
        st.info("No location data available for mapping")

    #### Age/sex breakdown bar chart
    st.subheader("🧬 Age / sex breakdown")

    # For age/sex breakdown, we need individual giraffe data
    # So we'll explode the herd data here if needed
    if not filtered_df.empty and "event_details.Herd" in df.columns:
        # Explode herd data for individual analysis
        individual_df = filtered_df.explode("event_details.Herd").reset_index(drop=True)
        if not individual_df["event_details.Herd"].isna().all():
            herd_details = json_normalize(individual_df["event_details.Herd"])
            individual_df = pd.concat([individual_df.drop(columns="event_details.Herd"), herd_details], axis=1)
            
            # Map the individual giraffe columns
            if "giraffe_sex" in individual_df.columns and "giraffe_age" in individual_df.columns:
                breakdown = (
                    individual_df.groupby(["giraffe_sex", "giraffe_age"])
                    .size()
                    .reset_index(name="Count")
                )
                fig2 = px.bar(breakdown, x="giraffe_age", y="Count", color="giraffe_sex", barmode="group")
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("No individual giraffe age/sex data available in herd details")
        else:
            st.info("No herd detail data available for age/sex breakdown")
    elif not filtered_df.empty and "evt_girSex" in filtered_df.columns and "evt_girAge" in filtered_df.columns:
        # Use direct event-level age/sex data if available
        breakdown = (
            filtered_df.groupby(["evt_girSex", "evt_girAge"])
            .size()
            .reset_index(name="Count")
        )
        fig2 = px.bar(breakdown, x="evt_girAge", y="Count", color="evt_girSex", barmode="group")
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No age/sex data available for breakdown chart")

    #### Simplified - AAG section removed as not applicable for EHGR

    # Logout button
    if st.sidebar.button("🔓 Logout"):
        for key in ['authenticated', 'username', 'password']:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

if __name__ == "__main__":
    main()