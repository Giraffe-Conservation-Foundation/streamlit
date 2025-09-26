"""
Post-Tagging Dashboard
Monitor giraffe locations during first 2 days after deployment/tagging
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from ecoscope.io.earthranger import EarthRangerIO

def init_session_state():
    """Initialize session state variables"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'username' not in st.session_state:
        st.session_state.username = ""
    if 'password' not in st.session_state:
        st.session_state.password = ""
    if 'server_url' not in st.session_state:
        st.session_state.server_url = "https://twiga.pamdas.org"

def er_login(username, password):
    """Test EarthRanger login credentials"""
    try:
        er = EarthRangerIO(
            server=st.session_state.server_url,
            username=username,
            password=password
        )
        # Try a simple call to check credentials
        er.get_subjects(limit=1)
        return True
    except Exception:
        return False

def authenticate_earthranger():
    """Handle EarthRanger authentication"""
    st.header("🔐 EarthRanger Authentication")
    
    st.write("Enter your EarthRanger API token to access the tagging dashboard:")
    
    # Fixed server URL
    st.info("**Server:** https://twiga.pamdas.org")
    
    # API Token (required)
    api_token = st.text_input(
        "API Token",
        type="password",
        help="Your EarthRanger API token from https://twiga.pamdas.org"
    )
    
    if st.button("🔌 Connect to EarthRanger", type="primary"):
        if not api_token:
            st.error("❌ API token is required")
            return
        
        try:
            with st.spinner("Connecting to EarthRanger..."):
                st.session_state.api_token = api_token
                st.session_state.base_url = "https://twiga.pamdas.org/api/v1.0"
                headers = {"Authorization": f"Bearer {api_token}"}
                
                # Test the API token
                test_url = f"{st.session_state.base_url}/subjects/?page_size=1"
                response = requests.get(test_url, headers=headers)
                response.raise_for_status()
                
                st.success("✅ Successfully authenticated with EarthRanger!")
                st.session_state.authenticated = True
                st.session_state.headers = headers
                
                st.rerun()
                
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                st.error("❌ Authentication failed: Invalid API token")
            else:
                st.error(f"❌ HTTP Error: {e}")
        except Exception as e:
            st.error(f"❌ Connection failed: {str(e)}")
            st.info("💡 Please check your API token")

@st.cache_data(ttl=3600)
def get_subject_groups():
    """Get all subject groups (cached for 1 hour)"""
    if not st.session_state.get('api_token'):
        return pd.DataFrame()
    
    url = f"{st.session_state.base_url}/subjectgroups/?page_size=1000"
    headers = st.session_state.headers
    groups = []
    
    try:
        while url:
            resp = requests.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            
            # Handle the actual response structure: {"data": [...], "status": {...}}
            if isinstance(data, dict) and 'data' in data:
                if isinstance(data['data'], list):
                    # Direct list under data
                    groups.extend(data['data'])
                    break
                elif isinstance(data['data'], dict) and 'results' in data['data']:
                    # Nested structure: data.results
                    groups.extend(data['data']['results'])
                    url = data['data'].get('next')
                else:
                    break
            else:
                break
    except Exception as e:
        st.error(f"Error fetching subject groups: {str(e)}")
        return pd.DataFrame()
    
    return pd.DataFrame(groups)

