"""
6-Month Post-Tagging Dashboard Page
Monitor tagged giraffe subjects 6 months after deployment start date
"""

import streamlit as st
import sys
from pathlib import Path
import importlib.util

# Add the post_tagging_dashboard directory to Python path
current_dir = Path(__file__).parent.parent
post_tagging_dir = current_dir / "post_tagging_dashboard"
app_file = post_tagging_dir / "app.py"

# Import the specific app.py file from post_tagging_dashboard
spec = importlib.util.spec_from_file_location("post_tagging_app", app_file)
post_tagging_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(post_tagging_app)

# Get the main function
main = post_tagging_app.main

# Run the 6-Month Post-Tagging dashboard
if __name__ == "__main__":
    main()