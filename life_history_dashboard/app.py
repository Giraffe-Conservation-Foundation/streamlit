"""
Life History Dashboard
Shows all events linked to a selected EarthRanger subject (giraffe individual).
Covers veterinary, translocation, monitoring/tag-update, and survey events.
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import json
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from shared.utils import render_page_header

# Ecoscope imports for EarthRanger integration
try:
    from ecoscope.io.earthranger import EarthRangerIO
    ECOSCOPE_AVAILABLE = True
except ImportError:
    ECOSCOPE_AVAILABLE = False

# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────

SERVER_URL = "https://twiga.pamdas.org"

# Event categories and types we want to surface in the life history
EVENT_CATEGORIES = [
    "veterinary",   # captures vet interventions, mortality, translocation
    "monitoring",   # captures tag updates / unit_update events
]

# Human-readable labels for known event_type slugs
EVENT_TYPE_LABELS = {
    # veterinary
    "giraffe_translocation_3": "Translocation",
    "giraffe_translocation_2": "Translocation (legacy)",
    "giraffe_mortality":       "Mortality",
    "giraffe_vet_treatment":   "Veterinary Treatment",
    "vet_intervention":        "Veterinary Intervention",
    "veterinary":              "Veterinary",
    # monitoring
    "unit_update":             "Tag / Unit Update",
    "survey_observation":      "Survey Observation",
    "survey":                  "Survey",
    "monitoring":              "Monitoring",
    # catch-all for unknown types — displayed as-is
}

# Category badge colours (background, text)
EVENT_COLORS = {
    "Translocation":           ("#1565C0", "#FFFFFF"),
    "Translocation (legacy)":  ("#1976D2", "#FFFFFF"),
    "Mortality":               ("#C62828", "#FFFFFF"),
    "Veterinary Treatment":    ("#6A1B9A", "#FFFFFF"),
    "Veterinary Intervention": ("#7B1FA2", "#FFFFFF"),
    "Veterinary":              ("#AD1457", "#FFFFFF"),
    "Tag / Unit Update":       ("#2E7D32", "#FFFFFF"),
    "Survey Observation":      ("#EF6C00", "#FFFFFF"),
    "Survey":                  ("#F57C00", "#FFFFFF"),
    "Monitoring":              ("#00838F", "#FFFFFF"),
}


# ──────────────────────────────────────────────────────────────────────────────
# Session state
# ──────────────────────────────────────────────────────────────────────────────

def init_session_state():
    defaults = {
        "lh_authenticated": False,
        "lh_username": "",
        "lh_password": "",
        "lh_server_url": SERVER_URL,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


# ──────────────────────────────────────────────────────────────────────────────
# Authentication
# ──────────────────────────────────────────────────────────────────────────────

def authenticate_earthranger():
    """Render the EarthRanger login form."""
    if not ECOSCOPE_AVAILABLE:
        st.error("❌ Ecoscope package is required but not available. Please install ecoscope.")
        return

    st.header("🔐 EarthRanger Authentication")
    st.write("Enter your EarthRanger credentials to view individual life histories:")
    st.info(f"**Server:** {SERVER_URL}")

    username = st.text_input("Username", key="lh_input_username",
                             help="Your EarthRanger username")
    password = st.text_input("Password", type="password", key="lh_input_password",
                             help="Your EarthRanger password")

    if st.button("🔌 Connect to EarthRanger", type="primary", key="lh_connect_btn"):
        if not username or not password:
            st.error("❌ Both username and password are required")
            return
        with st.spinner("🔐 Authenticating with EarthRanger…"):
            try:
                er_io = EarthRangerIO(
                    server=st.session_state.lh_server_url,
                    username=username,
                    password=password,
                )
                # Quick connectivity test
                er_io.get_subjects(limit=1)
                st.session_state.lh_authenticated = True
                st.session_state.lh_username = username
                st.session_state.lh_password = password
                st.success("✅ Successfully authenticated!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Authentication failed: {e}")
                st.info("💡 Please check your username and password.")


def get_er_connection():
    """Return an authenticated EarthRangerIO connection."""
    return EarthRangerIO(
        server=st.session_state.lh_server_url,
        username=st.session_state.lh_username,
        password=st.session_state.lh_password,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Data loading (cached)
# ──────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=1800, show_spinner=False)
def load_subjects(_username: str, _password: str):
    """
    Load ALL subjects (active and inactive) from EarthRanger.
    Returns a DataFrame with columns: subject_id, name, subject_subtype,
    is_active, subject_group_label, _group_debug.
    """
    er_io = EarthRangerIO(server=SERVER_URL, username=_username, password=_password)

    # ------------------------------------------------------------------
    # 1. Fetch subjects
    # ------------------------------------------------------------------
    try:
        subjects_df = er_io.get_subjects(include_inactive=True)
    except TypeError:
        subjects_df = er_io.get_subjects()

    if subjects_df is None or subjects_df.empty:
        return pd.DataFrame()

    subjects_df = subjects_df.reset_index(drop=True)

    keep = {
        "id":              "subject_id",
        "name":            "name",
        "subject_subtype": "subject_subtype",
        "is_active":       "is_active",
    }
    rename_map = {k: v for k, v in keep.items() if k in subjects_df.columns}
    small_df = subjects_df[list(rename_map.keys())].rename(columns=rename_map).copy()

    # ------------------------------------------------------------------
    # 2. Fetch subject groups via er_io._get() — the same internal method
    #    ecoscope uses. Returns a list of group dicts each with
    #    {"id", "name", "subjects": [{"id", "name", ...}, ...]}
    # ------------------------------------------------------------------
    group_map: dict[str, list[str]] = {}  # subject_id -> [group_name, …]
    group_debug_lines: list[str] = []

    try:
        raw_groups = er_io._get(
            "subjectgroups/",
            params={
                "flat": True,
                "include_inactive": True,
                "include_hidden": True,
            },
        )
        group_debug_lines.append(
            f"_get('subjectgroups/') returned type={type(raw_groups).__name__}, "
            f"count={len(raw_groups) if isinstance(raw_groups, list) else '?'}"
        )
        if isinstance(raw_groups, list) and raw_groups:
            first = raw_groups[0]
            group_debug_lines.append(
                f"First group keys: {list(first.keys()) if isinstance(first, dict) else 'not a dict'}"
            )
            if isinstance(first, dict):
                sample_subjects = first.get("subjects", [])
                group_debug_lines.append(
                    f"First group name='{first.get('name')}', "
                    f"subjects count={len(sample_subjects)}, "
                    f"first subject={str(sample_subjects[0])[:200] if sample_subjects else 'none'}"
                )

        SKIP_PREFIXES = ("AF_",)
        SKIP_EXACT   = {"New_subjects"}
        SKIP_WORDS   = ("people", "donor", "wildscape", "adopt", "alive", "movebank", "twiga")

        if isinstance(raw_groups, list):
            for grp in raw_groups:
                if not isinstance(grp, dict):
                    continue
                grp_name = grp.get("name") or ""
                # Skip utility / noise groups
                if (
                    any(grp_name.startswith(p) for p in SKIP_PREFIXES)
                    or grp_name in SKIP_EXACT
                    or any(w in grp_name.lower() for w in SKIP_WORDS)
                ):
                    continue
                for member in (grp.get("subjects") or []):
                    if isinstance(member, dict):
                        sid = str(member.get("id") or "")
                    else:
                        sid = str(member)
                    if sid and grp_name:
                        group_map.setdefault(sid, [])
                        if grp_name not in group_map[sid]:
                            group_map[sid].append(grp_name)

        group_debug_lines.append(
            f"Group map built: {len(group_map)} subjects mapped to groups."
        )

    except Exception as exc:
        group_debug_lines.append(f"_get('subjectgroups/') failed: {exc}")

    if not group_map:
        group_debug_lines.append(
            f"⚠️ No groups found. Subject columns: {list(subjects_df.columns)}"
        )

    small_df["subject_groups"] = small_df["subject_id"].apply(
        lambda sid: group_map.get(str(sid), [])
    )
    small_df["subject_group_label"] = small_df["subject_groups"].apply(
        lambda g: ", ".join(g) if g else "— No group —"
    )

    if "is_active" in small_df.columns:
        small_df["is_active"] = small_df["is_active"].astype(bool)
    else:
        small_df["is_active"] = True

    small_df["_group_debug"] = "\n".join(group_debug_lines)
    return small_df


@st.cache_data(ttl=1800, show_spinner=False)
def load_events_for_subject(_username: str, _password: str, subject_id: str):
    """
    Fetch all events linked to a specific subject UUID via the ER REST API.

    Uses er_io._get() with manual pagination (page_size=100) instead of
    get_objects_multithreaded() to avoid 504 timeout errors caused by the
    large default page size and parallel thread load on the server.

    Returns (df, debug_lines).
    """
    er_io = EarthRangerIO(server=SERVER_URL, username=_username, password=_password)
    debug: list[str] = []

    filter_payload = json.dumps({"related_subjects": [subject_id]})
    debug.append(f"Querying ER for subject {subject_id}")
    debug.append(f"Filter: {filter_payload}")

    PAGE_SIZE = 50
    all_results: list[dict] = []
    page = 1

    while True:
        try:
            response = er_io._get(
                "activity/events/",
                params={
                    "filter": filter_payload,
                    "page_size": PAGE_SIZE,
                    "page": page,
                },
            )
            # _get() returns parsed JSON — either a list or {"results": [...], "count": N}
            if isinstance(response, list):
                results = response
                more_pages = False
            elif isinstance(response, dict):
                results = response.get("results") or []
                total_count = response.get("count", 0)
                more_pages = page * PAGE_SIZE < total_count
            else:
                results = []
                more_pages = False

            debug.append(f"  Page {page}: {len(results)} events")
            all_results.extend(results)

            if not results or not more_pages or len(results) < PAGE_SIZE:
                break
            page += 1

        except Exception as exc:
            debug.append(f"  Page {page} ERROR: {exc}")
            break

    debug.append(f"Total raw events fetched: {len(all_results)}")

    if not all_results:
        debug.append("No events found for this subject.")
        return pd.DataFrame(), debug

    combined = pd.DataFrame(all_results)

    # Deduplicate by event id
    if "id" in combined.columns:
        before = len(combined)
        combined = combined.drop_duplicates(subset=["id"])
        debug.append(f"After dedup: {len(combined)} events (removed {before - len(combined)} dupes)")

    # Parse timestamps
    if "time" in combined.columns:
        combined["time"] = pd.to_datetime(combined["time"], errors="coerce", utc=True)
        combined["date"] = combined["time"].dt.date

    debug.append(f"✅ Total unique events for subject: {len(combined)}")
    return combined, debug


# ──────────────────────────────────────────────────────────────────────────────
# Display helpers
# ──────────────────────────────────────────────────────────────────────────────

def _event_label(event_type_slug: str) -> str:
    label = EVENT_TYPE_LABELS.get(event_type_slug)
    if label:
        return label
    # Make slug more readable
    return event_type_slug.replace("_", " ").title() if event_type_slug else "Unknown"


def _badge(label: str) -> str:
    bg, fg = EVENT_COLORS.get(label, ("#546E7A", "#FFFFFF"))
    return (
        f'<span style="background:{bg};color:{fg};border-radius:4px;'
        f'padding:2px 8px;font-size:0.78rem;font-weight:600;">{label}</span>'
    )


def _safe_details(val) -> str:
    """Return a human-readable string from an event_details dict/str."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    if isinstance(val, dict):
        parts = []
        for k, v in val.items():
            if v is not None and v != "" and v != []:
                parts.append(f"**{k.replace('_',' ').title()}:** {v}")
        return "  \n".join(parts)
    if isinstance(val, str):
        try:
            return _safe_details(json.loads(val))
        except Exception:
            return val
    return str(val)


