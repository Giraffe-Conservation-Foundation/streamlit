"""
SMART2WB: SMART Export → GiraffeSpotter (WildBook) Bulk Import Formatter
Uploads a SMART patrol CSV + a ZIP of survey photos (folder with subfolders
per day, e.g. day-folder/AM1/IMG_0001.JPG), reformats it for GiraffeSpotter
bulk upload, and produces a downloadable .xlsx + matched/renamed photos ZIP.

Photo renaming/matching mirrors IMAG_SMART_GSpotter_20240715b.R:
- climb up from each photo past any age/sex/individual-count folder
  (AM1, AF2, SAM, "2 together", etc.) to find the day folder
- pull observer initials from the day folder name (capital letters in the
  last "_"-separated token)
- rename to {country}_{date}_{initials}_{original name}.JPG
- match renamed photos to SMART rows by EXIF datetime within a buffer window
"""

import io
import os
import re
import gc
import shutil
import tempfile
import zipfile
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
from PIL import Image
from PIL.ExifTags import TAGS


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


def extract_exif_datetime(img_bytes_or_file) -> datetime | None:
    """Extract DateTimeOriginal from image bytes (or an uploaded image file)."""
    try:
        img = Image.open(img_bytes_or_file)
        exif_data = img._getexif()
        if not exif_data:
            return None
        for tag_id, val in exif_data.items():
            if TAGS.get(tag_id) == "DateTimeOriginal":
                return datetime.strptime(val, "%Y:%m:%d %H:%M:%S")
    except Exception:
        return None
    return None


# ─── Photo folder handling (mirrors the R script's rename step) ───────────────

# Age/sex/individual-count folder names the R script skips past when climbing
# up to find the observer's day folder — e.g. "AM1", "SAF3", "CU12", bare
# "AM"/"SA"/etc, or "2 together".
_CODE_FOLDER_RE = re.compile(r'^(AM|SAM|SAF|SA|CU|AF|M|F|C)\d{0,2}$', re.IGNORECASE)


def _is_code_folder(name: str) -> bool:
    norm = name.strip()
    if _CODE_FOLDER_RE.match(norm):
        return True
    return norm.lower().replace(" ", "").replace("_", "") == "2together"


def _find_day_folder(dir_parts: list) -> str:
    """Climb up from the immediate parent folder past any age/sex/individual
    code folders (AM1, AF2, SAM, "2 together", …) to find the day folder.
    Handles any nesting depth — including photos sitting directly in the day
    folder with no code folder at all."""
    idx = len(dir_parts) - 1
    while idx >= 0 and _is_code_folder(dir_parts[idx]):
        idx -= 1
    return dir_parts[idx] if idx >= 0 else ""


def _extract_initials(folder_name: str) -> str:
    """Pull observer initials from a day-folder name, e.g. '15 July_FOtten' ->
    'FO'. Mirrors the R script's extract_initials(): strip a trailing
    _<digits>, split on '_', take the last part's capital letters."""
    name = re.sub(r'_\d+$', '', folder_name)
    parts = name.split('_')
    if len(parts) < 2:
        return ""
    last = parts[-1]
    caps = "".join(ch for ch in last if ch.isupper())
    return caps[:2]


def _date_from_filename(filename: str) -> str | None:
    m = re.search(r'(\d{4})[-_]?(\d{2})[-_]?(\d{2})', filename)
    return "".join(m.groups()) if m else None


def _rename_photo(rel_path: str, exif_dttm: datetime | None, country: str) -> str:
    """Build the renamed filename {country}_{date}_{initials}_{original}.JPG,
    matching the R script's naming convention."""
    parts = rel_path.replace("\\", "/").split("/")
    fname = parts[-1]
    dir_parts = parts[:-1]

    day_folder = _find_day_folder(dir_parts)
    observer = _extract_initials(day_folder) if day_folder else ""

    if exif_dttm is not None:
        date_str = exif_dttm.strftime("%Y%m%d")
    else:
        date_str = _date_from_filename(fname) or "UNKNOWNDATE"

    stem = re.sub(r'\..*$', '', fname)  # strip from the first dot onward, like the R script
    return f"{country}_{date_str}_{observer}_{stem}.JPG"


