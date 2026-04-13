"""
SMART2WB: SMART Export → GiraffeSpotter (WildBook) Bulk Import Formatter
Uploads a SMART patrol CSV, reformats it for GiraffeSpotter bulk upload,
and produces a downloadable .xlsx file.
"""

import io
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st
from PIL import Image
from PIL.ExifTags import TAGS
sys.path.append(str(Path(__file__).parent.parent))
from shared.utils import render_page_header


# ─── Helpers ──────────────────────────────────────────────────────────────────

def parse_smart_csv(uploaded_file) -> pd.DataFrame:
    """Read SMART export CSV, trying multiple encodings."""
    raw = uploaded_file.read()
    for enc in ("utf-8-sig", "latin-1", "cp1252", "utf-16"):
        try:
            return pd.read_csv(io.BytesIO(raw), encoding=enc)
        except (UnicodeDecodeError, Exception):
            continue
    raise ValueError("Could not decode CSV with any supported encoding (utf-8, latin-1, cp1252, utf-16).")


def detect_date_col(df: pd.DataFrame) -> str | None:
    for col in df.columns:
        if col.strip().lower() == "waypoint date":
            return col
    return None


def detect_time_col(df: pd.DataFrame) -> str | None:
    for col in df.columns:
        if col.strip().lower() == "waypoint time":
            return col
    return None


def parse_datetime_series(date_ser: pd.Series, time_ser: pd.Series | None) -> pd.Series:
    """Parse date + optional time series into a datetime series."""
    dates = date_ser.astype(str).str.strip()
    dates = dates.str.replace(r'\bSept\b', 'Sep', regex=True, case=False)
    times = time_ser.astype(str).str.strip() if time_ser is not None else pd.Series([""] * len(dates))
    times = times.str.upper().replace("NAN", "")

    date_fmts = ["%d-%b-%y", "%d-%b-%Y", "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%Y/%m/%d", "%d %m %Y"]
    time_fmts = ["%H:%M:%S", "%H:%M", "%I:%M:%S %p", "%I:%M %p"]

    result = pd.Series([pd.NaT] * len(dates), dtype="datetime64[ns]")

    for dfmt in date_fmts:
        unparsed = result.isna()
        if not unparsed.any():
            break
        for tfmt in time_fmts:
            combined = dates[unparsed] + " " + times[unparsed]
            parsed = pd.to_datetime(combined, format=f"{dfmt} {tfmt}", errors="coerce")
            result[unparsed] = result[unparsed].fillna(parsed)
        unparsed = result.isna()
        if unparsed.any():
            parsed = pd.to_datetime(dates[unparsed], format=dfmt, errors="coerce")
            result[unparsed] = result[unparsed].fillna(parsed)

    return result


def coerce_count(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0).astype(int)


def clean_str(val) -> str:
    if pd.isna(val):
        return ""
    s = str(val).strip()
    return "" if s.lower() == "nan" else s


def extract_exif_datetime(img_file) -> datetime | None:
    """Extract DateTimeOriginal from an uploaded image file."""
    try:
        img = Image.open(img_file)
        exif_data = img._getexif()
        if not exif_data:
            return None
        for tag_id, val in exif_data.items():
            if TAGS.get(tag_id) == "DateTimeOriginal":
                return datetime.strptime(val, "%Y:%m:%d %H:%M:%S")
    except Exception:
        return None
    return None


def match_images(smrt_dttms: pd.Series, image_files: list, minute_buffer: int) -> pd.DataFrame:
    """
    For each SMART record datetime, find uploaded images whose EXIF datetime
    falls within minute_buffer minutes. Returns a DataFrame of image filename
    columns (Encounter.mediaAsset0, 1, …) aligned to smrt_dttms index.
    """
    # Extract EXIF datetimes from all uploaded images
    image_info = []  # list of (filename_stem, exif_dttm)
    progress = st.progress(0, text="Reading image EXIF data…")
    for i, f in enumerate(image_files):
        dttm = extract_exif_datetime(f)
        stem = f.name.rsplit(".", 1)[0]
        image_info.append((stem + ".JPG", dttm))
        progress.progress((i + 1) / len(image_files), text=f"Reading EXIF: {f.name}")
    progress.empty()

    buf = timedelta(minutes=minute_buffer)
    rows = []
    for smrt_dttm in smrt_dttms:
        if pd.isna(smrt_dttm):
            rows.append([])
            continue
        matched = [
            name for name, img_dttm in image_info
            if img_dttm is not None and abs(smrt_dttm - img_dttm) <= buf
        ]
        rows.append(matched)

    max_imgs = max((len(r) for r in rows), default=0)
    if max_imgs == 0:
        return pd.DataFrame(index=smrt_dttms.index)

    cols = {f"Encounter.mediaAsset{i}": [] for i in range(max_imgs)}
    for matched in rows:
        for i in range(max_imgs):
            cols[f"Encounter.mediaAsset{i}"].append(matched[i] if i < len(matched) else "")

    return pd.DataFrame(cols, index=smrt_dttms.index)


