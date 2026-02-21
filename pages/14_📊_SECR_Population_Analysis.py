"""
SECR Population Analysis Page
Spatially-Explicit Capture-Recapture and Bailey's Triple Catch
Version: 2026-02-18-CACHE-FIX
"""

import streamlit as st
import sys
from pathlib import Path
import importlib.util
import importlib

# Add shared utilities for logo
current_dir = Path(__file__).parent.parent
sys.path.append(str(current_dir))
from shared.utils import add_sidebar_logo

# Add logo to sidebar at the top
add_sidebar_logo()

# Add the secr_analysis directory to Python path
secr_dir = current_dir / "secr_analysis"
app_file = secr_dir / "app.py"

# Force reload if module already exists in sys.modules
module_name = "secr_app_live"
if module_name in sys.modules:
    del sys.modules[module_name]

# Import the specific app.py file from secr_analysis
spec = importlib.util.spec_from_file_location(module_name, app_file)
secr_app = importlib.util.module_from_spec(spec)
sys.modules[module_name] = secr_app
spec.loader.exec_module(secr_app)

# Get the main function
main = secr_app.main

# Run the SECR Dashboard
if __name__ == "__main__":
    main()
