"""
GPS Data Availability Dashboard
Quick summary of GPS tracking data available by subject group.
"""

import json
import streamlit as st
import pandas as pd
from datetime import datetime
from pathlib import Path
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

EMBARGO_CONFIG_FILE = Path(__file__).parent / "embargo_config.json"

# Days remaining before we switch from 🔴 to 🟡 (expiring soon)
EXPIRING_SOON_DAYS = 60


# ── Embargo config (persists across restarts) ─────────────────────────────────

def load_embargo_config():
    if EMBARGO_CONFIG_FILE.exists():
        try:
            with open(EMBARGO_CONFIG_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"sheet_url": ""}


def save_embargo_config(url: str):
    try:
        with open(EMBARGO_CONFIG_FILE, 'w') as f:
            json.dump({"sheet_url": url}, f)
        return True
    except Exception:
        return False


# ── Embargo data loading ──────────────────────────────────────────────────────

def _build_csv_url(sheet_url: str, tab_name: str = "data_embargo") -> str:
    """
    Convert any Google Sheets URL into a CSV export URL for a specific tab.
    Works with 'Anyone with the link' sharing — no Publish to web needed.
    Accepts: full sheet URL, spreadsheet ID alone, or already-built export URLs.
    """
    import re
    # Already a CSV export URL — use as-is
    if "output=csv" in sheet_url or "tqx=out:csv" in sheet_url:
        return sheet_url
    # Extract spreadsheet ID
    match = re.search(r'/spreadsheets/d/([a-zA-Z0-9_-]+)', sheet_url)
    if match:
        sheet_id = match.group(1)
    else:
        # Assume raw ID was pasted
        sheet_id = sheet_url.strip()
    return (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}"
        f"/gviz/tq?tqx=out:csv&sheet={tab_name}"
    )


@st.cache_data(ttl=1800)
def load_embargo_data(sheet_url: str) -> pd.DataFrame:
    """Load embargo registry from a Google Sheet shared with 'Anyone with the link'."""
    if not sheet_url:
        return pd.DataFrame()
    csv_url = _build_csv_url(sheet_url)
    df = pd.read_csv(csv_url)
    df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
    for col in ('embargo_start', 'embargo_end'):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    if 'group' in df.columns:
        df['group'] = df['group'].str.strip()
    return df


def get_active_embargoes(group_name: str, embargo_df: pd.DataFrame) -> list:
    """Return list of active embargo record dicts for a group (today's date).
    The 'group' column may contain multiple groups separated by ';'.
    """
    if embargo_df.empty or 'group' not in embargo_df.columns:
        return []
    today = pd.Timestamp.now().normalize()
    target = group_name.strip()

    def matches(cell):
        return any(g.strip() == target for g in str(cell).split(';'))

    group_match = embargo_df['group'].apply(matches)
    mask = (
        group_match &
        (embargo_df['embargo_start'].notna()) &
        (embargo_df['embargo_end'].notna()) &
        (embargo_df['embargo_start'] <= today) &
        (embargo_df['embargo_end'] >= today)
    )
    return embargo_df[mask].to_dict('records')


def format_embargo_status(embargoes: list) -> str:
    """Format embargo list into a single display string."""
    if not embargoes:
        return "🟢 Available"
    today = pd.Timestamp.now().normalize()
    parts = []
    for e in embargoes:
        end = e.get('embargo_end')
        student = e.get('researcher_name', '?')
        project = e.get('project_title', '?')
        days_left = int((end - today).days) if pd.notna(end) else None
        if days_left is not None and days_left <= EXPIRING_SOON_DAYS:
            icon = "🟡"
            end_str = f"until {end.strftime('%y-%m-%d')} ({days_left}d)"
        else:
            icon = "🔴"
            end_str = f"until {end.strftime('%y-%m-%d')}" if pd.notna(end) else "?"
        parts.append(f"{icon} {student} — {project} ({end_str})")
    return "\n".join(parts)


# ── Session state ──────────────────────────────────────────────────────────────

def init_session_state():
    defaults = {'authenticated': False, 'username': '', 'password': ''}
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


# ── EarthRanger client ────────────────────────────────────────────────────────

@st.cache_resource
def get_er_client(username, password):
    return EarthRangerIO(server=ER_SERVER, username=username, password=password)


# ── Authentication ────────────────────────────────────────────────────────────

def er_login(username, password):
    try:
        er = get_er_client(username, password)
        er.get_subjectgroups(flat=True)
        return True
    except Exception:
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
    er = get_er_client(username, password)
    return er.get_subjects(subject_group_id=group_id, include_inactive=True)


@st.cache_data(ttl=3600)
def load_subject_sources_raw(username, password, subject_id):
    er = get_er_client(username, password)
    try:
        result = er.get_subject_sources(subject_id=subject_id)
        if isinstance(result, list):
            return result
        if isinstance(result, pd.DataFrame):
            return result.to_dict('records')
        return []
    except Exception:
        return []


