"""
Survey Dashboard (ZMB) — Zambia Luangwa giraffe survey summary + subject movement map.

Tab 1: giraffe_survey_monitoring_zmb event summary (monitoring_zmb category)
Tab 2: Subject movement tracks for ZMB_Luangwa_giraffe subject group
"""

import streamlit as st
import pandas as pd
import math
import plotly.express as px
import plotly.graph_objects as go
import folium
import streamlit.components.v1 as components
from datetime import datetime, timedelta, date
from pandas import json_normalize
from ecoscope.io.earthranger import EarthRangerIO

ER_SERVER = "https://twiga.pamdas.org"
SUBJECT_GROUP = "ZMB_Luangwa_giraffe"

# Colour palette for subject tracks (cycles if >12 subjects)
TRACK_COLOURS = [
    "#DB580F", "#1f77b4", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
    "#ff7f0e", "#aec7e8",
]


# ─── Auth ─────────────────────────────────────────────────────────────────────

def _er_login(username: str, password: str) -> bool:
    try:
        er = EarthRangerIO(server=ER_SERVER, username=username, password=password)
        er.get_subjects(limit=1)
        return True
    except Exception:
        return False


def _get_er(username: str, password: str) -> EarthRangerIO:
    return EarthRangerIO(server=ER_SERVER, username=username, password=password)


# ─── Data fetches ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def load_survey_events(er_username: str, er_password: str,
                       since_str: str, until_str: str) -> pd.DataFrame:
    """Fetch giraffe_survey_monitoring_zmb events and flatten to one row per event."""
    er = _get_er(er_username, er_password)
    try:
        gdf = er.get_events(
            event_category="monitoring_zmb",
            since=since_str,
            until=until_str,
            include_details=True,
            drop_null_geometry=False,
        )
    except Exception as exc:
        st.error(f"❌ Error fetching survey events: {exc}")
        return pd.DataFrame()

    if gdf is None or gdf.empty:
        return pd.DataFrame()

    # Keep the three ZMB giraffe event types
    _ZMB_TYPES = {
        "giraffe_survey_encounter_zmb",
        "giraffe_random_encounter_zmb",
        "giraffe_survey_monitoring_zmb",
    }
    if "event_type" in gdf.columns:
        gdf = gdf[gdf["event_type"].isin(_ZMB_TYPES)]

    if gdf.empty:
        return pd.DataFrame()

    flat = json_normalize(gdf.reset_index(drop=True).to_dict(orient="records"))
    return flat


@st.cache_data(ttl=1800, show_spinner=False)
def load_subject_tracks(er_username: str, er_password: str,
                        since_str: str, until_str: str):
    """
    Fetch all subjects in SUBJECT_GROUP and their relocations in [since, until].
    Returns a dict {subject_name: GeoDataFrame-of-points} sorted by time.
    """
    er = _get_er(er_username, er_password)

    # Get subjects in the group
    try:
        subjects_gdf = er.get_subjects(subject_group_name=SUBJECT_GROUP, include_inactive=True)
    except Exception as exc:
        return {}, f"Could not fetch subjects: {exc}"

    if subjects_gdf is None or subjects_gdf.empty:
        return {}, f"No subjects found in group '{SUBJECT_GROUP}'"

    tracks = {}
    errors = []

    for _, subj in subjects_gdf.iterrows():
        subj_id   = str(subj.get("id", ""))
        subj_name = str(subj.get("name", subj_id))
        if not subj_id:
            continue
        try:
            result = er.get_subject_observations(
                subject_ids=[subj_id],
                since=since_str,
                until=until_str,
                include_source_details=False,
            )
            # ecoscope returns a Relocations object — extract the GeoDataFrame
            if hasattr(result, "gdf"):
                obs = result.gdf
            else:
                obs = result
            if obs is not None and len(obs) > 0:
                tracks[subj_name] = obs
        except Exception as exc:
            errors.append(f"{subj_name}: {exc}")

    err_msg = "; ".join(errors) if errors else None
    return tracks, err_msg


# ─── Helpers ──────────────────────────────────────────────────────────────────

_SURVEY_COLOURS = {
    "giraffe_survey_encounter_zmb":   "#DB580F",   # orange
    "giraffe_random_encounter_zmb":   "#888888",   # grey
    "giraffe_survey_monitoring_zmb":  "#888888",   # grey
}
_SURVEY_LABELS = {
    "giraffe_survey_encounter_zmb":  "Survey encounter",
    "giraffe_random_encounter_zmb":  "Random encounter",
    "giraffe_survey_monitoring_zmb": "Monitoring encounter",
}


