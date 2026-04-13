import streamlit as st
import pandas as pd
import calendar
from datetime import date, datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from ecoscope.io.earthranger import EarthRangerIO
import gspread
from google.oauth2.service_account import Credentials
import json
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from shared.utils import render_page_header


def main():
    """Main application entry point"""
    return _main_implementation()


# --- Manufacturer display name mappings ---
MANUFACTURER_DISPLAY = {
    'mapipedia': 'Ceres',
    'gsatsolar': 'GSat',
    'awt-gundi': 'Africa Wildlife Tracking',
    'savannah_tracking_provider': 'Savannah Tracking',
    'spoortrack': 'SpoorTrack',
}
MANUFACTURER_PROVIDER = {v: k for k, v in MANUFACTURER_DISPLAY.items()}

# Expected good daily location count per provider
DAILY_RATE = {
    'spoortrack': 24,
    'savannah_tracking_provider': 24,
    'mapipedia': 3,
    'gsatsolar': 3,
}

# Battery type by provider (voltage vs percentage)
VOLTAGE_PROVIDERS = {'spoortrack', 'savannah_tracking_provider'}
PERCENTAGE_PROVIDERS = {'mapipedia', 'gsatsolar'}

# Providers to hide from the manufacturer filter (system/integration sources)
EXCLUDED_PROVIDERS = {
    'twiga-awe-telemetry',
    'move_bank',
    'gundi_awt_push_v2_9c89bde7-2d98-437b-9170-6913906fd9f6',
    'cereswild-gcf',
    'SOURCE_PROVIDER',
}


# --- Session state ---

def init_session_state():
    defaults = {'authenticated': False, 'username': '', 'password': ''}
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


# --- Stock & Planning (Google Sheets) ---

@st.cache_data(ttl=900)
def load_stock_sheet_data(sheet_id):
    """Load stock, orders, and deployment plan data from Google Sheet (cached 15 min)."""
    try:
        if 'gcp_service_account' in st.secrets:
            creds_dict = dict(st.secrets['gcp_service_account'])
        elif 'gee_service_account' in st.secrets:
            creds_dict = dict(st.secrets['gee_service_account'])
        else:
            return None, "No service account credentials found in Streamlit secrets."

        credentials = Credentials.from_service_account_info(
            creds_dict,
            scopes=[
                'https://www.googleapis.com/auth/spreadsheets.readonly',
                'https://www.googleapis.com/auth/drive.readonly',
            ]
        )
        client = gspread.authorize(credentials)
        spreadsheet = client.open_by_key(sheet_id)

        result = {}
        for tab in ['stock', 'orders', 'deployment_plans']:
            try:
                result[tab] = pd.DataFrame(spreadsheet.worksheet(tab).get_all_records())
            except gspread.WorksheetNotFound:
                result[tab] = pd.DataFrame()

        return result, None

    except Exception as e:
        return None, str(e)


def _er_source_assignment_panel():
    """Cross-reference panel: ER sources with no subject assignment, grouped by provider."""
    st.markdown("---")
    st.subheader("🔗 EarthRanger Cross-Reference")
    st.caption(
        "Active tracking sources in ER with no subject assignment — "
        "these are likely in hand or undeployed. Cross-check with your stock sheet above."
    )

    try:
        with st.spinner("Checking ER source assignments..."):
            sources = get_all_sources(st.session_state.username, st.session_state.password)
    except Exception as e:
        st.warning(f"Could not load ER data: {e}")
        return

    if sources is None or sources.empty:
        st.info("No sources found in EarthRanger.")
        return

    tracking = sources[
        (sources['source_type'] == 'tracking-device') &
        (~sources['provider'].isin(EXCLUDED_PROVIDERS))
    ].copy()

    if tracking.empty:
        st.info("No tracking device sources found in EarthRanger.")
        return

    tracking['provider_display'] = tracking['provider'].map(MANUFACTURER_DISPLAY).fillna(tracking['provider'])
    tracking['label'] = tracking['collar_key'].fillna(tracking['id']).astype(str)

    if 'subject_id' not in tracking.columns:
        st.warning("EarthRanger did not return subject assignment data — cannot determine which sources are unassigned.")
        return

    unassigned = tracking[tracking['subject_id'].isna() | (tracking['subject_id'].astype(str).str.strip().isin(['', 'None', 'nan']))]
    assigned_count = len(tracking) - len(unassigned)

    ec1, ec2, ec3 = st.columns(3)
    ec1.metric("Active in ER", len(tracking))
    ec2.metric("Assigned to subject", assigned_count)
    ec3.metric("Unassigned in ER", len(unassigned))

    if unassigned.empty:
        st.success("All active ER tracking sources are currently assigned to a subject.")
        return

    by_provider = (
        unassigned.groupby('provider_display')['label']
        .apply(list)
        .reset_index()
    )
    by_provider['Count'] = by_provider['label'].apply(len)
    by_provider['Unit IDs'] = by_provider['label'].apply(lambda x: ', '.join(sorted(x)))
    by_provider = by_provider.rename(columns={'provider_display': 'Provider'})[['Provider', 'Count', 'Unit IDs']]
    st.dataframe(by_provider, use_container_width=True, hide_index=True)


