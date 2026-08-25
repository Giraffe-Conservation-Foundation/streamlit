"""
SUPERSEDED 2026-08-15 — Courtney chose the local-JSON storage option instead
of Google Sheets for this module (no new cloud dependency, single-user local
planning use). Nothing imports this file anymore — see local_store.py for
the active storage layer. Kept here for reference in case this ever needs to
become a shared/team backend, since the Sheets approach still has one real
advantage local_store.py doesn't: multiple people looking at the same
up-to-date cache. Swapping back in is a matter of pointing app.py and
scripts/refresh_site_summaries.py at this module's three functions again.

SITE_SUMMARIES sheet read/write.

Reuses the gcf_projects_dashboard gspread pattern, but
needs WRITE scope (not read-only) because both the monthly refresh job and
the app's on-demand "Refresh this site" button write back to this sheet —
a refresh that only updated the clicking user's session would leave
everyone else looking at stale data, which defeats the point of a shared
cache.

Secrets needed (new):
  site_summaries_sheet_id  — Google Sheet ID for SITE_SUMMARIES. Create the
                              sheet, share Editor access with the service
                              account's client_email (the one already in
                              gcp_service_account), then set this secret.

The existing gcp_service_account secret is reused here, but requested with
the non-readonly `spreadsheets` scope — gcf_projects_dashboard's own SCOPES
list uses spreadsheets.readonly, which is fine to leave as-is for that page.
This module requests its own client with write scope rather than changing
that shared constant, so no existing read-only page is affected.
"""

from __future__ import annotations

from typing import Optional

import gspread
import pandas as pd
import streamlit as st
from google.oauth2 import service_account

from site_overview_dashboard.site_registry import SITE_SUMMARIES_COLUMNS

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",   # write, not readonly
    "https://www.googleapis.com/auth/drive.readonly",
]

WORKSHEET_NAME = "SITE_SUMMARIES"


def _get_client() -> Optional[gspread.Client]:
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
    except Exception:
        return None
    creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)


def _get_sheet_id() -> Optional[str]:
    try:
        return st.secrets.get("site_summaries_sheet_id")
    except Exception:
        return None


@st.cache_data(ttl=300, show_spinner=False)
def read_site_summaries() -> pd.DataFrame:
    """Read the cached SITE_SUMMARIES sheet — this is what the map reads by default."""
    gc = _get_client()
    sheet_id = _get_sheet_id()
    if gc is None or sheet_id is None:
        return pd.DataFrame(columns=SITE_SUMMARIES_COLUMNS)
    try:
        ws = gc.open_by_key(sheet_id).worksheet(WORKSHEET_NAME)
        records = ws.get_all_records()
        df = pd.DataFrame(records)
        if df.empty:
            return pd.DataFrame(columns=SITE_SUMMARIES_COLUMNS)
        return df
    except gspread.exceptions.WorksheetNotFound:
        return pd.DataFrame(columns=SITE_SUMMARIES_COLUMNS)
    except Exception:
        return pd.DataFrame(columns=SITE_SUMMARIES_COLUMNS)


def upsert_site_summary(profile: dict) -> None:
    """
    Write one site's profile back to the sheet — used by both the monthly
    batch job and the on-demand refresh button. Updates the existing row for
    that site_code if present, otherwise appends a new row.

    Raises RuntimeError if secrets aren't configured, so callers (both the
    script and the app) surface that clearly instead of silently no-op'ing.
    """
    gc = _get_client()
    sheet_id = _get_sheet_id()
    if gc is None or sheet_id is None:
        raise RuntimeError(
            "SITE_SUMMARIES write skipped — gcp_service_account or "
            "site_summaries_sheet_id secret not configured."
        )

    sh = gc.open_by_key(sheet_id)
    try:
        ws = sh.worksheet(WORKSHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=WORKSHEET_NAME, rows=200, cols=len(SITE_SUMMARIES_COLUMNS))
        ws.append_row(SITE_SUMMARIES_COLUMNS)

    existing = ws.get_all_records()
    row_values = [str(profile.get(col, "")) for col in SITE_SUMMARIES_COLUMNS]

    for i, rec in enumerate(existing, start=2):  # row 1 = header
        if rec.get("site_code") == profile.get("site_code"):
            ws.update(f"A{i}", [row_values])
            read_site_summaries.clear()  # invalidate cache so the map picks up the change
            return

    ws.append_row(row_values)
    read_site_summaries.clear()
