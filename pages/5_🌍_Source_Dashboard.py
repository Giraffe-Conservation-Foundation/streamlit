"""
Source Dashboard Page
Monitor and analyze EarthRanger tracking device sources
"""

import streamlit as st
import sys
from pathlib import Path

# Add the source_dashboard directory to Python path
current_dir = Path(__file__).parent.parent
source_dir = current_dir / "source_dashboard"
sys.path.insert(0, str(source_dir))

# Import the main application
from app import main

# Run the Source dashboard
if __name__ == "__main__":
    main()