def stock_planning_tab():
    """Stock and deployment planning dashboard, driven by a Google Sheet."""
    st.header("📦 Stock & Deployment Planning")

    try:
        sheet_id = st.secrets.get("gps_stock_sheet_id", "")
    except FileNotFoundError:
        sheet_id = ""
    if not sheet_id:
        st.warning("Google Sheet not configured yet.")
        with st.expander("Setup instructions", expanded=True):
            st.markdown("""
**Steps to connect your planning sheet:**

1. [Create a new Google Sheet](https://sheets.google.com) with these 3 tabs (exact names):

   **`stock`** — one row per individual unit (add a row when a unit arrives in hand):
   `unit_id` | `device_type` | `serial_no` | `office` | `status` | `allocated_project` | `allocated_site` | `planned_date` | `notes`
   - `unit_id`: your internal ID (e.g. STC-045)
   - `status` values: `in_hand`, `deployed`, `retired`
   - `allocated_project`: leave blank if unallocated

   **`orders`** — one row per order (count-based, since serial numbers aren't known yet):
   `order_date` | `device_type` | `quantity` | `office` | `supplier` | `expected_delivery` | `status` | `notes`
   *(status values: `ordered`, `received`, `cancelled`)*

   **`deployment_plans`** — one row per planned deployment:
   `project` | `country` | `site` | `office` | `device_type` | `units_needed` | `planned_date` | `status` | `notes`
   *(status values: `planned`, `confirmed`, `completed`, `cancelled`)*

2. Share the sheet (view access) with your service account email — find it in the `client_email` field of your GEE/GCP service account JSON in Streamlit secrets.

3. Copy the Sheet ID from the URL:
   `https://docs.google.com/spreadsheets/d/**SHEET_ID**/edit`

4. Add to your Streamlit secrets (`secrets.toml` or the Streamlit Cloud UI):
   ```toml
   gps_stock_sheet_id = "paste_sheet_id_here"
   ```
""")
        return

    if st.button("🔄 Refresh sheet data", key="refresh_stock"):
        load_stock_sheet_data.clear()
        st.rerun()

    with st.spinner("Loading sheet data..."):
        data, error = load_stock_sheet_data(sheet_id)

    if error:
        st.error(f"Could not load sheet: {error}")
        st.info("Check that the sheet is shared with your service account and the sheet ID in secrets is correct.")
        return

    stock_df = data.get('stock', pd.DataFrame())
    orders_df = data.get('orders', pd.DataFrame())
    plans_df = data.get('deployment_plans', pd.DataFrame())

    # Normalise status columns
    for df, col in [(stock_df, 'status'), (orders_df, 'status'), (plans_df, 'status')]:
        if not df.empty and col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.lower()

    # ── Derive summary counts ──────────────────────────────────────────────────
    in_hand_df = (
        stock_df[stock_df['status'] == 'in_hand']
        if not stock_df.empty and 'status' in stock_df.columns
        else pd.DataFrame()
    )
    total_in_hand = len(in_hand_df)
    if not in_hand_df.empty and 'allocated_project' in in_hand_df.columns:
        allocated_count = in_hand_df['allocated_project'].astype(str).str.strip().ne('').sum()
    else:
        allocated_count = 0
    unallocated_count = total_in_hand - allocated_count

    pending_orders_df = (
        orders_df[orders_df['status'] == 'ordered']
        if not orders_df.empty and 'status' in orders_df.columns
        else pd.DataFrame()
    )
    total_on_order = (
        int(pending_orders_df['quantity'].sum())
        if not pending_orders_df.empty and 'quantity' in pending_orders_df.columns
        else 0
    )

    active_plans_df = (
        plans_df[plans_df['status'].isin(['planned', 'confirmed'])]
        if not plans_df.empty and 'status' in plans_df.columns
        else pd.DataFrame()
    )
    total_needed = (
        int(active_plans_df['units_needed'].sum())
        if not active_plans_df.empty and 'units_needed' in active_plans_df.columns
        else 0
    )

    total_available = total_in_hand + total_on_order
    total_gap = max(0, total_needed - total_available)
    total_surplus = max(0, total_available - total_needed)

    # ── KPI cards ─────────────────────────────────────────────────────────────
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("In Hand", total_in_hand)
    k2.metric("Unallocated", unallocated_count)
    k3.metric("On Order", total_on_order)
    k4.metric("Planned Need", total_needed)
    if total_gap > 0:
        k5.metric("Shortfall", f"-{total_gap}", delta=f"-{total_gap}", delta_color="inverse")
    elif total_surplus > 0:
        k5.metric("Surplus", f"+{total_surplus}", delta=f"+{total_surplus}")
    else:
        k5.metric("Coverage", "Exact fit")

    # ── ER cross-reference (only when logged in) ───────────────────────────────
    if st.session_state.get('authenticated'):
        _er_source_assignment_panel()

    # ── Gap analysis ───────────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("⚖️ Gap Analysis by Office & Device Type")

    # Build per-(office, device_type) breakdown from individual stock rows
    in_hand_counts = {}
    allocated_counts = {}
    if not stock_df.empty and 'office' in stock_df.columns and 'device_type' in stock_df.columns and 'status' in stock_df.columns:
        ih = stock_df[stock_df['status'] == 'in_hand']
        for _, row in ih.iterrows():
            key = (str(row.get('office', '')), str(row.get('device_type', '')))
            in_hand_counts[key] = in_hand_counts.get(key, 0) + 1
            if 'allocated_project' in row and str(row['allocated_project']).strip():
                allocated_counts[key] = allocated_counts.get(key, 0) + 1

    on_order_counts = {}
    if not pending_orders_df.empty and 'office' in pending_orders_df.columns and 'device_type' in pending_orders_df.columns:
        for _, row in pending_orders_df.iterrows():
            key = (str(row.get('office', '')), str(row.get('device_type', '')))
            on_order_counts[key] = on_order_counts.get(key, 0) + int(row.get('quantity', 0))

    needed_counts = {}
    if not active_plans_df.empty and 'office' in active_plans_df.columns and 'device_type' in active_plans_df.columns:
        for _, row in active_plans_df.iterrows():
            key = (str(row.get('office', '')), str(row.get('device_type', '')))
            needed_counts[key] = needed_counts.get(key, 0) + int(row.get('units_needed', 0))

    all_keys = sorted(set(in_hand_counts) | set(on_order_counts) | set(needed_counts))
    if all_keys:
        gap_rows = []
        for office, device in all_keys:
            key = (office, device)
            ih = in_hand_counts.get(key, 0)
            alloc = allocated_counts.get(key, 0)
            oo = on_order_counts.get(key, 0)
            need = needed_counts.get(key, 0)
            avail = ih + oo
            gap_rows.append({
                'Office': office,
                'Device Type': device,
                'In Hand': ih,
                'Allocated': alloc,
                'Unallocated': ih - alloc,
                'On Order': oo,
                'Needed': need,
                'Gap': max(0, need - avail),
                'Surplus': max(0, avail - need),
            })
        gap_df = pd.DataFrame(gap_rows)

        if gap_df['Gap'].sum() == 0:
            st.success("✅ You have enough units for all planned deployments.")
        else:
            st.error(f"⚠️ You need to order {int(gap_df['Gap'].sum())} more units across all offices.")

        def _highlight_gap(row):
            if row['Gap'] > 0:
                return ['background-color: #ffcccc'] * len(row)
            elif row['Surplus'] > 0:
                return ['background-color: #ccffcc'] * len(row)
            return [''] * len(row)

        st.dataframe(gap_df.style.apply(_highlight_gap, axis=1), use_container_width=True, hide_index=True)
    else:
        st.info("Add stock and deployment plan data to see the gap analysis.")

    # ── Filters (apply to the three detail sections below) ────────────────────
    st.markdown("---")
    all_offices = sorted({
        str(v) for df in [stock_df, orders_df, plans_df]
        if not df.empty and 'office' in df.columns
        for v in df['office'].dropna()
    })
    all_device_types = sorted({
        str(v) for df in [stock_df, orders_df, plans_df]
        if not df.empty and 'device_type' in df.columns
        for v in df['device_type'].dropna()
    })
    fc1, fc2 = st.columns(2)
    with fc1:
        filter_office = st.multiselect("Filter by office", all_offices, key="stock_filter_office")
    with fc2:
        filter_device = st.multiselect("Filter by device type", all_device_types, key="stock_filter_device")

    def _apply_filters(df):
        if df.empty:
            return df
        if filter_office and 'office' in df.columns:
            df = df[df['office'].isin(filter_office)]
        if filter_device and 'device_type' in df.columns:
            df = df[df['device_type'].isin(filter_device)]
        return df

    # ── Units in hand (individual) ─────────────────────────────────────────────
    st.subheader("📦 Units in Hand")

    display_stock = _apply_filters(stock_df.copy()) if not stock_df.empty else stock_df
    if display_stock.empty:
        st.info("No unit data found. Add rows to the `stock` tab in your Google Sheet.")
    else:
        status_filter = st.radio(
            "Show", ["In hand", "Deployed", "All"], horizontal=True, key="stock_status_radio"
        )
        if status_filter == "In hand":
            display_stock = display_stock[display_stock['status'] == 'in_hand'] if 'status' in display_stock.columns else display_stock
        elif status_filter == "Deployed":
            display_stock = display_stock[display_stock['status'] == 'deployed'] if 'status' in display_stock.columns else display_stock

        if display_stock.empty:
            st.info(f"No units with status '{status_filter.lower()}'.")
        else:
            display_cols = [c for c in ['unit_id', 'serial_no', 'device_type', 'office', 'status', 'allocated_project', 'allocated_site', 'planned_date', 'notes'] if c in display_stock.columns]
            st.dataframe(display_stock[display_cols], use_container_width=True, hide_index=True)

    # ── Pending orders ─────────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("🚚 Pending Orders")

    display_orders = _apply_filters(orders_df.copy()) if not orders_df.empty else orders_df
    if display_orders.empty:
        st.info("No orders found. Add rows to the `orders` tab in your Google Sheet.")
    else:
        if 'status' in display_orders.columns:
            pending = display_orders[~display_orders['status'].isin(['received', 'cancelled'])]
        else:
            pending = display_orders

        if pending.empty:
            st.success("No pending orders — all orders received or cancelled.")
        else:
            st.dataframe(pending, use_container_width=True, hide_index=True)

        if len(display_orders) > len(pending):
            with st.expander(f"All orders ({len(display_orders)} total)"):
                st.dataframe(display_orders, use_container_width=True, hide_index=True)

    # ── Deployment plans ───────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("📋 Deployment Plans")

    display_plans = _apply_filters(plans_df.copy()) if not plans_df.empty else plans_df
    if display_plans.empty:
        st.info("No deployment plans found. Add rows to the `deployment_plans` tab in your Google Sheet.")
    else:
        if 'status' in display_plans.columns:
            active_display = display_plans[~display_plans['status'].isin(['completed', 'cancelled'])]
        else:
            active_display = display_plans

        if not active_display.empty:
            if 'planned_date' in active_display.columns:
                active_display = active_display.sort_values('planned_date', na_position='last')
            st.dataframe(active_display, use_container_width=True, hide_index=True)
        else:
            st.info("No active plans.")

        if len(display_plans) > len(active_display):
            with st.expander(f"All plans ({len(display_plans)} total)"):
                st.dataframe(display_plans, use_container_width=True, hide_index=True)


