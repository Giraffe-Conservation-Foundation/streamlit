#!/usr/bin/env python3
"""
Site Summaries Refresh — local-first version
Giraffe Conservation Foundation

Loops over every site in site_crosswalk.json (the canonical protected-area
list — see site_overview_dashboard/site_registry.py's module docstring for
why that's the crosswalk now, not ER's live subject_group list) and every
source in site_profile.get_site_profile(), then writes the results to the
local site_summaries.json (see local_store.py) — no Google Sheets, no GCP
service account required.

EarthRanger is now OPT-IN PER SITE via the crosswalk's er_subject_group
column, so this script only asks for your ER login if at least one site
actually has that column filled in — until you've confirmed the mapping
from a site_code to its real ER subject_group and added it to
site_crosswalk.json, ER is simply skipped and everything else (AGOL/GAD,
Zotero, and Wildbook/GQueues once those are wired up) still refreshes.

EarthRanger credentials: reads ER_USERNAME/ER_PASSWORD from the environment
if set (so this still works unattended, e.g. from a future scheduled job);
otherwise prompts interactively, same login you'd use in the Streamlit app.

ArcGIS + Zotero credentials come from st.secrets automatically (this repo's
.streamlit/secrets.toml already has both) — nothing to pass on the command
line for those.

Usage (test, one site only):
    python scripts/refresh_site_summaries.py --site MMNR

Usage (full run, all sites in site_crosswalk.json):
    python scripts/refresh_site_summaries.py

Usage (skip ER even if some sites have er_subject_group set):
    python scripts/refresh_site_summaries.py --skip-er
"""

import argparse
import getpass
import json
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

_root = Path(__file__).parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from site_overview_dashboard.site_registry import get_canonical_sites  # noqa: E402
from site_overview_dashboard.site_profile import get_site_profile  # noqa: E402
from site_overview_dashboard.local_store import read_crosswalk, write_site_summaries  # noqa: E402


def get_er_credentials() -> tuple[str, str]:
    username = os.environ.get("ER_USERNAME")
    password = os.environ.get("ER_PASSWORD")
    if username and password:
        return username, password

    log.info("No ER_USERNAME/ER_PASSWORD in environment — prompting for EarthRanger login.")
    username = input("EarthRanger username: ").strip()
    password = getpass.getpass("EarthRanger password: ")
    return username, password


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", help="Refresh a single site_code only (for testing)")
    parser.add_argument("--skip-er", action="store_true",
                         help="Don't fetch EarthRanger data even if some sites have er_subject_group set")
    args = parser.parse_args()

    log.info("=" * 60)
    log.info("Site Summaries Refresh")
    log.info("=" * 60)

    crosswalk = read_crosswalk()
    if crosswalk.empty:
        log.error("site_crosswalk.json is empty — nothing to refresh. Add sites there first.")
        sys.exit(1)

    if args.site:
        crosswalk = crosswalk[crosswalk["site_code"] == args.site]
        if crosswalk.empty:
            log.error(f"No crosswalk row for site_code={args.site!r}.")
            sys.exit(1)

    wants_er = (not args.skip_er) and crosswalk.get("er_subject_group", "").astype(str).str.strip().ne("").any()

    sites_df = None
    if wants_er:
        er_username, er_password = get_er_credentials()
        log.info("Fetching live EarthRanger subject_group list...")
        sites_df = get_canonical_sites(er_username, er_password)
        if sites_df.empty:
            log.warning("  No subject_groups returned from ER — continuing without ER data for this run.")
            sites_df = None
        else:
            log.info(f"  {len(sites_df)} ER subject_group(s) found")
    else:
        log.info("No site has er_subject_group set (or --skip-er passed) — skipping EarthRanger login "
                  "entirely for this run.")

    cw_by_code = {r["site_code"]: r for r in crosswalk.to_dict("records")}
    site_codes = list(cw_by_code.keys())

    profiles = []
    n_ok, n_partial, n_error = 0, 0, 0
    for site_code in site_codes:
        cw_row = cw_by_code.get(site_code, {})
        profile = get_site_profile(site_code, crosswalk_row=cw_row, sites_df=sites_df)
        profiles.append(profile)

        status = profile.get("refresh_status")
        if status == "ok":
            n_ok += 1
        elif status == "partial":
            n_partial += 1
            log.warning(f"  {site_code}: partial — {profile.get('refresh_notes')}")
        else:
            n_error += 1
            log.error(f"  {site_code}: error — {profile.get('refresh_notes')}")

    log.info(f"Processed {len(profiles)} site(s): {n_ok} ok, {n_partial} partial, {n_error} error")

    if args.site:
        log.info("Single-site test run — not overwriting the full file. Profile:")
        log.info(json.dumps(profiles[0], indent=2, default=str))
        log.info(
            "Looked good? Re-run without --site to refresh all sites and write "
            "site_overview_dashboard/data/site_summaries.json for real."
        )
        return

    log.info("Writing site_overview_dashboard/data/site_summaries.json ...")
    write_site_summaries(profiles)
    log.info("Done. Reload the Streamlit app to see it.")


if __name__ == "__main__":
    main()
