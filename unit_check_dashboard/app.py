import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time
import plotly.express as px
import plotly.graph_objects as go
from ecoscope.io.earthranger import EarthRangerIO
import json
import os
import gspread
from google.oauth2.service_account import Credentials

# Make main available at module level for import
def main():
    """Main application entry point - delegates to _main_implementation"""
    return _main_implementation()

# Custom CSS for better styling (minimal - no forced backgrounds)
st.markdown("""
<style>
    .logo-title {
        color: #2E8B57;
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 0.5rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
    }
    .logo-subtitle {
        color: #4F4F4F;
        font-size: 1.3rem;
        font-weight: 300;
        margin-top: 0;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #2E8B57;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

def init_session_state():
    """Initialize session state variables"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'username' not in st.session_state:
        st.session_state.username = ""
    if 'password' not in st.session_state:
        st.session_state.password = ""
    if 'current_tab' not in st.session_state:
        st.session_state.current_tab = "Unit Check"
    if 'stock_data' not in st.session_state:
        st.session_state.stock_data = load_stock_data()

# --- Stock Management with EarthRanger Events ---
STOCK_EVENT_TYPE = 'ab2912ed-b89f-4873-9586-866aa29287bd'  # unit_stock
DEPLOYMENT_PLAN_EVENT_TYPE = '3957b3a7-97f2-4d94-a6de-5f171ab041f6'  # unit_plan (may need to be updated based on actual event type)
# Note: If unit_plan events are stored under a different event_type, update DEPLOYMENT_PLAN_EVENT_TYPE above

def get_stock_from_earthranger(er_io):
    """Get GPS unit stock from EarthRanger events"""
    try:
        since_date = datetime.now() - timedelta(days=180)
        
        events = er_io.get_events(
            event_type=[STOCK_EVENT_TYPE],
            since=since_date.isoformat(),
            include_details=True
        )
        
        stock_by_office = {
            'Namibia': {'spoortrack': 0, 'gsatsolar': 0, 'ordered_st': 0, 'ordered_gs': 0},
            'Kenya': {'spoortrack': 0, 'gsatsolar': 0, 'ordered_st': 0, 'ordered_gs': 0},
            'South Africa': {'spoortrack': 0, 'gsatsolar': 0, 'ordered_st': 0, 'ordered_gs': 0}
        }
        
        if not events.empty:
            events_df = events.copy()
            events_df['time'] = pd.to_datetime(events_df['time'])
            events_df = events_df.sort_values('time')
            
            for idx, event_row in events_df.iterrows():
                # Handle event_details which might be None
                if 'event_details' not in event_row or event_row['event_details'] is None:
                    continue
                    
                details = event_row['event_details']
                
                # Map office codes to full names
                office_code = details.get('unit_office', 'kenya').lower()
                office_map = {
                    'nam': 'Namibia',
                    'namibia': 'Namibia',
                    'kenya': 'Kenya',
                    'ken': 'Kenya',
                    'south africa': 'South Africa',
                    'zaf': 'South Africa',
                    'rsa': 'South Africa'
                }
                office = office_map.get(office_code, 'Kenya')
                
                # Map unit type codes to full names
                unit_type_code = details.get('unit_manufac', 'spoortrack').lower()
                unit_type_map = {
                    'spoortrack': 'SpoorTrack',
                    'gsatsolar': 'GSatSolar',
                    'gsat': 'GSatSolar'
                }
                unit_type = unit_type_map.get(unit_type_code, 'SpoorTrack')
                
                quantity = int(details.get('unit_number', 0))
                
                # Map transaction codes
                stock_action_code = details.get('unit_transaction', 'stock_count').lower()
                stock_action_map = {
                    'stock_count': 'stock_count',
                    'count': 'stock_count',
                    'order_placed': 'order_placed',
                    'order': 'order_placed',
                    'order_received': 'order_received',
                    'received': 'order_received'
                }
                stock_action = stock_action_map.get(stock_action_code, 'stock_count')
                
                if office not in stock_by_office:
                    continue
                
                if stock_action == 'stock_count':
                    if unit_type == 'SpoorTrack':
                        stock_by_office[office]['spoortrack'] = quantity
                    elif unit_type == 'GSatSolar':
                        stock_by_office[office]['gsatsolar'] = quantity
                elif stock_action == 'order_placed':
                    if unit_type == 'SpoorTrack':
                        stock_by_office[office]['ordered_st'] += quantity
                    elif unit_type == 'GSatSolar':
                        stock_by_office[office]['ordered_gs'] += quantity
                elif stock_action == 'order_received':
                    if unit_type == 'SpoorTrack':
                        stock_by_office[office]['spoortrack'] += quantity
                        stock_by_office[office]['ordered_st'] = max(0, stock_by_office[office]['ordered_st'] - quantity)
                    elif unit_type == 'GSatSolar':
                        stock_by_office[office]['gsatsolar'] += quantity
                        stock_by_office[office]['ordered_gs'] = max(0, stock_by_office[office]['ordered_gs'] - quantity)
        
        return stock_by_office
    except Exception as e:
        st.error(f"❌ Error loading stock from EarthRanger: {e}")
        import traceback
        st.error(f"Traceback: {traceback.format_exc()}")
        return {
            'Namibia': {'spoortrack': 0, 'gsatsolar': 0, 'ordered_st': 0, 'ordered_gs': 0},
            'Kenya': {'spoortrack': 0, 'gsatsolar': 0, 'ordered_st': 0, 'ordered_gs': 0},
            'South Africa': {'spoortrack': 0, 'gsatsolar': 0, 'ordered_st': 0, 'ordered_gs': 0}
        }

def get_deployment_plans_from_earthranger(er_io):
    """Get deployment plans from EarthRanger events"""
    try:
        since_date = datetime.now() - timedelta(days=365)
        
        events = er_io.get_events(
            event_type=[DEPLOYMENT_PLAN_EVENT_TYPE],
            since=since_date.isoformat(),
            include_details=True
        )
        
        plans = []
        if not events.empty:
            for idx, event_row in events.iterrows():
                # Handle event_details which might be None
                if 'event_details' not in event_row or event_row['event_details'] is None:
                    continue
                    
                details = event_row['event_details']
                status = details.get('deployment_status', 'planned')
                if status != 'cancelled':
                    # Map office codes to full names
                    office_code = details.get('unit_office', 'kenya').lower() if details.get('unit_office') else 'kenya'
                    office_map = {
                        'nam': 'Namibia',
                        'namibia': 'Namibia',
                        'kenya': 'Kenya',
                        'ken': 'Kenya',
                        'south africa': 'South Africa',
                        'zaf': 'South Africa',
                        'rsa': 'South Africa'
                    }
                    office = office_map.get(office_code, 'Kenya')
                    
                    # Map country codes
                    country_code = details.get('unit_plan_country', '').lower()
                    country = office_map.get(country_code, details.get('unit_plan_country', ''))
                    
                    # Map manufacturer codes
                    manufacturer_code = details.get('unit_plan_manufac', 'spoortrack').lower()
                    manufacturer_map = {
                        'spoortrack': 'SpoorTrack',
                        'gsatsolar': 'GSatSolar',
                        'gsat': 'GSatSolar'
                    }
                    manufacturer = manufacturer_map.get(manufacturer_code, 'SpoorTrack')
                    
                    plans.append({
                        'event_id': event_row.get('id', '') if 'id' in event_row else '',
                        'country': country,
                        'site': details.get('unit_plan_site', ''),
                        'manufacturer': manufacturer,
                        'office': office,
                        'date': details.get('unit_plan_date', ''),
                        'spoortrack': int(details.get('unit_plan_number', 0)) if manufacturer == 'SpoorTrack' else 0,
                        'gsatsolar': int(details.get('unit_plan_number', 0)) if manufacturer == 'GSatSolar' else 0,
                        'status': status,
                        'notes': details.get('notes', '')
                    })
        
        return plans
    except Exception as e:
        st.error(f"❌ Could not load deployment plans: {e}")
        import traceback
        st.error(f"Traceback: {traceback.format_exc()}")
        return []

def create_stock_event(er_io, office, unit_type, quantity, stock_action, notes=""):
    """Create a stock event in EarthRanger"""
    try:
        event_data = {
            'event_type': STOCK_EVENT_TYPE,
            'time': datetime.now().isoformat(),
            'event_details': {
                'unit_office': office,
                'unit_manufac': unit_type,
                'unit_number': quantity,
                'unit_transaction': stock_action,
                'notes': notes
            }
        }
        er_io.post_event(event_data)
        return True
    except Exception as e:
        st.error(f"Failed to create stock event: {e}")
        return False

def create_deployment_plan_event(er_io, country, site, office, manufacturer, planned_date, quantity, notes=""):
    """Create a deployment plan event in EarthRanger"""
    try:
        event_data = {
            'event_type': DEPLOYMENT_PLAN_EVENT_TYPE,
            'time': datetime.now().isoformat(),
            'event_details': {
                'unit_plan_country': country,
                'unit_plan_site': site,
                'unit_office': office,
                'unit_plan_manufac': manufacturer,
                'unit_plan_number': quantity,
                'unit_plan_date': planned_date,
                'deployment_status': 'planned',
                'notes': notes
            }
        }
        er_io.post_event(event_data)
        return True
    except Exception as e:
        st.error(f"Failed to create deployment plan: {e}")
        return False

# --- Stock Management Functions (Google Sheets - deprecated) ---
SHEET_NAME = 'GPS_Unit_Stock_Planning'

def get_google_sheets_client():
    """Get authenticated Google Sheets client"""
    try:
        # Try to get credentials from Streamlit secrets
        # Check for gcp_service_account first, then fall back to gee_service_account
        if hasattr(st, 'secrets'):
            if 'gcp_service_account' in st.secrets:
                st.info("✓ Using gcp_service_account credentials")
                credentials = Credentials.from_service_account_info(
                    st.secrets['gcp_service_account'],
                    scopes=['https://www.googleapis.com/auth/spreadsheets',
                           'https://www.googleapis.com/auth/drive']
                )
            elif 'gee_service_account' in st.secrets:
                st.info("✓ Using gee_service_account credentials")
                credentials = Credentials.from_service_account_info(
                    st.secrets['gee_service_account'],
                    scopes=['https://www.googleapis.com/auth/spreadsheets',
                           'https://www.googleapis.com/auth/drive']
                )
            else:
                st.error("❌ No Google service account found in secrets. See GOOGLE_SHEETS_SETUP.md")
                return None
        else:
            st.error("❌ Streamlit secrets not accessible")
            return None
        
        client = gspread.authorize(credentials)
        st.success("✅ Successfully authenticated with Google Sheets")
        return client
    except Exception as e:
        st.error(f"❌ Error authenticating with Google Sheets: {e}")
        st.info("Make sure Google Sheets API AND Google Drive API are both enabled in your Google Cloud project.")
        import traceback
        st.code(traceback.format_exc())
        return None

def load_stock_data():
    """Load stock data from Google Sheets"""
    try:
        client = get_google_sheets_client()
        if client is None:
            return get_default_stock_data()
        
        # Open the spreadsheet (will create if doesn't exist)
        try:
            spreadsheet = client.open(SHEET_NAME)
        except gspread.SpreadsheetNotFound:
            # Create new spreadsheet if it doesn't exist
            spreadsheet = client.create(SHEET_NAME)
            sheet_url = spreadsheet.url
            # Share with your email so you can access it
            try:
                spreadsheet.share('gcf.spatial@giraffeconservation.org', perm_type='user', role='writer')
                st.success(f"✅ Created new spreadsheet '{SHEET_NAME}' and shared it with gcf.spatial@giraffeconservation.org")
                st.markdown(f"### 🔗 [Click here to open the Google Sheet]({sheet_url})")
                st.info(f"📧 You should also receive an email notification. Bookmark this link!")
            except Exception as e:
                st.warning(f"Created spreadsheet but couldn't auto-share: {e}")
                st.markdown(f"### 🔗 [Click here to open the Google Sheet]({sheet_url})")
                st.info("You may need to request access when you open it.")
            return get_default_stock_data()
        
        # Load each worksheet
        data = get_default_stock_data()
        
        # Load deployment plan
        try:
            plan_sheet = spreadsheet.worksheet('deployment_plan')
            records = plan_sheet.get_all_records()
            if records:
                # Ensure numeric fields are properly typed
                for record in records:
                    record['spoortrack'] = int(record.get('spoortrack', 0)) if pd.notna(record.get('spoortrack')) else 0
                    record['gsatsolar'] = int(record.get('gsatsolar', 0)) if pd.notna(record.get('gsatsolar')) else 0
                    record['spoortrack_assigned'] = int(record.get('spoortrack_assigned', 0)) if pd.notna(record.get('spoortrack_assigned')) else 0
                    record['gsatsolar_assigned'] = int(record.get('gsatsolar_assigned', 0)) if pd.notna(record.get('gsatsolar_assigned')) else 0
                data['deployment_plan'] = records
                st.success(f"✅ Loaded {len(records)} deployment plans from Google Sheets")
        except gspread.WorksheetNotFound:
            st.info("No deployment_plan worksheet found yet")
        except Exception as e:
            st.warning(f"Could not load deployment plans: {e}")
        
        # Load in_hand
        try:
            hand_sheet = spreadsheet.worksheet('in_hand')
            records = hand_sheet.get_all_records()
            if records:
                data['in_hand'] = records
        except gspread.WorksheetNotFound:
            pass
        
        # Load in_mail
        try:
            mail_sheet = spreadsheet.worksheet('in_mail')
            records = mail_sheet.get_all_records()
            if records:
                data['in_mail'] = records
        except gspread.WorksheetNotFound:
            pass
        
        # Load stock summary
        try:
            summary_sheet = spreadsheet.worksheet('stock_summary')
            summary_records = summary_sheet.get_all_records()
            if summary_records:
                for record in summary_records:
                    type_name = record.get('type', '').lower()
                    if type_name in data['stock_summary']:
                        data['stock_summary'][type_name]['in_hand'] = int(record.get('in_hand', 0)) if pd.notna(record.get('in_hand')) else 0
                        data['stock_summary'][type_name]['in_mail'] = int(record.get('in_mail', 0)) if pd.notna(record.get('in_mail')) else 0
                st.success(f"✅ Loaded stock summary from Google Sheets")
        except gspread.WorksheetNotFound:
            st.info("No stock_summary worksheet found yet")
        except Exception as e:
            st.warning(f"Could not load stock summary: {e}")
        
        # Load office stock distribution
        try:
            office_sheet = spreadsheet.worksheet('office_stock')
            office_records = office_sheet.get_all_records()
            if office_records:
                # Initialize office_stock if not exists
                if 'office_stock' not in data:
                    data['office_stock'] = {
                        'Namibia': {'spoortrack': 0, 'gsatsolar': 0},
                        'Kenya': {'spoortrack': 0, 'gsatsolar': 0},
                        'South Africa': {'spoortrack': 0, 'gsatsolar': 0}
                    }
                for record in office_records:
                    office = record.get('office', '')
                    if office in data['office_stock']:
                        data['office_stock'][office]['spoortrack'] = int(record.get('spoortrack', 0)) if pd.notna(record.get('spoortrack')) else 0
                        data['office_stock'][office]['gsatsolar'] = int(record.get('gsatsolar', 0)) if pd.notna(record.get('gsatsolar')) else 0
                st.success(f"✅ Loaded office stock distribution from Google Sheets")
        except gspread.WorksheetNotFound:
            st.info("No office_stock worksheet found yet (will be created on first save)")
        except Exception as e:
            st.warning(f"Could not load office stock: {e}")
        
        return data
    except Exception as e:
        st.warning(f"Could not load from Google Sheets: {e}. Using default data.")
        return get_default_stock_data()

def get_default_stock_data():
    """Return default empty stock data structure"""
    return {
        'deployment_plan': [],
        'in_hand': [],
        'in_mail': [],
        'stock_summary': {
            'spoortrack': {'in_hand': 0, 'in_mail': 0},
            'gsatsolar': {'in_hand': 0, 'in_mail': 0}
        },
        'office_stock': {
            'Namibia': {'spoortrack': 0, 'gsatsolar': 0},
            'Kenya': {'spoortrack': 0, 'gsatsolar': 0},
            'South Africa': {'spoortrack': 0, 'gsatsolar': 0}
        }
    }

def save_stock_data(data):
    """Save stock data to Google Sheets"""
    try:
        client = get_google_sheets_client()
        if client is None:
            st.error("Cannot save: Google Sheets client not available")
            return False
        
        # Open or create spreadsheet
        try:
            spreadsheet = client.open(SHEET_NAME)
            st.info(f"📝 Updating existing spreadsheet...")
        except gspread.SpreadsheetNotFound:
            st.info(f"📄 Creating new spreadsheet...")
            spreadsheet = client.create(SHEET_NAME)
            # Share with your email
            try:
                spreadsheet.share('gcf.spatial@giraffeconservation.org', perm_type='user', role='writer')
                st.success(f"✅ Shared with gcf.spatial@giraffeconservation.org")
            except Exception as e:
                st.warning(f"Could not auto-share: {e}")
        
        # Always show the link
        sheet_url = spreadsheet.url
        st.markdown(f"### 🔗 [Open Google Sheet]({sheet_url})")
        st.caption("Bookmark this link to access your data anytime!")
        
        # Save stock summary
        summary_data = [
            {'type': 'spoortrack', 'in_hand': data['stock_summary']['spoortrack']['in_hand'], 'in_mail': data['stock_summary']['spoortrack']['in_mail']},
            {'type': 'gsatsolar', 'in_hand': data['stock_summary']['gsatsolar']['in_hand'], 'in_mail': data['stock_summary']['gsatsolar']['in_mail']}
        ]
        df_summary = pd.DataFrame(summary_data)
        try:
            sheet = spreadsheet.worksheet('stock_summary')
            sheet.clear()
        except gspread.WorksheetNotFound:
            sheet = spreadsheet.add_worksheet(title='stock_summary', rows=100, cols=10)
        sheet.update([df_summary.columns.values.tolist()] + df_summary.values.tolist())
        st.success("✅ Stock summary saved!")
        
        # Save office stock distribution
        if 'office_stock' in data:
            office_data = []
            for office, stock in data['office_stock'].items():
                office_data.append({'office': office, 'spoortrack': stock['spoortrack'], 'gsatsolar': stock['gsatsolar']})
            df_office = pd.DataFrame(office_data)
            try:
                sheet = spreadsheet.worksheet('office_stock')
                sheet.clear()
            except gspread.WorksheetNotFound:
                sheet = spreadsheet.add_worksheet(title='office_stock', rows=100, cols=10)
            sheet.update([df_office.columns.values.tolist()] + df_office.values.tolist())
            st.success("✅ Office stock distribution saved!")
        
        # Save deployment plan
        if data['deployment_plan']:
            df_plan = pd.DataFrame(data['deployment_plan'])
            try:
                sheet = spreadsheet.worksheet('deployment_plan')
                sheet.clear()
            except gspread.WorksheetNotFound:
                sheet = spreadsheet.add_worksheet(title='deployment_plan', rows=1000, cols=20)
            sheet.update([df_plan.columns.values.tolist()] + df_plan.values.tolist())
            st.success(f"✅ Saved {len(data['deployment_plan'])} deployment plans")
        
        # Save in_hand
        if data['in_hand']:
            df_hand = pd.DataFrame(data['in_hand'])
            try:
                sheet = spreadsheet.worksheet('in_hand')
                sheet.clear()
            except gspread.WorksheetNotFound:
                sheet = spreadsheet.add_worksheet(title='in_hand', rows=1000, cols=20)
            sheet.update([df_hand.columns.values.tolist()] + df_hand.values.tolist())
            st.success(f"✅ Saved {len(data['in_hand'])} in-hand units")
        
        # Save in_mail
        if data['in_mail']:
            df_mail = pd.DataFrame(data['in_mail'])
            try:
                sheet = spreadsheet.worksheet('in_mail')
                sheet.clear()
            except gspread.WorksheetNotFound:
                sheet = spreadsheet.add_worksheet(title='in_mail', rows=1000, cols=20)
            sheet.update([df_mail.columns.values.tolist()] + df_mail.values.tolist())
            st.success(f"✅ Saved {len(data['in_mail'])} in-mail orders")
        
        return True
    except Exception as e:
        st.error(f"Error saving to Google Sheets: {e}")
        import traceback
        st.code(traceback.format_exc())
        return False

def deployment_planning_dashboard(er_io):
    """Deployment planning and stock management dashboard using EarthRanger events"""
    st.header("📊 Deployment Planning & Stock Management")
    st.caption("Stock and plans tracked via EarthRanger events")
    
    with st.spinner("Loading data from EarthRanger..."):
        stock_data = get_stock_from_earthranger(er_io)
        deployment_plans = get_deployment_plans_from_earthranger(er_io)
    
    # Check if deployment plans exist
    if not deployment_plans or len(deployment_plans) == 0:
        st.info("💡 No deployment plans found. Create unit_plan events in EarthRanger to see them here.")
    
    tab1, tab2 = st.tabs(["📋 Stock & Plans", "📊 Summary"])
    
    with tab1:
        st.subheader("📋 Stock & Deployment Plans")
        
        st.markdown("### 📦 Current Stock by Office")
        st.caption("📊 Calculated from EarthRanger stock events")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**🇳🇦 Namibia**")
            st.metric("SpoorTrack", stock_data['Namibia']['spoortrack'])
            st.metric("GSatSolar", stock_data['Namibia']['gsatsolar'])
            if stock_data['Namibia']['ordered_st'] > 0 or stock_data['Namibia']['ordered_gs'] > 0:
                st.caption(f"📬 Ordered: ST:{stock_data['Namibia']['ordered_st']} GS:{stock_data['Namibia']['ordered_gs']}")
        
        with col2:
            st.markdown("**🇰🇪 Kenya**")
            st.metric("SpoorTrack", stock_data['Kenya']['spoortrack'])
            st.metric("GSatSolar", stock_data['Kenya']['gsatsolar'])
            if stock_data['Kenya']['ordered_st'] > 0 or stock_data['Kenya']['ordered_gs'] > 0:
                st.caption(f"📬 Ordered: ST:{stock_data['Kenya']['ordered_st']} GS:{stock_data['Kenya']['ordered_gs']}")
        
        with col3:
            st.markdown("**🇿🇦 South Africa**")
            st.metric("SpoorTrack", stock_data['South Africa']['spoortrack'])
            st.metric("GSatSolar", stock_data['South Africa']['gsatsolar'])
            if stock_data['South Africa']['ordered_st'] > 0 or stock_data['South Africa']['ordered_gs'] > 0:
                st.caption(f"📬 Ordered: ST:{stock_data['South Africa']['ordered_st']} GS:{stock_data['South Africa']['ordered_gs']}")
        
        st.markdown("---")
        st.markdown("### 📋 Deployment Plans")
        
        if deployment_plans:
            df_plan = pd.DataFrame(deployment_plans)
            
            for office in ['Namibia', 'Kenya', 'South Africa']:
                office_plans = df_plan[df_plan['office'] == office]
                if len(office_plans) > 0:
                    with st.expander(f"📍 {office} Office - {len(office_plans)} plans", expanded=True):
                        for idx, row in office_plans.iterrows():
                            col1, col2 = st.columns([5, 1])
                            with col1:
                                st.write(f"**{row['country']} - {row['site']}**")
                                st.caption(f"Date: {row['date']} | Status: {row['status']}")
                                st.caption(f"📦 {row['manufacturer']}: {row.get('spoortrack', 0) + row.get('gsatsolar', 0)} units")
                                if row['notes']:
                                    st.caption(f"📝 {row['notes']}")
                            with col2:
                                st.caption(f"ID: {row['event_id'][:8]}...")
        else:
            st.info("No deployment plans found in EarthRanger.")
    
    with tab2:
        st.subheader("📊 Summary: Do I Need to Order More?")
        
        total_st_in_stock = sum([stock_data[office]['spoortrack'] for office in ['Namibia', 'Kenya', 'South Africa']])
        total_gs_in_stock = sum([stock_data[office]['gsatsolar'] for office in ['Namibia', 'Kenya', 'South Africa']])
        
        total_st_ordered = sum([stock_data[office]['ordered_st'] for office in ['Namibia', 'Kenya', 'South Africa']])
        total_gs_ordered = sum([stock_data[office]['ordered_gs'] for office in ['Namibia', 'Kenya', 'South Africa']])
        
        total_st_available = total_st_in_stock + total_st_ordered
        total_gs_available = total_gs_in_stock + total_gs_ordered
        
        if deployment_plans:
            df_plan = pd.DataFrame(deployment_plans)
            total_st_needed = df_plan['spoortrack'].sum()
            total_gs_needed = df_plan['gsatsolar'].sum()
        else:
            total_st_needed = 0
            total_gs_needed = 0
        
        st_gap = max(0, total_st_needed - total_st_available)
        gs_gap = max(0, total_gs_needed - total_gs_available)
        
        # Debug Report
        with st.expander("🔍 Debug Report - Calculation Details", expanded=False):
            st.markdown("#### Stock Data")
            st.json(stock_data)
            
            st.markdown("#### Calculated Totals")
            debug_data = {
                "SpoorTrack": {
                    "In Stock": total_st_in_stock,
                    "Ordered": total_st_ordered,
                    "Available": total_st_available,
                    "Needed": total_st_needed,
                    "Gap": st_gap
                },
                "GSatSolar": {
                    "In Stock": total_gs_in_stock,
                    "Ordered": total_gs_ordered,
                    "Available": total_gs_available,
                    "Needed": total_gs_needed,
                    "Gap": gs_gap
                }
            }
            st.json(debug_data)
            
            if deployment_plans:
                st.markdown("#### Deployment Plans (Raw Data)")
                st.dataframe(df_plan)
                
                st.markdown("#### Sum Verification")
                st.write(f"**SpoorTrack column sum:** {df_plan['spoortrack'].sum()}")
                st.write(f"**GSatSolar column sum:** {df_plan['gsatsolar'].sum()}")
                st.write(f"**Total plans:** {len(df_plan)}")
                
                # Show breakdown by manufacturer
                st.markdown("#### Plans by Manufacturer")
                st.write(f"**SpoorTrack plans:** {len(df_plan[df_plan['manufacturer'] == 'SpoorTrack'])}")
                st.write(f"**GSatSolar plans:** {len(df_plan[df_plan['manufacturer'] == 'GSatSolar'])}")
                
                # Show individual values
                st.markdown("#### Individual Plan Quantities")
                for idx, row in df_plan.iterrows():
                    st.write(f"Plan {idx}: {row['site']} - Mfr: {row['manufacturer']} | ST: {row['spoortrack']} | GS: {row['gsatsolar']}")
            else:
                st.write("No deployment plans found")
        
        st.markdown("### Overall Stock Status")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### SpoorTrack")
            subcol1, subcol2, subcol3, subcol4 = st.columns(4)
            with subcol1:
                st.metric("In Stock", total_st_in_stock)
            with subcol2:
                st.metric("Ordered", total_st_ordered)
            with subcol3:
                st.metric("Needed", total_st_needed)
            with subcol4:
                if st_gap > 0:
                    st.metric("⚠️ To Order", st_gap, delta=f"-{st_gap}", delta_color="inverse")
                else:
                    surplus = total_st_available - total_st_needed
                    st.metric("✅ Surplus", surplus, delta=f"+{surplus}", delta_color="normal")
        
        with col2:
            st.markdown("#### GSatSolar")
            subcol1, subcol2, subcol3, subcol4 = st.columns(4)
            with subcol1:
                st.metric("In Stock", total_gs_in_stock)
            with subcol2:
                st.metric("Ordered", total_gs_ordered)
            with subcol3:
                st.metric("Needed", total_gs_needed)
            with subcol4:
                if gs_gap > 0:
                    st.metric("⚠️ To Order", gs_gap, delta=f"-{gs_gap}", delta_color="inverse")
                else:
                    surplus = total_gs_available - total_gs_needed
                    st.metric("✅ Surplus", surplus, delta=f"+{surplus}", delta_color="normal")
        
        st.markdown("---")
        total_gap = st_gap + gs_gap
        if total_gap == 0:
            st.success("✅ **You have enough units!** No orders needed.")
        else:
            st.error(f"⚠️ **ACTION NEEDED:** Order {total_gap} more units ({st_gap} SpoorTrack, {gs_gap} GSatSolar)")
        
        st.markdown("---")
        st.markdown("### Stock by Office")
        
        if deployment_plans:
            df_plan = pd.DataFrame(deployment_plans)
            
            for office in ['Namibia', 'Kenya', 'South Africa']:
                office_plans = df_plan[df_plan['office'] == office]
                office_stock_data = stock_data[office]
                
                st.markdown(f"#### {office}")
                
                if len(office_plans) > 0:
                    office_st_needed = office_plans['spoortrack'].sum()
                    office_gs_needed = office_plans['gsatsolar'].sum()
                else:
                    office_st_needed = 0
                    office_gs_needed = 0
                
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**SpoorTrack:** {office_stock_data['spoortrack']} in stock | {office_st_needed} needed")
                    if office_st_needed > office_stock_data['spoortrack']:
                        st.warning(f"⚠️ Short by {office_st_needed - office_stock_data['spoortrack']}")
                with col2:
                    st.write(f"**GSatSolar:** {office_stock_data['gsatsolar']} in stock | {office_gs_needed} needed")
                    if office_gs_needed > office_stock_data['gsatsolar']:
                        st.warning(f"⚠️ Short by {office_gs_needed - office_stock_data['gsatsolar']}")
        else:
            st.info("Add deployment plans to see breakdown by office.")

def er_login(username, password):
    """Create EarthRanger connection and return connection object"""
    try:
        er_io = EarthRangerIO(
            server="https://twiga.pamdas.org",
            username=username,
            password=password
        )
        # Test connection
        er_io.get_sources(limit=1)
        return er_io
    except Exception as e:
        st.error(f"Failed to connect to EarthRanger: {e}")
        return None

def authenticate_earthranger():
    """Handle EarthRanger authentication with username/password"""
    st.header("🔐 EarthRanger Authentication")
    
    st.write("Enter your EarthRanger credentials to access the unit check dashboard:")
    
    # Fixed server URL
    st.info("**Server:** https://twiga.pamdas.org")
    
    # Username and Password
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

# --- Data fetching functions ---
@st.cache_data(ttl=3600)
def get_all_sources(_username, _password):
    """Fetch all sources using ecoscope (cached for 1 hour)"""
    er = EarthRangerIO(
        server="https://twiga.pamdas.org",
        username=_username,
        password=_password
    )
    sources_df = er.get_sources()
    return sources_df

def get_last_7_days(source_id, username, password):
    """Fetch last 7 days of locations for a source using ecoscope"""
    er = EarthRangerIO(
        server="https://twiga.pamdas.org",
        username=username,
        password=password
    )
    
    since = (datetime.utcnow() - timedelta(days=7)).isoformat()
    
    try:
        # Use EarthRangerIO get_source_observations method with correct parameters
        relocations = er.get_source_observations(
            source_ids=[source_id],  # This method expects source_ids (plural) as a list
            since=since,
            include_details=True,
            relocations=False  # Get raw DataFrame instead of Relocations object
        )
        

        
        if relocations.empty:
            return pd.DataFrame()
        
        # Convert to the format we need
        points = []
        for _, row in relocations.iterrows():
            # Extract coordinates from geometry (Point object)
            latitude, longitude = None, None
            if 'geometry' in row:
                try:
                    geom = row['geometry']
                    if geom is not None and hasattr(geom, 'y') and hasattr(geom, 'x'):
                        latitude = geom.y
                        longitude = geom.x
                except:
                    # Fallback to location dict if available
                    if 'location' in row and isinstance(row['location'], dict):
                        latitude = row['location'].get('latitude')
                        longitude = row['location'].get('longitude')
            
            point = {
                'datetime': row['recorded_at'],
                'latitude': latitude,
                'longitude': longitude
            }
            
            # Extract battery data - check multiple sources
            battery_found = False
            
            # First check observation_details (most direct)
            if 'observation_details' in row:
                obs_details = row['observation_details']
                if obs_details is not None and isinstance(obs_details, dict):
                    battery_fields = ['voltage', 'battery', 'batt', 'batt_perc', 'bat_soc']
                    for field in battery_fields:
                        if field in obs_details:
                            point['battery'] = obs_details[field]
                            battery_found = True
                            break
            
            # If not found, check device_status_properties
            if not battery_found and 'device_status_properties' in row:
                device_status = row['device_status_properties']
                # Check if device_status is not null and not empty
                if device_status is not None and device_status != [] and device_status != '':
                    if isinstance(device_status, list):
                        for item in device_status:
                            if isinstance(item, dict) and 'label' in item and 'value' in item:
                                label = item['label'].lower()
                                # Look for voltage, battery, batt, or bat_soc
                                if any(battery_term in label for battery_term in ['voltage', 'battery', 'batt', 'bat_soc']):
                                    point['battery'] = item['value']
                                    battery_found = True
                                    break
            
            points.append(point)
        
        return pd.DataFrame(points)
        
    except Exception as e:
        st.error(f"Error fetching observations: {e}")
        import traceback
        st.code(traceback.format_exc())
        return pd.DataFrame()

def unit_dashboard():
    """Main unit check dashboard interface"""
    
    # Create main tabs in the dashboard
    main_tab1, main_tab2 = st.tabs(["🔍 Unit Check", "📊 Deployment Planning"])
    
    with main_tab1:
        unit_check_tab()
    
    with main_tab2:
        # Create EarthRanger connection for deployment planning
        username = st.session_state.username
        password = st.session_state.password
        er_io = er_login(username, password)
        if er_io:
            deployment_planning_dashboard(er_io)
        else:
            st.error("⚠️ Cannot load deployment planning without EarthRanger connection")
            st.info("Please check your credentials and try again")

def unit_check_tab():
    """Unit check functionality"""
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
    
    # Filter to only tracking-device sources
    df_sources = df_sources[df_sources['source_type'] == 'tracking-device']
    
    if df_sources.empty:
        st.warning("No tracking device sources found.")
        return
    
    # First filter by manufacturer - default to SpoorTrack (case insensitive)
    manufacturers = ['All'] + sorted(df_sources['provider'].dropna().unique().tolist())
    
    # Find SpoorTrack with case-insensitive search
    spoortrack_match = None
    for manufacturer in manufacturers:
        if manufacturer.lower() == "spoortrack":
            spoortrack_match = manufacturer
            break
    
    # Set SpoorTrack as default if it exists (using the actual case from data)
    default_manufacturer = spoortrack_match if spoortrack_match else "All"
    default_index = manufacturers.index(default_manufacturer)
    
    selected_manufacturer = st.selectbox("Select a manufacturer", manufacturers, 
                                       index=default_index)
    
    # Filter by manufacturer if not "All"
    if selected_manufacturer != 'All':
        df_sources = df_sources[df_sources['provider'] == selected_manufacturer]
    
    # Use collar_key for the dropdown label (fallback to id if missing)
    df_sources['label'] = df_sources['collar_key'].fillna(df_sources['id']).astype(str)
    # Sort alphanumerically by label
    df_sources = df_sources.sort_values('label')
    
    # Multi-select for sources
    selected_labels = st.multiselect(
        "Select sources (you can select multiple)", 
        df_sources['label'].tolist(),
        default=[df_sources['label'].iloc[0]] if len(df_sources) > 0 else []
    )
    
    if not selected_labels:
        st.warning("Please select at least one source.")
        return
    
    selected_source_ids = df_sources[df_sources['label'].isin(selected_labels)]['id'].tolist()
    
    # Create a color mapping for the selected sources
    colors = px.colors.qualitative.Set1
    color_map = {label: colors[i % len(colors)] for i, label in enumerate(selected_labels)}
    
    # Separator between filter and activity sections
    st.markdown("---")
    
    # Last 7 days combined chart
    st.subheader("📊 Activity (last 7 days)")
    
    all_7_day_data = []
    all_battery_data = []
    
    try:
        with st.spinner("Fetching 7-day location data..."):
            for i, source_id in enumerate(selected_source_ids):
                source_label = selected_labels[i]
                try:
                    df_7 = get_last_7_days(source_id, username, password)
                except Exception as e:
                    st.warning(f"Could not fetch data for {source_label}: {e}")
                    continue
                
                if not df_7.empty:
                    df_7['date'] = pd.to_datetime(df_7['datetime']).dt.date
                    counts = df_7.groupby('date').size().reset_index(name='count')
                    counts['source'] = source_label
                    all_7_day_data.append(counts)
                    
                    # Collect battery data if available
                    if 'battery' in df_7.columns:
                        # Convert battery values to numeric, handling any non-numeric values
                        df_7['battery_numeric'] = pd.to_numeric(df_7['battery'], errors='coerce')
                        
                        # Only proceed if we have valid numeric battery values
                        if df_7['battery_numeric'].notna().any():
                            battery_data = df_7.groupby('date')['battery_numeric'].mean().reset_index()
                            battery_data = battery_data.rename(columns={'battery_numeric': 'battery'})
                            battery_data['source'] = source_label
                            all_battery_data.append(battery_data)
    except Exception as e:
        st.error(f"Error fetching activity data: {e}")
        st.info("The Deployment Planning tab doesn't require EarthRanger connection and will still work.")
    
    # Create two columns for charts
    col1, col2 = st.columns(2)
    
    with col1:
        if all_7_day_data:
            combined_df = pd.concat(all_7_day_data, ignore_index=True)
            
            # Create a plotly bar chart with different colors for each source
            fig = px.bar(
                combined_df,
                x='date',
                y='count',
                color='source',
                title="Daily location counts",
                barmode='group'
            )
            
            # Determine manufacturer type based on selected manufacturer
            # Add reference lines for expected daily location counts
            if selected_manufacturer.lower() in ['spoortrack', 'savannah tracking', 'savannah_tracking_provider']:
                # SpoorTrack and Savannah: good activity at 24 locations/day
                fig.add_hline(
                    y=24, 
                    line_dash="dash", 
                    line_color="green",
                    annotation_text="Good (24/day)",
                    annotation_position="top right",
                    annotation_font_color="green"
                )
            elif selected_manufacturer.lower() in ['gsatsolar', 'ceres']:
                # GSatSolar and Ceres: good activity at 3 locations/day
                fig.add_hline(
                    y=3, 
                    line_dash="dash", 
                    line_color="green",
                    annotation_text="Good (3/day)",
                    annotation_position="top right",
                    annotation_font_color="green"
                )
            elif selected_manufacturer == 'All':
                # When "All" is selected, check the actual sources in the data
                sources_in_data = combined_df['source'].unique()
                # Get the manufacturer for each source from the original data
                source_manufacturers = df_sources[df_sources['label'].isin(selected_labels)]['provider'].unique()
                
                # If all sources are voltage-type manufacturers, use 24
                voltage_manufacturers = ['spoortrack', 'savannah tracking', 'savannah_tracking_provider']
                percentage_manufacturers = ['gsatsolar', 'ceres']
                
                if all(mfg.lower() in voltage_manufacturers for mfg in source_manufacturers):
                    fig.add_hline(y=24, line_dash="dash", line_color="green", 
                                annotation_text="Good (24/day)", annotation_position="top right",
                                annotation_font_color="green")
                elif all(mfg.lower() in percentage_manufacturers for mfg in source_manufacturers):
                    fig.add_hline(y=3, line_dash="dash", line_color="green", 
                                annotation_text="Good (3/day)", annotation_position="top right",
                                annotation_font_color="green")
                # For mixed manufacturers, don't add a reference line
            
            fig.update_layout(
                xaxis_title="Date", 
                yaxis_title="Number of locations",
                xaxis=dict(tickformat='%Y-%m-%d')
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No locations in the last 7 days for any selected sources.")
    
    with col2:
        if all_battery_data:
            battery_df = pd.concat(all_battery_data, ignore_index=True)
            
            # Determine battery type based on values (voltage vs percentage)
            max_battery = battery_df['battery'].max()
            min_battery = battery_df['battery'].min()
            
            # If values are in range 3-5, it's voltage; if 6-100, it's percentage
            is_voltage = max_battery <= 5.0 and min_battery >= 3.0
            is_percentage = max_battery > 10 and max_battery <= 100
            
            # Create battery level chart
            fig_battery = px.line(
                battery_df,
                x='date',
                y='battery',
                color='source',
                title="Average daily battery",
                markers=True
            )
            
            # Add reference line for "good" battery level and set y-axis limits
            if is_voltage:
                # For voltage (SpoorTrack, Savannah): good level at 3.9V
                fig_battery.add_hline(
                    y=3.9, 
                    line_dash="dash", 
                    line_color="green",
                    annotation_text="Good (3.9V)",
                    annotation_position="bottom right",
                    annotation_font_color="green"
                )
                y_title = "Battery voltage (V)"
                y_range = [3.2, 4.2]
            elif is_percentage:
                # For percentage (GSatSolar, Ceres): good level at 80%
                fig_battery.add_hline(
                    y=80, 
                    line_dash="dash", 
                    line_color="green",
                    annotation_text="Good (80%)",
                    annotation_position="bottom right",
                    annotation_font_color="green"
                )
                y_title = "Battery level (%)"
                y_range = [0, 100]
            else:
                # Unknown type, use generic label and auto-range
                y_title = "Battery Level"
                y_range = None
            
            fig_battery.update_layout(
                xaxis_title="Date",
                yaxis_title=y_title,
                xaxis=dict(tickformat='%Y-%m-%d'),
                yaxis=dict(range=y_range) if y_range else {}
            )
            st.plotly_chart(fig_battery, use_container_width=True)
        else:
            st.info("No battery data available for selected sources.")
    
    # Separator between activity and last location sections
    st.markdown("---")
    
    # Last location map for all selected sources
    st.subheader("🗺️ Last location")
    
    last_locations = []
    
    try:
        with st.spinner("Getting last locations..."):
            for i, source_id in enumerate(selected_source_ids):
                source_label = selected_labels[i]
                try:
                    df_7 = get_last_7_days(source_id, username, password)
                except Exception as e:
                    st.warning(f"Could not fetch location for {source_label}: {e}")
                    continue
                
                if not df_7.empty and 'latitude' in df_7.columns and 'longitude' in df_7.columns:
                    # Sort by datetime and get the most recent location
                    df_sorted = df_7.sort_values('datetime', ascending=False)
                    last_location = df_sorted.iloc[0]
                    
                    location_data = {
                        'source': source_label,
                        'latitude': last_location['latitude'],
                        'longitude': last_location['longitude'],
                        'datetime': last_location['datetime'],
                        'color': color_map[source_label]
                    }
                    
                    # Add battery info if available
                    battery_value = last_location.get('battery')
                    if 'battery' in df_7.columns and battery_value is not None:
                        location_data['battery'] = battery_value
                    
                    last_locations.append(location_data)
    except Exception as e:
        st.error(f"Error fetching location data: {e}")
    
    if last_locations:
        last_locations_df = pd.DataFrame(last_locations)
        
        # Prepare hover data - only include battery if it exists
        hover_data = {'datetime': True, 'latitude': ':.6f', 'longitude': ':.6f'}
        if 'battery' in last_locations_df.columns:
            hover_data['battery'] = True
        
        # Create map with last locations only
        fig_map = px.scatter_mapbox(
            last_locations_df,
            lat='latitude',
            lon='longitude',
            color='source',
            hover_data=hover_data,
            title="Last known locations",
            mapbox_style='open-street-map',
            height=500,
            size_max=15
        )
        
        # Make markers larger
        fig_map.update_traces(marker=dict(size=12))
        
        # Center map on all last locations
        fig_map.update_layout(
            mapbox=dict(
                center=dict(
                    lat=last_locations_df['latitude'].mean(),
                    lon=last_locations_df['longitude'].mean()
                ),
                zoom=8
            )
        )
        
        st.plotly_chart(fig_map, use_container_width=True)
        
        # Show last location details in a table
        st.subheader("📍 Last location details")
        display_columns = ['source', 'datetime', 'latitude', 'longitude']
        display_df = last_locations_df[display_columns].copy()
        
        if 'battery' in last_locations_df.columns:
            display_df['battery'] = last_locations_df['battery']
            
        display_df['datetime'] = pd.to_datetime(display_df['datetime']).dt.strftime('%Y-%m-%d %H:%M:%S')
        st.dataframe(display_df, use_container_width=True)
        
    else:
        st.info("No location data available for mapping.")
    
    # Show summary statistics
    if all_7_day_data:
        combined_df = pd.concat(all_7_day_data, ignore_index=True)
        total_locations = combined_df['count'].sum()
        avg_daily = combined_df.groupby('source')['count'].mean()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total locations (7 days)", total_locations)
        with col2:
            st.metric("Average daily locations", f"{avg_daily.mean():.1f}")
        with col3:
            st.metric("Sources reporting", len(selected_labels))
    
    # Separator before unit update events section
    st.markdown("---")
    
    # Unit Update Events section
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
            # Fetch ALL events with category=monitoring and type=unit_update (UUID)
            # No date filters - fetch all historical events
            events_df = er.get_events(
                event_category='monitoring',
                event_type='7bb99e0c-9d37-405b-b8e7-edca8e9b5d6b',
                include_details=True,
                since=None,  # No date restriction
                until=None   # No date restriction
            )
            
            if events_df.empty:
                st.info("No unit update events found in the system.")
                return
            
            # Filter events to only those associated with the selected sources
            # Source IDs are in the 'event_details' field (unitupdate_subject or unitupdate_unitid)
            filtered_events = []
            
            for _, event in events_df.iterrows():
                # Check event_details for unitupdate_subject or unitupdate_unitid
                event_details = event.get('event_details')
                
                if event_details:
                    # Parse event_details if it's a string
                    if isinstance(event_details, str):
                        try:
                            import json
                            event_details = json.loads(event_details)
                        except:
                            continue
                    
                    if isinstance(event_details, dict):
                        # Check both unitupdate_subject and unitupdate_unitid
                        subject_id = event_details.get('unitupdate_subject')
                        unit_id = event_details.get('unitupdate_unitid')
                        
                        # Match against selected source IDs
                        matched_id = None
                        if subject_id in source_ids:
                            matched_id = subject_id
                        elif unit_id in source_ids:
                            matched_id = unit_id
                        
                        if matched_id:
                            # Add source label for display
                            event_copy = event.to_dict()
                            source_idx = source_ids.index(matched_id)
                            event_copy['source_label'] = source_labels[source_idx]
                            event_copy['matched_field'] = 'unitupdate_subject' if subject_id == matched_id else 'unitupdate_unitid'
                            filtered_events.append(event_copy)
                            continue
                
                # Fallback: Also check related_subjects (in case some events use it)
                related_subjects = event.get('related_subjects', [])
                if isinstance(related_subjects, list):
                    for subject in related_subjects:
                        if isinstance(subject, dict):
                            subject_id = subject.get('id') or subject.get('subject_id')
                            if subject_id in source_ids:
                                event_copy = event.to_dict()
                                source_idx = source_ids.index(subject_id)
                                event_copy['source_label'] = source_labels[source_idx]
                                event_copy['matched_field'] = 'related_subjects'
                                filtered_events.append(event_copy)
                                break
            
            if not filtered_events:
                st.warning("No unit update events found for the selected sources.")
                return
            
            # Convert to DataFrame
            filtered_df = pd.DataFrame(filtered_events)
            
            # Show summary table
            st.subheader("📊 Events Summary")
            
            # Build summary with additional fields from event_details
            summary_data = []
            for _, event in filtered_df.iterrows():
                row = {
                    'Source': event.get('source_label', ''),
                    'Time': pd.to_datetime(event.get('time')).strftime('%Y-%m-%d %H:%M:%S') if event.get('time') else '',
                    'Serial #': event.get('serial_number', ''),
                    'State': event.get('state', '')
                }
                
                # Extract fields from event_details
                event_details = event.get('event_details')
                if event_details:
                    if isinstance(event_details, str):
                        try:
                            import json
                            event_details = json.loads(event_details)
                        except:
                            pass
                    
                    if isinstance(event_details, dict):
                        row['Action'] = event_details.get('unitupdate_action', '')
                        row['Notes'] = event_details.get('unitupdate_notes', '')
                        row['Country'] = event_details.get('unitupdate_country', '')
                
                summary_data.append(row)
            
            if summary_data:
                summary_df = pd.DataFrame(summary_data)
                st.dataframe(summary_df, use_container_width=True)
            
        except Exception as e:
            st.error(f"Error fetching unit update events: {e}")
            import traceback
            st.code(traceback.format_exc())

def _main_implementation():
    """Main application logic"""
    init_session_state()
    
    # Header with logo
    with st.container():
        st.title("🔍 Unit Check Dashboard")
        st.markdown("Monitor GPS tracking units (7 day activity/battery, and last location)")
    
    # Landing page (only shown if not authenticated yet)
    if not st.session_state.authenticated:
        # Show authentication directly on landing page
        authenticate_earthranger()
        return
    
    # Sidebar navigation
    st.sidebar.title("Navigation")
    
    # Authentication status
    st.sidebar.markdown("### 🔐 Authentication ✅")
    if st.session_state.get('username'):
        st.sidebar.write(f"**User:** {st.session_state.username}")
        st.sidebar.write("**Server:** https://twiga.pamdas.org")
    
    # Show dashboard with tabs
    unit_dashboard()
    
    # Sidebar options
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔧 Options")
    
    if st.sidebar.button("🔄 Refresh Data"):
        # Clear cached data
        get_all_sources.clear()
        st.rerun()
    
    if st.sidebar.button("🔓 Logout"):
        # Clear authentication
        for key in ['authenticated', 'username', 'password']:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

# Make main() available for import while still allowing direct execution
if __name__ == "__main__":
    main()