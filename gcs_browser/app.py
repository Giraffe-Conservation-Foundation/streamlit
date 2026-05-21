"""
☁️ Google Cloud Buckets
Browse all GCS buckets and their top-level folders in the gcf-camera-traps project.
Uses the existing gcp_service_account secret — no additional credentials required.
"""

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

# ── Deep-dive config: bucket → top-level folder → sub-folders to expand ──────
# For these buckets, specific first-level folders will show their sub-folders.
DEEP_FOLDERS = {
    "gcf_nam_ehgr": {
        "survey":      ["survey_vehicle", "survey_aerial"],
        "camera_trap": ["camera_fence", "camera_water", "camera_grid"],
    }
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
                for sf in sub_folders_found:
                    # Strip the parent prefix and trailing slash for clean display
                    display = sf.removeprefix(sub_prefix).rstrip("/")
                    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;📁 `{display}`")
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
    deep_config = DEEP_FOLDERS.get(bucket.name, {})

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

                    if folder_name in deep_config:
                        # Render with nested sub-folder expansion
                        render_deep_folder(
                            client, bucket.name,
                            folder_name, deep_config[folder_name]
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
    "File counts and sizes are not fetched to keep this view fast."
)