def _survey_map(map_df: pd.DataFrame, event_type_col) -> go.Figure:
    """Return a Plotly figure for survey sighting points, coloured by event type."""
    lats = map_df["lat"].tolist()
    lons = map_df["lon"].tolist()

    lat_span = max(lats) - min(lats)
    lon_span = max(lons) - min(lons)
    max_span = max(lat_span, lon_span, 0.001)
    zoom = max(1, math.floor(math.log2(180 / max_span)) + 1)

    fig = go.Figure()

    # Group by event type so each gets its own legend entry
    etypes = (
        map_df[event_type_col].fillna("unknown").unique().tolist()
        if event_type_col and event_type_col in map_df.columns
        else ["unknown"]
    )

    for etype in sorted(etypes):
        colour = _SURVEY_COLOURS.get(str(etype), "#888888")
        label  = _SURVEY_LABELS.get(str(etype), etype)
        subset = map_df[map_df[event_type_col] == etype] if event_type_col else map_df

        fig.add_trace(go.Scattermapbox(
            lat=subset["lat"].tolist(),
            lon=subset["lon"].tolist(),
            mode="markers",
            marker=dict(color=colour, size=10, opacity=0.85),
            name=label,
            text=[
                (
                    f"<b>{label}</b><br>"
                    f"Serial: {row.get('serial_number', '—')}<br>"
                    f"Date/Time: {str(row.get('time', ''))[:19]}<br>"
                    f"Observer: {row.get('reported_by.name', '—')}<br>"
                    f"Herd size: {row.get('event_details.herd_size', '—')}<br>"
                    f"River system: {row.get('event_details.river_system', '—')}<br>"
                    f"Lat: {row['lat']:.6f}  Lon: {row['lon']:.6f}"
                )
                for _, row in subset.iterrows()
            ],
            hovertemplate="%{text}<extra></extra>",
        ))

    fig.update_layout(
        mapbox=dict(
            style="white-bg",
            center=dict(lat=(min(lats) + max(lats)) / 2,
                        lon=(min(lons) + max(lons)) / 2),
            zoom=zoom,
            layers=[dict(
                below="traces",
                sourcetype="raster",
                source=[
                    "https://services.arcgisonline.com/arcgis/rest/services/"
                    "World_Topo_Map/MapServer/tile/{z}/{y}/{x}"
                ],
            )],
        ),
        margin=dict(l=0, r=0, t=30, b=0),
        legend=dict(
            bgcolor="rgba(255,255,255,0.88)",
            bordercolor="#ccc",
            borderwidth=1,
            title=dict(text="Event type", font=dict(size=10)),
            x=0.01,
            xanchor="left",
            y=0.99,
            yanchor="top",
            font=dict(size=9),
        ),
        height=500,
    )
    return fig