_IMAGE_EXT = (".jpg", ".jpeg")


def process_photo_zip(zip_path: str, country: str, dest_dir: str) -> tuple[list, pd.DataFrame]:
    """
    Walk every JPEG in the uploaded ZIP (any subfolder depth), read its EXIF
    datetime, rename it per _rename_photo(), and write the renamed copy to
    dest_dir (one image at a time — the ZIP is never fully loaded in memory).

    Returns (records, rename_log) where records is a list of
    {"new_filename", "path", "exif_dttm", "orig_relpath"} dicts.
    """
    records = []
    log_rows = []

    with zipfile.ZipFile(zip_path) as zf:
        members = [
            n for n in zf.namelist()
            if not n.endswith("/")
            and not os.path.basename(n).startswith(".")
            and "__MACOSX" not in n
            and n.lower().endswith(_IMAGE_EXT)
        ]

        progress = st.progress(0, text="Reading photo EXIF data…") if members else None
        for i, name in enumerate(members):
            img_bytes = zf.read(name)  # one photo at a time, not the whole zip
            exif_dttm = extract_exif_datetime(io.BytesIO(img_bytes))
            new_filename = _rename_photo(name, exif_dttm, country)

            out_path = os.path.join(dest_dir, new_filename)
            with open(out_path, "wb") as out_f:
                out_f.write(img_bytes)

            records.append({
                "new_filename": new_filename,
                "path": out_path,
                "exif_dttm": exif_dttm,
                "orig_relpath": name,
            })
            log_rows.append({
                "Original path": name,
                "Renamed to": new_filename,
                "EXIF datetime": str(exif_dttm) if exif_dttm else "— none —",
            })
            if progress is not None:
                progress.progress((i + 1) / len(members), text=f"Processing: {os.path.basename(name)}")

        if progress is not None:
            progress.empty()

    return records, pd.DataFrame(log_rows)


def match_renamed_photos(smrt_dttms: pd.Series, photo_records: list, minute_buffer: int) -> tuple[pd.DataFrame, set]:
    """
    For each SMART record datetime, find renamed photos whose EXIF datetime
    falls within minute_buffer minutes. Returns (media_df, matched_filenames).
    """
    photo_info = [(r["new_filename"], r["exif_dttm"]) for r in photo_records]

    buf = timedelta(minutes=minute_buffer)
    rows = []
    matched_filenames = set()
    for smrt_dttm in smrt_dttms:
        if pd.isna(smrt_dttm):
            rows.append([])
            continue
        matched = [
            name for name, img_dttm in photo_info
            if img_dttm is not None and abs(smrt_dttm - img_dttm) <= buf
        ]
        rows.append(matched)
        matched_filenames.update(matched)

    max_imgs = max((len(r) for r in rows), default=0)
    if max_imgs == 0:
        return pd.DataFrame(index=smrt_dttms.index), matched_filenames

    cols = {f"Encounter.mediaAsset{i}": [] for i in range(max_imgs)}
    for matched in rows:
        for i in range(max_imgs):
            cols[f"Encounter.mediaAsset{i}"].append(matched[i] if i < len(matched) else "")

    return pd.DataFrame(cols, index=smrt_dttms.index), matched_filenames


def to_xlsx_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Wildbook")
    return buf.getvalue()


