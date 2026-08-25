"""
Local JSON storage for Site Overview data — no Google Sheets, no cloud storage.

Chosen 2026-08-15: this is for Courtney's own local planning use, not a
shared team backend, so there's no "other people see stale data" problem to
solve — the on-demand refresh button can write straight to these files.

site_summaries.json  — the cached per-site summary table (what the map/table read)
site_crosswalk.json  — manual mapping from site_code to Wildbook/GQueues/Zotero/AGOL/ER keys
site_boundaries.json — cached OpenStreetMap protected-area boundary per site_code (added
                        2026-08-25, see boundary_lookup.py) — a dict keyed by site_code,
                        NOT a list like the other two, since it's a lookup table rather
                        than a row-per-site table with a fixed column schema

All three are plain JSON, committed to the repo like any other data file (not
gitignored) — a scheduled job could commit updates the same way, if this ever
needs to run unattended. For now all are hand-editable/inspectable: open
site_crosswalk.json in any editor to add a site's Wildbook locality, GQueues
codes, Zotero collection, AGOL site field, or EarthRanger subject_group.

If this ever needs to become a shared/team backend instead of local-only,
swap this module for a GCS-blob or Sheets-backed one — app.py, site_profile.py,
and the refresh scripts only depend on the functions below, so the storage
backend is swappable without touching anything else. (See sheet_io.py for the
original Sheets-based version, kept for reference.)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pandas as pd

from site_overview_dashboard.site_registry import SITE_CROSSWALK_COLUMNS, SITE_SUMMARIES_COLUMNS

DATA_DIR = Path(__file__).parent / "data"
SUMMARIES_PATH = DATA_DIR / "site_summaries.json"
CROSSWALK_PATH = DATA_DIR / "site_crosswalk.json"
BOUNDARIES_PATH = DATA_DIR / "site_boundaries.json"


def _read_json_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def read_site_summaries() -> pd.DataFrame:
    records = _read_json_records(SUMMARIES_PATH)
    if not records:
        return pd.DataFrame(columns=SITE_SUMMARIES_COLUMNS)
    return pd.DataFrame(records)


def write_site_summaries(profiles: list[dict]) -> None:
    """Full overwrite — used by the batch refresh (all sites at once)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARIES_PATH.write_text(json.dumps(profiles, indent=2, default=str), encoding="utf-8")


def upsert_site_summary(profile: dict) -> None:
    """Update-or-append one site — used by the app's on-demand refresh button."""
    existing = _read_json_records(SUMMARIES_PATH)
    replaced = False
    for i, rec in enumerate(existing):
        if rec.get("site_code") == profile.get("site_code"):
            existing[i] = profile
            replaced = True
            break
    if not replaced:
        existing.append(profile)
    write_site_summaries(existing)


def read_crosswalk() -> pd.DataFrame:
    records = _read_json_records(CROSSWALK_PATH)
    if not records:
        return pd.DataFrame(columns=SITE_CROSSWALK_COLUMNS)
    return pd.DataFrame(records)


def read_boundaries() -> dict:
    """site_code -> {'geojson', 'bbox', 'display_name', 'osm_type', 'osm_id'} | {'_error': ...} | None.
    Dict, not a DataFrame — see module docstring."""
    if not BOUNDARIES_PATH.exists():
        return {}
    try:
        data = json.loads(BOUNDARIES_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_boundaries(boundaries: dict) -> None:
    """Full overwrite — used by scripts/refresh_site_boundaries.py."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BOUNDARIES_PATH.write_text(json.dumps(boundaries, indent=2, default=str), encoding="utf-8")