def render_event_timeline(events: pd.DataFrame):
    """Render events as an interactive table + expandable detail cards."""
    if events.empty:
        st.info("No events found for this individual.")
        return

    # Sort chronologically
    if "time" in events.columns:
        events = events.sort_values("time", ascending=False)

    # ── Summary table ────────────────────────────────────────────────────────
    st.subheader(f"📋 {len(events)} event(s) on record")

    table_rows = []
    for _, row in events.iterrows():
        etype = row.get("event_type", "")
        elabel = _event_label(etype)
        t = row.get("time")
        date_str = t.strftime("%d %b %Y") if pd.notna(t) else "—"
        title_str = row.get("title", "") or row.get("event_type", "")
        table_rows.append({
            "Date": date_str,
            "Type": elabel,
            "Title / Event Type": title_str,
            "Category": row.get("_source_category", ""),
            "Serial #": row.get("serial_number", "") or "",
        })

    table_df = pd.DataFrame(table_rows)
    st.dataframe(table_df, use_container_width=True, hide_index=True)

    # ── Detailed cards ───────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("🗂️ Event Details")

    for _, row in events.iterrows():
        etype = row.get("event_type", "")
        elabel = _event_label(etype)
        t = row.get("time")
        date_str = t.strftime("%d %b %Y %H:%M UTC") if pd.notna(t) else "—"
        title_str = row.get("title", "") or elabel
        serial = row.get("serial_number", "")
        notes = row.get("notes", "") or ""

        expander_label = f"{date_str} — {elabel}"
        if serial:
            expander_label += f"  (#{serial})"

        with st.expander(expander_label, expanded=False):
            col_a, col_b = st.columns([1, 2])
            with col_a:
                st.markdown(f"**Event type:** {_badge(elabel)}", unsafe_allow_html=True)
                st.markdown(f"**Date:** {date_str}")
                if serial:
                    st.markdown(f"**Serial #:** {serial}")
                cat = row.get("_source_category", "")
                if cat:
                    st.markdown(f"**Category:** {cat}")
                # Reported by / created by
                reported = row.get("reported_by", None)
                if reported and isinstance(reported, dict):
                    st.markdown(f"**Reported by:** {reported.get('name', '')}")
                created = row.get("created_at", None)
                if pd.notna(created) if not isinstance(created, float) else False:
                    try:
                        ct = pd.to_datetime(created, utc=True)
                        st.markdown(f"**Recorded:** {ct.strftime('%d %b %Y')}")
                    except Exception:
                        pass

            with col_b:
                # Title
                if title_str and title_str != elabel:
                    st.markdown(f"**Title:** {title_str}")
                # Event details
                details = row.get("event_details", None)
                details_text = _safe_details(details)
                if details_text:
                    st.markdown("**Details:**")
                    st.markdown(details_text)
                # Notes
                if notes:
                    st.markdown("**Notes:**")
                    st.markdown(notes)
                # Related subjects (others besides the one we filtered on)
                related = row.get("related_subjects", [])
                if related and len(related) > 1:
                    others = [r["name"] or r["id"] for r in related]
                    st.markdown(f"**Related subjects:** {', '.join(others)}")