def _movement_map(tracks: dict) -> go.Figure | None:
    """Return a Plotly figure with one coloured line per subject (has built-in PNG toolbar)."""
    all_lats, all_lons = [], []

    # Pre-extract coords for centering
    for obs in tracks.values():
        if "geometry" in obs.columns:
            all_lats += [g.y for g in obs.geometry if g is not None]
            all_lons += [g.x for g in obs.geometry if g is not None]
        elif "latitude" in obs.columns:
            all_lats += obs["latitude"].dropna().tolist()
            all_lons += obs["longitude"].dropna().tolist()

    if not all_lats:
        return None

    fig = go.Figure()

    for idx, (name, obs) in enumerate(sorted(tracks.items())):
        colour = TRACK_COLOURS[idx % len(TRACK_COLOURS)]
        label = name.rsplit("_", 1)[-1]

        # Extract coords
        if "geometry" in obs.columns:
            obs = obs.copy()
            obs["_lon"] = obs.geometry.apply(lambda g: g.x if g else None)
            obs["_lat"] = obs.geometry.apply(lambda g: g.y if g else None)
        elif "longitude" in obs.columns:
            obs = obs.copy().rename(columns={"longitude": "_lon", "latitude": "_lat"})
        else:
            continue

        # Sort by time
        time_col = next((c for c in ["recorded_at", "fixtime", "time", "timestamp"]
                         if c in obs.columns), None)
        if time_col:
            obs = obs.sort_values(time_col)

        obs = obs.dropna(subset=["_lat", "_lon"])
        if obs.empty:
            continue

        lats = obs["_lat"].tolist()
        lons = obs["_lon"].tolist()

        # Track line
        fig.add_trace(go.Scattermapbox(
            lat=lats, lon=lons,
            mode="lines",
            line=dict(color=colour, width=2.5),
            name=label,
            showlegend=True,
        ))

        # Start dot
        fig.add_trace(go.Scattermapbox(
            lat=[lats[0]], lon=[lons[0]],
            mode="markers",
            marker=dict(color=colour, size=8),
            name=label,
            showlegend=False,
        ))

    # Fit zoom to bounding box
    lat_span = max(all_lats) - min(all_lats)
    lon_span = max(all_lons) - min(all_lons)
    max_span = max(lat_span, lon_span, 0.001)
    zoom = max(1, math.floor(math.log2(180 / max_span)) + 1)

    # Taller map to suit tall/thin study areas; extra right margin for legend
    map_height = max(600, min(900, int(lat_span / lon_span * 500))) if lon_span > 0 else 700

    fig.update_layout(
        mapbox=dict(
            style="white-bg",
            center=dict(lat=(min(all_lats) + max(all_lats)) / 2,
                        lon=(min(all_lons) + max(all_lons)) / 2),
            zoom=zoom,
            layers=[dict(
                below="traces",
                sourcetype="raster",
                source=[
                    "https://services.arcgisonline.com/arcgis/rest/services/"
                    "World_Topo_Map/MapServer/tile/{z}/{y}/{x}"
                ],
            )],
        ),
        margin=dict(l=0, r=0, t=30, b=0),
        legend=dict(
            bgcolor="rgba(255,255,255,0.88)",
            bordercolor="#ccc",
            borderwidth=1,
            title=dict(text="Subjects", font=dict(size=10)),
            x=0.01,
            xanchor="left",
            y=0.99,
            yanchor="top",
            font=dict(size=9),
            entrywidth=15,
            entrywidthmode="pixels",
        ),
        height=map_height,
    )
    return fig


def _html_legend_survey(present_types: list) -> str:
    """Return an HTML legend string for the survey map event types."""
    rows = "".join(
        f"<div style='display:flex;align-items:center;gap:8px;margin-bottom:4px'>"
        f"<div style='width:12px;height:12px;border-radius:50%;background:{_SURVEY_COLOURS.get(et,'#888')};flex-shrink:0'></div>"
        f"<span>{_SURVEY_LABELS.get(et, et)}</span></div>"
        for et in sorted(present_types)
    )
    return (
        "<div style='font-family:sans-serif;font-size:12px;"
        "background:rgba(255,255,255,0.95);border:1px solid #ccc;"
        "border-radius:6px;padding:8px 12px;display:inline-block'>"
        "<b style='font-size:13px'>Event type</b><br/><br/>"
        + rows + "</div>"
    )


