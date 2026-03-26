"""
Post-Tagging Dashboard
Review immobilisation records and monitor animal welfare during the first 48 hours
after darting and collar deployment.
"""

import os
import re
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
from ecoscope.io.earthranger import EarthRangerIO

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

SERVER = "https://twiga.pamdas.org"

# Country code → display name mapping (GCF range countries)
COUNTRY_PREFIXES = {
    # Kenya
    "KH": "Kenya", "HSB": "Kenya", "NAI": "Kenya", "TSA": "Kenya",
    "MAA": "Kenya", "SAM": "Kenya", "LAI": "Kenya", "KE": "Kenya",
    # Tanzania
    "TZ": "Tanzania", "SER": "Tanzania", "MAN": "Tanzania",
    "TAR": "Tanzania", "RUA": "Tanzania",
    # Uganda
    "UG": "Uganda", "QEP": "Uganda", "MUR": "Uganda", "KID": "Uganda",
    # Botswana
    "BW": "Botswana", "BOT": "Botswana", "OKA": "Botswana", "CHO": "Botswana",
    # Namibia
    "NAM": "Namibia", "ETO": "Namibia", "DAM": "Namibia", "NA": "Namibia",
    # South Africa
    "RSA": "South Africa", "KRU": "South Africa", "ZA": "South Africa",
    # Zimbabwe
    "ZIM": "Zimbabwe", "HWA": "Zimbabwe", "ZW": "Zimbabwe",
    # Zambia
    "ZAM": "Zambia", "SKF": "Zambia", "NKF": "Zambia", "ZM": "Zambia",
    # Niger
    "NIG": "Niger", "NE": "Niger",
    # Ethiopia
    "ETH": "Ethiopia", "ET": "Ethiopia",
    # Angola
    "ANG": "Angola", "AGO": "Angola",
    # Mozambique
    "MOZ": "Mozambique", "MZ": "Mozambique",
    # Chad
    "CHA": "Chad", "TD": "Chad",
    # Cameroon
    "CAM": "Cameroon", "CM": "Cameroon",
}


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

def init_session_state():
    for key, val in {
        "authenticated": False,
        "username": "",
        "password": "",
    }.items():
        if key not in st.session_state:
            st.session_state[key] = val


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def authenticate_earthranger():
    st.header("🔐 EarthRanger Login")
    st.info(f"**Server:** {SERVER}")

    with st.form("auth_form"):
        username = st.text_input("Username", value=st.session_state.username)
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("🔌 Connect", type="primary")

    if submitted:
        if not username or not password:
            st.error("Username and password are required.")
            return
        with st.spinner("Authenticating…"):
            try:
                er = EarthRangerIO(server=SERVER, username=username, password=password)
                er.get_subjects(limit=1)
                st.session_state.authenticated = True
                st.session_state.username = username
                st.session_state.password = password
                st.success("✅ Connected!")
                st.rerun()
            except Exception as e:
                st.error(f"Authentication failed: {e}")


