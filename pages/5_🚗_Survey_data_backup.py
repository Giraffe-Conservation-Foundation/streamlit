"""
🚗 Survey data backup
Upload ZIPs produced by the ER2WB Converter to the country/site Google Cloud
Storage bucket. Images are stored under survey/<survey_type>/YYYYMM/ and any
XLSX form in the ZIP is uploaded alongside.
"""

import sys
from pathlib import Path

# Resolve project paths
current_dir = Path(__file__).parent.parent
sys.path.insert(0, str(current_dir))
sys.path.insert(0, str(current_dir / "survey_upload"))

from shared.utils import add_sidebar_logo  # noqa: E402

add_sidebar_logo()

# Execute the self-contained survey upload app
app_path = current_dir / "survey_upload" / "app.py"
exec(compile(app_path.read_text(encoding="utf-8"), str(app_path), "exec"))