# --- EarthRanger connection ---

def er_login(username, password):
    """Create EarthRanger connection and test it"""
    try:
        er_io = EarthRangerIO(
            server="https://twiga.pamdas.org",
            username=username,
            password=password
        )
        er_io.get_sources(limit=1)
        return er_io
    except Exception as e:
        st.error(f"Failed to connect to EarthRanger: {e}")
        return None


def authenticate_earthranger():
    """Render EarthRanger login form"""
    st.header("🔐 EarthRanger Authentication")
    st.write("Enter your EarthRanger credentials to access the unit check dashboard:")
    st.info("**Server:** https://twiga.pamdas.org")

    username = st.text_input("Username", help="Your EarthRanger username")
    password = st.text_input("Password", type="password", help="Your EarthRanger password")

    if st.button("🔌 Login to EarthRanger", type="primary"):
        if not username or not password:
            st.error("❌ Username and password are required")
            return
        if er_login(username, password):
            st.session_state.authenticated = True
            st.session_state.username = username
            st.session_state.password = password
            st.success("✅ Successfully logged in to EarthRanger!")
            st.rerun()
        else:
            st.error("❌ Invalid credentials. Please try again.")


# --- Data fetching ---

@st.cache_data(ttl=3600)
def get_all_sources(_username, _password):
    """Fetch all tracking sources (cached for 1 hour)"""
    er = EarthRangerIO(
        server="https://twiga.pamdas.org",
        username=_username,
        password=_password
    )
    return er.get_sources()


def get_last_7_days(source_id, username, password):
    """Fetch last 7 days of locations and battery data for a source"""
    er = EarthRangerIO(
        server="https://twiga.pamdas.org",
        username=username,
        password=password
    )
    since = (datetime.utcnow() - timedelta(days=7)).isoformat()

    try:
        relocations = er.get_source_observations(
            source_ids=[source_id],
            since=since,
            include_details=True,
            relocations=False
        )

        if relocations.empty:
            return pd.DataFrame()

        points = []
        for _, row in relocations.iterrows():
            latitude, longitude = None, None
            if 'geometry' in row:
                try:
                    geom = row['geometry']
                    if geom is not None and hasattr(geom, 'y') and hasattr(geom, 'x'):
                        latitude = geom.y
                        longitude = geom.x
                except Exception:
                    if 'location' in row and isinstance(row['location'], dict):
                        latitude = row['location'].get('latitude')
                        longitude = row['location'].get('longitude')

            point = {
                'datetime': row['recorded_at'],
                'latitude': latitude,
                'longitude': longitude,
            }

            # Extract battery — check observation_details first, then device_status_properties
            battery_found = False
            if 'observation_details' in row:
                obs = row['observation_details']
                if isinstance(obs, dict):
                    for field in ['voltage', 'battery', 'batt', 'batt_perc', 'bat_soc']:
                        if field in obs:
                            point['battery'] = obs[field]
                            battery_found = True
                            break

            if not battery_found and 'device_status_properties' in row:
                device_status = row['device_status_properties']
                if isinstance(device_status, list):
                    for item in device_status:
                        if isinstance(item, dict) and 'label' in item and 'value' in item:
                            if any(t in item['label'].lower() for t in ['voltage', 'battery', 'batt', 'bat_soc']):
                                point['battery'] = item['value']
                                break

            points.append(point)

        return pd.DataFrame(points)

    except Exception as e:
        st.error(f"Error fetching observations: {e}")
        import traceback
        st.code(traceback.format_exc())
        return pd.DataFrame()


# --- Unit Check tab ---

