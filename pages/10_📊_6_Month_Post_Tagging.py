"""
6-Month Post-Tagging Dashboard Page
Monitor tagged giraffe subjects 6 months after deployment start date
"""

import streamlit as st
import sys
from pathlib import Path

# Add the post_tagging_dashboard directory to Python path
current_dir = Path(__file__).parent.parent
sys.path.insert(0, str(current_dir / "post_tagging_dashboard"))

# Simple import approach for Streamlit Cloud compatibility
try:
    import app as post_tagging_app
    # Run the 6-Month Post-Tagging dashboard
    post_tagging_app.main()
except ImportError as e:
    st.error(f"Error importing post-tagging dashboard: {e}")
except Exception as e:
    st.error(f"Error running post-tagging dashboard: {e}")