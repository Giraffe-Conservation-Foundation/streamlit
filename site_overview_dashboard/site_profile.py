"""
Site Profile — pulls a single-site summary from all five data sources.

See site_overview_dashboard/README.md for full status.

get_site_profile() is the one function both the monthly refresh job
(scripts/refresh_site_summaries.py) and the app's "Refresh this site" button
call. Each source is fetched in its own try/except so one platform being
down or slow doesn't take out the whole profile — direct lesson from the
EarthRanger master-dataset backup failure (exit 143 / OOM): isolate
failures per-source, don't let one all-or-nothing call bring down the job.

What's real vs stubbed (updated 2026-08-25 — Courtney's priority order is
EarthRanger + GAD first, GiraffeSpotter once API access is confirmed, Zotero
and GQueues pinned/deprioritized for now):
  - ER summary:        REAL, but now OPT-IN per site via the crosswalk's
                        `er_subject_group` field (see site_registry.py's
                        module docstring for why) — a site with that field
                        blank is skipped silently, same as any other source
                        with a blank crosswalk field, rather than guessed.
  - AGOL/GAD summary:   REAL — reuses gad_dashboard's load_gad_data(), filtered
                        by the crosswalk's agol_site_field. That field also
                        needs confirming per site against live GAD data before
                        it's filled in — see README "Known open items".
  - Wildbook/GiraffeSpotter summary: STUB, pending Courtney supplying the
                        Wildbook API base URL + credentials — no existing
                        live-read integration in this codebase to build on
                        (er2wb_dashboard only *writes* Wildbook import CSVs).
                        wildbook_locality is now populated for every site
                        (same as its site_code), so this stub's "not
                        implemented" note will show for every site until the
                        real call is built — that's expected, not a bug.
  - Zotero summary:    REAL and left running (works off credentials already in
                        secrets.toml) but deprioritized — not a focus this pass.
  - GQueues summary:   PARTIAL, deprioritized — same as before, reuses
                        gqueues_dashboard's CSV-backup parser but isn't wired
                        up, and needs gcp_service_account which isn't in the
                        local secrets.toml.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

_root = Path(__file__).parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))



# ─── ER — batch path (used by the monthly script, which already has the full ────
# sites_df computed once for every site) ──────────────────────────────────────────
def _fetch_er_summary(subject_group: str, sites_df: pd.DataFrame) -> dict:
    """Pull this subject_group's row out of an already-fetched ER site rollup.
    No separate API call — site_registry.get_canonical_sites() did the work.
    `subject_group` is the crosswalk's er_subject_group value, NOT site_code
    — see site_registry.py's module docstring for why those are separate."""
    if sites_df is None or sites_df.empty:
        return {}
    row = sites_df[sites_df["er_subject_group"] == subject_group]
    if row.empty:
        return {}
    r = row.iloc[0]
    return {
        "er_active_collars":           int(r.get("Active", 0)),
        "er_total_subjects":           int(r.get("Subjects", 0)),
        "er_species":                  r.get("Species", ""),
        "er_most_recent_fix_days_ago": r.get("Most Recent Fix (days ago)"),
        "er_avg_tracking_days":        r.get("Avg Tracking (days)"),
    }


# ─── ER — live single-site path (used by the app's on-demand refresh button, ────
# which only has an authenticated er_client from shared.auth, not raw creds) ─────
def _fetch_er_summary_live(subject_group: str, er_client) -> dict:
    """
    Self-contained live ER summary for one site. Deliberately independent of
    twiga_dash.fetch_subjects (which needs raw username/password to build its
    own client) so the on-demand path can reuse the app's existing logged-in
    EarthRanger session instead of asking the user to sign in twice.

    `subject_group` is the crosswalk's er_subject_group value, NOT site_code
    — see site_registry.py's module docstring for why those are separate.
    """
    try:
        raw_groups = er_client._get(
            "subjectgroups/",
            params={"flat": True, "include_inactive": True, "include_hidden": True},
        )
    except Exception as exc:
        return {"_er_error": f"subjectgroups/ failed: {exc}"}

    if not isinstance(raw_groups, list):
        return {"_er_error": "subjectgroups/ returned unexpected shape"}

    group = next((g for g in raw_groups if isinstance(g, dict) and g.get("name") == subject_group), None)
    if group is None:
        return {"_er_error": f"no ER subject_group named '{subject_group}'"}

    member_ids = {
        str(m.get("id") if isinstance(m, dict) else m)
        for m in (group.get("subjects") or [])
    }
    if not member_ids:
        return {}

    try:
        subjects = er_client.get_subjects(include_inactive=True)
    except TypeError:
        subjects = er_client.get_subjects()
    except Exception as exc:
        return {"_er_error": f"get_subjects failed: {exc}"}

    if subjects is None or subjects.empty:
        return {}

    site_subjects = subjects[subjects["id"].astype(str).isin(member_ids)]
    if site_subjects.empty:
        return {}

    now = pd.Timestamp.now(tz="UTC")
    fix_dates = pd.to_datetime(site_subjects.get("last_position_date"), errors="coerce", utc=True)
    days_since = (now - fix_dates).dt.days

    return {
        "er_total_subjects":           int(len(site_subjects)),
        "er_active_collars":           int(pd.Series(site_subjects.get("is_active")).fillna(False).sum()),
        "er_species":                  ", ".join(sorted(pd.Series(site_subjects.get("common_name")).dropna().unique())),
        "er_most_recent_fix_days_ago": float(days_since.min()) if days_since.notna().any() else None,
    }


