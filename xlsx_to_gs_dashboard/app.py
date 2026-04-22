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
    ("Occurrence.numAdults",         "# adults (total)",      False, "Group counts"),
    ("Occurrence.numAdultFemales",   "# adult females",       False, "Group counts"),
    ("Occurrence.numAdultMales",     "# adult males",         False, "Group counts"),
    ("Occurrence.numSubAdults",      "# sub-adults (total)",  False, "Group counts"),
    ("Occurrence.numSubFemales",     "# sub-adult females",   False, "Group counts"),
    ("Occurrence.numSubMales",       "# sub-adult males",     False, "Group counts"),
    ("Occurrence.numCalves",         "# calves / juveniles",  False, "Group counts"),
    # Sighting geometry
    ("Occurrence.distance",          "Distance (m)",          False, "Sighting geometry"),
    ("Occurrence.bearing",           "Bearing (°)",           False, "Sighting geometry"),
    # Media
    ("Encounter.mediaAsset0",        "Photo 1 filename",      False, "Media"),
    ("Encounter.mediaAsset1",        "Photo 2 filename",      False, "Media"),
]

# Synonyms for auto-suggesting column matches.
# Two lists per field:
#   "exact"     — the full column name must equal one of these (case-insensitive)
#   "substring" — the synonym just needs to appear anywhere in the column name
SYNONYMS = {
    "Encounter.decimalLatitude":    {"exact": ["lat", "latitude", "y"],
                                     "substring": ["latitude"]},
    "Encounter.decimalLongitude":   {"exact": ["lon", "long", "longitude", "x"],
                                     "substring": ["longitude"]},
    "Encounter.individualID":       {"exact": ["id", "name", "individual_id", "giraffe_id"],
                                     "substring": ["individual", "giraffe_id", "animal_id"]},
    "Encounter.sex":                {"exact": ["sex", "gender"],
                                     "substring": ["sex", "gender"]},
    "Encounter.lifeStage":          {"exact": ["age", "class", "stage"],
                                     "substring": ["life_stage", "lifestage", "age_class"]},
    "Encounter.occurrenceRemarks":  {"exact": ["notes", "remarks", "comments", "activity"],
                                     "substring": ["note", "remark", "comment", "activity", "behaviour", "behavior"]},
    "Occurrence.groupSize":         {"exact": ["size", "total", "count", "n"],
                                     "substring": ["group_size", "herd_size", "group size"]},
    "Occurrence.numAdults":         {"exact": ["adults", "ad"],
                                     "substring": ["num_adult", "n_adult", "nadult"]},
    "Occurrence.numAdultFemales":   {"exact": ["female", "females", "af"],
                                     "substring": ["adult_f", "adult female"]},
    "Occurrence.numAdultMales":     {"exact": ["male", "males", "am"],
                                     "substring": ["adult_m", "adult male"]},
    "Occurrence.numSubAdults":      {"exact": ["sa", "subadult", "sub_adult", "subadults", "juvenile"],
                                     "substring": ["sub_adult", "subadult"]},
    "Occurrence.numSubFemales":     {"exact": ["sf", "subf", "sub_f"],
                                     "substring": ["sub_f", "subf"]},
    "Occurrence.numSubMales":       {"exact": ["sm", "subm", "sub_m"],
                                     "substring": ["sub_m", "subm"]},
    "Occurrence.numCalves":         {"exact": ["baby", "babies", "infant", "infants", "calf", "calves", "cub"],
                                     "substring": ["calf", "calv", "baby", "infant", "juvenile"]},
    "Occurrence.distance":          {"exact": ["dist", "distance"],
                                     "substring": ["dist", "distance"]},
    "Occurrence.bearing":           {"exact": ["bearing", "direction", "azimuth"],
                                     "substring": ["bearing", "azimuth"]},
    "Encounter.mediaAsset0":        {"exact": ["photo", "photo1", "image", "right"],
                                     "substring": ["photo1", "image1", "right_photo", "media0"]},
    "Encounter.mediaAsset1":        {"exact": ["photo2", "left"],
                                     "substring": ["photo2", "image2", "left_photo", "media1"]},
}

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
    "random_encounter",
]

