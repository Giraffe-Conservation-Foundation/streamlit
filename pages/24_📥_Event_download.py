"""
Event Download Page
Export flattened EarthRanger events by event type and date range.
Ported from the open-source ERpatrolExport app (Marneweck, CJ 2026).
"""

import re as _re

import geopandas as gpd
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
from ecoscope.io.earthranger import EarthRangerIO
from shapely.geometry import shape

# ── Session state ──────────────────────────────────────────────────────────────
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "er_io" not in st.session_state:
    st.session_state.er_io = None

# ── Helpers ────────────────────────────────────────────────────────────────────

def authenticate_earthranger(server: str, username: str, password: str):
    """Return (EarthRangerIO, error_str) — error_str is None on success."""
    try:
        er_io = EarthRangerIO(server=server, username=username, password=password)
        return er_io, None
    except Exception as exc:
        return None, str(exc)


def build_entity_lookup(er_io) -> dict:
    """Return {uuid: display_name} covering subjects, sources (GPS units), and users."""
    lookup = {}

    # Subjects (collared animals)
    try:
        df = er_io.get_subjects(include_inactive=True)
        if df is not None and not df.empty and "id" in df.columns and "name" in df.columns:
            lookup.update(zip(df["id"].astype(str), df["name"].astype(str)))
    except Exception:
        pass

    # Sources (GPS units / devices)
    try:
        df = er_io.get_sources()
        if df is not None and not df.empty and "id" in df.columns:
            # Prefer 'manufacturer_id' as the human-readable label, fall back to 'model'
            label_col = next(
                (c for c in ["manufacturer_id", "model", "provider_key"] if c in df.columns), None
            )
            if label_col:
                lookup.update(zip(df["id"].astype(str), df[label_col].astype(str)))
    except Exception:
        pass

    # Users / reporters
    try:
        df = er_io.get_users()
        if df is not None and not df.empty and "id" in df.columns:
            label_col = next(
                (c for c in ["name", "username", "display_name"] if c in df.columns), None
            )
            if label_col:
                lookup.update(zip(df["id"].astype(str), df[label_col].astype(str)))
    except Exception:
        pass

    return lookup


_UUID_RE = _re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", _re.I
)


def resolve_uuid_columns(df: pd.DataFrame, uuid_to_name: dict, col_prefix: str = "detail_") -> pd.DataFrame:
    """
    For each column whose values look mostly like UUIDs, insert a companion
    '<col>_name' column immediately after it with resolved display names.
    Only adds the name column when at least one value resolves successfully.
    """
    if not uuid_to_name:
        return df

    def _is_uuid(val):
        return isinstance(val, str) and bool(_UUID_RE.match(val.strip()))

    inserts = []
    for i, col in enumerate(df.columns):
        if col.endswith("_name") or not col.startswith(col_prefix):
            continue
        sample = df[col].dropna()
        if sample.empty:
            continue
        if sample.apply(_is_uuid).mean() >= 0.5:
            name_series = df[col].apply(
                lambda v: uuid_to_name.get(str(v).strip(), "") if isinstance(v, str) else ""
            )
            if name_series.str.len().sum() > 0:
                inserts.append((i + 1, col + "_name", name_series))

    result = df.copy()
    for offset, (pos, name_col, series) in enumerate(inserts):
        if name_col not in result.columns:
            result.insert(pos + offset, name_col, series.values)
    return result


def extract_geometry(row):
    """Pull a Shapely geometry from a geojson dict field."""
    geojson = row.get("geojson")
    if geojson and isinstance(geojson, dict):
        try:
            return shape(geojson)
        except Exception:
            pass
    return None


def extract_datetime_from_geojson(geojson):
    """Extract datetime string from geojson.properties.datetime."""
    if isinstance(geojson, dict):
        props = geojson.get("properties", {})
        if isinstance(props, dict) and props.get("datetime"):
            try:
                return pd.to_datetime(props["datetime"], utc=True)
            except Exception:
                pass
    return None


