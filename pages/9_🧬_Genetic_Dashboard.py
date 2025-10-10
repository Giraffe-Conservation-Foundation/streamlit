"""  
Genetic Dashboard Page  
Monitor and analyze biological sample events from EarthRanger
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

# Add the genetic_dashboard directory to Python path
genetic_dir = current_dir / "genetic_dashboard"
app_file = genetic_dir / "app.py"

# Import the specific app.py file from genetic_dashboard
spec = importlib.util.spec_from_file_location("genetic_app", app_file)
genetic_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(genetic_app)

# Get the main function
main = genetic_app.main

# Run the Genetic dashboard
if __name__ == "__main__":
    main()