# Full subspecies epithets as expected by GiraffeSpotter
SPECIES_OPTIONS = [
    "giraffa giraffa",
    "giraffa angolensis",
    "tippelskirchi tippelskirchi",
    "tippelskirchi thornicrofti",
    "camelopardalis camelopardalis",
    "camelopardalis antiquorum",
    "camelopardalis peralta",
]

# ISO-3166 alpha-3 codes for countries where GCF operates
COUNTRY_CODES = [
    ("BWA", "Botswana"),
    ("CMR", "Cameroon"),
    ("ETH", "Ethiopia"),
    ("KEN", "Kenya"),
    ("MOZ", "Mozambique"),
    ("NAM", "Namibia"),
    ("NGA", "Nigeria"),
    ("RWA", "Rwanda"),
    ("SOM", "Somalia"),
    ("SSD", "South Sudan"),
    ("TZA", "Tanzania"),
    ("UGA", "Uganda"),
    ("ZAF", "South Africa"),
    ("ZMB", "Zambia"),
    ("ZWE", "Zimbabwe"),
]

NONE_OPT = "(not mapped)"


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


def _load_file(uploaded) -> tuple[pd.DataFrame, list[str]]:
    """Return (dataframe, sheet_names). sheet_names is [] for CSV."""
    name = uploaded.name.lower()
    if name.endswith(".csv"):
        return pd.read_csv(uploaded), []
    xf = pd.ExcelFile(uploaded)
    return None, xf.sheet_names  # caller picks sheet then re-reads


def _auto_suggest(gs_field: str, src_cols_opt: list[str]) -> int:
    """Return the index into src_cols_opt that best matches gs_field, or 0 (= not mapped)."""
    syn_def = SYNONYMS.get(gs_field, {})
    exact_syns     = syn_def.get("exact", [])
    substring_syns = syn_def.get("substring", [])
    # Exact match first (higher confidence)
    for ci, sc in enumerate(src_cols_opt):
        if sc.lower() in exact_syns:
            return ci
    # Substring match fallback
    for ci, sc in enumerate(src_cols_opt):
        sc_low = sc.lower()
        if any(syn in sc_low for syn in substring_syns):
            return ci
    return 0


