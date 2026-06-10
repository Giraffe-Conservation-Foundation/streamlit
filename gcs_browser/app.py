"""
☁️ Google Cloud Buckets
Browse all GCS buckets and their top-level folders in the gcf-camera-traps project.
Uses the existing gcp_service_account secret — no additional credentials required.
"""

import re
import sys
from pathlib import Path

import streamlit as st
from google.cloud import storage
from google.oauth2 import service_account

# Shared auth helpers
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from shared.auth import require_gcf_login  # noqa: E402

# ── Page header ───────────────────────────────────────────────────────────────
st.title("☁️ Google Cloud Buckets")
st.caption("Project: **gcf-camera-traps** — top-level folder listing only")
st.markdown("---")

# ── Auth gate ─────────────────────────────────────────────────────────────────
require_gcf_login("Google Cloud Buckets")

# ── Deep-dive config: folder name → sub-folders to expand ────────────────────
# Any bucket containing these top-level folder names will show their sub-folders.
DEEP_FOLDERS = {
    "survey":      ["survey_vehicle", "survey_aerial"],
    "camera_trap": ["camera_fence", "camera_water", "camera_grid"],
}

# ── Auth ──────────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def _get_client():
    creds = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    return storage.Client(project="gcf-camera-traps", credentials=creds)


# ── Helpers ───────────────────────────────────────────────────────────────────
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp")
_DATE_RE = re.compile(r"_(20\d{6})_")  # YYYYMMDD from standardised filenames


def _parse_date(blob_name: str) -> str | None:
    """Extract YYYYMMDD from a standardised filename; None if absent."""
    m = _DATE_RE.search(Path(blob_name).name)
    return m.group(1) if m else None


def _fmt_date(yyyymmdd: str) -> str:
    return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:]}"


@st.cache_data(ttl=600, show_spinner=False)
def first_last_images(bucket_name: str, prefix: str) -> tuple[str, str] | None:
    """
    First and last image names (recursive, all sub-folders) under `prefix`,
    ordered by the YYYYMMDD date in the filename where present,
    falling back to lexicographic order. Returns None if no images.
    """
    client = _get_client()
    blobs = client.list_blobs(bucket_name, prefix=prefix, fields="items(name),nextPageToken")
    names = [b.name for b in blobs if b.name.lower().endswith(IMAGE_EXTS)]
    if not names:
        return None
    # Sort by (parsed date or fallback), then name — keeps order date-correct
    names.sort(key=lambda n: (_parse_date(n) or "99999999", n))
    return names[0], names[-1]


def _date_range_line(bucket_name: str, prefix: str, display: str) -> str:
    """Markdown line for a leaf folder with first → last image and date range."""
    result = first_last_images(bucket_name, prefix)
    indent = "&nbsp;" * 8
    if result is None:
        return f"{indent}📁 `{display}` — *no images found*"
    first, last = result
    d1, d2 = _parse_date(first), _parse_date(last)
    dates = f" &nbsp;**{_fmt_date(d1)} → {_fmt_date(d2)}**" if d1 and d2 else ""
    return (
        f"{indent}📁 `{display}`{dates}<br>"
        f"{indent}&nbsp;&nbsp;&nbsp;&nbsp;`{Path(first).name}` → `{Path(last).name}`"
    )


def list_prefixes(client: storage.Client, bucket_name: str, prefix: str = "") -> list[str]:
    """Return sorted sub-folder prefixes directly under `prefix`."""
    iterator = client.list_blobs(bucket_name, prefix=prefix or None, delimiter="/", max_results=2000)
    _ = list(iterator)  # consume to populate .prefixes
    return sorted(iterator.prefixes)


def render_deep_folder(client, bucket_name, top_folder, sub_folders):
    """
    Render a top-level folder with named sub-folders expanded,
    each showing their own sub-folder names.
    e.g. survey/ → survey_vehicle/ → [2023/, 2024/, ...]
    """
    top_prefix = f"{top_folder}/"
    st.markdown(f"📁 **{top_folder}/**")

    for sub in sub_folders:
        sub_prefix = f"{top_folder}/{sub}/"
        sub_folders_found = list_prefixes(client, bucket_name, sub_prefix)

        with st.expander(f"&nbsp;&nbsp;&nbsp;&nbsp;📂 {sub}/", expanded=False):
            if sub_folders_found:
                with st.spinner("Checking image date ranges…"):
                    for sf in sub_folders_found:
                        # Strip the parent prefix and trailing slash for clean display
                        display = sf.removeprefix(sub_prefix).rstrip("/")
                        st.markdown(
                            _date_range_line(bucket_name, sf, display),
                            unsafe_allow_html=True,
                        )
            else:
                st.caption("No sub-folders found.")


# ── Main ──────────────────────────────────────────────────────────────────────
try:
    client = _get_client()
except Exception as e:
    st.error(f"Could not initialise GCS client: {e}")
    st.stop()

with st.spinner("Fetching bucket list…"):
    try:
        buckets = sorted(client.list_buckets(), key=lambda b: b.name)
    except Exception as e:
        st.error(
            f"**Could not list buckets.** "
            f"The service account may need `Storage Viewer` at the project level.\n\n`{e}`"
        )
        st.stop()

if not buckets:
    st.info("No buckets found in project gcf-camera-traps.")
    st.stop()

st.markdown(f"**{len(buckets)} bucket{'s' if len(buckets) != 1 else ''} found**")
st.markdown("")

# ── Per-bucket expanders ──────────────────────────────────────────────────────
for bucket in buckets:
    with st.expander(f"🪣  {bucket.name}", expanded=False):
        col1, col2 = st.columns([3, 1])

        with col1:
            try:
                top_folders = list_prefixes(client, bucket.name)
            except Exception as e:
                st.warning(f"Could not list folders: {e}")
                top_folders = []

            if top_folders:
                st.markdown("**Top-level folders**")
                for folder_prefix in top_folders:
                    folder_name = folder_prefix.rstrip("/")

                    if folder_name in DEEP_FOLDERS:
                        # Render with nested sub-folder expansion
                        render_deep_folder(
                            client, bucket.name,
                            folder_name, DEEP_FOLDERS[folder_name]
                        )
                    else:
                        st.markdown(f"&nbsp;&nbsp;&nbsp;📁 `{folder_name}`")
            else:
                st.caption("No sub-folders — files may be at the root level.")

        with col2:
            try:
                bucket.reload()
                location = bucket.location or "—"
                storage_class = bucket.storage_class or "—"
            except Exception:
                location = "—"
                storage_class = "—"

            st.markdown("**Bucket info**")
            st.markdown(f"📍 Location: `{location}`")
            st.markdown(f"🗂️ Class: `{storage_class}`")

st.markdown("---")
st.caption(
    "Folder listing uses GCS delimiter `/`. "
    "Date ranges are parsed from the YYYYMMDD in standardised filenames "
    "(first → last image across all sub-folders) and cached for 10 minutes."
)
