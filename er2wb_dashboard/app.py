"""
ER2WB: EarthRanger → GiraffeSpotter (WildBook) Bulk Import Formatter  v2.2 Python
Uses ecoscope EarthRangerIO to fetch giraffe survey encounter events,
formats them for GiraffeSpotter bulk import, and renames associated images.
"""

import io
import math
import sys
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st
from ecoscope.io.earthranger import EarthRangerIO

# ─── Constants ────────────────────────────────────────────────────────────────

COUNTRY_EVENT_UUIDS = {
    "rwa_aknp": "594fdd03-7c47-46cd-ac55-e6f9a7cf5e47",
    "bwa":      "3837db4e-efa3-4b7c-bf42-0e029f09565e",
    "cmr":      "c6a1ef55-f02f-40f8-800f-d22fb3cda632",
    "ken":      "3ed0d010-132a-4814-b8c3-eb1815de9378",
    "nam":      "242cc527-4ab2-4e5d-85cf-76b011720fae",
    "nanw":     "a10bb6b4-4d0f-4814-b5fe-9c4c3ec3c1ab",
    "tza":      "53a18c77-b733-4129-bb9c-15a37782b4c1",
    "uga":      "541f0ec7-1c76-4a23-93bf-c2a117287aa2",
    "zaf":      "4d5eb11e-1585-4d73-9594-461f34a75e01",
    "zmb":      "cb2eedf0-38c7-4b8c-a76c-9cc3b90b01ae",
}

TIMEZONE_MAP = {
    "BWA": "Africa/Gaborone",
    "CMR": "Africa/Douala",
    "KEN": "Africa/Nairobi",
    "NAM": "Africa/Windhoek",
    "NANW": "Africa/Windhoek",
    "TZA": "Africa/Dar_es_Salaam",
    "UGA": "Africa/Kampala",
    "ZAF": "Africa/Johannesburg",
    "ZMB": "Africa/Lusaka",
    "RWA_AKNP": "Africa/Kigali",
}

COUNTRY_SITES = {
    "BWA":      ["CHNP", "CTGR", "MWNP", "NPNP", "NTGR"],
    "CMR":      ["BNNP"],
    "KEN":      ["COCO", "EOCO", "ISCO", "LECO", "MBCO", "MMNR", "MNWC", "MOCO",
                 "MTCO", "NACO", "NAWC", "OHCO", "OICO", "OLCO", "OKWC", "PACA",
                 "RHNP", "RICO", "RUNP", "SICO", "TENP", "TWNP"],
    "NAM":      ["BACO", "BLCO", "BWNP", "DZCO", "EHGR", "GMCO", "KWCO", "MNCO",
                 "MNNP", "MSCO", "MUNP", "MYCO", "NJCO", "NLNP", "NNCO", "SACO",
                 "SBCO", "SKCO", "UIFA", "WUCO"],
    "NANW":     ["NANW"],
    "TZA":      ["SANP"],
    "UGA":      ["KVNP", "LMNP", "MFNP", "PUWR"],
    "ZAF":      ["TKGR"],
    "ZMB":      ["LVNP", "LUNP"],
    # ZCP_SMART and RWA_AKNP have non-standard data structures — handled separately
}

COUNTRY_NAMES = {
    "BWA":  "Botswana",
    "CMR":  "Cameroon",
    "KEN":  "Kenya",
    "NAM":  "Namibia",
    "NANW": "Namibia (North-West)",
    "TZA":  "Tanzania",
    "UGA":  "Uganda",
    "ZAF":  "South Africa",
    "ZMB":  "Zambia",
}

SITE_NAMES = {
    # Botswana
    "CHNP": "Chobe National Park",            "CTGR": "Central Tuli Game Reserve",
    "MWNP": "Makgadikgadi & Nxai Pan NP",     "NPNP": "Nxai Pan National Park",
    "NTGR": "Northern Tuli Game Reserve",
    # Cameroon
    "BNNP": "Bouba Ndjida National Park",
    # Namibia
    "BWNP": "Bwabwata National Park",         "EHGR": "Etosha Heights Private Reserve",
    "UIFA": "Uitkoms Farm",                   "MUNP": "Mudumu National Park",
    "NLNP": "Nkasa Lupala National Park",     "MNNP": "Mangetti National Park",
    "GMCO": "George Mukoya Conservancy",      "MNCO": "Muduva Nyangana Conservancy",
    "NJCO": "Najagna Conservancy",            "NNCO": "Nyae Nyae Conservancy",
    "SACO": "Salambala Conservancy",          "MSCO": "Mashi Conservancy",
    "MYCO": "Mayuni Conservancy",             "SBCO": "Sobbe Conservancy",
    "BACO": "Bamunu Conservancy",             "DZCO": "Dzoti Conservancy",
    "KWCO": "Kwandu Conservancy",             "BLCO": "Balyerwa Conservancy",
    "WUCO": "Wuparo Conservancy",             "SKCO": "Sikunga Conservancy",
    "NANW": "North-western Namibia",
    # Kenya
    "LMNP": "Lake Mburo",                     "RUNP": "Ruma National Park",
    "TENP": "Tsavo East National Park",       "TWNP": "Tsavo West National Park",
    "MMNR": "Maasai Mara National Reserve",   "RHNP": "Ruma Hill National Park",
    "COCO": "Ol Chorro Conservancy",          "OLCO": "Olderkesi Conservancy",
    "EOCO": "Enonkishu Conservancy",          "ISCO": "Isaaten Conservancy",
    "LECO": "Lemek Conservancy",              "MBCO": "Mbokishi Conservancy",
    "MNWC": "Mara North",                     "MOCO": "Olare Motorogi Conservancy",
    "MTCO": "Mara Triangle Conservancy",      "NACO": "Nashulai Conservancy",
    "NAWC": "Naboisho",                       "OHCO": "Olarro North Conservancy",
    "OICO": "Oloisukut Conservancy",          "OKWC": "Ol Kinyei",
    "PACA": "Pardamat Conservation Area",     "RICO": "Ripoi Conservancy",
    "SICO": "Siana Conservancy",
    # Tanzania
    "SANP": "Serengeti National Park",
    # Uganda
    "KVNP": "Kidepo Valley National Park",    "PUWR": "Pian Upe Wildlife Reserve",
    "MFNP": "Murchison Falls National Park",
    # South Africa
    "TKGR": "Tswalu Kalahari Reserve",
    # Zambia
    "LVNP": "Luangwa",                        "LUNP": "Luambe National Park",
}

SPECIES_MAP = {
    "Masai":       {"Luangwa": "tippelskirchi thornicrofti",
                    "Masai":   "tippelskirchi tippelskirchi"},
    "Northern":    {"Kordofan":     "camelopardalis antiquorum",
                    "Nubian":       "camelopardalis camelopardalis",
                    "West African": "camelopardalis peralta"},
    "Reticulated": {"Reticulated": "reticulata"},
    "Southern":    {"Angolan":      "giraffa angolensis",
                    "South African":"giraffa giraffa"},
}