_COLS_STRIP = [
    "level_8", "index", "location", "reported_by", "event_details",
    "geojson", "attributes", "notes", "patrols", "patrol_segments",
    "is_contained_in", "related_subjects", "location_lat", "location_lon",
    "message", "provenance", "event_category", "priority_label", "comment",
    "end_time", "sort_at", "icon_id", "url", "image_url", "external_source",
]

_PREFERRED_COLS = [
    "event_id", "serial_number", "event_type", "subject_name", "subject_id",
    "longitude", "latitude", "event_datetime",
    "priority", "title", "state", "updated_at", "created_at", "is_collection",
]


def _flatten_and_display(events_gdf: gpd.GeoDataFrame, start_date, end_date, selected_event_types: list):
    """Flatten event_details, explode list-of-dict columns, resolve UUIDs,
    display a preview table and provide a CSV download button."""

    # Coordinates
    if "geometry" in events_gdf.columns:
        events_gdf["longitude"] = events_gdf.geometry.apply(lambda g: g.x if g else None)
        events_gdf["latitude"] = events_gdf.geometry.apply(lambda g: g.y if g else None)

    # Datetime fallback from geojson
    if "time" not in events_gdf.columns and "geojson" in events_gdf.columns:
        events_gdf["time"] = events_gdf["geojson"].apply(extract_datetime_from_geojson)

    # reported_by → subject_name / subject_id
    if "reported_by" in events_gdf.columns:
        events_gdf["subject_name"] = events_gdf["reported_by"].apply(
            lambda x: x.get("name", "") if isinstance(x, dict) else ""
        )
        if "subject_id" not in events_gdf.columns:
            events_gdf["subject_id"] = events_gdf["reported_by"].apply(
                lambda x: x.get("id", "") if isinstance(x, dict) else ""
            )

    # ── Repair repeat-group "orphan" child rows ────────────────────────────────
    # The ER API returns 1 parent row (event metadata, no individual data) +
    # N child rows (individual data, no event metadata).  We forward-fill the
    # metadata onto child rows then drop the now-superseded parent rows.
    _id_check = next(
        (c for c in ["serial_number", "time", "event_type"] if c in events_gdf.columns), None
    )
    if _id_check:
        _orphan = events_gdf[_id_check].apply(
            lambda x: pd.isna(x) or (isinstance(x, str) and x.strip() == "")
        )
        if _orphan.any() and not _orphan.all():
            _meta_cols = [c for c in [
                "time", "id", "serial_number", "event_type", "priority", "title",
                "state", "updated_at", "created_at", "is_collection",
                "reported_by", "longitude", "latitude", "subject_name", "subject_id",
            ] if c in events_gdf.columns]
            events_gdf[_meta_cols] = events_gdf[_meta_cols].ffill()
            # Forward-fill geometry
            _geom = events_gdf.geometry.values.copy()
            for _i in range(1, len(_geom)):
                if _geom[_i] is None or (hasattr(_geom[_i], "is_empty") and _geom[_i].is_empty):
                    _geom[_i] = _geom[_i - 1]
            events_gdf = events_gdf.set_geometry(gpd.GeoSeries(_geom, crs=4326))
            # Drop parent rows now superseded by their children
            _parent_mask = (~_orphan) & _orphan.shift(-1, fill_value=False)
            events_gdf = gpd.GeoDataFrame(
                events_gdf[~_parent_mask].reset_index(drop=True),
                geometry="geometry", crs=4326,
            )

    # ── Unnest event_details ───────────────────────────────────────────────────
    if "event_details" in events_gdf.columns:
        details_df = pd.json_normalize(events_gdf["event_details"]).reset_index(drop=True)
        details_df.columns = ["detail_" + c for c in details_df.columns]
        geom_col = events_gdf.geometry.reset_index(drop=True)
        events_gdf = gpd.GeoDataFrame(
            pd.concat([events_gdf.reset_index(drop=True), details_df], axis=1),
            geometry=geom_col, crs=4326,
        )

    # ── Explode list-of-dict detail_ columns (e.g. detail_Herd) ───────────────
    list_dict_cols = [
        col for col in events_gdf.columns
        if col.startswith("detail_") and events_gdf[col].apply(
            lambda x: isinstance(x, list) and len(x) > 0 and isinstance(x[0], dict)
        ).any()
    ]
    for col in list_dict_cols:
        events_gdf[col] = events_gdf[col].apply(
            lambda x: x if (isinstance(x, list) and len(x) > 0) else [{}]
        )
        events_gdf = events_gdf.explode(col, ignore_index=True)
        nested = pd.json_normalize(
            events_gdf[col].apply(lambda x: x if isinstance(x, dict) else {})
        )
        events_gdf = gpd.GeoDataFrame(
            pd.concat([events_gdf.drop(columns=[col]).reset_index(drop=True), nested], axis=1),
            geometry="geometry", crs=4326,
        )

    # ── Resolve UUIDs in detail_ columns ──────────────────────────────────────
    with st.spinner("Resolving display names for ID fields..."):
        uuid_to_name = build_entity_lookup(st.session_state.er_io)
    events_gdf = resolve_uuid_columns(events_gdf, uuid_to_name, col_prefix="")

    # ── Build display / export frame ───────────────────────────────────────────
    display_cols = [c for c in events_gdf.columns if c not in ("geometry", "geojson")]
    display_df = events_gdf[display_cols].copy()
    display_df = display_df.drop(columns=[c for c in _COLS_STRIP if c in display_df.columns])
    display_df = display_df.rename(columns={"id": "event_id", "time": "event_datetime"})

    detail_cols = sorted(c for c in display_df.columns if c.startswith("detail_"))
    item_cols = sorted(
        c for c in display_df.columns if not c.startswith("detail_") and c not in _PREFERRED_COLS
    )
    ordered = [c for c in _PREFERRED_COLS if c in display_df.columns]
    ordered += detail_cols + [c for c in item_cols if c not in ordered]
    ordered += [c for c in display_df.columns if c not in ordered]
    display_df = display_df[ordered]

    # Persist for the rendering / format-selection block below.
    # Stored in session_state so switching output format (which triggers a
    # Streamlit rerun) does not require re-fetching from EarthRanger.
    st.session_state.export_df = display_df
    st.session_state.export_meta = {
        "start_date": start_date,
        "end_date": end_date,
        "event_types": list(selected_event_types),
    }


