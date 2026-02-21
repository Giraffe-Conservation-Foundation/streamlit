"""
Publications Dashboard Page
Display GCF publications from Zotero library
"""

import streamlit as st
import sys
from pathlib import Path
import importlib.util

# Add shared utilities for logo
current_dir = Path(__file__).parent.parent
sys.path.append(str(current_dir))
from shared.utils import add_sidebar_logo

# Add logo to sidebar at the top
add_sidebar_logo()

# Add the publications directory to Python path
publications_dir = current_dir / "publications"
app_file = publications_dir / "app.py"

# Import the specific app.py file from publications
spec = importlib.util.spec_from_file_location("publications_app", app_file)
publications_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publications_app)

# Get the main function
main = publications_app.main

# Run the Publications Dashboard
if __name__ == "__main__":
    main()
