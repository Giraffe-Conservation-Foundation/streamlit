import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import math
from datetime import datetime, date, timedelta
from ecoscope.io.earthranger import EarthRangerIO
from pandas import json_normalize, to_datetime
import requests
import os
from pathlib import Path

# Try to load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    st.sidebar.warning("⚠️ python-dotenv not installed. Using default settings.")

# Configuration - can be overridden by environment variables
EARTHRANGER_SERVER = os.getenv('EARTHRANGER_SERVER', 'https://twiga.pamdas.org')
MAPBOX_TOKEN = os.getenv('MAPBOX_TOKEN', '')  # Add your Mapbox token here or in .env file

# Subject groups
GIRAFFE_GROUP_ID = "518a21df-46a0-4dfb-90de-54e1caca889e"
ELEPHANT_GROUP_ID = "7dac5314-214d-4103-b16d-46fa95f7e158"
AAG_GROUP_ID = "660dbfb0-a7cb-4b93-92e9-a8f006f9bead"

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
            st.rerun()
        else:
            st.error("Invalid credentials. Please try again.")
    st.stop()

# After this point, only the dashboard is shown!
username = st.session_state["username"]
password = st.session_state["password"]


#### SUBJECT GROUPS ###################################################
@st.cache_data(ttl=3600)
def get_active_subjects(group_id, include_inactive=False):
    """Get subjects belonging to an EarthRanger subject group."""
    er = EarthRangerIO(
        server=EARTHRANGER_SERVER,
        username=username,
        password=password
    )
    try:
        subjects_df = er.get_subjects(subject_group_id=group_id, include_inactive=include_inactive)
    except AssertionError:
        # ecoscope's get_subjects raises an AssertionError when the group has
        # no subjects matching the filter (e.g. empty/new subject group).
        return []
    subjects = subjects_df.to_dict('records')
    if not include_inactive:
        subjects = [s for s in subjects if s.get("is_active") is True]
    return subjects

@st.cache_data(ttl=3600)
def get_hoanib_giraffe_subjects():
    """Get subjects from NAM_Hoanib_giraffe group (GPS-collared giraffes)"""
    er = EarthRangerIO(
        server=EARTHRANGER_SERVER,
        username=username,
        password=password
    )
    subjects_df = er.get_subjects(subject_group_name="NAM_Hoanib_giraffe", include_inactive=True)
    subjects = subjects_df.to_dict('records')
    return subjects

active_giraffe_subjects = get_active_subjects(GIRAFFE_GROUP_ID)
active_elephant_subjects = get_active_subjects(ELEPHANT_GROUP_ID)
aag_subjects = get_active_subjects(AAG_GROUP_ID, include_inactive=True)
hoanib_gps_subjects = get_hoanib_giraffe_subjects()
aag_id_to_name = {s["id"]: s["name"] for s in aag_subjects if "id" in s and "name" in s}
aag_ids = set(aag_id_to_name.keys())

@st.cache_data(ttl=3600)
def get_active_sources():
    er = EarthRangerIO(
        server=EARTHRANGER_SERVER,
        username=username,
        password=password
    )
    sources_df = er.get_sources()
    sources = sources_df.to_dict('records')

    # Filter for sources on NANW giraffes (exclude dummy sources)
    nanw_subject_ids = {s["id"] for s in active_giraffe_subjects}
    active_sources = [
        s for s in sources
        if s.get("subject_id") in nanw_subject_ids
        and s.get("provider") != "dummy"
        and s.get("is_active") is True
    ]
    return active_sources

active_sources = get_active_sources()


#### EVENT DATA LOADING ###############################################
def build_rename_map(species):
    """Column rename map for a monitoring event, parameterized by species
    (event field names follow the pattern '{species}_id', '{species}_age', etc.)"""
    return {
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
        f"{species}_id": "evt_spID",
        f"{species}_age": "evt_spAge",
        f"{species}_gsd": "evt_spGSD",
        f"{species}_sex": "evt_spSex",
        f"{species}_dire": "evt_spDire",
        f"{species}_dist": "evt_spDist",
        f"{species}_snar": "evt_spSnare",
        f"{species}_notes": "evt_spNotes",
        f"{species}_right": "evt_spRight",
        f"{species}_left": "evt_spLeft",
        f"{species}_gsd_loc": "evt_spGSD_loc",
        f"{species}_gsd_sev": "evt_spGSD_sev",
        "event_details.river_system": "evt_riverSystem",
    }

