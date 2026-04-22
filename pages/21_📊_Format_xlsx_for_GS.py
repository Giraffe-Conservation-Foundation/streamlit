"""
Format xlsx for GiraffeSpotter — upload a survey spreadsheet and map columns
to the GiraffeSpotter bulk-import format. No EarthRanger login required.
"""

import importlib.util
import sys
from pathlib import Path

import streamlit as st

current_dir = Path(__file__).parent.parent
sys.path.append(str(current_dir))
from shared.utils import add_sidebar_logo

add_sidebar_logo()

app_file = current_dir / "xlsx_to_gs_dashboard" / "app.py"
if not app_file.exists():
    st.error(f"App module not found at: {app_file}")
    st.stop()

spec   = importlib.util.spec_from_file_location("xlsx_to_gs_app", app_file)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

module.main()