def build_wildbook(smrt: pd.DataFrame, settings: dict, image_files: list, minute_buffer: int, photo_col: str | None = None) -> tuple[pd.DataFrame, dict]:
    """Transform SMART dataframe into GiraffeSpotter Wildbook bulk-upload format."""
    country  = settings["country"]
    location = settings["locationID"]
    user     = settings["username"]
    genus    = settings["genus"]
    epithet  = settings["specificEpithet"]

    smrt = smrt.copy()

    # ── Parse datetimes ──────────────────────────────────────────────────────
    date_col = detect_date_col(smrt)
    time_col = detect_time_col(smrt)
    diagnostics = {"date_col": date_col, "time_col": time_col}

    if date_col:
        smrt["_dttm"] = parse_datetime_series(
            smrt[date_col],
            smrt[time_col] if time_col else None,
        )
    else:
        smrt["_dttm"] = pd.NaT

    diagnostics["parsed_ok"]   = int(smrt["_dttm"].notna().sum())
    diagnostics["parsed_fail"] = int(smrt["_dttm"].isna().sum())
    failed_mask = smrt["_dttm"].isna()
    diagnostics["fail_dates"] = smrt.loc[failed_mask, date_col].tolist() if date_col else []
    diagnostics["fail_times"] = smrt.loc[failed_mask, time_col].tolist() if time_col else []

    # ── Coerce count columns ─────────────────────────────────────────────────
    count_cols = [
        "Number of adult females", "Number of adult males",
        "Number of subadult females", "Number of subadult males",
        "Number of female calves", "Number of male calves",
        "Number of unknown calves",
    ]
    for col in count_cols:
        smrt[col] = coerce_count(smrt[col]) if col in smrt.columns else 0

    smrt["_num_calves"] = (
        smrt["Number of female calves"]
        + smrt["Number of male calves"]
        + smrt["Number of unknown calves"]
    )

    if "Group size" in smrt.columns:
        smrt["_group_size"] = pd.to_numeric(smrt["Group size"], errors="coerce").fillna(0).astype(int)
    else:
        smrt["_group_size"] = (
            smrt["Number of adult females"] + smrt["Number of adult males"]
            + smrt["Number of subadult females"] + smrt["Number of subadult males"]
            + smrt["_num_calves"]
        )

    # ── Build core dataframe ─────────────────────────────────────────────────
    def _oid(dttm):
        return f"{country}_{dttm.strftime('%Y%m%d%H%M%S')}" if pd.notna(dttm) else f"{country}_UNKNOWN"

    vb_locality = smrt["Location"].apply(clean_str) if "Location" in smrt.columns else settings["verbatimLocality"]
    veg_class   = smrt["Vegetation class"].apply(clean_str) if "Vegetation class" in smrt.columns else pd.Series([""] * len(smrt))

    observer_col = next((c for c in smrt.columns if c.strip().lower() == "zcp observer"), None)
    if observer_col:
        obs_str = smrt[observer_col].apply(lambda v: f"ZCP observer: {clean_str(v)}" if clean_str(v) else "")
        remarks = veg_class.str.cat(obs_str, sep=" | ", na_rep="").str.strip(" |")
    else:
        remarks = veg_class

    dttm = smrt["_dttm"]

    gs = pd.DataFrame({
        "Survey.vessel":             "random_encounter",
        "Survey.id":                 "",
        "Occurrence.occurrenceID":   dttm.apply(_oid),
        "Encounter.decimalLongitude": smrt.get("X", smrt.get("Longitude", pd.Series([""] * len(smrt)))),
        "Encounter.decimalLatitude":  smrt.get("Y", smrt.get("Latitude",  pd.Series([""] * len(smrt)))),
        "Encounter.locationID":      location,
        "Encounter.verbatimLocality": vb_locality,
        "Encounter.year":            dttm.apply(lambda d: d.year   if pd.notna(d) else ""),
        "Encounter.month":           dttm.apply(lambda d: d.month  if pd.notna(d) else ""),
        "Encounter.day":             dttm.apply(lambda d: d.day    if pd.notna(d) else ""),
        "Encounter.hour":            dttm.apply(lambda d: d.hour   if pd.notna(d) else ""),
        "Encounter.minutes":         dttm.apply(lambda d: d.minute if pd.notna(d) else ""),
        "Encounter.submitterID":     user,
        "Occurrence.groupSize":      smrt["_group_size"],
        "Occurrence.numAdults":      smrt["Number of adult females"] + smrt["Number of adult males"],
        "Occurrence.numAdultFemales": smrt["Number of adult females"],
        "Occurrence.numAdultMales":  smrt["Number of adult males"],
        "Occurrence.numSubAdults":   smrt["Number of subadult females"] + smrt["Number of subadult males"],
        "Occurrence.numSubFemales":  smrt["Number of subadult females"],
        "Occurrence.numSubMales":    smrt["Number of subadult males"],
        "Occurrence.numCalves":      smrt["_num_calves"],
        "Occurrence.observer":       "",
        "Occurrence.distance":       "",
        "Occurrence.bearing":        "",
        "Encounter.behavior":        "",
        "Encounter.sex":             "",
        "Encounter.genus":           genus,
        "Encounter.specificEpithet": epithet,
        "Encounter.occurrenceRemarks": remarks,
        "Encounter.individualID":    "",
        "MarkedIndividual.nickname": "",
    })

    # ── Media assets ─────────────────────────────────────────────────────────
    media_df = pd.DataFrame(index=smrt.index)

    diagnostics["photo_cols_found"] = photo_col if photo_col else None

    if photo_col and photo_col in smrt.columns:
        # Split comma-separated photo numbers and format as ZMB_Luangwa_yyyymmdd_photonumber.JPG
        def fmt_photo(photo_num: str, dttm, country: str, loc: str) -> str:
            num = photo_num.strip()
            if not num:
                return ""
            date_str = dttm.strftime("%Y%m%d") if pd.notna(dttm) else "UNKNOWN"
            return f"{country}_{loc}_{date_str}_{num}.JPG"

        split_vals = smrt[photo_col].apply(clean_str).str.split(r"[,;]\s*", expand=False)
        max_photos = split_vals.apply(len).max()
        for i in range(max_photos):
            media_df[f"Encounter.mediaAsset{i}"] = [
                fmt_photo(lst[i] if i < len(lst) else "", dttm, country, location)
                for lst, dttm in zip(split_vals, smrt["_dttm"])
            ]
        diagnostics["images_matched"] = (media_df != "").any(axis=1).sum()

    # Fallback: EXIF-based matching from uploaded image files
    elif image_files:
        media_df = match_images(smrt["_dttm"], image_files, minute_buffer)
        diagnostics["images_matched"] = (media_df != "").any(axis=1).sum() if not media_df.empty else 0
    else:
        diagnostics["images_matched"] = None

    if not media_df.empty:
        gs = pd.concat([gs, media_df], axis=1)

    # ── Clean nan strings ────────────────────────────────────────────────────
    for col in gs.select_dtypes(include="object").columns:
        gs[col] = gs[col].apply(lambda v: "" if pd.isna(v) or str(v).strip().lower() == "nan" else v)

    # ── Expand rows by individual count ─────────────────────────────────────
    individual_count = gs["Occurrence.groupSize"].clip(lower=1).fillna(1).astype(int)
    gs = gs.loc[gs.index.repeat(individual_count)].reset_index(drop=True)

    return gs, diagnostics