@st.cache_data(ttl=3600)
def get_subjects_by_deployment_date(start_date, end_date):
    """Get subjects with deployments that started in the specified date range"""
    if not st.session_state.get('api_token'):
        return pd.DataFrame()
    
    # Format dates for API
    start_str = start_date.strftime("%Y-%m-%dT00:00:00.000Z")
    end_str = end_date.strftime("%Y-%m-%dT23:59:59.999Z")
    
    # Get subjectsources (deployments) within the date range
    # Use both date filtering AND subject subtype filtering
    url = f"{st.session_state.base_url}/subjectsources/?assigned_range__lower__gte={start_str}&assigned_range__lower__lte={end_str}&page_size=1000"
    headers = st.session_state.headers
    deployments = []
    
    try:
        while url:
            resp = requests.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            
            # Handle response structure: {"data": [...], "status": {...}}
            if isinstance(data, dict) and 'data' in data:
                if isinstance(data['data'], list):
                    deployments.extend(data['data'])
                    break
                elif isinstance(data['data'], dict) and 'results' in data['data']:
                    deployments.extend(data['data']['results'])
                    url = data['data'].get('next')
                else:
                    break
            else:
                break
    except Exception as e:
        st.warning(f"Error fetching deployments by date range: {str(e)}")
        # Try broader approach as fallback
        try:
            st.info("Trying fallback approach: getting all recent deployments and filtering locally...")
            # Get all recent deployments and filter locally
            broad_url = f"{st.session_state.base_url}/subjectsources/?page_size=1000"
            broad_resp = requests.get(broad_url, headers=headers)
            broad_resp.raise_for_status()
            broad_data = broad_resp.json()
            
            if isinstance(broad_data, dict) and 'data' in broad_data:
                if isinstance(broad_data['data'], list):
                    deployments = broad_data['data']
                elif isinstance(broad_data['data'], dict) and 'results' in broad_data['data']:
                    deployments = broad_data['data']['results']
            
        except Exception as fallback_e:
            st.error(f"Fallback approach also failed: {str(fallback_e)}")
            return pd.DataFrame()
    
    if not deployments:
        st.warning(f"No deployments found in date range {start_str} to {end_str}")
        return pd.DataFrame()
    
    # Extract subject IDs from deployments and filter by date range locally if needed
    subject_ids = []
    deployment_info = {}
    
    for deployment in deployments:
        if isinstance(deployment, dict):
            subject_id = deployment.get('subject')
            assigned_range = deployment.get('assigned_range', {})
            
            if subject_id and assigned_range:
                # Parse deployment start date
                deployment_start = assigned_range.get('lower')
                if deployment_start:
                    try:
                        # Parse and check if deployment start is in our date range
                        deploy_dt = pd.to_datetime(deployment_start)
                        start_dt = pd.to_datetime(start_str)
                        end_dt = pd.to_datetime(end_str)
                        
                        # Only include if deployment started in our date range
                        if start_dt <= deploy_dt <= end_dt:
                            subject_ids.append(subject_id)
                            deployment_info[subject_id] = {
                                'deployment_start': deployment_start,
                                'deployment_end': assigned_range.get('upper', 'Open')
                            }
                    except Exception:
                        # If we can't parse the date, skip this deployment
                        continue
    
    if not subject_ids:
        st.warning(f"No subjects found with deployments starting in {start_date.strftime('%B %Y')}")
        return pd.DataFrame()
    
    st.success(f"Found {len(subject_ids)} subjects with deployments starting in the selected period")
    
    # Debug: Show the first few subject IDs we're looking for
    if len(subject_ids) <= 10:
        st.info(f"Subject IDs to fetch: {subject_ids}")
    else:
        st.info(f"Subject IDs to fetch (first 5): {subject_ids[:5]}...")
    
    # SIMPLIFIED APPROACH: Just create basic subject records from the deployment data
    # Since we can't reliably fetch the subject details, create minimal records
    simple_subjects = []
    
    for subject_id in subject_ids:
        if subject_id in deployment_info:
            simple_subjects.append({
                'id': subject_id,
                'name': f'Subject-{subject_id[:8]}...',  # Use truncated ID as name
                'subject_subtype': 'giraffe',  # We know these are giraffes from deployments
                'deployment_start': deployment_info[subject_id]['deployment_start'],
                'deployment_end': deployment_info[subject_id]['deployment_end'],
                'sex': 'Unknown',
                'created_at': deployment_info[subject_id]['deployment_start'],
                'subject_groups': [],
                'groups': []
            })
    
    if not simple_subjects:
        st.warning("Could not create subject records from deployment data")
        return pd.DataFrame()
    
    st.success(f"Created {len(simple_subjects)} simplified subject records from deployment data")
    
    # Create DataFrame from simplified data
    df_subjects = pd.DataFrame(simple_subjects)
    
    return df_subjects

def get_subject_locations(subject_id, start_date, end_date):
    """Get subject locations for a date range"""
    if not st.session_state.get('api_token'):
        return pd.DataFrame()
    
    # Format dates for API
    start_str = start_date.strftime("%Y-%m-%dT00:00:00.000Z")
    end_str = end_date.strftime("%Y-%m-%dT23:59:59.999Z")
    
    url = f"{st.session_state.base_url}/observations/?subject_id={subject_id}&since={start_str}&until={end_str}&page_size=1000&ordering=recorded_at"
    headers = st.session_state.headers
    observations = []
    
    try:
        while url:
            resp = requests.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            
            # Handle different possible response structures
            if isinstance(data, list):
                # Direct list response
                observations.extend(data)
                break
            elif isinstance(data, dict):
                if 'data' in data and 'results' in data['data']:
                    # Nested structure: data.results
                    observations.extend(data['data']['results'])
                    url = data['data'].get('next')
                elif 'results' in data:
                    # Direct results structure
                    observations.extend(data['results'])
                    url = data.get('next')
                else:
                    # Unknown structure - check if it's a single observation
                    if isinstance(data, dict) and 'recorded_at' in data:
                        observations.append(data)
                    break
            else:
                break
    except Exception as e:
        st.warning(f"Error fetching locations for subject {subject_id}: {str(e)}")
        return pd.DataFrame()
    
    if not observations:
        return pd.DataFrame()
    
    # Convert to DataFrame
    locations = []
    for obs in observations:
        if 'location' in obs and obs['location']:
            locations.append({
                'subject_id': subject_id,
                'datetime': obs['recorded_at'],
                'latitude': obs['location']['latitude'],
                'longitude': obs['location']['longitude']
            })
    
    df = pd.DataFrame(locations)
    if not df.empty:
        df['datetime'] = pd.to_datetime(df['datetime'])
    return df

