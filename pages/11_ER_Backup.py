# -*- coding: utf-8 -*-
"""
ER Backup Tool Launcher
This file serves as a launcher for the ER Backup dashboard.
The main app logic is located in the er_backup module.
"""

import sys
import importlib.util
from pathlib import Path

# Get the path to the er_backup module
current_dir = Path(__file__).parent.parent
er_backup_path = current_dir / "er_backup" / "app.py"

# Load and execute the ER Backup app
if er_backup_path.exists():
    spec = importlib.util.spec_from_file_location("er_backup_app", er_backup_path)
    er_backup_module = importlib.util.module_from_spec(spec)
    
    # Add the er_backup directory to sys.path so imports work
    sys.path.insert(0, str(current_dir / "er_backup"))
    
    try:
        spec.loader.exec_module(er_backup_module)
        # Run the main function if it exists
        if hasattr(er_backup_module, 'main'):
            er_backup_module.main()
    except Exception as e:
        import streamlit as st
        st.error(f"Error loading ER Backup Tool: {str(e)}")
        st.info("Please check that the er_backup module is properly configured.")
    finally:
        # Clean up sys.path
        if str(current_dir / "er_backup") in sys.path:
            sys.path.remove(str(current_dir / "er_backup"))
else:
    import streamlit as st
    st.error("ER Backup Tool not found.")
    st.info(f"Expected location: {er_backup_path}")
    st.info("Please check that the er_backup directory and app.py file exist.")
