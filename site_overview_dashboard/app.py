"""
Site Overview Dashboard — click a protected area, see what we have.

See site_overview_dashboard/README.md for full status.

Redesigned 2026-08-25 (Courtney's request to revisit this):
  - The map now shows every site in site_crosswalk.json — the GCF protected-
    area list — whether or not it's been refreshed yet, instead of only
    sites that already have a cached summary row. An un-refreshed site shows
    on the map with its name and a "not refreshed yet" note.
  - Each site draws as its real boundary polygon (site_overview_dashboard/
    boundary_lookup.py, cached in data/site_boundaries.json — see
    scripts/refresh_site_boundaries.py) when one's been matched, falling
    back to the AGOL GAD layer's x/y point (as before) when it hasn't, and
    to "not on the map yet" (still listed in the table + selector) when
    neither source has a location for that site.
  - Clicking a shape or marker on the map now actually selects that site in
    the detail panel below, instead of only being able to pick it from the
    dropdown.
"""

from __future__ import annotations

import sys
from pathlib import Path

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

_root = Path(__file__).parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from shared.auth import require_earthranger_login
from site_overview_dashboard.site_profile import get_site_profile
from site_overview_dashboard.local_store import (
    read_boundaries,
    read_crosswalk,
    read_site_summaries,
    upsert_site_summary,
)

# Fill/border for a protected area's boundary polygon.
_BOUNDARY_STYLE = {"fillColor": "#2E7D32", "color": "#1B5E20", "weight": 2, "fillOpacity": 0.25}
_BOUNDARY_HIGHLIGHT = {"fillColor": "#66BB6A", "color": "#1B5E20", "weight": 3, "fillOpacity": 0.4}


def _agol_marker_location(agol_site_field, gad_df) -> tuple | None:
    if not agol_site_field or gad_df is None or gad_df.empty:
        return None
    match = gad_df[
        (gad_df.get("Site") == agol_site_field)
        | (gad_df.get("Region1") == agol_site_field)
        | (gad_df.get("Region0") == agol_site_field)
    ]
    match = match[match["x"].notna() & match["y"].notna()]
    if match.empty:
        return None
    return float(match["y"].mean()), float(match["x"].mean())


def _popup_html(site_code: str, site_name: str, summary_row: dict | None) -> str:
    if not summary_row:
        return f"<b>{site_name}</b><br>({site_code})<br><i>Not refreshed yet — pick it below and hit Refresh.</i>"

    return f"""
    <b>{site_name}</b><br>({site_code})<br>
    Active collars (ER): {summary_row.get('er_active_collars') or '—'}<br>
    Population est. (GAD): {summary_row.get('agol_population_estimate') or '—'} ({summary_row.get('agol_estimate_year') or '—'})<br>
    GiraffeSpotter individuals: {summary_row.get('wildbook_individuals_count') or '— (not connected yet)'}<br>
    Last refreshed: {summary_row.get('last_refreshed') or 'never'}<br>
    Status: {summary_row.get('refresh_status') or '—'}
    """