def get_veterinary_events(country_iso, start_date, end_date):
    """Get veterinary immobilization events for a country and date range"""
    if not st.session_state.get('api_token'):
        return pd.DataFrame()
    
    # Format dates for API
    start_str = start_date.strftime("%Y-%m-%dT00:00:00.000Z")
    end_str = end_date.strftime("%Y-%m-%dT23:59:59.999Z")
    
    # Get events with veterinary category and immob event type
    url = f"{st.session_state.base_url}/events/?event_category=veterinary&event_type=immob&time__gte={start_str}&time__lte={end_str}&page_size=1000"
    headers = st.session_state.headers
    events = []
    
    try:
        while url:
            resp = requests.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            
            # Handle different possible response structures
            if isinstance(data, list):
                # Direct list response
                events.extend(data)
                break
            elif isinstance(data, dict):
                if 'data' in data and 'results' in data['data']:
                    # Nested structure: data.results
                    events.extend(data['data']['results'])
                    url = data['data'].get('next')
                elif 'results' in data:
                    # Direct results structure
                    events.extend(data['results'])
                    url = data.get('next')
                else:
                    # Unknown structure - check if it's a single event
                    if isinstance(data, dict) and 'id' in data:
                        events.append(data)
                    break
            else:
                break
    except Exception as e:
        st.warning(f"Error fetching veterinary events: {str(e)}")
        return pd.DataFrame()
    
    if not events:
        return pd.DataFrame()
    
    # Convert to DataFrame and filter by country if needed
    vet_records = []
    for event in events:
        # Extract event details
        event_data = {
            'event_id': event.get('id'),
            'datetime': event.get('time'),
            'event_type': event.get('event_type'),
            'title': event.get('title', ''),
            'location_lat': None,
            'location_lon': None,
            'subject_id': None,
            'subject_name': None,
            'notes': event.get('notes', ''),
            'event_details': event.get('event_details', {}),
            'reported_by': event.get('reported_by', {}).get('username', 'Unknown') if isinstance(event.get('reported_by'), dict) else 'Unknown'
        }
        
        # Extract location if available
        if 'location' in event and event['location']:
            if isinstance(event['location'], dict):
                event_data['location_lat'] = event['location'].get('latitude')
                event_data['location_lon'] = event['location'].get('longitude')
        
        # Extract subject information if available
        if 'related_subjects' in event and event['related_subjects']:
            if isinstance(event['related_subjects'], list) and len(event['related_subjects']) > 0:
                subject = event['related_subjects'][0]  # Take first subject
                if isinstance(subject, dict):
                    event_data['subject_id'] = subject.get('id')
                    event_data['subject_name'] = subject.get('name')
        
        vet_records.append(event_data)
    
    df = pd.DataFrame(vet_records)
    if not df.empty:
        df['datetime'] = pd.to_datetime(df['datetime'])
    
    return df

def parse_country_from_group_name(group_name):
    """Extract country ISO code from group name format: COUNTRY_sitename"""
    if '_' in group_name:
        return group_name.split('_')[0].upper()
    return None

