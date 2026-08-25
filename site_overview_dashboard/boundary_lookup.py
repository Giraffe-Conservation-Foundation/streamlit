"""
Protected-area boundary lookup via OpenStreetMap Nominatim — free, no API key.

Added 2026-08-25 in response to Courtney wanting an actual map of protected-
area SHAPES, not just point markers. The alternative considered was the WDPA
(World Database on Protected Areas) via the Protected Planet API, which is
the more "official" conservation boundary source — but it requires a
registered API token and its bulk shapefile is a multi-GB global download,
neither of which fit a lightweight local tool. OpenStreetMap's Nominatim
search already indexes most national parks/reserves as tagged relations with
usable polygon geometry, needs no signup, and is queryable by plain-text
name — good enough for a planning-level map, not a legal/survey-grade
boundary source.

Usage policy (nominatim.org/release-docs/latest/api/Search): max ~1 request/
second against the public instance, and a descriptive User-Agent identifying
the app. This module is meant to be run in small, deliberate batches (see
scripts/refresh_site_boundaries.py) — NOT called live from the Streamlit app
on every page load or click, both to stay well within that limit and because
a park's boundary essentially never changes, so there's nothing to gain from
re-fetching it on demand the way EarthRanger/AGOL/Zotero numbers are.

Not every protected area resolves cleanly — a name that also matches a town,
a reserve OSM hasn't mapped as a polygon, or an ambiguous/duplicate name can
all return nothing or the wrong feature. fetch_boundary() returns None for
"no usable polygon found" and a dict with "_error" for a request failure, so
callers (and the refresh script's printed output) can tell the two apart and
a bad match can be caught by eye before it ends up on the map.
"""

from __future__ import annotations

import time
from typing import Optional

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# Nominatim's usage policy asks for an identifying User-Agent so they can
# reach out if a client is misbehaving — include a real contact, not a
# generic library default.
USER_AGENT = "TwigaTools-SiteOverview/1.0 (courtney@giraffeconservation.org)"

# Minimum polite spacing between requests when calling in a loop — see
# fetch_boundaries_batch(). fetch_boundary() itself makes exactly one request
# and does not sleep, so callers making a single lookup aren't penalized.
MIN_REQUEST_INTERVAL_SECONDS = 1.1


def fetch_boundary(query: str) -> Optional[dict]:
    """
    One Nominatim lookup for `query` (e.g. 'Maasai Mara National Reserve, Kenya').

    Returns:
      - a dict with 'geojson' (a Polygon or MultiPolygon), 'bbox', 'display_name',
        'osm_type', 'osm_id' on a match with usable polygon geometry
      - None if the query didn't match anything, or matched only a point/line
        (no polygon to draw)
      - {'_error': str} if the HTTP request itself failed — distinct from "no
        match" so a network hiccup isn't recorded as a confirmed non-match
    """
    if not query:
        return None

    params = {
        "q": query,
        "format": "jsonv2",
        "polygon_geojson": 1,
        "limit": 1,
    }
    headers = {"User-Agent": USER_AGENT}

    try:
        resp = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        results = resp.json()
    except Exception as exc:
        return {"_error": f"Nominatim request failed: {exc}"}

    if not results:
        return None

    top = results[0]
    geojson = top.get("geojson")
    if not geojson or geojson.get("type") not in ("Polygon", "MultiPolygon"):
        return None

    return {
        "geojson": geojson,
        "bbox": top.get("boundingbox"),
        "display_name": top.get("display_name"),
        "osm_type": top.get("osm_type"),
        "osm_id": top.get("osm_id"),
    }


def fetch_boundaries_batch(queries: dict[str, str], delay_seconds: float = MIN_REQUEST_INTERVAL_SECONDS) -> dict:
    """
    queries: {site_code: boundary_query}. Looks each one up in turn with a
    polite delay between requests per Nominatim's usage policy — a batch of
    ~30 sites takes well under a minute. Meant to be run locally/manually
    (see scripts/refresh_site_boundaries.py), not from a live web request.

    Returns {site_code: fetch_boundary(...) result}.
    """
    out: dict = {}
    for i, (site_code, query) in enumerate(queries.items()):
        out[site_code] = fetch_boundary(query)
        if i < len(queries) - 1:
            time.sleep(delay_seconds)
    return out