def _build_gs(src: pd.DataFrame, settings: dict, date_cfg: dict, col_map: dict) -> pd.DataFrame:
    # ── Resolve datetime series ────────────────────────────────────────────────
    dt = None
    mode = date_cfg["mode"]
    try:
        if mode == "datetime" and date_cfg.get("dt_col"):
            dt = pd.to_datetime(src[date_cfg["dt_col"]], errors="coerce")
        elif mode == "date_time":
            d = pd.to_datetime(src[date_cfg["date_col"]].astype(str), errors="coerce")
            if date_cfg.get("time_col"):
                t = pd.to_datetime(
                    src[date_cfg["time_col"]].astype(str), errors="coerce",
                    format="mixed",
                )
                dt = d + pd.to_timedelta(
                    t.dt.hour * 3600 + t.dt.minute * 60, unit="s"
                )
            else:
                dt = d
        elif mode == "ymd":
            def _ymd(row):
                try:
                    y  = int(row[date_cfg["year_col"]])
                    m  = int(row[date_cfg["month_col"]])
                    d  = int(row[date_cfg["day_col"]])
                    h  = int(row[date_cfg["hour_col"]]) if date_cfg.get("hour_col") else 0
                    mn = int(row[date_cfg["min_col"]])  if date_cfg.get("min_col")  else 0
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
        prefix = f"{country}_{site}" if country else site
        return f"{prefix}_{ts.strftime('%Y%m')}"

    def _occ_id(ts):
        if pd.isna(ts):
            return ""
        prefix = f"{country}_{site}" if country else site
        return f"{prefix}_{ts.strftime('%Y%m%d%H%M%S')}"

    rows = []
    for i in range(len(src)):
        src_row = src.iloc[i]
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
            "Survey.vessel":              settings["vessel"],
            "Survey.id":                  _survey_id(ts),
            "Occurrence.occurrenceID":    _occ_id(ts),
            "Encounter.decimalLongitude": _get("Encounter.decimalLongitude"),
            "Encounter.decimalLatitude":  _get("Encounter.decimalLatitude"),
            "Encounter.locationID":       location,
            "Encounter.year":             ts.year   if pd.notna(ts) else None,
            "Encounter.month":            ts.month  if pd.notna(ts) else None,
            "Encounter.day":              ts.day    if pd.notna(ts) else None,
            "Encounter.hour":             ts.hour   if pd.notna(ts) else None,
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
    )
    if not uploaded:
        st.stop()

    # Sheet selection for multi-sheet Excel files
    is_csv = uploaded.name.lower().endswith(".csv")
    if is_csv:
        try:
            src = pd.read_csv(uploaded)
        except Exception as e:
            st.error(f"Could not read file: {e}")
            st.stop()
    else:
        try:
            xf = pd.ExcelFile(uploaded)
            sheet_names = xf.sheet_names
        except Exception as e:
            st.error(f"Could not read file: {e}")
            st.stop()

        if len(sheet_names) > 1:
            sheet = st.selectbox("Select sheet", sheet_names)
        else:
            sheet = sheet_names[0]

        try:
            src = xf.parse(sheet)
        except Exception as e:
            st.error(f"Could not read sheet '{sheet}': {e}")
            st.stop()

    # Drop entirely empty rows/cols that Excel sometimes adds
    src = src.dropna(how="all").reset_index(drop=True)
    src.columns = [str(c).strip() for c in src.columns]

    st.success(f"Loaded **{len(src):,} rows** × **{len(src.columns)} columns**")

    with st.expander("Preview source data", expanded=False):
        st.dataframe(src.head(20), use_container_width=True)

    st.info(
        "This tool maps **one source row → one GiraffeSpotter row**. "
        "Each row can be a herd-level sighting (group counts, no individual ID) "
        "or an individually-identified giraffe — both work. "
        "If your file has multiple giraffes per row you'll need to reshape it first."
    )

    src_cols     = list(src.columns)
    src_cols_opt = [NONE_OPT] + src_cols

    # Auto-detect date column names for sensible defaults
    _col_lower = {c.lower(): c for c in src_cols}
    _has_date  = any("date" in c for c in _col_lower)
    _has_time  = any(c in _col_lower for c in ["time"])
    _has_dt    = any(c in _col_lower for c in ["datetime", "date_time", "timestamp"])

    # ── Step 2: Survey settings ────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Step 2: Survey settings")

    c1, c2, c3 = st.columns(3)
    with c1:
        submitter   = st.text_input("GiraffeSpotter username (submitterID) *", placeholder="e.g. courtney_gcf")
        location_id = st.text_input("Location / site name (locationID) *",     placeholder="e.g. Rombo")
        country_labels = [f"{code} — {name}" for code, name in COUNTRY_CODES]
        country_sel    = st.selectbox("Country", country_labels,
                                      index=next((i for i, (c, _) in enumerate(COUNTRY_CODES) if c == "TZA"), 0))
        country = COUNTRY_CODES[country_labels.index(country_sel)][0]
    with c2:
        vessel  = st.selectbox("Survey method (Survey.vessel)", VESSEL_OPTIONS)
        genus   = st.text_input("Genus", value="Giraffa")
        epithet = st.selectbox("Species epithet", SPECIES_OPTIONS,
                               index=SPECIES_OPTIONS.index("tippelskirchi tippelskirchi"))
    with c3:
        st.caption(
            "**Required fields** (marked \\*) must be filled before generating.  \n\n"
            "Country code is used to build `Survey.id` and `Occurrence.occurrenceID` "
            "— leave blank to omit the prefix."
        )

    settings = dict(
        submitter=submitter, location_id=location_id, country=country,
        vessel=vessel, genus=genus, epithet=epithet,
    )

    # ── Step 3: Date & time ────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Step 3: Date & time")
    st.caption(
        "Used to populate Encounter.year/month/day/hour/minutes and to "
        "auto-generate Survey.id and Occurrence.occurrenceID."
    )

    date_modes = [
        "Separate date + time columns",
        "Single datetime column",
        "Separate year / month / day columns",
    ]
    default_mode = 1 if _has_dt else 0   # prefer date+time when both cols likely present
    date_mode = st.radio("How is the date stored?", date_modes,
                         index=default_mode, horizontal=True)

    date_cfg = {"mode": None}

    if date_mode == "Single datetime column":
        date_cfg["mode"] = "datetime"
        default_dt = next((i+1 for i, c in enumerate(src_cols)
                           if any(k in c.lower() for k in ["datetime","timestamp","date_time"])), 0)
        sel = st.selectbox("Datetime column", src_cols_opt, index=default_dt, key="dt_col")
        date_cfg["dt_col"] = None if sel == NONE_OPT else sel

    elif date_mode == "Separate date + time columns":
        date_cfg["mode"] = "date_time"
        dc1, dc2 = st.columns(2)
        with dc1:
            default_d = next((i+1 for i, c in enumerate(src_cols) if "date" in c.lower()), 0)
            sel_d = st.selectbox("Date column", src_cols_opt, index=default_d, key="date_col")
            date_cfg["date_col"] = None if sel_d == NONE_OPT else sel_d
        with dc2:
            default_t = next((i+1 for i, c in enumerate(src_cols)
                              if c.lower() in ("time", "time_of_day", "obs_time")), 0)
            sel_t = st.selectbox("Time column (optional)", src_cols_opt, index=default_t, key="time_col")
            date_cfg["time_col"] = None if sel_t == NONE_OPT else sel_t

    else:
        date_cfg["mode"] = "ymd"
        dc1, dc2, dc3, dc4, dc5 = st.columns(5)
        def _pick(label, key, hints, col_widget):
            default = next((i+1 for i, c in enumerate(src_cols)
                            if any(h in c.lower() for h in hints)), 0)
            with col_widget:
                v = st.selectbox(label, src_cols_opt, index=default, key=key)
                return None if v == NONE_OPT else v
        date_cfg["year_col"]  = _pick("Year",             "ymd_y",  ["year"],   dc1)
        date_cfg["month_col"] = _pick("Month",            "ymd_m",  ["month"],  dc2)
        date_cfg["day_col"]   = _pick("Day",              "ymd_d",  ["day"],    dc3)
        date_cfg["hour_col"]  = _pick("Hour (optional)",  "ymd_h",  ["hour"],   dc4)
        date_cfg["min_col"]   = _pick("Minute (optional)","ymd_mn", ["minute"], dc5)

    # ── Step 4: Column mapping ─────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Step 4: Map columns")
    st.caption(
        "Select which column in your file maps to each GiraffeSpotter field. "
        "Suggestions are auto-filled based on column names — check them before generating. "
        "Fields marked \\* are required."
    )

    # Warn about common multi-column situations
    juvenile_cols = [c for c in src_cols if any(w in c.lower() for w in ["baby","infant","cub","juvenile"])]
    if len(juvenile_cols) > 1:
        st.warning(
            f"Multiple juvenile columns detected ({', '.join(juvenile_cols)}). "
            "GiraffeSpotter has a single **# calves / juveniles** field — "
            "map one column or combine them into a single column before uploading."
        )

    col_map      = {}
    section_fields: dict = {}
    for gs_field, label, required, section in GS_FIELDS:
        section_fields.setdefault(section, []).append((gs_field, label, required))

    for section, fields in section_fields.items():
        with st.expander(section, expanded=(section in ("Location", "Individual", "Group counts"))):
            ncols = 2 if len(fields) > 2 else len(fields)
            cols  = st.columns(ncols)
            for idx, (gs_field, label, required) in enumerate(fields):
                marker = " *" if required else ""
                with cols[idx % ncols]:
                    default_idx = _auto_suggest(gs_field, src_cols_opt)
                    chosen = st.selectbox(
                        f"{label}{marker}",
                        src_cols_opt,
                        index=default_idx,
                        key=f"map_{gs_field}",
                    )
                    col_map[gs_field] = None if chosen == NONE_OPT else chosen

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

        today    = date.today().strftime("%Y%m%d")
        slug     = f"{country}_{location_id}" if country else location_id
        filename = f"GS_bulkimport_{slug}_{today}.xlsx"

        st.download_button(
            "⬇️ Download GS xlsx",
            data=_excel_bytes(gs),
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
