"""
☁️ Google Cloud Buckets
Lists all GCS buckets and top-level folders in the gcf-camera-traps project.
"""

import sys
from pathlib import Path

current_dir = Path(__file__).parent.parent
sys.path.insert(0, str(current_dir))
sys.path.insert(0, str(current_dir / "gcs_browser"))

from shared.utils import add_sidebar_logo  # noqa: E402

add_sidebar_logo()

app_path = current_dir / "gcs_browser" / "app.py"
exec(compile(app_path.read_text(encoding="utf-8"), str(app_path), "exec"))