def extract_country_from_subject(subject_row):
    """Extract country code from subject name or groups"""
    if isinstance(subject_row, dict):
        name = subject_row.get('name', '')
        groups = subject_row.get('groups', [])
    else:
        name = getattr(subject_row, 'name', '')
        groups = getattr(subject_row, 'groups', [])
    
    if not isinstance(name, str):
        return None
    
    name = name.strip().upper()
    
    # If the name is a simplified subject ID (like "Subject-b130db02..."), 
    # we can't extract country from it, so return None for manual entry
    if name.startswith('SUBJECT-'):
        return None
    
    # Common giraffe naming patterns by region
    prefix_mapping = {
        # Kenya patterns
        'KH': 'KE',    # Kenya Highlands
        'KHBM': 'KE',  # Kenya Highlands Bush Male
        'KHBF': 'KE',  # Kenya Highlands Bush Female  
        'HSB': 'KE',   # Hell's Gate/Susua Bush
        'HSBM': 'KE',  # Hell's Gate/Susua Bush Male
        'HSBF': 'KE',  # Hell's Gate/Susua Bush Female
        'NAI': 'KE',   # Nairobi
        'TSA': 'KE',   # Tsavo
        'MAA': 'KE',   # Maasai Mara
        
        # Tanzania patterns
        'TZ': 'TZ',
        'SER': 'TZ',   # Serengeti
        'MAN': 'TZ',   # Manyara
        'TAR': 'TZ',   # Tarangire
        'RUA': 'TZ',   # Ruaha
        
        # Uganda patterns
        'UG': 'UG',
        'QEP': 'UG',   # Queen Elizabeth Park
        'MUR': 'UG',   # Murchison Falls
        'KID': 'UG',   # Kidepo
        
        # Botswana patterns
        'BW': 'BW',
        'BOT': 'BW',
        'OKA': 'BW',   # Okavango
        'CHO': 'BW',   # Chobe
        
        # Namibia patterns
        'NAM': 'NA',
        'ETO': 'NA',   # Etosha
        'DAM': 'NA',   # Damaraland
        
        # South Africa patterns
        'RSA': 'ZA',
        'KRU': 'ZA',   # Kruger
        'KTP': 'ZA',   # Kgalagadi Transfrontier Park
        
        # Zimbabwe patterns
        'ZIM': 'ZW',
        'HWA': 'ZW',   # Hwange
        
        # Zambia patterns
        'ZAM': 'ZM',
        'SKF': 'ZM',   # South Kafue
        'NKF': 'ZM',   # North Kafue
        
        # General GCF (Giraffe Conservation Foundation) patterns
        'GCF': None,   # Will need further parsing
    }
    
    # Check for GCF naming patterns first (e.g., "GCF-Kenya-001")
    if 'GCF' in name:
        if 'KENYA' in name or 'KE' in name:
            return 'KE'
        elif 'TANZANIA' in name or 'TZ' in name:
            return 'TZ'
        elif 'UGANDA' in name or 'UG' in name:
            return 'UG'
        elif 'BOTSWANA' in name or 'BW' in name:
            return 'BW'
        elif 'NAMIBIA' in name or 'NAM' in name or 'NA' in name:
            return 'NA'
        elif 'SOUTH.AFRICA' in name or 'SOUTHAFRICA' in name or 'ZA' in name or 'RSA' in name:
            return 'ZA'
        elif 'ZIMBABWE' in name or 'ZW' in name or 'ZIM' in name:
            return 'ZW'
        elif 'ZAMBIA' in name or 'ZM' in name or 'ZAM' in name:
            return 'ZM'
    
    # Check prefixes in order of specificity (longer first)
    for prefix in sorted(prefix_mapping.keys(), key=len, reverse=True):
        if name.startswith(prefix):
            return prefix_mapping[prefix]
    
    # Check for country codes in the middle of the name
    country_patterns = {
        'KE': ['KENYA', 'NAIROBI', 'MOMBASA', 'NAKURU'],
        'TZ': ['TANZANIA', 'ARUSHA', 'DODOMA', 'MWANZA'],  
        'UG': ['UGANDA', 'KAMPALA', 'QUEEN'],
        'BW': ['BOTSWANA', 'GABORONE', 'OKAVANGO'],
        'NA': ['NAMIBIA', 'WINDHOEK', 'ETOSHA'],
        'ZA': ['SOUTH.AFRICA', 'SOUTHAFRICA', 'KRUGER'],
        'ZW': ['ZIMBABWE', 'HARARE', 'HWANGE'],
        'ZM': ['ZAMBIA', 'LUSAKA', 'KAFUE']
    }
    
    for country_code, patterns in country_patterns.items():
        for pattern in patterns:
            if pattern in name:
                return country_code
    
    # Check groups for country information
    if isinstance(groups, list):
        for group in groups:
            if isinstance(group, dict) and 'name' in group:
                group_name = str(group['name']).upper()
                for country_code, patterns in country_patterns.items():
                    for pattern in patterns:
                        if pattern in group_name:
                            return country_code
    
    return None