# ── Parse source assignments ──────────────────────────────────────────────────

def _parse_source_assignments(raw_assignments):
    providers = []
    mfr_names = set()
    for item in raw_assignments:
        prov = item.get('provider', '')
        if prov and prov not in EXCLUDED_PROVIDERS:
            providers.append(prov)
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
    for field in ('last_position_date', 'last_observation_date'):
        val = subject.get(field)
        if val:
            return val
    return None


def _total_days(start_val, end_val):
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


# ── Build per-subject detail rows ─────────────────────────────────────────────

def build_detail_rows(group_name, subjects_df, username, password, load_mfr, embargo_df):
    embargo_status = format_embargo_status(get_active_embargoes(group_name, embargo_df))
    rows = []
    for _, subject in subjects_df.iterrows():
        sid          = str(subject.get('id', ''))
        last_fix     = _last_fix_from_subject(subject)
        is_active    = bool(subject.get('is_active', False))
        deploy_start = subject.get('created_at')
        sex          = (subject.get('sex') or '').strip()

        if is_active:
            deploy_end_fmt = "Active"
            end_for_days   = last_fix
        else:
            end_date       = last_fix or subject.get('updated_at')
            deploy_end_fmt = _fmt_date(end_date)
            end_for_days   = end_date

        days = _total_days(deploy_start, end_for_days)

        base = {
            'Subject':      subject.get('name', sid),
            'Group':        group_name,
            'Sex':          sex,
            'Active':       is_active,
            'Deploy Start': _fmt_date(deploy_start),
            'Deploy End':   deploy_end_fmt,
            'Last Fix':     _fmt_date(last_fix),
            'Total Days':   days,
            'Embargo':      embargo_status,
        }

        if load_mfr:
            raw = load_subject_sources_raw(username, password, sid)
            if raw:
                for item in raw:
                    prov       = item.get('provider', '')
                    additional = item.get('additional') or {}
                    collar_mfr = additional.get('collar_manufacturer', '').strip()
                    if collar_mfr:
                        mfr = collar_mfr
                    elif prov and prov not in EXCLUDED_PROVIDERS:
                        mfr = MANUFACTURER_DISPLAY.get(prov, prov)
                    else:
                        mfr = prov
                    rows.append({**base, 'Manufacturer': mfr})
            else:
                rows.append({**base, 'Manufacturer': ''})
        else:
            rows.append(base)

    return rows


# ── Summary table builder ─────────────────────────────────────────────────────

def build_summary_row(group_name, subjects_df, username, password, load_mfr, embargo_df):
    deploy_starts     = []
    last_fixes        = []
    all_manufacturers = set()
    has_active        = False

    for _, subject in subjects_df.iterrows():
        sid       = str(subject.get('id', ''))
        is_active = bool(subject.get('is_active', False))
        if is_active:
            has_active = True

        created = subject.get('created_at')
        if created:
            try:
                deploy_starts.append(pd.to_datetime(created))
            except Exception:
                pass

        lf = _last_fix_from_subject(subject)
        if lf:
            try:
                last_fixes.append(pd.to_datetime(lf))
            except Exception:
                pass

        if load_mfr:
            raw = load_subject_sources_raw(username, password, sid)
            _, mfr = _parse_source_assignments(raw)
            if mfr:
                all_manufacturers.add(mfr)

    n_active = int(subjects_df['is_active'].sum()) if 'is_active' in subjects_df.columns else "?"

    if 'sex' in subjects_df.columns:
        sex_counts = subjects_df['sex'].fillna('').str.strip().str.upper().value_counts()
        parts = []
        for code, label in [('MALE', 'M'), ('FEMALE', 'F'), ('M', 'M'), ('F', 'F')]:
            if code in sex_counts and label not in [p[-1] for p in parts]:
                parts.append(f"{sex_counts[code]}{label}")
        sex_summary = " / ".join(parts) if parts else "—"
    else:
        sex_summary = "—"

    data_start = min(deploy_starts) if deploy_starts else None
    data_end   = max(last_fixes)   if last_fixes   else None

    if has_active:
        deploy_end = "Active"
    elif data_end:
        deploy_end = _fmt_date(data_end)
    else:
        deploy_end = ""

    # Embargo summary for this group
    active_embargoes = get_active_embargoes(group_name, embargo_df)
    embargo_status   = format_embargo_status(active_embargoes)

    return {
        'Group':         group_name,
        'Subjects':      len(subjects_df),
        'Active':        n_active,
        'Sex':           sex_summary,
        'Data Start':    _fmt_date(data_start),
        'Data End':      _fmt_date(data_end),
        'Total Days':    _total_days(data_start, data_end),
        'Deploy Start':  _fmt_date(data_start),
        'Deploy End':    deploy_end,
        'Manufacturers': ", ".join(sorted(all_manufacturers)) if all_manufacturers else ("—" if not load_mfr else ""),
        'Embargo':       embargo_status,
    }


