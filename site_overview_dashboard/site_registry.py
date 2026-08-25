"""
Site Registry — canonical protected-area list + cross-platform crosswalk.

See site_overview_dashboard/README.md for full status.

REDESIGNED 2026-08-25: the canonical `site_code` is now the same short code
GCF already uses for GiraffeSpotter/Wildbook uploads (er2wb_dashboard's
COUNTRY_SITES / SITE_NAMES, e.g. 'MMNR' = Maasai Mara National Reserve) —
that's the one list of "our protected areas" that's actually maintained and
authoritative across the org, so the map is never empty just because nobody
has logged into EarthRanger yet.

This is a deliberate change from the original design, which used the live
EarthRanger `subject_group` name (e.g. 'KEN_MaraNorth') as the canonical key.
That still doesn't have a confirmed 1:1 mapping to these Wildbook site codes
(nobody has compared the two lists site-by-site), so ER matching is now a
SEPARATE, optional crosswalk field — `er_subject_group` — filled in per site
once confirmed, rather than assumed from site_code. A site with no
er_subject_group set simply shows no EarthRanger stats yet (same as any
other source with a blank crosswalk field); it still appears on the map via
its protected-area boundary/name.

Every platform (Wildbook, GQueues, Zotero, AGOL, EarthRanger) uses its own
naming convention, so the hand-maintained SITE_CROSSWALK JSON file
(local_store.py, site_overview_dashboard/data/site_crosswalk.json) maps each
canonical site_code to the equivalent key/filter value on that platform. See
SITE_CROSSWALK_COLUMNS below for the schema.

NOTE on two ER access paths in this module:
  - get_canonical_sites(username, password) — used by the standalone monthly
    refresh script (scripts/refresh_site_summaries.py), which has real
    ER_USERNAME/ER_PASSWORD from GitHub Actions secrets and builds its own
    EarthRangerIO client, same as scripts/backup_earthranger.py already does.
    Returns ER's own subject_group list (column `er_subject_group`) — NOT
    the canonical site_code list, see redesign note above.
  - site_profile._fetch_er_summary_live(subject_group, er_client) — used by
    the Streamlit app's on-demand "Refresh this site" button, which only has
    an already-authenticated er_client from
    shared.auth.require_earthranger_login() (no raw password available in
    session_state, by design). This is a separate, self-contained code path
    — see site_profile.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

# Reuse twiga_dash's already-tested ER subject-group parsing rather than
# duplicating it — see twiga_dash/app.py::fetch_subjects / build_project_sites_df.
_root = Path(__file__).parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from twiga_dash.app import fetch_subjects, build_summary_df, build_project_sites_df, COUNTRY_NAMES  # noqa: E402


# ─── SITE_CROSSWALK schema — data/site_crosswalk.json, hand-edit to add sites ────
SITE_CROSSWALK_COLUMNS = [
    "site_code",          # canonical key — the GiraffeSpotter/Wildbook site code
                           # from er2wb_dashboard's SITE_NAMES, e.g. 'MMNR'
    "site_name",           # full protected-area name, e.g. 'Maasai Mara National Reserve'
    "country",              # display country name, e.g. 'Kenya'
    "boundary_query",      # free-text place name+country for the OpenStreetMap boundary
                            # lookup (scripts/refresh_site_boundaries.py), e.g.
                            # 'Maasai Mara National Reserve, Kenya'
    "er_subject_group",    # EXACT EarthRanger subject_group name for this site, once
                            # confirmed, e.g. 'KEN_MaraNorth' — leave blank to skip ER
                            # for this site rather than guess and get it wrong
    "wildbook_locality",   # locality/location string used in GiraffeSpotter/Wildbook
                            # encounters — defaults to site_code, override if different
    "gqueues_codes",       # comma-separated GQueues project codes at this site, e.g. 'KEN1,KEN3'
    "zotero_collection",   # Zotero collection name holding reports/docs for this site
    "agol_site_field",     # value to match against AGOL GAD layer's Site/Region1/Region0
                            # field — needs confirming against live GAD data, left blank
                            # until verified rather than guessed
    "notes",
]

# ─── SITE_SUMMARIES schema — data/site_summaries.json, the cached output ────────
SITE_SUMMARIES_COLUMNS = [
    "site_code", "country", "site_name", "last_refreshed",
    "er_active_collars", "er_total_subjects", "er_species",
    "er_most_recent_fix_days_ago", "er_avg_tracking_days",
    "wildbook_individuals_count", "wildbook_last_encounter_date",
    "agol_population_estimate", "agol_estimate_year",
    "zotero_document_count", "zotero_last_added_date",
    "gqueues_open_projects", "gqueues_project_codes",
    "refresh_status",   # 'ok' | 'partial' | 'error'
    "refresh_notes",    # which source(s) failed, if any — keeps a bad API day from hiding silently
]


def get_canonical_sites(username: str, password: str) -> pd.DataFrame:
    """
    Live EarthRanger subject_group list + stats, for matching against the
    crosswalk's `er_subject_group` column. Requires raw ER credentials
    (builds its own EarthRangerIO client) — intended for the standalone
    refresh script, not the Streamlit app session.

    Returns the same shape as twiga_dash's "Project Sites" tab, with the ER
    group-name column renamed to `er_subject_group` (NOT `site_code` — see
    the module-level redesign note: this is ER's own naming, matched into
    the canonical site list via the crosswalk, not used as the canonical key
    itself): er_subject_group, Country, Species, Subjects, Active, First
    Deployment, Most Recent Fix (days ago), Avg Tracking (days), Total
    Tracking (days).

    twiga_dash's pipeline is two steps, not one: fetch_subjects() returns the
    raw subject rows (with a 'subject_group_label' column), and a separate
    build_summary_df() reshapes that into the 'summary' table (with a
    'subject_group' column, is_active, days_since, tracking_days, etc.) that
    build_project_sites_df() actually expects. Skipping build_summary_df()
    and passing raw fetch_subjects() output straight into
    build_project_sites_df() raises KeyError('subject_group') — that's the
    bug fixed here on 2026-08-19 after Courtney hit it on a real run.
    """
    raw = fetch_subjects(username, password)
    summary, _debug_lines = build_summary_df(raw)
    sites_df = build_project_sites_df(summary)
    if not sites_df.empty:
        sites_df = sites_df.rename(columns={"Site / Group": "er_subject_group"})
    return sites_df


# NOTE: the crosswalk is now loaded from a local JSON file, not a Google
# Sheet — see local_store.read_crosswalk(). This module still owns the
# column schema above since it's shared by the registry, the profile
# builder, and the storage layer.