def render_map(crosswalk: pd.DataFrame, summaries: pd.DataFrame) -> str | None:
    """Draws the map and returns the site_code of whatever was clicked this run, if any."""
    try:
        from gad_dashboard.app import load_gad_data
        gad_df = load_gad_data()
    except Exception:
        gad_df = pd.DataFrame()

    boundaries = read_boundaries()
    summaries_by_code = {r["site_code"]: r for r in summaries.to_dict("records")} if not summaries.empty else {}

    m = folium.Map(location=[0, 20], zoom_start=4, tiles="OpenStreetMap")
    unmapped: list[str] = []
    n_polygons, n_markers = 0, 0

    for _, cw in crosswalk.iterrows():
        site_code = cw.get("site_code")
        if not site_code:
            continue
        site_name = cw.get("site_name") or site_code
        summary_row = summaries_by_code.get(site_code)
        popup_html = _popup_html(site_code, site_name, summary_row)

        boundary = boundaries.get(site_code)
        geojson = boundary.get("geojson") if isinstance(boundary, dict) else None

        if geojson:
            folium.GeoJson(
                geojson,
                name=site_code,
                tooltip=site_code,
                popup=folium.Popup(popup_html, max_width=300),
                style_function=lambda _f: _BOUNDARY_STYLE,
                highlight_function=lambda _f: _BOUNDARY_HIGHLIGHT,
            ).add_to(m)
            n_polygons += 1
            continue

        loc = _agol_marker_location(cw.get("agol_site_field"), gad_df)
        if loc is None:
            unmapped.append(f"{site_code} ({site_name})")
            continue

        folium.Marker(
            location=loc,
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=site_code,
        ).add_to(m)
        n_markers += 1

    map_state = st_folium(m, width=None, height=550, key="site_overview_map")

    st.caption(
        f"{n_polygons} site(s) shown as boundary shapes, {n_markers} as points (from GAD's site "
        f"coordinates, pending a boundary match). Run `python scripts/refresh_site_boundaries.py` "
        f"to fill in more boundary shapes."
    )
    if unmapped:
        with st.expander(f"⚠️ {len(unmapped)} site(s) not on the map yet"):
            st.caption(
                "No boundary match and no AGOL site coordinate for these — set `boundary_query` "
                "and/or `agol_site_field` in site_crosswalk.json, then re-run the relevant refresh script."
            )
            st.write(", ".join(unmapped))

    clicked_tooltip = (map_state or {}).get("last_object_clicked_tooltip")
    return clicked_tooltip


def render_refresh_panel(site_code: str, crosswalk: pd.DataFrame, er_client) -> None:
    match = crosswalk[crosswalk["site_code"] == site_code]
    cw_row: dict = match.iloc[0].to_dict() if not match.empty else {}
    site_name = cw_row.get("site_name") or site_code

    st.subheader(f"{site_name} ({site_code})")

    if st.button(f"🔄 Refresh {site_code} now", key=f"refresh_{site_code}"):
        with st.spinner(f"Pulling live data for {site_code}..."):
            profile = get_site_profile(site_code, crosswalk_row=cw_row, er_client=er_client)
            try:
                upsert_site_summary(profile)
                st.success(f"Updated. Status: {profile['refresh_status']}")
                if profile.get("refresh_notes"):
                    st.warning(profile["refresh_notes"])
                st.rerun()
            except Exception as exc:
                st.error(f"Could not write to site_summaries.json: {exc}")

    if not cw_row.get("er_subject_group"):
        st.caption("ℹ️ EarthRanger: no `er_subject_group` set for this site in site_crosswalk.json yet.")
    if not cw_row.get("agol_site_field"):
        st.caption("ℹ️ GAD/AGOL: no `agol_site_field` set for this site in site_crosswalk.json yet.")
    st.caption("ℹ️ GiraffeSpotter: live read-back not built yet — pending Wildbook API access.")


def main() -> None:
    st.title("🗺️ Site Overview")
    st.caption(
        "Birds-eye view of what we have per protected area: GPS tracking (EarthRanger), "
        "population estimates (GAD/ArcGIS), individual ID (GiraffeSpotter/Wildbook), plus "
        "reports (Zotero) and project status (GQueues) once those are back in scope. "
        "Cached — pick or click a site to refresh it on demand."
    )

    er_client = require_earthranger_login("Site Overview")

    crosswalk = read_crosswalk()
    summaries = read_site_summaries()

    if crosswalk.empty:
        st.warning(
            "site_overview_dashboard/data/site_crosswalk.json is empty — nothing to show yet. "
            "Add a row per protected area (see the README) to get started."
        )
        return

    clicked_site = render_map(crosswalk, summaries)

    if not summaries.empty:
        st.dataframe(summaries, use_container_width=True)
    else:
        st.info(
            "No sites refreshed yet — pick one below and hit \"Refresh\", or run "
            "`python scripts/refresh_site_summaries.py` to pull all of them at once."
        )

    st.divider()
    site_options = sorted(crosswalk["site_code"].dropna().unique().tolist())
    default_index = site_options.index(clicked_site) if clicked_site in site_options else 0
    chosen = st.selectbox("Site to inspect / refresh", site_options, index=default_index)
    if chosen:
        render_refresh_panel(chosen, crosswalk, er_client)


if __name__ == "__main__":
    main()