# ── Camera operation table (camtrapR / unmarked) ────────────────────────────────

_TRUTHY = {"true", "t", "yes", "y", "1", "1.0", "functional", "ok",
           "working", "active", "operational", "on"}


def _truthy(val) -> bool:
    """Interpret a yes/no functional flag across the formats ER might store it in."""
    if isinstance(val, bool):
        return val
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return False
    return str(val).strip().lower() in _TRUTHY


def build_camera_operation_table(df, station_col, status_col, datetime_col,
                                 window_start=None, window_end=None):
    """
    Reconstruct a camtrapR-style camera operation matrix from check events.

    Rows = stations, columns = one per day across the survey window. Cell values:
        1 = camera operational that day
        0 = camera deployed but not functional (malfunction/error)

    The deployment window is the selected date range (`window_start` →
    `window_end`); columns span every day in it and every station is assumed
    deployed across the whole window. Each check's status is carried *back* over
    the interval since the previous check (the first check back-fills to the
    window start), and the last check carries *forward* to the window end. When a
    station is checked more than once on the same day, the last check of that day
    wins. If a window is not supplied it falls back to the observed check range
    (and days outside each station's first→last check are left as NA).
    Returns (matrix_df, n_stations, n_days).
    """
    work = df[[station_col, status_col, datetime_col]].copy()
    work[datetime_col] = pd.to_datetime(work[datetime_col], utc=True, errors="coerce")
    work = work.dropna(subset=[station_col, datetime_col])
    if work.empty:
        return pd.DataFrame(), 0, 0

    work["_date"] = work[datetime_col].dt.tz_convert("UTC").dt.normalize().dt.tz_localize(None)
    work["_func"] = work[status_col].apply(lambda v: 1 if _truthy(v) else 0)
    work[station_col] = work[station_col].astype(str)

    # One status per station per day — last check of the day wins.
    work = (
        work.sort_values([station_col, datetime_col])
        .groupby([station_col, "_date"], as_index=False)
        .agg(_func=("_func", "last"))
    )

    use_window = window_start is not None and window_end is not None
    start = pd.Timestamp(window_start).normalize() if use_window else work["_date"].min()
    end = pd.Timestamp(window_end).normalize() if use_window else work["_date"].max()
    all_days = pd.date_range(start, end, freq="D")
    stations = sorted(work[station_col].unique())
    matrix = pd.DataFrame(index=stations, columns=all_days, dtype="object")

    for stn, grp in work.groupby(station_col):
        grp = grp.sort_values("_date")
        check_days = grp["_date"].tolist()
        check_func = grp["_func"].tolist()
        setup, retrieval = check_days[0], check_days[-1]
        last_func = check_func[-1]
        for day in all_days:
            # status of the first check that closes the interval containing `day`
            idx = next((i for i, cd in enumerate(check_days) if cd >= day), None)
            if idx is not None:
                matrix.at[stn, day] = check_func[idx]
            elif use_window:
                # past the last check but still inside the survey window → carry forward
                matrix.at[stn, day] = last_func
            # else: no window given and day > retrieval → leave NaN (NA)
            if not use_window and (day < setup or day > retrieval):
                matrix.at[stn, day] = None

    matrix.columns = [d.strftime("%Y-%m-%d") for d in all_days]
    matrix.insert(0, "Station", matrix.index)
    matrix = matrix.reset_index(drop=True)
    return matrix, len(stations), len(all_days)


