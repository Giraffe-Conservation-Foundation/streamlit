"""
Format xlsx for GiraffeSpotter
Upload any survey spreadsheet and map columns to the GS bulk-import format.
No EarthRanger login required.
"""

import io
from datetime import date

import pandas as pd
import streamlit as st

# ── GS field definitions ───────────────────────────────────────────────────────
# (gs_column, display_label, required, section)
GS_FIELDS = [
    # Location
    ("Encounter.decimalLatitude",    "Latitude",              True,  "Location"),
    ("Encounter.decimalLongitude",   "Longitude",             True,  "Location"),
    # Individual
    ("Encounter.individualID",       "Individual ID",         False, "Individual"),
    ("Encounter.sex",                "Sex",                   False, "Individual"),
    ("Encounter.lifeStage",          "Life stage / age",      False, "Individual"),
    ("Encounter.occurrenceRemarks",  "Notes / remarks",       False, "Individual"),
    # Group counts
    ("Occurrence.groupSize",         "Group size",            False, "Group counts"),
    ("Occurrence.numAdults",         "# adults",              False, "Group counts"),
    ("Occurrence.numAdultFemales",   "# adult females",       False, "Group counts"),
    ("Occurrence.numAdultMales",     "# adult males",         False, "Group counts"),
    ("Occurrence.numSubAdults",      "# sub-adults",          False, "Group counts"),
    ("Occurrence.numSubFemales",     "# sub-adult females",   False, "Group counts"),
    ("Occurrence.numSubMales",       "# sub-adult males",     False, "Group counts"),
    ("Occurrence.numCalves",         "# calves",              False, "Group counts"),
    # Sighting geometry
    ("Occurrence.distance",          "Distance (m)",          False, "Sighting geometry"),
    ("Occurrence.bearing",           "Bearing (°)",           False, "Sighting geometry"),
    # Media
    ("Encounter.mediaAsset0",        "Photo 1 filename",      False, "Media"),
    ("Encounter.mediaAsset1",        "Photo 2 filename",      False, "Media"),
]

INT_FIELDS = {
    "Occurrence.groupSize", "Occurrence.numAdults", "Occurrence.numAdultFemales",
    "Occurrence.numAdultMales", "Occurrence.numSubAdults", "Occurrence.numSubFemales",
    "Occurrence.numSubMales", "Occurrence.numCalves",
}

FLOAT_FIELDS = {
    "Encounter.decimalLatitude", "Encounter.decimalLongitude",
    "Occurrence.distance", "Occurrence.bearing",
}

VESSEL_OPTIONS = [
    "vehicle_based_photographic",
    "foot_based_photographic",
    "aerial_based_photographic",
    "boat_based_photographic",
]

SPECIES_OPTIONS = [
    "camelopardalis", "giraffa", "reticulata", "tippelskirchi",
    "antiquorum", "peralta", "rothschildi", "thornicrofti",
]


def _safe_int(x):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return None


def _safe_float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _excel_bytes(df: pd.DataFrame) -> bytes:
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            if hasattr(out[col].dt, "tz") and out[col].dt.tz is not None:
                out[col] = out[col].dt.tz_localize(None)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        out.to_excel(writer, index=False)
    buf.seek(0)
    return buf.read()


def _load_file(uploaded) -> pd.DataFrame:
    name = uploaded.name.lower()
    if name.endswith(".csv"):
        return pd.read_csv(uploaded)
    return pd.read_excel(uploaded)