# ─── AGOL (real) ────────────────────────────────────────────────────────────────
def _fetch_agol_summary(agol_site_field: Optional[str]) -> dict:
    """Filter gad_dashboard's already-loaded AGOL population data to this site."""
    if not agol_site_field:
        return {}
    try:
        from gad_dashboard.app import load_gad_data
        df = load_gad_data()
        match = df[
            (df.get("Site") == agol_site_field)
            | (df.get("Region1") == agol_site_field)
            | (df.get("Region0") == agol_site_field)
        ]
        if match.empty:
            return {}
        latest = match.sort_values("Year", ascending=False).iloc[0]
        return {
            "agol_population_estimate": int(latest["Estimate"]) if pd.notna(latest.get("Estimate")) else None,
            "agol_estimate_year":       int(latest["Year"]) if pd.notna(latest.get("Year")) else None,
        }
    except Exception as exc:
        return {"_agol_error": str(exc)}


# ─── Wildbook (stub) ────────────────────────────────────────────────────────────
def _fetch_wildbook_summary(wildbook_locality: Optional[str]) -> dict:
    """
    TODO: no existing live-read Wildbook integration in this codebase to build
    on. er2wb_dashboard only produces Wildbook *import* CSVs — it doesn't call
    the Wildbook REST API to read encounters/individuals back.

    Sketch once endpoint + auth are confirmed:
        GET {wildbook_base_url}/api/org.ecocean.Encounter/list?locationID={wildbook_locality}
        -> count distinct individuals, find max encounter date.
    Needs wildbook_base_url + API key/session in st.secrets.
    """
    if not wildbook_locality:
        return {}
    return {"_wildbook_error": "not implemented — see TODO in _fetch_wildbook_summary"}


# ─── Zotero (real — Courtney's local secrets.toml already has [zotero] creds) ───
def _fetch_zotero_summary(zotero_collection: Optional[str]) -> dict:
    """
    Real implementation. Reads library_id/api_key/collection_key from
    st.secrets["zotero"] — already present in the local secrets.toml, so
    this works locally without adding anything new.

    OPEN QUESTION: the local secrets only have ONE global collection_key,
    not a per-site one. If a site's crosswalk row doesn't set its own
    zotero_collection, this falls back to that single global collection —
    meaning every site with no explicit crosswalk entry will show the SAME
    document count/date, not a site-specific one, until Zotero is actually
    organised per-site (separate collections, or a consistent tag scheme).
    Surfaces correctly-scoped numbers only for sites with a real
    zotero_collection set in site_crosswalk.json.

    Also unverified: whether the GCF Zotero library is a 'group' or 'user'
    library — assumed 'group' below (typical for an org library). If wrong,
    the API call fails cleanly and shows up in refresh_notes rather than
    silently returning bad data.
    """
    try:
        import streamlit as st
    except ImportError:
        return {"_zotero_error": "streamlit not available in this context"}

    try:
        zt = st.secrets.get("zotero", {})
        library_id = zt.get("library_id")
        api_key = zt.get("api_key")
        default_collection = zt.get("collection_key")
    except Exception:
        return {"_zotero_error": "could not read [zotero] secrets"}

    collection_key = zotero_collection or default_collection
    if not library_id or not api_key or not collection_key:
        return {}

    try:
        from pyzotero import zotero
    except ImportError:
        return {"_zotero_error": "pyzotero not installed — pip install pyzotero"}

    try:
        zot = zotero.Zotero(library_id, "group", api_key)  # TODO: confirm 'group' vs 'user'
        items = zot.collection_items(collection_key, limit=100)
    except Exception as exc:
        return {"_zotero_error": f"Zotero API call failed: {exc}"}

    if not items:
        return {"zotero_document_count": 0}

    dates = [
        it.get("data", {}).get("dateAdded")
        for it in items
        if isinstance(it, dict) and it.get("data", {}).get("dateAdded")
    ]
    return {
        "zotero_document_count": len(items),
        "zotero_last_added_date": max(dates) if dates else None,
    }


