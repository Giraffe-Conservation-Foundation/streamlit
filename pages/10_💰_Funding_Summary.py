"""
Funding Summary Page
Secure financial donation analysis and reporting
"""

import streamlit as st
import sys
from pathlib import Path
import importlib.util

# Add the funding_summary directory to Python path
current_dir = Path(__file__).parent.parent
funding_dir = current_dir / "funding_summary"
app_file = funding_dir / "app.py"

# Import the specific app.py file from funding_summary
spec = importlib.util.spec_from_file_location("funding_app", app_file)
funding_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(funding_app)

# Get the main function
main = funding_app.main

# Run the Funding Summary dashboard
if __name__ == "__main__":
    main()
