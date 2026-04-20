"""
Survey data backup — Google Cloud Storage upload for post-ER2WB survey packages.

Expects ZIPs produced by the ER2WB Converter (already renamed, plus any XLSX
form). Files are uploaded as-is to:
    gs://gcf_<country>_<site>/survey/<survey_type>/YYYYMM/<filename>

YYYYMM is parsed from the ER2WB filename pattern
(e.g. NAM_EHGR_20250101_CM_0001.JPG -> 202501). Files that don't match the
pattern (the XLSX form, READMEs, etc.) fall back to the year/month the user
selects on the page.
"""

import io
import json
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

# Shared helpers (Google OIDC login + GCS client). Resolve project root so the
# module is importable whether this file is executed directly or via exec().
_streamlit_root = Path(__file__).resolve().parent.parent
if str(_streamlit_root) not in sys.path:
    sys.path.insert(0, str(_streamlit_root))

from shared.auth import (  # noqa: E402
    require_gcf_login,
    get_storage_client,
    load_buckets,
    extract_countries_sites_from_buckets,
    resolve_bucket_name,
)


# ─── Constants ────────────────────────────────────────────────────────────────
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".tif", ".tiff")
RETAINED_NON_IMAGE_EXTS = (".xlsx", ".xls", ".csv", ".txt", ".pdf")
# ER2WB-produced image names: COUNTRY_SITE_YYYYMMDD_XX_####.ext
ER2WB_PATTERN = re.compile(r"^[A-Z]{3,4}_[A-Z]{3,4}_(\d{8})_", re.IGNORECASE)
MAX_ZIP_MB = 1024  # 1 GB — matches ER2WB output ceiling and server.maxUploadSize


def month_folder_from_filename(name: str) -> str | None:
    """Return YYYYMM if the filename matches the ER2WB pattern, else None."""
    m = ER2WB_PATTERN.match(Path(name).name)
    return m.group(1)[:6] if m else None


def er2wb_reminder() -> None:
    st.info(
        "📌 **This page expects a ZIP produced by the ER2WB Converter.**\n\n"
        "Run ER2WB first — it renames images to the GCF standard and packages "
        "them with the bulk-import XLSX. Both the renamed images and any XLSX "
        "form inside the ZIP will be uploaded here together."
    )