# Default species/subspecies per country — used to auto-fill on country change
COUNTRY_SPECIES = {
    "BWA":      ("Southern",    "South African"),
    "CMR":      ("Northern",    "West African"),
    "KEN":      ("Masai",       "Masai"),
    "NAM":      ("Southern",    "Angolan"),
    "NANW":     ("Southern",    "Angolan"),
    "TZA":      ("Masai",       "Masai"),
    "UGA":      ("Northern",    "Nubian"),
    "ZAF":      ("Southern",    "South African"),
    "ZMB":      ("Masai",       "Luangwa"),
    "RWA_AKNP": ("Northern",    "Nubian"),
}

AGE_MAP = {"ad": "adult", "sa": "juvenile", "ju": "calf", "ca": "calf", "u": "unknown"}
SEX_MAP = {"f": "female", "m": "male", "u": "unknown"}


# ─── Session state ─────────────────────────────────────────────────────────────

def _init_session_state():
    """Initialise persistent session state keys with sensible defaults."""
    defaults = {
        # ── EarthRanger session ─────────────────────────────────────────────────
        "er_client":        None,
        "er_authenticated": False,
        "er_event_types":   [],    # [{label, uuid, category}] fetched from ER after login
        "event_type_sel":   "",    # label of selected event type
        "event_type_uuid":  "",    # UUID of selected event type (empty = use category)
        # ── Processed data (cleared by Reset) ──────────────────────────────────
        "processed_df":         None,
        "gs_data":              None,
        "renamed_files":        {},
        "download_zip":         None,
        "n_matched":            None,
        "raw_events":           [],
        "available_observers":  [],
        # ── Settings (persisted across reruns) ─────────────────────────────────
        "er_observer_filter":   "",    # "" = all observers
        "er_instance":     "twiga.pamdas.org",
        "er_login_user":   "",
        "er_login_pass":   "",
        "er_observer":     "",    # full name → used to filter events by reporter
        "er_initials":     "",    # initials for image filenames (auto-derived, editable)
        "has_images":      True,  # whether to show Step 3 image processing
        "gs_org":          "Giraffe Conservation Foundation",
        "gs_username":     "",
        "date_start":      date.today() - timedelta(days=10),
        "date_end":        date.today(),
        "country_sel":     list(COUNTRY_SITES.keys())[0],
        "site_sel":        None,
        "species_sel":     list(SPECIES_MAP.keys())[0],
        "subsp_sel":       None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def _reset_results():
    """Clear processed data but keep all settings."""
    st.session_state.processed_df         = None
    st.session_state.gs_data              = None
    st.session_state.renamed_files        = {}
    st.session_state.download_zip         = None
    st.session_state.n_matched            = None
    st.session_state.raw_events           = []
    st.session_state.available_observers  = []


def _disconnect_er():
    """Log out of EarthRanger and clear all derived data."""
    st.session_state.er_client        = None
    st.session_state.er_authenticated = False
    st.session_state.er_event_types   = []
    st.session_state.event_type_sel   = ""
    st.session_state.event_type_uuid  = ""
    _reset_results()


# ─── ER client ─────────────────────────────────────────────────────────────────

def _make_er_client(instance: str, username: str, password: str) -> EarthRangerIO:
    """Create an EarthRangerIO client using username/password auth."""
    return EarthRangerIO(server=f"https://{instance}",
                         username=username,
                         password=password)


# ─── Event-type fetch ─────────────────────────────────────────────────────────

def _fetch_event_types(client: EarthRangerIO) -> list:
    """
    Fetch all event types from EarthRanger.
    Returns a sorted list of dicts: [{label, uuid, category}].
    Giraffe-related types are sorted to the top.
    Falls back to [] if the call fails or the method is unavailable.
    """
    try:
        df = client.get_event_types()
        if df is None or df.empty:
            return []
        rows = []
        for _, row in df.iterrows():
            label = str(row.get("display", row.get("value", ""))).strip()
            uuid  = str(row.get("id", "")).strip()
            cat   = str(row.get("category", "")).strip()
            if label and uuid and uuid.lower() not in ("nan", "none", ""):
                rows.append({"label": label, "uuid": uuid, "category": cat})
        # Filter to giraffe survey encounter types only
        rows = [r for r in rows if "giraffe survey encounter" in r["label"].lower()]
        # Sort alphabetically
        rows.sort(key=lambda x: x["label"].lower())
        return rows
    except Exception:
        return []


def _on_country_change():
    """Auto-fill species and subspecies when country changes."""
    country = st.session_state.get("country_sel", "")
    if country in COUNTRY_SPECIES:
        sp, sub = COUNTRY_SPECIES[country]
        st.session_state["species_sel"] = sp
        st.session_state["subsp_sel"]   = sub
    # Reset site selection
    sites = COUNTRY_SITES.get(country, [])
    if st.session_state.get("site_sel") not in sites:
        st.session_state["site_sel"] = sites[0] if sites else None


# ─── Helpers ──────────────────────────────────────────────────────────────────

def get_initials(full_name: str) -> str:
    parts = full_name.strip().split()
    return "".join(p[0].upper() for p in parts if p)


def dest_point(lon: float, lat: float, bearing_deg: float, distance_m: float):
    """Haversine destination point — mirrors R's geosphere::destPoint."""
    R = 6371000.0
    lr = math.radians(lat)
    br = math.radians(bearing_deg)
    lat2 = math.asin(
        math.sin(lr) * math.cos(distance_m / R)
        + math.cos(lr) * math.sin(distance_m / R) * math.cos(br)
    )
    lon2 = math.radians(lon) + math.atan2(
        math.sin(br) * math.sin(distance_m / R) * math.cos(lr),
        math.cos(distance_m / R) - math.sin(lr) * math.sin(lat2),
    )
    return math.degrees(lon2), math.degrees(lat2)


def get_exif_datetime(img_bytes: bytes) -> datetime:
    """Extract DateTimeOriginal from JPEG EXIF; falls back to now()."""
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS
        img  = Image.open(io.BytesIO(img_bytes))
        exif = img._getexif()
        if exif:
            for tag_id, val in exif.items():
                if TAGS.get(tag_id) == "DateTimeOriginal":
                    return datetime.strptime(val, "%Y:%m:%d %H:%M:%S")
    except Exception:
        pass
    return datetime.now()


def get_exif_gps_direction(img_bytes: bytes):
    """
    Extract GPSImgDirection from JPEG EXIF (ZMB only).
    Returns bearing in degrees, or None if not present.
    """
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS, GPSTAGS
        img  = Image.open(io.BytesIO(img_bytes))
        exif = img._getexif()
        if not exif:
            return None
        for tag_id, val in exif.items():
            if TAGS.get(tag_id) == "GPSInfo":
                for gps_tag_id, gps_val in val.items():
                    if GPSTAGS.get(gps_tag_id) == "GPSImgDirection":
                        if hasattr(gps_val, "__float__"):
                            return float(gps_val)
                        if isinstance(gps_val, tuple) and len(gps_val) == 2:
                            return gps_val[0] / gps_val[1]
    except Exception:
        pass
    return None


def _excel_bytes(df: pd.DataFrame) -> bytes:
    """Serialise a DataFrame to an in-memory Excel file and return raw bytes."""
    out = df.copy()
    # Drop internal helper columns (prefixed with _)
    internal_cols = [c for c in out.columns if c.startswith("_")]
    out = out.drop(columns=internal_cols)
    # Excel cannot handle tz-aware datetimes — strip timezone from any such columns
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            if hasattr(out[col].dt, "tz") and out[col].dt.tz is not None:
                out[col] = out[col].dt.tz_localize(None)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        out.to_excel(writer, index=False)
    buf.seek(0)
    return buf.read()


# ─── ER data fetch ─────────────────────────────────────────────────────────────

def fetch_er_events(country: str,
                    date_start: date, date_end: date,
                    er_client: EarthRangerIO,
                    event_type_uuid: str = None,
                    event_category: str = None) -> list:
    """
    Fetch giraffe survey events via ecoscope EarthRangerIO.get_events().
    Returns a list of dicts that process_er_data expects.

    Parameters
    ----------
    event_type_uuid : str | None
        ER event type UUID to filter by (preferred — works for any ER instance).
    event_category : str | None
        ER event category string to filter by (fallback when no UUID given).
        If neither is provided, falls back to the legacy country→UUID/category mapping.
    """
    kwargs = dict(
        since=date_start.strftime("%Y-%m-%dT00:00:00Z"),
        until=date_end.strftime("%Y-%m-%dT23:59:59Z"),
        include_details=True,
        drop_null_geometry=False,
    )

    if event_type_uuid:
        kwargs["event_type"] = [event_type_uuid]
    elif event_category:
        kwargs["event_category"] = event_category
    else:
        # Legacy fallback: derive from country
        country_lower = country.lower()
        if country_lower in COUNTRY_EVENT_UUIDS:
            kwargs["event_type"] = [COUNTRY_EVENT_UUIDS[country_lower]]
        else:
            cat = "monitoring_zmb" if country == "ZMB" else f"monitoring_{country_lower}"
            kwargs["event_category"] = cat

    gdf = er_client.get_events(**kwargs)

    if gdf is None or gdf.empty:
        return []

    # Ensure id and serial_number are columns (ecoscope may set id as the index)
    if "id" not in gdf.columns:
        gdf = gdf.reset_index()

    # Convert GeoDataFrame rows to dicts that match what process_er_data expects
    results = []
    for _, row in gdf.iterrows():
        rec = row.to_dict()

        # Geometry → location dict
        geom = rec.pop("geometry", None)
        if geom is not None and hasattr(geom, "x"):
            rec["location"] = {"longitude": geom.x, "latitude": geom.y}
        else:
            rec.setdefault("location", {})

        # Ensure reported_by is a dict with a "name" key.
        # Ecoscope may: (a) keep it as a nested dict, (b) flatten it into
        # reported_by_name / reported_by_id columns, or (c) stringify the dict.
        rb = rec.get("reported_by")
        if isinstance(rb, dict) and rb.get("name"):
            pass  # already correct
        else:
            rb_name = str(rec.get("reported_by_name") or "").strip()
            rb_id   = str(rec.get("reported_by_id")   or "").strip()
            # fallback: try parsing a stringified dict  e.g. "{'name': 'Jane'}"
            if not rb_name and isinstance(rb, str) and rb.startswith("{"):
                try:
                    import ast
                    _parsed = ast.literal_eval(rb)
                    if isinstance(_parsed, dict):
                        rb_name = str(_parsed.get("name") or "").strip()
                        rb_id   = str(_parsed.get("id")   or "").strip()
                except Exception:
                    pass
            rec["reported_by"] = {"name": rb_name, "id": rb_id}

        # Ensure event_details is a dict
        ed = rec.get("event_details")
        if not isinstance(ed, dict):
            rec["event_details"] = {}

        results.append(rec)

    return results


# ─── Data processing ───────────────────────────────────────────────────────────

def process_er_data(raw_events: list, country: str, er_username: str,
                    date_start: date, date_end: date) -> pd.DataFrame:
    """
    Flatten raw ER event JSON into a tidy DataFrame.
    One row per individual giraffe (Herd record), joined with event-level fields.
    """
    country_lower = country.lower()
    herd_rows, evt_rows = [], []

    for evt in raw_events:
        try:
            evt_date = pd.to_datetime(evt.get("time", "")).date()
            if not (date_start <= evt_date <= date_end):
                continue
        except Exception:
            continue

        rep      = evt.get("reported_by") or {}
        rep_name = rep.get("name", "")

        if er_username.strip() and country_lower != "rwa_aknp":
            if rep_name != er_username.strip():
                continue

        loc = evt.get("location") or {}
        lat = loc.get("latitude") or loc.get("lat")
        lon = loc.get("longitude") or loc.get("lon")
        det = evt.get("event_details") or {}

        evt_rows.append({
            "id":                          evt.get("id"),
            "serial_number":               evt.get("serial_number"),
            "time":                        evt.get("time"),
            "event_type":                  evt.get("event_type"),
            "event_category":              evt.get("event_category"),
            "location_latitude":           lat,
            "location_longitude":          lon,
            "reported_by_name":            rep_name,
            "reported_by_id":              rep.get("id"),
            "event_details_herd_size":     det.get("herd_size"),
            "event_details_herd_notes":    det.get("herd_notes"),
            "event_details_river_system":  det.get("river_system"),
            "event_details_image_prefix":  det.get("image_prefix"),
            "event_details_herd_dire":     det.get("herd_dire") or det.get("direction"),
            "event_details_herd_dist":     det.get("herd_dist") or det.get("distance"),
        })

        herd_list = det.get("Herd") or []
        if isinstance(herd_list, list) and herd_list:
            for giraffe in herd_list:
                if not isinstance(giraffe, dict):
                    continue
                gr = giraffe.get("giraffe_right")
                gl = giraffe.get("giraffe_left")
                herd_rows.append({
                    "id":            evt.get("id"),
                    "giraffe_id":    giraffe.get("giraffe_id", ""),
                    "giraffe_age":   giraffe.get("giraffe_age", ""),
                    "giraffe_sex":   giraffe.get("giraffe_sex", ""),
                    "giraffe_right": str(int(gr)).zfill(4) if gr is not None else None,
                    "giraffe_left":  str(int(gl)).zfill(4) if gl is not None else None,
                    "giraffe_notes": giraffe.get("giraffe_notes", ""),
                })
        else:
            herd_rows.append({
                "id": evt.get("id"),
                "giraffe_id": "", "giraffe_age": "", "giraffe_sex": "",
                "giraffe_right": None, "giraffe_left": None, "giraffe_notes": "",
            })

    if not evt_rows:
        return pd.DataFrame()

    herd_df = pd.DataFrame(herd_rows)
    evt_df  = pd.DataFrame(evt_rows)

    final = herd_df.merge(evt_df, on="id", how="left").rename(columns={
        "id":                         "evt_id",
        "serial_number":              "evt_serial",
        "location_latitude":          "evt_lat",
        "location_longitude":         "evt_lon",
        "time":                       "evt_dttm",
        "event_category":             "evt_cat",
        "event_type":                 "evt_type",
        "reported_by_id":             "usr_id",
        "reported_by_name":           "usr_name",
        "giraffe_id":                 "gir_giraffeId",
        "giraffe_age":                "gir_giraffeAge",
        "giraffe_sex":                "gir_giraffeSex",
        "giraffe_right":              "gir_giraffeRight",
        "giraffe_left":               "gir_giraffeLeft",
        "giraffe_notes":              "gir_giraffeNotes",
        "event_details_herd_size":    "gir_herdSize",
        "event_details_herd_notes":   "gir_herdNotes",
        "event_details_river_system": "gir_riverSystem",
        "event_details_image_prefix": "gir_imagePrefix",
        "event_details_herd_dire":    "gir_direction",
        "event_details_herd_dist":    "gir_distance",
    })

    def clean_id(gid):
        if pd.isna(gid) or str(gid).strip().lower() in ("unknown", ""):
            return ""
        gid = str(gid)
        return gid.split("_")[0] if "_" in gid else gid

    final["gir_giraffeId"] = final["gir_giraffeId"].apply(clean_id)

    final["evt_lon_original"] = final["evt_lon"]
    final["evt_lat_original"] = final["evt_lat"]
    final["evt_notes"]        = None

    def _reproject(row):
        try:
            if pd.notna(row["gir_direction"]) and pd.notna(row["gir_distance"]):
                new_lon, new_lat = dest_point(
                    float(row["evt_lon_original"]), float(row["evt_lat_original"]),
                    float(row["gir_direction"]), float(row["gir_distance"]),
                )
                note = (
                    f"reprojected from lon={row['evt_lon_original']:.6f}, "
                    f"lat={row['evt_lat_original']:.6f} "
                    f"(bearing={float(row['gir_direction']):.0f}°, "
                    f"distance={float(row['gir_distance']):.0f}m)"
                )
                return pd.Series({"evt_lon": new_lon, "evt_lat": new_lat, "evt_notes": note})
        except Exception:
            pass
        return pd.Series({"evt_lon": row["evt_lon"], "evt_lat": row["evt_lat"],
                           "evt_notes": None})

    final[["evt_lon", "evt_lat", "evt_notes"]] = final.apply(_reproject, axis=1)

    return final


# ─── GiraffeSpotter formatting ─────────────────────────────────────────────────

def format_gs_data(final_df: pd.DataFrame, country: str, site: str,
                   gs_username: str, gs_org: str,
                   species_epithet: str, initials: str) -> pd.DataFrame:
    """Convert processed ER DataFrame to GiraffeSpotter bulk import format."""
    if final_df.empty:
        return pd.DataFrame()

    local_tz  = TIMEZONE_MAP.get(country, "UTC")
    site_name = SITE_NAMES.get(site, site)

    df = final_df.copy()

    # Normalise evt_dttm to UTC — cast via str first so pd.to_datetime can
    # parse both string timestamps and already-aware pd.Timestamp objects
    # regardless of pandas version behaviour with mixed types.
    df["evt_dttm_utc"] = pd.to_datetime(
        df["evt_dttm"].astype(str), utc=True, errors="coerce"
    )
    df["evt_dttm_local"] = df["evt_dttm_utc"].dt.tz_convert(local_tz)

    df["gir_giraffeAge"] = df["gir_giraffeAge"].apply(
        lambda x: AGE_MAP.get(str(x).lower().strip(), str(x))
        if pd.notna(x) and x != "" else "")
    df["gir_giraffeSex"] = df["gir_giraffeSex"].apply(
        lambda x: SEX_MAP.get(str(x).lower().strip(), str(x))
        if pd.notna(x) and x != "" else "")

    # Compute per-encounter age/sex counts on a minimal subset so the merge
    # never creates _x/_y column conflicts (pandas 2.2 groupby.apply returns
    # all input columns in the result even with include_groups=False).
    _age = df["gir_giraffeAge"]
    _sex = df["gir_giraffeSex"]
    counts = (
        df[["evt_id"]].assign(
            ad=(_age == "adult").astype(int),
            af=((_age == "adult")    & (_sex == "female")).astype(int),
            am=((_age == "adult")    & (_sex == "male")).astype(int),
            sa=(_age == "juvenile").astype(int),
            sf=((_age == "juvenile") & (_sex == "female")).astype(int),
            sm=((_age == "juvenile") & (_sex == "male")).astype(int),
            ca=(_age == "calf").astype(int),
        )
        .groupby("evt_id", as_index=False)
        .sum()
    )
    df = df.merge(counts, on="evt_id", how="left")

    def make_media(row, side):
        num    = row.get(f"gir_giraffe{side}")
        prefix = row.get("gir_imagePrefix")
        dt     = row.get("evt_dttm_local")
        # Skip if any required field is missing or explicitly "NA"
        if num is None or prefix is None:
            return None
        if isinstance(num, float) and pd.isna(num):
            return None
        if isinstance(prefix, float) and pd.isna(prefix):
            return None
        num = str(num).strip()
        if num.upper() in ("NA", "NAN", "NONE", ""):
            return None
        date_str = dt.strftime("%Y%m%d") if pd.notna(dt) else "UNKNOWN"
        return f"{country}_{site}_{date_str}_{initials}_{prefix}{num}.JPG".upper()

    df["media0"] = df.apply(lambda r: make_media(r, "Right"), axis=1)
    df["media1"] = df.apply(lambda r: make_media(r, "Left"),  axis=1)

    def safe_int(x):
        try:
            return int(float(x))
        except (TypeError, ValueError):
            return None

    gs = pd.DataFrame({
        "_evt_serial":              df["evt_serial"],   # internal — stripped before export
        "Survey.vessel":            "vehicle_based_photographic",
        "Survey.id":                df["evt_dttm_local"].apply(
            lambda d: f"{country}_{site}_{d.strftime('%Y%m')}" if pd.notna(d) else ""),
        "Occurrence.occurrenceID":  df.apply(
            lambda r: f"{country}_{site}_{r['evt_dttm_local'].strftime('%Y%m%d%H%M%S')}"
                      if pd.notna(r["evt_dttm_local"]) else "", axis=1),
        "Encounter.decimalLongitude":   df["evt_lon"],
        "Encounter.decimalLatitude":    df["evt_lat"],
        "Encounter.locationID":         site_name,
        "Encounter.year":               df["evt_dttm_local"].dt.year,
        "Encounter.month":              df["evt_dttm_local"].dt.month,
        "Encounter.day":                df["evt_dttm_local"].dt.day,
        "Encounter.hour":               df["evt_dttm_local"].dt.hour,
        "Encounter.minutes":            df["evt_dttm_local"].dt.minute,
        "Encounter.submitterID":        gs_username,
        "Occurrence.groupSize":         df["gir_herdSize"].apply(safe_int),
        "Occurrence.numAdults":         df["ad"].fillna(0).astype(int),
        "Occurrence.numAdultFemales":   df["af"].fillna(0).astype(int),
        "Occurrence.numAdultMales":     df["am"].fillna(0).astype(int),
        "Occurrence.numSubAdults":      df["sa"].fillna(0).astype(int),
        "Occurrence.numSubFemales":     df["sf"].fillna(0).astype(int),
        "Occurrence.numSubMales":       df["sm"].fillna(0).astype(int),
        "Occurrence.numCalves":         df["ca"].fillna(0).astype(int),
        "Occurrence.distance":          df["gir_distance"],
        "Occurrence.bearing":           df["gir_direction"],
        "Encounter.individualID":       df["gir_giraffeId"].fillna(""),
        "Encounter.sex":                df["gir_giraffeSex"],
        "Encounter.lifeStage":          df["gir_giraffeAge"],
        "Encounter.genus":              "Giraffa",
        "Encounter.specificEpithet":    species_epithet,
        "Encounter.occurrenceRemarks":  df.apply(
            lambda r: "; ".join(filter(None, [
                str(r["gir_giraffeNotes"]).strip() if pd.notna(r["gir_giraffeNotes"]) and str(r["gir_giraffeNotes"]).strip() else "",
                str(r["evt_notes"]).strip()        if pd.notna(r.get("evt_notes")) and str(r.get("evt_notes", "")).strip() else "",
            ])), axis=1),
        "Encounter.mediaAsset0":        df["media0"],
        "Encounter.mediaAsset1":        df["media1"],
    })

    # Clean up filenames that ended up with NA in place of a photo number
    def _clean_media(v):
        if pd.isna(v) or str(v).strip() in ("", "nan", "None"):
            return None
        if str(v).upper().endswith("NA.JPG") or str(v).upper().endswith("NA.JPEG"):
            return None
        return v

    gs["Encounter.mediaAsset0"] = gs["Encounter.mediaAsset0"].apply(_clean_media)
    gs["Encounter.mediaAsset1"] = gs["Encounter.mediaAsset1"].apply(_clean_media)

    return gs


# ─── Validation ────────────────────────────────────────────────────────────────

def validate_gs_data(gs_df: pd.DataFrame) -> list:
    """
    Check GiraffeSpotter data for common issues.
    Returns a list of {"level": str, "icon": str, "message": str} dicts.
    Uses the internal _evt_serial column (if present) to list ER serial numbers
    next to issues so the user knows exactly which events need fixing.
    """
    issues = []

    def _serials_for(mask) -> str:
        """Return a compact list of ER serial numbers for rows where mask is True."""
        if "_evt_serial" not in gs_df.columns:
            return ""
        serials = (
            gs_df.loc[mask, "_evt_serial"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )
        if not serials:
            return ""
        label = ", ".join(serials[:10])
        if len(serials) > 10:
            label += f" … (+{len(serials) - 10} more)"
        return f" — ER serials: {label}"

    # Missing coordinates
    mask = gs_df[["Encounter.decimalLongitude",
                  "Encounter.decimalLatitude"]].isna().any(axis=1)
    n = mask.sum()
    if n:
        issues.append({"level": "warning", "icon": "⚠️",
                        "message": f"{n} row(s) have missing coordinates{_serials_for(mask)}"})

    # Missing age / life stage
    mask = (gs_df["Encounter.lifeStage"].fillna("") == "")
    n = mask.sum()
    if n:
        issues.append({"level": "info", "icon": "ℹ️",
                        "message": f"{n} row(s) have no age / life stage recorded{_serials_for(mask)}"})

    # Missing sex
    mask = (gs_df["Encounter.sex"].fillna("") == "")
    n = mask.sum()
    if n:
        issues.append({"level": "info", "icon": "ℹ️",
                        "message": f"{n} row(s) have no sex recorded{_serials_for(mask)}"})

    # No image filename (missing prefix or photo numbers in ER)
    def _no_media(v):
        return pd.isna(v) or str(v).strip() in ("", "nan", "None")
    mask = gs_df["Encounter.mediaAsset0"].apply(_no_media)
    n = mask.sum()
    if n:
        issues.append({"level": "warning", "icon": "⚠️",
                        "message": (f"{n} row(s) have no image filename — "
                                    f"check image_prefix and photo numbers in EarthRanger"
                                    f"{_serials_for(mask)}")})

    if not issues:
        issues.append({"level": "success", "icon": "✅",
                        "message": "No data issues detected — looking good!"})
    return issues


# ─── Image processing ──────────────────────────────────────────────────────────

def process_images_zip(zip_bytes: bytes, country: str, site: str,
                       initials: str,
                       on_progress=None) -> tuple:
    """
    Extract ZIP, rename every JPEG using EXIF datetime.
    For ZMB, also extracts GPSImgDirection from each image.

    Parameters
    ----------
    on_progress : callable(float) | None
        Called after each image with a fraction 0.0–1.0.  Use to drive a
        st.progress bar.

    Returns
    -------
    renamed_files : dict  {new_name: bytes}
    rename_log    : pd.DataFrame  with Original / Renamed / Status columns
    gps_lookup    : dict  {full_image_stem: bearing_degrees}  (ZMB only)
    """
    renamed, log_rows, gps_lookup = {}, [], {}

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        jpg_names = [n for n in zf.namelist()
                     if n.lower().endswith((".jpg", ".jpeg"))
                     and not Path(n).name.startswith(".")]

        total = len(jpg_names) or 1   # avoid divide-by-zero

        for idx, name in enumerate(jpg_names):
            try:
                img_bytes = zf.read(name)
                dttm      = get_exif_datetime(img_bytes)
                date_str  = dttm.strftime("%Y%m%d")

                # ── FIX: preserve alphanumeric stems (e.g. 4D1A2407) ──────────
                stem = Path(name).stem
                num  = stem.zfill(4) if stem.isdigit() else stem
                # ─────────────────────────────────────────────────────────────

                new_name         = f"{country}_{site}_{date_str}_{initials}_{num}.JPG".upper()
                renamed[new_name] = img_bytes

                # ZMB: capture GPS bearing from EXIF for coordinate reprojection
                gps_dir  = None
                gps_note = ""
                if country == "ZMB":
                    gps_dir = get_exif_gps_direction(img_bytes)
                    if gps_dir is not None:
                        # e.g. ZMB_LVNP_20250817_FO_4D1A2407.JPG → 4D1A2407
                        full_img_stem = new_name.rsplit("_", 1)[-1].replace(".JPG", "")
                        gps_lookup[full_img_stem] = gps_dir
                        gps_note = f" | GPS dir: {gps_dir:.1f}°"

                log_rows.append({
                    "Original": Path(name).name,
                    "Renamed":  new_name,
                    "Status":   f"✅ OK{gps_note}",
                })
            except Exception as exc:
                log_rows.append({"Original": Path(name).name,
                                  "Renamed":  "",
                                  "Status":   f"❌ {exc}"})

            if on_progress:
                on_progress((idx + 1) / total)

    return renamed, pd.DataFrame(log_rows), gps_lookup


def apply_exif_reprojection(processed_df: pd.DataFrame,
                             gps_lookup: dict) -> pd.DataFrame:
    """
    ZMB only: for rows that have no manual direction but do have a distance
    and an image prefix, look up the GPSImgDirection bearing from the EXIF
    GPS lookup dict and reproject the coordinates.
    """
    if not gps_lookup or processed_df.empty:
        return processed_df

    df = processed_df.copy()

    def _reproject_exif(row):
        has_manual = (pd.notna(row.get("gir_direction"))
                      and str(row.get("gir_direction", "")).strip() != "")
        has_dist   = pd.notna(row.get("gir_distance"))
        has_prefix = pd.notna(row.get("gir_imagePrefix"))

        if has_manual or not has_dist or not has_prefix:
            return pd.Series({"evt_lon": row["evt_lon"],
                               "evt_lat": row["evt_lat"],
                               "evt_notes": row.get("evt_notes")})

        prefix     = str(row["gir_imagePrefix"])
        candidates = []
        for side in ("gir_giraffeRight", "gir_giraffeLeft"):
            val = row.get(side)
            if pd.notna(val) and val is not None:
                candidates.append(f"{prefix}{val}")

        bearing = next((gps_lookup[c] for c in candidates if c in gps_lookup), None)

        if bearing is None:
            return pd.Series({"evt_lon": row["evt_lon"],
                               "evt_lat": row["evt_lat"],
                               "evt_notes": row.get("evt_notes")})
        try:
            new_lon, new_lat = dest_point(
                float(row["evt_lon_original"]), float(row["evt_lat_original"]),
                float(bearing), float(row["gir_distance"]),
            )
            note = (
                f"reprojected from lon={row['evt_lon_original']:.6f}, "
                f"lat={row['evt_lat_original']:.6f} "
                f"(bearing={bearing:.0f}° from EXIF, "
                f"distance={float(row['gir_distance']):.0f}m)"
            )
            return pd.Series({"evt_lon": new_lon, "evt_lat": new_lat, "evt_notes": note})
        except Exception:
            return pd.Series({"evt_lon": row["evt_lon"],
                               "evt_lat": row["evt_lat"],
                               "evt_notes": row.get("evt_notes")})

    df[["evt_lon", "evt_lat", "evt_notes"]] = df.apply(_reproject_exif, axis=1)
    return df


def build_download_zip(renamed_files: dict, gs_data: pd.DataFrame,
                       country: str, site: str) -> tuple:
    """
    Build ZIP containing matched images + GiraffeSpotter Excel.
    Returns (zip_bytes, n_matched_images).
    """
    gs_asset_names = set()
    for col in ("Encounter.mediaAsset0", "Encounter.mediaAsset1"):
        if col in gs_data.columns:
            gs_asset_names.update(
                str(v).upper() for v in gs_data[col].dropna()
                if str(v) not in ("", "nan", "None")
            )

    matched = {k: v for k, v in renamed_files.items() if k.upper() in gs_asset_names}

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname, fbytes in matched.items():
            zf.writestr(fname, fbytes)

        xls_name = f"GS_bulkimport_{country}{site}_{date.today().strftime('%Y%m%d')}.xlsx"
        zf.writestr(xls_name, _excel_bytes(gs_data))

    buf.seek(0)
    return buf.read(), len(matched)


# ─── Streamlit UI ─────────────────────────────────────────────────────────────

def main():
    _init_session_state()



    # ══════════════════════════════════════════════════════════════════════════
    # STEP 1 — EarthRanger login
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("---")
    st.subheader("🔑 Step 1: Connect to EarthRanger")

    if not st.session_state.er_authenticated:
        er_c1, er_c2, er_c3 = st.columns(3)
        with er_c1:
            st.text_input(
                "Instance", key="er_instance",
                help="Without https://, e.g. twiga.pamdas.org")
        with er_c2:
            st.text_input("Username", key="er_login_user")
        with er_c3:
            st.text_input("Password", type="password", key="er_login_pass")

        if st.button("Connect", type="primary"):
            usr = st.session_state.er_login_user.strip()
            pwd = st.session_state.er_login_pass.strip()
            ins = st.session_state.er_instance.strip()
            if not usr or not pwd or not ins:
                st.error("Please fill in all three fields.")
            else:
                with st.spinner("Connecting to EarthRanger…"):
                    try:
                        client = _make_er_client(ins, usr, pwd)
                        # Lightweight auth check using ecoscope method
                        client.get_sources(limit=1)
                        st.session_state.er_client        = client
                        st.session_state.er_authenticated = True
                        # Fetch event types for the selector
                        st.session_state.er_event_types = _fetch_event_types(client)
                        st.rerun()
                    except Exception as exc:
                        status = getattr(getattr(exc, "response", None), "status_code", None)
                        if status == 401:
                            st.error("❌ Login failed — check your username and password.")
                        elif status:
                            st.error(f"❌ API error {status}. Check the instance URL.")
                        else:
                            st.error(f"❌ Could not connect: {exc}")
        st.stop()   # nothing below renders until logged in

    # ── Logged-in banner ──────────────────────────────────────────────────────
    lc1, lc2, lc3 = st.columns([4, 1, 1])
    with lc1:
        st.success(
            f"✅ Connected to **{st.session_state.er_instance}** "
            f"as **{st.session_state.er_login_user}**")
    with lc2:
        if st.session_state.processed_df is not None:
            if st.button("🔄 Start Over", use_container_width=True):
                _reset_results()
                st.rerun()
    with lc3:
        if st.button("Disconnect", use_container_width=True):
            _disconnect_er()
            st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 1 (cont.) — Survey & GiraffeSpotter settings
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("---")
    st.subheader("⚙️ Step 1 (cont.): Settings")
    instance = st.session_state.er_instance   # used downstream

    # ── Survey details ────────────────────────────────────────────────────────
    st.markdown("**Survey**")

    # Country / site (country change auto-fills species/subspecies)
    country_keys = list(COUNTRY_SITES.keys())
    if st.session_state.country_sel not in country_keys:
        st.session_state.country_sel = country_keys[0]

    sv_c1, sv_c2 = st.columns(2)
    with sv_c1:
        country = st.selectbox(
            "Country", country_keys, key="country_sel",
            format_func=lambda c: COUNTRY_NAMES.get(c, c),
            on_change=_on_country_change)
    with sv_c2:
        site_options = COUNTRY_SITES.get(country, [])
        if st.session_state.site_sel not in site_options:
            st.session_state.site_sel = site_options[0] if site_options else None
        site = st.selectbox(
            "Site", site_options, key="site_sel",
            format_func=lambda s: SITE_NAMES.get(s, s))

    # Dates
    dt_c1, dt_c2 = st.columns(2)
    with dt_c1:
        date_start = st.date_input("Start date", key="date_start")
    with dt_c2:
        date_end   = st.date_input("End date",   key="date_end")

    # ── Event type selector ───────────────────────────────────────────────────
    st.markdown("**EarthRanger event type**")
    st.caption("Select the giraffe survey encounter event type to fetch from EarthRanger.")

    er_event_types = st.session_state.er_event_types   # [{label, uuid, category}]

    # Resolve selected event type UUID
    event_type_uuid  = ""
    event_type_label = ""

    if er_event_types:
        et_labels = [et["label"] for et in er_event_types]
        if st.session_state.event_type_sel not in et_labels:
            st.session_state.event_type_sel = et_labels[0]

        event_type_label = st.selectbox(
            "Encounter event type", et_labels, key="event_type_sel")
        matched = next((et for et in er_event_types
                        if et["label"] == event_type_label), None)
        event_type_uuid = matched["uuid"] if matched else ""
    else:
        # Fallback: manual UUID entry (e.g. if get_event_types() is unavailable)
        st.info("Could not fetch event types from this ER instance. "
                "Enter the event type UUID manually, or leave blank to use the "
                "default country-based category filter.")
        et_c1, et_c2 = st.columns(2)
        with et_c1:
            event_type_uuid = st.text_input(
                "Event type UUID (optional)",
                value=st.session_state.event_type_uuid,
                key="event_type_uuid",
                help="e.g. 3837db4e-efa3-4b7c-bf42-0e029f09565e")

    # ── Observer filter ───────────────────────────────────────────────────────
    st.markdown("**Observer filter**")
    _obs_available = st.session_state.available_observers
    if _obs_available:
        _obs_options = ["All observers"] + _obs_available
        if st.session_state.er_observer_filter not in _obs_options:
            st.session_state.er_observer_filter = "All observers"
        st.selectbox("Export data for", _obs_options, key="er_observer_filter")
    else:
        st.caption("Fetch data in Step 2 to see available observers.")

    st.markdown("---")

    # ── 1c: GiraffeSpotter ────────────────────────────────────────────────────
    st.markdown("**GiraffeSpotter**")
    gs_c1, gs_c2, gs_c3, gs_c4 = st.columns(4)

    with gs_c1:
        gs_username = st.text_input("GiraffeSpotter username", key="gs_username")
        gs_org      = st.session_state.gs_org   # kept in state but not shown prominently

    with gs_c2:
        initials = st.text_input(
            "Observer initials (e.g., CM)", key="er_initials",
            help="Used in renamed image filenames, e.g. CM → NAM_EHGR_20250101_CM_0001.JPG.")

    with gs_c3:
        # Persist species selection
        species_keys = list(SPECIES_MAP.keys())
        if st.session_state.species_sel not in species_keys:
            st.session_state.species_sel = species_keys[0]
        species_choice = st.selectbox("Species", species_keys, key="species_sel")

    with gs_c4:
        subsp_options = list(SPECIES_MAP[species_choice].keys())
        if st.session_state.subsp_sel not in subsp_options:
            st.session_state.subsp_sel = subsp_options[0]
        subsp_choice    = st.selectbox("Subspecies", subsp_options, key="subsp_sel")
        species_epithet = SPECIES_MAP[species_choice][subsp_choice]

    st.session_state["has_images"] = True

    # ── Auto-reprocess when observer filter changes (no re-fetch needed) ─────
    _obs_filter = st.session_state.er_observer_filter
    _obs_for_proc = "" if _obs_filter in ("", "All observers") else _obs_filter
    _prev_filter  = st.session_state.get("_prev_observer_filter", _obs_filter)
    if (st.session_state.raw_events
            and st.session_state.processed_df is not None
            and _prev_filter != _obs_filter):
        st.session_state._prev_observer_filter = _obs_filter
        _reprocessed = process_er_data(
            st.session_state.raw_events, country, _obs_for_proc,
            date_start, date_end)
        if not _reprocessed.empty:
            st.session_state.processed_df = _reprocessed
            st.session_state.gs_data = format_gs_data(
                _reprocessed, country, site,
                gs_username, gs_org, species_epithet, initials)
        st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 2 — Fetch & Format
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("---")
    st.subheader("🔄 Step 2: Fetch my ER data")
    st.caption("Fetches events from EarthRanger and formats them for GiraffeSpotter.")

    if st.button("Fetch my ER data", type="primary"):
        with st.spinner("Fetching events from EarthRanger…"):
            try:
                raw = fetch_er_events(country, date_start, date_end,
                                      st.session_state.er_client,
                                      event_type_uuid=event_type_uuid or None)

                if not raw:
                    st.warning("No events returned for this date range and country.")
                else:
                    # Extract unique observer names for the filter selectbox
                    st.session_state.raw_events = raw
                    st.session_state._prev_observer_filter = _obs_for_proc

                    # Extract unique observer names via an unfiltered process pass
                    _all_processed = process_er_data(raw, country, "",
                                                     date_start, date_end)
                    if "usr_name" in _all_processed.columns:
                        _obs_names = sorted(
                            _all_processed["usr_name"].dropna()
                            .astype(str).str.strip()
                            .replace("", pd.NA).dropna().unique().tolist()
                        )
                    else:
                        _obs_names = []
                    st.session_state.available_observers = _obs_names

                    st.info(f"Fetched **{len(raw)}** raw events from "
                            f"**{len(_obs_names)}** observer(s).")
                    processed = process_er_data(raw, country, _obs_for_proc,
                                                date_start, date_end)

                    if processed.empty:
                        st.warning(
                            "No records found. Check your date range and event type selection.")
                    else:
                        gs = format_gs_data(
                            processed, country, site,
                            gs_username, gs_org, species_epithet, initials)

                        st.session_state.processed_df = processed
                        st.session_state.gs_data      = gs

                        # ── Summary metrics ────────────────────────────────────
                        n_enc    = processed["evt_id"].nunique()
                        n_gir    = len(gs)
                        n_photos = gs["Encounter.mediaAsset0"].apply(
                            lambda v: pd.notna(v) and str(v) not in ("", "nan", "None")
                        ).sum()
                        m1, m2, m3 = st.columns(3)
                        m1.metric("Encounters",  n_enc)
                        m2.metric("Giraffes",    n_gir)
                        m3.metric("With photos", int(n_photos))

                        st.success(
                            f"✅ Formatted **{n_gir}** individual giraffe records "
                            f"from **{n_enc}** encounters.")

                        # ── Encounter map ──────────────────────────────────────
                        _map_cols = ["evt_id", "evt_lat", "evt_lon", "evt_serial",
                                     "evt_dttm", "gir_herdSize", "usr_name",
                                     "gir_riverSystem"]
                        _avail = [c for c in _map_cols if c in processed.columns]
                        map_df = (
                            processed[_avail]
                            .drop_duplicates(subset=["evt_id"])
                            .dropna(subset=["evt_lat", "evt_lon"])
                            .rename(columns={"evt_lat": "latitude",
                                             "evt_lon": "longitude"})
                        )
                        if not map_df.empty:
                            with st.expander("🗺️ Encounter locations", expanded=True):
                                import folium
                                import streamlit.components.v1 as _components
                                _fmap = folium.Map(
                                    location=[map_df["latitude"].mean(),
                                              map_df["longitude"].mean()],
                                    zoom_start=10,
                                    tiles="CartoDB positron",
                                )
                                for _, _row in map_df.iterrows():
                                    _dttm = str(_row.get("evt_dttm", ""))[:19]
                                    _popup_html = (
                                        f"<div style='font-family:sans-serif;font-size:13px;line-height:1.6'>"
                                        f"<b>Serial:</b> {_row.get('evt_serial', '—')}<br/>"
                                        f"<b>Date/Time (UTC):</b> {_dttm}<br/>"
                                        f"<b>Herd size:</b> {_row.get('gir_herdSize', '—')}<br/>"
                                        f"<b>Observer:</b> {_row.get('usr_name', '—')}<br/>"
                                        f"<b>Lat:</b> {_row['latitude']:.6f}<br/>"
                                        f"<b>Lon:</b> {_row['longitude']:.6f}"
                                        f"</div>"
                                    )
                                    folium.CircleMarker(
                                        location=[_row["latitude"], _row["longitude"]],
                                        radius=7,
                                        color="#DB580F",
                                        fill=True,
                                        fill_color="#DB580F",
                                        fill_opacity=0.85,
                                        popup=folium.Popup(_popup_html, max_width=260),
                                    ).add_to(_fmap)
                                _components.html(_fmap._repr_html_(), height=440)

                        # ── Validation summary ─────────────────────────────────
                        issues = validate_gs_data(gs)
                        with st.expander("🔍 Data validation"):
                            for issue in issues:
                                lvl = issue["level"]
                                msg = f"{issue['icon']} {issue['message']}"
                                if lvl == "warning":
                                    st.warning(msg)
                                elif lvl == "info":
                                    st.info(msg)
                                else:
                                    st.success(msg)

                        # ── GS data preview ────────────────────────────────────
                        with st.expander("Preview GiraffeSpotter data (first 20 rows)"):
                            st.dataframe(gs.head(20), hide_index=True)

            except Exception as exc:
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if status == 401:
                    st.error("❌ Authentication failed (401). "
                             "Check your credentials are valid and not expired.")
                elif status:
                    st.error(f"❌ API error {status}. Check instance URL and credentials.")
                else:
                    st.error(f"❌ {exc}")
                    st.exception(exc)

    # ── Download buttons (always visible once data exists) ─────────────────────
    if st.session_state.gs_data is not None:
        today_str = date.today().strftime("%Y%m%d")
        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "⬇️ Download GS data (no images)",
                data=_excel_bytes(st.session_state.gs_data),
                file_name=f"GS_bulkimport_{country}{site}_{today_str}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        with c2:
            st.download_button(
                "⬇️ Download raw ER data",
                data=_excel_bytes(st.session_state.processed_df),
                file_name=f"ER_events_{country}{site}_{today_str}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 3 — Images
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("---")
    st.subheader("📸 Step 3: Process my images")
    st.caption("Upload a single flat ZIP of your survey JPEGs (max 1 GB, no subfolders needed).")

    uploaded_zip = st.file_uploader("Upload image ZIP", type=["zip"])

    if uploaded_zip and st.button("Rename my images"):
        if st.session_state.gs_data is None:
            st.error("Run Step 2 first so we know how to name the images.")
        elif not initials.strip():
            st.error("No initials — enter your initials in the Step 1 GiraffeSpotter section.")
        else:
            progress_bar = st.progress(0, text="Processing images…")
            try:
                renamed, log, gps_lookup = process_images_zip(
                    uploaded_zip.read(),
                    country, site, initials,
                    on_progress=lambda p: progress_bar.progress(
                        p, text=f"Processing images… {int(p * 100)}%"),
                )
                progress_bar.empty()

                st.session_state.renamed_files = renamed
                st.success(f"✅ Renamed **{len(renamed)}** images.")
                st.dataframe(log)

                # ZMB: apply EXIF GPS direction reprojection
                if country == "ZMB" and gps_lookup:
                    st.info(
                        f"🧭 Found EXIF GPS bearings in **{len(gps_lookup)}** images. "
                        "Applying coordinate reprojection for records without manual direction…"
                    )
                    updated_df = apply_exif_reprojection(
                        st.session_state.processed_df, gps_lookup)
                    st.session_state.processed_df = updated_df

                    updated_gs = format_gs_data(
                        updated_df, country, site,
                        gs_username, gs_org, species_epithet, initials)
                    st.session_state.gs_data = updated_gs
                    st.success("✅ Coordinates updated using EXIF GPS directions. "
                               "GiraffeSpotter data has been refreshed.")

            except Exception as exc:
                progress_bar.empty()
                st.error(f"❌ {exc}")
                st.exception(exc)

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 4 — Download ZIP
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("---")
    st.subheader("⬇️ Step 4: Download your GiraffeSpotter data packet")

    can_build = (st.session_state.gs_data is not None
                 and bool(st.session_state.renamed_files))

    if not can_build and st.session_state.gs_data is not None:
        st.info("Complete Step 3 (rename images) before building the ZIP.")

    if st.button("Build Download ZIP", type="primary", disabled=not can_build):
        with st.spinner("Packaging images + GS Excel…"):
            try:
                zip_bytes, n = build_download_zip(
                    st.session_state.renamed_files,
                    st.session_state.gs_data,
                    country, site)
                st.session_state.download_zip = zip_bytes
                st.session_state.n_matched    = n

                n_renamed   = len(st.session_state.renamed_files)
                n_unmatched = n_renamed - n
                st.success(f"✅ ZIP ready — **{n}** matched images + GS Excel.")
                if n_unmatched > 0:
                    st.warning(
                        f"⚠️ **{n_unmatched}** renamed image(s) had no matching "
                        "encounter record and were excluded from the ZIP. "
                        "Check that image_prefix and photo numbers in EarthRanger "
                        "match the actual image filenames.")
                if n == 0:
                    st.error(
                        "No images matched any encounter record. "
                        "Verify that the image_prefix and photo number fields "
                        "in EarthRanger are correct.")
            except Exception as exc:
                st.error(f"❌ {exc}")
                st.exception(exc)

    if st.session_state.download_zip:
        n = st.session_state.n_matched or 0
        today_str = date.today().strftime("%Y%m%d")
        st.download_button(
            f"⬇️ Download ZIP ({n} images + GS Excel)",
            data=st.session_state.download_zip,
            file_name=f"GS_bulkimport_{country}{site}_{today_str}.zip",
            mime="application/zip",
        )

    # ══════════════════════════════════════════════════════════════════════════
    # Done — only shown once ZIP is ready
    # ══════════════════════════════════════════════════════════════════════════
    if st.session_state.download_zip:
        st.markdown("---")
        st.subheader("✅ Done!")
        st.markdown("""
Use the files in your downloaded ZIP for the **GiraffeSpotter bulk import**:
- **Excel file** → upload as the bulk import spreadsheet
- **Images** → upload as media assets

To process a new survey, click **🔄 Start Over** in the banner above.
""")

    st.markdown("---")
    with st.expander("❓ Help"):
        st.markdown("""
**Mistake in my data?**
Download the raw ER data (Step 2), find the record using `evt_serial`,
fix it directly in EarthRanger, then click **Start Over** and re-run.

**Image count mismatch?**
The tool only includes images that match the filenames derived from EarthRanger.
Check that your image prefix and photo numbers in EarthRanger match the actual filenames.

**Alphanumeric image filenames (e.g. 4D1A2407.JPG)?**
These are handled automatically. The full stem is preserved and matched against
the image prefix + photo number stored in EarthRanger (e.g. prefix `4D1A` + number `2407`).

**Something else?**
Contact courtney@giraffeconservation.org
""")


if __name__ == "__main__":
    main()