# ── Embargo sidebar section ───────────────────────────────────────────────────

def render_embargo_sidebar() -> pd.DataFrame:
    """
    Render the embargo sheet config in the sidebar.
    Returns the loaded embargo DataFrame (empty if not configured / failed).
    """
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📋 Embargo Registry")

    config   = load_embargo_config()
    saved_url = config.get("sheet_url", "")

    with st.sidebar.expander("⚙️ Configure sheet URL", expanded=(not saved_url)):
        st.markdown(
            "Paste your **Google Sheet URL** (shared with *Anyone with the link*).\n\n"
            "The tab must be named **`data_embargo`**."
        )
        new_url = st.text_input(
            "Google Sheet URL",
            value=saved_url,
            placeholder="https://docs.google.com/spreadsheets/d/...",
            label_visibility="collapsed",
        )
        col1, col2 = st.columns(2)
        if col1.button("💾 Save", use_container_width=True):
            if save_embargo_config(new_url.strip()):
                st.success("Saved!")
                st.rerun()
            else:
                st.error("Could not save config.")
        if col2.button("🗑️ Clear", use_container_width=True):
            save_embargo_config("")
            st.rerun()

    sheet_url = saved_url  # use saved; new_url only takes effect after Save+rerun

    if not sheet_url:
        st.sidebar.info("No embargo sheet configured.")
        return pd.DataFrame()

    try:
        embargo_df = load_embargo_data(sheet_url)
        n = len(embargo_df)
        today = pd.Timestamp.now().normalize()
        n_active = 0
        if not embargo_df.empty and 'embargo_end' in embargo_df.columns:
            n_active = int(
                (embargo_df['embargo_end'].notna() & (embargo_df['embargo_end'] >= today)).sum()
            )
        st.sidebar.success(f"{n} record(s) loaded · {n_active} active embargo(s)")
        if st.sidebar.button("🔄 Refresh embargo data"):
            load_embargo_data.clear()
            st.rerun()
        return embargo_df
    except Exception as e:
        st.sidebar.error(f"Could not load sheet: {e}")
        return pd.DataFrame()


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

    # Sidebar — auth
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

    # Sidebar — embargo registry
    embargo_df = render_embargo_sidebar()

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

    # ── Load subjects ─────────────────────────────────────────────────────────
    all_subjects = {}
    with st.spinner("Loading subjects..."):
        for group in selected_groups:
            try:
                group_id = name_to_id.get(group)
                df = load_subjects_for_group(username, password, group_id if group_id else group)
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
                build_summary_row(group_name, subjects_df, username, password, load_mfr, embargo_df)
            )

    summary_df = pd.DataFrame(summary_rows)
    if not load_mfr:
        summary_df = summary_df.drop(columns=['Manufacturers'], errors='ignore')

    st.dataframe(summary_df, use_container_width=True, hide_index=True)

    # ── Embargo overview (if sheet is loaded) ─────────────────────────────────
    required_cols = {'group', 'embargo_start', 'embargo_end'}
    if not embargo_df.empty and not required_cols.issubset(embargo_df.columns):
        st.warning(
            f"⚠️ Embargo sheet is missing expected columns. "
            f"Found: `{list(embargo_df.columns)}`. "
            f"Check that the published URL points to the **data_embargo** tab specifically, not the entire document."
        )
    if not embargo_df.empty and 'embargo_end' in embargo_df.columns:
        today = pd.Timestamp.now().normalize()
        active_all = embargo_df[
            embargo_df['embargo_end'].notna() & (embargo_df['embargo_end'] >= today)
        ].copy()

        if not active_all.empty:
            st.markdown("---")
            st.subheader("🔴 Active Embargoes")
            display_cols = [c for c in
                ['group', 'project_title', 'researcher_name', 'researcher_institution',
                 'embargo_start', 'embargo_end', 'dsa_id', 'zotero_link', 'gqueues_link', 'notes']
                if c in active_all.columns]
            active_display = active_all[display_cols].copy()
            for col in ('embargo_start', 'embargo_end'):
                if col in active_display.columns:
                    active_display[col] = active_display[col].dt.strftime('%Y-%m-%d')
            active_display.columns = [c.replace('_', ' ').title() for c in active_display.columns]
            link_cols = {
                col: st.column_config.LinkColumn(col, display_text="Open")
                for col in ('Zotero Link', 'Gqueues Link')
                if col in active_display.columns
            }
            st.dataframe(active_display, use_container_width=True, hide_index=True,
                         column_config=link_cols or None)

    # ── Detailed subject table ────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("📋 Subject Detail")

    detail_rows = []
    with st.spinner("Loading per-subject deployment details…"):
        for group_name, subjects_df in all_subjects.items():
            detail_rows.extend(
                build_detail_rows(group_name, subjects_df, username, password, load_mfr, embargo_df)
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