def build_download_zip(photo_records: list, matched_filenames: set, gs_data: pd.DataFrame) -> bytes:
    """Package the matched/renamed photos + Wildbook Excel into one ZIP."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for rec in photo_records:
            if rec["new_filename"] in matched_filenames:
                zf.write(rec["path"], arcname=f"images/{rec['new_filename']}")
        zf.writestr("wildbook_bulkimport.xlsx", to_xlsx_bytes(gs_data))
    return buf.getvalue()


def build_wildbook(smrt: pd.DataFrame, settings: dict, photo_records: list, minute_buffer: int,
                    photo_col: str | None = None) -> tuple[pd.DataFrame, dict, set]:
    """Transform SMART dataframe into GiraffeSpotter Wildbook bulk-upload format."""
    country  = settings["country"]
    location = settings["locationID"]
    org      = settings["organization"]
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
    ]
    for col in count_cols:
        smrt[col] = coerce_count(smrt[col]) if col in smrt.columns else 0

    # Calves — the SMART export (per the reference R script) carries a single
    # "Number of calves" column; only fall back to summing sex-split columns
    # if that column isn't present.
    if "Number of calves" in smrt.columns:
        smrt["_num_calves"] = coerce_count(smrt["Number of calves"])
        diagnostics["calf_col_used"] = "Number of calves"
    else:
        for col in ["Number of female calves", "Number of male calves", "Number of unknown calves"]:
            smrt[col] = coerce_count(smrt[col]) if col in smrt.columns else 0
        smrt["_num_calves"] = (
            smrt["Number of female calves"]
            + smrt["Number of male calves"]
            + smrt["Number of unknown calves"]
        )
        diagnostics["calf_col_used"] = "Number of female/male/unknown calves (summed — 'Number of calves' not found)"

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

    def _survey_id(dttm):
        return f"{country}_{dttm.strftime('%Y%m')}" if pd.notna(dttm) else f"{country}_UNKNOWN"

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
        "Survey.vessel":             "",
        "Survey.id":                 dttm.apply(_survey_id),
        "Occurrence.occurrenceID":   dttm.apply(_oid),
        "Encounter.otherCatalogNumbers": "",
        "Encounter.decimalLongitude": smrt.get("X", smrt.get("Longitude", pd.Series([""] * len(smrt)))),
        "Encounter.decimalLatitude":  smrt.get("Y", smrt.get("Latitude",  pd.Series([""] * len(smrt)))),
        "Encounter.locationID":      location,
        "Encounter.verbatimLocality": vb_locality,
        "Encounter.depth":           "",
        "Encounter.year":            dttm.apply(lambda d: d.year   if pd.notna(d) else ""),
        "Encounter.month":           dttm.apply(lambda d: d.month  if pd.notna(d) else ""),
        "Encounter.day":             dttm.apply(lambda d: d.day    if pd.notna(d) else ""),
        "Encounter.hour":            dttm.apply(lambda d: d.hour   if pd.notna(d) else ""),
        "Encounter.minutes":         dttm.apply(lambda d: d.minute if pd.notna(d) else ""),
        "Encounter.submitterOrganization": org,
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
        "SatelliteTag.serialNumber": "",
        "TissueSample.sampleID":    "",
        "MicrosatelliteMarkersAnalysis.analysisID": "",
        "SexAnalysis.processingLabTaskID": "",
        "SexAnalysis.sex":           "",
        "version GS_20200813":       "",
    })

    # ── Media assets ─────────────────────────────────────────────────────────
    media_df = pd.DataFrame(index=smrt.index)
    matched_filenames = set()

    diagnostics["photo_cols_found"] = photo_col if photo_col else None

    if photo_records:
        # Primary: real photos uploaded — match by EXIF datetime.
        media_df, matched_filenames = match_renamed_photos(smrt["_dttm"], photo_records, minute_buffer)
        diagnostics["images_matched"] = (media_df != "").any(axis=1).sum() if not media_df.empty else 0
        diagnostics["media_source"] = "photo ZIP (EXIF match)"
    elif photo_col and photo_col in smrt.columns:
        # Fallback: fabricate filenames from a "photo numbers on camera" column
        # when no photo ZIP was uploaded.
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
        diagnostics["media_source"] = "photo numbers column (fallback — no photo ZIP uploaded)"
    else:
        diagnostics["images_matched"] = None
        diagnostics["media_source"] = None

    if not media_df.empty:
        gs = pd.concat([gs, media_df], axis=1)

    # ── Clean nan strings ────────────────────────────────────────────────────
    for col in gs.select_dtypes(include="object").columns:
        gs[col] = gs[col].apply(lambda v: "" if pd.isna(v) or str(v).strip().lower() == "nan" else v)

    # ── Expand rows by individual count ─────────────────────────────────────
    individual_count = gs["Occurrence.groupSize"].clip(lower=1).fillna(1).astype(int)
    gs = gs.loc[gs.index.repeat(individual_count)].reset_index(drop=True)

    return gs, diagnostics, matched_filenames


# ─── Main UI ──────────────────────────────────────────────────────────────────

def main():

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

    st.caption(
        "Upload a ZIP of your survey photos — subfolders per day are fine "
        "(and per observer/age-sex-code folder inside each day, e.g. "
        "`15 July_FOtten/AM1/IMG_0001.JPG`); any depth is walked recursively. "
        "**Keep the ZIP under ~40 MB** — large uploads (hundreds of MB) are "
        "unreliable here, the same memory-limited shared process as the "
        "ER2WB converter."
    )
    photo_zip = st.file_uploader("Upload photo ZIP", type=["zip"])

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
            "Photo column not auto-detected — select manually if present "
            "(used only as a fallback when no photo ZIP is uploaded)",
            options=["— none —"] + list(smrt.columns),
        )
        photo_col_choice = None if photo_col_choice == "— none —" else photo_col_choice

    if photo_zip:
        st.caption(f"Photo ZIP uploaded: {photo_zip.name}")

    # ── Process ───────────────────────────────────────────────────────────────
    if st.button("Convert to Wildbook format", type="primary"):
        photo_records = []
        rename_log = pd.DataFrame()
        zip_tmp_path = None
        images_tmp_dir = None

        try:
            if photo_zip is not None:
                with st.spinner("Reading photo ZIP…"):
                    fd, zip_tmp_path = tempfile.mkstemp(suffix=".zip", prefix="smart2wb_upload_")
                    with os.fdopen(fd, "wb") as out_f:
                        shutil.copyfileobj(photo_zip, out_f)

                    images_tmp_dir = tempfile.mkdtemp(prefix="smart2wb_images_")
                    photo_records, rename_log = process_photo_zip(
                        zip_tmp_path, settings["country"], images_tmp_dir)

                if not photo_records:
                    st.warning("No JPEGs found inside that ZIP — check it isn't empty or nested oddly.")

            with st.spinner("Converting…"):
                try:
                    gs, diag, matched_filenames = build_wildbook(
                        smrt, settings, photo_records, int(minute_buffer), photo_col=photo_col_choice)
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

            st.caption(f"Calf count source: {diag['calf_col_used']}")

            if diag["images_matched"] is not None:
                st.info(f"{diag['images_matched']} of {len(smrt)} SMART records matched at least one photo "
                        f"({diag['media_source']}).")
            elif not photo_zip and not photo_col_choice:
                st.warning("No photo column detected in CSV and no photo ZIP uploaded — mediaAsset columns will be absent.")

            if not rename_log.empty:
                with st.expander(f"🔍 Photo rename log ({len(rename_log)} photos)"):
                    st.dataframe(rename_log, use_container_width=True, hide_index=True)
                    st.caption("Observer initials are pulled from the day-folder name above any "
                               "AM1/AF2/SAM/'2 together'-style folder. '— none —' EXIF datetime "
                               "means that photo can't be matched to a SMART row.")

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

            if photo_records:
                zip_filename = f"ZCP_{year_str}_bulkimport.zip"
                st.download_button(
                    label=f"⬇️  Download {zip_filename} (Excel + matched photos)",
                    data=build_download_zip(photo_records, matched_filenames, gs),
                    file_name=zip_filename,
                    mime="application/zip",
                )
            else:
                filename = f"ZCP_{year_str}_bulkimport.xlsx"
                st.download_button(
                    label=f"⬇️  Download {filename}",
                    data=to_xlsx_bytes(gs),
                    file_name=filename,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

        finally:
            if zip_tmp_path and os.path.exists(zip_tmp_path):
                try:
                    os.remove(zip_tmp_path)
                except OSError:
                    pass
            if images_tmp_dir and os.path.exists(images_tmp_dir):
                shutil.rmtree(images_tmp_dir, ignore_errors=True)
            gc.collect()
