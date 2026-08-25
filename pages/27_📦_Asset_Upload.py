import streamlit as st
import importlib.util
import os

# Page Configuration set by twiga_tools.py (st.navigation entry point)
# st.set_page_config(
#     page_title="Asset Upload - GCF Asset Register",
#     page_icon="📦",
#     layout="wide"
# )

# Get the path to the Asset Upload dashboard app
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
app_file = os.path.join(parent_dir, "asset_upload_dashboard", "app.py")

# Import and run the Asset Upload dashboard
spec = importlib.util.spec_from_file_location("asset_upload_app", app_file)
asset_upload_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(asset_upload_app)

# Get the main function
main = asset_upload_app.main

# Run the dashboard
if __name__ == "__main__":
    main()
