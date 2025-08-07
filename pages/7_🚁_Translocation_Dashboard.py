"""
Translocation Dashboard Page
Monitor and analyze giraffe translocation events from EarthRanger
"""

import streamlit as st
import sys
from pathlib import Path

# Add the translocation_dashboard directory to Python path
current_dir = Path(__file__).parent.parent
translocation_dir = current_dir / "translocation_dashboard"
sys.path.insert(0, str(translocation_dir))

# Import the main application
from app import main

# Run the Translocation dashboard
if __name__ == "__main__":
    main()