@st.cache_data(ttl=3600)
def load_species_data(event_type, since, until, event_category="monitoring_nanw"):
    """Fetch events of a given event_category for a given event_type and explode the Herd details."""
    er = EarthRangerIO(
        server=EARTHRANGER_SERVER,
        username=username,
        password=password
    )

    events = er.get_events(
        event_category=event_category,
        since=since,
        until=until,
        include_details=True,
        include_notes=False
    )
    flat = json_normalize(events.to_dict(orient="records"))

    if flat.empty or "event_type" not in flat.columns:
        return pd.DataFrame(), pd.DataFrame()

    species_only = flat[flat["event_type"] == event_type]

    if species_only.empty:
        return pd.DataFrame(), pd.DataFrame()

    # Keep herd-level data for accurate metrics calculation
    herd_level_data = species_only.copy()

    # Explode for individual analysis
    species_only = species_only.explode("event_details.Herd").reset_index(drop=True)
    herd_df = json_normalize(species_only["event_details.Herd"])
    events_final = pd.concat([species_only.drop(columns="event_details.Herd"), herd_df], axis=1)

    return events_final, herd_level_data

def prep_species_df(raw_df, species):
    if raw_df.empty:
        return pd.DataFrame()
    df = raw_df.rename(columns=build_rename_map(species))
    df["evt_dttm"] = pd.to_datetime(df["evt_dttm"], errors="coerce")
    df = df.dropna(subset=["evt_dttm"])
    return df

# Fetch a window that comfortably covers the last 3 years (used for the Total
# Population calc) regardless of which dates are picked in the filter below.
since_dt = datetime.today() - timedelta(days=3 * 365 + 2)
SINCE = since_dt.strftime("%Y-%m-%dT00:00:00Z")
UNTIL = "2030-12-31T23:59:59Z"

df_gir_raw, herd_gir_raw = load_species_data("giraffe_nw_monitoring", SINCE, UNTIL)
df_ele_raw, herd_ele_raw = load_species_data("elephant_nw_monitoring", SINCE, UNTIL)
df_ele_ns_raw, herd_ele_ns_raw = load_species_data(
    "elephant_nw_monitoring_ns", SINCE, UNTIL, event_category="monitoring_ns"
)

df_ele_raw = pd.concat([df_ele_raw, df_ele_ns_raw], ignore_index=True)
herd_ele_raw = pd.concat([herd_ele_raw, herd_ele_ns_raw], ignore_index=True)

df_gir = prep_species_df(df_gir_raw, "giraffe")
df_ele = prep_species_df(df_ele_raw, "elephant")

# Check if we have any giraffe data at all (giraffe is the primary dataset for this page)
if df_gir.empty or herd_gir_raw.empty:
    st.warning("⚠️ No monitoring data available for the selected date range. Please check back later or adjust your date range.")
    st.stop()


#### DASHBOARD LAYOUT ###############################################
#st.title("🦒 GCF Namibia NW monitoring")

# Date filter row (shared across both species tabs)
st.subheader("📅 Filter Date Range")
col_date_start, col_date_end = st.columns(2)

# Set min/max dates for date picker - allow broader range than just event dates
data_min_date = date(2020, 1, 1)  # Allow dates back to 2020
data_max_date = datetime.today().date()

# Set default dates: last 30 days
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

if start_date and end_date and start_date > end_date:
    st.error("⚠️ Start date must be before end date")
    st.stop()

def filter_by_date(df):
    if df.empty:
        return df
    df_dates = df["evt_dttm"].dt.tz_localize(None).dt.date if df["evt_dttm"].dt.tz is not None else df["evt_dttm"].dt.date
    return df[(df_dates >= start_date) & (df_dates <= end_date)]

filtered_gir = filter_by_date(df_gir)
filtered_ele = filter_by_date(df_ele)