def _html_legend_tracks(track_names: list) -> str:
    """Return an HTML legend string for the movement map subjects."""
    rows = "".join(
        f"<div style='display:flex;align-items:center;gap:8px;margin-bottom:4px'>"
        f"<div style='width:24px;height:3px;background:{TRACK_COLOURS[i % len(TRACK_COLOURS)]};flex-shrink:0'></div>"
        f"<span style='white-space:nowrap'>{name}</span></div>"
        for i, name in enumerate(sorted(track_names))
    )
    return (
        "<div style='font-family:sans-serif;font-size:12px;"
        "background:rgba(255,255,255,0.95);border:1px solid #ccc;"
        "border-radius:6px;padding:8px 12px;display:inline-block'>"
        "<b style='font-size:13px'>Subjects</b><br/><br/>"
        + rows + "</div>"
    )


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    # ── Login ─────────────────────────────────────────────────────────────────
    for k, v in [("zmb_auth", False), ("zmb_user", ""), ("zmb_pass", "")]:
        if k not in st.session_state:
            st.session_state[k] = v

    if not st.session_state.zmb_auth:
        st.title("🦒 Survey Dashboard (ZMB) — Login")
        u = st.text_input("EarthRanger username")
        p = st.text_input("EarthRanger password", type="password")
        if st.button("Login", type="primary"):
            with st.spinner("Connecting…"):
                if _er_login(u, p):
                    st.session_state.zmb_auth = True
                    st.session_state.zmb_user = u
                    st.session_state.zmb_pass = p
                    st.rerun()
                else:
                    st.error("❌ Invalid credentials.")
        st.stop()

    username = st.session_state.zmb_user
    password = st.session_state.zmb_pass

    # ── Date filter (shared across tabs) ──────────────────────────────────────
    st.subheader("📅 Date range")
    dc1, dc2 = st.columns(2)
    with dc1:
        date_start = st.date_input("Start date",
                                   value=date.today() - timedelta(days=30),
                                   key="zmb_date_start")
    with dc2:
        date_end = st.date_input("End date", value=date.today(), key="zmb_date_end")

    since_str = date_start.strftime("%Y-%m-%dT00:00:00Z")
    until_str = date_end.strftime("%Y-%m-%dT23:59:59Z")

    st.markdown("---")

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab_survey, tab_movement = st.tabs(["🦒 Survey summary", "📍 Subject movement"])

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 1 — Survey summary
    # ══════════════════════════════════════════════════════════════════════════
    with tab_survey:
        if st.button("Load survey data", type="primary", key="zmb_load_survey"):
            load_survey_events.clear()

        with st.spinner("Loading survey events…"):
            df = load_survey_events(username, password, since_str, until_str)

        if df.empty:
            st.warning("No giraffe survey encounters found for this date range.")
            st.stop()

        # Parse time
        time_col = next((c for c in ["time", "created_at"] if c in df.columns), None)
        if time_col:
            df[time_col] = pd.to_datetime(df[time_col], errors="coerce", utc=True)
            df = df.dropna(subset=[time_col])

        # Lat / lon
        lat_col = next((c for c in ["location.latitude", "lat"] if c in df.columns), None)
        lon_col = next((c for c in ["location.longitude", "lon"] if c in df.columns), None)
        if lat_col:
            df = df.rename(columns={lat_col: "lat", lon_col: "lon"})

        herd_size_col = next(
            (c for c in ["event_details.herd_size", "event_details_herd_size"]
             if c in df.columns), None)

        # ── Metrics ───────────────────────────────────────────────────────────
        n_enc  = df["serial_number"].nunique() if "serial_number" in df.columns else len(df)
        n_ind  = int(df[herd_size_col].sum()) if herd_size_col else 0
        avg_hs = df[herd_size_col].mean() if herd_size_col else None

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Encounters",       n_enc)
        m2.metric("Individuals seen", n_ind)
        m3.metric("Avg herd size",    f"{avg_hs:.1f}" if avg_hs else "—")
        m4.metric("Days",             (date_end - date_start).days)

        # ── Sightings map ─────────────────────────────────────────────────────
        st.subheader("📍 Sightings map")
        map_df = df.dropna(subset=["lat", "lon"]) if "lat" in df.columns else pd.DataFrame()
        if not map_df.empty:
            _et_col = "event_type" if "event_type" in map_df.columns else None
            st.plotly_chart(_survey_map(map_df, _et_col), use_container_width=True,
                            config={"toImageButtonOptions": {"format": "png", "width": 1600, "height": 900, "scale": 2}})
        else:
            st.info("No coordinates available for mapping.")

        # ── Sightings table ───────────────────────────────────────────────────
        st.subheader("📋 Sightings table")
        display_cols = {
            time_col:                           "Date/Time (UTC)",
            "reported_by.name":                 "Observer",
            "serial_number":                    "Serial #",
            "event_details.herd_size":          "Herd size",
            "event_details.river_system":       "River system",
            "event_details.herd_dire":          "Direction (°)",
            "event_details.herd_dist":          "Distance (m)",
            "event_details.herd_notes":         "Herd notes",
            "event_details.image_prefix":       "Image prefix",
            "lat":                              "Lat",
            "lon":                              "Lon",
        }
        avail = {k: v for k, v in display_cols.items() if k in df.columns}
        tbl = df[list(avail.keys())].rename(columns=avail).copy()
        if "Date/Time (UTC)" in tbl.columns:
            tbl["Date/Time (UTC)"] = tbl["Date/Time (UTC)"].dt.strftime("%Y-%m-%d %H:%M")
        tbl = tbl.sort_values("Date/Time (UTC)", ascending=False) \
            if "Date/Time (UTC)" in tbl.columns else tbl
        st.dataframe(tbl, use_container_width=True, hide_index=True)

        # ── Age / sex breakdown ───────────────────────────────────────────────
        st.subheader("🧬 Age / sex breakdown")

        herd_col = next(
            (c for c in ["event_details.Herd", "event_details_Herd"] if c in df.columns), None)

        if herd_col:
            ind_df = df.explode(herd_col).reset_index(drop=True)
            herd_details = json_normalize(
                ind_df[herd_col].dropna().tolist()
            )
            if not herd_details.empty and \
                    "giraffe_sex" in herd_details.columns and \
                    "giraffe_age" in herd_details.columns:
                age_map = {"ad": "Adult", "sa": "Subadult", "ju": "Juvenile",
                           "ca": "Calf", "u": "Unknown"}
                sex_map = {"f": "Female", "m": "Male", "u": "Unknown"}
                herd_details["Age"]  = herd_details["giraffe_age"].map(age_map).fillna(herd_details["giraffe_age"])
                herd_details["Sex"]  = herd_details["giraffe_sex"].map(sex_map).fillna(herd_details["giraffe_sex"])
                breakdown = (herd_details.groupby(["Age", "Sex"])
                             .size().reset_index(name="Count"))
                fig = px.bar(breakdown, x="Age", y="Count", color="Sex",
                             barmode="group",
                             category_orders={"Age": ["Adult", "Subadult", "Juvenile", "Calf", "Unknown"]},
                             color_discrete_map={"Female": "#DB580F", "Male": "#1f77b4", "Unknown": "#aaa"})
                st.plotly_chart(fig, use_container_width=True,
                                    config={"toImageButtonOptions": {"format": "png", "width": 1800, "height": 1200, "scale": 2}})
            else:
                st.info("No individual age/sex data found in herd details.")
        else:
            st.info("No herd details column found in event data.")

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2 — Subject movement
    # ══════════════════════════════════════════════════════════════════════════
    with tab_movement:
        st.markdown(f"Tracks for subjects in **{SUBJECT_GROUP}** over the selected date range.")

        if st.button("Load movement data", type="primary", key="zmb_load_movement"):
            load_subject_tracks.clear()

        with st.spinner(f"Fetching subject tracks from {SUBJECT_GROUP}…"):
            tracks, err_msg = load_subject_tracks(username, password, since_str, until_str)

        if err_msg:
            st.warning(f"⚠️ Some subjects could not be loaded: {err_msg}")

        if not tracks:
            st.info("No movement data found for this date range.")
        else:
            n_subj   = len(tracks)
            n_fixes  = sum(len(v) for v in tracks.values())
            s1, s2 = st.columns(2)
            s1.metric("Subjects with fixes", n_subj)
            s2.metric("Total GPS fixes",     n_fixes)

            # Subject selector (multiselect, default all)
            all_names = sorted(tracks.keys())
            selected  = st.multiselect(
                "Show subjects", all_names, default=all_names, key="zmb_subj_sel")
            filtered_tracks = {k: v for k, v in tracks.items() if k in selected}

            if filtered_tracks:
                fig = _movement_map(filtered_tracks)
                if fig is not None:
                    st.plotly_chart(fig, use_container_width=True,
                                    config={"toImageButtonOptions": {"format": "png", "width": 1800, "height": 1200, "scale": 2}})
                else:
                    st.info("No coordinate data to map for selected subjects.")

                # Debug: fix counts per subject
                with st.expander("🔍 GPS fix counts per subject"):
                    fix_counts = [
                        {"Subject": n, "Fixes in period": len(v)}
                        for n, v in sorted(filtered_tracks.items())
                    ]
                    st.dataframe(pd.DataFrame(fix_counts),
                                 use_container_width=True, hide_index=True)
                    st.caption("Subjects need ≥ 2 fixes in the period to draw a track line.")

                # Summary table — last fix per subject
                st.subheader("Last fix per subject")
                rows = []
                for name, obs in sorted(filtered_tracks.items()):
                    time_col_obs = next(
                        (c for c in ["recorded_at", "fixtime", "time", "timestamp"]
                         if c in obs.columns), None)
                    if time_col_obs:
                        latest = obs.sort_values(time_col_obs).iloc[-1]
                        if "geometry" in obs.columns:
                            lon_v = latest.geometry.x if latest.geometry else None
                            lat_v = latest.geometry.y if latest.geometry else None
                        else:
                            lon_v = latest.get("longitude") or latest.get("_lon")
                            lat_v = latest.get("latitude")  or latest.get("_lat")
                        rows.append({
                            "Subject":    name,
                            "Last fix":   str(latest[time_col_obs])[:19],
                            "Lat":        round(lat_v, 6) if lat_v else None,
                            "Lon":        round(lon_v, 6) if lon_v else None,
                            "Fixes in period": len(obs),
                        })
                if rows:
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            else:
                st.info("No subjects selected.")

    # ── Logout ────────────────────────────────────────────────────────────────
    if st.sidebar.button("🔓 Logout", key="zmb_logout"):
        for k in ["zmb_auth", "zmb_user", "zmb_pass"]:
            st.session_state.pop(k, None)
        st.rerun()


if __name__ == "__main__":
    main()
