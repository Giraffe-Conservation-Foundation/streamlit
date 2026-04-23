"""
📷 Camera Trap Data Backup
Camera trap image processing and Google Cloud Storage upload.
"""

import sys
from pathlib import Path

current_dir = Path(__file__).parent.parent
sys.path.insert(0, str(current_dir))
sys.path.insert(0, str(current_dir / "camera_trap_upload"))
sys.path.insert(0, str(current_dir / "shared"))

from shared.utils import add_sidebar_logo  # noqa: E402

add_sidebar_logo()

app_path = current_dir / "camera_trap_upload" / "app.py"
exec(compile(app_path.read_text(encoding="utf-8"), str(app_path), "exec"))
