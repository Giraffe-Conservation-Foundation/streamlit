"""
Populate site_overview_dashboard/data/site_boundaries.json from OpenStreetMap.

Run this locally whenever you add a site to site_crosswalk.json or change its
boundary_query. Safe to re-run — by default it skips any site_code already
cached with a successful match, so a normal run only fetches what's new.

Usage:
    python scripts/refresh_site_boundaries.py                # fetch missing/uncached sites
    python scripts/refresh_site_boundaries.py --site MMNR    # just one site
    python scripts/refresh_site_boundaries.py --force        # re-fetch everything

No login, no secrets needed — OpenStreetMap's Nominatim search is public and
free. See site_overview_dashboard/boundary_lookup.py for the usage-policy
rate limiting (~1 request/second) this script respects.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from site_overview_dashboard.boundary_lookup import fetch_boundary, MIN_REQUEST_INTERVAL_SECONDS  # noqa: E402
from site_overview_dashboard.local_store import read_boundaries, read_crosswalk, write_boundaries  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", help="Only refresh this one site_code")
    parser.add_argument("--force", action="store_true", help="Re-fetch even sites already cached")
    args = parser.parse_args()

    crosswalk = read_crosswalk()
    if crosswalk.empty:
        print("site_crosswalk.json is empty — nothing to look up.")
        return

    if args.site:
        crosswalk = crosswalk[crosswalk["site_code"] == args.site]
        if crosswalk.empty:
            print(f"No crosswalk row for site_code={args.site!r}.")
            return

    boundaries = dict(read_boundaries())
    fetched = 0

    for _, row in crosswalk.iterrows():
        site_code = row.get("site_code")
        query = row.get("boundary_query")

        if not site_code:
            continue
        if not query:
            print(f"skip {site_code}: no boundary_query set in site_crosswalk.json")
            continue

        cached = boundaries.get(site_code)
        already_matched = isinstance(cached, dict) and cached.get("geojson") is not None
        if already_matched and not args.force:
            print(f"skip {site_code}: already cached (use --force to re-fetch)")
            continue

        print(f"fetching {site_code}: {query!r} ...", end=" ", flush=True)
        result = fetch_boundary(query)
        boundaries[site_code] = result
        fetched += 1

        if result is None:
            print("no polygon match found")
        elif isinstance(result, dict) and result.get("_error"):
            print(f"ERROR: {result['_error']}")
        else:
            print(f"matched: {result.get('display_name')}")

        time.sleep(MIN_REQUEST_INTERVAL_SECONDS)

    write_boundaries(boundaries)
    print(f"\nDone. {fetched} site(s) queried this run; {len(boundaries)} total cached in "
          f"site_overview_dashboard/data/site_boundaries.json.")
    print("Reload the Streamlit app to see updated boundaries on the map.")


if __name__ == "__main__":
    main()
