import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from ecoscope.io.earthranger import EarthRangerIO
from pandas import json_normalize, to_datetime
import requests
import os

# Force deployment update - timestamp: Sep 3, 2025 - SIMPLIFIED HERD COUNT FIX
# NANW Dashboard - Fixed double-counting issue in herd metrics (simplified approach)

# Try to load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    st.sidebar.warning("⚠️ python-dotenv not installed. Using default settings.")
    
# Force deployment update - timestamp: Aug 5, 2025

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
    st.title("Login to EarthRanger Dashboard")
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











@st.cache_data(ttl=3600)
def get_active_nanw_subjects():
    er = EarthRangerIO(
        server="https://twiga.pamdas.org",
        username=username,
        password=password
    )
    subjects_df = er.get_subjects(subject_group_id="518a21df-46a0-4dfb-90de-54e1caca889e")
    subjects = subjects_df.to_dict('records')
    active = [s for s in subjects if s.get("is_active") is True]
    return active

@st.cache_data(ttl=3600)
def get_active_aag_subjects():
    er = EarthRangerIO(
        server="https://twiga.pamdas.org",
        username=username,
        password=password
    )
    subjects_df = er.get_subjects(subject_group_id="660dbfb0-a7cb-4b93-92e9-a8f006f9bead")
    subjects = subjects_df.to_dict('records')
    return subjects

active_subjects = get_active_nanw_subjects()
aag_subjects = get_active_aag_subjects()
aag_id_to_name = {s["id"]: s["name"] for s in aag_subjects if "id" in s and "name" in s}
aag_ids = set(aag_id_to_name.keys())

@st.cache_data(ttl=3600)
def get_active_sources():
    er = EarthRangerIO(
        server="https://twiga.pamdas.org",
        username=username,
        password=password
    )
    sources_df = er.get_sources()
    sources = sources_df.to_dict('records')
    
    # Filter for sources on NANW giraffes (exclude dummy sources)
    nanw_subject_ids = {s["id"] for s in active_subjects}
    active_sources = [
        s for s in sources 
        if s.get("subject_id") in nanw_subject_ids 
        and s.get("provider") != "dummy"
        and s.get("is_active") is True
    ]
    return active_sources

active_sources = get_active_sources()



@st.cache_data(ttl=3600)
def load_data():
    er = EarthRangerIO(
        server="https://twiga.pamdas.org",
        username=username,
        password=password
    )
    
    event_cat = "monitoring_nanw"
    event_type = "giraffe_nw_monitoring"
    since = "2024-07-01T00:00:00Z"
    until = "2026-12-31T23:59:59Z"

    events = er.get_events(
        event_category=event_cat,
        since=since,
        until=until,
        include_details=True,
        include_notes=False
    )
    flat = json_normalize(events.to_dict(orient="records"))
    
    # Check if we have data and the event_type column exists
    if flat.empty or "event_type" not in flat.columns:
        # Return empty DataFrames with expected structure
        return pd.DataFrame(), pd.DataFrame()
    
    giraffe_only = flat[flat["event_type"] == event_type]

    # Keep herd-level data for accurate metrics calculation
    herd_level_data = giraffe_only.copy()
    
    # Check if we have any giraffe events
    if giraffe_only.empty:
        return pd.DataFrame(), pd.DataFrame()
    
    # Explode for individual giraffe analysis
    giraffe_only = giraffe_only.explode("event_details.Herd").reset_index(drop=True)
    herd_df = json_normalize(giraffe_only["event_details.Herd"])
    events_final = pd.concat([giraffe_only.drop(columns="event_details.Herd"), herd_df], axis=1)
    
    # Return both datasets
    return events_final, herd_level_data

    return events_final

df, herd_level_df = load_data()

# Check if we have data
if df.empty or herd_level_df.empty:
    st.warning("⚠️ No monitoring data available for the selected date range. Please check back later or adjust your date range.")
    st.stop()

# Rename columns
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




#### DASHBOARD LAYOUT ###############################################
#st.title("🦒 GCF Namibia NW monitoring")

# Date filter row
st.subheader("📅 Filter Date Range")
col_date_start, col_date_end = st.columns(2)

# Clean evt_dttm and drop NaT values
df["evt_dttm"] = pd.to_datetime(df["evt_dttm"], errors="coerce")
df = df.dropna(subset=["evt_dttm"])

# Set min/max dates from data for date picker range
if df["evt_dttm"].notna().any():
    data_min_date = df["evt_dttm"].min().date()
    data_max_date = df["evt_dttm"].max().date()
else:
    data_min_date = datetime.today().date()
    data_max_date = datetime.today().date()

# Set default dates: last 30 days
from datetime import timedelta
default_end_date = datetime.today().date()
default_start_date = default_end_date - timedelta(days=30)

# Adjust defaults to be within data range
if default_end_date > data_max_date:
    default_end_date = data_max_date
if default_start_date < data_min_date:
    default_start_date = data_min_date
if default_start_date > data_max_date:
    default_start_date = data_max_date

with col_date_start:
    start_date = st.date_input(
        "Start Date", 
        value=default_start_date,
        min_value=data_min_date,
        max_value=data_max_date,
        key="start_date"
    )

