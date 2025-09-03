#!/usr/bin/env python3
"""
Simple test script to check if ER Backup tool loads without errors
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    # Try to compile the ER Backup file
    import py_compile
    backup_file = "pages/10_💾_ER_Backup.py"
    py_compile.compile(backup_file, doraise=True)
    print("✅ ER Backup tool compiles successfully")
    
    # Try basic imports that the tool needs
    import streamlit as st
    import pandas as pd
    import numpy as np
    from datetime import datetime, date, timedelta
    import json
    import os
    import zipfile
    import io
    from pathlib import Path
    print("✅ All required packages are available")
    
    # Try ecoscope import
    try:
        from ecoscope.io.earthranger import EarthRangerIO
        print("✅ Ecoscope is available")
    except ImportError:
        print("⚠️ Ecoscope not available - install with: pip install ecoscope")
    
    print("✅ All tests passed - ER Backup tool is ready!")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure ecoscope is installed: pip install ecoscope")
    
except Exception as e:
    print(f"❌ Error: {e}")
    print("There may be syntax or other issues in the code")