def _build_gs(src: pd.DataFrame, settings: dict, date_cfg: dict, col_map: dict) -> pd.DataFrame:
    n = len(src)

    # ── Resolve datetime series ────────────────────────────────────────────────
    dt = None
    mode = date_cfg["mode"]
    try:
        if mode == "datetime" and date_cfg.get("dt_col"):
            dt = pd.to_datetime(src[date_cfg["dt_col"]], errors="coerce")
        elif mode == "date_time":
            d = pd.to_datetime(src[date_cfg["date_col"]].astype(str), errors="coerce")
            if date_cfg.get("time_col"):
                t = pd.to_datetime(src[date_cfg["time_col"]].astype(str), errors="coerce")
                dt = d + pd.to_timedelta(t.dt.hour * 3600 + t.dt.minute * 60, unit="s")
            else:
                dt = d
        elif mode == "ymd":
            def _ymd(row):
                try:
                    y = int(row[date_cfg["year_col"]])
                    m = int(row[date_cfg["month_col"]])
                    d = int(row[date_cfg["day_col"]])
                    h  = int(row[date_cfg["hour_col"]])  if date_cfg.get("hour_col")  else 0
                    mn = int(row[date_cfg["min_col"]])   if date_cfg.get("min_col")   else 0
                    return pd.Timestamp(y, m, d, h, mn)
                except Exception:
                    return pd.NaT
            dt = src.apply(_ymd, axis=1)
    except Exception:
        dt = None

    country  = settings["country"].strip().upper()
    site     = settings["location_id"].strip()
    location = settings["location_id"].strip()

    def _survey_id(ts):
        if pd.isna(ts):
            return ""
        return f"{country}_{site}_{ts.strftime('%Y%m')}" if country else site

    def _occ_id(ts):
        if pd.isna(ts):
            return ""
        return f"{country}_{site}_{ts.strftime('%Y%m%d%H%M%S')}" if country else site

    rows = []
    for i, src_row in src.iterrows():
        ts = dt.iloc[i] if dt is not None else pd.NaT

        def _get(gs_field):
            src_col = col_map.get(gs_field)
            if not src_col:
                return None
            val = src_row.get(src_col)
            if gs_field in INT_FIELDS:
                return _safe_int(val)
            if gs_field in FLOAT_FIELDS:
                return _safe_float(val)
            v = str(val).strip() if pd.notna(val) else ""
            return v if v and v.lower() != "nan" else ""

        row = {
            "Survey.vessel":             settings["vessel"],
            "Survey.id":                 _get("Survey.id") or _survey_id(ts),
            "Occurrence.occurrenceID":   _get("Occurrence.occurrenceID") or _occ_id(ts),
            "Encounter.decimalLongitude": _get("Encounter.decimalLongitude"),
            "Encounter.decimalLatitude":  _get("Encounter.decimalLatitude"),
            "Encounter.locationID":       location,
            "Encounter.year":             ts.year  if pd.notna(ts) else None,
            "Encounter.month":            ts.month if pd.notna(ts) else None,
            "Encounter.day":              ts.day   if pd.notna(ts) else None,
            "Encounter.hour":             ts.hour  if pd.notna(ts) else None,
            "Encounter.minutes":          ts.minute if pd.notna(ts) else None,
            "Encounter.submitterID":      settings["submitter"],
            "Occurrence.groupSize":       _get("Occurrence.groupSize"),
            "Occurrence.numAdults":       _get("Occurrence.numAdults"),
            "Occurrence.numAdultFemales": _get("Occurrence.numAdultFemales"),
            "Occurrence.numAdultMales":   _get("Occurrence.numAdultMales"),
            "Occurrence.numSubAdults":    _get("Occurrence.numSubAdults"),
            "Occurrence.numSubFemales":   _get("Occurrence.numSubFemales"),
            "Occurrence.numSubMales":     _get("Occurrence.numSubMales"),
            "Occurrence.numCalves":       _get("Occurrence.numCalves"),
            "Occurrence.distance":        _get("Occurrence.distance"),
            "Occurrence.bearing":         _get("Occurrence.bearing"),
            "Encounter.individualID":     _get("Encounter.individualID"),
            "Encounter.sex":              _get("Encounter.sex"),
            "Encounter.lifeStage":        _get("Encounter.lifeStage"),
            "Encounter.genus":            settings["genus"],
            "Encounter.specificEpithet":  settings["epithet"],
            "Encounter.occurrenceRemarks": _get("Encounter.occurrenceRemarks"),
            "Encounter.mediaAsset0":      _get("Encounter.mediaAsset0") or None,
            "Encounter.mediaAsset1":      _get("Encounter.mediaAsset1") or None,
        }
        rows.append(row)

    return pd.DataFrame(rows)


