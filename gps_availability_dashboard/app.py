"""
GPS Data Availability Dashboard
Quick summary of GPS tracking data available by subject group.
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from ecoscope.io.earthranger import EarthRangerIO

ER_SERVER = "https://twiga.pamdas.org"

MANUFACTURER_DISPLAY = {
    'mapipedia': 'Ceres',
    'gsatsolar': 'GSat',
    'awt-gundi': 'Africa Wildlife Tracking',
    'savannah_tracking_provider': 'Savannah Tracking',
    'spoortrack': 'SpoorTrack',
}

EXCLUDED_PROVIDERS = {
    'twiga-awe-telemetry',
    'move_bank',
    'gundi_awt_push_v2_9c89bde7-2d98-437b-9170-6913906fd9f6',
    'SOURCE_PROVIDER',
}


# ── Session state ──────────────────────────────────────────────────────────────

def init_session_state():
    defaults = {'authenticated': False, 'username': '', 'password': ''}
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


# ── EarthRanger client (one instance per username/password, shared across calls) ─

@st.cache_resource
def get_er_client(username, password):
    """
    Create and cache a single EarthRangerIO instance per credential pair.
    Using cache_resource means one login happens, then the authenticated
    session is reused for all subsequent API calls — no repeated logins.
    """
    return EarthRangerIO(server=ER_SERVER, username=username, password=password)


# ── Authentication ────────────────────────────────────────────────────────────

def er_login(username, password):
    try:
        er = get_er_client(username, password)
        er.get_subjectgroups(flat=True)
        return True
    except Exception:
        # Clear the cached (broken) client so the next attempt creates a fresh one
        get_er_client.clear()
        return False


def authenticate_earthranger():
    st.header("🔐 EarthRanger Authentication")
    st.info(f"**Server:** {ER_SERVER}")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("🔌 Login to EarthRanger", type="primary"):
        if not username or not password:
            st.error("❌ Username and password are required")
            return
        with st.spinner("Authenticating..."):
            if er_login(username, password):
                st.session_state.authenticated = True
                st.session_state.username = username
                st.session_state.password = password
                st.success("✅ Successfully logged in!")
                st.rerun()
            else:
                st.error("❌ Invalid credentials. Please try again.")


# ── Data loading (all cached 1 hour) ─────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_subject_groups(username, password):
    er = get_er_client(username, password)
    result = er.get_subjectgroups(include_inactive=False, include_hidden=True, isvisible=True, flat=True)
    if isinstance(result, list):
        return pd.DataFrame(result) if result else pd.DataFrame()
    return result


@st.cache_data(ttl=3600)
def load_subjects_for_group(username, password, group_id):
    """
    Fetch all subjects (active + inactive) for a group using its UUID.
    Using subject_group_id bypasses ecoscope's internal name→ID lookup,
    which can 404 for groups that contain only inactive subjects.
    """
    er = get_er_client(username, password)
    return er.get_subjects(subject_group_id=group_id, include_inactive=True)


@st.cache_data(ttl=3600)
def load_subject_sources_raw(username, password, subject_id):
    """
    Returns raw list of source-assignment dicts for a subject.
    Each item looks like:
      {
        "source": {"provider": "mapipedia", "manufacturer_id": "GCF01278",
                   "model_name": "...", ...},
        "assigned_range": {"lower": "2023-01-15T00:00:00Z", "upper": null},
        ...
      }
    Returns [] on failure.
    """
    er = get_er_client(username, password)
    try:
        result = er.get_subject_sources(subject_id=subject_id)
        if isinstance(result, list):
            return result
        # Some ecoscope versions return a DataFrame — convert to records
        if isinstance(result, pd.DataFrame):
            return result.to_dict('records')
        return []
    except Exception:
        return []


# ── Parse source assignments ──────────────────────────────────────────────────

def _parse_source_assignments(raw_assignments):
    """
    Parse the flat list returned by get_subject_sources.
    Each item is a source dict with top-level 'provider' and
    'additional.collar_manufacturer' — there is NO assigned_range here.

    Returns:
      providers     – list of non-excluded provider strings
      manufacturer  – human-readable manufacturer string (prefers
                      additional.collar_manufacturer, falls back to
                      MANUFACTURER_DISPLAY lookup on provider)
    """
    providers = []
    mfr_names = set()

    for item in raw_assignments:
        prov = item.get('provider', '')
        if prov and prov not in EXCLUDED_PROVIDERS:
            providers.append(prov)

        # Prefer the human-readable name stored in additional
        additional = item.get('additional') or {}
        collar_mfr = additional.get('collar_manufacturer', '').strip()
        if collar_mfr:
            mfr_names.add(collar_mfr)
        elif prov and prov not in EXCLUDED_PROVIDERS:
            mfr_names.add(MANUFACTURER_DISPLAY.get(prov, prov))

    manufacturer = ", ".join(sorted(mfr_names)) if mfr_names else ""
    return providers, manufacturer


# ── Helper utilities ──────────────────────────────────────────────────────────

def _fmt_date(val, fmt='%y-%m-%d'):
    """Format date/datetime to short YY-MM-DD, or '' if missing."""
    if val is None:
        return ""
    try:
        dt = pd.to_datetime(val)
        if pd.isna(dt):
            return ""
        return dt.strftime(fmt)
    except Exception:
        return ""


def _last_fix_from_subject(subject):
    """Extract last GPS fix date from subject fields (no extra API call)."""
    for field in ('last_position_date', 'last_observation_date'):
        val = subject.get(field)
        if val:
            return val
    return None


# ── Total-days helper ────────────────────────────────────────────────────────

def _total_days(start_val, end_val):
    """Return integer days between two date-like values, or '' if either is missing."""
    if not start_val or not end_val:
        return ""
    try:
        s = pd.to_datetime(start_val)
        e = pd.to_datetime(end_val)
        if pd.isna(s) or pd.isna(e):
            return ""
        return int((e - s).days)
    except Exception:
        return ""


# ── Build per-subject detail rows (one row per source/manufacturer) ───────────

def build_detail_rows(group_name, subjects_df, username, password, load_mfr):
    rows = []
    for _, subject in subjects_df.iterrows():
        sid          = str(subject.get('id', ''))
        last_fix     = _last_fix_from_subject(subject)
        is_active    = bool(subject.get('is_active', False))
        deploy_start = subject.get('created_at')
        deploy_end_fmt = "Active" if is_active else ""
        days         = _total_days(deploy_start, last_fix)

        base = {
            'Subject':      subject.get('name', sid),
            'Group':        group_name,
            'Active':       is_active,
            'Deploy Start': _fmt_date(deploy_start),
            'Deploy End':   deploy_end_fmt,
            'Last Fix':     _fmt_date(last_fix),
            'Total Days':   days,
        }

        if load_mfr:
            raw = load_subject_sources_raw(username, password, sid)
            if raw:
                # One row per source so each manufacturer gets its own line
                for item in raw:
                    prov       = item.get('provider', '')
                    additional = item.get('additional') or {}
                    collar_mfr = additional.get('collar_manufacturer', '').strip()
                    if collar_mfr:
                        mfr = collar_mfr
                    elif prov and prov not in EXCLUDED_PROVIDERS:
                        mfr = MANUFACTURER_DISPLAY.get(prov, prov)
                    else:
                        mfr = prov  # show raw if not mapped / not excluded
                    rows.append({**base, 'Manufacturer': mfr})
            else:
                rows.append({**base, 'Manufacturer': ''})
        else:
            rows.append(base)

    return rows


# ── Summary table builder ─────────────────────────────────────────────────────

def build_summary_row(group_name, subjects_df, username, password, load_mfr):
    deploy_starts    = []
    last_fixes       = []
    all_manufacturers = set()
    has_active       = False

    for _, subject in subjects_df.iterrows():
        sid       = str(subject.get('id', ''))
        is_active = bool(subject.get('is_active', False))
        if is_active:
            has_active = True

        # Deploy start from subject's created_at
        created = subject.get('created_at')
        if created:
            try:
                deploy_starts.append(pd.to_datetime(created))
            except Exception:
                pass

        # Last fix
        lf = _last_fix_from_subject(subject)
        if lf:
            try:
                last_fixes.append(pd.to_datetime(lf))
            except Exception:
                pass

        # Manufacturer (per-subject source call)
        if load_mfr:
            raw = load_subject_sources_raw(username, password, sid)
            _, mfr = _parse_source_assignments(raw)
            if mfr:
                all_manufacturers.add(mfr)

    n_active = int(subjects_df['is_active'].sum()) if 'is_active' in subjects_df.columns else "?"

    data_start = min(deploy_starts) if deploy_starts else None
    data_end   = max(last_fixes)   if last_fixes   else None

    return {
        'Group':         group_name,
        'Subjects':      len(subjects_df),
        'Active':        n_active,
        'Data Start':    _fmt_date(data_start),
        'Data End':      _fmt_date(data_end),
        'Total Days':    _total_days(data_start, data_end),
        'Deploy Start':  _fmt_date(data_start),
        'Deploy End':    "Active" if has_active else "",
        'Manufacturers': ", ".join(sorted(all_manufacturers)) if all_manufacturers else ("—" if not load_mfr else ""),
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    return _main_impl()


def _main_impl():
    init_session_state()

    st.title("📡 GPS Data Availability")
    st.markdown(
        "Quick overview of GPS tracking data by subject group — "
        "subjects, date coverage, deployments, and tag manufacturers."
    )

    if not st.session_state.authenticated:
        authenticate_earthranger()
        return

    username = st.session_state.username
    password = st.session_state.password

    # Sidebar
    st.sidebar.markdown("### 🔐 Authentication ✅")
    st.sidebar.write(f"**User:** {username}")
    st.sidebar.write(f"**Server:** {ER_SERVER}")
    st.sidebar.markdown("---")

    if st.sidebar.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()

    if st.sidebar.button("🔓 Logout"):
        st.cache_resource.clear()
        for key in ['authenticated', 'username', 'password']:
            st.session_state.pop(key, None)
        st.rerun()

    # ── Load subject groups ───────────────────────────────────────────────────
    with st.spinner("Loading subject groups..."):
        try:
            groups_df = load_subject_groups(username, password)
        except Exception as e:
            st.error(f"Could not load subject groups: {e}")
            return

    if groups_df.empty:
        st.warning("No subject groups found in EarthRanger.")
        return

    name_col = next(
        (c for c in ('name', 'group_name', 'title') if c in groups_df.columns),
        groups_df.columns[0],
    )
    id_col = next(
        (c for c in ('id', 'group_id') if c in groups_df.columns),
        None,
    )
    group_names = sorted(groups_df[name_col].dropna().unique().tolist())

    # name → id lookup (used to call get_subjects by ID, avoiding a secondary
    # name-resolution call that 404s for inactive-only groups)
    name_to_id = (
        dict(zip(groups_df[name_col], groups_df[id_col]))
        if id_col else {}
    )

    # ── Group selector ────────────────────────────────────────────────────────
    selected_groups = st.multiselect(
        "Select subject groups",
        options=group_names,
        default=[],
        help="Choose one or more subject groups to view GPS data availability.",
    )

    load_mfr = st.checkbox(
        "Include GPS manufacturer info",
        value=True,
        help="Shows the GPS tag manufacturer/provider for each subject.",
    )

    if not selected_groups:
        st.info("Select one or more subject groups above to get started.")
        return

    # ── Load subjects for selected groups ────────────────────────────────────
    all_subjects = {}
    with st.spinner("Loading subjects..."):
        for group in selected_groups:
            try:
                group_id = name_to_id.get(group)
                if group_id:
                    df = load_subjects_for_group(username, password, group_id)
                else:
                    # Fallback to name if ID wasn't in the groups response
                    df = load_subjects_for_group(username, password, group)
                if not df.empty:
                    all_subjects[group] = df
                else:
                    st.warning(f"No subjects found in group '{group}'.")
            except Exception as e:
                st.warning(f"Could not load subjects for '{group}': {e}")

    if not all_subjects:
        st.warning("No subjects found for the selected groups.")
        return

    total = sum(len(df) for df in all_subjects.values())
    st.success(f"Found **{total}** subjects across **{len(all_subjects)}** group(s).")

    # ── Summary table ─────────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("📊 Group Summary")

    summary_rows = []
    with st.spinner("Loading deployment info for summary…"):
        for group_name, subjects_df in all_subjects.items():
            summary_rows.append(
                build_summary_row(group_name, subjects_df, username, password, load_mfr)
            )

    summary_df = pd.DataFrame(summary_rows)
    if not load_mfr:
        summary_df = summary_df.drop(columns=['Manufacturers'], errors='ignore')

    st.dataframe(summary_df, use_container_width=True, hide_index=True)

    # ── Detailed subject table ────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("📋 Subject Detail")

    detail_rows = []
    with st.spinner("Loading per-subject deployment details…"):
        for group_name, subjects_df in all_subjects.items():
            detail_rows.extend(
                build_detail_rows(group_name, subjects_df, username, password, load_mfr)
            )

    if not detail_rows:
        st.info("No subject detail data available.")
        return

    detail_df = pd.DataFrame(detail_rows)
    if not load_mfr:
        detail_df = detail_df.drop(columns=['Manufacturer'], errors='ignore')

    st.dataframe(detail_df, use_container_width=True, hide_index=True)

    # Download
    csv = detail_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="⬇️ Download detail as CSV",
        data=csv,
        file_name=f"gps_availability_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    main()
