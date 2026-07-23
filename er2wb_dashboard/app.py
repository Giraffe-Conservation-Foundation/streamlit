"""
ER2WB: EarthRanger → Wildbook Bulk Import Formatter  v3.0 Python
Uses ecoscope EarthRangerIO to fetch survey/encounter events, formats them
for the selected Wildbook platform (GiraffeSpotter, Whiskerbook, or African
Carnivore Wildbook), and renames associated images.
"""

import gc
import io
import math
import os
import shutil
import sys
import tempfile
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

# Value string → UUID for event types not returned by the API due to permissions
EVENT_VALUE_TO_UUID = {
    "giraffe_survey_kaza": "16847384-f16c-4a1c-aa57-6bba66fb7ed2",
}

TIMEZONE_MAP = {
    "BWA": "Africa/Gaborone",
    "CMR": "Africa/Douala",
    "KEN": "Africa/Nairobi",
    "NAM": "Africa/Windhoek",
    "TZA": "Africa/Dar_es_Salaam",
    "UGA": "Africa/Kampala",
    "ZAF": "Africa/Johannesburg",
    "ZMB": "Africa/Lusaka",
    "RWA_AKNP": "Africa/Kigali",
}

COUNTRY_SITES = {
    "BWA":      ["CHNP", "CTGR", "MWNP", "NG20", "NG29", "NPNP", "NTGR"],
    "CMR":      ["BNNP"],
    "KEN":      ["BINR", "COCO", "EOCO", "IMRA", "ISCO", "KONP", "LECO", "LOWC", "MBCO",
                 "MENP", "MMNR", "MNWC", "MOCO", "MPRC", "MTCO", "MUWC", "MWNR", "NACO",
                 "NAWC", "NIWC", "OHCO", "OICO", "OLCO", "OKWC", "PACA", "RHNP", "RICO",
                 "RUNP", "SANR", "SICO", "TENP", "TWNP"],
    "NAM":      ["BACO", "BLCO", "BWNP", "DZCO", "EHGR", "GMCO", "KWCO", "MNCO",
                 "MNNP", "MSCO", "MUNP", "MYCO", "NANW", "NJCO", "NKNP", "NNCO", "SACO",
                 "SBCO", "SKCO", "UIFA", "WUCO"],
    "TZA":      ["MKNP", "SANP"],
    "UGA":      ["KVNP", "LMNP", "MFNP", "PUWR"],
    "ZAF":      ["TKGR"],
    "ZMB":      ["LLVA", "LUNP", "NLNP", "SICC", "SLNP"],
    # ZCP_SMART and RWA_AKNP have non-standard data structures — handled separately
}

COUNTRY_NAMES = {
    "BWA":  "Botswana",
    "CMR":  "Cameroon",
    "KEN":  "Kenya",
    "NAM":  "Namibia",
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
    "NKNP": "Nkasa Lupala National Park",     "MNNP": "Mangetti National Park",
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
    "IMRA": "Ilmotiok",                       "LOWC": "Loisaba",
    "MPRC": "Mpala",                          "MUWC": "Mugie",
    "MWNR": "Mwea National Reserve",          "NIWC": "Naibunga",
    "SANR": "Samburu National Reserve",
    "MENP": "Meru National Park",             "KONP": "Kora National Park",
    "BINR": "Bisanadi National Reserve",
    # Tanzania
    "MKNP": "Mkomazi National Park",       "SANP": "Serengeti National Park",
    # Uganda
    "KVNP": "Kidepo Valley National Park",    "PUWR": "Pian Upe Wildlife Reserve",
    "MFNP": "Murchison Falls National Park",
    # South Africa
    "TKGR": "Tswalu Kalahari Reserve",
    # Zambia
    "LLVA": "Lower Luangwa Valley",            "LUNP": "Luambe National Park",
    "SICC": "Simalaha Community Conservancy", "SLNP": "South Luangwa National Park",
    "NLNP": "North Luangwa National Park",
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
    "TZA":      ("Masai",       "Masai"),
    "UGA":      ("Northern",    "Nubian"),
    "ZAF":      ("Southern",    "South African"),
    "ZMB":      ("Masai",       "Luangwa"),
    "RWA_AKNP": ("Northern",    "Nubian"),
}

AGE_MAP = {"ad": "adult", "sa": "juvenile", "ju": "calf", "ca": "calf", "u": "unknown"}
SEX_MAP = {"f": "female", "m": "male", "u": "unknown"}

# ─── Wildbook platforms ─────────────────────────────────────────────────────
# All three platforms share the same EarthRanger event_details structure
# (a list of per-individual records with id/age/sex/right/left/notes fields);
# only the list key differs — "Herd" for giraffe/elephant, "Group" for predators.

WILDBOOK_PLATFORMS = ["GiraffeSpotter", "Whiskerbook", "African Carnivore Wildbook"]

PLATFORM_PREFIX = {
    "GiraffeSpotter":             "GS",
    "Whiskerbook":                "WB",
    "African Carnivore Wildbook": "AC",
}

PLATFORM_LIST_KEY = {
    "GiraffeSpotter":             "Herd",
    "Whiskerbook":                "Herd",
    "African Carnivore Wildbook": "Group",
}

# Elephants — always the same species, always Namibia/KAZA
ELEPHANT_GENUS_EPITHET = ("Loxodonta", "africana")

# Predator species is detected from the ER event type name/value
PREDATOR_SPECIES_MAP = {
    "lion":     ("Panthera",  "leo"),
    "cheetah":  ("Acinonyx",  "jubatus"),
    "leopard":  ("Panthera",  "pardus"),
}