def _render_export():
    """Render preview + output-format selection + downloads from the persisted export.

    Lives outside the export button block so changing the output format (a
    Streamlit rerun) re-renders from session_state without re-querying ER.
    """
    display_df = st.session_state.get("export_df")
    if display_df is None:
        return

    meta = st.session_state.get("export_meta", {})
    start_date = meta.get("start_date")
    end_date = meta.get("end_date")
    event_types = meta.get("event_types", [])
    start_str = start_date.strftime("%y%m%d") if start_date else "start"
    end_str = end_date.strftime("%y%m%d") if end_date else "end"

    st.success(f"✅ {len(display_df):,} event row(s) extracted and flattened!")
    st.subheader("Events data preview")
    st.dataframe(display_df, use_container_width=True)

    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        st.metric("Total event rows", f"{len(display_df):,}")
    with col_m2:
        if "event_type" in display_df.columns:
            st.metric("Event types", display_df["event_type"].nunique())
    with col_m3:
        if "subject_name" in display_df.columns:
            st.metric("Unique reporters", display_df["subject_name"].nunique())

    st.markdown("---")
    st.subheader("Output format")
    fmt = st.radio(
        "Choose an export format:",
        ["Standard flattened CSV", "Camera operation table (camtrapR / unmarked)"],
        help="The camera operation table is built for occupancy analysis. Use it "
             "with camera-check events (e.g. cam_trap_2) that carry a functional flag.",
    )

    # ── Standard flattened CSV (original behaviour) ─────────────────────────────
    if fmt == "Standard flattened CSV":
        type_slug = "_".join(
            "".join(c if c.isalnum() else "_" for c in t) for t in event_types[:5]
        )
        st.download_button(
            "📥 Download Events CSV",
            data=display_df.to_csv(index=False),
            file_name=f"er_events_{type_slug}_{start_str}_{end_str}.csv",
            mime="text/csv",
            use_container_width=True,
        )
        return

    # ── Camera operation table mode ─────────────────────────────────────────────
    # Fixed cam_trap_2 field mapping. The deployment window is the selected date
    # range: columns span every day in it and every station is assumed deployed
    # across the whole window. Each check's status back-fills to the previous check
    # (first check back to the range start) and the last check carries forward to
    # the range end. Non-functional checks become 0, i.e. the matrix always carries
    # "problems" (camtrapR hasProblems = TRUE).
    STATION_COL = "detail_camtrap_site"
    STATUS_COL = "detail_camtrap_active"
    DATETIME_COL = "event_datetime"

    missing = [c for c in (STATION_COL, STATUS_COL, DATETIME_COL) if c not in display_df.columns]
    if missing:
        st.error(
            "❌ Expected cam_trap_2 field(s) not found in the export: "
            + ", ".join(f"`{c}`" for c in missing)
            + ". Make sure you selected the `cam_trap_2` event type."
        )
        return

    st.caption(
        f"Station = `{STATION_COL}` · functional flag = `{STATUS_COL}` · "
        f"check time = `{DATETIME_COL}`. Window = your selected date range "
        f"({start_date} → {end_date}); every station is assumed deployed across it."
    )

    try:
        matrix, n_stn, n_days = build_camera_operation_table(
            display_df, STATION_COL, STATUS_COL, DATETIME_COL,
            window_start=start_date, window_end=end_date,
        )
    except Exception as exc:
        st.error(f"❌ Could not build camera operation table: {exc}")
        return

    if matrix.empty:
        st.warning("No usable check records (need a station and a valid datetime).")
        return

    st.success(f"📋 Camera operation table: {n_stn} station(s) × {n_days} day(s).")
    st.caption("1 = operational · 0 = deployed but not functional. (Any blank = NA.)")
    st.dataframe(matrix, use_container_width=True)

    # NA cells (if any) are written as the literal "NA" so R reads them with na.strings="NA".
    csv_data = matrix.to_csv(index=False, na_rep="NA")
    st.download_button(
        "📥 Download camera operation table (CSV)",
        data=csv_data,
        file_name=f"camera_operation_{start_str}_{end_str}.csv",
        mime="text/csv",
        use_container_width=True,
    )
    with st.expander("How to load this in R (camtrapR / unmarked)"):
        st.code(
            f'op <- read.csv("camera_operation_{start_str}_{end_str}.csv",\n'
            '               row.names = 1, check.names = FALSE, na.strings = "NA")\n'
            'camop <- as.matrix(op)   # stations x days; 1 / 0 / NA\n\n'
            '# 0s mark non-functional periods, so build histories with hasProblems = TRUE:\n'
            'detHist <- camtrapR::detectionHistory(camOp = camop, hasProblems = TRUE, ...)\n'
            '# then feed detHist$detection_history to unmarked::unmarkedFrameOccu().',
            language="r",
        )