#### MOVEMENT STATISTICS SECTION (giraffe only) #######################
def render_movement_statistics(id_to_name, start_date, end_date):
    st.subheader("📊 Movement Statistics")
    st.info("Calculate distance traveled and home ranges for tagged giraffes during the selected date range.")

    if st.button("🔄 Calculate Movement Statistics", use_container_width=True):
        with st.spinner("Fetching trajectory data and calculating statistics..."):
            try:
                import numpy as np
                from shapely.geometry import MultiPoint
                from scipy.spatial import ConvexHull

                er = EarthRangerIO(
                    server=EARTHRANGER_SERVER,
                    username=username,
                    password=password
                )

                hoanib_subject_ids = [s["id"] for s in hoanib_gps_subjects]
                subjects_to_process = hoanib_subject_ids

                st.info(f"Checking {len(subjects_to_process)} GPS-collared Hoanib giraffe(s) for observations...")

                since_str = datetime.combine(start_date, datetime.min.time()).isoformat() + "Z"
                until_str = datetime.combine(end_date, datetime.max.time()).isoformat() + "Z"

                movement_stats = []

                for subject_id in subjects_to_process:
                    try:
                        subject_name = id_to_name.get(subject_id, f"Unknown ({subject_id})")

                        try:
                            trajectories = er.get_subject_observations(
                                subject_ids=[subject_id],
                                since=since_str,
                                until=until_str
                            )
                        except Exception as api_error:
                            error_msg = str(api_error)
                            if "Expecting value" in error_msg or "JSON" in error_msg:
                                st.info(f"⏭️ Skipping {subject_name}: No GPS data available (empty API response)")
                            else:
                                st.warning(f"⚠️ API error for {subject_name}: {error_msg}")
                            continue

                        if trajectories is None:
                            st.info(f"⏭️ Skipping {subject_name}: No GPS data returned from API")
                            continue

                        gdf = trajectories

                        if gdf.empty:
                            st.info(f"⏭️ Skipping {subject_name}: No GPS observations in date range")
                            continue

                        n_obs = len(gdf)

                        if n_obs < 2:
                            st.info(f"⏭️ Skipping {subject_name}: Only {n_obs} GPS point(s) in date range (need at least 2)")
                            continue

                        gdf = gdf.sort_values('fixtime')

                        def haversine_distance(lat1, lon1, lat2, lon2):
                            """Calculate distance between two points in km"""
                            R = 6371  # Earth radius in km
                            lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
                            dlat = lat2 - lat1
                            dlon = lon2 - lon1
                            a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
                            c = 2 * np.arcsin(np.sqrt(a))
                            return R * c

                        lats = gdf.geometry.y.values
                        lons = gdf.geometry.x.values

                        distances = []
                        for i in range(n_obs - 1):
                            dist = haversine_distance(lats[i], lons[i], lats[i+1], lons[i+1])
                            distances.append(dist)

                        total_distance = sum(distances)

                        first_date = pd.to_datetime(gdf['fixtime'].min())
                        last_date = pd.to_datetime(gdf['fixtime'].max())
                        days_active = max(1, (last_date - first_date).days)

                        avg_km_per_day = total_distance / days_active

                        coords = np.column_stack([gdf.geometry.x.values, gdf.geometry.y.values])

                        if len(coords) < 3:
                            home_range_area = 0
                        else:
                            points = MultiPoint(coords)
                            centroid = points.centroid

                            distances_from_center = []
                            for coord in coords:
                                dist = haversine_distance(centroid.y, centroid.x, coord[1], coord[0])
                                distances_from_center.append((dist, coord))

                            distances_from_center.sort(key=lambda x: x[0])
                            n_points_95 = max(3, int(len(distances_from_center) * 0.95))
                            coords_95 = [coord for _, coord in distances_from_center[:n_points_95]]

                            if len(coords_95) >= 3:
                                try:
                                    hull = ConvexHull(coords_95)
                                    area_deg2 = hull.volume  # In 2D, volume is actually area
                                    home_range_area = area_deg2 * (111 * 111)  # Convert to km²
                                except Exception:
                                    home_range_area = 0
                            else:
                                home_range_area = 0

                        movement_stats.append({
                            'subject_id': subject_id,
                            'subject_name': subject_name,
                            'total_distance_km': total_distance,
                            'days_active': days_active,
                            'avg_km_per_day': avg_km_per_day,
                            'home_range_km2': home_range_area,
                            'n_observations': n_obs
                        })

                    except Exception as e:
                        st.warning(f"Could not process data for {subject_name}: {str(e)}")
                        continue

                if not movement_stats:
                    st.warning("No movement data available for the selected date range.")
                else:
                    stats_df = pd.DataFrame(movement_stats)

                    st.subheader("🏆 Movement Champions")

                    col_stat1, col_stat2 = st.columns(2)

                    with col_stat1:
                        st.markdown("**Distance Traveled**")
                        max_dist_row = stats_df.loc[stats_df['total_distance_km'].idxmax()]
                        min_dist_row = stats_df.loc[stats_df['total_distance_km'].idxmin()]

                        st.markdown(f"🥇 **Farthest Traveler:** {max_dist_row['subject_name']}")
                        st.info(f"**{max_dist_row['total_distance_km']:.2f} km** traveled over {int(max_dist_row['days_active'])} days")

                        st.markdown(f"🐌 **Shortest Distance:** {min_dist_row['subject_name']}")
                        st.info(f"**{min_dist_row['total_distance_km']:.2f} km** traveled over {int(min_dist_row['days_active'])} days")

                    with col_stat2:
                        st.markdown("**Home Range Size (95% MCP)**")
                        max_hr_row = stats_df.loc[stats_df['home_range_km2'].idxmax()]
                        min_hr_row = stats_df.loc[stats_df['home_range_km2'].idxmin()]

                        st.markdown(f"🏔️ **Largest Home Range:** {max_hr_row['subject_name']}")
                        st.info(f"**{max_hr_row['home_range_km2']:.2f} km²** from {int(max_hr_row['n_observations'])} GPS points")

                        st.markdown(f"🏠 **Smallest Home Range:** {min_hr_row['subject_name']}")
                        st.info(f"**{min_hr_row['home_range_km2']:.2f} km²** from {int(min_hr_row['n_observations'])} GPS points")

                    st.markdown("---")
                    st.subheader("📈 Average Statistics (All Active Subjects)")

                    col_avg1, col_avg2, col_avg3 = st.columns(3)

                    with col_avg1:
                        avg_distance = stats_df['total_distance_km'].mean()
                        st.metric("Avg Total Distance", f"{avg_distance:.2f} km")

                    with col_avg2:
                        avg_daily = stats_df['avg_km_per_day'].mean()
                        st.metric("Avg Distance per Day", f"{avg_daily:.2f} km/day")

                    with col_avg3:
                        avg_home_range = stats_df['home_range_km2'].mean()
                        st.metric("Avg Home Range", f"{avg_home_range:.2f} km²")

                    st.markdown("---")
                    st.subheader("📋 Detailed Movement Statistics")

                    display_stats = stats_df.copy()
                    display_stats = display_stats.sort_values('total_distance_km', ascending=False)
                    display_stats['total_distance_km'] = display_stats['total_distance_km'].round(2)
                    display_stats['avg_km_per_day'] = display_stats['avg_km_per_day'].round(2)
                    display_stats['home_range_km2'] = display_stats['home_range_km2'].round(2)

                    display_stats = display_stats[[
                        'subject_name', 'total_distance_km', 'avg_km_per_day',
                        'home_range_km2', 'days_active', 'n_observations'
                    ]]
                    display_stats.columns = [
                        'Giraffe Name', 'Total Distance (km)', 'Avg km/day',
                        'Home Range (km²)', 'Days Active', 'GPS Observations'
                    ]

                    st.dataframe(display_stats, use_container_width=True)

            except ImportError as e:
                st.error(f"Missing required package: {str(e)}")
                st.info("Please ensure you have the required packages installed: numpy, shapely, scipy")
            except Exception as e:
                import traceback
                st.error(f"Error calculating movement statistics: {str(e)}")
                with st.expander("🔍 Show detailed error"):
                    st.code(traceback.format_exc())
                st.info("If the error persists, try adjusting the date range or check your EarthRanger connection.")