with col_date_end:
    end_date = st.date_input(
        "End Date", 
        value=default_end_date,
        min_value=data_min_date,
        max_value=data_max_date,
        key="end_date"
    )

# Ensure dates are valid
if start_date and end_date:
    if start_date > end_date:
        st.error("⚠️ Start date must be before end date")
        st.stop()
    
    # Apply date range filter - normalize timezone-aware datetimes to dates for comparison
    df_dates = df["evt_dttm"].dt.tz_localize(None).dt.date if df["evt_dttm"].dt.tz is not None else df["evt_dttm"].dt.date
    filtered_df = df[(df_dates >= start_date) & (df_dates <= end_date)]
else:
    filtered_df = df.copy()

# Display filter info
if len(df) > 0:
    st.caption(f"Showing {len(filtered_df)} sightings from {start_date} to {end_date}")
else:
    st.caption(f"No data available")

st.markdown("---")

#### heading metrics

# Calculate percentage of population seen
distinct_individuals_seen = filtered_df["evt_girID"].nunique()
total_population = len(active_subjects)
if total_population > 0:
    percentage_seen = (distinct_individuals_seen / total_population) * 100
else:
    percentage_seen = 0

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("Total Population", total_population)
with col2:
    st.metric("Individuals Seen", distinct_individuals_seen)
with col3:
    import math
    st.metric("% Population Seen", f"{math.ceil(percentage_seen)}%")
with col4:
    # Use herd-level data for accurate herd count
    # Process the herd-level data with same date filtering
    herd_df_for_metrics = herd_level_df.copy()
    herd_df_for_metrics["evt_dttm"] = pd.to_datetime(herd_df_for_metrics["time"], errors="coerce")
    herd_df_for_metrics = herd_df_for_metrics.dropna(subset=["evt_dttm"])
    
    # Apply date range filter
    herd_df_for_metrics = herd_df_for_metrics[
        (herd_df_for_metrics["evt_dttm"].dt.date >= start_date) & 
        (herd_df_for_metrics["evt_dttm"].dt.date <= end_date)
    ]
    
    herd_count = len(herd_df_for_metrics)
    st.metric("Herds Seen", herd_count)
with col5:
    # Use herd-level data for average herd size calculation
    herd_df_for_metrics = herd_df_for_metrics.rename(columns={"event_details.herd_size": "evt_herdSize"})
    avg_herd_size = herd_df_for_metrics["evt_herdSize"].mean() if "evt_herdSize" in herd_df_for_metrics.columns else filtered_df["evt_herdSize"].mean()
    st.metric("Avg Herd Size", f"{avg_herd_size:.1f}" if not pd.isna(avg_herd_size) else "N/A")

#### Sighting map
st.subheader("📍 Sightings map")
map_df = filtered_df.dropna(subset=["lat", "lon"])
if not map_df.empty:
    # Create plotly map with dark satellite style (same as ZAF dashboard)
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

#### Sightings/month bar chart
st.subheader("📅 Sightings per month")
monthly_counts = (
    filtered_df.groupby(filtered_df["evt_dttm"].dt.to_period("M"))
    .size()
    .reset_index(name="Sightings")
)
monthly_counts["Month"] = monthly_counts["evt_dttm"].astype(str)
fig1 = px.bar(monthly_counts, x="Month", y="Sightings", title="Monthly Sightings")
st.plotly_chart(fig1, use_container_width=True)

#### Age/sex breakdown bar chart
st.subheader("🧬 Age / sex breakdown")
breakdown = (
    filtered_df.groupby(["evt_girSex", "evt_girAge"])
    .size()
    .reset_index(name="Count")
)
fig2 = px.bar(breakdown, x="evt_girAge", y="Count", color="evt_girSex", barmode="group")
st.plotly_chart(fig2, use_container_width=True)

#### Table of giraffe names 
st.subheader("🦒 List of giraffe seen")
id_to_name = {s["id"]: s["name"] for s in active_subjects if "id" in s and "name" in s}   # Build a mapping from subject ID to name
filtered_df["giraffe_name"] = filtered_df["evt_girID"].map(id_to_name)   # Map evt_girID to giraffe name
girid_table = (
    filtered_df[["evt_girID", "giraffe_name"]]
    .drop_duplicates()
    .sort_values("giraffe_name")
    .reset_index(drop=True)
)
st.dataframe(girid_table[["giraffe_name"]].drop_duplicates().sort_values("giraffe_name").reset_index(drop=True), use_container_width=True)

#### Table of Adopt A Giraffe giraffe seen 
aag_seen = filtered_df[filtered_df["evt_girID"].isin(aag_ids)].copy()
aag_seen["giraffe_name"] = aag_seen["evt_girID"].map(aag_id_to_name)
aag_table = (
    aag_seen[["evt_girID", "giraffe_name"]]
    .drop_duplicates()
    .sort_values("giraffe_name")
    .reset_index(drop=True)
)
st.subheader("🦒 List of AAG giraffe seen")
if not aag_table.empty:
    st.dataframe(aag_table[["giraffe_name"]].drop_duplicates().sort_values("giraffe_name").reset_index(drop=True), use_container_width=True)
else:
    st.info("No AAG giraffes seen in the selected data.")
