"""
KEEP Survey Dashboard Page
Embeds the KEEP AGOL dashboard
"""

import streamlit as st
import streamlit.components.v1 as components
import sys
from pathlib import Path

current_dir = Path(__file__).parent.parent
sys.path.append(str(current_dir))
from shared.utils import add_sidebar_logo
from shared.auth import require_gcf_login

add_sidebar_logo()
require_gcf_login(page_label="KEEP")

st.title("🦒 KEEP")
st.markdown("---")

components.iframe(
    "https://giraffecf.maps.arcgis.com/apps/dashboards/572591b7353b4c1db3a4e85d200ed2de",
    height=1000,
    scrolling=True,
)