# ── Page ───────────────────────────────────────────────────────────────────────
st.title("📥 Event download")
st.markdown(
    "Export flattened EarthRanger events by event type and date range. "
    "Event detail fields are fully unpacked into individual columns."
)

# Authentication
st.markdown("---")
st.subheader("🔐 EarthRanger login")

if not st.session_state.authenticated:
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        server_input = st.text_input("Instance URL", placeholder="twiga.pamdas.org")
    with col_b:
        username = st.text_input("Username")
    with col_c:
        password = st.text_input("Password", type="password")

    if st.button("Login", type="primary", use_container_width=True):
        if server_input and username and password:
            server = server_input if server_input.startswith("http") else f"https://{server_input}"
            with st.spinner("Authenticating..."):
                er_io, error = authenticate_earthranger(server, username, password)
                if er_io:
                    st.session_state.er_io = er_io
                    st.session_state.authenticated = True
                    st.success("✅ Successfully authenticated!")
                    st.rerun()
                else:
                    st.error(f"❌ Authentication failed: {error}")
        else:
            st.warning("Please fill in all fields")
else:
    col_s1, col_s2 = st.columns([3, 1])
    with col_s1:
        st.success("✅ Logged in to EarthRanger")
    with col_s2:
        if st.button("Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.er_io = None
            st.rerun()

st.markdown("---")

# Main content
if not st.session_state.authenticated:
    st.info("👈 Please log in to your EarthRanger instance using the form above")
    st.stop()

# ── 1. Date range ──────────────────────────────────────────────────────────────
st.subheader("1️⃣ Select date range")
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input(
        "Start date",
        value=datetime.now() - timedelta(days=14),
        help="Beginning of date range",
    )
with col2:
    end_date = st.date_input(
        "End date",
        value=datetime.now(),
        help="End of date range",
    )

since = datetime.combine(start_date, datetime.min.time()).isoformat()
until = datetime.combine(end_date, datetime.max.time()).isoformat()

st.markdown("---")

# ── 2. Load available event types ─────────────────────────────────────────────
st.subheader("2️⃣ Select event type(s)")

try:
    with st.spinner("Loading available event types from EarthRanger..."):
        sample_events = st.session_state.er_io.get_events(
            since=since,
            until=until,
            include_details=True,
        )

    if sample_events.empty or "event_type" not in sample_events.columns:
        st.info("No events found in the selected date range.")
        st.stop()

    available_event_types = sorted(sample_events["event_type"].dropna().unique().tolist())
    st.write(f"Found **{len(available_event_types)}** event type(s) in the selected date range.")

    selected_event_types = st.multiselect(
        "Select event type(s) to export:",
        options=available_event_types,
        default=None,
        help="Select one or more event types — all detail fields will be flattened into columns",
    )

except Exception as exc:
    st.error(f"❌ Error loading event types: {exc}")
    import traceback
    st.error(traceback.format_exc())
    st.stop()

if not selected_event_types:
    st.info("👆 Select at least one event type above, then click Export.")
    st.stop()

st.markdown("---")

# ── 3. Export ──────────────────────────────────────────────────────────────────
if st.button("📥 Export selected events", type="primary", use_container_width=True):
    with st.spinner(f"Fetching and flattening {len(selected_event_types)} event type(s)..."):
        try:
            # Filter to selected types — sample_events already has include_details=True
            filtered = sample_events[sample_events["event_type"].isin(selected_event_types)].copy()

            if filtered.empty:
                st.warning("No events found for the selected event types.")
                st.stop()

            st.info(f"Found {len(filtered):,} event(s) — fetching full details in batches...")

            # If event_details is already present (include_details=True worked), use as-is.
            # Otherwise batch-fetch full details by event ID.
            if "event_details" not in filtered.columns:
                id_col = next(
                    (c for c in ["id", "event_id", "serial_number"] if c in filtered.columns), None
                )
                if not id_col:
                    st.error("Cannot find an event ID column in the data.")
                    st.stop()

                event_ids = [e for e in filtered[id_col].tolist() if e and pd.notna(e)]
                batch_size = 50
                detailed_list = []
                progress = st.progress(0)

                for i in range(0, len(event_ids), batch_size):
                    batch = event_ids[i : i + batch_size]
                    try:
                        chunk = st.session_state.er_io.get_events(
                            event_ids=batch,
                            include_details=True,
                            include_notes=True,
                        )
                        if not chunk.empty:
                            detailed_list.append(chunk)
                    except Exception as batch_err:
                        st.warning(
                            f"Could not fetch batch {i // batch_size + 1}: {str(batch_err)[:100]}"
                        )
                    progress.progress(min(1.0, (i + batch_size) / len(event_ids)))
                progress.empty()

                if not detailed_list:
                    st.warning("No detailed events could be retrieved.")
                    st.stop()

                filtered = pd.concat(detailed_list, ignore_index=True)

            # Attach geometry
            filtered["geometry"] = filtered.apply(extract_geometry, axis=1)
            events_gdf = gpd.GeoDataFrame(filtered, geometry="geometry", crs=4326)

            _flatten_and_display(events_gdf, start_date, end_date, selected_event_types)

        except Exception as exc:
            st.error(f"❌ Error during export: {exc}")
            import traceback
            st.error(traceback.format_exc())

# ── 4. Preview, format selection & download ─────────────────────────────────────
# Rendered from session_state so switching output format re-runs without
# re-querying EarthRanger.
_render_export()