# ──────────────────────────────────────────────────────────────────────────────
# Main app
# ──────────────────────────────────────────────────────────────────────────────

def main():
    init_session_state()

    # ── Authentication ────────────────────────────────────────────────────────
    if not st.session_state.lh_authenticated:
        authenticate_earthranger()
        return

    render_page_header("Life History", "Complete event timeline for any EarthRanger subject", "📜")

    # Logout button
    with st.sidebar:
        st.success(f"✅ Connected as **{st.session_state.lh_username}**")
        if st.button("🔓 Disconnect", key="lh_logout"):
            for k in ["lh_authenticated", "lh_username", "lh_password"]:
                st.session_state[k] = "" if k != "lh_authenticated" else False
            st.cache_data.clear()
            st.rerun()

    st.markdown("---")

    # ── Load subjects ─────────────────────────────────────────────────────────
    with st.spinner("Loading subjects from EarthRanger…"):
        subjects_df = load_subjects(
            _username=st.session_state.lh_username,
            _password=st.session_state.lh_password,
        )

    if subjects_df.empty:
        st.error("No subjects found. Please check your EarthRanger connection.")
        return

    # ── Subject group debug ───────────────────────────────────────────────────
    with st.expander("🐛 Debug: subject group loading", expanded=False):
        debug_text = subjects_df["_group_debug"].iloc[0] if "_group_debug" in subjects_df.columns else "No debug info"
        st.code(debug_text, language="")
        n_with_groups = (subjects_df["subject_group_label"] != "— No group —").sum()
        st.write(f"Subjects with a group: **{n_with_groups}** / {len(subjects_df)}")
        if n_with_groups > 0:
            st.dataframe(
                subjects_df[["name", "subject_group_label", "is_active"]]
                .query("subject_group_label != '— No group —'")
                .head(20),
                use_container_width=True,
                hide_index=True,
            )

    # ── Filters ───────────────────────────────────────────────────────────────
    st.subheader("🔍 Select Individual")

    filter_col1, filter_col2 = st.columns([1, 2])

    # 1. Subject group filter
    with filter_col1:
        all_groups = sorted({
            grp
            for groups in subjects_df["subject_group_label"]
            for grp in groups.split(", ")
            if grp and grp != "— No group —"
        })
        group_options = ["All groups"] + all_groups + ["— No group —"]

        selected_group = st.selectbox(
            "Filter by Subject Group",
            options=group_options,
            index=0,
            key="lh_group_select",
            help="Filter individuals by their EarthRanger subject group",
        )

    # Apply group filter
    if selected_group == "All groups":
        filtered_subjects = subjects_df.copy()
    elif selected_group == "— No group —":
        filtered_subjects = subjects_df[subjects_df["subject_group_label"] == "— No group —"]
    else:
        filtered_subjects = subjects_df[
            subjects_df["subject_group_label"].str.contains(selected_group, na=False)
        ]

    # 2. Individual subject selector
    with filter_col2:
        if filtered_subjects.empty:
            st.warning("No individuals match the selected filters.")
            return

        # Build dropdown labels "Name (group | active/inactive)"
        def _subject_label(row):
            status = "active" if row["is_active"] else "inactive"
            grp = row["subject_group_label"]
            subtype = row.get("subject_subtype", "")
            parts = [p for p in [grp, subtype] if p and p != "— No group —"]
            extra = " | ".join(parts) if parts else ""
            return f"{row['name']}  [{status}{' | ' + extra if extra else ''}]"

        filtered_subjects = filtered_subjects.copy()
        filtered_subjects["_label"] = filtered_subjects.apply(_subject_label, axis=1)
        filtered_subjects = filtered_subjects.sort_values("name")

        subject_labels = ["— Select an individual —"] + filtered_subjects["_label"].tolist()
        selected_label = st.selectbox(
            f"Individual ({len(filtered_subjects)} shown)",
            options=subject_labels,
            index=0,
            key="lh_subject_select",
        )

    if selected_label == "— Select an individual —":
        st.info("👆 Select a subject group and individual to view their life history.")
        return

    # Resolve selected subject
    selected_row = filtered_subjects[filtered_subjects["_label"] == selected_label].iloc[0]
    subject_id = str(selected_row["subject_id"])
    subject_name = selected_row["name"]

    # ── Subject summary banner ────────────────────────────────────────────────
    st.markdown("---")
    banner_cols = st.columns(4)
    with banner_cols[0]:
        st.metric("Individual", subject_name)
    with banner_cols[1]:
        st.metric("Status", "Active ✅" if selected_row["is_active"] else "Inactive ⛔")
    with banner_cols[2]:
        grp_display = selected_row["subject_group_label"]
        st.metric("Subject Group", grp_display if grp_display != "— No group —" else "—")
    with banner_cols[3]:
        subtype = selected_row.get("subject_subtype", "") or "—"
        st.metric("Subject Type", subtype)

    st.markdown("---")

    # ── Load events for this subject ──────────────────────────────────────────
    with st.status(f"Loading events for **{subject_name}**…", expanded=True) as _status:
        st.write(f"📡 Querying EarthRanger events endpoint")
        st.write(f"🔑 Subject UUID: `{subject_id}`")
        st.write(f"🔗 Filter: `{{\"related_subjects\": [\"{subject_id}\"]}}`")
        st.write("⏳ Fetching pages of 50 events at a time — please wait…")
        subject_events, event_debug = load_events_for_subject(
            _username=st.session_state.lh_username,
            _password=st.session_state.lh_password,
            subject_id=subject_id,
        )
        if subject_events.empty:
            _status.update(label=f"⚠️ No events found for {subject_name}", state="error", expanded=True)
        else:
            _status.update(label=f"✅ {len(subject_events)} events loaded for {subject_name}", state="complete", expanded=False)

    with st.expander("🐛 Debug: event loading", expanded=subject_events.empty):
        st.code("\n".join(event_debug), language="")

    # ── Optional date-range filter ────────────────────────────────────────────
    if not subject_events.empty and "time" in subject_events.columns:
        with st.expander("📅 Filter by date range (optional)", expanded=False):
            min_date = subject_events["time"].min().date()
            max_date = subject_events["time"].max().date()
            date_col1, date_col2 = st.columns(2)
            with date_col1:
                from_date = st.date_input("From", value=min_date, key="lh_date_from")
            with date_col2:
                to_date = st.date_input("To", value=max_date, key="lh_date_to")
            if from_date and to_date:
                subject_events = subject_events[
                    (subject_events["time"].dt.date >= from_date) &
                    (subject_events["time"].dt.date <= to_date)
                ]

    # ── Event type filter ─────────────────────────────────────────────────────
    if not subject_events.empty and "event_type" in subject_events.columns:
        present_types = sorted(subject_events["event_type"].dropna().unique().tolist())
        type_labels = {t: _event_label(t) for t in present_types}
        all_label_options = sorted(set(type_labels.values()))

        if len(all_label_options) > 1:
            selected_type_labels = st.multiselect(
                "Filter by event type",
                options=all_label_options,
                default=all_label_options,
                key="lh_event_type_filter",
            )
            # Map labels back to slugs
            selected_slugs = [slug for slug, label in type_labels.items()
                              if label in selected_type_labels]
            subject_events = subject_events[subject_events["event_type"].isin(selected_slugs)]

    # ── Render timeline ───────────────────────────────────────────────────────
    st.subheader(f"🦒 Life History: {subject_name}")
    render_event_timeline(subject_events)


if __name__ == "__main__":
    main()
