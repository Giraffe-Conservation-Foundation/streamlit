"""
Tagging Dashboard Page
Monitor newly tagged giraffes by month and country
"""

import streamlit as st
import sys
from pathlib import Path

# Add the tagging_dashboard directory to Python path
current_dir = Path(__file__).parent.parent
tagging_dir = current_dir / "tagging_dashboard"
sys.path.insert(0, str(tagging_dir))

# Import the main application
from app import main

# Run the Tagging dashboard
if __name__ == "__main__":
    main()
