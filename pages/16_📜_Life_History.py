"""
Life History Dashboard Page
View the full event history for any EarthRanger subject (individual giraffe).
"""

import streamlit as st
import sys
from pathlib import Path

# ── Shared utilities ──────────────────────────────────────────────────────────
current_dir = Path(__file__).parent.parent
sys.path.append(str(current_dir))

try:
    from shared.utils import add_sidebar_logo
    add_sidebar_logo()
except Exception:
    pass  # Logo is cosmetic — don't fail if unavailable

# ── Import and run the life history dashboard ─────────────────────────────────
import importlib.util

app_file = current_dir / "life_history_dashboard" / "app.py"
spec = importlib.util.spec_from_file_location("life_history_app", app_file)
life_history_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(life_history_app)

if __name__ == "__main__":
    life_history_app.main()