def main():
    st.title("📊 Format xlsx for GiraffeSpotter")
    st.caption(
        "Upload any survey spreadsheet, map its columns to the GiraffeSpotter bulk-import "
        "format, and download a ready-to-upload xlsx. No EarthRanger login required."
    )

    # ── Step 1: Upload ─────────────────────────────────────────────────────────
    st.subheader("Step 1: Upload survey file")
    uploaded = st.file_uploader(
        "Upload xlsx, xls or csv",
        type=["xlsx", "xls", "csv"],
        help="One row per individual giraffe encounter.",
    )
    if not uploaded:
        st.stop()

    try:
        src = _load_file(uploaded)
    except Exception as e:
        st.error(f"Could not read file: {e}")
        st.stop()

    st.success(f"Loaded **{len(src):,} rows** × **{len(src.columns)} columns**")

    with st.expander("Preview source data", expanded=False):
        st.dataframe(src.head(20), use_container_width=True)

    one_per_row = st.checkbox(
        "Each row represents one individual giraffe (one-giraffe-per-row format)",
        value=True,
    )
    if not one_per_row:
        st.warning(
            "This tool only supports one-giraffe-per-row data. "
            "Please reshape your spreadsheet (e.g. one row per Herd member) before uploading."
        )
        st.stop()

    src_cols    = list(src.columns)
    none_option = "(not mapped)"
    src_cols_opt = [none_option] + src_cols

    # ── Step 2: Survey settings ────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Step 2: Survey settings")

    c1, c2, c3 = st.columns(3)
    with c1:
        submitter   = st.text_input("GiraffeSpotter username (submitterID) *", placeholder="e.g. courtney_gcf")
        location_id = st.text_input("Location / site name (locationID) *",     placeholder="e.g. Hoanib")
        country     = st.text_input("Country code (for auto-generated IDs)",    placeholder="e.g. NAM", max_chars=3).upper()
    with c2:
        vessel  = st.selectbox("Survey method (Survey.vessel)", VESSEL_OPTIONS)
        genus   = st.text_input("Genus", value="Giraffa")
        epithet = st.selectbox("Species epithet", SPECIES_OPTIONS)
    with c3:
        st.caption(
            "**Required fields** (marked \\*) must be filled to generate a valid GS file.  \n"
            "Country code is used to auto-build Survey.id and Occurrence.occurrenceID — "
            "leave blank to omit the prefix."
        )

    settings = dict(
        submitter=submitter,
        location_id=location_id,
        country=country,
        vessel=vessel,
        genus=genus,
        epithet=epithet,
    )

    # ── Step 3: Date & time ────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Step 3: Date & time")
    st.caption(
        "Dates are used to populate Encounter.year/month/day/hour/minutes and "
        "to auto-generate Survey.id and Occurrence.occurrenceID."
    )

    date_mode = st.radio(
        "How is the date stored in your file?",
        ["Single datetime column", "Separate date + time columns", "Separate year / month / day columns"],
        horizontal=True,
    )

    date_cfg = {"mode": None}
    if date_mode == "Single datetime column":
        date_cfg["mode"]   = "datetime"
        date_cfg["dt_col"] = st.selectbox("Datetime column", src_cols_opt, key="dt_col")
        if date_cfg["dt_col"] == none_option:
            date_cfg["dt_col"] = None

    elif date_mode == "Separate date + time columns":
        date_cfg["mode"] = "date_time"
        dc1, dc2 = st.columns(2)
        with dc1:
            date_cfg["date_col"] = st.selectbox("Date column", src_cols_opt, key="date_col")
            if date_cfg["date_col"] == none_option:
                date_cfg["date_col"] = None
        with dc2:
            date_cfg["time_col"] = st.selectbox("Time column (optional)", src_cols_opt, key="time_col")
            if date_cfg["time_col"] == none_option:
                date_cfg["time_col"] = None

    else:
        date_cfg["mode"] = "ymd"
        dc1, dc2, dc3, dc4, dc5 = st.columns(5)
        def _pick(label, key, col):
            with col:
                v = st.selectbox(label, src_cols_opt, key=key)
                return None if v == none_option else v
        date_cfg["year_col"]  = _pick("Year",   "ymd_y", dc1)
        date_cfg["month_col"] = _pick("Month",  "ymd_m", dc2)
        date_cfg["day_col"]   = _pick("Day",    "ymd_d", dc3)
        date_cfg["hour_col"]  = _pick("Hour (optional)",   "ymd_h",  dc4)
        date_cfg["min_col"]   = _pick("Minute (optional)", "ymd_mn", dc5)

    # ── Step 4: Column mapping ─────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Step 4: Map columns")
    st.caption("Select which column in your file maps to each GiraffeSpotter field. Fields marked * are required.")

    col_map = {}
    sections_seen = []
    section_fields = {}
    for gs_field, label, required, section in GS_FIELDS:
        section_fields.setdefault(section, []).append((gs_field, label, required))

    for section, fields in section_fields.items():
        with st.expander(section, expanded=(section in ("Location", "Individual"))):
            ncols = 2 if len(fields) > 2 else len(fields)
            cols  = st.columns(ncols)
            for idx, (gs_field, label, required) in enumerate(fields):
                marker = " *" if required else ""
                with cols[idx % ncols]:
                    # Auto-suggest: look for a source column whose name contains key words
                    keywords = label.lower().split()
                    default_idx = 0
                    for ci, sc in enumerate(src_cols_opt):
                        sc_low = sc.lower()
                        if any(kw in sc_low for kw in keywords):
                            default_idx = ci
                            break
                    chosen = st.selectbox(
                        f"{label}{marker}",
                        src_cols_opt,
                        index=default_idx,
                        key=f"map_{gs_field}",
                    )
                    col_map[gs_field] = None if chosen == none_option else chosen

    # ── Step 5: Generate ───────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Step 5: Generate & download")

    missing = []
    if not submitter:
        missing.append("GiraffeSpotter username")
    if not location_id:
        missing.append("Location / site name")
    if not col_map.get("Encounter.decimalLatitude"):
        missing.append("Latitude column mapping")
    if not col_map.get("Encounter.decimalLongitude"):
        missing.append("Longitude column mapping")

    if missing:
        st.warning("Please fill in before generating: " + ", ".join(missing))

    if st.button("Generate GiraffeSpotter file", type="primary", disabled=bool(missing)):
        with st.spinner("Building GS output…"):
            try:
                gs = _build_gs(src, settings, date_cfg, col_map)
            except Exception as e:
                st.error(f"Error building output: {e}")
                st.exception(e)
                st.stop()

        st.success(f"✅ Generated **{len(gs)}** rows ready for GiraffeSpotter.")

        with st.expander("Preview GS output", expanded=True):
            st.dataframe(gs, use_container_width=True)

        today = date.today().strftime("%Y%m%d")
        slug  = f"{country}{location_id}" if country else location_id
        filename = f"GS_bulkimport_{slug}_{today}.xlsx"

        st.download_button(
            "⬇️ Download GS xlsx",
            data=_excel_bytes(gs),
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