def unit_check_tab():
    """Main unit check dashboard"""
    username = st.session_state.username
    password = st.session_state.password

    try:
        with st.spinner("Loading all sources..."):
            df_sources = get_all_sources(username, password)
    except Exception as e:
        st.error(f"Error connecting to EarthRanger: {e}")
        st.info("Please check your internet connection and EarthRanger server status.")
        return

    if df_sources.empty:
        st.warning("No sources found.")
        return

    df_sources = df_sources[df_sources['source_type'] == 'tracking-device']
    if df_sources.empty:
        st.warning("No tracking device sources found.")
        return

    # Build manufacturer selector with display names (exclude system/integration providers)
    raw_providers = sorted(
        p for p in df_sources['provider'].dropna().unique()
        if p not in EXCLUDED_PROVIDERS
    )
    display_names = [MANUFACTURER_DISPLAY.get(p, p) for p in raw_providers]
    manufacturer_options = ['All'] + display_names

    # Default to SpoorTrack if available
    default_index = next(
        (i + 1 for i, p in enumerate(raw_providers) if p.lower() == 'spoortrack'),
        0
    )
    selected_display = st.selectbox("Select a manufacturer", manufacturer_options, index=default_index)

    # Filter sources by selected manufacturer
    if selected_display != 'All':
        selected_provider = MANUFACTURER_PROVIDER.get(selected_display, selected_display)
        df_sources = df_sources[df_sources['provider'] == selected_provider]

    df_sources['label'] = df_sources['collar_key'].fillna(df_sources['id']).astype(str)
    df_sources = df_sources.sort_values('label')

    selected_labels = st.multiselect(
        "Select sources (you can select multiple)",
        df_sources['label'].tolist(),
        default=[df_sources['label'].iloc[0]] if len(df_sources) > 0 else []
    )

    if not selected_labels:
        st.warning("Please select at least one source.")
        return

    selected_source_ids = df_sources[df_sources['label'].isin(selected_labels)]['id'].tolist()
    colors = px.colors.qualitative.Set1
    color_map = {label: colors[i % len(colors)] for i, label in enumerate(selected_labels)}

    st.markdown("---")
    st.subheader("📊 Activity (last 7 days)")

    # Fetch data once per source, reuse for all charts
    source_data = {}
    with st.spinner("Fetching 7-day location data..."):
        for i, source_id in enumerate(selected_source_ids):
            label = selected_labels[i]
            try:
                source_data[label] = get_last_7_days(source_id, username, password)
            except Exception as e:
                st.warning(f"Could not fetch data for {label}: {e}")
                source_data[label] = pd.DataFrame()

    # Build chart inputs from fetched data
    all_7_day_data = []
    all_battery_data = []
    last_locations = []

    for label, df_7 in source_data.items():
        if df_7.empty:
            continue

        df_7['date'] = pd.to_datetime(df_7['datetime']).dt.date

        counts = df_7.groupby('date').size().reset_index(name='count')
        counts['source'] = label
        all_7_day_data.append(counts)

        if 'battery' in df_7.columns:
            df_7['battery_numeric'] = pd.to_numeric(df_7['battery'], errors='coerce')
            if df_7['battery_numeric'].notna().any():
                batt_agg = df_7.groupby('date')['battery_numeric'].mean().reset_index()
                batt_agg = batt_agg.rename(columns={'battery_numeric': 'battery'})
                batt_agg['source'] = label
                all_battery_data.append(batt_agg)

        if 'latitude' in df_7.columns and 'longitude' in df_7.columns:
            last = df_7.sort_values('datetime', ascending=False).iloc[0]
            loc = {
                'source': label,
                'latitude': last['latitude'],
                'longitude': last['longitude'],
                'datetime': last['datetime'],
                'color': color_map[label],
            }
            if 'battery' in df_7.columns and last.get('battery') is not None:
                loc['battery'] = last['battery']
            last_locations.append(loc)

    # Determine provider family for reference lines
    selected_providers = set(
        df_sources[df_sources['label'].isin(selected_labels)]['provider'].dropna().str.lower()
    )

    # --- Activity chart ---
    col1, col2 = st.columns(2)

    with col1:
        if all_7_day_data:
            combined_df = pd.concat(all_7_day_data, ignore_index=True)
            fig = px.bar(
                combined_df, x='date', y='count', color='source',
                title="Daily location counts", barmode='group'
            )
            # Add reference line only if all selected sources share the same expected rate
            rates = {DAILY_RATE[p] for p in selected_providers if p in DAILY_RATE}
            if len(rates) == 1:
                rate = rates.pop()
                fig.add_hline(
                    y=rate, line_dash="dash", line_color="green",
                    annotation_text=f"Good ({rate}/day)",
                    annotation_position="top right",
                    annotation_font_color="green"
                )
            fig.update_layout(
                xaxis_title="Date",
                yaxis_title="Number of locations",
                xaxis=dict(tickformat='%Y-%m-%d')
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No locations in the last 7 days for any selected sources.")

    # --- Battery chart ---
    with col2:
        if all_battery_data:
            battery_df = pd.concat(all_battery_data, ignore_index=True)
            max_batt = battery_df['battery'].max()
            min_batt = battery_df['battery'].min()
            is_voltage = max_batt <= 5.0 and min_batt >= 3.0
            is_percentage = max_batt > 10 and max_batt <= 100

            fig_batt = px.line(
                battery_df, x='date', y='battery', color='source',
                title="Average daily battery", markers=True
            )

            if is_voltage:
                fig_batt.add_hline(
                    y=3.9, line_dash="dash", line_color="green",
                    annotation_text="Good (3.9V)",
                    annotation_position="bottom right",
                    annotation_font_color="green"
                )
                y_title, y_range = "Battery voltage (V)", [3.2, 4.2]
            elif is_percentage:
                fig_batt.add_hline(
                    y=80, line_dash="dash", line_color="green",
                    annotation_text="Good (80%)",
                    annotation_position="bottom right",
                    annotation_font_color="green"
                )
                y_title, y_range = "Battery level (%)", [0, 100]
            else:
                y_title, y_range = "Battery Level", None

            fig_batt.update_layout(
                xaxis_title="Date",
                yaxis_title=y_title,
                xaxis=dict(tickformat='%Y-%m-%d'),
                yaxis=dict(range=y_range) if y_range else {}
            )
            st.plotly_chart(fig_batt, use_container_width=True)
        else:
            st.info("No battery data available for selected sources.")

    # --- Last location map ---
    st.markdown("---")
    st.subheader("🗺️ Last location")

    if last_locations:
        last_df = pd.DataFrame(last_locations)
        hover_data = {'datetime': True, 'latitude': ':.6f', 'longitude': ':.6f'}
        if 'battery' in last_df.columns:
            hover_data['battery'] = True

        fig_map = px.scatter_mapbox(
            last_df,
            lat='latitude', lon='longitude', color='source',
            hover_data=hover_data,
            title="Last known locations",
            mapbox_style='open-street-map',
            height=500, size_max=15
        )
        fig_map.update_traces(marker=dict(size=12))
        fig_map.update_layout(mapbox=dict(
            center=dict(lat=last_df['latitude'].mean(), lon=last_df['longitude'].mean()),
            zoom=8
        ))
        st.plotly_chart(fig_map, use_container_width=True)

        st.subheader("📍 Last location details")
        display_cols = ['source', 'datetime', 'latitude', 'longitude']
        display_df = last_df[display_cols].copy()
        if 'battery' in last_df.columns:
            display_df['battery'] = last_df['battery']
        display_df['datetime'] = pd.to_datetime(display_df['datetime']).dt.strftime('%Y-%m-%d %H:%M:%S')
        st.dataframe(display_df, use_container_width=True)
    else:
        st.info("No location data available for mapping.")

    # --- Summary stats ---
    if all_7_day_data:
        combined_df = pd.concat(all_7_day_data, ignore_index=True)
        avg_daily = combined_df.groupby('source')['count'].mean()
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total locations (7 days)", combined_df['count'].sum())
        with col2:
            st.metric("Average daily locations", f"{avg_daily.mean():.1f}")
        with col3:
            st.metric("Sources reporting", len(selected_labels))

    # --- Unit update events ---
    st.markdown("---")
    st.subheader("📝 Unit Update Events")
    fetch_unit_update_events(selected_source_ids, selected_labels, username, password)


def fetch_unit_update_events(source_ids, source_labels, username, password):
    """Fetch and display unit update events for selected sources"""
    try:
        er = EarthRangerIO(
            server="https://twiga.pamdas.org",
            username=username,
            password=password
        )
    except Exception as e:
        st.error(f"Error connecting to EarthRanger: {e}")
        return

    with st.spinner("Fetching unit update events (all time)..."):
        try:
            events_df = er.get_events(
                event_category='monitoring',
                event_type=['7bb99e0c-9d37-405b-b8e7-edca8e9b5d6b'],
                include_details=True,
                drop_null_geometry=False,
            )

            if events_df.empty:
                st.info("No unit update events found in the system.")
                return

            filtered_events = []

            for _, event in events_df.iterrows():
                event_details = event.get('event_details')

                if event_details:
                    if isinstance(event_details, str):
                        try:
                            event_details = json.loads(event_details)
                        except Exception:
                            continue

                    if isinstance(event_details, dict):
                        subject_id = event_details.get('unitupdate_subject')
                        unit_id = event_details.get('unitupdate_unitid')
                        matched_id = next(
                            (sid for sid in [subject_id, unit_id] if sid in source_ids),
                            None
                        )
                        if matched_id:
                            event_copy = event.to_dict()
                            event_copy['source_label'] = source_labels[source_ids.index(matched_id)]
                            filtered_events.append(event_copy)
                            continue

                # Fallback: check related_subjects
                related_subjects = event.get('related_subjects', [])
                if isinstance(related_subjects, list):
                    for subject in related_subjects:
                        if isinstance(subject, dict):
                            subject_id = subject.get('id') or subject.get('subject_id')
                            if subject_id in source_ids:
                                event_copy = event.to_dict()
                                event_copy['source_label'] = source_labels[source_ids.index(subject_id)]
                                filtered_events.append(event_copy)
                                break

            if not filtered_events:
                st.warning("No unit update events found for the selected sources.")
                return

            filtered_df = pd.DataFrame(filtered_events)
            st.subheader("📊 Events Summary")

            summary_data = []
            for _, event in filtered_df.iterrows():
                row = {
                    'Source': event.get('source_label', ''),
                    'Time': pd.to_datetime(event.get('time')).strftime('%Y-%m-%d %H:%M:%S') if event.get('time') else '',
                    'Serial #': event.get('serial_number', ''),
                    'State': event.get('state', ''),
                }
                details = event.get('event_details')
                if isinstance(details, str):
                    try:
                        details = json.loads(details)
                    except Exception:
                        pass
                if isinstance(details, dict):
                    row['Action'] = details.get('unitupdate_action', '')
                    row['Notes'] = details.get('unitupdate_notes', '')
                    row['Country'] = details.get('unitupdate_country', '')
                summary_data.append(row)

            if summary_data:
                st.dataframe(pd.DataFrame(summary_data), use_container_width=True)

        except Exception as e:
            st.error(f"Error fetching unit update events: {e}")
            import traceback
            st.code(traceback.format_exc())


# --- Unit Update Event Upload ---

def render_unit_update_upload_tab():
    """Bulk-import unit_update monitoring events via CSV using EarthRangerIO"""
    st.header("📥 Upload Unit Update Events")
    st.markdown(
        "Upload a CSV to create `unit_update` events in EarthRanger. "
        "Each row records when a GPS unit was activated or deactivated, and from where, "
        "linked to the unit's source ID."
    )

    # ── Template download ───────────────────────────────────────────────────
    template_cols = ["source_id", "event_datetime", "action", "country", "latitude", "longitude", "notes"]
    example_rows = [
        ["abc123-uuid", "2025-06-01T08:00:00Z", "activated", "KEN", "-0.606", "37.120", "Deployed at Samburu"],
        ["def456-uuid", "2025-06-02T09:30:00Z", "deactivated", "NAM", "-20.123", "17.456", "Collar removed post-study"],
    ]
    template_csv = ",".join(template_cols) + "\n"
    for row in example_rows:
        template_csv += ",".join(row) + "\n"

    st.download_button(
        "⬇️ Download CSV template",
        data=template_csv,
        file_name="unit_update_events_template.csv",
        mime="text/csv",
    )
    st.markdown(
        "**Required:** `source_id`, `event_datetime`  \n"
        "**Optional:** `action`, `country`, `latitude`, `longitude`, `notes`  \n"
        "`event_datetime` format: `YYYY-MM-DDTHH:MM:SSZ` or `YYYY-MM-DD HH:MM:SS`"
    )

    # ── File upload ─────────────────────────────────────────────────────────
    uploaded_file = st.file_uploader("Upload CSV", type="csv", key="unit_update_csv_uploader")
    if uploaded_file is None:
        return

    try:
        df_upload = pd.read_csv(uploaded_file)
    except Exception as e:
        st.error(f"Error reading CSV: {e}")
        return

    if 'source_id' not in df_upload.columns or 'event_datetime' not in df_upload.columns:
        st.error("CSV must have `source_id` and `event_datetime` columns.")
        return

    df_upload = df_upload.dropna(subset=['source_id', 'event_datetime'])
    st.write(f"**{len(df_upload)} event(s) ready to import — preview:**")
    st.dataframe(df_upload.head(10), use_container_width=True, hide_index=True)
    if len(df_upload) > 10:
        st.caption(f"Showing first 10 of {len(df_upload)} rows.")

    if not st.button("Import Events", type="primary", key="unit_update_csv_import_btn"):
        return

    username = st.session_state.username
    password = st.session_state.password

    try:
        er = EarthRangerIO(
            server="https://twiga.pamdas.org",
            username=username,
            password=password,
        )
    except Exception as e:
        st.error(f"Could not connect to EarthRanger: {e}")
        return

    results = []
    progress = st.progress(0)
    total = len(df_upload)

    for i, (_, row) in enumerate(df_upload.iterrows()):
        try:
            src_id = str(row['source_id']).strip()

            raw_dt = str(row['event_datetime']).strip()
            try:
                from dateutil import parser as date_parser
                iso_time = date_parser.parse(raw_dt).strftime('%Y-%m-%dT%H:%M:%SZ')
            except Exception:
                iso_time = raw_dt

            action_val = str(row['action']).strip() if pd.notna(row.get('action')) else 'activated'
            country_val = str(row['country']).strip() if pd.notna(row.get('country')) else ''
            notes_val = str(row['notes']).strip() if pd.notna(row.get('notes')) else ''

            event_payload = {
                'event_type': 'unit_update',
                'title': 'Unit update',
                'time': iso_time,
                'state': 'new',
                'priority': 200,
                'is_collection': False,
                'event_details': {
                    'unitupdate_unitid': src_id,
                    'unitupdate_action': action_val,
                    'unitupdate_country': country_val,
                    'unitupdate_notes': notes_val,
                },
            }

            lat = row.get('latitude')
            lon = row.get('longitude')
            if pd.notna(lat) and pd.notna(lon):
                try:
                    event_payload['location'] = {'latitude': float(lat), 'longitude': float(lon)}
                except (ValueError, TypeError):
                    pass

            er.post_event(event_payload)
            results.append({'success': True, 'row': i + 1, 'source_id': src_id, 'event_datetime': iso_time})

        except Exception as e:
            results.append({'success': False, 'error': str(e), 'row': i + 1, 'source_id': str(row.get('source_id', ''))})

        progress.progress((i + 1) / total)

    progress.empty()
    success_count = sum(1 for r in results if r.get('success'))
    fail_count = total - success_count

    if success_count > 0:
        st.success(f"✅ Successfully imported {success_count} event(s)")
    if fail_count > 0:
        st.error(f"❌ Failed to import {fail_count} event(s):")
        for r in results:
            if not r.get('success'):
                st.write(f"  - Row {r['row']} ({r.get('source_id', '')} / {r.get('event_datetime', '')}): {r.get('error', 'Unknown error')}")
    if success_count > 0:
        st.info("The new events will appear in the **Unit Update Events** section after the next data refresh.")


# --- Iridium Invoice Calculator ---

ER_SERVER = "https://twiga.pamdas.org"


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_subjectsources_all(_username, _password):
    """Fetch all subject-source assignments (deployment dates) from EarthRanger."""
    er = EarthRangerIO(server=ER_SERVER, username=_username, password=_password)
    all_results = []
    url = f"{ER_SERVER}/api/v1.0/subjectsources/?page_size=500&include_inactive=true"
    while url:
        resp = er._http_session.get(url, headers=er.auth_headers())
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            all_results.extend(data)
            break
        inner = data.get('data', data)
        if isinstance(inner, dict):
            all_results.extend(inner.get('results', []))
            url = inner.get('next')
        elif isinstance(inner, list):
            all_results.extend(inner)
            url = data.get('next')
        else:
            break
    return all_results


@st.cache_data(ttl=1800, show_spinner=False)
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_recently_active_sources(_username, _password, source_ids_tuple, since_iso, until_iso):
    """Return the subset of source IDs that have any observation between since_iso and until_iso.

    Both since AND until are required — the ER observations endpoint ignores a lone
    'since' and returns arbitrary historical records.  Passing until=today gives the
    same since+until pattern used by the billing month checks, which is confirmed working.

    Cached for 1 hour — reflects current deployment status, changes infrequently.
    """
    er = EarthRangerIO(server=ER_SERVER, username=_username, password=_password)
    headers = er.auth_headers()
    active = set()
    for source_id in source_ids_tuple:
        url = (
            f"{ER_SERVER}/api/v1.0/observations/"
            f"?source_id={source_id}&since={since_iso}&until={until_iso}&page_size=1"
        )
        try:
            resp = er._http_session.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            items = data.get('results') or data.get('data', {}).get('results', [])
            if items:
                active.add(source_id)
        except Exception:
            pass
    return active


def fetch_all_source_active_months(_username, _password, source_ids_tuple, billing_months_tuple):
    """Check which billing months each source had GPS observations.

    Makes one lightweight REST call (page_size=1) per source per billing month,
    all reusing the same authenticated session.
    Returns dict: source_id → set of (year, month) tuples.
    """
    er = EarthRangerIO(server=ER_SERVER, username=_username, password=_password)
    headers = er.auth_headers()
    results = {sid: set() for sid in source_ids_tuple}

    for source_id in source_ids_tuple:
        for y, m in billing_months_tuple:
            m_start = date(y, m, 1).isoformat()
            m_end = date(y, m, calendar.monthrange(y, m)[1]).isoformat()
            url = (
                f"{ER_SERVER}/api/v1.0/observations/"
                f"?source_id={source_id}&since={m_start}&until={m_end}&page_size=1"
            )
            try:
                resp = er._http_session.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                items = data.get('results') or data.get('data', {}).get('results', [])
                if items:
                    results[source_id].add((y, m))
            except Exception:
                pass

    return results


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_unit_updates_for_billing(_username, _password, since_iso, until_iso):
    """Fetch unit_update monitoring events and return a tidy DataFrame.

    Returns columns: source_id (str, the ER source UUID from unitupdate_unitid),
    action (str, lowercased + normalised), time.
    """
    er = EarthRangerIO(server=ER_SERVER, username=_username, password=_password)
    try:
        gdf = er.get_events(
            event_category='monitoring',
            event_type=['7bb99e0c-9d37-405b-b8e7-edca8e9b5d6b'],
            since=since_iso,
            until=until_iso,
            include_details=True,
            drop_null_geometry=False,
        )
        if gdf is None or gdf.empty:
            return pd.DataFrame(columns=['source_id', 'action', 'time'])
        df = pd.DataFrame(gdf)
        records = []
        for _, row in df.iterrows():
            unit_id = action = None
            # ecoscope may flatten event_details into direct columns
            if 'unitupdate_unitid' in row.index:
                unit_id = row.get('unitupdate_unitid')
            if 'unitupdate_action' in row.index:
                action = row.get('unitupdate_action')
            # fall back to nested event_details dict
            if not unit_id or not action:
                details = row.get('event_details') or {}
                if isinstance(details, dict):
                    unit_id = unit_id or details.get('unitupdate_unitid')
                    action = action or details.get('unitupdate_action')
            if unit_id and action:
                # Normalise action string: lowercase, spaces → underscores
                action_norm = str(action).strip().lower().replace(' ', '_')
                records.append({
                    'source_id': str(unit_id).strip(),
                    'action': action_norm,
                    'time': row.get('time') or row.get('created_at'),
                })
        return pd.DataFrame(records) if records else pd.DataFrame(columns=['source_id', 'action', 'time'])
    except Exception as e:
        st.warning(f"Could not load unit_update events: {e}")
        return pd.DataFrame(columns=['source_id', 'action', 'time'])


def _billing_months(start_d, end_d):
    """Return list of (year, month) tuples covering start_d through end_d."""
    months = []
    d = start_d.replace(day=1)
    while d <= end_d:
        months.append((d.year, d.month))
        d = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
    return months


def iridium_invoice_tab():
    """Iridium satellite billing validator."""
    st.header("📡 Iridium Invoice Calculator")
    st.caption(
        "Validate your quarterly Iridium satellite bill by checking which units "
        "were active each month of the billing period."
    )

    # ── Billing parameters ────────────────────────────────────────────────────
    st.subheader("⚙️ Billing Parameters")

    # Default: most recent complete calendar quarter
    today = datetime.utcnow().date()
    q = (today.month - 1) // 3          # 0-based quarter of current month
    if q == 0:
        def_start = date(today.year - 1, 10, 1)
        def_end = date(today.year - 1, 12, 31)
    else:
        def_start = date(today.year, (q - 1) * 3 + 1, 1)
        end_month = q * 3
        def_end = date(today.year, end_month, calendar.monthrange(today.year, end_month)[1])

    c1, c2 = st.columns(2)
    with c1:
        start_date = st.date_input("Billing period start", value=def_start, key="inv_start")
        cost_active = st.number_input(
            "Active unit cost (USD/month)", min_value=0.0, value=41.0, step=1.0, key="inv_cost_active"
        )
        cost_suspended = st.number_input(
            "Suspended unit cost (USD/month)", min_value=0.0, value=3.0, step=1.0, key="inv_cost_suspended"
        )
        schedule_change_fee = st.number_input(
            "Schedule change fee (USD/event)", min_value=0.0, value=0.50, step=0.10, key="inv_sched_fee"
        )
    with c2:
        end_date = st.date_input("Billing period end", value=def_end, key="inv_end")
        activation_fee = st.number_input(
            "Activation fee (USD/event)", min_value=0.0, value=30.0, step=1.0, key="inv_activation"
        )
        suspension_fee = st.number_input(
            "Suspension fee, one-time (USD/event)", min_value=0.0, value=3.0, step=1.0, key="inv_susp_fee"
        )

    manufacturer = st.selectbox(
        "Manufacturer", ["SpoorTrack"], key="inv_manufacturer",
        help="Filter to units from this manufacturer. Additional providers can be added in future."
    )

    with st.expander("Suspended units (charged at reduced rate)", expanded=False):
        st.caption("Enter one unit ID per line (collar_key as shown in EarthRanger).")
        suspended_text = st.text_area(
            "Suspended unit IDs", height=150, key="inv_suspended",
            placeholder="STC-001\nSTC-002\n..."
        )
    suspended_units = {u.strip() for u in suspended_text.splitlines() if u.strip()}

    if start_date > end_date:
        st.error("Start date must be before end date.")
        return

    if not st.button("🧮 Calculate Invoice", type="primary", key="inv_calc"):
        return

    # ── Fetch sources ─────────────────────────────────────────────────────────
    provider_key = MANUFACTURER_PROVIDER.get(manufacturer)   # e.g. 'spoortrack'
    with st.spinner("Loading EarthRanger sources..."):
        sources = get_all_sources(st.session_state.username, st.session_state.password)

    if sources is None or sources.empty:
        st.error("Could not load EarthRanger sources.")
        return

    mfr_sources = sources[
        (sources['source_type'] == 'tracking-device') &
        (sources['provider'] == provider_key)
    ].copy()

    if mfr_sources.empty:
        st.warning(f"No {manufacturer} tracking sources found in EarthRanger.")
        return

    mfr_sources['unit_label'] = mfr_sources['collar_key'].fillna(mfr_sources['id']).astype(str)
    source_id_to_label = dict(zip(mfr_sources['id'].astype(str), mfr_sources['unit_label']))
    source_ids = list(mfr_sources['id'].astype(str))

    # Extract source creation date — when the unit was first activated in ER.
    # Try common column names returned by ecoscope/ER API.
    created_col = next(
        (c for c in ('created_at', 'sourceCreated', 'created', 'source_created')
         if c in mfr_sources.columns),
        None
    )
    source_id_to_created = {}
    if created_col:
        for _, src_row in mfr_sources.iterrows():
            val = src_row.get(created_col)
            if pd.notna(val):
                try:
                    source_id_to_created[str(src_row['id'])] = pd.to_datetime(val).date()
                except Exception:
                    pass
    else:
        st.info(
            "Source creation date not found in EarthRanger data — "
            f"available columns: {list(mfr_sources.columns)}. "
            "Activation fees cannot be calculated."
        )

    # ── Fetch deployment assignments ──────────────────────────────────────────
    with st.spinner("Loading deployment assignments..."):
        try:
            subjectsources = fetch_subjectsources_all(
                st.session_state.username, st.session_state.password
            )
        except Exception as e:
            st.warning(f"Could not load deployment data ({e}). Deployment start dates will not be available.")
            subjectsources = []

    # Build lookup: source_id → {deploy_start, subject_name}
    deploy_info = {}
    for ss in (subjectsources or []):
        if not isinstance(ss, dict):
            continue
        src_id = str(ss.get('source') or ss.get('source_id') or '').strip()
        if src_id not in source_id_to_label:
            continue
        ar = ss.get('assigned_range') or {}
        dep_start_str = ar.get('lower')
        dep_start = None
        if dep_start_str:
            try:
                dep_start = pd.to_datetime(dep_start_str).date()
            except Exception:
                pass
        subject_info = ss.get('subject') or {}
        subject_name = ''
        _uuid_pat = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        if isinstance(subject_info, dict):
            subject_name = subject_info.get('name') or subject_info.get('display_name') or ''
        elif isinstance(subject_info, str):
            import re
            if not re.match(_uuid_pat, subject_info.strip(), re.I):
                subject_name = subject_info

        # Keep most recent deployment start for this source
        if src_id not in deploy_info or (
            dep_start and deploy_info[src_id]['deploy_start']
            and dep_start > deploy_info[src_id]['deploy_start']
        ):
            deploy_info[src_id] = {'deploy_start': dep_start, 'subject_name': subject_name}

    # ── Pre-filter: drop units with no data in the last 3 months from today ─────
    # A unit is inactive if its last-ever observation was > 90 days ago.
    today_iso = datetime.utcnow().date().isoformat()
    activity_cutoff = (datetime.utcnow().date() - timedelta(days=90)).isoformat()
    with st.spinner(
        f"Checking which {manufacturer} units are currently active "
        f"(data since {activity_cutoff})…"
    ):
        recently_active_ids = fetch_recently_active_sources(
            st.session_state.username,
            st.session_state.password,
            tuple(sorted(source_ids)),
            activity_cutoff,
            today_iso,
        )
    source_ids = [s for s in source_ids if s in recently_active_ids]
    if not source_ids:
        st.warning(f"No {manufacturer} units with data in the last 90 days.")
        return
    st.caption(
        f"Filtered to **{len(source_ids)}** currently active {manufacturer} units "
        f"(last data within 90 days of today)."
    )

    # ── Check which months each source had GPS activity ───────────────────────
    since_iso = start_date.isoformat()
    until_iso = end_date.isoformat()
    billing_ym = _billing_months(start_date, end_date)
    month_labels = [datetime(y, m, 1).strftime("%b %Y") for y, m in billing_ym]
    n_checks = len(source_ids) * len(billing_ym)

    with st.spinner(
        f"Checking activity for {len(source_ids)} {manufacturer} units × "
        f"{len(billing_ym)} months ({n_checks} requests) — cached for 30 min…"
    ):
        active_months_per_source = fetch_all_source_active_months(
            st.session_state.username,
            st.session_state.password,
            tuple(sorted(source_ids)),
            tuple(billing_ym),
        )

    # ── Fetch unit_update events ───────────────────────────────────────────────
    with st.spinner("Loading unit_update events..."):
        events_df = fetch_unit_updates_for_billing(
            st.session_state.username, st.session_state.password,
            since_iso, until_iso,
        )

    # Per-source event counts keyed by normalised action
    # unitupdate_unitid stores the source UUID — match directly against source_ids
    source_events = {sid: {'activated': 0, 'suspended': 0, 'schedule_change': 0, 'deactivated': 0}
                     for sid in source_ids}
    if not events_df.empty:
        for _, ev in events_df.iterrows():
            src_id = str(ev['source_id']).strip()
            action = str(ev['action']).strip()
            if src_id in source_events and action in source_events[src_id]:
                source_events[src_id][action] += 1

    if not events_df.empty:
        st.caption(
            f"Loaded {len(events_df)} unit_update event(s) — "
            f"{events_df['action'].value_counts().to_dict()}"
        )

    # ── Build billing table ───────────────────────────────────────────────────
    rows = []
    for src_id in source_ids:
        active_in = active_months_per_source[src_id]
        evts = source_events.get(src_id, {})
        # Include rows that either had GPS activity OR had a unit_update event this period
        if not active_in and not any(evts.values()):
            continue
        unit_label = source_id_to_label[src_id]
        info = deploy_info.get(src_id, {})
        subject_name = info.get('subject_name', '')

        source_created = source_id_to_created.get(src_id)
        is_suspended = unit_label in suspended_units
        n_months = len(active_in)
        rate = cost_suspended if is_suspended else cost_active

        # Event-based fees
        # Activation: use unit_update 'activated' events (more accurate than sourceCreated).
        # Fall back to sourceCreated only if no activated events were recorded.
        n_activations = evts.get('activated', 0)
        n_suspensions = evts.get('suspended', 0)
        n_schedule_changes = evts.get('schedule_change', 0)
        n_deactivations = evts.get('deactivated', 0)

        if n_activations > 0:
            act_fee = n_activations * activation_fee
        elif source_created is not None and start_date <= source_created <= end_date:
            act_fee = activation_fee   # sourceCreated fallback for new units
            n_activations = 1          # treat as 1 implicit activation
        else:
            act_fee = 0.0

        susp_fee = n_suspensions * suspension_fee
        sched_fee = n_schedule_changes * schedule_change_fee

        row = {
            'Unit ID': unit_label,
            'Subject': subject_name,
            'Status': 'Suspended' if is_suspended else 'Active',
            'Source Created': source_created.strftime('%Y-%m-%d') if source_created else '',
        }
        for (y, m), label in zip(billing_ym, month_labels):
            row[label] = '✓' if (y, m) in active_in else ''
        row.update({
            'Months Active': n_months,
            'Rate ($/mo)': rate,
            'Monthly Cost ($)': n_months * rate,
            'Activations': n_activations,
            'Activation ($)': act_fee,
            'Suspensions': n_suspensions,
            'Suspension ($)': susp_fee,
            'Sched. Changes': n_schedule_changes,
            'Sched. Change ($)': sched_fee,
            'Deactivations': n_deactivations,
            'Total ($)': n_months * rate + act_fee + susp_fee + sched_fee,
        })
        rows.append(row)

    if not rows:
        st.warning(
            f"No {manufacturer} units with activity found between {start_date} and {end_date}."
        )
        return

    billing_df = pd.DataFrame(rows).sort_values(['Status', 'Unit ID']).reset_index(drop=True)

    # ── Display results ────────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("📊 Invoice Summary")

    n_active_units = (billing_df['Status'] == 'Active').sum()
    n_suspended_units = (billing_df['Status'] == 'Suspended').sum()
    total_monthly = billing_df['Monthly Cost ($)'].sum()
    total_activation = billing_df['Activation ($)'].sum()
    total_suspension = billing_df['Suspension ($)'].sum()
    total_sched = billing_df['Sched. Change ($)'].sum()
    total_invoice = billing_df['Total ($)'].sum()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Units", len(billing_df))
    m2.metric("Active", n_active_units)
    m3.metric("Suspended", n_suspended_units)
    m4.metric("Schedule Changes", int(billing_df['Sched. Changes'].sum()))

    st.markdown("#### Monthly Breakdown")
    monthly_rows = []
    for (y, m), label in zip(billing_ym, month_labels):
        n = billing_df[label].str.strip().eq('✓').sum()
        monthly_rows.append({'Month': label, 'Units Active': n, 'Est. Cost ($)': n * cost_active})
    st.dataframe(pd.DataFrame(monthly_rows), use_container_width=True, hide_index=True)

    st.markdown("#### Estimated Invoice Total")
    i1, i2, i3, i4, i5 = st.columns(5)
    i1.metric("Monthly", f"${total_monthly:,.2f}")
    i2.metric("Activations", f"${total_activation:,.2f}")
    i3.metric("Suspensions", f"${total_suspension:,.2f}")
    i4.metric("Sched. Changes", f"${total_sched:,.2f}")
    i5.metric("TOTAL", f"${total_invoice:,.2f}")

    st.markdown("---")
    st.subheader("📋 Unit Detail")
    st.dataframe(billing_df, use_container_width=True, hide_index=True)

    csv = billing_df.to_csv(index=False).encode('utf-8')
    fname = f"{manufacturer}_invoice_{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}.csv"
    st.download_button("⬇️ Download CSV", data=csv, file_name=fname, mime='text/csv', key="inv_download")


# --- Main entry point ---

def _main_implementation():
    init_session_state()

    if not st.session_state.authenticated:
        authenticate_earthranger()
        return

    render_page_header("GPS Unit Check", "Monitor tracking device health · battery · fix history", "🔋")

    st.sidebar.markdown("### 🔐 Authentication ✅")
    if st.session_state.get('username'):
        st.sidebar.write(f"**User:** {st.session_state.username}")
        st.sidebar.write("**Server:** https://twiga.pamdas.org")

    tab1, tab2, tab3, tab4 = st.tabs(["🔍 Unit Check", "📦 Stock & Planning", "📥 Upload Events", "📡 Iridium Invoice"])
    with tab1:
        unit_check_tab()
    with tab2:
        stock_planning_tab()
    with tab3:
        render_unit_update_upload_tab()
    with tab4:
        iridium_invoice_tab()

    st.sidebar.markdown("---")
    st.sidebar.subheader("🔧 Options")

    if st.sidebar.button("🔄 Refresh Data"):
        get_all_sources.clear()
        load_stock_sheet_data.clear()
        fetch_subjectsources_all.clear()
        fetch_recently_active_sources.clear()
        fetch_all_source_active_months.clear()
        fetch_unit_updates_for_billing.clear()
        st.rerun()

    if st.sidebar.button("🔓 Logout"):
        for key in ['authenticated', 'username', 'password']:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()


if __name__ == "__main__":
    main()
