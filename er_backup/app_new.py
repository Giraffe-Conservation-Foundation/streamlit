# -*- coding: utf-8 -*-
"""
ER Backup Tool - High Performance Incremental Version
Designed for large date ranges with month-by-month processing and resume capabilities.
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import json
import os
import zipfile
import io
from pathlib import Path
import warnings
import pickle
warnings.filterwarnings("ignore")

# Ecoscope imports for EarthRanger integration
try:
    from ecoscope.io.earthranger import EarthRangerIO
    ECOSCOPE_AVAILABLE = True
except ImportError:
    ECOSCOPE_AVAILABLE = False
    st.warning("Ecoscope package not available. Please install ecoscope to use this backup tool.")

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
    if 'backup_progress' not in st.session_state:
        st.session_state.backup_progress = {}
    if 'current_backup_id' not in st.session_state:
        st.session_state.current_backup_id = None

def er_login(username, password):
    """Simple login function"""
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
    """Handle EarthRanger authentication using ecoscope"""
    if not ECOSCOPE_AVAILABLE:
        st.error("❌ Ecoscope package is required but not available. Please install ecoscope.")
        return
        
    st.title("🔐 Login to ER Backup Tool - High Performance")
    st.info("**Server:** https://twiga.pamdas.org")
    
    username = st.text_input("EarthRanger Username")
    password = st.text_input("EarthRanger Password", type="password")
    
    if st.button("Login"):
        if er_login(username, password):
            st.session_state.authenticated = True
            st.session_state.username = username
            st.session_state.password = password
            st.success("Login successful!")
            st.rerun()
        else:
            st.error("Invalid credentials. Please try again.")
    st.stop()

def generate_month_ranges(start_date, end_date):
    """Generate list of month ranges for incremental processing"""
    months = []
    current = start_date.replace(day=1)  # Start from first day of month
    
    while current <= end_date:
        # Calculate end of current month
        if current.month == 12:
            next_month = current.replace(year=current.year + 1, month=1)
        else:
            next_month = current.replace(month=current.month + 1)
        
        month_end = min(next_month - timedelta(days=1), end_date)
        
        months.append({
            'start': current,
            'end': month_end,
            'label': current.strftime('%Y-%m')
        })
        
        current = next_month
    
    return months

def save_backup_progress(backup_id, progress_data):
    """Save backup progress to disk"""
    progress_dir = Path("backup_progress")
    progress_dir.mkdir(exist_ok=True)
    
    progress_file = progress_dir / f"{backup_id}.json"
    with open(progress_file, 'w') as f:
        json.dump(progress_data, f, default=str)

def load_backup_progress(backup_id):
    """Load backup progress from disk"""
    progress_file = Path("backup_progress") / f"{backup_id}.json"
    if progress_file.exists():
        with open(progress_file, 'r') as f:
            return json.load(f)
    return None

def get_sources_and_deployments(username, password, server_url):
    """Get sources and deployments data using direct API calls (R-style)"""
    try:
        import requests
        
        # Get authentication token
        if 'er_io' not in st.session_state:
            from ecoscope.io.earthranger import EarthRangerIO
            st.session_state.er_io = EarthRangerIO(
                server=server_url,
                username=username,
                password=password
            )
        
        # Get authentication token safely
        auth_token = None
        if hasattr(st.session_state.er_io, 'auth') and hasattr(st.session_state.er_io.auth, 'token'):
            auth_token = f"Bearer {st.session_state.er_io.auth.token}"
        elif hasattr(st.session_state.er_io, '_token'):
            auth_token = f"Bearer {st.session_state.er_io._token}"
        elif hasattr(st.session_state.er_io, 'session') and hasattr(st.session_state.er_io.session, 'headers'):
            # Extract from session headers
            auth_header = st.session_state.er_io.session.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                auth_token = auth_header
        
        if not auth_token:
            # Fallback: try to authenticate directly with requests
            st.write("🔐 Getting fresh authentication token...")
            auth_url = f"{server_url}/oauth2/token/"
            auth_data = {
                'username': username,
                'password': password,
                'grant_type': 'password',
                'client_id': 'das_web_client'
            }
            auth_response = requests.post(auth_url, data=auth_data)
            if auth_response.status_code == 200:
                token_data = auth_response.json()
                auth_token = f"Bearer {token_data['access_token']}"
            else:
                raise Exception(f"Authentication failed: {auth_response.status_code}")
        
        headers = {
            'Authorization': auth_token,
            'Content-Type': 'application/json'
        }
        
        # Get sources (like your R src query)
        st.write("📡 Getting sources data...")
        sources_url = f"{server_url}/api/v1.0/sources/?page=1&page_size=4000"
        response = requests.get(sources_url, headers=headers)
        
        if response.status_code == 200:
            sources_data = response.json()
            if 'results' in sources_data:
                sources_df = pd.DataFrame(sources_data['results'])
                # Process sources like your R code
                if not sources_df.empty:
                    sources_df = sources_df.rename(columns={
                        'id': 'sourceID',
                        'manufacturer_id': 'tagID',
                        'collar_key': 'ceresID',
                        'collar_manufacturer': 'tagManufac',
                        'collar_model': 'tagModel',
                        'created_at': 'sourceCreated'
                    })
                    sources_df['sourceCreated'] = pd.to_datetime(sources_df['sourceCreated'], errors='coerce')
                    st.success(f"✅ Got {len(sources_df):,} sources")
                else:
                    sources_df = pd.DataFrame()
            else:
                sources_df = pd.DataFrame()
        else:
            st.error(f"Failed to get sources: {response.status_code}")
            sources_df = pd.DataFrame()
        
        # Get deployments/subjectsources (like your R dep query)
        st.write("🔗 Getting deployments data...")
        deployments_url = f"{server_url}/api/v1.0/subjectsources/?page=1&page_size=4000"
        response = requests.get(deployments_url, headers=headers)
        
        if response.status_code == 200:
            deployments_data = response.json()
            if 'results' in deployments_data:
                deployments_df = pd.DataFrame(deployments_data['results'])
                # Process deployments like your R code
                if not deployments_df.empty:
                    deployments_df = deployments_df.rename(columns={
                        'id': 'deployID',
                        'source': 'sourceID',
                        'subject': 'subjectID'
                    })
                    
                    # Handle assigned_range like your R code
                    if 'assigned_range' in deployments_df.columns:
                        range_data = []
                        for idx, row in deployments_df.iterrows():
                            assigned_range = row.get('assigned_range', {})
                            if isinstance(assigned_range, dict):
                                start = assigned_range.get('lower')
                                end = assigned_range.get('upper')
                            else:
                                start = end = None
                            range_data.append({
                                'deployStart': pd.to_datetime(start, errors='coerce') if start else None,
                                'deployEnd': pd.to_datetime(end, errors='coerce') if end else None
                            })
                        
                        range_df = pd.DataFrame(range_data)
                        deployments_df = pd.concat([deployments_df.reset_index(drop=True), range_df], axis=1)
                    
                    # Calculate deployment days like your R code
                    if 'deployStart' in deployments_df.columns and 'deployEnd' in deployments_df.columns:
                        deployments_df['deployDays'] = (deployments_df['deployEnd'] - deployments_df['deployStart']).dt.days
                    
                    # Handle additional comments (notes)
                    if 'additional' in deployments_df.columns:
                        notes_data = []
                        for idx, row in deployments_df.iterrows():
                            additional = row.get('additional', {})
                            if isinstance(additional, dict):
                                notes = additional.get('comments', '')
                            else:
                                notes = ''
                            notes_data.append({'notes': notes})
                        
                        notes_df = pd.DataFrame(notes_data)
                        deployments_df = pd.concat([deployments_df.reset_index(drop=True), notes_df], axis=1)
                    
                    # Remove duplicates like your R code
                    deployments_df = deployments_df.drop_duplicates(subset=['sourceID'], keep='first')
                    st.success(f"✅ Got {len(deployments_df):,} deployments")
                else:
                    deployments_df = pd.DataFrame()
            else:
                deployments_df = pd.DataFrame()
        else:
            st.error(f"Failed to get deployments: {response.status_code}")
            deployments_df = pd.DataFrame()
        
        return sources_df, deployments_df
        
    except Exception as e:
        st.error(f"Error getting sources/deployments: {str(e)}")
        return pd.DataFrame(), pd.DataFrame()

def process_deployment_notes(df):
    """Process deployment notes to extract tag placement info (like your R code)"""
    try:
        if 'notes' not in df.columns:
            return df
        
        st.write("🏷️ Processing deployment notes for tag placement details...")
        
        # Split notes by pipe character like your R separate() function
        note_columns = ['note1', 'note2', 'note3', 'note4', 'note5', 'note6']
        notes_split = df['notes'].str.split('|', expand=True, n=5)
        notes_split.columns = note_columns[:notes_split.shape[1]]
        
        # Fill missing columns
        for col in note_columns:
            if col not in notes_split.columns:
                notes_split[col] = ''
        
        df = pd.concat([df.reset_index(drop=True), notes_split], axis=1)
        
        # Extract tag placement like your R case_when logic
        placement_conditions = ['ear', 'ossicone', 'tail', 'neck', 'ankle', 'head', 'collar']
        
        def extract_tag_place(row):
            for col in note_columns:
                note_text = str(row.get(col, '')).lower()
                for placement in placement_conditions:
                    if placement in note_text:
                        return placement
            return None
        
        df['tagPlace'] = df.apply(extract_tag_place, axis=1)
        
        # Extract ear placement details
        def extract_ear_inside_outside(row):
            for col in note_columns:
                note_text = str(row.get(col, '')).lower()
                if 'inside' in note_text:
                    return 'inside'
                elif 'outside' in note_text:
                    return 'outside'
            return None
        
        def extract_ear_left_right(row):
            for col in note_columns:
                note_text = str(row.get(col, '')).lower()
                if 'right' in note_text:
                    return 'right'
                elif 'left' in note_text:
                    return 'left'
            return None
        
        df['tagPlaceEar1'] = df.apply(extract_ear_inside_outside, axis=1)
        df['tagPlaceEar2'] = df.apply(extract_ear_left_right, axis=1)
        
        # Extract age information
        def extract_age(row):
            for col in note_columns:
                note_text = str(row.get(col, '')).lower()
                if 'subadult' in note_text:
                    return 'subadult'
            return 'adult'
        
        df['subAge'] = df.apply(extract_age, axis=1)
        
        # Extract deployment end cause
        def extract_end_cause(row):
            for col in note_columns:
                note_text = str(row.get(col, '')).lower()
                if 'failed' in note_text:
                    return 'failed'
                elif 'fell off' in note_text:
                    return 'fell off'
                elif 'death' in note_text:
                    return 'death'
            return 'unknown'
        
        df['depEndCause'] = df.apply(extract_end_cause, axis=1)
        
        # Extract additional species information
        def extract_species_additional(row):
            for col in note_columns:
                note_text = str(row.get(col, ''))
                if 'Species;' in note_text:
                    return note_text
            return None
        
        df['species_additional'] = df.apply(extract_species_additional, axis=1)
        
        # Clean up note columns
        df = df.drop(columns=note_columns, errors='ignore')
        
        st.success("✅ Processed deployment notes for tag placement details")
        return df
        
    except Exception as e:
        st.warning(f"⚠️ Error processing deployment notes: {str(e)}")
        return df

def create_master_file(obs_df, sources_df, deployments_df, subjects_df, groups_df):
    """Create master file with all joins like your R code lines 1-140"""
    try:
        st.write("🔗 Creating master file with all data joins...")
        
        # Start with observations (like your R data1/data0)
        master_df = obs_df.copy()
        
        # Join with sources (like your R left_join(src1))
        if not sources_df.empty and 'source_id' in master_df.columns:
            master_df = master_df.merge(sources_df, left_on='source_id', right_on='sourceID', how='left')
            st.info("✅ Joined sources data")
        
        # Join with deployments (like your R left_join(dep1))
        if not deployments_df.empty and 'source_id' in master_df.columns:
            master_df = master_df.merge(deployments_df, left_on='source_id', right_on='sourceID', how='left', suffixes=('', '_dep'))
            st.info("✅ Joined deployments data")
        
        # Join with subjects (like your R left_join(sub1))
        if not subjects_df.empty and 'subject_id' in master_df.columns:
            # Prepare subjects data
            subjects_clean = subjects_df.rename(columns={
                'id': 'subjectID',
                'name': 'subjectName',
                'subject_subtype': 'subjectType',
                'common_name': 'subjectSpecies',
                'sex': 'subjectSex',
                'is_active': 'subjectActive',
                'last_position_date': 'subjectLastDate',
                'region': 'obsLandscape'
            })
            
            master_df = master_df.merge(subjects_clean, left_on='subject_id', right_on='subjectID', how='left', suffixes=('', '_sub'))
            st.info("✅ Joined subjects data")
        
        # Join with groups (like your R left_join(grp1))
        if not groups_df.empty and 'subject_id' in master_df.columns:
            master_df = master_df.merge(groups_df, on='subject_id', how='left', suffixes=('', '_grp'))
            st.info("✅ Joined groups data")
        
        # Filter records within deployment period (like your R filter)
        if 'recorded_at' in master_df.columns and 'deployStart' in master_df.columns and 'deployEnd' in master_df.columns:
            master_df['recorded_at'] = pd.to_datetime(master_df['recorded_at'], errors='coerce')
            initial_count = len(master_df)
            
            # Filter within deployment range
            mask = (
                (master_df['recorded_at'] >= master_df['deployStart']) & 
                (master_df['recorded_at'] <= master_df['deployEnd'])
            ) | (
                master_df['deployStart'].isna() | master_df['deployEnd'].isna()
            )
            
            master_df = master_df[mask]
            filtered_count = len(master_df)
            st.info(f"🔍 Filtered to deployment periods: {initial_count:,} → {filtered_count:,} records")
        
        # Remove duplicates (like your R distinct)
        if all(col in master_df.columns for col in ['source_id', 'recorded_at', 'longitude', 'latitude']):
            initial_count = len(master_df)
            master_df = master_df.drop_duplicates(subset=['source_id', 'recorded_at', 'longitude', 'latitude'], keep='first')
            final_count = len(master_df)
            st.info(f"🧹 Removed duplicates: {initial_count:,} → {final_count:,} records")
        
        # Process deployment notes for tag placement
        master_df = process_deployment_notes(master_df)
        
        # Clean up and standardize column names (like your R data3 section)
        master_df = standardize_master_columns(master_df)
        
        st.success(f"✅ Master file created with {len(master_df):,} records")
        return master_df
        
    except Exception as e:
        st.error(f"Error creating master file: {str(e)}")
        return obs_df

def standardize_master_columns(df):
    """Standardize column names and clean data like your R data3 section"""
    try:
        st.write("🧹 Standardizing column names and cleaning data...")
        
        # Remove unwanted columns (like your R select(-"created_at", ...))
        columns_to_remove = [
            'created_at', 'exclusion_flags', 'accuracy', 'locationAccuracy',
            'activity1', 'activity2', 'activity3', 'activity4', 'charge_status',
            'orientation', 'activity', 'activity_label', 'location_accuracy',
            'location_accuracy_label', 'GPS activity count', 'heading',
            'gps_hdop', 'event_id', 'sourceCreated', 'subjectLastDate',
            'location', 'device_status_properties',  # Remove these unwanted columns
            'additional', 'content_type', 'created_at_sub', 'device_status_properties_sub',
            'hex', 'image_url', 'last_position', 'last_position_status', 'source_id',
            'subjectActive', 'subjectName', 'subjectID', 'subjectSex', 'subjectSpecies',
            'subjectType', 'tracks_available', 'user', 'updated_at'
        ]
        
        for col in columns_to_remove:
            if col in df.columns:
                df = df.drop(columns=[col])
        
        # Filter out rangers and mobile devices (like your R filter)
        if 'subjectType' in df.columns:
            df = df[~df['subjectType'].isin(['ranger', 'er_mobile'])]
        
        # Consolidate battery voltage columns (like your R coalesce)
        battery_voltage_cols = ['battery_volts', 'batt', 'voltage', 'tag_voltage']
        battery_percentage_cols = ['battery_percentage', 'battery_percent', 'bat_soc']
        
        # Get available battery voltage columns
        available_voltage_cols = [col for col in battery_voltage_cols if col in df.columns]
        if available_voltage_cols:
            # Create consolidated battery voltage column using the first available column
            df['srcBatt_v'] = df[available_voltage_cols[0]]
            # Remove original battery voltage columns except the first one we used
            for col in available_voltage_cols:
                if col in df.columns:
                    df = df.drop(columns=[col])
        
        # Get available battery percentage columns  
        available_percentage_cols = [col for col in battery_percentage_cols if col in df.columns]
        if available_percentage_cols:
            # Create consolidated battery percentage column using the first available column
            df['srcBatt_p'] = df[available_percentage_cols[0]]
            # Remove original battery percentage columns
            for col in available_percentage_cols:
                if col in df.columns:
                    df = df.drop(columns=[col])
        
        # Rename columns to match your R naming convention
        column_mapping = {
            'id': 'obsID',
            'recorded_at': 'obsDatetime',
            'country': 'obsCountry',
            'source': 'srcID',
            'deployment_id': 'movebank_depID',
            'tag_local_identifier': 'tagID',
            'tag_id': 'movebank_tagID',
            'latitude': 'obsLat',
            'longitude': 'obsLon',
            'subject_id': 'subID',
            'subject_name': 'subName',
            'subject_type': 'subType',
            'subjectType': 'subGenus',
            'species': 'subSpecies',
            'subject_sex': 'subSex',
            'subject_active': 'subActive',
            'case_temperature_c': 'srcTemp_case_c',
            'device_temperature_c': 'srcTemp_unit_c',
            'temperature': 'srcTemp'
        }
        
        # Apply column renaming
        for old_name, new_name in column_mapping.items():
            if old_name in df.columns:
                df = df.rename(columns={old_name: new_name})
        
        # Ensure proper data types
        datetime_cols = ['obsDatetime', 'depStart', 'depEnd']
        for col in datetime_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        
        st.success("✅ Standardized column names and cleaned data")
        return df
        
    except Exception as e:
        st.warning(f"⚠️ Error standardizing columns: {str(e)}")
        return df

def get_all_subjects(username, password, server_url):
    """Get all subjects data using direct API calls"""
    try:
        import requests
        
        # Get authentication token
        if 'er_io' not in st.session_state:
            from ecoscope.io.earthranger import EarthRangerIO
            st.session_state.er_io = EarthRangerIO(
                server=server_url,
                username=username,
                password=password
            )
        
        # Get authentication token safely
        auth_token = None
        if hasattr(st.session_state.er_io, 'auth') and hasattr(st.session_state.er_io.auth, 'token'):
            auth_token = f"Bearer {st.session_state.er_io.auth.token}"
        elif hasattr(st.session_state.er_io, '_token'):
            auth_token = f"Bearer {st.session_state.er_io._token}"
        elif hasattr(st.session_state.er_io, 'session') and hasattr(st.session_state.er_io.session, 'headers'):
            # Extract from session headers
            auth_header = st.session_state.er_io.session.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                auth_token = auth_header
        
        if not auth_token:
            # Fallback: try to authenticate directly with requests
            st.write("🔐 Getting fresh authentication token...")
            auth_url = f"{server_url}/oauth2/token/"
            auth_data = {
                'username': username,
                'password': password,
                'grant_type': 'password',
                'client_id': 'das_web_client'
            }
            auth_response = requests.post(auth_url, data=auth_data)
            if auth_response.status_code == 200:
                token_data = auth_response.json()
                auth_token = f"Bearer {token_data['access_token']}"
            else:
                raise Exception(f"Authentication failed: {auth_response.status_code}")
        
        headers = {
            'Authorization': auth_token,
            'Content-Type': 'application/json'
        }
        
        # Get subjects
        st.write("👥 Getting subjects data...")
        subjects_url = f"{server_url}/api/v1.0/subjects/?page=1&page_size=4000&include_inactive=true"
        response = requests.get(subjects_url, headers=headers)
        
        if response.status_code == 200:
            subjects_data = response.json()
            if 'results' in subjects_data:
                subjects_df = pd.DataFrame(subjects_data['results'])
                if not subjects_df.empty:
                    st.success(f"✅ Got {len(subjects_df):,} subjects")
                    return subjects_df
                else:
                    return pd.DataFrame()
            else:
                return pd.DataFrame()
        else:
            st.error(f"Failed to get subjects: {response.status_code}")
            return pd.DataFrame()
            
    except Exception as e:
        st.error(f"Error getting subjects: {str(e)}")
        return pd.DataFrame()

def get_subject_groups(username, password, server_url):
    """Get subject groups data by processing subjects"""
    try:
        # Use cached subjects data or get fresh
        if 'subjects_df' in st.session_state:
            subjects_df = st.session_state.subjects_df
        else:
            subjects_df = get_all_subjects(username, password, server_url)
        
        if subjects_df.empty:
            return pd.DataFrame()
        
        st.write("🏷️ Processing subject groups...")
        
        # Process groups data like your R code
        groups_data = []
        for _, subject in subjects_df.iterrows():
            subject_id = subject.get('id')
            
            if 'groups' in subject and subject['groups']:
                groups = subject['groups'] if isinstance(subject['groups'], list) else [subject['groups']]
                for group in groups:
                    if isinstance(group, dict):
                        group_name = group.get('name', '')
                        country, region, species = None, None, None
                        if '_' in group_name:
                            parts = group_name.split('_', 2)
                            country = parts[0] if len(parts) > 0 else None
                            region = parts[1] if len(parts) > 1 else None
                            species = parts[2] if len(parts) > 2 else None
                        
                        groups_data.append({
                            'subject_id': subject_id,
                            'group_id': group.get('id'),
                            'group_name': group_name,
                            'country': country,
                            'region': region,
                            'species': species
                        })
        
        if groups_data:
            groups_df = pd.DataFrame(groups_data)
            # Filter out unwanted groups (like your R code)
            exclude_countries = ['AF', 'TwigaTracker', 'WildScapeVet', 'Donor', 'Movebank', 'White']
            groups_df = groups_df[
                ~groups_df['country'].isin(exclude_countries)
            ]
            st.success(f"✅ Processed {len(groups_df):,} group relationships")
            return groups_df
        else:
            return pd.DataFrame()
            
    except Exception as e:
        st.error(f"Error getting subject groups: {str(e)}")
        return pd.DataFrame()

def backup_all_observations_r_style(username, password, server_url, start_date, end_date, include_subject_details=True):
    """Backup all observations using direct API calls (R-style approach) - MUCH FASTER"""
    try:
        import requests
        from urllib.parse import quote
        
        # Format dates for API
        start_str = start_date.strftime('%Y-%m-%dT00:00:00+0000')
        end_str = end_date.strftime('%Y-%m-%dT23:59:59+0000')
        
        st.write(f"🚀 **Ultra-Fast R-Style Download**: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        
        # Get cached data or initialize ecoscope connection for other data
        if 'er_io' not in st.session_state:
            from ecoscope.io.earthranger import EarthRangerIO
            st.session_state.er_io = EarthRangerIO(
                server=server_url,
                username=username,
                password=password
            )
        
        er_io = st.session_state.er_io
        
        # Get subjects and groups data (cached)
        if include_subject_details and 'subjects_df' not in st.session_state:
            st.write("📥 Loading subject details (one-time fetch)...")
            st.session_state.subjects_df = er_io.get_subjects(include_inactive=True)
            
            # Process groups data like your R code
            if not st.session_state.subjects_df.empty:
                groups_data = []
                for _, subject in st.session_state.subjects_df.iterrows():
                    subject_id = subject.get('id')
                    
                    if 'groups' in subject and subject['groups']:
                        groups = subject['groups'] if isinstance(subject['groups'], list) else [subject['groups']]
                        for group in groups:
                            if isinstance(group, dict):
                                group_name = group.get('name', '')
                                country, region, species = None, None, None
                                if '_' in group_name:
                                    parts = group_name.split('_', 2)
                                    country = parts[0] if len(parts) > 0 else None
                                    region = parts[1] if len(parts) > 1 else None
                                    species = parts[2] if len(parts) > 2 else None
                                
                                groups_data.append({
                                    'subject_id': subject_id,
                                    'group_id': group.get('id'),
                                    'group_name': group_name,
                                    'country': country,
                                    'region': region,
                                    'species': species
                                })
                
                if groups_data:
                    st.session_state.groups_df = pd.DataFrame(groups_data)
                    # Filter out unwanted groups (like your R code)
                    exclude_countries = ['AF', 'TwigaTracker', 'WildScapeVet', 'Donor', 'Movebank', 'White']
                    st.session_state.groups_df = st.session_state.groups_df[
                        ~st.session_state.groups_df['country'].isin(exclude_countries)
                    ]
                else:
                    st.session_state.groups_df = pd.DataFrame()
        
        # Use direct API calls exactly like your R code - MAXIMUM SPEED!
        st.write(f"🚀 Starting ultra-fast direct API download (R-style with cursor pagination)...")
        
        try:
            # Get authentication token from ecoscope session
            # EarthRangerIO stores the token in the auth property
            if hasattr(er_io, 'auth') and hasattr(er_io.auth, 'token'):
                auth_token = f"Bearer {er_io.auth.token}"
            elif hasattr(er_io, '_token'):
                auth_token = f"Bearer {er_io._token}"
            elif hasattr(er_io, 'session') and hasattr(er_io.session, 'headers'):
                # Extract from session headers
                auth_header = er_io.session.headers.get('Authorization', '')
                if auth_header.startswith('Bearer '):
                    auth_token = auth_header
                else:
                    raise Exception("Could not find authentication token in EarthRangerIO session")
            else:
                # Fallback: try to authenticate directly with requests
                st.write("🔐 Getting fresh authentication token...")
                auth_url = f"{server_url}/oauth2/token/"
                auth_data = {
                    'username': username,
                    'password': password,
                    'grant_type': 'password',
                    'client_id': 'das_web_client'
                }
                auth_response = requests.post(auth_url, data=auth_data)
                if auth_response.status_code == 200:
                    token_data = auth_response.json()
                    auth_token = f"Bearer {token_data['access_token']}"
                else:
                    raise Exception(f"Authentication failed: {auth_response.status_code}")
            
            # URL encode the dates
            since_encoded = quote(start_str, safe='')
            until_encoded = quote(end_str, safe='')
            
            # Initial API call with cursor pagination (exactly like your R code)
            base_url = f"{server_url}/api/v1.0/observations/"
            url = f"{base_url}?page_size=4000&use_cursor=true&since={since_encoded}&until={until_encoded}"
            
            headers = {
                'Authorization': auth_token,
                'Content-Type': 'application/json'
            }
            
            # Progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            all_data = []
            page_count = 0
            start_time = datetime.now()
            
            # Pagination loop exactly like your R code
            while url:
                response = requests.get(url, headers=headers)
                if response.status_code != 200:
                    st.error(f"API request failed with status {response.status_code}: {response.text}")
                    break
                
                data = response.json()
                
                if 'data' in data and 'results' in data['data']:
                    results = data['data']['results']
                    if results:
                        all_data.extend(results)
                        page_count += 1
                        
                        # Update progress
                        elapsed = datetime.now() - start_time
                        status_text.text(f"📄 Page {page_count} | Records: {len(all_data):,} | Time: {elapsed.total_seconds():.1f}s")
                        
                        # Estimate progress (rough)
                        if page_count <= 10:
                            progress_bar.progress(min(page_count / 10, 0.9))
                    
                    # Get next URL for pagination (like your R while loop)
                    url = data['data'].get('next')
                else:
                    break
            
            progress_bar.progress(1.0)
            
            if not all_data:
                st.info("ℹ️ No observations found for the selected date range")
                return pd.DataFrame(), 0
            
            st.success(f"🚀 Downloaded {len(all_data):,} observations in {page_count} pages using R-style direct API!")
            
            # Convert to DataFrame (like your R bind_rows)
            df = pd.DataFrame(all_data)
            
            # Handle device status properties exactly like your R code
            if 'device_status_properties' in df.columns:
                st.write("🔧 Processing device status properties (R-style)...")
                
                device_props = []
                for idx, row in df.iterrows():
                    props = row.get('device_status_properties', [])
                    prop_dict = {}
                    if isinstance(props, list):
                        for prop in props:
                            if isinstance(prop, dict):
                                label = prop.get('label', 'unknown')
                                value = prop.get('value', None)
                                units = prop.get('units', '')
                                
                                # Handle battery voltage labeling exactly like R code
                                if units == 'v':
                                    label = 'battery_volts'
                                elif label == 'battery' and units:
                                    label = units
                                
                                prop_dict[label] = value
                    device_props.append(prop_dict)
                
                # Convert to DataFrame and merge (like R pivot_wider)
                if device_props:
                    device_df = pd.DataFrame(device_props)
                    df = pd.concat([df.reset_index(drop=True), device_df], axis=1)
            
            # Handle location data (like your R unnest)
            if 'location' in df.columns:
                st.write("📍 Processing location data (R-style unnest)...")
                
                location_data = []
                for idx, row in df.iterrows():
                    location = row.get('location', {})
                    if isinstance(location, dict):
                        lat = location.get('latitude', None)
                        lon = location.get('longitude', None)
                    else:
                        lat = lon = None
                    location_data.append({'latitude': lat, 'longitude': lon})
                
                location_df = pd.DataFrame(location_data)
                df = pd.concat([df.reset_index(drop=True), location_df], axis=1)
            
            # Handle subject identification
            if 'source' in df.columns:
                st.write("🔗 Processing source/subject relationships...")
                
                # Debug: Check what the source field actually looks like
                sample_sources = df['source'].head(3).tolist()
                st.write(f"📊 Debug: Sample source field values:")
                for i, src in enumerate(sample_sources):
                    st.write(f"  Row {i}: {type(src)} = {src}")
                
                source_data = []
                for idx, row in df.iterrows():
                    source = row.get('source', {})
                    
                    # Handle different possible formats
                    if isinstance(source, dict):
                        subject_id = source.get('subject')
                        source_id = source.get('id')
                    elif isinstance(source, str):
                        # If source is just a string ID, use it as source_id and try to get subject from subjectsources
                        source_id = source
                        subject_id = None  # Will need to get from subjectsources later
                    else:
                        subject_id = source_id = None
                        
                    source_data.append({'subject_id': subject_id, 'source_id': source_id})
                
                source_df = pd.DataFrame(source_data)
                df = pd.concat([df.reset_index(drop=True), source_df], axis=1)
                
                # Debug: Check extracted IDs
                valid_subject_ids = source_df['subject_id'].notna().sum()
                valid_source_ids = source_df['source_id'].notna().sum()
                st.info(f"📊 Debug: Extracted {valid_subject_ids:,} subject IDs and {valid_source_ids:,} source IDs")
                
                # If we have source IDs but no subject IDs, try to get subjects from subjectsources
                if valid_source_ids > 0 and valid_subject_ids == 0:
                    st.write("🔍 Attempting to get subject IDs from subjectsources...")
                    
                    # Get subjectsources data to map source_id to subject_id
                    if 'subjectsources_df' not in st.session_state:
                        if 'er_io' not in st.session_state:
                            from ecoscope.io.earthranger import EarthRangerIO
                            st.session_state.er_io = EarthRangerIO(
                                server=server_url,
                                username=username,
                                password=password
                            )
                        st.session_state.subjectsources_df = st.session_state.er_io.get_subjectsources()
                    
                    subjectsources = st.session_state.subjectsources_df
                    if not subjectsources.empty:
                        # Create mapping from source_id to subject_id
                        source_to_subject = dict(zip(subjectsources['source'], subjectsources['subject']))
                        
                        # Update subject_id based on source_id
                        df['subject_id'] = df['source_id'].map(source_to_subject).fillna(df['subject_id'])
                        
                        updated_subject_ids = df['subject_id'].notna().sum()
                        st.info(f"📊 Debug: Updated to {updated_subject_ids:,} subject IDs from subjectsources")
                    else:
                        st.warning("⚠️ No subjectsources data available")
            
            # Join with subject details (like your R left_join)
            if include_subject_details and 'subjects_df' in st.session_state and 'subject_id' in df.columns:
                st.write("👥 Joining subject details (R-style left_join)...")
                
                # Debug: Check what we have
                st.info(f"📊 Debug: Found {len(st.session_state.subjects_df):,} subjects in cache")
                st.info(f"📊 Debug: Unique subject_ids in observations: {df['subject_id'].nunique():,}")
                
                subject_cols = ['id', 'name', 'subject_subtype', 'common_name', 'sex', 'is_active']
                available_subject_cols = [col for col in subject_cols if col in st.session_state.subjects_df.columns]
                
                if available_subject_cols:
                    # Check subject IDs before join
                    obs_subject_ids = set(df['subject_id'].dropna().unique())
                    subj_ids = set(st.session_state.subjects_df['id'].unique())
                    matching_ids = obs_subject_ids.intersection(subj_ids)
                    st.info(f"📊 Debug: {len(matching_ids):,} matching subject IDs found")
                    
                    subjects_renamed = st.session_state.subjects_df[available_subject_cols].rename(columns={
                        'id': 'subject_id',
                        'name': 'subject_name',
                        'subject_subtype': 'subject_type',
                        'common_name': 'species',
                        'sex': 'subject_sex',
                        'is_active': 'subject_active'
                    })
                    
                    # Perform the join
                    before_join = len(df)
                    df = df.merge(subjects_renamed, on='subject_id', how='left')
                    after_join = len(df)
                    
                    # Check if subject data was actually joined
                    subject_data_filled = df['subject_name'].notna().sum()
                    st.info(f"✅ Joined subject details: {before_join} → {after_join} records, {subject_data_filled:,} with subject data")
                else:
                    st.warning(f"⚠️ No valid subject columns found. Available: {list(st.session_state.subjects_df.columns)}")
                
                # Join with groups data
                if 'groups_df' in st.session_state and not st.session_state.groups_df.empty:
                    df = df.merge(st.session_state.groups_df, on='subject_id', how='left')
                    st.info("✅ Joined group details")
            else:
                if not include_subject_details:
                    st.info("ℹ️ Subject details not requested")
                elif 'subjects_df' not in st.session_state:
                    st.warning("⚠️ No subjects data in cache")
                elif 'subject_id' not in df.columns:
                    st.warning("⚠️ No subject_id column in observations")
                    st.info(f"Available columns: {list(df.columns)}")
            
            # Ensure proper datetime columns
            datetime_cols = ['recorded_at', 'created_at', 'time']
            for col in datetime_cols:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce')
            
            # Sort by recorded_at
            if 'recorded_at' in df.columns:
                df = df.sort_values('recorded_at')
            
            total_time = datetime.now() - start_time
            st.success(f"✅ **R-Style Ultra-Fast Download Complete!**")
            st.success(f"📊 {len(df):,} observations processed in {total_time.total_seconds():.1f} seconds")
            
            # Create master file with comprehensive joins (like your R ER_dataPull.R lines 1-140)
            st.write("🔗 Creating comprehensive master file with all data joins...")
            
            # Get additional data for master file creation
            sources_df, deployments_df = get_sources_and_deployments(username, password, server_url)
            
            # Use cached subjects and groups data
            subjects_df = st.session_state.get('subjects_df', pd.DataFrame())
            groups_df = st.session_state.get('groups_df', pd.DataFrame())
            
            # Create master file with all joins
            master_df = create_master_file(df, sources_df, deployments_df, subjects_df, groups_df)
            
            # Return only the master file, not the raw observations
            return master_df, len(df)
            
        except Exception as e:
            st.error(f"Error in R-style download: {str(e)}")
            return pd.DataFrame(), 0
            
    except Exception as e:
        st.error(f"Error in ultra-fast backup: {str(e)}")
        return pd.DataFrame(), 0

def main():
    """Main high-performance backup tool interface"""
    init_session_state()
    
    # Header with logo
    current_dir = Path(__file__).parent.parent
    logo_path = current_dir / "shared" / "logo.png"
    
    if logo_path.exists():
        try:
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.image(str(logo_path), width=300)
                st.markdown('<div style="text-align: center;"><h1>💾 ER Backup Tool</h1></div>', unsafe_allow_html=True)
                st.markdown('<div style="text-align: center;"><h3>🚀 High Performance Incremental Backup</h3></div>', unsafe_allow_html=True)
        except Exception:
            st.title("💾 ER Backup Tool - High Performance")
    else:
        st.title("💾 ER Backup Tool - High Performance")
    
    # Authentication check
    if not st.session_state.authenticated:
        authenticate_earthranger()
        return
    
    # Show authentication status
    st.sidebar.markdown("### 🔐 Authentication ✅")
    st.sidebar.write(f"**User:** {st.session_state.username}")
    
    if st.sidebar.button("🔓 Logout"):
        for key in ['authenticated', 'username', 'password', 'subjectsources_df', 'subjects_df', 'groups_df']:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()
    
    st.sidebar.markdown("---")
    
    # Main interface
    st.markdown("""
    ## 🚀 High Performance Backup for Large Date Ranges
    
    **Ultra-Fast Mode Features:**
    - 🚀 **R-Style Performance**: Uses same direct API approach as your fast R code
    - ⚡ **Cursor Pagination**: Maximum speed download
    - 🔗 **Comprehensive Data Joins**: All sources, deployments, subjects, groups
    - 📊 **Master File Output**: Single comprehensive CSV file ready for analysis
    """)
    
    # Performance comparison
    st.info("""
    🚀 **This tool mimics your R code's approach for maximum speed:**
    - Direct API calls with cursor pagination
    - Comprehensive data processing pipeline
    - All joins and transformations from your ER_dataPull.R workflow
    - Single master file output with standardized column names
    """)
    
    # Backup configuration
    st.subheader("🛠️ Backup Configuration")
    
    col1, col2 = st.columns(2)
    
    with col1:
        backup_subjectsource_obs_enabled = st.checkbox("🔗 Include SubjectSource Observations", value=True, 
                                                       help="GPS data with animal details")
        backup_events_enabled = st.checkbox("📝 Include Events/Reports", value=True,
                                           help="Field observations and incidents")
    
    with col2:
        join_subject_details = st.checkbox("📋 Include Animal Details", value=True,
                                          help="Join subject and group info",
                                          disabled=not backup_subjectsource_obs_enabled)
    
    st.info("🚀 **Ultra-Fast Mode**: Uses direct API calls with cursor pagination (like your R code) - much faster than ecoscope!")
    
    # Date range selection
    st.subheader("📅 Date Range")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        start_date = st.date_input(
            "Start Date",
            value=date(2024, 1, 1),
            min_value=date(2016, 1, 1),
            help="Start date for backup"
        )
    
    with col2:
        end_date = st.date_input(
            "End Date",
            value=date.today(),
            help="End date for backup"
        )
    
    with col3:
        # Quick date range buttons
        if st.button("📅 Last Year"):
            start_date = date.today().replace(year=date.today().year - 1, month=1, day=1)
            end_date = date.today().replace(year=date.today().year - 1, month=12, day=31)
            st.rerun()
        
        if st.button("📅 Since 2016"):
            start_date = date(2016, 1, 1)
            end_date = date.today()
            st.rerun()
    
    if start_date > end_date:
        st.error("❌ Start date cannot be after end date")
        return
    
    # Show backup scope
    total_days = (end_date - start_date).days + 1
    
    st.info(f"""
    **Backup Scope:**
    - 📅 **Date Range**: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}
    - 📊 **Total Days**: {total_days:,}
    - ⏱️ **Estimated Time**: 2-5 minutes for typical ranges
    - 💾 **Strategy**: Ultra-fast R-style bulk processing
    """)
    
    # Backup execution
    st.subheader("🚀 Execute Backup")
    
    st.info("🚀 **Ultra-Fast Mode Selected**: Will download all data at once using R-style direct API calls")
    
    if st.button("🔄 Start High Performance Backup", type="primary"):
        if not backup_subjectsource_obs_enabled and not backup_events_enabled:
            st.error("❌ Please select at least one backup option")
            return
        
        # Generate backup ID
        backup_id = f"GCF_ER_Backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        st.session_state.current_backup_id = backup_id
        
        backup_data = {}
        total_records = 0
        start_time = datetime.now()
        
        try:
            # R-STYLE ULTRA-FAST MODE - Download all data at once
            st.markdown("### 🚀 Ultra-Fast R-Style Download")
            
            if backup_subjectsource_obs_enabled:
                master_df, obs_count = backup_all_observations_r_style(
                    username=st.session_state.username,
                    password=st.session_state.password,
                    server_url=st.session_state.server_url,
                    start_date=start_date,
                    end_date=end_date,
                    include_subject_details=join_subject_details
                )
                
                if not master_df.empty:
                    backup_data['master_file'] = master_df
                    total_records += obs_count
                    
                    st.success(f"✅ Master file created with {len(master_df):,} comprehensive records")
                    
                    # Show what's in the master file
                    with st.expander("📊 Master File Details"):
                        st.write("**Master file includes:**")
                        st.write("- 🗂️ Raw observations data")
                        st.write("- 🏷️ Source/tag information (ID, manufacturer, model)")
                        st.write("- 📅 Deployment details (start/end dates, duration)")
                        st.write("- 🐘 Subject details (name, species, sex)")
                        st.write("- 🏞️ Group/landscape information")
                        st.write("- 📍 Tag placement details (extracted from notes)")
                        st.write("- 🔋 Device status and battery information")
                        st.write("- 🧹 Filtered to deployment periods only")
                        st.write("- 📏 Standardized column names matching R output")
                        
                        cols = master_df.columns.tolist()
                        st.write(f"**Total columns:** {len(cols)}")
                        st.write(f"**Key columns:** {', '.join(cols[:10])}{'...' if len(cols) > 10 else ''}")
            
            if backup_events_enabled:
                # Use ecoscope for events (usually smaller dataset)
                if 'er_io' not in st.session_state:
                    from ecoscope.io.earthranger import EarthRangerIO
                    st.session_state.er_io = EarthRangerIO(
                        server=st.session_state.server_url,
                        username=st.session_state.username,
                        password=st.session_state.password
                    )
                
                st.write("📝 Getting events...")
                events_df = st.session_state.er_io.get_events(
                    since=start_date.strftime('%Y-%m-%dT00:00:00Z'),
                    until=end_date.strftime('%Y-%m-%dT23:59:59Z'),
                    include_details=True,
                    include_notes=True
                )
                
                if not events_df.empty:
                    events_clean = pd.DataFrame(events_df.drop(columns='geometry', errors='ignore'))
                    backup_data['events'] = events_clean
                    total_records += len(events_clean)
                    st.success(f"✅ Downloaded {len(events_clean):,} events")
            
            # Create download
            if backup_data:
                st.subheader("📦 Download Backup")
                
                elapsed_time = datetime.now() - start_time
                
                # Show summary
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Total Records", f"{total_records:,}")
                
                with col2:
                    st.metric("Mode", "Ultra-Fast R-Style")
                
                with col3:
                    st.metric("Total Time", f"{elapsed_time.total_seconds()/60:.1f} min")
                
                # Single master file download for ultra-fast mode
                if 'master_file' in backup_data and not backup_data['master_file'].empty:
                    st.markdown("### 🎯 Master File Download")
                    st.info("📊 Comprehensive file with all data joined and processed (like your R workflow)")
                    
                    master_csv = backup_data['master_file'].to_csv(index=False)
                    st.download_button(
                        label="🎯 Download Master Comprehensive File",
                        data=master_csv,
                        file_name=f"{backup_id}_MASTER_COMPREHENSIVE.csv",
                        mime="text/csv",
                        help="Single comprehensive file with all data joined (like your R ER_dataPull.R output)"
                    )
                else:
                    st.warning("⚠️ No master file was created.")
                    
            else:
                st.warning("⚠️ No data was backed up.")
                
        except Exception as e:
            st.error(f"❌ Backup failed: {str(e)}")
            st.exception(e)

if __name__ == "__main__":
    main()