#### SHARED SPECIES TAB RENDERER ######################################
def render_species_tab(
    species_label,
    emoji,
    full_df,
    filtered_df,
    herd_level_raw,
    active_subjects,
    start_date,
    end_date,
    show_individual_list=True,
    show_aag=False,
    show_movement=False,
    marker_color="red",
    color_by_event_type=False,
    event_type_colors=None,
):
    if full_df.empty:
        st.info(f"No {species_label.lower()} monitoring data available yet.")
        return

    st.caption(f"Showing {len(filtered_df)} sightings from {start_date} to {end_date}")
    st.markdown("---")

    active_ids = {s["id"] for s in active_subjects if "id" in s}
    id_to_name = {s["id"]: s["name"] for s in active_subjects if "id" in s and "name" in s}

    #### heading metrics
    # Total population = active subjects seen at least once in the last 3 years
    # (independent of the date range selected above)
    three_years_ago = date.today() - timedelta(days=3 * 365)
    seen_recently_ids = set(
        full_df.loc[full_df["evt_dttm"].dt.date >= three_years_ago, "evt_spID"].dropna().unique()
    )
    total_population = len(active_ids & seen_recently_ids)

    distinct_individuals_seen = filtered_df["evt_spID"].nunique()
    percentage_seen = (distinct_individuals_seen / total_population * 100) if total_population > 0 else 0

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Population", total_population)
    with col2:
        st.metric("Individuals Seen", distinct_individuals_seen)
    with col3:
        st.metric("% Population Seen", f"{math.ceil(percentage_seen)}%")
    with col4:
        herd_df_for_metrics = herd_level_raw.copy()
        herd_df_for_metrics["evt_dttm"] = pd.to_datetime(herd_df_for_metrics["time"], errors="coerce")
        herd_df_for_metrics = herd_df_for_metrics.dropna(subset=["evt_dttm"])
        herd_df_for_metrics = herd_df_for_metrics[
            (herd_df_for_metrics["evt_dttm"].dt.date >= start_date) &
            (herd_df_for_metrics["evt_dttm"].dt.date <= end_date)
        ]
        herd_count = len(herd_df_for_metrics)
        st.metric("Herds Seen", herd_count)
    with col5:
        herd_df_for_metrics = herd_df_for_metrics.rename(columns={"event_details.herd_size": "evt_herdSize"})
        avg_herd_size = herd_df_for_metrics["evt_herdSize"].mean() if "evt_herdSize" in herd_df_for_metrics.columns else filtered_df["evt_herdSize"].mean()
        st.metric("Avg Herd Size", f"{avg_herd_size:.1f}" if not pd.isna(avg_herd_size) else "N/A")

    #### Sighting map
    st.subheader("📍 Sightings map")
    map_df = filtered_df.dropna(subset=["lat", "lon"])
    if not map_df.empty:
        if MAPBOX_TOKEN:
            map_style = "satellite-streets"
            px.set_mapbox_access_token(MAPBOX_TOKEN)
        else:
            map_style = "open-street-map"

        use_event_type_color = color_by_event_type and "evt_type" in map_df.columns

        map_kwargs = dict(
            lat="lat",
            lon="lon",
            hover_data=["evt_dttm", "evt_herdSize"] if "evt_herdSize" in map_df.columns else ["evt_dttm"],
            zoom=8,
            height=500,
            title=f"{species_label} Sightings"
        )
        if use_event_type_color:
            map_kwargs["color"] = "evt_type"
            if event_type_colors:
                map_kwargs["color_discrete_map"] = event_type_colors

        fig_map = px.scatter_mapbox(map_df, **map_kwargs)

        fig_map.update_layout(
            mapbox_style=map_style,
            mapbox=dict(
                center=dict(lat=map_df["lat"].mean(), lon=map_df["lon"].mean()),
                zoom=8
            ),
            margin={"r": 0, "t": 50, "l": 0, "b": 0},
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)"
        )

        if use_event_type_color:
            fig_map.update_traces(marker=dict(size=12, opacity=0.8))
        else:
            fig_map.update_traces(marker=dict(size=12, color=marker_color, opacity=0.8))

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
        filtered_df.groupby(["evt_spSex", "evt_spAge"])
        .size()
        .reset_index(name="Count")
    )
    fig2 = px.bar(breakdown, x="evt_spAge", y="Count", color="evt_spSex", barmode="group")
    st.plotly_chart(fig2, use_container_width=True)

    #### Full event details table (all exploded event records, every field)
    st.subheader("📋 Event details")
    details_df = filtered_df.copy()
    details_df["subject_name"] = details_df["evt_spID"].map(id_to_name)
    detail_cols = {
        "evt_dttm": "Date/Time",
        "subject_name": f"{species_label} Name",
        "evt_spID": f"{species_label} ID",
        "evt_spAge": "Age",
        "evt_spSex": "Sex",
        "evt_spGSD": "GSD",
        "evt_spGSD_loc": "GSD Location",
        "evt_spGSD_sev": "GSD Severity",
        "evt_spDire": "Direction",
        "evt_spDist": "Distance",
        "evt_spSnare": "Snare",
        "evt_spNotes": "Notes",
        "evt_spRight": "Right Side Photo",
        "evt_spLeft": "Left Side Photo",
        "evt_herdSize": "Herd Size",
        "evt_herdNotes": "Herd Notes",
        "evt_herd_dir": "Herd Direction",
        "evt_herd_dist": "Herd Distance",
        "evt_riverSystem": "River System",
        "evt_imagePrefix": "Image Prefix",
        "lat": "Latitude",
        "lon": "Longitude",
        "user_name": "Recorded By",
        "evt_serial": "Serial Number",
    }
    available_detail_cols = [c for c in detail_cols if c in details_df.columns]
    display_details_df = (
        details_df[available_detail_cols]
        .rename(columns=detail_cols)
        .sort_values("Date/Time", ascending=False)
        .reset_index(drop=True)
    )
    st.dataframe(display_details_df, use_container_width=True)

    #### Table of names seen
    if show_individual_list:
        st.subheader(f"{emoji} List of {species_label.lower()} seen")
        named_df = filtered_df.copy()
        named_df["subject_name"] = named_df["evt_spID"].map(id_to_name)
        name_table = (
            named_df[["evt_spID", "subject_name"]]
            .drop_duplicates()
            .sort_values("subject_name")
            .reset_index(drop=True)
        )
        st.dataframe(name_table[["subject_name"]].drop_duplicates().sort_values("subject_name").reset_index(drop=True), use_container_width=True)

    #### Table of Adopt A Giraffe giraffe seen (giraffe only)
    if show_aag:
        aag_seen = filtered_df[filtered_df["evt_spID"].isin(aag_ids)].copy()
        aag_seen["giraffe_name"] = aag_seen["evt_spID"].map(aag_id_to_name)
        aag_table = (
            aag_seen[["evt_spID", "giraffe_name"]]
            .drop_duplicates()
            .sort_values("giraffe_name")
            .reset_index(drop=True)
        )
        st.subheader("🦒 List of AAG giraffe seen")
        if not aag_table.empty:
            st.dataframe(aag_table[["giraffe_name"]].drop_duplicates().sort_values("giraffe_name").reset_index(drop=True), use_container_width=True)
        else:
            st.info("No AAG giraffes seen in the selected data.")

    st.markdown("---")

    #### Movement statistics (giraffe only)
    if show_movement:
        render_movement_statistics(id_to_name, start_date, end_date)


#### TABS ##############################################################
tab_giraffe, tab_elephant = st.tabs(["🦒 Giraffe", "🐘 Elephants"])

with tab_giraffe:
    render_species_tab(
        species_label="Giraffe",
        emoji="🦒",
        full_df=df_gir,
        filtered_df=filtered_gir,
        herd_level_raw=herd_gir_raw,
        active_subjects=active_giraffe_subjects,
        start_date=start_date,
        end_date=end_date,
        show_individual_list=True,
        show_aag=True,
        show_movement=True,
        marker_color="#DB580F",
    )

with tab_elephant:
    render_species_tab(
        species_label="Elephant",
        emoji="🐘",
        full_df=df_ele,
        filtered_df=filtered_ele,
        herd_level_raw=herd_ele_raw,
        active_subjects=active_elephant_subjects,
        start_date=start_date,
        end_date=end_date,
        show_individual_list=False,
        show_aag=False,
        show_movement=False,
        marker_color="#4A4A4A",
        color_by_event_type=True,
        event_type_colors={
            "elephant_nw_monitoring": "#4A4A4A",
            "elephant_nw_monitoring_ns": "#2E86DE",
        },
    )