# ─── GQueues (partial — reuses existing CSV parser) ─────────────────────────────
def _fetch_gqueues_summary(gqueues_codes: Optional[str]) -> dict:
    """
    Reuses gqueues_dashboard's existing GQueues-backup-CSV parser (no live API
    yet — matches "api coming" in the meeting notes). Filters the already-parsed
    project list down to the codes assigned to this site in the crosswalk.

    TODO: confirm exact function names/signatures in gqueues_dashboard/app.py
    match what's imported here (parse_gqueues_csv / build_projects) — written
    from reading that module, not executed against live data yet.
    """
    if not gqueues_codes:
        return {}
    try:
        from gqueues_dashboard.app import build_projects  # TODO: confirm this is the right entry point + how it loads the latest backup CSV
        # TODO: build_projects() needs a `sections` dict (from parse_gqueues_csv);
        # this stub doesn't yet know how gqueues_dashboard locates "the latest"
        # backup CSV in Drive — see gqueues_folder_id secret / app.py for that logic.
        return {"_gqueues_error": "not wired up — see TODO in _fetch_gqueues_summary"}
    except Exception as exc:
        return {"_gqueues_error": str(exc)}


# ─── Orchestrator ───────────────────────────────────────────────────────────────
def get_site_profile(
    site_code: str,
    crosswalk_row: Optional[dict] = None,
    sites_df: Optional[pd.DataFrame] = None,
    er_client=None,
) -> dict:
    """
    Build one site's full summary dict, matching SITE_SUMMARIES_COLUMNS.
    Every source is isolated — a failure in one doesn't block the others,
    and gets recorded in refresh_notes instead of raising.

    Pass EITHER sites_df (batch path, e.g. the monthly script) OR er_client
    (on-demand path, e.g. the app's refresh button) for the ER portion.
    """
    crosswalk_row = crosswalk_row or {}
    errors: list[str] = []

    profile: dict = {
        "site_code": site_code,
        "site_name": crosswalk_row.get("site_name") or site_code,
        "country":   crosswalk_row.get("country"),
        "last_refreshed": datetime.now(timezone.utc).isoformat(),
    }

    # ER is opt-in per site via er_subject_group — a blank value means this
    # site hasn't been matched to an EarthRanger subject_group yet, so it's
    # skipped silently (same convention as AGOL/Wildbook/Zotero/GQueues below
    # when their crosswalk field is blank) rather than treated as an error.
    subject_group = crosswalk_row.get("er_subject_group")
    if subject_group:
        try:
            if sites_df is not None:
                profile.update(_fetch_er_summary(subject_group, sites_df))
            elif er_client is not None:
                result = _fetch_er_summary_live(subject_group, er_client)
                if "_er_error" in result:
                    errors.append(f"ER: {result['_er_error']}")
                else:
                    profile.update(result)
            else:
                errors.append("ER: neither sites_df nor er_client provided")
        except Exception as exc:
            errors.append(f"ER: {exc}")

    agol_result = _fetch_agol_summary(crosswalk_row.get("agol_site_field"))
    if "_agol_error" in agol_result:
        errors.append(f"AGOL: {agol_result['_agol_error']}")
    else:
        profile.update(agol_result)

    wb_result = _fetch_wildbook_summary(crosswalk_row.get("wildbook_locality"))
    if "_wildbook_error" in wb_result:
        errors.append(f"Wildbook: {wb_result['_wildbook_error']}")
    else:
        profile.update(wb_result)

    zot_result = _fetch_zotero_summary(crosswalk_row.get("zotero_collection"))
    if "_zotero_error" in zot_result:
        errors.append(f"Zotero: {zot_result['_zotero_error']}")
    else:
        profile.update(zot_result)

    gq_result = _fetch_gqueues_summary(crosswalk_row.get("gqueues_codes"))
    if "_gqueues_error" in gq_result:
        errors.append(f"GQueues: {gq_result['_gqueues_error']}")
    else:
        profile.update(gq_result)

    if not errors:
        profile["refresh_status"] = "ok"
    elif len(errors) >= 4:
        profile["refresh_status"] = "error"
    else:
        profile["refresh_status"] = "partial"
    profile["refresh_notes"] = "; ".join(errors)

    return profile