def to_xlsx_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Wildbook")
    return buf.getvalue()


# ─── Main UI ──────────────────────────────────────────────────────────────────

def main():
    render_page_header("SMART → Wildbook Converter", "Format SMART patrol data for Wildbook bulk import", "📋")

    # ── Settings ─────────────────────────────────────────────────────────────
    with st.expander("⚙️ Settings", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            country      = st.text_input("Country ISO code", value="ZMB",
                                         help="3-letter ISO code used as prefix (e.g. ZMB)")
            location_id  = st.text_input("Encounter.locationID", value="Luangwa")
            verbatim     = st.text_input("Encounter.verbatimLocality (fallback)", value="Luangwa",
                                         help="Used only when the CSV has no Location column")
            organization = st.text_input("Submitter organisation",
                                         value="Zambian Carnivore Programme")
        with c2:
            username      = st.text_input("Submitter username (WildBook)", value="")
            genus         = st.text_input("Encounter.genus", value="Giraffa")
            epithet       = st.text_input("Encounter.specificEpithet",
                                          value="tippelskirchi thornicrofti")
            minute_buffer = st.number_input("Image match window (minutes)", value=20, min_value=1, max_value=120)

    settings = {
        "country":          country.upper().strip(),
        "locationID":       location_id,
        "verbatimLocality": verbatim,
        "organization":     organization,
        "username":         username,
        "genus":            genus,
        "specificEpithet":  epithet,
    }

    # ── File uploads ──────────────────────────────────────────────────────────
    st.divider()
    uploaded = st.file_uploader("Upload SMART export CSV", type=["csv"])
    image_files = st.file_uploader(
        "Upload images (optional — for mediaAsset matching via EXIF timestamp)",
        type=["jpg", "jpeg"],
        accept_multiple_files=True,
    )

    photo_col_choice = None

    if uploaded is None:
        st.info("Upload a SMART patrol CSV to get started.")
        return

    # ── Parse & preview ───────────────────────────────────────────────────────
    try:
        smrt = parse_smart_csv(uploaded)
    except Exception as e:
        st.error(f"Could not read CSV: {e}")
        return

    st.subheader("Raw SMART data preview")
    st.dataframe(smrt.head(10), use_container_width=True)
    st.caption(f"{len(smrt)} rows · {len(smrt.columns)} columns")

    SMART_PHOTO_COL = "Photo numbers on camera (specify which photos, R and L, are the same individual)"
    if SMART_PHOTO_COL in smrt.columns:
        photo_col_choice = SMART_PHOTO_COL
    else:
        photo_col_choice = st.selectbox(
            "Photo column not auto-detected — select manually if present",
            options=["— none —"] + list(smrt.columns),
        )
        photo_col_choice = None if photo_col_choice == "— none —" else photo_col_choice

    if image_files:
        st.caption(f"{len(image_files)} image(s) uploaded")

    # ── Process ───────────────────────────────────────────────────────────────
    if st.button("Convert to Wildbook format", type="primary"):
        with st.spinner("Converting…"):
            try:
                gs, diag = build_wildbook(smrt, settings, image_files, int(minute_buffer), photo_col=photo_col_choice)
            except Exception as e:
                st.error(f"Conversion failed: {e}")
                st.exception(e)
                return

        # Datetime diagnostics
        if diag["date_col"] is None:
            st.error(f"No 'Waypoint Date' column found. Columns detected: {list(smrt.columns)}")
            return
        if diag["parsed_fail"] > 0:
            st.warning(f"⚠️ {diag['parsed_fail']} of {diag['parsed_ok'] + diag['parsed_fail']} rows could not be parsed as dates.")
            st.dataframe(pd.DataFrame({"date": diag["fail_dates"], "time": diag["fail_times"]}), use_container_width=True)
        else:
            st.success(f"All {diag['parsed_ok']} datetimes parsed successfully.")

        if diag["images_matched"] is not None:
            st.info(f"{diag['images_matched']} of {len(smrt)} SMART records matched at least one image.")
        if diag.get("photo_cols_found"):
            st.info(f"Photo columns detected in CSV: `{diag['photo_cols_found']}`")
        elif not image_files:
            st.warning("No photo column detected in CSV and no images uploaded — mediaAsset columns will be absent.")

        # Summary metrics
        c1, c2, c3 = st.columns(3)
        c1.metric("SMART rows", len(smrt))
        c2.metric("Wildbook rows (expanded)", len(gs))
        c3.metric("Occurrences", gs["Occurrence.occurrenceID"].nunique())

        st.subheader("Wildbook output preview")
        st.dataframe(gs.head(20), use_container_width=True)

        # Download
        year_vals = gs["Encounter.year"].replace("", pd.NA).dropna()
        year_str  = str(int(year_vals.iloc[0])) if len(year_vals) else "YYYY"
        filename  = f"ZCP_{year_str}_bulkimport.xlsx"

        st.download_button(
            label=f"⬇️  Download {filename}",
            data=to_xlsx_bytes(gs),
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
