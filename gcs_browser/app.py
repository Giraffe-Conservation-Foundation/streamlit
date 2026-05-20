"""
☁️ Google Cloud Buckets
Browse all GCS buckets and their top-level folders in the gcf-camera-traps project.
Uses the existing gcp_service_account secret — no additional credentials required.
"""

import streamlit as st
from google.cloud import storage
from google.oauth2 import service_account

# ── Page header ───────────────────────────────────────────────────────────────
st.title("☁️ Google Cloud Buckets")
st.caption("Project: **gcf-camera-traps** — top-level folder listing only")
st.markdown("---")

# ── Auth ──────────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def _get_client():
    creds = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    return storage.Client(project="gcf-camera-traps", credentials=creds)


# ── Helpers ───────────────────────────────────────────────────────────────────
def list_top_level_folders(client: storage.Client, bucket_name: str) -> list[str]:
    """Return sorted list of top-level prefixes (pseudo-folders) in a bucket."""
    iterator = client.list_blobs(bucket_name, delimiter="/", max_results=1000)
    _ = list(iterator)  # must consume the iterator to populate .prefixes
    return sorted(iterator.prefixes)


def format_size(total_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if total_bytes < 1024:
            return f"{total_bytes:.1f} {unit}"
        total_bytes /= 1024
    return f"{total_bytes:.1f} PB"


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
                folders = list_top_level_folders(client, bucket.name)
            except Exception as e:
                st.warning(f"Could not list folders: {e}")
                folders = []

            if folders:
                st.markdown("**Top-level folders**")
                for folder in folders:
                    # Strip trailing slash for display
                    display = folder.rstrip("/")
                    st.markdown(f"&nbsp;&nbsp;&nbsp;📁 `{display}`")
            else:
                st.caption("No sub-folders — files may be at the root level.")

        with col2:
            # Bucket metadata
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
    "Folder listing uses GCS delimiter `/` — only top-level prefixes are shown. "
    "File counts and sizes are not fetched to keep this view fast."
)
