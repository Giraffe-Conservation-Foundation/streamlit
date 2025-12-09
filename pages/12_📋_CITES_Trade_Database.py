import streamlit as st
import importlib.util
import os

# Page Configuration
st.set_page_config(
    page_title="CITES Trade Database", 
    page_icon="📋", 
    layout="wide"
)

# Get the path to the CITES dashboard app
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
app_file = os.path.join(parent_dir, "cites_dashboard", "app.py")

# Import and run the CITES dashboard
spec = importlib.util.spec_from_file_location("cites_app", app_file)
cites_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cites_app)

# Get the main function
main = cites_app.main

# Run the dashboard
if __name__ == "__main__":
    main()