# ─── Main flow ────────────────────────────────────────────────────────────────
def main() -> None:
    require_gcf_login(page_label="Survey data backup")

    st.title("🚗 Survey data backup")
    st.caption(f"Signed in as **{st.user.email}**")

    er2wb_reminder()

    client = get_storage_client()
    bucket_names = load_buckets(client)
    countries_sites = extract_countries_sites_from_buckets(bucket_names)
    if not countries_sites:
        st.error("No `gcf_<country>_<site>` buckets are accessible to the service account.")
        st.stop()

    # ── Step 1: configuration ────────────────────────────────────────────────
    st.subheader("1. Survey configuration")
    c1, c2, c3 = st.columns(3)
    country = c1.selectbox("Country", list(countries_sites.keys()))
    site = c2.selectbox("Site", countries_sites[country])
    survey_type = c3.selectbox(
        "Survey type",
        ["survey_vehicle", "survey_aerial"],
        format_func=lambda x: x.replace("survey_", "").title() + " survey",
    )

    st.caption(
        "Fallback year/month is used only for files inside the ZIP that don't "
        "match the ER2WB image naming pattern (e.g. the XLSX form)."
    )
    c4, c5 = st.columns(2)
    now = datetime.now()
    fallback_year = c4.selectbox(
        "Fallback year",
        list(range(now.year - 10, now.year + 1)),
        index=10,
    )
    fallback_month = c5.selectbox(
        "Fallback month",
        list(range(1, 13)),
        index=now.month - 1,
        format_func=lambda m: f"{m:02d} — {['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][m-1]}",
    )
    fallback_folder = f"{fallback_year}{fallback_month:02d}"

    bucket_name = resolve_bucket_name(country, site, bucket_names)
    if not bucket_name:
        st.error(
            f"No bucket matching `gcf_{country.lower()}_{site.lower()}` is "
            f"accessible to the service account."
        )
        st.stop()
    st.success(f"Target bucket: `{bucket_name}`")

    # ── Step 2: upload ZIP ───────────────────────────────────────────────────
    st.subheader("2. Upload ER2WB ZIP")
    zip_file = st.file_uploader(
        "ER2WB ZIP (images + optional XLSX form)",
        type=["zip"],
        accept_multiple_files=False,
    )
    if not zip_file:
        st.stop()

    size_mb = len(zip_file.getvalue()) / (1024 * 1024)
    if size_mb > MAX_ZIP_MB:
        st.error(f"ZIP is {size_mb:.1f} MB — max {MAX_ZIP_MB / 1024:.0f} GB. Split and upload in batches.")
        st.stop()
    st.caption(f"ZIP size: {size_mb:.1f} MB")

    # ── Step 3: scan ZIP contents ────────────────────────────────────────────
    st.subheader("3. Review ZIP contents")
    files: list[dict] = []
    unmatched_images = 0
    try:
        with zipfile.ZipFile(io.BytesIO(zip_file.getvalue())) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                fname = Path(info.filename).name
                if not fname or fname.startswith(".") or fname.startswith("__MACOSX"):
                    continue
                lower = fname.lower()
                if lower.endswith(IMAGE_EXTS):
                    kind = "image"
                elif lower.endswith(RETAINED_NON_IMAGE_EXTS):
                    kind = "form"
                else:
                    continue  # skip unsupported extensions silently

                parsed = month_folder_from_filename(fname)
                folder = parsed or fallback_folder
                if kind == "image" and parsed is None:
                    unmatched_images += 1

                data = zf.read(info.filename)
                files.append({
                    "name": fname,
                    "data": data,
                    "size_mb": len(data) / (1024 * 1024),
                    "target_folder": folder,
                    "kind": kind,
                })
    except zipfile.BadZipFile:
        st.error("Not a valid ZIP file.")
        st.stop()

    if not files:
        st.error("No images or forms found in ZIP.")
        st.stop()

    images = [f for f in files if f["kind"] == "image"]
    forms = [f for f in files if f["kind"] == "form"]
    by_folder: dict[str, list[dict]] = {}
    for f in files:
        by_folder.setdefault(f["target_folder"], []).append(f)

    c1, c2, c3 = st.columns(3)
    c1.metric("Images", len(images))
    c2.metric("Forms (XLSX/CSV/PDF)", len(forms))
    c3.metric("Target folders", len(by_folder))

    if unmatched_images:
        st.warning(
            f"⚠️ {unmatched_images} image(s) don't match the ER2WB naming pattern. "
            f"They will be uploaded to the fallback folder `{fallback_folder}/`."
        )

    with st.expander("Preview file list", expanded=False):
        preview_df = pd.DataFrame([
            {
                "File": f["name"],
                "Kind": f["kind"],
                "Target folder": f["target_folder"],
                "Size (MB)": f"{f['size_mb']:.2f}",
            }
            for f in files
        ])
        st.dataframe(preview_df, use_container_width=True)

    st.caption(
        f"Destination paths will be: "
        f"`gs://{bucket_name}/survey/{survey_type}/YYYYMM/<filename>`"
    )

    # ── Step 4: upload ───────────────────────────────────────────────────────
    st.subheader("4. Upload to Cloud Storage")
    st.warning("🛡️ Existing files will be skipped — no overwrites.")

    if not st.button("🚀 Start upload", type="primary"):
        st.stop()

    bucket = client.bucket(bucket_name)
    progress = st.progress(0.0)
    status = st.empty()
    uploaded: list[str] = []
    skipped: list[str] = []
    failed: list[tuple[str, str]] = []

    total = len(files)
    for i, f in enumerate(files, start=1):
        blob_path = f"survey/{survey_type}/{f['target_folder']}/{f['name']}"
        try:
            blob = bucket.blob(blob_path)
            if blob.exists():
                skipped.append(blob_path)
            else:
                blob.upload_from_string(f["data"])
                blob.metadata = {
                    "uploaded_by": st.user.email,
                    "country": country,
                    "site": site,
                    "survey_type": survey_type,
                    "source": "survey_data_backup_page",
                    "uploaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                }
                blob.patch()
                uploaded.append(blob_path)
        except Exception as e:
            failed.append((blob_path, str(e)))
        progress.progress(i / total)
        status.text(f"{i}/{total} — {f['name']}")

    # Upload manifest for audit trail
    if uploaded:
        manifest = {
            "uploaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "uploaded_by": st.user.email,
            "country": country,
            "site": site,
            "survey_type": survey_type,
            "total_files": total,
            "uploaded": uploaded,
            "skipped": skipped,
            "failed": [{"path": p, "error": e} for p, e in failed],
        }
        manifest_path = (
            f"survey/{survey_type}/_manifests/"
            f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_"
            f"{st.user.email.split('@')[0]}.json"
        )
        try:
            bucket.blob(manifest_path).upload_from_string(
                json.dumps(manifest, indent=2),
                content_type="application/json",
            )
        except Exception as e:
            st.warning(f"Upload manifest could not be saved: {e}")

    c1, c2, c3 = st.columns(3)
    c1.metric("Uploaded", len(uploaded))
    c2.metric("Skipped (existing)", len(skipped))
    c3.metric("Failed", len(failed))

    if failed:
        with st.expander("Errors", expanded=True):
            for p, e in failed:
                st.error(f"**{p}** — {e}")

    if uploaded and not failed:
        st.success(
            f"🎉 Uploaded {len(uploaded)} file(s) to "
            f"gs://{bucket_name}/survey/{survey_type}/"
        )

    if st.button("🔄 Upload another ZIP"):
        for k in ("available_buckets",):
            st.session_state.pop(k, None)
        st.rerun()


main()
