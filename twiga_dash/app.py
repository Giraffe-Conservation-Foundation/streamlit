"""
Twiga Dash — GPS Subject Tracking Dashboard
Provides a live summary of all GPS-collared giraffe subjects in EarthRanger.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timezone, timedelta
from ecoscope.io.earthranger import EarthRangerIO

# ─── Constants ────────────────────────────────────────────────────────────────
ER_SERVER = "https://twiga.pamdas.org"

# Subject group filtering — mirrors life_history_dashboard logic.
# NOTE: 'twiga' intentionally omitted from skip words here because this server
# IS twiga.pamdas.org — almost every group name contains 'twiga', adding it
# would skip everything and fall back to showing all 1433 subjects.
GROUP_SKIP_PREFIXES = ("AF_",)
GROUP_SKIP_EXACT    = {"New_subjects"}
GROUP_SKIP_WORDS    = ("people", "donor", "wildscape", "adopt", "alive", "movebank")

# Groups whose subjects must be HARD-EXCLUDED regardless of other group membership.
# Use this for groups that should never appear in the dashboard (e.g. non-GCF populations).
GROUP_HARD_EXCLUDE = {"NAM_NANW"}

# Subject type to include — everything else (people, vehicles, etc.) is excluded
GIRAFFE_SUBJECT_SUBTYPE = "giraffe"

# Species colour palette — accent: GCF orange #DB580F + complementary hues
SUBSPECIES_COLORS = {
    "peralta":        "#DB0F0F",
    "antiquorum":     "#9A392B",
    "camelopardalis": "#E6751A",
    "reticulata":     "#C41697",
    "tippelskirchi":  "#216DCC",
    "thornicrofti":   "#5BAED9",
    "giraffa":        "#4D9C2C",
    "angolensis":     "#457132",
    "unknown":        "#888888",
}

SPECIES_LABELS = {
    "peralta":        "G. c. peralta",
    "antiquorum":     "G. c. antiquorum",
    "camelopardalis": "G. c. camelopardalis",
    "reticulata":     "G. reticulata",
    "tippelskirchi":  "G. t. tippelskirchi",
    "thornicrofti":   "G. t. thornicrofti",
    "giraffa":        "G. g. giraffa",
    "angolensis":     "G. g. angolensis",
    "unknown":        "Unknown",
}
# Keep old name as alias so internal references don't break during transition
SUBSPECIES_LABELS = SPECIES_LABELS

# ─── CSS & Styling ─────────────────────────────────────────────────────────────
DASHBOARD_CSS = """
<style>
/* ── Hero banner ── */
.twiga-hero {
    background: linear-gradient(135deg, #1a0b04 0%, #5c2308 45%, #9b3b07 100%);
    border-radius: 16px;
    padding: 2.2rem 2.8rem 1.8rem 2.8rem;
    margin-bottom: 1.6rem;
    position: relative;
    overflow: hidden;
}
.twiga-hero::before {
    content: "🦒";
    font-size: 9rem;
    position: absolute;
    right: 2rem;
    top: 50%;
    transform: translateY(-50%);
    opacity: 0.12;
}
.twiga-hero h1 {
    color: #f0f4f8;
    font-size: 2.4rem;
    font-weight: 800;
    margin: 0 0 0.3rem 0;
    letter-spacing: -0.5px;
}
.twiga-hero p {
    color: #f0b98a;
    font-size: 1.05rem;
    margin: 0;
}

/* ── Metric cards ── */
.metric-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 1rem;
    margin-bottom: 1.4rem;
}
.metric-card {
    background: linear-gradient(145deg, #1e293b, #0f172a);
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 1.2rem 1.4rem;
    position: relative;
    overflow: hidden;
}
.metric-card::before {
    content: "";
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: var(--accent, #DB580F);
    border-radius: 12px 12px 0 0;
}
.metric-label {
    color: #94a3b8;
    font-size: 0.78rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.35rem;
}
.metric-value {
    color: #f1f5f9;
    font-size: 2rem;
    font-weight: 800;
    line-height: 1;
}
.metric-sub {
    color: #64748b;
    font-size: 0.75rem;
    margin-top: 0.25rem;
}

/* ── Section headers ── */
.section-header {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    border-bottom: 2px solid #7a2e06;
    padding-bottom: 0.5rem;
    margin: 1.4rem 0 1rem 0;
}
.section-header h3 {
    color: #e2e8f0;
    font-size: 1.15rem;
    font-weight: 700;
    margin: 0;
}

/* ── Subspecies pill ── */
.subsp-pill {
    display: inline-block;
    padding: 0.18rem 0.65rem;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 600;
    color: white;
    margin: 2px;
}

/* ── Status badge ── */
.status-active   { color: #22c55e; font-weight: 700; }
.status-inactive { color: #f87171; font-weight: 700; }

/* ── Last-seen colour coding ── */
.lastseen-fresh  { color: #4ade80; }
.lastseen-warn   { color: #fbbf24; }
.lastseen-old    { color: #f87171; }

/* ── Login card ── */
.login-card {
    background: linear-gradient(145deg, #0f172a, #1e293b);
    border: 1px solid #334155;
    border-radius: 16px;
    padding: 2.5rem;
    max-width: 480px;
    margin: 3rem auto;
}
.login-card h2 {
    color: #f1f5f9;
    font-size: 1.5rem;
    font-weight: 800;
    margin-bottom: 0.5rem;
}
.login-card p { color: #94a3b8; margin-bottom: 1.5rem; }
</style>
"""


# ─── Session state helpers ─────────────────────────────────────────────────────

def init_session_state():
    defaults = {
        "td_authenticated": False,
        "td_username": "",
        "td_password": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ─── EarthRanger auth ─────────────────────────────────────────────────────────

def er_connect(username: str, password: str):
    """Connect to EarthRanger and return connection object, or None on failure."""
    try:
        er_io = EarthRangerIO(
            server=ER_SERVER,
            username=username,
            password=password,
        )
        er_io.get_sources(limit=1)   # cheap connection test
        return er_io
    except Exception as e:
        st.error(f"❌ Connection failed: {e}")
        return None


def render_login():
    """Render EarthRanger login form."""
    st.markdown(DASHBOARD_CSS, unsafe_allow_html=True)

    st.markdown("""
    <div class="login-card">
        <h2>🔐 Connect to EarthRanger</h2>
        <p>Enter your credentials to load the Twiga Dash.</p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("td_auth_form"):
        st.info(f"**Server:** {ER_SERVER}")
        username = st.text_input("Username", value=st.session_state.td_username)
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("🔌 Connect to EarthRanger", type="primary", use_container_width=True)

        if submitted:
            if not username or not password:
                st.error("Username and password are required.")
                return
            with st.spinner("Authenticating…"):
                er_io = er_connect(username, password)
            if er_io:
                st.session_state.td_authenticated = True
                st.session_state.td_username = username
                st.session_state.td_password = password
                st.success("✅ Connected!")
                st.rerun()


# ─── Data fetching ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=900, show_spinner=False)
def fetch_subjects(_username: str, _password: str) -> pd.DataFrame:
    """Fetch subjects from EarthRanger.

    Mirrors the life_history_dashboard approach:
    - Load all subjects
    - Fetch subject groups and build a subject_id -> group_names map
    - Store the group label on each row + debug info
    - Filter to subjects that belong to at least one valid (non-noise) group
      so we exclude people, vehicles, utility subjects, etc.
    """
    er_io = EarthRangerIO(server=ER_SERVER, username=_username, password=_password)
    debug_lines: list[str] = []

    # 1. Subjects
    try:
        df = er_io.get_subjects(include_inactive=True)
    except TypeError:
        df = er_io.get_subjects()

    if df is None or df.empty:
        return pd.DataFrame()

    df = df.reset_index(drop=True)
    debug_lines.append(f"Raw subjects loaded: {len(df)}")
    debug_lines.append(f"Columns: {list(df.columns)}")

    # ── Filter to giraffe subjects only ──────────────────────────────────────
    if "subject_subtype" in df.columns:
        before_filt = len(df)
        df = df[df["subject_subtype"].astype(str).str.lower() == GIRAFFE_SUBJECT_SUBTYPE]
        df = df.reset_index(drop=True)
        debug_lines.append(
            f"After subject_subtype=='{GIRAFFE_SUBJECT_SUBTYPE}' filter: "
            f"{len(df)} subjects (was {before_filt})"
        )
    else:
        debug_lines.append("subject_subtype column not present — cannot filter to giraffe")

    if df.empty:
        return pd.DataFrame()

    # Sample a subject to inspect key fields
    if len(df) > 0:
        sample = df.iloc[0].to_dict()
        for field in ("subject_subtype", "common_name", "assigned_range", "additional",
                       "last_position_date", "tracks_available", "is_active"):
            debug_lines.append(f"  sample['{field}'] = {repr(sample.get(field))[:200]}")

    # 2. Subject groups
    group_map: dict[str, list[str]] = {}  # subject_id -> [group_name, ...]
    excluded_subject_ids: set[str] = set()
    try:
        raw_groups = er_io._get(
            "subjectgroups/",
            params={"flat": True, "include_inactive": True, "include_hidden": True},
        )
        debug_lines.append(
            f"subjectgroups/ returned type={type(raw_groups).__name__}, "
            f"count={len(raw_groups) if isinstance(raw_groups, list) else '?'}"
        )
        if isinstance(raw_groups, list) and raw_groups:
            first = raw_groups[0]
            debug_lines.append(f"First group keys: {list(first.keys()) if isinstance(first, dict) else type(first)}")
            if isinstance(first, dict):
                debug_lines.append(f"First group name='{first.get('name')}', subjects={len(first.get('subjects', []))}")

        if isinstance(raw_groups, list):
            skipped_groups, included_groups = [], []
            # Build hard-exclude set first: subjects in these groups are always removed
            for grp in raw_groups:
                if not isinstance(grp, dict):
                    continue
                grp_nm = grp.get("name") or ""
                if any(grp_nm == excl or grp_nm.startswith(excl + "_") or grp_nm.startswith(excl)
                       for excl in GROUP_HARD_EXCLUDE):
                    for member in (grp.get("subjects") or []):
                        sid = str(member.get("id") if isinstance(member, dict) else member)
                        if sid:
                            excluded_subject_ids.add(sid)
            debug_lines.append(f"Hard-excluded subjects (NAM_NANW etc.): {len(excluded_subject_ids)}")

            for grp in raw_groups:
                if not isinstance(grp, dict):
                    continue
                grp_name = grp.get("name") or ""
                if (
                    any(grp_name.startswith(p) for p in GROUP_SKIP_PREFIXES)
                    or grp_name in GROUP_SKIP_EXACT
                    or any(grp_name == excl or grp_name.startswith(excl + "_") or grp_name.startswith(excl)
                           for excl in GROUP_HARD_EXCLUDE)
                    or any(w in grp_name.lower() for w in GROUP_SKIP_WORDS)
                ):
                    skipped_groups.append(grp_name)
                    continue
                included_groups.append(grp_name)
                for member in (grp.get("subjects") or []):
                    sid = str(member.get("id") if isinstance(member, dict) else member)
                    if sid:
                        group_map.setdefault(sid, [])
                        if grp_name not in group_map[sid]:
                            group_map[sid].append(grp_name)
            debug_lines.append(f"Groups included ({len(included_groups)}): {included_groups[:10]}")
            debug_lines.append(f"Groups skipped  ({len(skipped_groups)}): {skipped_groups[:10]}")
            debug_lines.append(f"Subjects mapped to a valid group: {len(group_map)}")
    except Exception as exc:
        debug_lines.append(f"subjectgroups/ FAILED: {exc}")
        # excluded_subject_ids stays as the empty set initialised above

    # 3. Attach group label to each subject row
    df["subject_group_label"] = df["id"].astype(str).apply(
        lambda sid: ", ".join(group_map.get(sid, [])) or "— No group —"
    )
    df["_group_debug"] = "\n".join(debug_lines)

    # 4. Hard-exclude NAM_NANW (and any other GROUP_HARD_EXCLUDE) subjects
    if excluded_subject_ids:
        before_excl = len(df)
        df = df[~df["id"].astype(str).isin(excluded_subject_ids)]
        debug_lines.append(f"After hard-exclusion: {len(df)} subjects (removed {before_excl - len(df)})")

    # 5. Filter: keep only subjects that appear in at least one valid group
    before = len(df)
    if group_map:                 # only filter if we actually got group data
        df = df[df["subject_group_label"] != "— No group —"]
    debug_lines.append(f"After group filter: {len(df)} subjects (was {before})")

    # 6. Deduplicate — a subject may appear in multiple valid groups, causing
    #    duplicate rows. Keep the first occurrence (group label already attached).
    before_dedup = len(df)
    df = df.drop_duplicates(subset=["id"])
    debug_lines.append(f"After dedup on id: {len(df)} subjects (removed {before_dedup - len(df)} dupes)")

    # Update debug with final result
    df["_group_debug"] = "\n".join(debug_lines)

    return df.reset_index(drop=True)


def _parse_assigned_range(assigned_range) -> tuple:
    """Extract (start_dt, end_dt) from an assigned_range value.

    The ER REST API returns assigned_range as a dict:
      {'start_time': <iso>, 'end_time': <iso|null>}
    When delivered via the ecoscope SDK the same dict may come through
    serialised as-is, or the field may simply be absent from the DataFrame.
    Also handles JSONB half-open ranges stored as 'lower'/'upper'.
    Returns (start_dt | None, end_dt | None).
    """
    if assigned_range is None:
        return None, None
    # If it came through as a string (JSON-encoded dict)
    if isinstance(assigned_range, str):
        try:
            import json as _json
            assigned_range = _json.loads(assigned_range)
        except Exception:
            return None, None
    if not isinstance(assigned_range, dict):
        return None, None
    start_raw = assigned_range.get("start_time") or assigned_range.get("lower")
    end_raw   = assigned_range.get("end_time")   or assigned_range.get("upper")
    start_dt = pd.to_datetime(start_raw, utc=True, errors="coerce") if start_raw else None
    end_dt   = pd.to_datetime(end_raw,   utc=True, errors="coerce") if end_raw   else None
    # Treat NaT as None
    if start_dt is not None and pd.isna(start_dt):
        start_dt = None
    if end_dt is not None and pd.isna(end_dt):
        end_dt = None
    return start_dt, end_dt


def _try_parse_dt(val) -> "pd.Timestamp | None":
    """Best-effort parse of any datetime-like value to a UTC Timestamp."""
    if val is None:
        return None
    try:
        result = pd.to_datetime(val, utc=True, errors="coerce")
        return None if pd.isna(result) else result
    except Exception:
        return None


# Common EarthRanger naming patterns for each species key.
# Primary source is 'common_name' — values from the Twiga ER instance are
# underscore-separated strings like 'Masai_Masai', 'Reticulated', etc.
# Aliases cover those exact values as well as slug/display-name variants.
_SPECIES_ALIASES: dict[str, list[str]] = {
    "peralta":        ["northern_westafrican", "westafrican", "west african", "peralta", "niger"],
    "antiquorum":     ["northern_kordofan", "kordofan", "antiquorum"],
    "camelopardalis": ["northern_nubian", "nubian", "rothschild", "camelopardalis"],
    "reticulata":     ["reticulated", "reticulata"],
    "tippelskirchi":  ["masai_masai", "tippelskirchi", "tippel", "maasai"],
    "thornicrofti":   ["masai_luangwa", "luangwa", "thornicrofti", "thornicroft"],
    "giraffa":        ["southern_southafrican", "southafrican", "south african", "giraffa"],
    "angolensis":     ["southern_angolan", "angolensis", "angolan", "namibian"],
}


def _match_species_key(text: str) -> str | None:
    """Return the species key if text matches any alias, else None."""
    t = text.strip().lower()
    if not t:
        return None
    for key, aliases in _SPECIES_ALIASES.items():
        for alias in aliases:
            if alias in t:
                return key
    return None


def _extract_species(row) -> str:
    """Extract species from a subject row.

    Priority order:
      1. common_name     — EarthRanger stores the subspecies display name here
                           e.g. 'Masai Giraffe', 'Reticulated Giraffe'
      2. subject_subtype — may hold slug like 'giraffe_tippelskirchi'
      3. additional dict — custom admin fields
      4. Name heuristic  — last resort
    """
    # 1. common_name — preferred source
    cn = str(row.get("common_name") or "")
    m = _match_species_key(cn)
    if m:
        return m

    # 2. subject_subtype slug
    st_type = str(row.get("subject_subtype") or "")
    m = _match_species_key(st_type)
    if m:
        return m

    # 3. additional dict — custom fields added by the ER admin
    additional = row.get("additional") or {}
    if isinstance(additional, dict):
        for key_name in ("subspecies", "Subspecies", "species", "Species",
                          "sub_species", "taxon", "type", "common_name"):
            val = str(additional.get(key_name) or "")
            m = _match_species_key(val)
            if m:
                return m

    # 4. Subject name heuristic
    name = str(row.get("name") or "")
    m = _match_species_key(name)
    if m:
        return m

    return "unknown"


# Keep old name as alias
_extract_subspecies = _extract_species


def _last_position(row):
    """Return (lat, lon) from last_position field or None, None."""
    lp = row.get("last_position")
    if isinstance(lp, dict):
        coords = lp.get("geometry", {}).get("coordinates") or lp.get("coordinates")
        if coords and len(coords) >= 2:
            return coords[1], coords[0]   # lat, lon
    # GeoJSON geometry directly stored as last_position
    if hasattr(lp, "y") and hasattr(lp, "x"):
        return float(lp.y), float(lp.x)
    return None, None


def build_summary_df(raw: pd.DataFrame) -> tuple:
    """Transform raw subjects DataFrame into (summary_df, debug_lines)."""
    if raw.empty:
        return pd.DataFrame(), ["raw df is empty"]

    rows = []
    now = datetime.now(tz=timezone.utc)

    # ── Per-dataset debug — collect once before the loop ──
    debug: list[str] = []
    cols = list(raw.columns)
    debug.append(f"Subject columns ({len(cols)}): {cols}")

    # Show unique subject_subtype values for reference
    if "subject_subtype" in raw.columns:
        unique_subtypes = raw["subject_subtype"].dropna().unique().tolist()[:30]
        debug.append(f"subject_subtype unique values: {unique_subtypes}")
    else:
        debug.append("subject_subtype column NOT present")

    # Show unique common_name values — this is the primary species source
    if "common_name" in raw.columns:
        unique_cn = raw["common_name"].dropna().unique().tolist()[:30]
        debug.append(f"common_name unique values: {unique_cn}")
    else:
        debug.append("common_name column NOT present — will fall back to subject_subtype / additional")

    # Show what assigned_range looks like for the first subject that has it
    if "assigned_range" in raw.columns:
        sample_ar = raw["assigned_range"].dropna().head(3).tolist()
        debug.append(f"assigned_range samples: {[repr(x)[:300] for x in sample_ar]}")
    else:
        debug.append("assigned_range column NOT present")
        # List any date-like columns that might hold deployment times
        date_cols = [c for c in cols if any(w in c.lower() for w in
                     ("date", "time", "start", "deploy", "collar"))]
        debug.append(f"Date-like columns available: {date_cols}")

    # Sample the 'additional' field to spot custom date/species fields
    if "additional" in raw.columns:
        sample_add = raw["additional"].dropna().head(3).tolist()
        debug.append(f"additional field samples: {[repr(x)[:300] for x in sample_add]}")

    for _, row in raw.iterrows():
        is_active = bool(row.get("tracks_available", False)) or bool(row.get("is_active", False))

        # ── Tracking hours ──
        # Primary: assigned_range field (ER REST API deployment record)
        start_dt, end_dt = _parse_assigned_range(row.get("assigned_range"))

        # Fallback 1: additional dict may hold deployment dates
        if start_dt is None:
            additional = row.get("additional") or {}
            if isinstance(additional, dict):
                for k in ("deployment_start", "collar_start", "date_start",
                           "start_date", "date_of_deployment"):
                    v = additional.get(k)
                    if v:
                        start_dt = _try_parse_dt(v)
                        if start_dt:
                            break

        # Fallback 2: date columns on the subject row itself
        if start_dt is None:
            for col in ("date_added", "created_at", "date_birth"):
                v = row.get(col)
                if v:
                    start_dt = _try_parse_dt(v)
                    if start_dt:
                        break

        if start_dt is not None:
            if end_dt is not None and end_dt < now:
                effective_end = end_dt        # deployment finished
            else:
                effective_end = now           # still deployed
            tracking_hours = max((effective_end - start_dt).total_seconds() / 3600, 0)
        else:
            tracking_hours = 0.0

        # ── Last position ──
        last_pos_date = row.get("last_position_date")
        lp_dt = _try_parse_dt(last_pos_date)
        days_since = (now - lp_dt).total_seconds() / 86400 if lp_dt else None

        lat, lon = _last_position(row)

        rows.append({
            "id":              row.get("id", ""),
            "name":            row.get("name", "Unknown"),
            "is_active":       is_active,
            "subspecies":      _extract_species(row),
            "common_name":     str(row.get("common_name") or ""),
            "subject_subtype": str(row.get("subject_subtype") or ""),
            "subject_group":   str(row.get("subject_group_label") or ""),
            "start_dt":        start_dt,
            "end_dt":          end_dt,
            "tracking_hours":  round(tracking_hours, 1),
            "tracking_days":   round(tracking_hours / 24, 1),
            "last_pos_date":   last_pos_date,
            "days_since":      round(days_since, 1) if days_since is not None else None,
            "lat":             lat,
            "lon":             lon,
        })

    return pd.DataFrame(rows), debug


# ─── Chart helpers ─────────────────────────────────────────────────────────────

def _card(col, label: str, value: str, sub: str = "", accent: str = "#DB580F"):
    col.markdown(
        f"""
        <div class="metric-card" style="--accent:{accent}">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-sub">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def chart_subspecies_bar(df: pd.DataFrame) -> go.Figure:
    """Horizontal bar chart: subjects per species."""
    counts = (
        df.groupby("subspecies")
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=True)
    )
    counts["label"] = counts["subspecies"].map(SPECIES_LABELS).fillna(counts["subspecies"])
    counts["color"] = counts["subspecies"].map(SUBSPECIES_COLORS).fillna("#888")

    fig = go.Figure(go.Bar(
        x=counts["count"],
        y=counts["label"],
        orientation="h",
        marker_color=counts["color"],
        text=counts["count"],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Subjects: %{x}<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#cbd5e1"),
        margin=dict(l=10, r=40, t=10, b=10),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, tickfont=dict(size=12)),
        height=max(220, len(counts) * 42),
        bargap=0.35,
    )
    return fig


def chart_tracking_days(df: pd.DataFrame) -> go.Figure:
    """Histogram of tracking duration per subject (days)."""
    fig = go.Figure(go.Histogram(
        x=df[df["tracking_days"] > 0]["tracking_days"],
        nbinsx=20,
        marker=dict(
            color="rgba(219, 88, 15, 0.75)",
            line=dict(color="rgba(219, 88, 15, 1)", width=1),
        ),
        hovertemplate="Duration: %{x:.0f} days<br>Count: %{y}<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#cbd5e1"),
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(
            title=dict(text="Tracking duration (days)", font=dict(size=11)),
            showgrid=False,
        ),
        yaxis=dict(title="Subjects", showgrid=True, gridcolor="#1e293b"),
        height=280,
    )
    return fig


def chart_activity_donut(active: int, inactive: int) -> go.Figure:
    fig = go.Figure(go.Pie(
        labels=["Active", "Inactive"],
        values=[active, inactive],
        hole=0.68,
        marker=dict(colors=["#DB580F", "#ef4444"],
                    line=dict(color="#0f172a", width=2)),
        textinfo="none",
        hovertemplate="%{label}: %{value}<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#cbd5e1"),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.12, x=0.5,
                    xanchor="center", font=dict(size=11)),
        margin=dict(l=10, r=10, t=10, b=20),
        height=220,
        annotations=[dict(
            text=f"<b>{active}</b><br>active",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=18, color="#f1f5f9"),
            xanchor="center", yanchor="middle",
        )],
    )
    return fig


def chart_last_seen_scatter(df: pd.DataFrame) -> go.Figure:
    """Scatter: days since last fix vs tracking days, coloured by species."""
    plot_df = df[df["lat"].notna() & df["days_since"].notna()].copy()
    plot_df["subsp_label"] = plot_df["subspecies"].map(SPECIES_LABELS).fillna(plot_df["subspecies"])
    plot_df["color"] = plot_df["subspecies"].map(SUBSPECIES_COLORS).fillna("#888")

    fig = go.Figure()
    for subsp, grp in plot_df.groupby("subspecies"):
        fig.add_trace(go.Scatter(
            x=grp["tracking_days"],
            y=grp["days_since"],
            mode="markers",
            name=SPECIES_LABELS.get(subsp, subsp),
            marker=dict(
                color=SUBSPECIES_COLORS.get(subsp, "#888"),
                size=9,
                line=dict(width=1, color="white"),
                opacity=0.85,
            ),
            text=grp["name"],
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Tracking: %{x:.0f} days<br>"
                "Days since fix: %{y:.1f}<extra></extra>"
            ),
        ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#cbd5e1"),
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(title="Tracking duration (days)", showgrid=True, gridcolor="#1e293b"),
        yaxis=dict(title="Days since last fix", showgrid=True, gridcolor="#1e293b"),
        height=300,
        legend=dict(font=dict(size=10), bgcolor="rgba(15,23,42,0.7)"),
    )
    return fig


def chart_map(df: pd.DataFrame) -> go.Figure:
    """Plotly Scattermapbox showing last position of all subjects, coloured by subspecies."""
    map_df = df[df["lat"].notna() & df["lon"].notna()].copy()

    if map_df.empty:
        return None

    map_df["subsp_label"]   = map_df["subspecies"].map(SPECIES_LABELS).fillna(map_df["subspecies"])
    map_df["marker_color"]  = map_df["subspecies"].map(SUBSPECIES_COLORS).fillna("#888888")
    map_df["status_text"]   = map_df["is_active"].map({True: "Active ✅", False: "Inactive ❌"})
    map_df["days_since_str"] = map_df["days_since"].apply(
        lambda d: f"{d:.0f} days ago" if pd.notna(d) else "unknown"
    )
    map_df["hover"] = (
        "<b>" + map_df["name"] + "</b><br>"
        + map_df["subsp_label"] + "<br>"
        + map_df["status_text"] + "<br>"
        + "Last fix: " + map_df["days_since_str"] + "<br>"
        + "Tracking: " + map_df["tracking_days"].astype(str) + " days"
    )

    fig = go.Figure()

    for subsp, grp in map_df.groupby("subspecies"):
        color = SUBSPECIES_COLORS.get(subsp, "#888")
        fig.add_trace(go.Scattermapbox(
            lat=grp["lat"],
            lon=grp["lon"],
            mode="markers",
            name=SPECIES_LABELS.get(subsp, subsp),
            marker=go.scattermapbox.Marker(
                size=6,
                color=color,
                opacity=0.88,
            ),
            text=grp["hover"],
            hovertemplate="%{text}<extra></extra>",
        ))

    fig.update_layout(
        mapbox=dict(
            style="carto-darkmatter",
            center=dict(lat=0, lon=22),
            zoom=2.6,
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#cbd5e1"),
        height=580,
        margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(
            bgcolor="rgba(15,23,42,0.85)",
            bordercolor="#334155",
            borderwidth=1,
            font=dict(size=11),
            x=0.01, y=0.99,
            yanchor="top", xanchor="left",
        ),
    )
    return fig


def chart_subspecies_last_seen(df: pd.DataFrame) -> go.Figure:
    """Stacked bar: per-subspecies headcount split into Recent / Ageing / Stale recency bands."""
    plot_df = df[df["days_since"].notna()].copy()

    BANDS = [
        ("Recent (< 7d)",  "#e2e8f0"),   # near-white — most recent stands out
        ("Ageing (7–30d)", "#64748b"),   # mid grey
        ("Stale (> 30d)",  "#334155"),   # dark grey — fades toward background
    ]

    def _band(d: float) -> str:
        if d < 7:   return "Recent (< 7d)"
        if d <= 30: return "Ageing (7–30d)"
        return "Stale (> 30d)"

    plot_df["band"]  = plot_df["days_since"].apply(_band)
    plot_df["label"] = plot_df["subspecies"].map(SPECIES_LABELS).fillna(plot_df["subspecies"])

    # Aggregate counts per species × band
    agg = (
        plot_df.groupby(["label", "band"])
        .size()
        .reset_index(name="count")
    )

    # Sort subspecies so worst (most stale) appear at top
    stale_totals = (
        agg[agg["band"] == "Stale (> 30d)"]
        .groupby("label")["count"].sum()
        .sort_values(ascending=True)   # ascending → most stale at top
    )
    all_labels = agg["label"].unique().tolist()
    ordered = [l for l in all_labels if l not in stale_totals.index] + stale_totals.index.tolist()

    fig = go.Figure()
    for band_name, color in BANDS:
        band_data = agg[agg["band"] == band_name]
        fig.add_trace(go.Bar(
            y=band_data["label"],
            x=band_data["count"],
            name=band_name,
            orientation="h",
            marker_color=color,
            hovertemplate="<b>%{y}</b><br>" + band_name + ": %{x} individuals<extra></extra>",
        ))

    fig.update_layout(
        barmode="stack",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#cbd5e1"),
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(title="Number of individuals", showgrid=True, gridcolor="#1e293b"),
        yaxis=dict(categoryorder="array", categoryarray=ordered, showgrid=False),
        legend=dict(
            orientation="h", yanchor="bottom", y=-0.28, x=0.5,
            xanchor="center", font=dict(size=11),
        ),
        height=max(220, len(plot_df["label"].unique()) * 52 + 100),
    )
    return fig


def chart_subspecies_tracking(df: pd.DataFrame) -> go.Figure:
    """Box plot of tracking days per species."""
    plot_df = df[df["tracking_days"] > 0].copy()
    plot_df["subsp_label"] = plot_df["subspecies"].map(SPECIES_LABELS).fillna(plot_df["subspecies"])

    fig = go.Figure()
    for subsp, grp in plot_df.groupby("subspecies"):
        fig.add_trace(go.Box(
            x=grp["tracking_days"],
            name=SPECIES_LABELS.get(subsp, subsp),
            marker_color=SUBSPECIES_COLORS.get(subsp, "#888"),
            orientation="h",
            boxmean="sd",
            hovertemplate="<b>%{x:.0f} days</b><extra></extra>",
        ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#cbd5e1"),
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(title="Tracking days", showgrid=True, gridcolor="#1e293b"),
        yaxis=dict(showgrid=False),
        height=max(200, len(plot_df["subspecies"].unique()) * 50 + 60),
        showlegend=False,
    )
    return fig


# ─── Main dashboard UI ─────────────────────────────────────────────────────────

def _last_seen_class(days_since):
    if days_since is None:
        return "lastseen-old"
    if days_since < 3:
        return "lastseen-fresh"
    if days_since < 10:
        return "lastseen-warn"
    return "lastseen-old"


def render_dashboard():
    st.markdown(DASHBOARD_CSS, unsafe_allow_html=True)

    # ── Hero ──────────────────────────────────────────────────────────────────
    st.markdown("""
    <div class="twiga-hero">
        <h1>🦒 Twiga Dash</h1>
        <p>Live GPS tracking summary for all collared giraffe subjects in EarthRanger</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Sidebar controls ──────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### ⚙️ Controls")
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        if st.button("🔓 Logout", use_container_width=True):
            st.session_state.td_authenticated = False
            st.rerun()
        st.markdown("---")
        show_inactive = st.checkbox("Include inactive subjects", value=True)
        st.markdown("---")
        st.markdown(f"**Server:** `{ER_SERVER}`")
        st.markdown(f"**User:** `{st.session_state.td_username}`")
        st.markdown(f"*Data refreshes every 15 min*")

    # ── Load data ─────────────────────────────────────────────────────────────
    with st.spinner("📡 Loading subjects from EarthRanger…"):
        try:
            raw_df = fetch_subjects(
                st.session_state.td_username,
                st.session_state.td_password,
            )
        except Exception as e:
            st.error(f"Failed to load subjects: {e}")
            return

    if raw_df is None or raw_df.empty:
        st.warning("No subjects returned from EarthRanger.")
        return

    summary, build_debug = build_summary_df(raw_df)

    # Strip subjects with no recognised subspecies
    summary = summary[summary["subspecies"] != "unknown"].copy()

    if not show_inactive:
        summary = summary[summary["is_active"]]

    active_df   = summary[summary["is_active"]]
    inactive_df = summary[~summary["is_active"]]

    total              = len(summary)
    n_active           = len(active_df)
    n_inactive         = len(inactive_df)
    n_subspecies       = summary["subspecies"].nunique()
    total_hours        = summary["tracking_hours"].sum()
    total_days         = total_hours / 24
    avg_tracking_days  = summary[summary["tracking_days"] > 0]["tracking_days"].mean()
    subjects_with_fix  = summary["lat"].notna().sum()

    # ── KPI cards ─────────────────────────────────────────────────────────────
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    _card(c1, "Total Subjects",    str(total),             f"{subjects_with_fix} with GPS fix",  "#DB580F")
    _card(c2, "Active",            str(n_active),          "currently transmitting",             "#22c55e")
    _card(c3, "Inactive",          str(n_inactive),        "no recent signal",                   "#f87171")
    _card(c4, "Giraffe Subspecies", str(n_subspecies),      "represented",                        "#F0884B")
    _card(c5, "Total Tracking",    f"{int(total_days):,}d", f"≈ {int(total_hours/1000):,}k hrs",  "#DB580F")
    _card(c6, "Avg Deployment",    f"{avg_tracking_days:.0f}d" if not np.isnan(avg_tracking_days) else "—",
          "per subject",                                                                          "#A33D08")

    st.markdown("---")

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab_map, tab_subjects = st.tabs([
        "🗺️ Map & Overview",
        "📋 Subject Table",
    ])

    # ══════════════════════════════════════════════════════════════════════════
    with tab_map:
        # ── Map ───────────────────────────────────────────────────────────────
        st.markdown("""
        <div class="section-header">
            <h3>🗺️ Last Known Position of All Subjects</h3>
        </div>
        """, unsafe_allow_html=True)

        col_map, col_map_chart = st.columns([3, 2])
        with col_map:
            fig_map = chart_map(summary)
            if fig_map:
                st.plotly_chart(fig_map, use_container_width=True, config={"scrollZoom": True})
            else:
                st.info("No georeferenced subjects to display.")

        with col_map_chart:
            st.markdown("""
            <div class="section-header">
                <h3>� Tracking Days by Species</h3>
            </div>
            """, unsafe_allow_html=True)
            st.plotly_chart(chart_subspecies_tracking(summary), use_container_width=True)

        st.markdown("---")

        # ── Quick-facts row ───────────────────────────────────────────────────
        st.markdown("""
        <div class="section-header">
            <h3>📊 Overview & Stats</h3>
        </div>
        """, unsafe_allow_html=True)

        # Derived quick-fact values
        _countries = (
            summary["subject_group"]
            .str.extract(r'^([A-Z]{2,3})_', expand=False)
            .dropna()
            .unique()
        )
        n_countries = len(_countries)

        _longest = summary[summary["tracking_days"] > 0]["tracking_days"].max()
        _longest_name = (
            summary.loc[summary["tracking_days"].idxmax(), "name"]
            if summary["tracking_days"].max() > 0 else "—"
        )

        _most_recent_row = summary[summary["days_since"].notna()].nsmallest(1, "days_since")
        _most_recent_name  = _most_recent_row["name"].values[0] if len(_most_recent_row) else "—"
        _most_recent_days  = _most_recent_row["days_since"].values[0] if len(_most_recent_row) else None
        _most_recent_hrs   = round(_most_recent_days * 24, 1) if _most_recent_days is not None else None

        _avg_deploy = summary[summary["tracking_days"] > 0]["tracking_days"].mean()

        _n_known_subsp   = len(SPECIES_LABELS) - 1   # 8 recognised subspecies (exclude 'unknown')
        _n_represented   = summary[summary["subspecies"] != "unknown"]["subspecies"].nunique()

        fa1, fa2, fa3, fa4, fa5 = st.columns(5)
        _card(fa1, "Countries / Ranges",  str(n_countries),
              "active deployments",                                        "#216DCC")
        _card(fa2, "Longest Deployed",    f"{int(_longest):,}d" if pd.notna(_longest) else "—",
              _longest_name,                                               "#DB0F0F")
        _card(fa3, "Most Recent Fix",
              f"{_most_recent_hrs:.1f} hrs ago" if _most_recent_hrs is not None else "—",
              _most_recent_name,                                           "#22c55e")
        _card(fa4, "Avg Deployment",
              f"{_avg_deploy:.0f}d" if not np.isnan(_avg_deploy) else "—",
              "per individual",                                            "#A33D08")
        _card(fa5, "Subspecies Coverage",   f"{_n_represented} / {_n_known_subsp}",
              "subspecies tracked",                                        "#5BAED9")

        st.markdown("---")

        # ── Charts ────────────────────────────────────────────────────────────
        st.markdown("""
        <div class="section-header">
            <h3>🦒 Subjects per Species</h3>
        </div>
        """, unsafe_allow_html=True)
        st.plotly_chart(chart_subspecies_bar(summary), use_container_width=True)

        st.markdown("""
        <div class="section-header">
            <h3>🕐 Data Recency by Species</h3>
            <p style="color:#94a3b8;font-size:0.85rem;margin:0">
                How recently did each subspecies' collared individuals last transmit a GPS fix?
                &nbsp;<span style="color:#e2e8f0">&#9646;</span> Recent &lt; 7d
                &nbsp;<span style="color:#64748b">&#9646;</span> Ageing 7&ndash;30d
                &nbsp;<span style="color:#475569">&#9646;</span> Stale &gt; 30d
            </p>
        </div>
        """, unsafe_allow_html=True)
        st.plotly_chart(chart_subspecies_last_seen(summary),
                        use_container_width=True)

        # ── Subspecies breakdown table ────────────────────────────────────────
        st.markdown("""
        <div class="section-header">
            <h3>📋 Subspecies Summary</h3>
        </div>
        """, unsafe_allow_html=True)

        subsp_summary = (
            summary.groupby("subspecies")
            .agg(
                Total=("id", "count"),
                Active=("is_active", "sum"),
                Avg_Tracking_Days=("tracking_days", lambda x: round(x[x > 0].mean(), 1) if (x > 0).any() else 0),
                Total_Tracking_Days=("tracking_days", lambda x: round(x.sum(), 0)),
                Total_Tracking_Years=("tracking_hours", lambda x: round(x.sum() / 8760, 1)),
            )
            .reset_index()
        )
        subsp_summary["Label"] = subsp_summary["subspecies"].map(SPECIES_LABELS).fillna(subsp_summary["subspecies"])
        subsp_summary = subsp_summary.rename(columns={
            "Total":               "Total Subjects",
            "Active":              "Active (transmitting)",
            "Avg_Tracking_Days":   "Avg Deploy (days)",
            "Total_Tracking_Days": "Total Deploy (days)",
            "Total_Tracking_Years":"Total Deploy (years)",
        })
        display_cols = ["Label", "Total Subjects", "Active (transmitting)",
                        "Avg Deploy (days)", "Total Deploy (days)", "Total Deploy (years)"]
        st.dataframe(
            subsp_summary[display_cols].rename(columns={"Label": "Species"}),
            use_container_width=True,
            hide_index=True,
        )

    # ══════════════════════════════════════════════════════════════════════════
    with tab_subjects:
        st.markdown("""
        <div class="section-header">
            <h3>📋 All Subject Details</h3>
        </div>
        """, unsafe_allow_html=True)

        # Filter controls
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            subsp_opts = ["All"] + sorted(summary["subspecies"].unique().tolist())
            sel_subsp = st.selectbox("Filter by species", subsp_opts)
        with col_f2:
            status_opts = ["All", "Active", "Inactive"]
            sel_status = st.selectbox("Filter by status", status_opts)
        with col_f3:
            sort_opts = {
                "Name (A→Z)":          ("name", True),
                "Days since fix (↑)":  ("days_since", True),
                "Tracking days (↓)":   ("tracking_days", False),
                "Days since fix (↓)":  ("days_since", False),
            }
            sort_by = st.selectbox("Sort by", list(sort_opts.keys()))

        disp = summary.copy()
        if sel_subsp != "All":
            disp = disp[disp["subspecies"] == sel_subsp]
        if sel_status == "Active":
            disp = disp[disp["is_active"]]
        elif sel_status == "Inactive":
            disp = disp[~disp["is_active"]]
        col_name, asc = sort_opts[sort_by]
        disp = disp.sort_values(col_name, ascending=asc, na_position="last")

        disp_out = disp[[
            "name", "subspecies", "is_active", "tracking_days",
            "tracking_hours", "days_since", "last_pos_date", "lat", "lon"
        ]].copy()
        disp_out["subspecies"]   = disp_out["subspecies"].map(SPECIES_LABELS).fillna(disp_out["subspecies"])
        disp_out["is_active"]    = disp_out["is_active"].map({True: "✅ Active", False: "❌ Inactive"})
        disp_out["tracking_days"] = disp_out["tracking_days"].apply(
            lambda x: f"{x:,.0f}" if x > 0 else "—"
        )
        disp_out["tracking_hours"] = disp_out["tracking_hours"].apply(
            lambda x: f"{x:,.0f} hrs" if x > 0 else "—"
        )
        disp_out["days_since"]  = disp_out["days_since"].apply(
            lambda x: f"{x:.0f}d ago" if pd.notna(x) else "—"
        )
        disp_out["lat"] = disp_out["lat"].apply(lambda x: f"{x:.4f}" if pd.notna(x) else "—")
        disp_out["lon"] = disp_out["lon"].apply(lambda x: f"{x:.4f}" if pd.notna(x) else "—")
        disp_out["last_pos_date"] = pd.to_datetime(
            disp_out["last_pos_date"], errors="coerce", utc=True
        ).dt.strftime("%Y-%m-%d %H:%M UTC").fillna("—")

        disp_out = disp_out.rename(columns={
            "name":           "Subject",
            "subspecies":     "Species",
            "is_active":      "Status",
            "tracking_days":  "Deploy Days",
            "tracking_hours": "Tracking Hours",
            "days_since":     "Last Fix",
            "last_pos_date":  "Last Fix Date",
            "lat":            "Lat",
            "lon":            "Lon",
        })

        st.write(f"Showing **{len(disp_out)}** of {len(summary)} subjects")
        st.dataframe(disp_out, use_container_width=True, hide_index=True)

        # Download button
        csv = disp.to_csv(index=False)
        st.download_button(
            "⬇️ Download CSV",
            data=csv,
            file_name=f"twiga_dash_subjects_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )


# ─── Entry point ───────────────────────────────────────────────────────────────

def main():
    init_session_state()

    if not st.session_state.td_authenticated:
        render_login()
    else:
        render_dashboard()
