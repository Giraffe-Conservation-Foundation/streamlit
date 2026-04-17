# -*- coding: utf-8 -*-
"""
Survey Dashboard (ZMB) Page Launcher
"""

import streamlit as st
import sys
from pathlib import Path

current_dir = Path(__file__).parent.parent
sys.path.append(str(current_dir))
from shared.utils import add_sidebar_logo

add_sidebar_logo()

def main():
    current_dir = Path(__file__).parent.parent
    module_dir  = current_dir / "survey_dash_zmb"

    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "survey_dash_zmb_app", module_dir / "app.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.main()
    except ImportError as e:
        st.error(f"❌ Error loading Survey Dashboard (ZMB): {e}")
    except Exception as e:
        st.error(f"❌ Error running Survey Dashboard (ZMB): {e}")
        st.exception(e)

if __name__ == "__main__":
    main()
