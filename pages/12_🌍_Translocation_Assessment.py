import sys
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

# Page Configuration set by twiga_tools.py (st.navigation entry point)
# st.set_page_config(
#     page_title="Translocation Assessment",
#     page_icon="🌍",
#     layout="wide"
# )

# ── Shared helpers (logo + GCF Google OIDC gate) ─────────────────────────────
_streamlit_root = Path(__file__).resolve().parent.parent
if str(_streamlit_root) not in sys.path:
    sys.path.insert(0, str(_streamlit_root))

from shared.utils import add_sidebar_logo  # noqa: E402
from shared.auth import require_gcf_login  # noqa: E402

add_sidebar_logo()

# Gate behind GCF Google OIDC login (@giraffeconservation.org only)
require_gcf_login(page_label="Translocation Priority Assessment")

st.title("🌍 Giraffe Translocation Priority Assessment")

st.markdown("""
Interactive maps showing translocation priority areas for giraffe conservation based on 
environmental suitability analysis using Google Earth Engine.
""")

st.info("📱 For best experience, use the fullscreen button in the bottom-right of the map viewer.")

# Create tabs for each species
tab1, tab2, tab3, tab4 = st.tabs(["🦒 Masai Giraffe", "🦒 Northern Giraffe", "🦒 Reticulated Giraffe", "🦒 Southern Giraffe"])

with tab1:
    st.subheader("Masai Giraffe Translocation Priority")
    st.markdown("[Open in Google Earth Engine ↗](https://translocation-priority.projects.earthengine.app/view/masai-giraffe-priority)")
    
    components.iframe(
        "https://translocation-priority.projects.earthengine.app/view/masai-giraffe-priority",
        height=800,
        scrolling=True
    )

with tab2:
    st.subheader("Northern Giraffe Translocation Priority")
    st.markdown("[Open in Google Earth Engine ↗](https://translocation-priority.projects.earthengine.app/view/northern-giraffe-priority)")
    
    components.iframe(
        "https://translocation-priority.projects.earthengine.app/view/northern-giraffe-priority",
        height=800,
        scrolling=True
    )

with tab3:
    st.subheader("Reticulated Giraffe Translocation Priority")
    st.markdown("[Open in Google Earth Engine ↗](https://translocation-priority.projects.earthengine.app/view/reticulated-giraffe-priority)")
    
    components.iframe(
        "https://translocation-priority.projects.earthengine.app/view/reticulated-giraffe-priority",
        height=800,
        scrolling=True
    )

with tab4:
    st.subheader("Southern Giraffe Translocation Priority")
    st.markdown("[Open in Google Earth Engine ↗](https://translocation-priority.projects.earthengine.app/view/southern-giraffe-priority)")
    
    components.iframe(
        "https://translocation-priority.projects.earthengine.app/view/southern-giraffe-priority",
        height=800,
        scrolling=True
    )

st.markdown("---")
st.caption("Data source: Google Earth Engine | Giraffe Conservation Foundation")
