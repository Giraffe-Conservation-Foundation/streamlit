"""
ER2WB Converter Page
EarthRanger → GiraffeSpotter bulk import formatter
"""

import importlib.util
import sys
from pathlib import Path

import streamlit as st

# Add shared utilities for logo
current_dir = Path(__file__).parent.parent
sys.path.append(str(current_dir))
from shared.utils import add_sidebar_logo

add_sidebar_logo()

# Load er2wb_dashboard/app.py
app_file = current_dir / "er2wb_dashboard" / "app.py"

if not app_file.exists():
    st.error(f"ER2WB app not found at: {app_file}")
    st.stop()

spec   = importlib.util.spec_from_file_location("er2wb_app", app_file)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

module.main()
