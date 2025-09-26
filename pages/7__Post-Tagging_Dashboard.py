"""
Post-Tagging Dashboard Page
Monitor giraffe locations during first 2 days after deployment/tagging
"""

import streamlit as st
import sys
from pathlib import Path
import importlib.util

# Add the tagging_dashboard directory to Python path
current_dir = Path(__file__).parent.parent
tagging_dir = current_dir / "tagging_dashboard"
app_file = tagging_dir / "app.py"

# Import the specific app.py file from tagging_dashboard
spec = importlib.util.spec_from_file_location("tagging_app", app_file)
tagging_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tagging_app)

# Get the main function
main = tagging_app.main

# Run the Post-Tagging dashboard
if __name__ == "__main__":
    main()