# ---------------------------------------------------------------------------
# Data fetching  (ecoscope; credentials as explicit cache-key args)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=900, show_spinner=False)
def fetch_immobilization_events(since: str, until: str,
                                username: str, password: str) -> pd.DataFrame:
    """Fetch all veterinary / immob events, returned as a plain DataFrame."""
    try:
        er = EarthRangerIO(server=SERVER, username=username, password=password)
        gdf = er.get_events(
            event_category="veterinary",
            since=since,
            until=until,
            include_details=True,
            include_notes=True,
            include_files=True,
            drop_null_geometry=False,
        )
        if gdf.empty:
            return pd.DataFrame()

        df = pd.DataFrame(gdf)
        if "event_type" in df.columns:
            mask = df["event_type"].isin([
                "giraffe_immobilisation",
                "ca5714a4-e962-49c6-b326-0e3e96d81a2d",
            ])
            df = df[mask].copy()
        return df

    except Exception as e:
        st.error(f"Error fetching events: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=900, show_spinner=False)
def fetch_event_files(event_id: str, username: str, password: str) -> list[dict]:
    """
    Return the file attachment list for a single event.
    Hits GET /api/v1.0/activity/event/{id}/files/ directly so we always get
    the full file list regardless of how ecoscope serialises the events DataFrame.
    Each returned dict has keys: file_id, filename, download_url.
    """
    try:
        er = EarthRangerIO(server=SERVER, username=username, password=password)
        url = f"{SERVER}/api/v1.0/activity/event/{event_id}/files/"
        resp = er._http_session.get(url, headers=er.auth_headers())
        resp.raise_for_status()
        data = resp.json()
        raw = data if isinstance(data, list) else data.get("results", data.get("data", []))
        files = []
        for f in (raw or []):
            if not isinstance(f, dict):
                continue
            fid = str(f.get("id") or f.get("file_id") or "").strip()
            fname = (f.get("filename") or f.get("name") or "file").strip()
            if fid:
                dl_url = (
                    f"{SERVER}/api/v1.0/activity/event/{event_id}"
                    f"/file/{fid}/original/{fname}"
                )
                files.append({"file_id": fid, "filename": fname,
                               "download_url": dl_url})
        return files
    except Exception:
        return []


@st.cache_data(ttl=900, show_spinner=False)
def fetch_subject_observations(subject_id: str, since: str, until: str,
                               username: str, password: str) -> pd.DataFrame:
    """Fetch GPS fixes for a subject in a time window; returns [recorded_at, lat, lon]."""
    try:
        er = EarthRangerIO(server=SERVER, username=username, password=password)
        result = er.get_subject_observations(
            subject_ids=[subject_id],
            since=since,
            until=until,
            filter=0,
        )

        # ecoscope may return a Relocations wrapper — unwrap to GeoDataFrame
        gdf = result.gdf if hasattr(result, "gdf") else result

        if gdf is None or len(gdf) == 0:
            return pd.DataFrame()

        # Locate the timestamp column — name varies by ecoscope / ER version
        ts_col = next(
            (c for c in ("recorded_at", "fixtime", "time", "timestamp", "created_at")
             if c in gdf.columns),
            None,
        )
        if ts_col is None:
            st.warning(
                f"GPS data for {subject_id} has no recognised timestamp column. "
                f"Available columns: {list(gdf.columns)}"
            )
            return pd.DataFrame()

        return pd.DataFrame({
            "recorded_at": pd.to_datetime(gdf[ts_col]),
            "lat": gdf.geometry.y,
            "lon": gdf.geometry.x,
        }).dropna().sort_values("recorded_at").reset_index(drop=True)

    except Exception as e:
        st.warning(f"Could not load GPS track for {subject_id}: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_subject_id_by_name(name: str, username: str, password: str) -> str | None:
    """
    Resolve a subject UUID from its display name via EarthRanger.

    ecoscope stores the UUID as the DataFrame index, not as an 'id' column,
    so we check the index after filtering by name.  get_subjects() may not
    honour the name= kwarg server-side, so we also filter locally.
    """
    try:
        er = EarthRangerIO(server=SERVER, username=username, password=password)
        subjects = er.get_subjects()
        if subjects is None or len(subjects) == 0:
            return None

        # Locate the name column (varies by ecoscope version)
        name_col = next(
            (c for c in ("name", "display_name", "subject_name")
             if c in subjects.columns),
            None,
        )
        if name_col:
            match = subjects[subjects[name_col].str.lower() == name.lower()]
            if len(match) == 0:
                # Partial match fallback
                match = subjects[subjects[name_col].str.lower().str.contains(
                    name.lower(), na=False)]
            if len(match) > 0:
                subjects = match

        row = subjects.iloc[0]
        # Try explicit id column first, then fall back to the DataFrame index
        uid = row.get("id") or row.get("subject_id") or None
        if not uid:
            uid = subjects.index[0]
        return str(uid) if uid else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Event parsing helpers
# ---------------------------------------------------------------------------

_SUBJECT_NAME_FIELDS = (
    "subject_name", "animal_name", "animal", "subject", "individual_name",
)

# Broader list also checked for UUID extraction
_SUBJECT_ID_FIELDS = _SUBJECT_NAME_FIELDS + ("subject_id", "animal_id", "id")


def _find_subject_name_in_dict(d: dict) -> str | None:
    """
    Search the TOP LEVEL of event_details for a subject display name.
    If a field value is itself a dict (e.g. {"id": uuid, "name": "NTG-001"}),
    looks one level deeper for a "name" / "display_name" key.
    Does NOT recurse through all values to avoid matching drug/location names.
    """
    if not isinstance(d, dict):
        return None
    for field in _SUBJECT_NAME_FIELDS:
        val = d.get(field)
        if val is None:
            continue
        if isinstance(val, str):
            val = val.strip()
            if len(val) > 1 and not _UUID_RE.match(val):
                return val
        elif isinstance(val, dict):
            # Value is a linked-object dict — look for a display name inside it
            for name_key in ("name", "display_name", "subject_name"):
                inner = val.get(name_key)
                if isinstance(inner, str):
                    inner = inner.strip()
                    if len(inner) > 1 and not _UUID_RE.match(inner):
                        return inner
    return None


def _find_subject_uuid_in_dict(d: dict) -> str | None:
    """
    Search the TOP LEVEL of event_details for a subject UUID.
    Handles both plain UUID strings and linked-object dicts {"id": uuid, ...}.
    """
    if not isinstance(d, dict):
        return None
    for field in _SUBJECT_ID_FIELDS:
        val = d.get(field)
        if val is None:
            continue
        if isinstance(val, str) and _UUID_RE.match(val.strip()):
            return val.strip()
        elif isinstance(val, dict):
            for id_key in ("id", "uuid", "subject_id"):
                inner = val.get(id_key)
                if isinstance(inner, str) and _UUID_RE.match(inner.strip()):
                    return inner.strip()
    return None


def _country_from_name(name: str) -> str:
    """Attempt to derive a country label from a subject name prefix."""
    if not isinstance(name, str):
        return "Unknown"
    upper = name.strip().upper()
    # Try longest prefix first for specificity
    for prefix in sorted(COUNTRY_PREFIXES, key=len, reverse=True):
        if upper.startswith(prefix):
            return COUNTRY_PREFIXES[prefix]
    return "Unknown"


def parse_event(row: pd.Series) -> dict:
    lat = lon = None
    loc = row.get("location") or {}

    if isinstance(loc, dict):
        # GeoJSON Point: {"type": "Point", "coordinates": [lon, lat]}
        if loc.get("type") == "Point" and isinstance(loc.get("coordinates"), list):
            coords = loc["coordinates"]
            if len(coords) >= 2:
                lon, lat = coords[0], coords[1]
        else:
            # Flat dict variants
            lat = loc.get("latitude") or loc.get("lat")
            lon = loc.get("longitude") or loc.get("lon")

    # Fallback: check event_details for lat/lon fields
    if lat is None or lon is None:
        d = row.get("event_details") or {}
        lat = lat or d.get("latitude") or d.get("lat")
        lon = lon or d.get("longitude") or d.get("lon")

    related = row.get("related_subjects") or []
    subject_id = subject_name = None
    if isinstance(related, list) and related:
        s = related[0]
        if isinstance(s, dict):
            subject_id = s.get("id")
            subject_name = s.get("name")

    # Fallback: search event_details for both a display name and a subject UUID.
    # subject_name fields in ER event forms may store a UUID (subject picker) OR
    # a plain string (free-text).  Extract whichever is present.
    details_dict = row.get("event_details") or {}
    if not subject_name:
        subject_name = _find_subject_name_in_dict(details_dict)
    if not subject_id:
        subject_id = _find_subject_uuid_in_dict(details_dict)

    reporter = row.get("reported_by") or {}
    reporter_name = (
        reporter.get("username", "Unknown") if isinstance(reporter, dict) else "Unknown"
    )

    # ecoscope sets the event UUID as the DataFrame index (row.name), not as a column
    event_id = str(row.get("id") or row.get("event_id") or row.name or "")

    # Extract file attachments returned by get_events(include_files=True).
    # Each entry: {"file_id": str, "filename": str}
    raw_files = row.get("files") or []
    parsed_files: list[dict] = []
    if isinstance(raw_files, list):
        for f in raw_files:
            if not isinstance(f, dict):
                continue
            fid = str(f.get("id") or f.get("file_id") or "").strip()
            fname = (f.get("filename") or f.get("name") or "file").strip()
            if fid:
                parsed_files.append({"file_id": fid, "filename": fname})

    return {
        "event_id":     event_id,
        "er_url":       f"{SERVER}/events/{event_id}" if event_id else "",
        "serial":       row.get("serial_number"),
        "time":         pd.to_datetime(row.get("time")),
        "title":        row.get("title") or "",
        "notes":        row.get("notes") or "",
        "details":      row.get("event_details") or {},
        "lat":          lat,
        "lon":          lon,
        "subject_id":   subject_id,
        "subject_name": subject_name,
        "reported_by":  reporter_name,
        "country":      _country_from_name(subject_name or ""),
        "files":        parsed_files,
    }


# ---------------------------------------------------------------------------
# Map helpers
# ---------------------------------------------------------------------------

def _event_display_name(ev: dict) -> str:
    """Return the best human-readable label for an event, never a raw UUID."""
    sname = (ev.get("subject_name") or "").strip()
    if sname and not _UUID_RE.match(sname):
        return sname
    serial = ev.get("serial")
    if serial:
        return f"Event {serial}"
    return f"Event {str(ev.get('event_id', ''))[:8]}"


def _map_center(lats, lons):
    if lats:
        return dict(lat=np.mean(lats), lon=np.mean(lons)), 9
    return dict(lat=-2.0, lon=37.0), 4


def build_immob_sites_map(events: list) -> go.Figure:
    """Single-purpose map: just the immobilisation site markers."""
    fig = go.Figure()
    colors = px.colors.qualitative.Safe
    lats, lons = [], []

    for idx, ev in enumerate(events):
        if not ev["lat"] or not ev["lon"]:
            continue
        color = colors[idx % len(colors)]
        name = _event_display_name(ev)
        t = ev["time"].strftime("%Y-%m-%d %H:%M") if pd.notna(ev["time"]) else "?"

        # Build a hover summary of event_details
        detail_lines = ""
        if isinstance(ev["details"], dict):
            non_empty = {k: v for k, v in ev["details"].items()
                         if v not in (None, "", [], {})}
            if non_empty:
                detail_lines = "<br>".join(
                    f"<i>{k.replace('_',' ').capitalize()}:</i> {v}"
                    for k, v in list(non_empty.items())[:8]
                )

        hover = (
            f"<b>{name}</b><br>"
            f"Date: {t}<br>"
            f"Reported by: {ev['reported_by']}<br>"
            f"Lat: {ev['lat']:.5f}, Lon: {ev['lon']:.5f}"
        )
        if ev["notes"]:
            hover += f"<br><br><i>Notes:</i> {ev['notes'][:200]}"
        if detail_lines:
            hover += f"<br><br>{detail_lines}"

        fig.add_trace(go.Scattermapbox(
            lat=[ev["lat"]], lon=[ev["lon"]],
            mode="markers",
            marker=dict(size=18, color=color),
            name=name,
            text=hover,
            hovertemplate="%{text}<extra></extra>",
        ))
        lats.append(ev["lat"]); lons.append(ev["lon"])

    center, zoom = _map_center(lats, lons)
    fig.update_layout(
        mapbox=dict(style="open-street-map", center=center, zoom=zoom),
        height=500,
        margin=dict(l=0, r=0, t=0, b=150),
        legend=dict(
            orientation="h",
            yanchor="top", y=-0.02,
            xanchor="left", x=0,
            bgcolor="rgba(255,255,255,0.0)",
            font=dict(size=11),
        ),
    )
    return fig


def build_movement_map(events: list, subject_obs: dict) -> go.Figure:
    """Map showing 48-h GPS tracks only (no immobilisation site markers)."""
    fig = go.Figure()
    colors = px.colors.qualitative.Safe
    lats, lons = [], []

    for idx, ev in enumerate(events):
        color = colors[idx % len(colors)]
        name = _event_display_name(ev)

        # GPS track only — key matches the fetch loop cache_key
        _track_key = ev["subject_name"] or ev["subject_id"]
        obs = subject_obs.get(_track_key, pd.DataFrame())
        if not obs.empty:
            fig.add_trace(go.Scattermapbox(
                lat=obs["lat"], lon=obs["lon"],
                mode="lines+markers",
                line=dict(width=2, color=color),
                marker=dict(size=5, color=color, opacity=0.7),
                name=f"{name} – track",
                text=[
                    f"<b>{name}</b><br>{r.recorded_at.strftime('%Y-%m-%d %H:%M')}<br>"
                    f"Lat {r.lat:.5f}, Lon {r.lon:.5f}"
                    for r in obs.itertuples()
                ],
                hovertemplate="%{text}<extra></extra>",
                showlegend=True,
            ))
            lats.extend(obs["lat"].tolist())
            lons.extend(obs["lon"].tolist())

    center, zoom = _map_center(lats, lons)
    fig.update_layout(
        mapbox=dict(style="open-street-map", center=center, zoom=zoom),
        height=600,
        margin=dict(l=0, r=0, t=0, b=180),
        legend=dict(
            orientation="h",
            yanchor="top", y=-0.02,
            xanchor="left", x=0,
            bgcolor="rgba(255,255,255,0.0)",
            font=dict(size=11),
        ),
    )
    return fig


# ---------------------------------------------------------------------------
# Events table
# ---------------------------------------------------------------------------

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}


def _is_image(filename: str) -> bool:
    _, ext = os.path.splitext(str(filename).lower())
    return ext in _IMAGE_EXTS


def _flatten_details(details: dict) -> dict:
    """
    Recursively flatten event_details into a plain {col: value} dict.

    Rules:
    • dict values  → dot-expanded (up to 3 levels deep)
    • list-of-dicts → indexed columns, e.g.  drugs_1_name, drugs_1_dose_mg
      (handles unit/drugs/reversal_drugs nesting inside each drug item too)
    • list-of-scalars → comma-joined string
    • None / empty   → kept so the user can see every field name
    """
    flat = {}
    if not isinstance(details, dict):
        return flat

    for k, v in details.items():
        if isinstance(v, dict):
            # One dict level — expand, then handle any deeper nesting
            for k2, v2 in v.items():
                if isinstance(v2, dict):
                    for k3, v3 in v2.items():
                        flat[f"{k}.{k2}.{k3}"] = v3
                elif isinstance(v2, list) and v2 and isinstance(v2[0], dict):
                    for i, item in enumerate(v2, 1):
                        if isinstance(item, dict):
                            for k3, v3 in item.items():
                                flat[f"{k}.{k2}_{i}_{k3}"] = v3
                        else:
                            flat[f"{k}.{k2}_{i}"] = item
                else:
                    flat[f"{k}.{k2}"] = v2

        elif isinstance(v, list) and v and isinstance(v[0], dict):
            # List-of-dicts (drugs, reversal_drugs, tags, etc.)
            # → drugs_1_name, drugs_1_dose, drugs_1_unit.volume …
            for i, item in enumerate(v, 1):
                if isinstance(item, dict):
                    for k2, v2 in item.items():
                        if isinstance(v2, dict):
                            # e.g. unit: {volume: 10, concentration: 5}
                            for k3, v3 in v2.items():
                                flat[f"{k}_{i}_{k2}_{k3}"] = v3
                        elif isinstance(v2, list):
                            flat[f"{k}_{i}_{k2}"] = (
                                ", ".join(str(x) for x in v2) if v2 else None
                            )
                        else:
                            flat[f"{k}_{i}_{k2}"] = v2
                else:
                    flat[f"{k}_{i}"] = item

        elif isinstance(v, list):
            # Simple list of scalars
            flat[k] = ", ".join(str(x) for x in v) if v else None

        else:
            flat[k] = v

    return flat


def build_events_table(
    events: list, files_per_event: dict
) -> tuple[pd.DataFrame, dict]:
    """
    Build the events DataFrame with event_details exploded into individual columns.
    Files are split into separate File_1 … File_N URL columns so Streamlit's
    LinkColumn can render each one as a real clickable link.

    Returns (dataframe, column_config_dict).
    """
    # Work out the maximum number of files across all events so we can pre-size columns
    max_files = max(
        (len(files_per_event.get(ev["event_id"], [])) for ev in events),
        default=0,
    )

    rows = []
    for ev in events:
        file_list = files_per_event.get(ev["event_id"], [])

        time_str = ev["time"].strftime("%Y-%m-%d %H:%M") if pd.notna(ev["time"]) else "?"
        lat_str = f"{ev['lat']:.5f}" if ev["lat"] else "—"
        lon_str = f"{ev['lon']:.5f}" if ev["lon"] else "—"

        base = {
            "Serial #":          ev["serial"] or "—",
            "Date / Time (UTC)": time_str,
            "Subject":           ev["subject_name"] or "Unknown",
            "Country":           ev["country"],
            "Reported by":       ev["reported_by"],
            "Lat":               lat_str,
            "Lon":               lon_str,
            "Notes":             ev["notes"] or "",
            "ER Event":          ev["er_url"],
        }

        # One column per file — download_url is the cell value (LinkColumn)
        for i in range(max_files):
            col = f"File {i + 1}"
            if i < len(file_list):
                f = file_list[i]
                base[col] = (
                    f.get("download_url")
                    or f.get("url")
                    or f.get("file_url")
                    or None
                )
            else:
                base[col] = None

        # Explode event_details — each key becomes its own column
        base.update(_flatten_details(ev["details"]))
        rows.append(base)

    df = pd.DataFrame(rows)

    # Build the column config — LinkColumn for every file column
    col_config: dict = {
        "ER Event": st.column_config.LinkColumn("ER Event", display_text="Open ↗"),
    }
    for i in range(max_files):
        col = f"File {i + 1}"
        col_config[col] = st.column_config.LinkColumn(
            col, display_text="📎 Open"
        )

    return df, col_config


def show_photo_previews(events: list, files_per_event: dict):
    """
    Inline photo previews grouped by event, under collapsible expanders.
    Downloads image bytes via the authenticated ER session so the viewer
    works regardless of whether the user is logged into ER in their browser.
    """
    er = EarthRangerIO(
        server=SERVER,
        username=st.session_state.username,
        password=st.session_state.password,
    )
    auth_headers = er.auth_headers()

    any_shown = False
    for ev in events:
        file_list = files_per_event.get(ev["event_id"], [])
        images = [f for f in file_list if _is_image(f.get("filename", ""))]
        if not images:
            continue

        any_shown = True
        label = _event_display_name(ev)
        t = ev["time"].strftime("%Y-%m-%d %H:%M") if pd.notna(ev["time"]) else "?"
        with st.expander(f"📷 {label} — {t}  ({len(images)} photo(s))", expanded=False):
            cols = st.columns(min(len(images), 4))
            for i, img_file in enumerate(images):
                fname = img_file.get("filename", f"photo_{i + 1}")
                dl_url = (
                    img_file.get("download_url")
                    or img_file.get("url")
                    or img_file.get("file_url")
                    or ""
                )
                with cols[i % 4]:
                    if dl_url:
                        try:
                            resp = er._http_session.get(dl_url, headers=auth_headers,
                                                        timeout=15)
                            if resp.ok:
                                st.image(resp.content, caption=fname,
                                         use_container_width=True)
                            else:
                                st.markdown(f"[📷 {fname}]({dl_url})")
                        except Exception:
                            st.markdown(f"[📷 {fname}]({dl_url})")
                    else:
                        st.write(f"📷 {fname}")

    if not any_shown:
        st.info("No photos found for the selected events.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    st.title("📡 Post-Tagging Dashboard")
    st.markdown(
        "Review immobilisation records and monitor giraffe welfare during the "
        "first 48 hours after darting and collar deployment."
    )

    init_session_state()

    if not st.session_state.authenticated:
        authenticate_earthranger()
        return

    # ── Logout in sidebar
    with st.sidebar:
        st.markdown("---")
        if st.button("🔓 Log out"):
            for k in ("authenticated", "username", "password", "ptd_loaded"):
                st.session_state.pop(k, None)
            st.rerun()

    # ── Filters: date range + Load button at top of main page
    st.subheader("🔍 Select date range")
    default_end   = datetime.now().date()
    default_start = default_end - timedelta(days=30)

    f_col1, f_col2, f_col3 = st.columns([2, 2, 1])
    with f_col1:
        start_date = st.date_input("From", value=default_start, key="ptd_start")
    with f_col2:
        end_date = st.date_input("To", value=default_end, key="ptd_end")
    with f_col3:
        st.markdown("<br>", unsafe_allow_html=True)   # vertical align button
        load = st.button("🔄 Load events", type="primary", use_container_width=True)

    if start_date > end_date:
        st.error("Start date must be before end date.")
        return

    if not load and "ptd_loaded" not in st.session_state:
        st.info("Set the date range above and click **Load events**.")
        return

    if load:
        st.session_state["ptd_loaded"] = True
        fetch_immobilization_events.clear()
        fetch_event_files.clear()
        fetch_subject_observations.clear()

    user = st.session_state.username
    pwd  = st.session_state.password
    since = f"{start_date}T00:00:00Z"
    until = f"{end_date}T23:59:59Z"

    # ── Fetch events
    with st.spinner("Fetching immobilisation events…"):
        events_df = fetch_immobilization_events(since, until, user, pwd)

    if events_df.empty:
        st.warning(
            f"No immobilisation events found between **{start_date}** and **{end_date}**. "
            "Confirm events are recorded in EarthRanger with event category **veterinary** "
            "and event type **giraffe_immobilisation**."
        )
        return

    # Parse and deduplicate — the OR filter (event_type + UUID) can produce duplicates.
    # Use the DataFrame index (idx) as the canonical key because ecoscope stores the
    # event UUID there; ev["event_id"] falls back to it inside parse_event too.
    seen_ids: set = set()
    events_all = []
    for idx, row in events_df.iterrows():
        ev = parse_event(row)
        dedup_key = ev["event_id"] or str(idx)
        if dedup_key not in seen_ids:
            seen_ids.add(dedup_key)
            events_all.append(ev)
    events_all.sort(
        key=lambda e: e["time"] if pd.notna(e["time"]) else datetime.min,
        reverse=True,
    )

    # ── Country filter (derived from loaded events)
    countries_found = sorted({e["country"] for e in events_all})
    country_options = ["All countries"] + countries_found

    st.markdown("---")
    country_sel = st.selectbox("🌍 Filter by country / tagging operation",
                               country_options, key="ptd_country")

    events = (
        events_all if country_sel == "All countries"
        else [e for e in events_all if e["country"] == country_sel]
    )

    st.success(
        f"Showing **{len(events)}** immobilisation event(s)"
        + (f" in **{country_sel}**" if country_sel != "All countries" else "")
        + f" between {start_date} and {end_date}."
    )

    # ── Build file lists per event.
    # parse_event already extracts files when get_events(include_files=True) returns them.
    # For any event where that list is empty, fall back to the /files/ REST endpoint.
    files_per_event: dict[str, list] = {}
    needs_api = [ev for ev in events if not ev.get("files")]
    if needs_api:
        file_prog = st.progress(0, text="Loading event file attachments…")
        for i, ev in enumerate(needs_api):
            files_per_event[ev["event_id"]] = fetch_event_files(
                ev["event_id"], user, pwd
            )
            file_prog.progress((i + 1) / len(needs_api))
        file_prog.empty()
    # Merge: prefer pre-parsed files, supplement with API results
    for ev in events:
        eid = ev["event_id"]
        if ev.get("files"):
            # Build download_url for files that came from parse_event
            files_per_event[eid] = [
                {
                    "file_id":      f["file_id"],
                    "filename":     f["filename"],
                    "download_url": (
                        f"{SERVER}/api/v1.0/activity/event/{eid}"
                        f"/file/{f['file_id']}/original/{f['filename']}"
                    ),
                }
                for f in ev["files"]
            ]
        elif eid not in files_per_event:
            files_per_event[eid] = []

    # ── Fetch 48-h GPS tracks
    # Always key by subject_name so the fetch loop and the map builder agree.
    subject_obs: dict[str, pd.DataFrame] = {}
    to_fetch = [
        (ev["subject_id"], ev["subject_name"], ev["time"])
        for ev in events
        if (ev["subject_id"] or ev["subject_name"]) and pd.notna(ev["time"])
    ]
    if to_fetch:
        gps_prog = st.progress(0, text="Loading 48-hour GPS tracks…")
        for i, (sid, sname, t) in enumerate(to_fetch):
            # cache_key must match what build_movement_map uses:
            #   ev["subject_name"] or ev["subject_id"]
            cache_key = sname or sid
            if not cache_key or cache_key in subject_obs:
                gps_prog.progress((i + 1) / len(to_fetch))
                continue
            # Prefer UUID for the API call; only hit name-resolution if unavailable
            lookup_id = sid or fetch_subject_id_by_name(sname, user, pwd) or sname
            subject_obs[cache_key] = fetch_subject_observations(
                lookup_id,
                t.strftime("%Y-%m-%dT%H:%M:%SZ"),
                (t + timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                user, pwd,
            )
            gps_prog.progress((i + 1) / len(to_fetch))
        gps_prog.empty()

    st.markdown("---")

    # ════════════════════════════════════════════════════════════════════════
    # SECTION 1 — Immobilisation sites map
    # ════════════════════════════════════════════════════════════════════════
    st.subheader("📍 Immobilisation sites")
    st.caption("Hover over a marker for full event details including drugs and notes.")

    events_with_loc = [e for e in events if e["lat"] and e["lon"]]
    if events_with_loc:
        st.plotly_chart(
            build_immob_sites_map(events_with_loc),
            use_container_width=True,
            key="immob_map",
        )
    else:
        st.info("No location data available for the selected events.")

    st.markdown("---")

    # ════════════════════════════════════════════════════════════════════════
    # SECTION 2 — Events table
    # ════════════════════════════════════════════════════════════════════════
    st.subheader("📋 Immobilisation records")
    st.caption(
        "Event details including drugs, tags, and measurements. "
        "The **Files** column contains links to attached documents/photos. "
        "Click **ER Event** to open the full record in EarthRanger."
    )

    table_df, table_col_config = build_events_table(events, files_per_event)
    st.dataframe(
        table_df,
        use_container_width=True,
        hide_index=True,
        column_config=table_col_config,
    )

    # Photo previews (expandable per subject)
    any_photos = any(
        _is_image(f.get("filename", ""))
        for flist in files_per_event.values()
        for f in flist
    )
    if any_photos:
        st.markdown("**Photo previews**")
        show_photo_previews(events, files_per_event)

    st.markdown("---")

    # ════════════════════════════════════════════════════════════════════════
    # SECTION 3 — 48-hour movement map
    # ════════════════════════════════════════════════════════════════════════
    st.subheader("🗺️ 48-hour post-immobilisation movements")
    st.caption(
        "Stars mark immobilisation sites. Lines show GPS tracks for the "
        "48 hours following each darting event."
    )

    any_tracks = any(not obs.empty for obs in subject_obs.values())
    if any_tracks or events_with_loc:
        st.plotly_chart(
            build_movement_map(events, subject_obs),
            use_container_width=True,
            key="movement_map",
        )
    else:
        st.info("No GPS data available for the 48 hours after these events.")

    # Movement stats table
    stats = []
    for ev in events:
        _track_key = ev["subject_name"] or ev["subject_id"]
        obs = subject_obs.get(_track_key, pd.DataFrame())
        name = ev["subject_name"] or "Unknown"
        t = ev["time"].strftime("%Y-%m-%d %H:%M") if pd.notna(ev["time"]) else "?"
        if obs.empty:
            stats.append({
                "Subject": name, "Immob date": t,
                "GPS fixes": 0, "First fix": "—", "Last fix": "—",
                "Distance (km)": "—",
            })
        else:
            # Approximate straight-line distance sum
            lat_d = obs["lat"].diff()
            lon_d = obs["lon"].diff()
            dist_km = round((np.sqrt(lat_d**2 + lon_d**2) * 111).sum(), 2)
            stats.append({
                "Subject": name,
                "Immob date": t,
                "GPS fixes": len(obs),
                "First fix": obs["recorded_at"].iloc[0].strftime("%Y-%m-%d %H:%M"),
                "Last fix":  obs["recorded_at"].iloc[-1].strftime("%Y-%m-%d %H:%M"),
                "Distance (km)": dist_km,
            })

    if stats:
        st.dataframe(pd.DataFrame(stats), use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
