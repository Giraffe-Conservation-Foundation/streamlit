import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from ecoscope.io.earthranger import EarthRangerIO
import gspread
from google.oauth2.service_account import Credentials
import json


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

   **`stock`** — one row per office × device type:
   `office` | `device_type` | `in_hand` | `notes` | `last_updated`

   **`orders`** — one row per order:
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

    OFFICES = ['Namibia', 'Kenya', 'South Africa']

    # ── Current stock ──────────────────────────────────────────────────────────
    st.subheader("📦 Current Stock by Office")

    if stock_df.empty:
        st.info("No stock data found. Add rows to the `stock` tab in your Google Sheet.")
    else:
        cols = st.columns(len(OFFICES))
        for col, office in zip(cols, OFFICES):
            with col:
                st.markdown(f"**{office}**")
                office_rows = stock_df[stock_df['office'] == office] if 'office' in stock_df.columns else pd.DataFrame()
                if office_rows.empty:
                    st.caption("No data")
                else:
                    for _, row in office_rows.iterrows():
                        st.metric(row.get('device_type', '—'), int(row.get('in_hand', 0)))
                        if row.get('notes'):
                            st.caption(row['notes'])

    # ── Pending orders ─────────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("🚚 Pending Orders")

    if orders_df.empty:
        st.info("No orders found. Add rows to the `orders` tab in your Google Sheet.")
    else:
        if 'status' in orders_df.columns:
            pending = orders_df[~orders_df['status'].str.lower().isin(['received', 'cancelled'])]
        else:
            pending = orders_df

        if pending.empty:
            st.success("No pending orders — all orders received or cancelled.")
        else:
            st.dataframe(pending, use_container_width=True, hide_index=True)

        if len(orders_df) > len(pending):
            with st.expander(f"All orders ({len(orders_df)} total)"):
                st.dataframe(orders_df, use_container_width=True, hide_index=True)

    # ── Deployment plans ───────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("📋 Deployment Plans")

    if plans_df.empty:
        st.info("No deployment plans found. Add rows to the `deployment_plans` tab in your Google Sheet.")
    else:
        if 'status' in plans_df.columns:
            active_plans = plans_df[~plans_df['status'].str.lower().isin(['completed', 'cancelled'])]
        else:
            active_plans = plans_df

        if not active_plans.empty:
            st.dataframe(active_plans, use_container_width=True, hide_index=True)

        if len(plans_df) > len(active_plans):
            with st.expander(f"All plans ({len(plans_df)} total)"):
                st.dataframe(plans_df, use_container_width=True, hide_index=True)

    # ── Gap analysis ───────────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("⚖️ Do I Need to Order?")

    if stock_df.empty and plans_df.empty:
        st.info("Add stock and deployment plan data to see the gap analysis.")
        return

    # in_hand per (office, device_type)
    in_hand = {}
    if not stock_df.empty and 'office' in stock_df.columns and 'device_type' in stock_df.columns:
        for _, row in stock_df.iterrows():
            in_hand[(row['office'], row['device_type'])] = int(row.get('in_hand', 0))

    # on_order per (office, device_type) — orders with status='ordered'
    on_order = {}
    if not orders_df.empty and 'office' in orders_df.columns and 'device_type' in orders_df.columns:
        pending_orders = (
            orders_df[orders_df['status'].str.lower() == 'ordered']
            if 'status' in orders_df.columns else orders_df
        )
        for _, row in pending_orders.iterrows():
            key = (row.get('office', ''), row.get('device_type', ''))
            on_order[key] = on_order.get(key, 0) + int(row.get('quantity', 0))

    # needed per (office, device_type) — plans with status planned/confirmed
    needed = {}
    if not plans_df.empty and 'office' in plans_df.columns and 'device_type' in plans_df.columns:
        active = (
            plans_df[plans_df['status'].str.lower().isin(['planned', 'confirmed'])]
            if 'status' in plans_df.columns else plans_df
        )
        for _, row in active.iterrows():
            key = (row.get('office', ''), row.get('device_type', ''))
            needed[key] = needed.get(key, 0) + int(row.get('units_needed', 0))

    all_keys = sorted(set(in_hand) | set(on_order) | set(needed))
    if not all_keys:
        st.info("Not enough data to calculate gaps.")
        return

    gap_rows = []
    for office, device in all_keys:
        key = (office, device)
        avail = in_hand.get(key, 0) + on_order.get(key, 0)
        req = needed.get(key, 0)
        gap_rows.append({
            'Office': office,
            'Device Type': device,
            'In Hand': in_hand.get(key, 0),
            'On Order': on_order.get(key, 0),
            'Available': avail,
            'Needed': req,
            'Gap': max(0, req - avail),
            'Surplus': max(0, avail - req),
        })

    gap_df = pd.DataFrame(gap_rows)
    total_gap = gap_df['Gap'].sum()

    if total_gap == 0:
        st.success("✅ You have enough units for all planned deployments.")
    else:
        st.error(f"⚠️ You need to order {int(total_gap)} more units across all offices.")

    def _highlight_gap(row):
        if row['Gap'] > 0:
            return ['background-color: #ffcccc'] * len(row)
        elif row['Surplus'] > 0:
            return ['background-color: #ccffcc'] * len(row)
        return [''] * len(row)

    st.dataframe(gap_df.style.apply(_highlight_gap, axis=1), use_container_width=True, hide_index=True)


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


# --- Main entry point ---

def _main_implementation():
    init_session_state()

    st.title("🔍 Unit Check Dashboard")
    st.markdown("Monitor GPS tracking units (7 day activity/battery, and last location)")

    if not st.session_state.authenticated:
        authenticate_earthranger()
        return

    st.sidebar.markdown("### 🔐 Authentication ✅")
    if st.session_state.get('username'):
        st.sidebar.write(f"**User:** {st.session_state.username}")
        st.sidebar.write("**Server:** https://twiga.pamdas.org")

    tab1, tab2, tab3 = st.tabs(["🔍 Unit Check", "📦 Stock & Planning", "📥 Upload Events"])
    with tab1:
        unit_check_tab()
    with tab2:
        stock_planning_tab()
    with tab3:
        render_unit_update_upload_tab()

    st.sidebar.markdown("---")
    st.sidebar.subheader("🔧 Options")

    if st.sidebar.button("🔄 Refresh Data"):
        get_all_sources.clear()
        load_stock_sheet_data.clear()
        st.rerun()

    if st.sidebar.button("🔓 Logout"):
        for key in ['authenticated', 'username', 'password']:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()


if __name__ == "__main__":
    main()
