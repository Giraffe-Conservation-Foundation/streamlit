"""
📖 Create ID Book
Wildbook ID Generator Tool
"""

import streamlit as st
import sys
import os
from pathlib import Path


# Add shared utilities for logo
current_dir = Path(__file__).parent.parent
sys.path.append(str(current_dir))
from shared.utils import add_sidebar_logo

# Add logo to sidebar at the top
add_sidebar_logo()

# Add the wildbook directory to Python path
current_dir = Path(__file__).parent.parent
wildbook_dir = current_dir / "wildbook_id_generator"
sys.path.insert(0, str(wildbook_dir))

st.title("📖 Create an ID Book [beta]")

if wildbook_dir.exists() and (wildbook_dir / "app.py").exists():
    # Store original working directory
    original_dir = os.getcwd()
    
    try:
        # Change to the app directory
        os.chdir(wildbook_dir)
        
        # Load environment variables if available
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass  # dotenv not required for this tool
        
        # Read and execute the app code
        with open(wildbook_dir / "app.py", "r", encoding="utf-8") as f:
            app_code = f.read()
            
        # Remove any set_page_config calls since this is a page
        import re
        cleaned_code = re.sub(
            r'st\.set_page_config\s*\([^)]*\)',
            '',
            app_code,
            flags=re.MULTILINE | re.DOTALL
        )
        
        exec(cleaned_code)
        
    finally:
        # Always restore original directory
        os.chdir(original_dir)
else:
    st.error("❌ Wildbook ID generator not found!")
    st.info("Please ensure the wildbook_id_generator/app.py file exists.")