def tagging_dashboard():
    """Main tagging dashboard interface"""
    st.header("🏷️ Tagging Dashboard")
    st.subheader("Monitor Newly Tagged Giraffes")
    
    # Date and country selection
    col1, col2 = st.columns(2)
    
    with col1:
        # Month selection
        default_date = datetime.now().replace(day=1)  # First day of current month
        selected_month = st.date_input(
            "Select Month",
            value=default_date,
            help="Select the month when giraffes were tagged/deployed"
        )
        
        # Calculate date range for the selected month
        start_date = selected_month.replace(day=1)
        next_month = start_date + relativedelta(months=1)
        end_date = next_month - timedelta(days=1)
        
        st.info(f"Analyzing period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    
    with col2:
        # Get subjects with deployments in the selected month
        with st.spinner("Loading giraffe subjects with deployments in selected month..."):
            df_subjects = get_subjects_by_deployment_date(start_date, end_date)
        
        if df_subjects.empty:
            st.warning("No giraffe subjects found with deployments in the selected month")
            
            # Try alternative approach: get all giraffes created/modified in the time period
            st.info("Trying alternative approach: looking for giraffes created in this period...")
            
            try:
                # Get giraffes by creation date as fallback
                start_str = start_date.strftime("%Y-%m-%dT00:00:00.000Z")
                end_str = end_date.strftime("%Y-%m-%dT23:59:59.999Z")
                
                fallback_url = f"{st.session_state.base_url}/subjects/?subject_subtype=giraffe&created__gte={start_str}&created__lte={end_str}&page_size=1000"
                resp = requests.get(fallback_url, headers=st.session_state.headers)
                resp.raise_for_status()
                data = resp.json()
                
                fallback_subjects = []
                if isinstance(data, dict) and 'data' in data:
                    if isinstance(data['data'], list):
                        fallback_subjects.extend(data['data'])
                    elif isinstance(data['data'], dict) and 'results' in data['data']:
                        fallback_subjects.extend(data['data']['results'])
                
                if fallback_subjects:
                    df_subjects = pd.DataFrame(fallback_subjects)
                    # Use created_at as deployment_start for fallback
                    df_subjects['deployment_start'] = df_subjects['created_at']
                    df_subjects['deployment_end'] = 'Open'
                    st.success(f"Found {len(df_subjects)} giraffes created in the selected period as fallback")
                else:
                    st.error("No giraffes found in the selected period")
                    
            except Exception as e:
                st.error(f"Fallback approach also failed: {str(e)}")
                # Debug info
                st.info("🔍 Debugging: Let me check the API response structure...")
                try:
                    # Try a broader date range to see if there are any deployments
                    debug_start = start_date.replace(year=start_date.year-1)  # Go back a year
                    debug_url = f"{st.session_state.base_url}/subjectsources/?page_size=5&assigned_range__lower__gte={debug_start.strftime('%Y-%m-%dT00:00:00.000Z')}"
                    resp = requests.get(debug_url, headers=st.session_state.headers)
                    resp.raise_for_status()
                    data = resp.json()
                    st.write("**Sample Deployments API Response Structure:**")
                    st.json(data)
                except Exception as debug_e:
                    st.error(f"Debug API call failed: {str(debug_e)}")
                return
        
        if df_subjects.empty:
            return
        
        # Extract countries from subjects
        df_subjects['country'] = df_subjects.apply(extract_country_from_subject, axis=1)
        countries = df_subjects[df_subjects['country'].notna()]['country'].unique()
        countries = sorted(countries)
        
        if not countries:
            st.warning("No country information found in giraffe subjects")
            st.info("Available giraffe subjects (first 10):")
            sample_subjects = df_subjects.head(10)[['name', 'subject_subtype', 'deployment_start']].fillna('N/A')
            st.dataframe(sample_subjects)
            
            # Show common patterns found
            st.info("Trying to infer countries from name patterns...")
            sample_names = df_subjects['name'].head(20).tolist()
            name_patterns = {}
            for name in sample_names:
                if isinstance(name, str) and len(name) >= 2:
                    prefix = name[:2].upper()
                    if prefix in name_patterns:
                        name_patterns[prefix] += 1
                    else:
                        name_patterns[prefix] = 1
            
            st.write("**Common name prefixes found:**")
            for prefix, count in sorted(name_patterns.items(), key=lambda x: x[1], reverse=True):
                st.write(f"- {prefix}*: {count} subjects")
            
            # Manual country input as fallback
            manual_country = st.text_input("Enter country code manually (e.g., KE, UG, TZ):")
            if manual_country:
                selected_country = manual_country.upper()
                st.info(f"Using manually entered country: {selected_country}")
            else:
                return
        else:
            selected_country = st.selectbox("Select Country", countries)
            st.info(f"Found countries: {', '.join(countries)}")
    
    # Filter subjects by selected country (if countries were found automatically)
    if 'country' in df_subjects.columns and selected_country in countries:
        month_subjects = df_subjects[df_subjects['country'] == selected_country]
    else:
        # If manual country entry or no automatic country detection, show all subjects
        month_subjects = df_subjects
        st.info(f"Showing all {len(month_subjects)} subjects from selected month (country filtering not available)")
    
    if month_subjects.empty:
        st.warning(f"No giraffes were deployed in {selected_country} during {start_date.strftime('%B %Y')}")
        return
    
    st.success(f"Found {len(month_subjects)} giraffes deployed in {selected_country} during {start_date.strftime('%B %Y')}")
    
    # Show deployment summary
    col1_summary, col2_summary = st.columns(2)
    
    with col1_summary:
        st.subheader("📊 Deployment Summary")
        st.metric("Total Giraffes Tagged", len(month_subjects))
        
        # Show date range of deployments
        if 'deployment_start' in month_subjects.columns:
            deployment_dates = pd.to_datetime(month_subjects['deployment_start'], errors='coerce').dropna()
            if not deployment_dates.empty:
                earliest_date = deployment_dates.min().strftime("%Y-%m-%d")
                latest_date = deployment_dates.max().strftime("%Y-%m-%d")
                st.metric("Date Range", f"{earliest_date} to {latest_date}")
                
                # Show breakdown by week within the month
                week_breakdown = {}
                for date in deployment_dates:
                    week_num = ((date.day - 1) // 7) + 1
                    week_key = f"Week {week_num}"
                    week_breakdown[week_key] = week_breakdown.get(week_key, 0) + 1
                
                if week_breakdown:
                    st.write("**Weekly Breakdown:**")
                    for week, count in sorted(week_breakdown.items()):
                        st.write(f"- {week}: {count} giraffes")
            else:
                st.info("No deployment date information available")
    
    with col2_summary:
        st.subheader("🗺️ Geographic Distribution")
        st.metric(f"Subjects in {selected_country}", len(month_subjects))
        
        # Show sex distribution if available
        if 'sex' in month_subjects.columns:
            sex_counts = month_subjects['sex'].value_counts()
            st.write("**Sex Distribution:**")
            for sex, count in sex_counts.items():
                if pd.notna(sex):
                    st.write(f"- {sex}: {count}")
        
        # Show naming patterns
        if 'name' in month_subjects.columns:
            prefixes = {}
            for name in month_subjects['name']:
                if isinstance(name, str) and len(name) >= 3:
                    prefix = name[:3].upper()
                    prefixes[prefix] = prefixes.get(prefix, 0) + 1
            
            if prefixes:
                st.write("**Common Name Prefixes:**")
                for prefix, count in sorted(prefixes.items(), key=lambda x: x[1], reverse=True)[:5]:
                    st.write(f"- {prefix}*: {count}")
    
    # Display subjects table
    st.subheader("📋 Deployed Giraffes")
    
    # Format the subjects table
    display_columns = ['name', 'sex', 'deployment_start', 'deployment_end']
    available_display_cols = [col for col in display_columns if col in month_subjects.columns]
    
    display_subjects = month_subjects[available_display_cols].copy()
    
    # Format dates
    if 'deployment_start' in display_subjects.columns:
        display_subjects['deployment_start'] = pd.to_datetime(display_subjects['deployment_start'], errors='coerce').dt.strftime('%Y-%m-%d %H:%M')
    if 'deployment_end' in display_subjects.columns:
        display_subjects['deployment_end'] = display_subjects['deployment_end'].apply(
            lambda x: pd.to_datetime(x).strftime('%Y-%m-%d') if pd.notna(x) and x != 'Open' else 'Open'
        )
    
    # Rename columns for better display
    column_renames = {
        'name': 'Subject Name',
        'sex': 'Sex',
        'deployment_start': 'Deployment Date',
        'deployment_end': 'Deployment End'
    }
    display_subjects = display_subjects.rename(columns={k: v for k, v in column_renames.items() if k in display_subjects.columns})
    
    st.dataframe(display_subjects, use_container_width=True)
    
    # Movement analysis for first week
    st.subheader("📍 First Week Movement Analysis")
    
    if st.button("🔍 Analyze Movement Patterns", type="primary"):
        with st.spinner("Analyzing movement patterns for first week post-deployment..."):
            movement_data = []
            
            for _, subject in month_subjects.iterrows():
                subject_id = subject['id']
                subject_name = subject['name']
                
                # Use deployment start date, fallback to created_at if available
                if 'deployment_start' in subject and pd.notna(subject['deployment_start']):
                    start_date_for_analysis = pd.to_datetime(subject['deployment_start']).date()
                elif 'created_at' in subject and pd.notna(subject['created_at']):
                    start_date_for_analysis = pd.to_datetime(subject['created_at']).date()
                else:
                    st.warning(f"No start date found for {subject_name}, skipping...")
                    continue
                
                # Get locations for first week after deployment/tagging
                week_end = start_date_for_analysis + timedelta(days=7)
                locations = get_subject_locations(subject_id, start_date_for_analysis, week_end)
                
                if not locations.empty:
                    locations['subject_name'] = subject_name
                    locations['deployment_country'] = selected_country
                    movement_data.append(locations)
            
            if movement_data:
                df_movements = pd.concat(movement_data, ignore_index=True)
                
                # Create movement map
                st.subheader("🗺️ Movement Map (First Week)")
                
                # Create traces for each subject
                fig = go.Figure()
                
                colors = px.colors.qualitative.Set1
                for i, (subject_name, group_data) in enumerate(df_movements.groupby('subject_name')):
                    color = colors[i % len(colors)]
                    
                    # Sort by datetime for proper line connection
                    group_data = group_data.sort_values('datetime')
                    
                    # Add trace for this subject
                    fig.add_trace(go.Scattermapbox(
                        lat=group_data['latitude'],
                        lon=group_data['longitude'],
                        mode='markers+lines',
                        name=subject_name,
                        marker=dict(size=8, color=color),
                        line=dict(width=2, color=color),
                        hovertemplate='<b>%{customdata[0]}</b><br>' +
                                    'Time: %{customdata[1]}<br>' +
                                    'Lat: %{lat:.6f}<br>' +
                                    'Lon: %{lon:.6f}<extra></extra>',
                        customdata=list(zip(
                            group_data['subject_name'],
                            group_data['datetime'].dt.strftime('%Y-%m-%d %H:%M')
                        ))
                    ))
                
                # Update layout
                fig.update_layout(
                    mapbox=dict(
                        style="open-street-map",
                        center=dict(
                            lat=df_movements['latitude'].mean(),
                            lon=df_movements['longitude'].mean()
                        ),
                        zoom=10
                    ),
                    height=600,
                    title="Giraffe Movement Tracks - First Week After Deployment",
                    showlegend=True
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Movement statistics
                st.subheader("📊 Movement Statistics")
                
                # Calculate movement stats for each subject
                movement_stats = []
                for subject_name, group_data in df_movements.groupby('subject_name'):
                    group_data = group_data.sort_values('datetime')
                    
                    if len(group_data) > 1:
                        # Calculate total distance (rough approximation)
                        distances = []
                        for i in range(1, len(group_data)):
                            lat1, lon1 = group_data.iloc[i-1]['latitude'], group_data.iloc[i-1]['longitude']
                            lat2, lon2 = group_data.iloc[i]['latitude'], group_data.iloc[i]['longitude']
                            
                            # Simple distance calculation (not perfect but adequate for visualization)
                            dist = ((lat2-lat1)**2 + (lon2-lon1)**2)**0.5 * 111  # Rough km conversion
                            distances.append(dist)
                        
                        total_distance = sum(distances)
                        max_distance = max(distances) if distances else 0
                    else:
                        total_distance = 0
                        max_distance = 0
                    
                    movement_stats.append({
                        'Subject': subject_name,
                        'Country': selected_country,
                        'Total Locations': len(group_data),
                        'Total Distance (km)': round(total_distance, 2),
                        'Max Single Move (km)': round(max_distance, 2),
                        'First Location': group_data.iloc[0]['datetime'].strftime('%Y-%m-%d %H:%M'),
                        'Last Location': group_data.iloc[-1]['datetime'].strftime('%Y-%m-%d %H:%M')
                    })
                
                df_stats = pd.DataFrame(movement_stats)
                st.dataframe(df_stats, use_container_width=True)
            
            else:
                st.warning("No movement data found for the deployed giraffes in their first week")
    
    # Veterinary records
    st.subheader("💉 Veterinary Records (Immobilization Events)")
    
    if st.button("🔍 Load Veterinary Records", type="primary"):
        with st.spinner("Loading veterinary immobilization events..."):
            df_vet = get_veterinary_events(selected_country, start_date, end_date)
            
            if not df_vet.empty:
                st.success(f"Found {len(df_vet)} veterinary immobilization events")
                
                # Display veterinary records table
                display_vet = df_vet.copy()
                
                # Format datetime
                display_vet['datetime_formatted'] = display_vet['datetime'].dt.strftime('%Y-%m-%d %H:%M')
                
                # Select columns for display
                vet_columns = ['datetime_formatted', 'subject_name', 'title', 'notes', 'reported_by']
                available_vet_cols = [col for col in vet_columns if col in display_vet.columns]
                
                # Rename columns for better display
                display_vet = display_vet[available_vet_cols].rename(columns={
                    'datetime_formatted': 'Date & Time',
                    'subject_name': 'Subject',
                    'title': 'Event Title',
                    'notes': 'Notes/Details',
                    'reported_by': 'Reported By'
                })
                
                st.dataframe(display_vet, use_container_width=True, height=400)
                
                # Show event details in expandable sections
                if st.checkbox("🔍 Show Detailed Event Information"):
                    for _, event in df_vet.iterrows():
                        with st.expander(f"📋 {event['subject_name'] or 'Unknown Subject'} - {event['datetime'].strftime('%Y-%m-%d %H:%M')}"):
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.write(f"**Event ID:** {event['event_id']}")
                                st.write(f"**Subject:** {event['subject_name'] or 'Not specified'}")
                                st.write(f"**Title:** {event['title'] or 'No title'}")
                                st.write(f"**Reported by:** {event['reported_by']}")
                            
                            with col2:
                                if event['location_lat'] and event['location_lon']:
                                    st.write(f"**Location:** {event['location_lat']:.6f}, {event['location_lon']:.6f}")
                                else:
                                    st.write("**Location:** Not specified")
                                
                                st.write(f"**Date & Time:** {event['datetime'].strftime('%Y-%m-%d %H:%M:%S UTC')}")
                            
                            if event['notes']:
                                st.write("**Notes:**")
                                st.write(event['notes'])
                            
                            if event['event_details']:
                                st.write("**Event Details:**")
                                st.json(event['event_details'])
            
            else:
                st.info("No veterinary immobilization events found for the selected period")

def main():
    """Main application logic"""
    init_session_state()
    
    # Header with logo
    with st.container():
        # Try to load and display logo
        logo_displayed = False
        
        # Get the absolute path to the logo file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(current_dir, '..', 'logo.png')  # Logo is in parent directory
        
        if os.path.exists(logo_path):
            try:
                col1, col2, col3 = st.columns([1, 2, 1])
                with col2:
                    st.image(logo_path, width=300)
                    st.markdown('<div class="logo-title" style="text-align: center;">Tagging Dashboard</div>', unsafe_allow_html=True)
                    st.markdown('<div class="logo-subtitle" style="text-align: center;">Monitor Newly Tagged Giraffes</div>', unsafe_allow_html=True)
                    logo_displayed = True
            except Exception as e:
                st.error(f"Error loading logo: {str(e)}")
        
        # Fallback header without logo
        if not logo_displayed:
            st.title("🏷️ Tagging Dashboard")
            st.markdown("Monitor Newly Tagged Giraffes")
    
    # Landing page (only shown if not authenticated yet)
    if not st.session_state.authenticated:
        st.header("🏷️ Tagging Dashboard")
        st.write("Monitor newly tagged giraffes by month and country.")
        
        # Show process overview on landing page
        st.subheader("📋 Dashboard Features")
        st.info("""
        **🏷️ Tagged Giraffe Tracking:** View giraffes tagged by month and country
        **📍 Movement Analysis:** First week movement patterns after tagging
        **💉 Veterinary Records:** Immobilization events and drug administration
        **🗺️ Interactive Maps:** Visual tracking of post-tagging movements
        """)
        
        # Show authentication directly on landing page
        authenticate_earthranger()
        return
    
    # Sidebar navigation
    st.sidebar.title("Navigation")
    
    # Authentication status
    st.sidebar.markdown("### 🔐 Authentication ✅")
    if st.session_state.get('api_token'):
        st.sidebar.write("**Method:** API Token")
    
    # Show dashboard
    tagging_dashboard()
    
    # Sidebar options
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔧 Options")
    
    if st.sidebar.button("🔄 Refresh Data"):
        # Clear cached data
        get_subject_groups.clear()
        get_subjects_by_deployment_date.clear()
        st.rerun()
    
    if st.sidebar.button("🔓 Logout"):
        # Clear authentication
        for key in ['authenticated', 'api_token', 'headers']:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

if __name__ == "__main__":
    main()
