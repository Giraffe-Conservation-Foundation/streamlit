"""
Site Overview — Twiga Tools page wrapper.
SKELETON — see site_overview_dashboard/README.md before enabling for the team.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from site_overview_dashboard.app import main

main()