# Event types worth showing in the dropdown — anything that looks like a
# survey/encounter event, plus anything tagged for north-western Namibia ("nw")
EVENT_TYPE_KEYWORDS = ("random", "survey", "encounter", "nw")


def detect_predator_species(event_text: str):
    """Detect (genus, epithet) from an ER event type label/value string.
    Returns (None, None) if no known predator species is found."""
    t = (event_text or "").lower()
    for key, (genus, epithet) in PREDATOR_SPECIES_MAP.items():
        if key in t:
            return genus, epithet
    if "wild" in t and "dog" in t:
        return "Lycaon", "pictus"
    return None, None


def resolve_location_id(platform: str, event_text: str, site: str) -> str:
    """GiraffeSpotter keeps the existing site-name lookup. Whiskerbook and
    African Carnivore Wildbook use a fixed locationID based on whether the
    event type name references KAZA or Namibia."""
    if platform == "GiraffeSpotter":
        return SITE_NAMES.get(site, site)
    t = (event_text or "").lower()
    if "kaza" in t:
        return "KAZA TFCA"
    if "nam" in t:
        return "Namibia"
    return SITE_NAMES.get(site, site)


# ─── Session state ─────────────────────────────────────────────────────────────

def _init_session_state():
    """Initialise persistent session state keys with sensible defaults."""
    defaults = {
        # ── EarthRanger session ─────────────────────────────────────────────────
        "er_client":        None,
        "er_authenticated": False,
        "er_event_types":   [],    # [{label, uuid, category}] fetched from ER after login, keyword-filtered
        "er_event_types_all": [],  # same, but unfiltered — used to resolve manual UUID/value entries
        "event_type_sel":   "",    # label of selected event type
        "event_type_uuid":  "",    # UUID of selected event type (empty = use category)
        # ── Processed data (cleared by Reset) ──────────────────────────────────
        "processed_df":         None,
        "gs_data":              None,
        "renamed_files":        {},
        "rename_log":           pd.DataFrame(),  # accumulates across multiple upload batches
        "download_zip":         None,
        "n_matched":            None,
        "raw_events":           [],
        "available_observers":  [],
        "giraffe_id_map":       {},    # UUID → display-name for giraffe_id choice field
        # ── Settings (persisted across reruns) ─────────────────────────────────
        "er_observer_filter":   "",    # "" = all observers
        "er_instance":     "twiga.pamdas.org",
        "er_login_user":   "",
        "er_login_pass":   "",
        "er_observer":     "",    # full name → used to filter events by reporter
        "er_initials":     "",    # initials for image filenames (auto-derived, editable)
        "has_images":      True,  # whether to show Step 3 image processing
        "compress_images": False,
        "compress_quality": 85,
        "gs_org":          "Giraffe Conservation Foundation",
        "gs_username":     "",
        "survey_vessel":   "vehicle_based_photographic",
        "date_start":      date.today() - timedelta(days=10),
        "date_end":        date.today(),
        "country_sel":     list(COUNTRY_SITES.keys())[0],
        "site_sel":        None,
        "species_sel":     list(SPECIES_MAP.keys())[0],
        "subsp_sel":       None,
        "wb_platform":     WILDBOOK_PLATFORMS[0],
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


# ─── Disk-backed temp storage for renamed images ───────────────────────────
# Renamed image bytes are written to a per-session temp directory on disk
# instead of being held in st.session_state, since this app runs as one
# shared process for all users — a single large ZIP held fully in memory
# (raw bytes + decoded/renamed copies) can exceed the host's memory limit
# and crash the app for everyone, not just the uploader.

def _get_images_tmp_dir() -> str:
    """Return (creating if needed) this session's temp dir for renamed images."""
    d = st.session_state.get("images_tmp_dir")
    if not d or not os.path.isdir(d):
        d = tempfile.mkdtemp(prefix="er2wb_imgs_")
        st.session_state["images_tmp_dir"] = d
    return d


def _cleanup_images_tmp_dir():
    """Delete the session's temp image dir entirely (Start Over / Disconnect)."""
    d = st.session_state.get("images_tmp_dir")
    if d and os.path.isdir(d):
        shutil.rmtree(d, ignore_errors=True)
    st.session_state["images_tmp_dir"] = None
    gc.collect()


def _reset_results():
    """Clear processed data but keep all settings and observer list."""
    st.session_state.processed_df  = None
    st.session_state.gs_data       = None
    st.session_state.renamed_files = {}
    st.session_state.rename_log    = pd.DataFrame()
    st.session_state.download_zip  = None
    st.session_state.n_matched     = None
    st.session_state.raw_events    = []
    st.session_state.giraffe_id_map = {}
    _cleanup_images_tmp_dir()
    # available_observers intentionally NOT cleared — list is refreshed on
    # every fetch and should survive Start Over / date changes.


def _disconnect_er():
    """Log out of EarthRanger and clear all derived data."""
    st.session_state.er_client        = None
    st.session_state.er_authenticated = False
    st.session_state.er_event_types   = []
    st.session_state.er_event_types_all = []
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

def _fetch_event_types(client: EarthRangerIO) -> tuple:
    """
    Fetch all event types from EarthRanger.
    Returns (filtered_rows, all_rows) where:
      filtered_rows = sorted list of dicts [{label, uuid, category, value}],
                      restricted to EVENT_TYPE_KEYWORDS — used for the dropdown
      all_rows      = full deduped list (no keyword filter) — used to resolve
                      a manually-entered UUID/value back to its real label/value
                      for species + locationID detection
    """
    all_rows = []

    for api_ver in ("v1", "v2"):
        try:
            df = client.get_event_types(include_inactive=True, api_version=api_ver)
            if df is None or df.empty:
                continue
            for _, row in df.iterrows():
                value = str(row.get("value", "")).strip()
                label = str(row.get("display", value)).strip()
                uuid  = str(row.get("id", "")).strip()
                if not uuid or uuid.lower() in ("nan", "none", ""):
                    uuid = value
                cat = str(row.get("category", "")).strip()
                if label and uuid:
                    all_rows.append({"label": label, "uuid": uuid,
                                     "category": cat, "value": value.lower()})
        except Exception:
            continue

    if not all_rows:
        return [], []

    seen = set()
    deduped = []
    for r in all_rows:
        if r["uuid"] not in seen:
            seen.add(r["uuid"])
            deduped.append(r)
    deduped.sort(key=lambda x: x["label"].lower())

    rows = [r for r in deduped if any(
                kw in r["label"].lower() or kw in r["value"].lower()
                for kw in EVENT_TYPE_KEYWORDS)]
    return rows, deduped


def _fetch_giraffe_id_mapping(client: EarthRangerIO, _event_type_uuid: str = "") -> dict:
    """
    Build a subject UUID → subject name mapping by fetching all subjects from ER.
    The giraffe_id field in event_details stores a subject UUID; this map resolves it
    to the human-readable subject name (e.g. "HNBF093_Aubrey").
    Returns {} on any failure so callers degrade gracefully.
    """
    try:
        df = client.get_subjects(include_inactive=True)
        if df is None or df.empty:
            return {}
        if "id" not in df.columns or "name" not in df.columns:
            return {}
        return dict(zip(df["id"].astype(str), df["name"].astype(str)))
    except Exception:
        return {}


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

    try:
        gdf = er_client.get_events(**kwargs)
    except AssertionError:
        # ecoscope raises AssertionError when the query returns no events
        return []

    if gdf is None or gdf.empty:
        return []

    # Ensure id and serial_number are columns (ecoscope may set id as the index)
    if "id" not in gdf.columns:
        gdf = gdf.reset_index()

    # Pre-scan GDF columns for any reporter-name shaped column ecoscope may use
    _rb_name_col = next(
        (c for c in gdf.columns
         if "reported_by" in c.lower() and "name" in c.lower()),
        None,
    )
    _rb_id_col = next(
        (c for c in gdf.columns
         if "reported_by" in c.lower() and "id" in c.lower()
         and c != _rb_name_col),
        None,
    )

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

        # Build a clean {"name": ..., "id": ...} reported_by dict regardless of
        # how ecoscope returned it (nested dict, flattened columns, stringified).
        rb     = rec.get("reported_by")
        rb_name, rb_id = "", ""

        if isinstance(rb, dict):
            # name or username may hold the display name
            rb_name = str(rb.get("name") or rb.get("username") or "").strip()
            rb_id   = str(rb.get("id")   or "").strip()

        if not rb_name:
            # flattened columns detected by pre-scan
            if _rb_name_col:
                rb_name = str(rec.get(_rb_name_col) or "").strip()
            if _rb_id_col and not rb_id:
                rb_id = str(rec.get(_rb_id_col) or "").strip()

        if not rb_name:
            # dot-notation variants pandas sometimes creates
            rb_name = str(
                rec.get("reported_by.name") or
                rec.get("reported_by_name")  or ""
            ).strip()

        if not rb_name and isinstance(rb, str) and "{" in rb:
            # last resort: stringified dict e.g. "{'name': 'Jane Smith'}"
            try:
                import ast
                _parsed = ast.literal_eval(rb)
                if isinstance(_parsed, dict):
                    rb_name = str(_parsed.get("name") or _parsed.get("username") or "").strip()
                    rb_id   = str(_parsed.get("id") or "").strip()
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

# Per-individual fields inside the Herd/Group list are keyed under a
# species-specific prefix in ER (giraffe_id/giraffe_age/... for GiraffeSpotter,
# elephant_id/elephant_age/... for Whiskerbook, lion_id/cheetah_id/leopard_id/
# wilddog_id/... for African Carnivore Wildbook), even though the form
# structure is otherwise identical across platforms. Rather than hardcoding
# every species name, find whichever prefix is actually present in the record.


def _individual_field(rec: dict, field: str):
    """Look up a per-individual field (id/age/sex/right/left/notes) by
    matching the "*_{field}" key actually present in this record, regardless
    of the species-specific prefix ER stored it under."""
    suffix = f"_{field}"
    for key in rec:
        if key.endswith(suffix):
            return rec.get(key)
    return None


def process_er_data(raw_events: list, country: str, er_username: str,
                    date_start: date, date_end: date,
                    giraffe_id_map: dict = None,
                    list_key: str = "Herd") -> pd.DataFrame:
    """
    Flatten raw ER event JSON into a tidy DataFrame.
    One row per individual record (list_key — "Herd" for giraffe/elephant,
    "Group" for predators), joined with event-level fields. Field names
    inside the list are the same across all platforms (giraffe_id,
    giraffe_age, giraffe_sex, giraffe_right, giraffe_left, giraffe_notes) —
    EarthRanger reuses the same form structure for every species.
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

        herd_list = det.get(list_key) or []
        if isinstance(herd_list, list) and herd_list:
            for giraffe in herd_list:
                if not isinstance(giraffe, dict):
                    continue
                gr = _individual_field(giraffe, "right")
                gl = _individual_field(giraffe, "left")
                herd_rows.append({
                    "id":            evt.get("id"),
                    "giraffe_id":    _individual_field(giraffe, "id") or "",
                    "giraffe_age":   _individual_field(giraffe, "age") or "",
                    "giraffe_sex":   _individual_field(giraffe, "sex") or "",
                    "giraffe_right": str(int(gr)).zfill(4) if gr is not None else None,
                    "giraffe_left":  str(int(gl)).zfill(4) if gl is not None else None,
                    "giraffe_notes": _individual_field(giraffe, "notes") or "",
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
        gid = str(gid).strip()
        if giraffe_id_map and gid in giraffe_id_map:
            gid = giraffe_id_map[gid]
        return gid  # full resolved name; GS export applies the _ clip separately

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


# ─── Wildbook formatting ────────────────────────────────────────────────────

def format_gs_data(final_df: pd.DataFrame, country: str, site: str,
                   gs_username: str, gs_org: str,
                   species_epithet: str, initials: str,
                   date_start: date = None,
                   survey_vessel: str = "vehicle_based_photographic",
                   genus: str = "Giraffa",
                   location_id: str = None) -> pd.DataFrame:
    """Convert processed ER DataFrame to Wildbook bulk import format.
    Works for any of the three platforms — genus/species_epithet/location_id
    are resolved by the caller based on the selected Wildbook platform."""
    if final_df.empty:
        return pd.DataFrame()

    local_tz  = TIMEZONE_MAP.get(country, "UTC")
    site_name = location_id if location_id else SITE_NAMES.get(site, site)

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
        "Survey.vessel":            survey_vessel,
        "Survey.id":                (
            f"{country}_{site}_{date_start.strftime('%Y%m')}"
            if date_start is not None
            else df["evt_dttm_local"].apply(
                lambda d: f"{country}_{site}_{d.strftime('%Y%m')}" if pd.notna(d) else "")
        ),
        "Occurrence.occurrenceID":  df.apply(
            lambda r: f"{country}_{site}_{r['evt_dttm_local'].strftime('%Y%m%d%H%M%S')}"
                      if pd.notna(r["evt_dttm_local"]) else "", axis=1),
        "Encounter.decimalLongitude":   df["evt_lon"],
        "Encounter.decimalLatitude":    df["evt_lat"],
        "Encounter.locationID":         site_name,
        "Encounter.verbatimLocality":   df.get("gir_riverSystem"),
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
        "Encounter.individualID":       df["gir_giraffeId"].fillna("").apply(
            lambda v: v.split("_")[0] if "_" in v else v),
        "Encounter.sex":                df["gir_giraffeSex"],
        "Encounter.lifeStage":          df["gir_giraffeAge"],
        "Encounter.genus":              genus,
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

def compress_image(img_bytes: bytes, quality: int) -> bytes:
    """Re-save JPEG at the given quality (1–95). Strips non-essential metadata
    but preserves EXIF so datetime and GPS direction extraction still works."""
    from PIL import Image
    img = Image.open(io.BytesIO(img_bytes))
    # Preserve EXIF data
    exif = img.info.get("exif", b"")
    out  = io.BytesIO()
    img.save(out, format="JPEG", quality=quality, optimize=True,
             exif=exif if exif else None)
    out.seek(0)
    return out.read()


def process_images_zip(zip_path: str, country: str, site: str,
                       initials: str, images_dir: str,
                       compress: bool = False, quality: int = 85,
                       on_progress=None) -> tuple:
    """
    Extract ZIP (read from disk, one member at a time), rename every JPEG
    using EXIF datetime, and write each renamed image straight to
    `images_dir` on disk. For ZMB, also extracts GPSImgDirection.

    Renamed images are NOT held in memory afterwards — only their on-disk
    paths are returned — so a near-1GB ZIP of photos doesn't need a
    near-1GB resident copy of decoded image bytes for the rest of the
    session.

    Parameters
    ----------
    zip_path : str
        Path to the uploaded ZIP on disk (written there by the caller so the
        full ZIP is never held as a single in-memory bytes blob).
    images_dir : str
        Directory to write renamed images into.
    on_progress : callable(float) | None
        Called after each image with a fraction 0.0–1.0.  Use to drive a
        st.progress bar.

    Returns
    -------
    renamed_paths : dict  {new_name: path_on_disk}
    rename_log    : pd.DataFrame  with Original / Renamed / Status columns
    gps_lookup    : dict  {full_image_stem: bearing_degrees}  (ZMB only)
    """
    renamed_paths, log_rows, gps_lookup = {}, [], {}

    with zipfile.ZipFile(zip_path) as zf:
        jpg_names = [n for n in zf.namelist()
                     if n.lower().endswith((".jpg", ".jpeg"))
                     and not Path(n).name.startswith(".")]

        total = len(jpg_names) or 1   # avoid divide-by-zero

        for idx, name in enumerate(jpg_names):
            try:
                img_bytes = zf.read(name)   # one image at a time, not the whole zip
                dttm      = get_exif_datetime(img_bytes)
                date_str  = dttm.strftime("%Y%m%d")

                # ── FIX: preserve alphanumeric stems (e.g. 4D1A2407) ──────────
                stem = Path(name).stem
                num  = stem.zfill(4) if stem.isdigit() else stem
                # ─────────────────────────────────────────────────────────────

                new_name = f"{country}_{site}_{date_str}_{initials}_{num}.JPG".upper()
                if compress:
                    try:
                        orig_kb = len(img_bytes) // 1024
                        img_bytes = compress_image(img_bytes, quality)
                        comp_kb   = len(img_bytes) // 1024
                        compress_note = f" | {orig_kb} KB → {comp_kb} KB"
                    except Exception as ce:
                        compress_note = f" | compress failed: {ce}"
                else:
                    compress_note = ""

                # ZMB: capture GPS bearing from EXIF for coordinate reprojection
                # (must happen before img_bytes is written/dropped)
                gps_dir  = None
                gps_note = ""
                if country == "ZMB":
                    gps_dir = get_exif_gps_direction(img_bytes)
                    if gps_dir is not None:
                        # e.g. ZMB_LVNP_20250817_FO_4D1A2407.JPG → 4D1A2407
                        full_img_stem = new_name.rsplit("_", 1)[-1].replace(".JPG", "")
                        gps_lookup[full_img_stem] = gps_dir
                        gps_note = f" | GPS dir: {gps_dir:.1f}°"

                dest_path = os.path.join(images_dir, new_name)
                with open(dest_path, "wb") as out_f:
                    out_f.write(img_bytes)
                renamed_paths[new_name] = dest_path
                del img_bytes   # drop the decoded copy as soon as it's on disk

                log_rows.append({
                    "Original": Path(name).name,
                    "Renamed":  new_name,
                    "Status":   f"✅ OK{gps_note}{compress_note}",
                })
            except Exception as exc:
                log_rows.append({"Original": Path(name).name,
                                  "Renamed":  "",
                                  "Status":   f"❌ {exc}"})

            if on_progress:
                on_progress((idx + 1) / total)

            # Periodic GC sweep so peak memory doesn't creep up over a large
            # batch (mainly a safety net — refcounting already frees most
            # objects immediately, but PIL/EXIF parsing can create cycles).
            if (idx + 1) % 100 == 0:
                gc.collect()

    gc.collect()
    return renamed_paths, pd.DataFrame(log_rows), gps_lookup


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


def build_download_zip(renamed_paths: dict, gs_data: pd.DataFrame,
                       country: str, site: str, prefix: str = "GS") -> tuple:
    """
    Build ZIP containing matched images + Wildbook bulk-import Excel.
    `renamed_paths` maps {new_name: path_on_disk} — images are streamed in
    from disk one at a time rather than held in memory as a dict of bytes.
    Returns (zip_bytes, n_matched_images).
    """
    gs_asset_names = set()
    for col in ("Encounter.mediaAsset0", "Encounter.mediaAsset1"):
        if col in gs_data.columns:
            gs_asset_names.update(
                str(v).upper() for v in gs_data[col].dropna()
                if str(v) not in ("", "nan", "None")
            )

    matched = {k: v for k, v in renamed_paths.items() if k.upper() in gs_asset_names}

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname, fpath in matched.items():
            zf.write(fpath, arcname=fname)   # streams from disk, not from a resident dict

        xls_name = f"{prefix}_bulkimport_{country}{site}_{date.today().strftime('%Y%m%d')}.xlsx"
        zf.writestr(xls_name, _excel_bytes(gs_data))

    buf.seek(0)
    gc.collect()
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
                        et_rows, et_rows_all = _fetch_event_types(client)
                        st.session_state.er_event_types     = et_rows
                        st.session_state.er_event_types_all = et_rows_all
                        st.rerun()
                    except Exception as exc:
                        status = getattr(getattr(exc, "response", None), "status_code", None)
                        if status == 401:
                            st.error("❌ Login failed — check your username and password.")
                        elif status == 403:
                            st.error("❌ Access denied (403) — your account may not have API access.")
                        elif status:
                            st.error(f"❌ API error {status}. Check the instance URL.")
                        else:
                            msg = str(exc)
                            st.error(f"❌ Could not connect: {msg}")
                            if "Failed login" in msg:
                                st.info(
                                    "💡 Common causes: wrong username (try email address instead), "
                                    "wrong password, or account not active on this EarthRanger instance. "
                                    "Try logging in at the EarthRanger web interface to confirm your credentials."
                                )
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
    # STEP 1 (cont.) — Survey & Wildbook settings
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
    event_type_value = ""

    if er_event_types:
        et_labels = [et["label"] for et in er_event_types]
        if st.session_state.event_type_sel not in et_labels:
            st.session_state.event_type_sel = et_labels[0]

        event_type_label = st.selectbox(
            "Encounter event type", et_labels, key="event_type_sel")
        matched = next((et for et in er_event_types
                        if et["label"] == event_type_label), None)
        event_type_uuid  = matched["uuid"]  if matched else ""
        event_type_value = matched["value"] if matched else ""
    else:
        st.info("Could not fetch event types from this ER instance. "
                "Enter the event type value or UUID manually below.")
        event_type_uuid = ""

    # Manual override — always visible so users can enter types not shown in the list
    # (e.g. types in categories with restricted API permissions like monitoring_kaza)
    manual_et = st.text_input(
        "Event type not in list? Enter value or UUID manually",
        value="",
        placeholder="e.g. giraffe_survey_kaza  or  16847384-f16c-4a1c-aa57-6bba66fb7ed2",
        help="Some event types are restricted to certain user roles in the EarthRanger API "
             "and won't appear in the dropdown. Enter the event type value (e.g. "
             "giraffe_survey_kaza) or UUID directly to fetch those events.",
    )
    if manual_et.strip():
        _manual = manual_et.strip()
        # If a value string (not UUID) is entered, resolve to UUID if known
        import re as _re
        _UUID_RE = _re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            _re.IGNORECASE)
        _entered_uuid = _UUID_RE.match(_manual) is not None
        if not _entered_uuid:
            _manual = EVENT_VALUE_TO_UUID.get(_manual.lower(), _manual)
        event_type_uuid = _manual

        # The text used for species/locationID detection must be the event
        # type's NAME (e.g. "lion_sighting"), not a UUID — if the user typed
        # a UUID (or it got resolved to one above), look up its real
        # label/value from the full unfiltered event-type list so detection
        # still works. This fixes manually-entered types matching events
        # but never resolving a species/location (UUID text has no "lion"
        # or "kaza" substring for detect_predator_species/resolve_location_id
        # to find).
        if _UUID_RE.match(event_type_uuid):
            _all_types = st.session_state.get("er_event_types_all", [])
            _lookup = next((et for et in _all_types
                            if et["uuid"].lower() == event_type_uuid.lower()), None)
            if _lookup:
                event_type_value = (_lookup.get("value") or _lookup.get("label") or "").lower()
                event_type_label = _lookup.get("label", "")
            else:
                # UUID not found in the fetched list (e.g. restricted category that
                # never came back from ER at all) — nothing to detect species/location
                # from; user input itself isn't usable as detection text.
                event_type_value = ""
        else:
            event_type_value = manual_et.strip().lower()

    # Combined text used to infer species (predators) and locationID
    # (Whiskerbook / African Carnivore Wildbook) from the chosen event type
    event_type_text = (event_type_value or event_type_label or "").lower()

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

    # ── 1c: Wildbook platform & species ───────────────────────────────────────
    st.markdown("**Wildbook platform**")
    platform = st.selectbox(
        "Which Wildbook is this data going to?",
        WILDBOOK_PLATFORMS, key="wb_platform")

    gs_c1, gs_c2, gs_c3, gs_c4 = st.columns(4)

    with gs_c1:
        gs_username = st.text_input("Wildbook username", key="gs_username")
        gs_org      = st.session_state.gs_org   # kept in state but not shown prominently

    with gs_c2:
        initials = st.text_input(
            "Observer initials (e.g., CM)", key="er_initials",
            help="Used in renamed image filenames, e.g. CM → NAM_EHGR_20250101_CM_0001.JPG.")

    genus = None
    species_epithet = None

    if platform == "GiraffeSpotter":
        with gs_c3:
            species_keys = list(SPECIES_MAP.keys())
            if st.session_state.species_sel not in species_keys:
                st.session_state.species_sel = species_keys[0]
            species_choice = st.selectbox("Species", species_keys, key="species_sel")
        with gs_c4:
            subsp_options = list(SPECIES_MAP[species_choice].keys())
            if st.session_state.subsp_sel not in subsp_options:
                st.session_state.subsp_sel = subsp_options[0]
            subsp_choice    = st.selectbox("Subspecies", subsp_options, key="subsp_sel")
            genus           = "Giraffa"
            species_epithet = SPECIES_MAP[species_choice][subsp_choice]

    elif platform == "Whiskerbook":
        genus, species_epithet = ELEPHANT_GENUS_EPITHET
        with gs_c3:
            st.text_input("Genus", value=genus, disabled=True)
        with gs_c4:
            st.text_input("Species", value=species_epithet, disabled=True)

    else:  # African Carnivore Wildbook
        genus, species_epithet = detect_predator_species(event_type_text)
        with gs_c3:
            st.text_input("Genus", value=genus or "(select event type)", disabled=True)
        with gs_c4:
            st.text_input("Species", value=species_epithet or "(select event type)", disabled=True)
        if not genus:
            st.warning(
                "⚠️ Couldn't detect a predator species from the selected event type. "
                "Pick an event type whose name includes lion, cheetah, leopard, or wild dog.")

    location_id = resolve_location_id(platform, event_type_text, site)
    prefix      = PLATFORM_PREFIX[platform]
    list_key    = PLATFORM_LIST_KEY[platform]

    _SURVEY_VESSEL_OPTIONS = {
        "Road survey":        "vehicle_based_photographic",
        "Random encounter":   "random_encounter",
        "Aerial survey":      "aerial_based_photographic",
        "Camera trap":        "camera_trap",
    }
    _vessel_label = st.selectbox(
        "Survey type",
        options=list(_SURVEY_VESSEL_OPTIONS.keys()),
        index=list(_SURVEY_VESSEL_OPTIONS.values()).index(
            st.session_state.get("survey_vessel", "vehicle_based_photographic")),
        key="_survey_vessel_label",
        help="Sets the Survey.vessel field in the Wildbook output.",
    )
    st.session_state["survey_vessel"] = _SURVEY_VESSEL_OPTIONS[_vessel_label]

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
            date_start, date_end,
            giraffe_id_map=st.session_state.get("giraffe_id_map", {}),
            list_key=list_key)
        if not _reprocessed.empty:
            st.session_state.processed_df = _reprocessed
            st.session_state.gs_data = format_gs_data(
                _reprocessed, country, site,
                gs_username, gs_org, species_epithet, initials,
                date_start=date_start,
                survey_vessel=st.session_state.get("survey_vessel", "vehicle_based_photographic"),
                genus=genus, location_id=location_id)
        st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 2 — Fetch & Format
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("---")
    st.subheader("🔄 Step 2: Fetch my ER data")
    st.caption("Fetches events from EarthRanger and formats them for the selected Wildbook platform.")

    if st.button("Fetch my ER data", type="primary"):
        with st.spinner("Fetching events from EarthRanger…"):
            try:
                raw = fetch_er_events(country, date_start, date_end,
                                      st.session_state.er_client,
                                      event_type_uuid=event_type_uuid or None)

                if not raw:
                    st.warning(
                        "No events returned for this date range. "
                        "If you're using a non-GCF EarthRanger instance, make sure you've "
                        "selected the correct **Encounter event type** in the selector above."
                    )
                else:
                    st.session_state.raw_events = raw
                    st.session_state._prev_observer_filter = _obs_for_proc

                    # Resolve giraffe_id subject UUIDs → subject names
                    giraffe_id_map = _fetch_giraffe_id_mapping(
                        st.session_state.er_client, event_type_uuid)
                    st.session_state.giraffe_id_map = giraffe_id_map

                    # Unfiltered pass → populate observer dropdown
                    _all_proc = process_er_data(raw, country, "", date_start, date_end,
                                                giraffe_id_map=giraffe_id_map,
                                                list_key=list_key)
                    _obs_names = sorted(
                        _all_proc["usr_name"].dropna()
                        .astype(str).str.strip()
                        .replace("", pd.NA).dropna().unique().tolist()
                    ) if "usr_name" in _all_proc.columns else []
                    st.session_state.available_observers = _obs_names

                    # Filtered pass → Wildbook output
                    processed = process_er_data(raw, country, _obs_for_proc,
                                                date_start, date_end,
                                                giraffe_id_map=giraffe_id_map,
                                                list_key=list_key)
                    if processed.empty:
                        st.warning(
                            "No records found. Check your date range and event type selection.")
                    else:
                        gs = format_gs_data(processed, country, site,
                                            gs_username, gs_org, species_epithet, initials,
                                            date_start=date_start,
                                            survey_vessel=st.session_state.get("survey_vessel", "vehicle_based_photographic"),
                                            genus=genus, location_id=location_id)
                        st.session_state.processed_df = processed
                        st.session_state.gs_data      = gs
                        st.rerun()   # rerun so observer filter renders with the new names

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

    # ── Results (rendered from session state on every run) ─────────────────────
    if st.session_state.processed_df is not None and st.session_state.gs_data is not None:
        processed = st.session_state.processed_df
        gs        = st.session_state.gs_data

        n_enc    = processed["evt_id"].nunique()
        n_gir    = len(gs)
        def _has_media(v):
            return pd.notna(v) and str(v) not in ("", "nan", "None")
        n_photos = (
            gs["Encounter.mediaAsset0"].apply(_has_media) |
            gs["Encounter.mediaAsset1"].apply(_has_media)
        ).sum()
        m1, m2, m3 = st.columns(3)
        m1.metric("Encounters",  n_enc)
        m2.metric("Individuals", n_gir)
        m3.metric("With photos", int(n_photos))

        st.success(f"✅ Formatted **{n_gir}** individual records "
                   f"from **{n_enc}** encounters for **{platform}**.")

        # ── Encounter map ──────────────────────────────────────────────────────
        _map_cols = ["evt_id", "evt_lat", "evt_lon", "evt_serial",
                     "evt_dttm", "gir_herdSize", "usr_name", "gir_riverSystem"]
        _avail = [c for c in _map_cols if c in processed.columns]
        map_df = (
            processed[_avail]
            .drop_duplicates(subset=["evt_id"])
            .dropna(subset=["evt_lat", "evt_lon"])
            .rename(columns={"evt_lat": "latitude", "evt_lon": "longitude"})
        )
        if not map_df.empty:
            with st.expander("🗺️ Encounter locations", expanded=True):
                import folium
                import streamlit.components.v1 as _components
                _fmap = folium.Map(
                    location=[map_df["latitude"].mean(), map_df["longitude"].mean()],
                    zoom_start=10, tiles="CartoDB positron",
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
                        radius=7, color="#DB580F", fill=True,
                        fill_color="#DB580F", fill_opacity=0.85,
                        popup=folium.Popup(_popup_html, max_width=260),
                    ).add_to(_fmap)
                _components.html(_fmap._repr_html_(), height=440)

        # ── Validation summary ─────────────────────────────────────────────────
        issues = validate_gs_data(gs)
        with st.expander("🔍 Data validation"):
            for issue in issues:
                lvl = issue["level"]
                msg = f"{issue['icon']} {issue['message']}"
                if lvl == "warning":    st.warning(msg)
                elif lvl == "info":     st.info(msg)
                else:                   st.success(msg)

        # ── GS data preview ────────────────────────────────────────────────────
        with st.expander("Preview Wildbook data (first 20 rows)"):
            st.dataframe(gs.head(20), hide_index=True)

    # ── Download buttons (always visible once data exists) ─────────────────────
    if st.session_state.gs_data is not None:
        today_str = date.today().strftime("%Y%m%d")
        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "⬇️ Download Wildbook data (no images)",
                data=_excel_bytes(st.session_state.gs_data),
                file_name=f"{prefix}_bulkimport_{country}{site}_{today_str}.xlsx",
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
    st.caption(
        "Upload a flat ZIP of your survey JPEGs (no subfolders needed). "
        "**Keep each ZIP under ~40 MB.** Large uploads (hundreds of MB) are "
        "unreliable here — the app buffers the whole file in a memory-limited "
        "shared process, so a big ZIP can hang on the spinner or crash before "
        "it finishes uploading. Split your photos into several small ZIPs and "
        "upload/rename them one at a time below; **each batch adds to the "
        "results, it doesn't replace them.** Use **🔄 Start Over** above to "
        "clear everything and begin fresh."
    )
    st.caption(
        "💡 To split a big photo folder into upload-sized ZIPs automatically, "
        "run `scripts/split_images_for_er2wb.ps1` on your PC — e.g. "
        "`.\\split_images_for_er2wb.ps1 -Source \"C:\\path\\to\\photos\"`. "
        "It writes `batch_01.zip`, `batch_02.zip`, … each ≤ 40 MB."
    )

    uploaded_zip = st.file_uploader("Upload image ZIP", type=["zip"])

    # ── Compression option ─────────────────────────────────────────────────────
    _QUALITY_PRESETS = {
        "None — keep original":                    None,
        "Medium — 85% quality (~50% smaller)":     85,
        "High compression — 75% quality (~65% smaller, smallest files)": 75,
    }
    compress_choice = st.radio(
        "Image compression",
        options=list(_QUALITY_PRESETS.keys()),
        index=0,
        horizontal=True,
        help=(
            "**JPEG quality compression** — reduces file size by increasing lossy "
            "encoding of colour and fine detail. Image dimensions (pixels) are unchanged. "
            "85% quality is generally indistinguishable from the original and recommended "
            "for Wildbook photo-ID. 75% gives the smallest files and is still "
            "suitable for pattern matching, but fine texture in close-ups may soften slightly. "
            "EXIF metadata (datetime, GPS) is preserved in all cases."
        ),
    )
    _compress_quality = _QUALITY_PRESETS[compress_choice]
    _do_compress      = _compress_quality is not None

    if uploaded_zip and st.button("Rename my images"):
        if st.session_state.gs_data is None:
            st.error("Run Step 2 first so we know how to name the images.")
        elif not initials.strip():
            st.error("No initials — enter your initials in the Step 1 Wildbook platform section.")
        else:
            progress_bar = st.progress(0, text="Processing images…")
            zip_tmp_path = None
            try:
                # Stream the upload straight to disk in chunks instead of
                # reading it into a single in-memory bytes blob — for a
                # ~1GB ZIP that avoids a ~1GB resident copy on top of
                # whatever the decoded/renamed images need.
                fd, zip_tmp_path = tempfile.mkstemp(suffix=".zip", prefix="er2wb_upload_")
                with os.fdopen(fd, "wb") as out_f:
                    shutil.copyfileobj(uploaded_zip, out_f)

                images_dir = _get_images_tmp_dir()
                # NOTE: previously cleared images_dir here before every run, which
                # meant uploading a second (smaller, e.g. workaround-for-timeout)
                # batch silently wiped out the first batch's results. Batches now
                # accumulate instead — use "Start Over" to clear everything.

                renamed_paths, log, gps_lookup = process_images_zip(
                    zip_tmp_path,
                    country, site, initials, images_dir,
                    compress=_do_compress,
                    quality=_compress_quality or 85,
                    on_progress=lambda p: progress_bar.progress(
                        p, text=f"Processing images… {int(p * 100)}%"),
                )
                progress_bar.empty()

                st.session_state.renamed_files.update(renamed_paths)
                st.session_state.rename_log = pd.concat(
                    [st.session_state.rename_log, log], ignore_index=True
                ) if len(st.session_state.rename_log) else log

                total_so_far = len(st.session_state.renamed_files)
                st.success(
                    f"✅ Renamed **{len(renamed_paths)}** images this batch "
                    f"(**{total_so_far}** total so far)."
                )
                st.dataframe(st.session_state.rename_log)

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
                        gs_username, gs_org, species_epithet, initials,
                        date_start=date_start,
                        survey_vessel=st.session_state.get("survey_vessel", "vehicle_based_photographic"),
                        genus=genus, location_id=location_id)
                    st.session_state.gs_data = updated_gs
                    st.success("✅ Coordinates updated using EXIF GPS directions. "
                               "Wildbook data has been refreshed.")

            except Exception as exc:
                progress_bar.empty()
                st.error(f"❌ {exc}")
                st.exception(exc)
            finally:
                # The uploaded ZIP itself is only needed transiently — the
                # renamed images now live in images_dir, so drop the upload
                # copy right away regardless of success/failure.
                if zip_tmp_path and os.path.exists(zip_tmp_path):
                    try:
                        os.remove(zip_tmp_path)
                    except OSError:
                        pass
                gc.collect()

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 4 — Download ZIP
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("---")
    st.subheader("⬇️ Step 4: Download your Wildbook data packet")

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
                    country, site, prefix=prefix)
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
            f"⬇️ Download ZIP ({n} images + Wildbook Excel)",
            data=st.session_state.download_zip,
            file_name=f"{prefix}_bulkimport_{country}{site}_{today_str}.zip",
            mime="application/zip",
        )

    # ══════════════════════════════════════════════════════════════════════════
    # Done — only shown once ZIP is ready
    # ══════════════════════════════════════════════════════════════════════════
    if st.session_state.download_zip:
        st.markdown("---")
        st.subheader("✅ Done!")
        st.markdown(f"""
Use the files in your downloaded ZIP for the **{platform} bulk import**:
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

**Wrong species/genus detected for African Carnivore Wildbook?**
The species is auto-detected from the selected ER event type name (must contain
lion, cheetah, leopard, or wild dog). If nothing is detected, pick a different
event type or rename it in EarthRanger.

**Something else?**
Contact courtney@giraffeconservation.org
""")


if __name__ == "__main__":
    main()
